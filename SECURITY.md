# Security

How Beliefline was reviewed for security before its first release, what was found, and what is still open.

## Threat model

Local-first service on 127.0.0.1:7700. Owner token (CLI) can do everything; per-agent bearer keys touch only their own agent. Only /v1/health is unauthenticated. Tokens are 256-bit random and stored as SHA-256. Python stdlib only, SQLite store.

### Entry points

| entry point | who can reach it | authentication | notes |
|---|---|---|---|
| GET /v1/health | public | none | intentionally public |
| /v1/whoami, /v1/events, /v1/beliefs, /v1/actions, /v1/history, /v1/retract | public | agent bearer key | scoped to the key's agent |
| GET /v1/events/{id} | public | agent key or owner token | agent sees only its own |
| all other /v1/* (agents, keys, export, verify, backup, settings, token rotate, demo load, explain, asof, report, diff) | admin | owner token | backup writes to any path the service user can write |
| CLI (bin/beliefline) | local | owner token in ~/.beliefline/cli.json (0600) |  |
| data dir ~/.beliefline | local | filesystem permissions | see s3 |

### Assets

| asset | kind | where |
|---|---|---|
| agent memory history (personal data) | personal data | beliefline.db |
| owner token and agent keys (hashes only) | secrets | db, cli.json |
| integrity of the event chain | integrity | db |
| service availability | availability | HTTP server |

## What was checked, and how

The product was started as its README says and probed while running.

| area | check | result | evidence |
|---|---|---|---|
| authN/authZ | all 36 routes anonymously | pass | all return 401 except /v1/health |
| authN/authZ | agent key on owner routes (status, agents, keys, export, rotate, settings, backup, operator set on another agent) | pass | all 401 |
| authN/authZ | agent 1 reading/citing agent 2's event ids | pass | 404 / 400 unknown cause; no cross-agent access |
| hostile HTTP | Content-Length abc / -1 / 99999999999999999999 / 20000000 | pass | 400 / 400 / 413 / 413 immediately; body not read (limit 16 MiB) |
| hostile HTTP | malformed JSON, 10,000-level nested JSON (top-level and in value), NaN, 1e999, huge/negative expected_version, 5000-digit ids | pass | all 400 (one 409), no crash |
| hostile HTTP | idle / half-sent requests and slow bodies | fail | 300 partial requests and a 10 MB Content-Length with 1 byte sent hold threads with no timeout (s1) |
| hostile HTTP | owner endpoints with out-of-range numbers or wrong types | fail | report to=99999999999999999 and PUT /v1/settings with a list key return 500 (s4) |
| injection | SQL quotes and ' OR 1=1 -- in key, reason, idempotency_key, prefix, ids | pass | parameterised; rejected 400 or stored literally |
| injection | stored/reflected XSS | n/a | no HTML is served; all responses are JSON |
| injection | path traversal in agent names/ids; backup path | pass | traversal in names gives 404. Backup path is owner-chosen by design |
| injection | CSRF / open redirect / cookies / sessions | n/a | bearer-token API, no cookies, forms or redirects |
| authentication | repeated wrong tokens | fail | 300 wrong tokens all answered 401 with no limit (s2) |
| authentication | token storage | pass | 256-bit random tokens, SHA-256, constant-time compare; slow hash unnecessary for high-entropy tokens |
| secrets | default credentials / hard-coded secrets | pass | owner token random on first run, printed once; none in code; cli.json is 0600 |
| secrets | file permissions | fail | beliefline.db is 0644 and the data dir 0775 (s3) |
| dependencies | pip-audit | pass | no third-party dependencies |
| error pages | bad ids, bad input | pass | JSON errors without tracebacks; 500 bodies are generic (traceback goes to the log only) |

## Findings

| | severity | finding | status |
|---|---|---|---|
| S1 | medium | No socket timeout: idle or slow connections hold server threads forever | fixed (a test checks it) |
| S2 | medium | No rate limit or lockout on wrong owner token / agent key | fixed (a test checks it) |
| S3 | low | Database and data directory readable by other local users | fixed |
| S4 | low | Owner endpoints return 500 on out-of-range or wrongly typed input | fixed |

### S3 (low): Database and data directory readable by other local users

- Where: beliefline/store.py (db was created with default umask; now 0600, data dir and backups 0700, tightened on every start)
- What happens: any local user can read all agent memories and the key hashes
- What should happen: db 0600, dir 0700 (backups and cli.json already are 0600)
- Reproduce: `ls -la ~/.beliefline  ->  beliefline.db -rw-r--r--, dir drwxrwxr-x`
- Test: `tests/acceptance/test_database_file_data_dir_not_readable_other_local_users.py` 

### S4 (low): Owner endpoints return 500 on out-of-range or wrongly typed input

- Where: store.report/iso (store.py:46,926); store.put_setting (store.py:404)
- What happens: 500 internal error; traceback (year out of range / unhashable list) in the log
- What should happen: 400 with field and detail
- Reproduce: `curl -H "Authorization: Bearer $OWNER" '127.0.0.1:7700/v1/agents/a1/report?from=0&to=99999999999999999'; curl -X PUT -d '{"key":["x"],"value":"y"}' /v1/settings`
- Test: `tests/acceptance/test_out_range_report_time_range_non_string_setting_key_returns.py` (passes)

## Dependency audit

- Tool: pip-audit; result: no_dependencies.
- pyproject dependencies = []; stdlib only

## Known limits

- This was a time-boxed review of v1 by one reviewer with the code and a running copy: scripted probes and manual checks, not a penetration test or an external audit.
- TLS and non-localhost deployment not tested
- Memory growth under large (16 MiB) bodies not measured; the 16 MiB cap is applied before reading
- Concurrency/chain-integrity correctness was not reviewed in depth
- see Findings limits (fd/thread exhaustion) were not driven to an actual outage

## Reporting a security issue

Please report security problems privately, not in a public issue: use the repository host's private vulnerability reporting (on GitHub: Security, then Report a vulnerability), or write to the maintainers directly. Include the version, the steps to reproduce and what an attacker could do. You will get an answer within a few working days.
