# photo-book-toolkit

Machinery for turning a few thousand unsorted phone photos into a curated set
ready for a print service. Download, filter automatically, curate by hand in a
browser, export at print resolution.

Built for a 2025 year-in-review book (3,937 photos in, 591 out) and generalized
so the next one is a `git clone` rather than a rebuild.

**No photos live in this repo.** The image directories are gitignored. What is
tracked is the tooling, the conventions, and the manifests of past runs.

---

## Quick start

```bash
git clone <this-repo> my-photo-project
cd my-photo-project
pip3 install -r requirements.txt

# 1. Pull photos into raw/, organized however you like (month folders work well)
rclone copy "dropbox:/camera roll - 2025" raw/ \
  --include "*.jpg" --include "*.jpeg" --include "*.JPG" --include "*.JPEG" \
  --include "*.png" --include "*.PNG" \
  --include "*.heic" --include "*.HEIC" --include "*.heif" --include "*.HEIF" \
  --transfers 8 --progress

# 2. Automated filtering — scan first, then apply
python3 scripts/content_filter.py            # screenshots, documents  → report
python3 scripts/content_filter.py --apply
python3 scripts/triage.py                    # blur, burst duplicates  → report
python3 scripts/triage.py --apply

# 3. Manual curation in the browser
python3 scripts/browser.py                   # browse raw/, K to keep
python3 scripts/browser.py --cull            # second pass over selected/

# 4. Export at print resolution
python3 scripts/export_prep.py
python3 scripts/export_prep.py --apply
```

Every destructive script is two-step: it writes a report and moves nothing until
you pass `--apply`.

---

## Directory contract

The scripts locate everything relative to the repo root, so the folder names
below are load-bearing. Create them empty; nothing else is required.

| Folder      | Role                                                            |
|-------------|-----------------------------------------------------------------|
| `raw/`      | Originals, ideally in `01 - January/` style subfolders. Never modified. |
| `flagged/`  | Ambiguous auto-filter hits awaiting your eyes                    |
| `rejected/` | Auto-filter discards. A holding area, not a delete.              |
| `selected/` | Your keepers. Copied from `raw/`, never moved.                   |
| `exports/`  | Resized, upload-ready output                                     |
| `docs/`     | Filter reports written by the scripts                            |

`raw/` is treated as immutable. `browser.py` copies into `selected/`; it never
moves an original. That means you can rerun the whole pipeline from scratch
without re-downloading.

---

## The scripts

### `content_filter.py`
Finds screenshots (matched against known device screen dimensions) and photos of
documents or flyers. High-confidence hits go to `rejected/`; ambiguous ones —
a sign in the background, a partially-framed page — go to `flagged/` for review.

```bash
python3 scripts/content_filter.py --reject-threshold 0.75 --flag-threshold 0.45
```

### `triage.py`
Finds blurry frames (Laplacian variance) and near-duplicate bursts (perceptual
hash within a time window). Both thresholds are tunable, and both should be
calibrated per library — see Calibration below.

```bash
python3 scripts/triage.py --blur-threshold 25 --hash-distance 12
```

### `browser.py`
A local Flask lightbox for the part no script can do. Month sidebar, thumbnail
grid, keyboard-driven.

- `K` / `Space` — keep (or, in cull mode, remove)
- `←` / `→` — previous / next
- `Esc` — close the lightbox

Normal mode browses `raw/` and copies keepers into `selected/`. `--cull` browses
`selected/` for a second, harsher pass. Header title defaults to the project
folder name; override it:

```bash
PHOTO_PROJECT_TITLE="Iceland 2026" python3 scripts/browser.py
```

### `export_prep.py`
Resizes anything with a long side over 3,000px, copies the rest through, and
flags photos whose short side is under 800px as likely to print soft. Writes
`docs/export_report.txt`.

---

## Calibration

**Do not reuse thresholds across libraries.** The blur threshold especially is a
property of your camera and your shooting, not a universal constant. Run
`triage.py` in scan mode first and read the score distribution in the report,
then set the threshold near the bottom quartile.

For the 2025 run: median Laplacian variance was 71, the bottom 25% fell below
~27, and 25 was chosen. A different phone will land somewhere else entirely.

---

## Requirements

- Python 3.10+
- `pip3 install -r requirements.txt` (Flask, Pillow, numpy, pillow-heif)
- [rclone](https://rclone.org) for the download step, if pulling from a cloud
  provider. Connects over OAuth2 with no background daemon, which matters on
  machines where vendor desktop clients are prohibited.

HEIC/HEIF support comes from `pillow-heif`. Without it the scripts still run,
they just skip HEIC files.

---

## Past runs

`examples/` holds the manifests and reports from completed projects — no images,
just the record of what happened. See
[`examples/2025_year_in_review/`](examples/2025_year_in_review/) for a full
worked example with counts that reconcile end to end.
