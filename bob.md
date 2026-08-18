---
project: Photo Book Toolkit
type: web
status: dormant
priority: low
importance: medium
path: /Users/PTT2/Documents/GitHub/photo-book-toolkit
deadline: null
target: null
effort_remaining: none — toolkit is complete and shipped. Effort only resumes when a new photo project starts, at which point the work is per-project curation, not toolkit development.
weekly_commitment: 0h
last_updated: 2026-08-18
blockers: null
blocking_others: null
phase: complete
repo: https://github.com/petertanksley/photo-book-toolkit
sync: github
---

## Objectives

- Reusable machinery for turning a few thousand unsorted phone photos into a
  curated, print-ready set: rclone download, automated filtering (screenshots,
  documents, blur, burst duplicates), browser-based manual curation, and
  resize-for-print export
- Personal project, no deliverable owed to anyone
- Exists so photo project #2 is a `git clone` rather than a rebuild

## This Week

- **2026-08-18 — packaged and shipped.** Extracted the machinery from the 2025
  year-in-review project, genericized it, and pushed to GitHub. Scripts were
  already path-portable; only docstrings and the browser's hardcoded header
  title needed changing (now `PHOTO_PROJECT_TITLE`).
- Wrote filename manifests for all five pipeline stages of the 2025 run before
  deleting its 32 GB of images — Dropbox preserved the originals but not the
  curation decisions. Manifests are the recovery key and are committed.
- Found and corrected a stale per-month count table in the old project
  `CLAUDE.md` (claimed 1,925, actual 2,110) using the manifest as ground truth.
- Source folder `Non_work_work/current_projects/Personal_Projects/year_in_review`
  deleted in full. Nothing remains on OneDrive.

## Upcoming Milestones

- No scheduled work. Next activity is whenever a new photo project starts.

## Team & Dependencies

| Name | Role | Institution |
|------|------|-------------|
| Peter Tanksley | solo | personal |

## Notes

Dormant by design — this is finished infrastructure, not work in progress. It is
registered so that Bob surfaces it when the next photo project comes up, not so
it competes for weekly hours. Nothing here should ever appear as urgent.

`type: web` is the closest match among the bob templates because it carries the
`repo`/`sync` fields; this is a CLI toolkit, not a website.

**Backup dependency:** the 2025 originals live at `dropbox:/camera roll - 2025`
(verified 2026-08-18: 4,061 objects, 30.6 GiB). The local copies were deleted,
so that Dropbox folder is now the only copy of those photos. Worth keeping in
mind before any Dropbox housekeeping.

Repo is on GitHub, not OneDrive, per the standing rule against git repos on
synced storage.
