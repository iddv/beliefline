# Changelog

All notable changes to Beliefline. Releases are tagged on GitHub; their notes list the merged
pull requests. Add a line under *Unreleased* in the same PR as the change.

## Unreleased

- Owner endpoints return 400 with field and detail, not 500, for an out-of-range time or sequence number or a non-string setting key.
- The database, its -wal/-shm files and the log are now owner-only (0600) and the data and backups directories 0700; existing installs are tightened on start.
- Maintenance files: issue labels, `.github/bears.yml`, `AGENTS.md`, `CLAUDE.md`, CI that runs
  AGENTS.md's commands, Dependabot for Actions, issue forms and a pull request template.

## 0.1.0 — 2026-10-11

- First release.
