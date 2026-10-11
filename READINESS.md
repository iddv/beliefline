# Readiness

Where Beliefline stands on the way to production: each item was checked by doing it (installing from the README, starting it, backing it up and restoring it, ...) or by reading the repository. Green is ready, amber needs attention before production, red is a gap.

**13 green, 5 amber, 2 red**.

| item | status | why | next step to production |
|---|---|---|---|
| Clean install from the README | green | README command worked first time with no dependencies | - |
| The README's quick-start commands work as written (install, run, backup) | red | a README command fails as written: `beliefline backup file.db` (README.md:116) exits 127: bash: line 1: beliefline: command not found | make every quick-start command in the README work exactly as written on a fresh copy (fix the command or the script, or the README) |
| Listens on localhost unless configured | green | binds 127.0.0.1:7700 by default; HOST override works | - |
| Starts empty; demo data only on an explicit flag or command | green | fresh start has 0 agents, 0 events; demo only via `demo load` | - |
| First-run admin setup, no default password | green | random owner token printed once, saved 0600, only hash stored; no default password | - |
| Configuration by environment or file, every option documented | amber | env vars documented in a table, but BELIEFLINE_ACCESS_LOG (turns on request logging) is in the code and not in the README | document BELIEFLINE_ACCESS_LOG (or make request logging default and drop it) |
| Data location documented | green | README says data is in BELIEFLINE_DATA_DIR (default ~/.beliefline) and lists contents | - |
| Backup and restore work end to end | green | backup while running, restore into empty dir with service stopped, verify OK, data identical | - |
| Data survives a restart | green | data survives SIGTERM and SIGKILL, immediate restart serves at once | - |
| Starts again at once after a stop or a crash (services) | green | `./bin/beliefline start` on 127.0.0.1:7700 served again 0.11 s after a graceful stop and 0.11 s after a SIGKILL | - |
| Graceful shutdown | amber | SIGTERM exits in ~50ms and data is intact, but there is no documented stop command | add a `stop` command or document kill/SIGTERM and the pid location |
| Health endpoint (services) | amber | /v1/health answers without login but always returns {"ok": true} without touching the database, and is not in the README | check the DB (e.g. schema version) in the health response and document it |
| Readable logs, no secrets or personal data | green | fixed in this version (its test passes); it was: log has one untimestamped startup line; no request, command or error lines (request log is off unless an undocumented env var is set) | - |
| Schema changes and upgrades keep the data | amber | schema is versioned (meta.schema_version) with auto pre-migration backup, but only v1 exists and MIGRATIONS is empty, so the upgrade path is untested | ship and test a real v1->v2 migration before the first schema change |
| CI workflow installs the project and runs the tests | green | .github/workflows/test.yml installs and runs the tests | - |
| Dependencies locked or pinned | green | no third-party runtime dependencies (standard library only) | - |
| Sensible .gitignore, no build artefacts in the repository | red | no .gitignore | add a .gitignore for caches, virtual environments, build output and local data files |
| README covers install, configure, run, upgrade, backup and restore, troubleshooting and limitations | amber | missing sections: troubleshooting, limitations | add troubleshooting, limitations sections |
| The documented test commands run green, as written | green | 34 own test(s) pass; the acceptance suite is green (86 pass, 3 known open item(s) marked); the README's test commands run green as written | - |
| User-facing docs in plain words | green | no build-process jargon in README, ASSUMPTIONS, SECURITY, READINESS or the tests | - |

## Security

See `SECURITY.md`: 4 finding(s), 2 not fixed by a tested change (low 2).

## Known open items in the tests

Marked as expected failures in `tests/acceptance/` (the suite stays green):

- `test_database_file_data_dir_not_readable_other_local_users.py`: Known security issue (low): The database file in the data dir is not readable by other local users
- `test_flow_walk_7.py`: Not complete yet: Flow walk
- `test_out_range_report_time_range_non_string_setting_key_returns.py`: Known security issue (low): An out-of-range report time range or a non-string setting key returns 400, never 500
