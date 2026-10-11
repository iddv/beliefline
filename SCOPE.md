# Scope: Beliefline

Beliefline is an append-only memory log that a developer runs next to their own AI agents. The agent writes every memory change to it and reads its current beliefs back through a local HTTP JSON API. Nothing is ever overwritten or deleted. v1 lets the operator (the developer who runs the agents) do three things from a command line:

- ask what any agent believed at any past moment,
- trace which events led to each belief,
- see which beliefs an agent held when it took an action, such as sending that email at 03:14.

## Users

- **Operator (owner):** the developer who installs Beliefline and runs one or more agents.
  - Needs: register agents, issue and revoke keys, inspect, explain, correct, report, export and back up.
  - Access: the operator CLI on the same machine, which calls the API with the **owner token**.
  - First run: the `init` step creates the single owner token. It is random and shown once. Only a hash is stored.
- **Agent (API client):** the operator's AI agent process, in any language.
  - Needs: append memory events, read current beliefs, log actions.
  - Access: a per-agent API key sent as a bearer token. A key can only touch its own agent's data.

There are no other accounts in v1.

## Core flows

### F1: Install and first run
- Who: Operator
- Steps:
  1. On a fresh machine, the operator runs the single install-and-start command from the README.
  2. The system creates the data directory, applies the schema and starts the service on 127.0.0.1:7700 (default).
  3. On first start with an empty store, it creates the owner token, prints it once and writes it to the CLI config file (file mode 0600).
  4. The operator runs `beliefline status`. It shows: service up, schema version, 0 agents, 0 events, chain verified.
  5. Optionally, the operator runs `beliefline demo load`, which loads the demo data (see Install and run).
- When it goes wrong:
  - Port in use: the service exits with "port 7700 in use; set BELIEFLINE_PORT".
  - Data dir not writable: it exits naming the path.
  - `demo load` on a non-empty store: refused with "store not empty; demo data only loads into an empty store".
  - Wrong or missing owner token: 401 "invalid owner token".

### F2: Connect an agent
- Who: Operator
- Steps:
  1. The operator runs `agent create <name>`. The system validates the name (rule D1), records the agent and shows its id.
  2. The operator runs `key issue <agent>`. The system generates a key, shows it once, stores only its hash and records the label and creation time.
  3. The operator puts the key into the agent's config. The agent calls `GET /v1/whoami` and sees its agent name.
  4. The operator can also:
     - `agent list`: shows name, status, event count and last event time.
     - `agent rename`
     - `key list`: shows label, created time, last used time and revoked flag.
     - `key revoke <key-id>`
     - `agent archive`: all of its keys stop working and its history stays queryable.
     - `agent reactivate`
- When it goes wrong:
  - Duplicate or invalid name: "name taken" or "invalid name" with the rule.
  - Agent not found: "no agent named X".
  - Revoked key, or key for an archived agent: 401 "key revoked" or "agent archived".
  - More than 10 active keys per agent (default): "key limit reached; revoke one first".

### F3: Record memory changes
- Who: Agent
- Steps:
  1. The agent POSTs one event or a batch (rule D3) to `/v1/events`. Each event has these fields:
     - `type`: `set` or `delete`
     - `key`
     - `value` (for `set`)
     - optional `reason`
     - optional `source`
     - optional `caused_by` (earlier event ids)
     - optional `occurred_at`
     - optional `idempotency_key`
     - optional `expected_version`
  2. The system validates every event (D1–D5). If any event fails, the whole batch is rejected and nothing is written.
  3. The system assigns each event its per-agent sequence number, recorded time, hash and new key version.
  4. It returns those values, plus the resulting value for each key.
- When it goes wrong:
  - Invalid key, value too large or bad JSON: 400 naming the event index and field.
  - `caused_by` id not found, belonging to another agent, or not earlier: 400 "unknown cause <id>".
  - `expected_version` mismatch: 409 with the current version and value. Nothing is written.
  - Repeated `idempotency_key`: 200 with the original result and no new event.
  - Batch too large: 413 "max 100 events per batch".

### F4: Read current beliefs
- Who: Agent (Operator via CLI `beliefs <agent>`)
- Steps:
  1. The agent calls `GET /v1/beliefs` in one of three forms:
     - with `key=` for a single key,
     - with `prefix=` for a group of keys,
     - with neither, for all keys.
  2. The system computes current values by the belief rule (D6).
  3. The response shows, per key: value, version, the id of the event that set it, and its recorded time.
- When it goes wrong:
  - Key never set, or deleted: 404 "no belief for key", plus the time of the last delete if there was one.
  - Invalid prefix: 400.

### F5: Log an action
- Who: Agent
- Steps:
  1. Before or after acting, the agent POSTs `/v1/actions` with:
     - `kind` (e.g. `email.send`)
     - `summary` (e.g. "Sent RSVP yes to Dana")
     - optional `payload` (JSON)
     - `read_keys` (the keys it relied on)
     - optional `caused_by`
  2. The system records the action as an event in the same chain.
  3. For each read key, it snapshots the event id and version current at that instant (D7).
  4. It returns the action id and the snapshot.
- When it goes wrong:
  - Missing `kind` or `summary`: 400.
  - Read key with no belief: recorded as "absent" in the snapshot, not an error.
  - More than 50 read keys (default): 400.

### F6: Ask what the agent believed at a past moment
- Who: Operator
- Steps:
  1. The operator runs `asof <agent> <time> [--key K | --prefix P]`.
     - Time formats: ISO 8601 with offset, local time in the display zone (e.g. `2026-10-09 03:14`), `yesterday 03:14`, or `#<seq>`.
  2. The system applies D6 to all events recorded at or before that instant.
  3. It shows each key with its value, version, setting event and that event's recorded time. It also lists any retractions that were not yet recorded at that moment.
- When it goes wrong:
  - Unparseable time: "cannot read time; examples: …".
  - Time before the agent's first event: "agent had no beliefs yet (first event at …)".
  - Time in the future: treated as now, with a note.

### F7: Explain why
- Who: Operator
- Steps:
  1. The operator runs `history <agent> <key>`. It lists every event on that key in order: type, value, version, reason, source, retracted or not, and recorded time.
  2. The operator runs `explain <event-or-action-id>`. It shows:
     - the event,
     - for actions, the belief snapshot of each read key with that belief's history up to the action,
     - the `caused_by` chain walked backwards to depth 10 (default).
  3. The operator runs `actions <agent> --from --to [--kind]` to find the action to explain, e.g. the email at 03:14.
- When it goes wrong:
  - Unknown id: "no event <id>".
  - Cycle-free by construction (causes must be earlier). A depth limit reached shows "… N more causes".

### F8: Retract or correct a belief
- Who: Operator (and Agent, if the D8 setting allows)
- Steps:
  1. The operator runs `retract <event-id> --reason "<text>"`.
  2. The system checks that the target is a `set` or `delete` event of that agent and is not already retracted.
  3. It records a `retract` event. From then on, D6 ignores the target event, so the key falls back to its previous non-retracted value.
  4. The output shows the key's value before and after. Past `asof` answers before the retraction are unchanged.
  5. To restore a lost "no", the operator can instead run `set <agent> <key> <json> --reason` (an operator-authored `set` event).
  6. Undoing a retraction means retracting the retraction.
- When it goes wrong:
  - Target is an action: "actions cannot be retracted".
  - Target is already retracted: 409.
  - Target belongs to another agent: 404.
  - Agent retraction when the setting forbids it: 403.
  - Empty reason: 400 "reason required".

### F9: Daily report, diff, export and verify
- Who: Operator
- Steps:
  1. `report <agent> [--day YYYY-MM-DD]` covers a day in the display zone, default yesterday. It shows:
     - event counts by type,
     - keys changed with first and last value,
     - deletes,
     - retractions,
     - actions with summaries,
     - 409 conflicts and rejected writes.
  2. `diff <agent> <t1> <t2>` lists keys added, removed or changed between two moments, with old and new values.
  3. `export <agent|--all> --from --to > file.jsonl` writes one event per line with all fields and hashes.
  4. `verify [<agent>]` recomputes every hash chain and reports "OK, N events" or the first broken sequence number.
- When it goes wrong:
  - `t1` after `t2`: swapped, with a note.
  - Empty range: the report says "no events" and the export writes an empty file.
  - Chain broken: `verify` exits non-zero naming the agent and sequence number.

## Features
### Must have (v1)
- M1: One-command install and start, empty store, owner token on first run, `status`, explicit demo load (F1)
- M2: Agent lifecycle: create, list, rename, archive, reactivate (F2)
- M3: Per-agent API keys: issue (shown once), list, revoke, hashed at rest (F2)
- M4: Append-only event API: set and delete, batches, causes, reasons, idempotency, optimistic version check (F3)
- M5: Current-belief reads by key, prefix or all, with provenance (F4)
- M6: Action log with automatic snapshot of the beliefs read (F5, F7)
- M7: Point-in-time queries by time or sequence number, with flexible time input (F6)
- M8: Key history, `explain` with snapshot and cause chain, action search (F7)
- M9: Retraction (and retraction of a retraction) plus operator-authored `set` (F8)
- M10: Daily report and diff between two moments (F9)
- M11: JSONL export, per-agent hash chain with `verify`, and backup and restore commands (F9)
- M12: Operator CLI for every action above, with human-readable output by default and `--json` (all flows)

### Later (not in v1)
- Web timeline viewer: the CLI covers every question; a UI is polish.
- Language-specific client libraries: plain HTTP JSON works from any agent.
- Bitemporal queries ("as the agent later understood the past"): v1 answers "as recorded".
- Semantic or vector search over memories: an AI feature, not needed to answer "what and why".
- Multi-user accounts and roles: v1 has a single operator.
- Remote or multi-tenant hosting with TLS: localhost is the v1 target.
- Alerts when a belief flips (e.g. RSVP no → yes): useful, but needs a notification channel.
- Import from existing agent memory stores: each store has its own format.

## Domain rules and defaults
- **D1 Names and keys:**
  - Agent names: 1–64 chars from `[a-z0-9_-]`, unique.
  - Memory keys: 1–200 chars from `[A-Za-z0-9._:/-]`, case-sensitive. Use `/` or `.` for grouping (e.g. `rsvp/dana-wedding`).
- **D2 Values:** any JSON value, at most 64 KB serialized (default). `reason` is at most 2,000 chars (default). `source` is at most 200 chars (default).
- **D3 Batches:** at most 100 events per request (default). A batch is atomic, takes consecutive sequence numbers and shares one recorded time.
- **D4 Time:**
  - `recorded_at` is assigned by the server in UTC with millisecond precision. It is never decreasing per agent; if the clock goes back, the previous value is reused.
  - All as-of queries use `recorded_at`. `occurred_at` (agent-supplied) is stored and shown but never used for ordering.
  - Display zone is the machine's local time zone, overridable by `BELIEFLINE_TZ` (default).
- **D5 Versions and idempotency:**
  - Each key's version starts at 1 and increases by 1 on every `set`, `delete` or `retract` affecting it.
  - `expected_version: 0` means "key must not currently exist".
  - Idempotency keys are unique per agent forever. A retry with the same key but a different body returns 409 "idempotency key reused with different content".
- **D6 Belief rule:** to get the belief for a key as of instant T:
  1. Take that key's events with `recorded_at` ≤ T.
  2. Drop every event whose retraction (itself not retracted as of T) was recorded at or before T.
  3. The last remaining event decides the belief: `set` means its value, `delete` means absent.
- **D7 Action snapshot:** the snapshot is computed by D6 at the action's recorded time inside the same write, so no other write can slip between them.
- **D8 Retraction:**
  - Only `set`, `delete` and `retract` events can be retracted, and only with a non-empty reason.
  - Who may retract follows `retract.allowed_by`.
- **D9 Archived agents:** reads by the operator still work. Agent writes and reads return 401.
- **D10 Unchanged set:** when a `set` repeats the current value exactly, it is handled per `writes.unchanged_set`.

## Operator settings

| key | values | default | what it decides |
|---|---|---|---|
| `writes.version_check` | optional, required | optional | Whether every agent `set`/`delete` must carry `expected_version`; when required, writes without one get 400. |
| `writes.unchanged_set` | record, skip | record | Whether a `set` repeating the current value appends an event or returns the current version without writing. |
| `retract.allowed_by` | operator_only, operator_and_agent | operator_only | Whether agents may retract their own events through the API. |
| `display.time_zone` | local, utc | local | Whether CLI input and output times use the machine's zone or UTC (unless `BELIEFLINE_TZ` overrides). |

## Money and data integrity
- Beliefline handles no money.
- **Append-only storage:** events are never updated or deleted. No API, CLI command or migration may change a stored event. Corrections are new `set` or `retract` events.
- **Hash chain:** each event stores its per-agent sequence number (gap-free, starting at 1) and `hash = SHA-256(prev_hash + canonical JSON of the event)`. `verify` recomputes the chain.
- **Concurrency:** two writes to the same agent at the same moment are serialized, so sequence numbers are never duplicated or skipped. Two writers with the same `expected_version` result in exactly one success and one 409.
- **Retries:** an idempotency key prevents a retry from being double-counted.
- **Validation:** every field is validated before anything is written. A failed batch writes nothing.
- **Durability:** a write is acknowledged only after it is durably stored.
- **Derived data:** current beliefs and counts are always derivable from the events. Any cache must match a full replay; `verify` also checks this.

## Install and run
- **One command:** a single documented command installs dependencies, initializes the data directory and starts the service. The README shows it, plus `beliefline status`.
- **Safe defaults:**
  - The service binds to 127.0.0.1:7700 unless `BELIEFLINE_HOST`/`BELIEFLINE_PORT` say otherwise.
  - A fresh install has no agents and no events.
  - The owner token is random, generated on first run and printed once. `beliefline token rotate` replaces it.
  - There are no default credentials or demo keys.
- **Demo data:** `beliefline demo load` works only on an empty store. It creates:
  - Two agents, `assistant` and `scheduler`, with about 300 events over the last 3 days in total.
  - The RSVP story:
    1. At 22:10 two days ago, `rsvp/dana-wedding` is set to "no" with reason "user said can't make it".
    2. At 02:47 yesterday, a `set` to "yes" arrives with reason "summarized from old thread".
    3. At 03:14 yesterday, an `email.send` action reads that key.
  - One retraction.
  - One 409 conflict in the rejected-writes log.
  - It prints one demo API key per agent.
- **Configuration:** environment variables or a config file, all listed in the README with defaults:
  - `BELIEFLINE_HOST`
  - `BELIEFLINE_PORT`
  - `BELIEFLINE_DATA_DIR`
  - `BELIEFLINE_TZ`
  - `BELIEFLINE_URL` (for the CLI)
  - `BELIEFLINE_OWNER_TOKEN` (for the CLI)
  - the four operator settings
- **Data and backup:**
  - All data lives in `BELIEFLINE_DATA_DIR` (default `~/.beliefline`).
  - `beliefline backup <file>` writes a consistent snapshot while the service runs.
  - `beliefline restore <file>` works only into an empty data dir, and runs `verify` afterwards.
- **Upgrades:** the schema is versioned. On start, migrations run forward automatically after an automatic backup. Migrations never alter event content.

## Non-functional basics
- **Authentication and roles:**
  - The owner token can do everything.
  - An agent key can only append events and actions, read its own agent's beliefs and history, and retract its own events if the D8 setting allows.
  - Keys and tokens are stored hashed.
- **Validation and errors:** errors are JSON `{error, field, detail}` with the right HTTP status. CLI errors are one readable line with a non-zero exit code.
- **Rejected-writes log:** every 400, 409 and 413 from an agent is recorded (time, agent, reason) for the daily report. It is separate from the belief chain.
- **Persistence:** everything survives restarts and crashes. Acknowledged writes are never lost.
- **Tests:** one documented command runs the automated tests. They must cover:
  - the D6 rule with retractions of retractions,
  - as-of at exact boundaries,
  - batch atomicity,
  - concurrent writes with the same `expected_version`,
  - idempotent retries,
  - hash-chain verification and tamper detection,
  - the action snapshot,
  - backup and restore round trip,
  - each CLI command's happy path.

## Definition of done
- [ ] F1: Install and first run — after the one command and `status`, the operator sees the service on 127.0.0.1:7700, 0 agents, 0 events, chain OK. `demo load` then shows 2 agents and about 300 events.
- [ ] F2: Connect an agent — a new agent's key makes `GET /v1/whoami` return its name. After `key revoke`, the same call returns 401.
- [ ] F3: Record memory changes — a batch of `set`/`delete` events returns gap-free sequence numbers and versions. A stale `expected_version` gets 409 and writes nothing. A retried idempotency key creates no new event.
- [ ] F4: Read current beliefs — `GET /v1/beliefs?prefix=rsvp/` returns each key's value, version and setting event, matching the latest non-retracted events.
- [ ] F5: Log an action — the `email.send` action returns an id and a snapshot listing the exact event id and version of each read key.
- [ ] F6: Ask what the agent believed — in the demo, `asof assistant "yesterday 03:14" --key rsvp/dana-wedding` shows "yes", set at 02:47 with its reason, and `asof` at 23:00 two days ago shows "no".
- [ ] F7: Explain why — `explain <03:14 email action>` shows the "yes" belief it read, the 02:47 event that set it, the earlier "no" it replaced, and the cause chain.
- [ ] F8: Retract or correct a belief — retracting the 02:47 event makes current `beliefs` show "no" again. `asof "yesterday 03:14"` still shows "yes", and the retraction appears in `history`.
- [ ] F9: Daily report, diff, export and verify — `report` for yesterday lists the RSVP change, the email action and the conflict. `diff` shows "no" → "yes". `export` writes valid JSONL. `verify` prints "OK" and fails with the sequence number after a stored event is hand-edited.
