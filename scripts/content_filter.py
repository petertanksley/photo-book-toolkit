#!/usr/bin/env python3
"""
Content filter — identifies screenshots and document/flyer photos in raw/.


Two tiers:
  REJECT  — screenshots matched to known device screen dimensions
  REJECT  — high-confidence pure document images (flyer fills the frame)
  FLAG    — ambiguous document-like images (sign in background, partial doc)
            moved to flagged/ for manual review

Usage:
    python3 scripts/content_filter.py            # scan + report only
    python3 scripts/content_filter.py --apply    # move files to rejected/ / flagged/
    python3 scripts/content_filter.py --reject-threshold 0.75 --flag-threshold 0.45
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR      = PROJECT_ROOT / "raw"
REJECTED_DIR = PROJECT_ROOT / "rejected"
FLAGGED_DIR  = PROJECT_ROOT / "flagged"
DOCS_DIR     = PROJECT_ROOT / "docs"

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}

# Known iOS/iPadOS screen dimensions (portrait, width x height).
# Landscape screenshots = swapped dimensions, added below.
_PORTRAIT_SIZES = {
    (1320, 2868),  # iPhone 16 Pro Max
    (1206, 2622),  # iPhone 16 Pro
    (1290, 2796),  # iPhone 16 Plus / 15 Pro Max / 15 Plus / 14 Pro Max / 14 Plus
    (1179, 2556),  # iPhone 16 / 15 Pro / 15 / 14 Pro
    (1284, 2778),  # iPhone 14 / 13 Pro Max / 12 Pro Max
    (1170, 2532),  # iPhone 13 Pro / 13 / 12 Pro / 12
    (1080, 2340),  # iPhone 13 mini / 12 mini
    (1242, 2688),  # iPhone 11 Pro Max / XS Max
    (1125, 2436),  # iPhone 11 Pro / XS / X
    (828,  1792),  # iPhone 11 / XR
    (750,  1334),  # iPhone 8 / SE (2nd gen)
    (1080, 1920),  # iPhone 8 Plus
    (2048, 2732),  # iPad Pro 12.9"
    (1668, 2388),  # iPad Pro 11"
    (1640, 2360),  # iPad Air
    (1488, 2266),  # iPad mini
}
SCREENSHOT_SIZES = _PORTRAIT_SIZES | {(h, w) for w, h in _PORTRAIT_SIZES}


# --- detection ------------------------------------------------------------

def is_screenshot(img: Image.Image) -> bool:
    img = ImageOps.exif_transpose(img)
    return img.size in SCREENSHOT_SIZES


def document_score(img: Image.Image) -> float:
    """
    Returns 0–1 indicating how document-like the image is.
    Combines three signals: light background ratio, low color saturation,
    and horizontal edge density (text lines).

    High score (> 0.75) = frame is dominated by a document/flyer.
    Mid score (0.45–0.75) = partial document or sign in a scene.
    Low score (< 0.45) = normal photo.
    """
    img = ImageOps.exif_transpose(img)
    small = img.convert("RGB").resize((256, 256), Image.LANCZOS)
    rgb = np.array(small, dtype=float)

    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

    # Ratio of near-white pixels (paper / light background)
    white_ratio = float(np.mean(lum > 215))

    # Color saturation per pixel: (max_channel - min_channel) / max_channel
    ch_max = rgb.max(axis=2)
    ch_min = rgb.min(axis=2)
    sat = np.where(ch_max > 1, (ch_max - ch_min) / ch_max, 0.0)
    mean_sat = float(np.mean(sat))

    # Horizontal edge density — text creates many horizontal transitions
    h_edges = np.abs(np.diff(lum, axis=0))
    h_edge_density = float(np.mean(h_edges > 15))

    # White + desaturated = strong document signal; edges add resolution
    white_component = min(1.0, white_ratio / 0.55)
    sat_component   = max(0.0, 1.0 - mean_sat / 0.18)
    edge_component  = min(1.0, h_edge_density / 0.12)

    # Both white AND low-sat must be present for a high score.
    # Edge density breaks ties between a blank white image and actual text.
    base = white_component * sat_component
    score = base * 0.75 + edge_component * 0.25

    return float(min(1.0, score))


# --- main logic -----------------------------------------------------------

def load_photos(raw_dir: Path) -> list[Path]:
    return sorted(
        p for p in raw_dir.iterdir()
        if p.suffix.lower() in PHOTO_EXTS
    )


def analyze(photos: list[Path], reject_threshold: float, flag_threshold: float):
    to_reject = []
    to_flag   = []
    clean     = []
    skipped   = []

    print(f"Scanning {len(photos)} photos...", flush=True)
    for i, path in enumerate(photos):
        if i % 100 == 0:
            print(f"  {i}/{len(photos)}", flush=True)
        try:
            with Image.open(path) as img:
                img.load()
                if is_screenshot(img):
                    to_reject.append((path, "screenshot", 1.0))
                    continue
                score = document_score(img)
        except Exception as e:
            skipped.append((path, str(e)))
            continue

        if score >= reject_threshold:
            to_reject.append((path, "document", score))
        elif score >= flag_threshold:
            to_flag.append((path, score))
        else:
            clean.append(path)

    return to_reject, to_flag, clean, skipped


def write_report(
    to_reject, to_flag, clean, skipped,
    reject_threshold, flag_threshold,
    report_path: Path, json_path: Path,
):
    lines = [
        f"CONTENT FILTER REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        f"Scanned:          {len(to_reject) + len(to_flag) + len(clean) + len(skipped)}",
        f"Skipped (errors): {len(skipped)}",
        f"→ REJECT:         {len(to_reject)}  "
          f"(screenshots + documents, threshold: {reject_threshold})",
        f"→ FLAG:           {len(to_flag)}  "
          f"(ambiguous, threshold: {flag_threshold})",
        f"→ Clean:          {len(clean)}",
        "",
    ]

    screenshots = [(p, r) for p, r, s in to_reject if r == "screenshot"]
    documents   = [(p, s) for p, r, s in to_reject if r == "document"]

    if screenshots:
        lines.append(f"SCREENSHOTS ({len(screenshots)})")
        lines.append("-" * 40)
        for p, _ in screenshots:
            lines.append(f"  {p.name}")
        lines.append("")

    if documents:
        lines.append(f"DOCUMENTS / FLYERS ({len(documents)})")
        lines.append("-" * 40)
        for p, s in sorted(documents, key=lambda x: -x[1]):
            lines.append(f"  {p.name:<45}  score: {s:.2f}")
        lines.append("")

    if to_flag:
        lines.append(f"FLAGGED FOR REVIEW ({len(to_flag)}) — moved to flagged/")
        lines.append("-" * 40)
        for p, s in sorted(to_flag, key=lambda x: -x[1]):
            lines.append(f"  {p.name:<45}  score: {s:.2f}")
        lines.append("")

    if skipped:
        lines.append("SKIPPED (could not open)")
        lines.append("-" * 40)
        for p, err in skipped:
            lines.append(f"  {p.name}  [{err}]")
        lines.append("")

    report_path.write_text("\n".join(lines))
    print(f"\nReport written to {report_path}")

    json_path.write_text(json.dumps({
        "reject": [str(p) for p, _, _ in to_reject],
        "flag":   [str(p) for p, _ in to_flag],
        "generated": datetime.now().isoformat(),
    }, indent=2))


def apply_filter(json_path: Path):
    if not json_path.exists():
        print("No content filter JSON found. Run without --apply first.")
        sys.exit(1)

    data = json.loads(json_path.read_text())
    REJECTED_DIR.mkdir(exist_ok=True)
    FLAGGED_DIR.mkdir(exist_ok=True)

    rejected = moved = flagged = 0
    for src_str in data["reject"]:
        src = Path(src_str)
        if src.exists():
            shutil.move(str(src), str(REJECTED_DIR / src.name))
            rejected += 1

    for src_str in data["flag"]:
        src = Path(src_str)
        if src.exists():
            shutil.move(str(src), str(FLAGGED_DIR / src.name))
            flagged += 1

    print(f"Moved {rejected} files to rejected/")
    print(f"Moved {flagged} files to flagged/")


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Move files to rejected/ and flagged/")
    parser.add_argument("--reject-threshold", type=float, default=0.75,
                        help="Document score above this → rejected/ (default 0.75)")
    parser.add_argument("--flag-threshold", type=float, default=0.45,
                        help="Document score above this → flagged/ (default 0.45)")
    args = parser.parse_args()

    DOCS_DIR.mkdir(exist_ok=True)
    json_path   = DOCS_DIR / "content_filter_latest.json"
    report_path = DOCS_DIR / f"content_filter_{datetime.now().strftime('%Y-%m-%d')}.txt"

    if args.apply:
        apply_filter(json_path)
        return

    if not HEIC_SUPPORT:
        print("Warning: pillow-heif not available — HEIC files will be skipped")

    photos = load_photos(RAW_DIR)
    if not photos:
        print(f"No photos found in {RAW_DIR}")
        sys.exit(1)

    to_reject, to_flag, clean, skipped = analyze(
        photos, args.reject_threshold, args.flag_threshold
    )
    write_report(
        to_reject, to_flag, clean, skipped,
        args.reject_threshold, args.flag_threshold,
        report_path, json_path,
    )


if __name__ == "__main__":
    main()
