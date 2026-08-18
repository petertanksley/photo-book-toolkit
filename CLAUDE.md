# Photo Book Project — Working Conventions

Template. Clone the repo, fill in the bracketed fields, delete this line.

## Project Goal

Curate a large photo collection down to a set suitable for a printed book, then
export at print resolution for upload to a print service.

## Current Status (last updated [YYYY-MM-DD])

**Phase: [Download / Automated filtering / Manual curation / Export / Book layout]**

| Folder      | Count | Notes |
|-------------|-------|-------|
| `raw/`      | [n]   | Originals — do not modify |
| `selected/` | [n]   | Curated keepers |
| `flagged/`  | [n]   | Awaiting manual review |
| `rejected/` | [n]   | Auto-filtered out — holding area, not deleted |
| `exports/`  | [n]   | Upload-ready |

## Phases

1. **Download** — pull originals into `raw/`, organized into month subfolders
2. **Automated filtering** — `content_filter.py` then `triage.py`, scan before apply
3. **Manual curation** — `browser.py`, then a second `--cull` pass
4. **Export** — `export_prep.py --apply`
5. **Book layout** — upload `exports/` to the print service

## Working Conventions

- **Never modify files under `raw/`.** Copy to `selected/`; do not move. The
  pipeline must be re-runnable from scratch without re-downloading.
- **`rejected/` is a holding area, not permanent deletion.** Verify before emptying.
- **Every destructive script is two-step.** Scan writes a report and moves
  nothing; `--apply` acts. Never skip straight to `--apply` on a fresh library.
- **Calibrate thresholds per library.** Blur and duplicate thresholds are
  properties of the camera and the shooter, not universal constants. Read the
  scan report's score distribution before setting them.
- **Photos never enter git.** Image directories are gitignored at the repo root.
  If a photo shows up in `git status`, something is wrong with `.gitignore` —
  fix the ignore rule, do not `git add -f`.
- **Write a manifest before deleting images.** A cloud backup preserves your
  originals; it does not preserve which ones you chose. Filename manifests of
  `selected/`, `flagged/`, `rejected/`, and `exports/` are small, are text, and
  make the curation reproducible. Archive them under `examples/<run-name>/`.

## Target Sizing

Typical print-service book: 50–150 pages at 1–3 photos per page, so a final
count of roughly 100–300 images. A 591-photo selection is a large book — expect
to cull harder than feels comfortable.

## Settled Decisions

Record these as they are made, so the next run starts from evidence rather than
from scratch.

- **Source:** [cloud path, e.g. `dropbox:/camera roll - 2025`]
- **Download method:** [e.g. rclone v1.74.0 via OAuth2]
- **Blur threshold:** [n] — [how it was calibrated]
- **Duplicate hash distance:** [n]
- **Print service:** [name]
- **Curation workflow:** automated scripts first, then manual review

## Notes for Claude

- Prefer editing the scripts over writing one-off shell pipelines; the scripts
  are the durable artifact and the shell history is not.
- When counts are reported, reconcile them. `rejected + flagged + raw` should
  equal the original download, and `selected` should be a strict subset of
  `raw`. A mismatch means a file was moved when it should have been copied.
