# Beliefline

An append-only memory log you run next to your own AI agents. Agents report their memory changes to it over a local HTTP JSON API (or the CLI); Recorded events are append-only: no API or CLI path updates or deletes an event. Other stored data, such as settings and the owner token hash, can be overwritten, and direct database access can alter events undetected.. It records only what is reported to it and cannot see changes made elsewhere, so its history is only as complete as that reporting. You can then ask what an agent believed at any past moment, as far as it was reported, which events led to each belief, and which beliefs it held when it acted (e.g. sent an email at 03:14).

Python 3.9+ standard library only: no dependencies to install.

## Install and start (one command)

```
./bin/beliefline start -d
```

This creates the data directory (`~/.beliefline`), applies the schema, starts the service in the background on `127.0.0.1:7700`, and on first run prints the **owner token once** (also written to `~/.beliefline/cli.json`, mode 0600; only a hash is stored in the database). Then:

```
./bin/beliefline status      # service up, schema version, 0 agents, 0 events, chain verified
./bin/beliefline demo load   # optional: 2 agents, ~300 events, the RSVP story; prints one demo key per agent
```

Optionally `pip install .` puts a `beliefline` command on your PATH (`beliefline start -d`). `beliefline start` without `-d` runs in the foreground.

Run the tests: `python3 -m unittest discover -s tests -v`

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BELIEFLINE_HOST` / `BELIEFLINE_PORT` | `127.0.0.1` / `7700` | bind address |
| `BELIEFLINE_DATA_DIR` | `~/.beliefline` | database, CLI config, logs, automatic migration backups |
| `BELIEFLINE_TZ` | (setting) | display zone: `utc`, `local` or an IANA name; overrides `display.time_zone` |
| `BELIEFLINE_URL` | `http://HOST:PORT` | service URL for the CLI |
| `BELIEFLINE_OWNER_TOKEN` | from `cli.json` | owner token for the CLI |
| `BELIEFLINE_WRITES_VERSION_CHECK` | `optional` | `optional` / `required`: agent writes must carry `expected_version` |
| `BELIEFLINE_WRITES_UNCHANGED_SET` | `record` | `record` / `skip`: a `set` repeating the current value |
| `BELIEFLINE_RETRACT_ALLOWED_BY` | `operator_only` | `operator_only` / `operator_and_agent` |
| `BELIEFLINE_DISPLAY_TIME_ZONE` | `local` | `local` / `utc` |
| `BELIEFLINE_MAX_BATCH`, `_MAX_VALUE_BYTES`, `_MAX_REASON`, `_MAX_SOURCE`, `_MAX_KEYS`, `_MAX_READ_KEYS`, `_EXPLAIN_DEPTH` | 100, 65536, 2000, 200, 10, 50, 10 | limits |
| `WRITES_DELETE_ABSENT` (setting `writes.delete_absent`; overrides everything) | `recorded` | whole system. `recorded`: deleting a key with no current belief (never set or already deleted) appends a delete event and bumps the version. `refused`: such a delete is a 400 (`nothing to delete`, field `events[i].key`) and the whole batch writes nothing. |
| `AGENT_REACTIVATE_KEYS` (setting `agent.reactivate_keys`; overrides everything) | `restored` | whole system. `restored`: after `agent reactivate`, keys that were not explicitly revoked work again. `disabled`: keys created before the reactivation stay unusable (401 `key disabled; ...`) and new keys must be issued; keys issued after reactivation work. Checked on every request. |
| `ARCHIVE_OPERATOR_WRITES` (setting `archive.operator_writes`; overrides everything) | `allowed` | whole system. `allowed`: the operator can `set` and `retract` on archived agents. `refused`: those operator writes are rejected with 409 `agent archived` until the agent is reactivated (operator reads always work). |
| `ASOF_SEQ_IN_BATCH` (setting `asof.seq_in_batch`; overrides everything) | `whole_batch` | whole system. `asof #N` where N falls inside a batch: `whole_batch` includes the entire batch (all events of that agent with the same `recorded_at` as #N); `through_seq` includes events only up to N. Applies to every `#seq` time (`asof`, `diff`, `beliefs`). |

Settings whose variable has no `BELIEFLINE_` prefix (listed above) are system-wide and that variable wins over a value stored with `config set`. Settings can also be changed at runtime and are then stored in the database (they win over the env defaults): `beliefline config list`, `beliefline config set retract.allowed_by operator_and_agent`.

## Connect an agent

```
beliefline agent create assistant
beliefline key issue assistant --label prod      # key shown once
curl -H "Authorization: Bearer $KEY" localhost:7700/v1/whoami
```

### Agent API (bearer key; a key only touches its own agent)

| | |
|---|---|
| `GET /v1/whoami` | agent name |
| `POST /v1/events` | one event, a list, or `{"events":[...]}` (max 100, atomic). Event: `type` (`set`/`delete`), `key`, `value` (set), optional `reason`, `source`, `caused_by` (event ids), `occurred_at` (ISO 8601; stored, never used for ordering), `idempotency_key`, `expected_version` (`0` = key must not currently exist). Returns per event: `id`, `seq`, `version`, `recorded_at`, `hash`, and the resulting `belief`. 201 if anything was written, 200 for pure retries. |
| `GET /v1/beliefs` | `?key=` one key (404 if unset/deleted), `?prefix=`, or all. Each: `value`, `version` (use for `expected_version`), `event_id`, `event_version`, `recorded_at`, `reason`, `source`. |
| `POST /v1/actions` | `kind`, `summary`, optional `payload`, `read_keys`, `caused_by`. Returns the action id and the belief snapshot (event id + version per read key, `absent` if none), computed inside the same write. |
| `GET /v1/history?key=` | every event on a key, with retraction state |
| `GET /v1/events/{id}` | one of its own events |
| `POST /v1/retract` | `{event_id, reason}`; 403 unless `retract.allowed_by` = `operator_and_agent` |

Errors are `{"error","field","detail"}`. Every 400/409/413 from an agent is also stored in a separate rejected-writes log (shown in `report`).

Semantics worth knowing:
- A key's **version** starts at 1 and increments on every set, delete or retract affecting it. A version mismatch returns 409 with `current_version` and `current_value` and writes nothing. `expected_version: 0` passes when the key currently has no belief (never set, or deleted).
- **Belief rule (D6):** for a key at instant T, take its events recorded ≤ T, drop every event with an effective retraction recorded ≤ T (a retraction is effective unless itself retracted as of T), the last remaining event decides: `set` = its value, `delete` = absent.
- `recorded_at` is server time (UTC, ms, never decreasing per agent). All as-of queries use it.

## Operator CLI

Every command accepts `--json`. Errors are one line on stderr with a non-zero exit code.

```
beliefline status | init | start [-d] | token rotate | token reset
beliefline agent create|list|rename|archive|reactivate ...
beliefline key issue <agent> [--label L] | key list [agent] | key revoke <key-id>
beliefline beliefs <agent> [--key K | --prefix P]
beliefline asof <agent> <time> [--key K | --prefix P]     # time: 2026-10-09T03:14:00+02:00 | "2026-10-09 03:14" | "yesterday 03:14" | "2 days ago 22:10" | #<seq>
beliefline history <agent> <key>
beliefline actions <agent> [--from T] [--to T] [--kind email]
beliefline explain <event-or-action-id>                   # snapshot + history of each read key + caused_by chain (depth 10)
beliefline set <agent> <key> '<json>' --reason "..."      # operator-authored set
beliefline retract <event-id> --reason "..."              # retract a retraction to undo it
beliefline report <agent> [--day YYYY-MM-DD]              # default yesterday
beliefline diff <agent> <t1> <t2>
beliefline export <agent|--all> [--from T] [--to T] > events.jsonl
beliefline verify [agent]
beliefline anchor FILE
beliefline verify --anchor FILE
beliefline config list | config set <key> <value>
beliefline backup <file> | restore <file>
```

### The 3:14am question (with the demo data)

```
beliefline asof assistant "yesterday 03:14" --key rsvp/dana-wedding   # "yes", set 02:47, reason "summarized from old thread"
beliefline asof assistant "2 days ago 23:00" --key rsvp/dana-wedding  # "no"
beliefline actions assistant --kind email.send --from "yesterday 03:00" --to "yesterday 04:00"
beliefline explain act_<id>
beliefline retract <the 02:47 event id> --reason "bad summary"       # beliefs now say "no"; asof 03:14 still says "yes"
beliefline report assistant ; beliefline diff assistant "2 days ago 23:00" "yesterday 04:00"
```

## Integrity

- **Append-only:** no API or CLI path updates or deletes an event; SQLite triggers also reject `UPDATE`/`DELETE` on `events`. Corrections are new `set`/`retract` events.
- **Hash chain:** each event has a gap-free per-agent `seq` and `hash = SHA-256(prev_hash + canonical JSON of the event)`, where the canonical JSON is the exported event minus `agent`, `prev_hash`, `hash` (keys sorted, compact separators). The genesis `prev_hash` is 64 zeros. Each agent's head (`last_seq`, `last_hash`) is also kept so truncation at the tail is detected.
- **`verify`** recomputes every chain and also replays derived data: key versions, retract targets, cause references and each action's stored snapshot. There is no separate belief cache: beliefs and counts are always computed from the events. It prints `OK, N events` or the first broken sequence number per agent and exits non-zero.
  `verify` can catch an event that is edited without recomputing the chain. The hashes are unkeyed SHA-256 stored in the same database, so someone with direct database write access can rewrite events and their hashes and `verify` will not detect that, unless the chain heads were copied somewhere outside the database. `beliefline anchor FILE` writes each agent's `(last_seq, last_hash)` to FILE (it refuses to overwrite); copy it to another disk or a git repo, and later `beliefline verify --anchor FILE` fails, naming the agent and sequence, if the anchored event is gone or changed. Both take `--json`. The anchor is only as safe as where you keep it. To see the naive case yourself, drop the trigger first (`sqlite3 ~/.beliefline/beliefline.db 'drop trigger events_no_update'`), edit an event, run `beliefline verify`.
- **Concurrency/durability:** writes run in `BEGIN IMMEDIATE` transactions with `synchronous=FULL` (WAL); acknowledged means on disk. Two writers with the same `expected_version`: exactly one wins, the other gets 409.

## Backup, restore, upgrades

- `beliefline backup file.db` writes a consistent snapshot while the service runs (refuses to overwrite).
- `beliefline restore file.db` works only into an empty data dir with the service stopped, verifies the chain before installing, and keeps the backup's owner token (use `beliefline token reset` if you lost it).
- Schema is versioned; on start, forward migrations run after an automatic backup into `<data dir>/backups/`. Migrations never alter event content.

## Notes / interpretation choices

- `asof` before the agent's first event (or on an agent with no events) prints "agent had no beliefs yet (first event at …)" and exits 1. Future times are clamped to now with a note.
- Operator `set` requires a reason. Operator writes and retractions are allowed on archived agents (agent writes/reads return 401).
- Agents can retract only events they authored themselves (not operator-authored ones).
- Binding to a non-localhost address exposes the API without TLS; v1 targets localhost.

## Acceptance tests

End-to-end checks of the product's behaviour are in `tests/acceptance/` (they need pytest):

    python -m pytest tests/acceptance

2 of them are known open items, marked as expected failures and listed in `tests/acceptance/README.md`; the suite stays green.
