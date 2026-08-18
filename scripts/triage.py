#!/usr/bin/env python3
"""
Photo triage — finds blurry images and near-duplicate bursts in raw/.
Scans raw/ for blurry images and near-duplicate bursts, then writes a report.
Nothing is moved until you run with --apply.

Usage:
    python3 scripts/triage.py            # scan + report only
    python3 scripts/triage.py --apply    # move flagged files to rejected/
    python3 scripts/triage.py --blur-threshold 100  # adjust sensitivity
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR      = PROJECT_ROOT / "raw"
REJECTED_DIR = PROJECT_ROOT / "rejected"
DOCS_DIR     = PROJECT_ROOT / "docs"

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}

# --- image analysis -------------------------------------------------------

def laplacian_variance(img: Image.Image) -> float:
    gray = np.array(img.convert("L"), dtype=float)
    lap = (
        gray[:-2, 1:-1] + gray[2:, 1:-1]
        + gray[1:-1, :-2] + gray[1:-1, 2:]
        - 4 * gray[1:-1, 1:-1]
    )
    return float(np.var(lap))


def dhash(img: Image.Image, size: int = 8) -> np.ndarray:
    img = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = np.array(img, dtype=np.int16)
    return (px[:, 1:] > px[:, :-1]).flatten()


def hash_distance(h1: np.ndarray, h2: np.ndarray) -> int:
    return int(np.sum(h1 != h2))


# --- filename parsing ------------------------------------------------------

def parse_timestamp(path: Path) -> datetime | None:
    # Expects filenames like "2025-01-01 13.23.53.jpg"
    stem = path.stem  # "2025-01-01 13.23.53"
    try:
        return datetime.strptime(stem, "%Y-%m-%d %H.%M.%S")
    except ValueError:
        return None


# --- main logic -----------------------------------------------------------

def load_photos(raw_dir: Path) -> list[Path]:
    return sorted(
        p for p in raw_dir.iterdir()
        if p.suffix.lower() in PHOTO_EXTS
    )


def analyze(photos: list[Path], blur_threshold: float, dup_seconds: int, dup_bits: int):
    """
    Returns:
        results   — list of dicts with path, blur_score, hash, timestamp
        blurry    — set of paths flagged as blurry
        dup_groups — list of lists; each inner list is a group of near-duplicate
                     paths sorted sharpest-first (index 0 = keep)
    """
    results = []
    skipped = []

    print(f"Scanning {len(photos)} photos...", flush=True)
    for i, path in enumerate(photos):
        if i % 100 == 0:
            print(f"  {i}/{len(photos)}", flush=True)
        try:
            with Image.open(path) as img:
                img.load()
                score = laplacian_variance(img)
                h = dhash(img)
        except Exception as e:
            skipped.append((path, str(e)))
            continue

        results.append({
            "path": path,
            "blur_score": score,
            "hash": h,
            "timestamp": parse_timestamp(path),
        })

    # Blurry
    blurry = {r["path"] for r in results if r["blur_score"] < blur_threshold}

    # Near-duplicate groups via time window + hash distance
    dup_groups = []
    visited = set()

    time_sorted = sorted(
        (r for r in results if r["timestamp"] is not None),
        key=lambda r: r["timestamp"],
    )
    window = timedelta(seconds=dup_seconds)

    for i, ref in enumerate(time_sorted):
        if ref["path"] in visited:
            continue
        group = [ref]
        for j in range(i + 1, len(time_sorted)):
            cand = time_sorted[j]
            if cand["timestamp"] - ref["timestamp"] > window:
                break
            if cand["path"] in visited:
                continue
            if hash_distance(ref["hash"], cand["hash"]) <= dup_bits:
                group.append(cand)
                visited.add(cand["path"])
        if len(group) > 1:
            visited.add(ref["path"])
            group.sort(key=lambda r: r["blur_score"], reverse=True)
            dup_groups.append([r["path"] for r in group])

    return results, blurry, dup_groups, skipped


def write_report(
    results, blurry, dup_groups, skipped,
    blur_threshold, dup_seconds, dup_bits,
    report_path: Path, json_path: Path,
):
    flagged_dups = {p for g in dup_groups for p in g[1:]}
    total_flagged = blurry | flagged_dups
    kept = {r["path"] for r in results} - total_flagged

    lines = [
        f"TRIAGE REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        f"Scanned:           {len(results)}",
        f"Skipped (errors):  {len(skipped)}",
        f"Flagged blurry:    {len(blurry)}  (threshold: {blur_threshold})",
        f"Flagged duplicate: {len(flagged_dups)}  ({len(dup_groups)} groups, "
        f"window: {dup_seconds}s, bits: {dup_bits}/64)",
        f"Total flagged:     {len(total_flagged)}",
        f"Remaining (keep):  {len(kept)}",
        "",
    ]

    if blurry:
        lines.append("BLURRY")
        lines.append("-" * 40)
        for r in sorted(results, key=lambda x: x["blur_score"]):
            if r["path"] in blurry:
                lines.append(f"  {r['path'].name:<45}  score: {r['blur_score']:.1f}")
        lines.append("")

    if dup_groups:
        lines.append("DUPLICATE GROUPS")
        lines.append("-" * 40)
        for g in dup_groups:
            lines.append(f"  KEEP : {g[0].name}")
            for p in g[1:]:
                lines.append(f"  FLAG : {p.name}")
            lines.append("")

    if skipped:
        lines.append("SKIPPED (could not open)")
        lines.append("-" * 40)
        for path, err in skipped:
            lines.append(f"  {path.name}  [{err}]")
        lines.append("")

    report_path.write_text("\n".join(lines))
    print(f"\nReport written to {report_path}")

    # Machine-readable version for --apply
    json_path.write_text(json.dumps({
        "flagged": [str(p) for p in total_flagged],
        "generated": datetime.now().isoformat(),
    }, indent=2))


def apply_triage(json_path: Path):
    if not json_path.exists():
        print("No triage JSON found. Run without --apply first.")
        sys.exit(1)

    data = json.loads(json_path.read_text())
    flagged = [Path(p) for p in data["flagged"]]
    REJECTED_DIR.mkdir(exist_ok=True)

    moved = 0
    for src in flagged:
        if src.exists():
            dst = REJECTED_DIR / src.name
            shutil.move(str(src), str(dst))
            moved += 1

    print(f"Moved {moved} files to rejected/")


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Move flagged files to rejected/ (reads existing report)")
    parser.add_argument("--blur-threshold", type=float, default=150,
                        help="Laplacian variance below this = blurry (default 150)")
    parser.add_argument("--dup-seconds", type=int, default=10,
                        help="Time window for duplicate grouping in seconds (default 10)")
    parser.add_argument("--dup-bits", type=int, default=12,
                        help="Max hash bits different to count as duplicate (default 12/64)")
    args = parser.parse_args()

    DOCS_DIR.mkdir(exist_ok=True)
    json_path   = DOCS_DIR / "triage_latest.json"
    report_path = DOCS_DIR / f"triage_{datetime.now().strftime('%Y-%m-%d')}.txt"

    if args.apply:
        apply_triage(json_path)
        return

    if not HEIC_SUPPORT:
        print("Warning: pillow-heif not available — HEIC files will be skipped")

    photos = load_photos(RAW_DIR)
    if not photos:
        print(f"No photos found in {RAW_DIR}")
        sys.exit(1)

    results, blurry, dup_groups, skipped = analyze(
        photos, args.blur_threshold, args.dup_seconds, args.dup_bits
    )
    write_report(
        results, blurry, dup_groups, skipped,
        args.blur_threshold, args.dup_seconds, args.dup_bits,
        report_path, json_path,
    )


if __name__ == "__main__":
    main()
