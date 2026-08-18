#!/usr/bin/env python3
"""
export_prep.py — Prepare selected/ photos for print-service upload.

Actions:
  1. Flags photos below MIN_SHORT_SIDE (800px) as low-resolution.
  2. Resizes photos with long side > MAX_LONG_SIDE (3000px) down proportionally.
  3. Copies (or resizes) everything to exports/.
  4. Prints a summary report; writes docs/export_report.txt.

Usage:
  python3 scripts/export_prep.py          # dry run — report only
  python3 scripts/export_prep.py --apply  # write files to exports/
"""

import argparse
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

# --- Config ------------------------------------------------------------------
MIN_SHORT_SIDE = 800    # pixels; below this → flagged as low-res
MAX_LONG_SIDE  = 3000   # pixels; above this → resized down
JPEG_QUALITY   = 92     # quality for resized output
# -----------------------------------------------------------------------------

ROOT     = Path(__file__).resolve().parent.parent
SRC      = ROOT / "selected"
DST      = ROOT / "exports"
DOCS     = ROOT / "docs"


def process(apply: bool) -> None:
    photos = sorted(SRC.glob("*.jpg")) + sorted(SRC.glob("*.JPG"))

    if not photos:
        print("No JPG files found in selected/.")
        sys.exit(1)

    low_res   = []
    resized   = []
    copied_as_is = []
    errors    = []

    if apply:
        DST.mkdir(exist_ok=True)

    for src_path in photos:
        try:
            with Image.open(src_path) as img:
                corrected = ImageOps.exif_transpose(img)
                w, h = corrected.size
                short = min(w, h)
                long  = max(w, h)

                flagged = short < MIN_SHORT_SIDE
                needs_resize = long > MAX_LONG_SIDE

                if flagged:
                    low_res.append((src_path.name, w, h))

                dst_path = DST / src_path.name

                if apply:
                    if needs_resize:
                        scale = MAX_LONG_SIDE / long
                        new_w = round(w * scale)
                        new_h = round(h * scale)
                        resized_img = corrected.resize((new_w, new_h), Image.LANCZOS)
                        resized_img.save(dst_path, "JPEG", quality=JPEG_QUALITY)
                        resized.append((src_path.name, f"{w}x{h}", f"{new_w}x{new_h}"))
                    else:
                        corrected.save(dst_path, "JPEG", quality=JPEG_QUALITY)
                        copied_as_is.append(src_path.name)
                else:
                    if needs_resize:
                        scale = MAX_LONG_SIDE / long
                        new_w = round(w * scale)
                        new_h = round(h * scale)
                        resized.append((src_path.name, f"{w}x{h}", f"{new_w}x{new_h}"))
                    else:
                        copied_as_is.append(src_path.name)

        except Exception as e:
            errors.append((src_path.name, str(e)))

    # --- Report ---------------------------------------------------------------
    lines = []
    lines.append("=" * 60)
    lines.append("EXPORT PREP REPORT")
    lines.append(f"Mode: {'APPLY' if apply else 'DRY RUN'}")
    lines.append("=" * 60)
    lines.append(f"\nTotal photos in selected/: {len(photos)}")
    lines.append(f"  Will resize (long side > {MAX_LONG_SIDE}px): {len(resized)}")
    lines.append(f"  Copy as-is (already ≤ {MAX_LONG_SIDE}px): {len(copied_as_is)}")
    lines.append(f"  Errors: {len(errors)}")

    lines.append(f"\n--- LOW-RES FLAGS ({len(low_res)} photos, short side < {MIN_SHORT_SIDE}px) ---")
    if low_res:
        lines.append("  These may print soft in collage slots — review before uploading.")
        for name, w, h in low_res:
            lines.append(f"  {name}  ({w}x{h}px, short={min(w,h)}px)")
    else:
        lines.append("  None — all photos clear the resolution floor.")

    if errors:
        lines.append(f"\n--- ERRORS ---")
        for name, msg in errors:
            lines.append(f"  {name}: {msg}")

    if apply:
        lines.append(f"\nOutput written to: exports/  ({len(resized) + len(copied_as_is)} files)")
    else:
        lines.append("\nRun with --apply to write files to exports/.")

    lines.append("=" * 60)

    report = "\n".join(lines)
    print(report)

    DOCS.mkdir(exist_ok=True)
    (DOCS / "export_report.txt").write_text(report)
    print(f"\nReport saved to docs/export_report.txt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="Write resized/copied files to exports/ (default: dry run)")
    args = parser.parse_args()
    process(apply=args.apply)


if __name__ == "__main__":
    main()
