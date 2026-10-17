# AGENTS.md — Beliefline

An append-only memory log you run next to your own AI agents. Agents report their memory changes to it over a local HTTP JSON API (or the CLI); Recorded events are append-only: no API or CLI path updates or deletes an event. Other stored data, such as settings and the owner token hash, can be overwritten, and direct database access can alter events undetected.. It records only what is reported to it and cannot see changes made elsewhere, so its history is only as complete as that reporting. You can then ask what an agent believed at any past moment, as far as it was reported, which events led to each belief, and which beliefs it held when it acted (e.g. sent an email at 03:14).

Built by an autonomous build (see NOTICE); maintained through GitHub issues by the owner, by
bears, and by any coding agent that reads this file. CLAUDE.md imports this file.

## What this is

- **For:** see SCOPE.md › Users
- **Does:** Beliefline is an append-only memory log that a developer runs next to their own AI agents. The agent writes every memory change to it and reads its current beliefs back through a local HTTP JSON API. Nothing is ever overwritten or deleted.
- **Stack:** Python 3.9+, standard library only, SQLite, one process on 127.0.0.1.
- **Scope:** `SCOPE.md` (users, numbered flows F1–F9, domain rules, definition of done).
  `ASSUMPTIONS.md` lists the questions the idea left open and what this version does.

## Setup, run, test

These commands are run by CI exactly as written (`.github/workflows/ci.yml`, job `agents-md`).
If you change a command, change it here in the same commit. A line marked `# serve` starts the
service; the check waits for it to answer on 127.0.0.1, then stops it.

```sh
./bin/beliefline start -d   # serve: http://127.0.0.1:7700/ (port: BELIEFLINE_PORT)
python3 -m unittest discover -s tests -v   # the product's own tests
python -m pip install pytest==8.3.3 && python -m pytest tests/acceptance   # the acceptance suite
```

- pytest is only needed for the acceptance suite; install it inside a virtual environment if
  your system Python refuses.
- Demo data: `see README` (empty install only).
- Backup and restore: `see README`, `see README`.
- Configuration: environment variables or `a config file` (see README › Configuration).

## Architecture in brief

| Path | Holds |
|---|---|
| `beliefline/__main__.py` | Runs the package as a command: `python -m beliefline`. |
| `beliefline/cli.py` | Operator command line (includes `anchor FILE` and `verify --anchor FILE`). Talks to the local service with the owner token. |
| `beliefline/config.py` | Configuration from environment variables (read at call time). |
| `beliefline/demo.py` | Demo data: two agents, ~300 events over the last 3 days, and the RSVP story. |
| `beliefline/server.py` | Local HTTP JSON API. |
| `beliefline/store.py` | SQLite-backed append-only event store: all rules (D1-D10) live here. |
| `beliefline/tz.py` | Display zone handling and flexible time input. |
| `tests/test_beliefline.py` | Run: python3 -m unittest discover -s tests -v. |
| `tests/acceptance/` | The acceptance suite: one file per behaviour, through the real interface (pytest). |
| `tests/acceptance/_helpers/` | Drivers the acceptance tests share (start the service, sign in, submit forms). |

Data lives in `./data`; the schema is versioned (the schema version is stored with the data; pending migrations run at start), and a
pre-migration backup is written before any upgrade.

An append-only memory log you run next to your own AI agents. Agents report their memory changes to it over a local HTTP JSON API (or the CLI); Recorded events are append-only: no API or CLI path updates or deletes an event.

## Conventions

- Standard library only. Do not add a dependency to fix a bug.
- Operator settings (binary business rules) are settings with an environment override; a new one
  goes in the Settings page, the README table, `ASSUMPTIONS.md`, and gets an acceptance test per
  value. Never hard-code one side of a business rule.
- Every behaviour has one acceptance test file, `tests/acceptance/test_<what_it_checks>.py`,
  with a plain docstring (what it checks, what is expected, where the rule comes from). Helpers
  live in `tests/acceptance/_helpers/` and drive the product's real interface.
- The server checks roles and CSRF on every state-changing request; templates escape everything.
- Plain words in user-facing files: no build-process jargon, no internal ids.

## The acceptance suite, readiness and security

- `tests/acceptance/README.md` lists the **known open items**: tests marked
  `xfail(strict=False)` because the behaviour is not there yet. **To fix one:** make the test
  pass, then delete the mark block at the end of its file and the line in that README. CI fails
  if an xfail test now passes and still carries the mark.
- `READINESS.md` is the operational scorecard (install, localhost default, empty start, first
  admin, backup, restart, logs, CI, docs). Keep it true: a change that moves an item from amber
  to green edits the row.
- `SECURITY.md` is the threat model, what was probed, and the findings with their status. A fix
  for a finding changes its status there and names its test. Report new weaknesses privately
  (see its last section), never in a public issue.

## Operator settings

Set by an Admin on the in-app Settings page; each has an environment variable that wins when set (README › Configuration). `ASSUMPTIONS.md` says why each exists.

| Setting | Values | Default |
|---|---|---|
| `writes.delete_absent` | recorded, refused | `recorded` |
| `agent.reactivate_keys` | restored, disabled | `restored` |
| `archive.operator_writes` | allowed, refused | `allowed` |
| `asof.seq_in_batch` | through_seq, whole_batch | `whole_batch` |

## Maintenance protocol (issues and labels)

Labels are the state; GitHub is the only record. `.github/labels.yml` defines them.

1. **Pick** an open issue labelled `go` with no assignee and no `claim:*` label (or one whose
   lease comment has expired and that has no open linked PR). `p1` before `p2` before `p3`.
2. **Claim** it: a person assigns themself; an agent adds `claim:agent` and a comment
   `<!-- bears:claim lease_until=<UTC+6h> branch=<branch> -->  Working on this.` Leave issues
   with `claim:bears` or an assignee alone.
3. **Branch** from `main`: `<who>/<N>-<slug>` (bears uses `bears/<N>-<slug>`).
4. **Reproduce first:** write `tests/acceptance/test_<slug>.py` that fails on `main` for the
   reason the issue describes. If you cannot make it fail, label `cannot-reproduce`, say why in a
   comment, remove your claim, and stop.
5. **Fix** with the smallest change that makes it pass without weakening another test.
6. **Verify:** run every command in *Setup, run, test*; the whole suite must be green; the
   README's quick start must still work as written.
7. **Documents:** update this file if a command, module or convention changed; `READINESS.md`
   or `SECURITY.md` if a row changed; add a line under *Unreleased* in `CHANGELOG.md`.
8. **Open a PR** with the template (`.github/pull_request_template.md`): what and why, the
   failing test's name, the verification you ran, and `Fixes #N`. Remove your claim label; the
   PR is now the lock. **Never push to `main`. Never change `.github/workflows/` in a fix PR.**
   Never commit a secret, a database file or demo credentials.
9. The owner reviews and merges on GitHub. A release follows (`.github/bears.yml` ›
   `release.on_merge`).

bears follows exactly these steps; its comments carry `<!-- bears:… -->` markers and the PR
label `bears`. Policy for this repo: `.github/bears.yml`.

## Provenance

Generated by an autonomous software build from a short product brief, with automated checks (its tests, a walk of every documented flow, a security review and a readiness review) before release. See `NOTICE`, `LICENSE` and `READINESS.md`.
