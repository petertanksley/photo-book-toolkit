# 2025 Year in Review — worked example

The run this toolkit was built for. Completed May 2026; photo book printed via
Shutterfly. Source images were deleted from local disk in August 2026 — the
originals live in Dropbox at `dropbox:/camera roll - 2025`, and the manifests
here record what was done with them.

## Counts

| Stage       | Count | Notes |
|-------------|-------|-------|
| Downloaded  | 3,937 | `dropbox:/camera roll - 2025`, via rclone |
| Auto-rejected | 1,812 | screenshots, documents, blur, burst duplicates |
| Flagged for review | 15 | reviewed manually — no keepers, all discarded |
| Survived to `raw/` | 2,110 | organized into 12 month folders |
| Selected | 591 | two manual curation passes |
| Exported | 591 | resized to 3,000px max long side, 898 MB |

These reconcile exactly:

```
rejected 1,812 + flagged 15 + raw 2,110 = 3,937   ← the original download
selected 591 ⊂ raw 2,110                          ← verified, all 591 basenames present
```

Of the 591 exports, 530 were downsized and 61 copied through unchanged. 34 were
flagged low-resolution (short side under 800px) and kept anyway as acceptable
for collage slots — they are itemized in `reports/export_report.txt`.

## Settled decisions

- **Year:** 2025
- **Source:** `dropbox:/camera roll - 2025`
- **Download:** rclone v1.74.0 via Homebrew, OAuth2. The Dropbox desktop client
  is prohibited on this machine by university policy; rclone needs no daemon.
- **Blur threshold:** 25 (Laplacian variance). Calibrated against this library:
  median score 71, bottom quartile below ~27.
- **Print service:** Shutterfly

## Contents

- `manifests/` — filename lists for each stage. `raw.txt` paths include the
  month folder; `selected.txt` and `flagged.txt` are flat; `exports.txt` is
  month-foldered.
- `reports/` — the filter and export reports the scripts wrote at the time.

## Reconstructing this run

If the selection ever needs rebuilding:

```bash
rclone copy "dropbox:/camera roll - 2025" raw_all/
mkdir -p selected
while IFS= read -r p; do
  find raw_all -name "$(basename "$p")" -exec cp {} selected/ \;
done < examples/2025_year_in_review/manifests/selected.txt
python3 scripts/export_prep.py --apply
```

The manifests are the reason this is possible. Dropbox preserved the photos; it
did not preserve which 591 of 3,937 were worth printing.
