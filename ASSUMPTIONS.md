# Assumptions

The idea this product was built from leaves these questions open. Each section says what this version does.

The rules and numbers the idea left open are set as defaults in the product scope, `SCOPE.md` (each marked *(default)*).

## Settings

Where reasonable operators differ between two business policies, the operator chooses. Each setting below exists in this version; the README's configuration section says how to change it, and the environment variable named below overrides it everywhere.

| key | values | default | scope | settles |
|---|---|---|---|---|
| `writes.delete_absent` | recorded, refused | `recorded` | global | Is a delete of a key that has no current belief (never set or already deleted) recorded? |
| `agent.reactivate_keys` | restored, disabled | `restored` | global | When an archived agent is reactivated, do its keys that were not explicitly revoked work again? |
| `archive.operator_writes` | allowed, refused | `allowed` | global | May the operator write to an archived agent (operator-authored set or retract)? |
| `asof.seq_in_batch` | through_seq, whole_batch | `whole_batch` | global | An asof by sequence number that falls inside a batch: include only events up to that number, or the whole batch? |

- `writes.delete_absent` (`WRITES_DELETE_ABSENT`): `recorded`: deleting an absent key appends a delete event and bumps the version; `refused`: deleting an absent key is rejected with a client error and nothing is written.
- `agent.reactivate_keys` (`AGENT_REACTIVATE_KEYS`): `restored`: non-revoked keys work again after reactivation; `disabled`: keys from before archiving stay unusable; new keys must be issued.
- `archive.operator_writes` (`ARCHIVE_OPERATOR_WRITES`): `allowed`: operator can set and retract on archived agents; `refused`: operator writes to archived agents are rejected until reactivation.
- `asof.seq_in_batch` (`ASOF_SEQ_IN_BATCH`): `through_seq`: asof #N includes events up to N even mid-batch; `whole_batch`: asof #N includes the whole batch containing N.

## Decisions

Questions that aren't a simple switch. For each: the two ways to read it, and what this version does.

### When a retraction makes a key fall back to an earlier value, what version do belief reads report: the key's running version counter, or the version recorded on the event that now decides the belief?

- One reading: The running counter (every set/delete/retract bumps it), so after retracting v2 the key reports v3 while its setting event is the v1 event
- The other: Same as literal: version is the key's running counter, and expected_version checks compare against it
- **This version: The running counter (every set/delete/retract bumps it), so after retracting v2 the key reports v3 while its setting event is the v1 event.**

### Can an event's caused_by refer to an earlier event in the same batch, and how would the agent name it before ids exist?

- One reading: No: only ids of already-stored events are accepted; in-batch references fail as unknown causes
- The other: Allow referencing earlier events in the same batch, e.g. by batch index
- **This version: No: only ids of already-stored events are accepted; in-batch references fail as unknown causes.**

### How is a local time input resolved when it is ambiguous or non-existent due to a daylight-saving change (e.g. 02:30 on a fall-back night)?

- One reading: Unspecified; any interpretation
- The other: Pick one rule (earlier occurrence, refuse with a note, etc.) and state it in output
- **This version: it keeps the behaviour it was built with.**

### Do event counts in status, agent list and report include actions and retractions, and do skipped unchanged sets count?

- One reading: Every stored chain entry counts as an event, including actions and retractions; skipped sets do not exist
- The other: Same, with counts by type in the report
- **This version: Every stored chain entry counts as an event, including actions and retractions; skipped sets do not exist.**
