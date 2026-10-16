# Changelog

All notable changes to Beliefline. Releases are tagged on GitHub; their notes list the merged
pull requests. Add a line under *Unreleased* in the same PR as the change.

## Unreleased

- The package version (pyproject and `beliefline.__version__`) now matches the newest release tag, 0.1.2; a test keeps them equal.

- The database, its -wal/-shm files and the log are now owner-only (0600) and the data and backups directories 0700; existing installs are tightened on start.
- Maintenance files: issue labels, `.github/bears.yml`, `AGENTS.md`, `CLAUDE.md`, CI that runs
  AGENTS.md's commands, Dependabot for Actions, issue forms and a pull request template.

## 0.1.2

- Patch release.

## 0.1.1

- Patch release.

## 0.1.0 — 2026-10-11

- First release.
