"""SQLite-backed append-only event store: all rules (D1-D10) live here."""
import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

from . import config

SCHEMA_VERSION = 1
ZERO_HASH = "0" * 64
KEY_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,200}$")
NAME_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
KEY_RULE = "1-200 chars from [A-Za-z0-9._:/-]"
NAME_RULE = "1-64 chars from [a-z0-9_-]"


class ApiError(Exception):
    def __init__(self, status, error, field=None, detail=None, **extra):
        super().__init__(error)
        self.status, self.error, self.field, self.detail, self.extra = status, error, field, detail, extra

    def body(self):
        b = {"error": self.error, "field": self.field, "detail": self.detail}
        b.update(self.extra)
        return b


# ---------------------------------------------------------------- helpers

def now_ms():
    return int(time.time() * 1000)


def iso(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms // 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + f".{ms % 1000:03d}Z"


def canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _no_const(name):
    raise ValueError(f"non-finite number {name} not allowed")


def _parse_float(s):
    f = float(s)
    if not math.isfinite(f):
        raise ValueError("non-finite number not allowed")
    return f


def parse_json(text):
    return json.loads(text, parse_constant=_no_const, parse_float=_parse_float)


def row_dict(r):
    """Canonical event dict (this, minus nothing, is what gets hashed)."""
    def j(s):
        return None if s is None else json.loads(s)
    return {
        "id": r["id"], "agent_id": r["agent_id"], "seq": r["seq"], "type": r["type"], "key": r["key"],
        "value": j(r["value_json"]), "reason": r["reason"], "source": r["source"],
        "caused_by": json.loads(r["caused_by"]), "occurred_at": r["occurred_at"],
        "idempotency_key": r["idempotency_key"], "request_hash": r["request_hash"],
        "recorded_at": iso(r["recorded_at"]), "key_version": r["key_version"], "author": r["author"],
        "target": r["target"], "kind": r["kind"], "summary": r["summary"], "payload": j(r["payload_json"]),
        "read_keys": j(r["read_keys"]), "snapshot": j(r["snapshot"]),
    }


def event_hash(prev, d):
    return sha(prev + canon(d))


def analyze(evs):
    """D6 over one key's events (ascending, already cut at T).
    Returns (killed: target_id -> effective retract id, decider row or None)."""
    killed = {}
    decider = None
    for e in reversed(evs):
        if e["type"] == "retract":
            if e["id"] not in killed:
                killed[e["target"]] = e["id"]
        elif e["type"] in ("set", "delete") and decider is None and e["id"] not in killed:
            decider = e
    return killed, decider


def make_belief(evs):
    _, dec = analyze(evs)
    present = dec is not None and dec["type"] == "set"
    return {
        "present": present,
        "value": json.loads(dec["value_json"]) if present else None,
        "version": evs[-1]["key_version"] if evs else 0,
        "event_id": dec["id"] if dec is not None else None,
        "event_version": dec["key_version"] if dec is not None else None,
        "recorded_at": iso(dec["recorded_at"]) if dec is not None else None,
        "reason": dec["reason"] if dec is not None else None,
        "source": dec["source"] if dec is not None else None,
        "deleted_at": iso(dec["recorded_at"]) if dec is not None and dec["type"] == "delete" else None,
    }


def snapshot_entry(key, b):
    return {"key": key, "status": "present" if b["present"] else "absent", "event_id": b["event_id"],
            "version": b["version"], "event_version": b["event_version"], "value": b["value"],
            "recorded_at": b["recorded_at"]}


# ------------------------------------------------------------- validation

def _v_text(fp, name, v, maxlen, required=False):
    if v is None:
        if required:
            raise ApiError(400, f"{name} required", fp(name), f"{name} is required")
        return None
    if not isinstance(v, str):
        raise ApiError(400, f"invalid {name}", fp(name), "must be a string")
    if required and not v.strip():
        raise ApiError(400, f"{name} required", fp(name), f"{name} must not be empty")
    if len(v) > maxlen:
        raise ApiError(400, f"{name} too long", fp(name), f"max {maxlen} chars")
    return v


def v_key(fp, v, name="key"):
    if not isinstance(v, str) or not KEY_RE.fullmatch(v):
        raise ApiError(400, f"invalid {name}", fp(name), KEY_RULE)
    return v


def _v_json(fp, name, v):
    try:
        n = len(canon(v).encode("utf-8"))
    except (ValueError, RecursionError):
        raise ApiError(400, f"invalid {name}", fp(name), "not representable as JSON")
    if n > config.max_value_bytes():
        raise ApiError(400, f"{name} too large", fp(name), f"max {config.max_value_bytes()} bytes serialized, got {n}")
    return v


def _v_common(fp, raw):
    caused = raw.get("caused_by")
    if caused is None:
        caused = []
    if not isinstance(caused, list) or not all(isinstance(c, str) and c for c in caused) or len(caused) > 100:
        raise ApiError(400, "invalid caused_by", fp("caused_by"), "must be a list of event ids (max 100)")
    occ = raw.get("occurred_at")
    if occ is not None:
        try:
            if not isinstance(occ, str):
                raise ValueError
            datetime.fromisoformat(occ.replace("Z", "+00:00"))
        except ValueError:
            raise ApiError(400, "invalid occurred_at", fp("occurred_at"), "must be an ISO 8601 timestamp")
    idem = raw.get("idempotency_key")
    if idem is not None and (not isinstance(idem, str) or not 1 <= len(idem) <= 200):
        raise ApiError(400, "invalid idempotency_key", fp("idempotency_key"), "must be a string of 1-200 chars")
    return list(dict.fromkeys(caused)), occ, idem


def _unknown(fp, raw, allowed):
    for k in raw:
        if k not in allowed:
            raise ApiError(400, "unknown field", fp(k), f"allowed fields: {', '.join(sorted(allowed))}")


def norm_event(i, raw):
    fp = lambda n: f"events[{i}].{n}"
    if not isinstance(raw, dict):
        raise ApiError(400, "invalid event", f"events[{i}]", "must be a JSON object")
    _unknown(fp, raw, {"type", "key", "value", "reason", "source", "caused_by", "occurred_at",
                       "idempotency_key", "expected_version"})
    typ = raw.get("type")
    if typ not in ("set", "delete"):
        raise ApiError(400, "invalid type", fp("type"), "must be 'set' or 'delete'")
    key = v_key(fp, raw.get("key"))
    value = None
    if typ == "set":
        if "value" not in raw:
            raise ApiError(400, "value required", fp("value"), "a set event needs a value (use null for JSON null)")
        value = _v_json(fp, "value", raw["value"])
    elif "value" in raw:
        raise ApiError(400, "value not allowed", fp("value"), "delete events carry no value")
    reason = _v_text(fp, "reason", raw.get("reason"), config.max_reason())
    source = _v_text(fp, "source", raw.get("source"), config.max_source())
    caused, occ, idem = _v_common(fp, raw)
    exp = raw.get("expected_version")
    if exp is not None and (isinstance(exp, bool) or not isinstance(exp, int) or exp < 0):
        raise ApiError(400, "invalid expected_version", fp("expected_version"), "must be an integer >= 0")
    req = {"type": typ, "key": key, "value": value, "reason": reason, "source": source, "caused_by": caused,
           "occurred_at": occ, "expected_version": exp}
    return {"type": typ, "key": key, "value": value, "reason": reason, "source": source, "caused_by": caused,
            "occurred_at": occ, "idempotency_key": idem, "expected_version": exp, "req": sha(canon(req))}


def norm_action(raw):
    fp = lambda n: n
    if not isinstance(raw, dict):
        raise ApiError(400, "invalid action", None, "body must be a JSON object")
    _unknown(fp, raw, {"kind", "summary", "payload", "read_keys", "caused_by", "idempotency_key", "occurred_at",
                       "reason", "source"})
    kind = _v_text(fp, "kind", raw.get("kind"), 200, required=True)
    summary = _v_text(fp, "summary", raw.get("summary"), config.max_reason(), required=True)
    payload = _v_json(fp, "payload", raw["payload"]) if raw.get("payload") is not None else None
    rk = raw.get("read_keys")
    if rk is None:
        rk = []
    if not isinstance(rk, list):
        raise ApiError(400, "invalid read_keys", "read_keys", "must be a list of keys")
    if len(rk) > config.max_read_keys():
        raise ApiError(400, "too many read_keys", "read_keys", f"max {config.max_read_keys()} read keys")
    for n, k in enumerate(rk):
        v_key(lambda _n, n=n: f"read_keys[{n}]", k, "key")
    rk = list(dict.fromkeys(rk))
    source = _v_text(fp, "source", raw.get("source"), config.max_source())
    reason = _v_text(fp, "reason", raw.get("reason"), config.max_reason())
    caused, occ, idem = _v_common(fp, raw)
    req = {"kind": kind, "summary": summary, "payload": payload, "read_keys": rk, "caused_by": caused,
           "occurred_at": occ, "source": source, "reason": reason}
    return {"kind": kind, "summary": summary, "payload": payload, "read_keys": rk, "caused_by": caused,
            "occurred_at": occ, "idempotency_key": idem, "source": source, "reason": reason,
            "req": sha(canon({"action": req}))}


def norm_batch(body):
    if isinstance(body, dict) and "events" in body:
        _unknown(lambda n: n, body, {"events"})
        items = body["events"]
    elif isinstance(body, dict):
        items = [body]
    else:
        items = body
    if not isinstance(items, list):
        raise ApiError(400, "invalid body", "events", "send an event object, a list, or {\"events\": [...]}")
    if not items:
        raise ApiError(400, "empty batch", "events", "at least one event is required")
    if len(items) > config.max_batch():
        raise ApiError(413, f"max {config.max_batch()} events per batch", "events",
                       f"got {len(items)} events")
    return [norm_event(i, r) for i, r in enumerate(items)]


# ------------------------------------------------------------------ schema

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE agents(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'active',
  created_at INTEGER NOT NULL, last_seq INTEGER NOT NULL DEFAULT 0, last_hash TEXT NOT NULL,
  last_recorded_at INTEGER NOT NULL DEFAULT 0);
CREATE TABLE api_keys(
  id TEXT PRIMARY KEY, agent_id INTEGER NOT NULL REFERENCES agents(id), label TEXT NOT NULL DEFAULT '',
  key_hash TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL, last_used_at INTEGER, revoked_at INTEGER);
CREATE TABLE events(
  gid INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, agent_id INTEGER NOT NULL REFERENCES agents(id),
  seq INTEGER NOT NULL, type TEXT NOT NULL CHECK(type IN ('set','delete','retract','action')),
  key TEXT, value_json TEXT, reason TEXT, source TEXT, caused_by TEXT NOT NULL, occurred_at TEXT,
  idempotency_key TEXT, request_hash TEXT, recorded_at INTEGER NOT NULL, key_version INTEGER,
  author TEXT NOT NULL, target TEXT, kind TEXT, summary TEXT, payload_json TEXT, read_keys TEXT, snapshot TEXT,
  prev_hash TEXT NOT NULL, hash TEXT NOT NULL, UNIQUE(agent_id, seq));
CREATE UNIQUE INDEX ev_idem ON events(agent_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX ev_key ON events(agent_id, key, seq);
CREATE INDEX ev_time ON events(agent_id, recorded_at);
CREATE TRIGGER events_no_update BEFORE UPDATE ON events
  BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events
  BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TABLE rejected(
  id INTEGER PRIMARY KEY, recorded_at INTEGER NOT NULL, agent_id INTEGER NOT NULL, status INTEGER NOT NULL,
  error TEXT, field TEXT, detail TEXT, endpoint TEXT);
CREATE INDEX rej_time ON rejected(agent_id, recorded_at);
"""

# version -> function(conn) applying that step; migrations never touch event content.
MIGRATIONS = {}


class Store:
    def __init__(self, data_dir=None, db_path=None):
        self.dir = Path(data_dir) if data_dir else config.data_dir()
        self.path = Path(db_path) if db_path else self.dir / "beliefline.db"
        self.local = threading.local()

    # ------------------------------------------------------ connection
    @property
    def c(self):
        conn = getattr(self.local, "conn", None)
        if conn is None:
            if not self.path.exists():
                os.close(os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600))
            conn = sqlite3.connect(self.path, isolation_level=None, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA foreign_keys=ON")
            self._tighten()
            self.local.conn = conn
        return conn

    def _tighten(self):
        """Owner-only modes for the database, its -wal/-shm files and the data dir."""
        for suffix in ("", "-wal", "-shm"):
            f = Path(str(self.path) + suffix)
            try:
                os.chmod(f, 0o600)
            except FileNotFoundError:
                pass
        for d in (self.path.parent, self.path.parent / "backups"):
            if d.is_dir():
                os.chmod(d, 0o700)

    def close(self):
        conn = getattr(self.local, "conn", None)
        if conn is not None:
            conn.close()
            self.local.conn = None

    @contextmanager
    def tx(self):
        c = self.c
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
        except BaseException:
            c.execute("ROLLBACK")
            raise
        c.execute("COMMIT")

    # ------------------------------------------------------ lifecycle
    def init(self):
        """Create the data dir and schema, migrate forward. Returns True if the DB was created."""
        d = self.path.parent
        try:
            d.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(d, 0o700)
            probe = d / ".write-test"
            probe.write_text("x")
            probe.unlink()
        except OSError:
            raise ApiError(500, f"data dir not writable: {d}")
        fresh = not self.path.exists()
        c = self.c
        has_meta = c.execute("SELECT 1 FROM sqlite_master WHERE name='meta'").fetchone()
        if not has_meta:
            self.c.executescript(SCHEMA)
            with self.tx() as c:
                c.execute("INSERT INTO meta VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
            return True
        self.migrate()
        return fresh

    def schema_version(self):
        r = self.c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return int(r[0]) if r else 0

    def migrate(self):
        v = self.schema_version()
        if v > SCHEMA_VERSION:
            raise ApiError(500, f"database schema v{v} is newer than this Beliefline (v{SCHEMA_VERSION})")
        if v == SCHEMA_VERSION:
            return
        bdir = self.path.parent / "backups"
        bdir.mkdir(exist_ok=True, mode=0o700)
        os.chmod(bdir, 0o700)
        self.backup(str(bdir / f"pre-migrate-v{v}-{time.strftime('%Y%m%d%H%M%S')}.db"))
        while v < SCHEMA_VERSION:
            with self.tx() as c:
                MIGRATIONS[v + 1](c)
                c.execute("UPDATE meta SET value=? WHERE key='schema_version'", (str(v + 1),))
            v += 1

    def backup(self, dest):
        dest = Path(dest)
        if dest.exists():
            raise ApiError(409, f"{dest} already exists", "path", "refusing to overwrite a backup")
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = sqlite3.connect(dest)
        try:
            self.c.backup(out)
        finally:
            out.close()
        os.chmod(dest, 0o600)
        return str(dest)

    # --------------------------------------------------------- meta/settings
    def _meta(self, key, c=None):
        r = (c or self.c).execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r[0] if r else None

    def _set_meta(self, key, value):
        self.c.execute("INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def settings(self, c=None):
        out = {}
        for k, (default, allowed) in config.SETTINGS.items():
            v = (os.environ.get(config.OVERRIDE_ENV.get(k, "")) or self._meta("setting:" + k, c)
                 or os.environ.get(config.setting_env_name(k)) or default)
            out[k] = v if v in allowed else default
        return out

    def put_setting(self, key, value):
        if key not in config.SETTINGS:
            raise ApiError(400, "unknown setting", "key", f"known settings: {', '.join(config.SETTINGS)}")
        allowed = config.SETTINGS[key][1]
        if value not in allowed:
            raise ApiError(400, "invalid value", "value", f"{key} must be one of: {', '.join(allowed)}")
        with self.tx():
            self._set_meta("setting:" + key, value)
        return self.settings()

    # -------------------------------------------------------------- tokens
    def ensure_owner_token(self):
        """Create the owner token on first start of an empty store; returns it once, else None."""
        with self.tx():
            if self._meta("owner_token_hash"):
                return None
            tok = "blo_" + secrets.token_urlsafe(32)
            self._set_meta("owner_token_hash", sha(tok))
        return tok

    def rotate_owner_token(self):
        tok = "blo_" + secrets.token_urlsafe(32)
        with self.tx():
            self._set_meta("owner_token_hash", sha(tok))
        return tok

    def check_owner_token(self, tok):
        h = self._meta("owner_token_hash")
        return bool(h) and bool(tok) and secrets.compare_digest(h, sha(tok))

    def auth_agent(self, tok):
        """Resolve an agent key -> (agent row, key row) or raise 401."""
        if not tok:
            raise ApiError(401, "missing API key")
        k = self.c.execute("SELECT * FROM api_keys WHERE key_hash=?", (sha(tok),)).fetchone()
        if k is None:
            raise ApiError(401, "invalid API key")
        if k["revoked_at"] is not None:
            raise ApiError(401, "key revoked")
        a = self.c.execute("SELECT * FROM agents WHERE id=?", (k["agent_id"],)).fetchone()
        if a["status"] != "active":
            raise ApiError(401, "agent archived")
        if self.settings()["agent.reactivate_keys"] == "disabled":
            ra = self._meta(f"reactivated_at:{a['id']}")
            if ra is not None and k["created_at"] < int(ra):
                raise ApiError(401, "key disabled; agent was reactivated, issue a new key")
        t = now_ms()
        if k["last_used_at"] is None or t - k["last_used_at"] > 1000:
            try:
                self.c.execute("UPDATE api_keys SET last_used_at=? WHERE id=?", (t, k["id"]))
            except sqlite3.OperationalError:
                pass
        return a, k

    # -------------------------------------------------------------- agents
    def agent(self, name):
        a = self.c.execute("SELECT * FROM agents WHERE name=?", (name,)).fetchone()
        if a is None:
            raise ApiError(404, f"no agent named {name}", "agent", None)
        return a

    @staticmethod
    def _check_name(name, field="name"):
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise ApiError(400, "invalid name", field, NAME_RULE)

    def agent_info(self, a):
        n, last = self.c.execute("SELECT COUNT(*), MAX(recorded_at) FROM events WHERE agent_id=?", (a["id"],)).fetchone()
        return {"id": f"agt_{a['id']}", "name": a["name"], "status": a["status"], "events": n,
                "last_event_at": iso(last), "created_at": iso(a["created_at"])}

    def create_agent(self, name, now=None):
        self._check_name(name)
        with self.tx() as c:
            if c.execute("SELECT 1 FROM agents WHERE name=?", (name,)).fetchone():
                raise ApiError(409, "name taken", "name", f"an agent named {name} already exists")
            cur = c.execute("INSERT INTO agents(name, created_at, last_hash) VALUES(?,?,?)",
                            (name, now or now_ms(), ZERO_HASH))
        return self.agent_info(self.agent(name))

    def list_agents(self):
        return [self.agent_info(a) for a in self.c.execute("SELECT * FROM agents ORDER BY id")]

    def rename_agent(self, name, new):
        self._check_name(new, "new_name")
        a = self.agent(name)
        with self.tx() as c:
            if c.execute("SELECT 1 FROM agents WHERE name=?", (new,)).fetchone():
                raise ApiError(409, "name taken", "new_name", f"an agent named {new} already exists")
            c.execute("UPDATE agents SET name=? WHERE id=?", (new, a["id"]))
        return self.agent_info(self.agent(new))

    def set_status(self, name, status):
        a = self.agent(name)
        with self.tx() as c:
            c.execute("UPDATE agents SET status=? WHERE id=?", (status, a["id"]))
            if status == "active" and a["status"] != "active":
                self._set_meta(f"reactivated_at:{a['id']}", str(now_ms()))
        return self.agent_info(self.agent(name))

    # ---------------------------------------------------------------- keys
    def issue_key(self, name, label="", now=None):
        a = self.agent(name)
        if a["status"] != "active":
            raise ApiError(409, "agent archived", "agent", "reactivate the agent before issuing keys")
        if not isinstance(label, str) or len(label) > 200:
            raise ApiError(400, "invalid label", "label", "max 200 chars")
        tok = "blk_" + secrets.token_urlsafe(32)
        kid = "key_" + secrets.token_hex(4)
        with self.tx() as c:
            n = c.execute("SELECT COUNT(*) FROM api_keys WHERE agent_id=? AND revoked_at IS NULL", (a["id"],)).fetchone()[0]
            if n >= config.max_keys_per_agent():
                raise ApiError(409, "key limit reached; revoke one first", "agent",
                               f"{n} active keys (max {config.max_keys_per_agent()})")
            c.execute("INSERT INTO api_keys(id, agent_id, label, key_hash, created_at) VALUES(?,?,?,?,?)",
                      (kid, a["id"], label, sha(tok), now or now_ms()))
        return {"id": kid, "agent": name, "label": label, "key": tok}

    def list_keys(self, name=None):
        q = "SELECT k.*, a.name AS agent FROM api_keys k JOIN agents a ON a.id=k.agent_id"
        args = ()
        if name:
            q += " WHERE a.name=?"
            args = (self.agent(name)["name"],)
        return [{"id": r["id"], "agent": r["agent"], "label": r["label"], "created_at": iso(r["created_at"]),
                 "last_used_at": iso(r["last_used_at"]), "revoked": r["revoked_at"] is not None,
                 "revoked_at": iso(r["revoked_at"])} for r in self.c.execute(q + " ORDER BY k.created_at, k.id", args)]

    def revoke_key(self, kid):
        with self.tx() as c:
            r = c.execute("SELECT * FROM api_keys WHERE id=?", (kid,)).fetchone()
            if r is None:
                raise ApiError(404, f"no key {kid}", "key_id")
            if r["revoked_at"] is None:
                c.execute("UPDATE api_keys SET revoked_at=? WHERE id=?", (now_ms(), kid))
        return [k for k in self.list_keys() if k["id"] == kid][0]

    # -------------------------------------------------------------- reading
    def _key_events(self, agent_id, key, cutoff=None):
        q, a = "SELECT * FROM events WHERE agent_id=? AND key=?", [agent_id, key]
        if cutoff is not None:
            q += " AND seq<=?"
            a.append(cutoff)
        return self.c.execute(q + " ORDER BY seq", a).fetchall()

    def belief(self, agent_id, key, cutoff=None):
        return make_belief(self._key_events(agent_id, key, cutoff))

    def beliefs(self, agent_id, cutoff=None, key=None, prefix=None):
        """key -> belief dict, including keys currently absent."""
        q, a = "SELECT * FROM events WHERE agent_id=? AND key IS NOT NULL", [agent_id]
        if cutoff is not None:
            q += " AND seq<=?"
            a.append(cutoff)
        if key is not None:
            q += " AND key=?"
            a.append(key)
        if prefix is not None:
            q += " AND substr(key,1,?)=?"
            a += [len(prefix), prefix]
        rows = self.c.execute(q + " ORDER BY key, seq", a)
        return {k: make_belief(list(g)) for k, g in groupby(rows, key=lambda r: r["key"])}

    def cutoff_for(self, agent_id, spec):
        """spec: {'at': ms} or {'seq': n} -> (cutoff_seq, at_ms|None, note|None)."""
        last = self.c.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE agent_id=?", (agent_id,)).fetchone()[0]
        if spec.get("seq") is not None:
            n = spec["seq"]
            note = f"sequence #{n} is beyond the last event (#{last}); showing #{last}" if n > last else None
            n = min(n, last)
            if n > 0 and self.settings()["asof.seq_in_batch"] == "whole_batch":
                # a batch shares one recorded_at: include every event recorded with #n
                n = self.c.execute(
                    "SELECT MAX(seq) FROM events WHERE agent_id=? AND recorded_at="
                    "(SELECT recorded_at FROM events WHERE agent_id=? AND seq=?)", (agent_id, agent_id, n)).fetchone()[0]
            return n, None, note
        at, note, t = spec["at"], None, now_ms()
        if at > t:
            at, note = t, "time is in the future; showing now"
        cut = self.c.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE agent_id=? AND recorded_at<=?",
                             (agent_id, at)).fetchone()[0]
        return cut, at, note

    @staticmethod
    def _bel_out(key, b):
        return {"key": key, **b}

    def read_beliefs(self, agent_id, key=None, prefix=None, spec=None, include_absent=False):
        for name, v in (("key", key), ("prefix", prefix)):
            if v is not None and not KEY_RE.fullmatch(v):
                raise ApiError(400, f"invalid {name}", name, KEY_RULE)
        cutoff = self.cutoff_for(agent_id, spec)[0] if spec else None
        bs = self.beliefs(agent_id, cutoff, key, prefix)
        if key is not None and not include_absent:
            b = bs.get(key)
            if b is None or not b["present"]:
                raise ApiError(404, "no belief for key", "key", f"{key} is not set" if b is None else f"{key} was deleted",
                               deleted_at=b["deleted_at"] if b else None)
        return [self._bel_out(k, b) for k, b in bs.items() if include_absent or b["present"]]

    def asof(self, agent, spec, key=None, prefix=None):
        a = agent
        cutoff, at, note = self.cutoff_for(a["id"], spec)
        first = self.c.execute("SELECT MIN(recorded_at) FROM events WHERE agent_id=?", (a["id"],)).fetchone()[0]
        out = {"agent": a["name"], "cutoff_seq": cutoff, "at": iso(at), "note": note,
               "first_event_at": iso(first), "no_beliefs_yet": cutoff == 0}
        if cutoff == 0:
            out.update(beliefs=[], later_retractions=[])
            return out
        for name, v in (("key", key), ("prefix", prefix)):
            if v is not None and not KEY_RE.fullmatch(v):
                raise ApiError(400, f"invalid {name}", name, KEY_RULE)
        bs = self.beliefs(a["id"], cutoff, key, prefix)
        out["beliefs"] = [self._bel_out(k, b) for k, b in bs.items()]
        # retractions recorded after the moment that target events visible at the moment
        q = ("SELECT r.*, t.seq AS tseq FROM events r JOIN events t ON t.id=r.target "
             "WHERE r.agent_id=? AND r.type='retract' AND r.seq>? AND t.seq<=?")
        args = [a["id"], cutoff, cutoff]
        if key is not None:
            q += " AND r.key=?"
            args.append(key)
        if prefix is not None:
            q += " AND substr(r.key,1,?)=?"
            args += [len(prefix), prefix]
        out["later_retractions"] = [
            {"id": r["id"], "key": r["key"], "target": r["target"], "reason": r["reason"], "author": r["author"],
             "recorded_at": iso(r["recorded_at"])} for r in self.c.execute(q + " ORDER BY r.seq", args)]
        return out

    def key_history(self, agent_id, key, cutoff=None):
        evs = self._key_events(agent_id, key, cutoff)
        killed, _ = analyze(evs)
        out = []
        for e in evs:
            d = row_dict(e)
            d["retracted_by"] = killed.get(e["id"])
            d["retracted"] = e["id"] in killed
            out.append(d)
        return out

    def history(self, agent, key):
        if not KEY_RE.fullmatch(key or ""):
            raise ApiError(400, "invalid key", "key", KEY_RULE)
        return {"agent": agent["name"], "key": key, "events": self.key_history(agent["id"], key)}

    def event_row(self, event_id, agent_id=None):
        r = self.c.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if r is None or (agent_id is not None and r["agent_id"] != agent_id):
            raise ApiError(404, f"no event {event_id}", "id")
        return r

    def event(self, event_id, agent_id=None):
        r = self.event_row(event_id, agent_id)
        d = row_dict(r)
        d["agent"] = self.c.execute("SELECT name FROM agents WHERE id=?", (r["agent_id"],)).fetchone()[0]
        d["prev_hash"], d["hash"] = r["prev_hash"], r["hash"]
        return d

    def actions(self, agent, frm=None, to=None, kind=None):
        q, a = "SELECT * FROM events WHERE agent_id=? AND type='action'", [agent["id"]]
        if frm is not None:
            q += " AND recorded_at>=?"
            a.append(frm)
        if to is not None:
            q += " AND recorded_at<=?"
            a.append(to)
        out = []
        for r in self.c.execute(q + " ORDER BY seq", a):
            if kind:
                k = r["kind"]
                if kind.endswith("*"):
                    ok = k.startswith(kind[:-1])
                else:
                    ok = k == kind or k.startswith(kind + ".")
                if not ok:
                    continue
            out.append(row_dict(r))
        return {"agent": agent["name"], "actions": out}

    def explain(self, event_id, agent_id=None):
        r = self.event_row(event_id, agent_id)
        ev = self.event(event_id)
        out = {"event": ev}
        if r["type"] == "action":
            reads = []
            for s in json.loads(r["snapshot"] or "[]"):
                reads.append({**s, "history": self.key_history(r["agent_id"], s["key"], r["seq"] - 1)})
            out["reads"] = reads
        elif r["type"] in ("set", "delete"):
            out["replaced"] = make_belief(self._key_events(r["agent_id"], r["key"], r["seq"] - 1))
        elif r["type"] == "retract":
            out["target"] = self.event(r["target"])
        depth_limit = config.explain_depth()
        chain, seen, more = [], {event_id}, 0
        frontier = [(c, event_id) for c in json.loads(r["caused_by"])]
        depth = 1
        while frontier:
            nxt = []
            for cid, child in frontier:
                if cid in seen:
                    continue
                seen.add(cid)
                cr = self.c.execute("SELECT * FROM events WHERE id=?", (cid,)).fetchone()
                if cr is None:
                    continue
                if depth <= depth_limit:
                    chain.append({"depth": depth, "cause_of": child, "event": self.event(cid)})
                else:
                    more += 1
                nxt += [(x, cid) for x in json.loads(cr["caused_by"])]
            frontier, depth = nxt, depth + 1
        out["causes"], out["more_causes"] = chain, more
        return out

    # -------------------------------------------------------------- writing
    def _append(self, c, st, rec, **f):
        gid = c.execute("SELECT COALESCE(MAX(gid),0) FROM events").fetchone()[0] + 1
        row = dict(key=None, value_json=None, reason=None, source=None, caused_by="[]", occurred_at=None,
                   idempotency_key=None, request_hash=None, key_version=None, target=None, kind=None,
                   summary=None, payload_json=None, read_keys=None, snapshot=None)
        row.update(f)
        row.update(gid=gid, id=("act_" if f["type"] == "action" else "evt_") + str(gid),
                   agent_id=st["agent_id"], seq=st["seq"] + 1, recorded_at=rec)
        h = event_hash(st["hash"], row_dict(row))
        row.update(prev_hash=st["hash"], hash=h)
        cols = list(row)
        c.execute(f"INSERT INTO events({','.join(cols)}) VALUES({','.join(':' + k for k in cols)})", row)
        st["seq"], st["hash"] = row["seq"], h
        return row

    def _begin_write(self, c, agent_id, now, author="agent"):
        a = c.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        if (author == "operator" and a["status"] != "active"
                and self.settings(c)["archive.operator_writes"] == "refused"):
            raise ApiError(409, "agent archived", "agent",
                           f"archive.operator_writes is 'refused'; reactivate {a['name']} first")
        st = {"agent_id": agent_id, "seq": a["last_seq"], "hash": a["last_hash"], "created": False}
        return st, max(now if now is not None else now_ms(), a["last_recorded_at"])

    def _end_write(self, c, st, rec):
        if st["created"]:
            c.execute("UPDATE agents SET last_seq=?, last_hash=?, last_recorded_at=? WHERE id=?",
                      (st["seq"], st["hash"], rec, st["agent_id"]))

    def _check_causes(self, c, st, caused, field):
        for cid in caused:
            r = c.execute("SELECT agent_id, seq FROM events WHERE id=?", (cid,)).fetchone()
            if r is None or r["agent_id"] != st["agent_id"] or r["seq"] > st["seq"]:
                raise ApiError(400, f"unknown cause {cid}", field, "caused_by must name earlier events of this agent")

    def _dup(self, c, agent_id, idem, req, field):
        r = c.execute("SELECT * FROM events WHERE agent_id=? AND idempotency_key=?", (agent_id, idem)).fetchone()
        if r is None:
            return None
        if r["request_hash"] != req:
            raise ApiError(409, "idempotency key reused with different content", field,
                           f"{idem} was first used by {r['id']}")
        return r

    def append_events(self, agent_id, items, author="agent", now=None):
        """Atomic batch of set/delete events. Returns (results, any_created)."""
        with self.tx() as c:
            st, rec = self._begin_write(c, agent_id, now, author)
            settings = self.settings(c)
            results = []
            for i, it in enumerate(items):
                fp = lambda n: f"events[{i}].{n}"
                key = it["key"]
                if it["idempotency_key"]:
                    d = self._dup(c, agent_id, it["idempotency_key"], it["req"], fp("idempotency_key"))
                    if d is not None:
                        b = make_belief(self._key_events(agent_id, key, d["seq"]))
                        results.append(self._result(i, "duplicate", d, b))
                        continue
                self._check_causes(c, st, it["caused_by"], fp("caused_by"))
                cur = make_belief(self._key_events(agent_id, key))
                exp = it["expected_version"]
                if it["type"] == "delete" and not cur["present"] and settings["writes.delete_absent"] == "refused":
                    raise ApiError(400, "nothing to delete", fp("key"),
                                   f"{key} has no current belief and writes.delete_absent is 'refused'")
                if exp is None and author == "agent" and settings["writes.version_check"] == "required":
                    raise ApiError(400, "expected_version required", fp("expected_version"),
                                   "writes.version_check is 'required'")
                if exp is not None:
                    ok = (not cur["present"]) if exp == 0 else cur["version"] == exp
                    if not ok:
                        raise ApiError(409, "version conflict", fp("expected_version"),
                                       f"expected version {exp}, current is {cur['version']}",
                                       current_version=cur["version"], current_value=cur["value"],
                                       present=cur["present"])
                if (it["type"] == "set" and cur["present"] and settings["writes.unchanged_set"] == "skip"
                        and canon(cur["value"]) == canon(it["value"])):
                    results.append({"index": i, "status": "skipped", "id": cur["event_id"], "seq": None,
                                    "type": "set", "key": key, "version": cur["version"],
                                    "recorded_at": cur["recorded_at"], "hash": None,
                                    "belief": {"present": True, "value": cur["value"], "version": cur["version"]}})
                    continue
                row = self._append(
                    c, st, rec, type=it["type"], key=key,
                    value_json=canon(it["value"]) if it["type"] == "set" else None,
                    reason=it["reason"], source=it["source"], caused_by=json.dumps(it["caused_by"]),
                    occurred_at=it["occurred_at"], idempotency_key=it["idempotency_key"],
                    request_hash=it["req"], key_version=cur["version"] + 1, author=author)
                st["created"] = True
                b = make_belief(self._key_events(agent_id, key))
                results.append(self._result(i, "created", row, b))
            self._end_write(c, st, rec)
        return results, st["created"]

    @staticmethod
    def _result(i, status, row, b):
        return {"index": i, "status": status, "id": row["id"], "seq": row["seq"], "type": row["type"],
                "key": row["key"], "version": row["key_version"], "recorded_at": iso(row["recorded_at"]),
                "hash": row["hash"],
                "belief": {"present": b["present"], "value": b["value"], "version": b["version"]}}

    def append_action(self, agent_id, a, author="agent", now=None):
        """Log an action; D7: snapshot is computed in the same write transaction."""
        with self.tx() as c:
            st, rec = self._begin_write(c, agent_id, now)
            if a["idempotency_key"]:
                d = self._dup(c, agent_id, a["idempotency_key"], a["req"], "idempotency_key")
                if d is not None:
                    return self._action_out(d, "duplicate"), False
            self._check_causes(c, st, a["caused_by"], "caused_by")
            snap = [snapshot_entry(k, make_belief(self._key_events(agent_id, k))) for k in a["read_keys"]]
            row = self._append(
                c, st, rec, type="action", kind=a["kind"], summary=a["summary"], reason=a["reason"],
                source=a["source"], payload_json=canon(a["payload"]) if a["payload"] is not None else None,
                read_keys=json.dumps(a["read_keys"]), snapshot=canon(snap), caused_by=json.dumps(a["caused_by"]),
                occurred_at=a["occurred_at"], idempotency_key=a["idempotency_key"], request_hash=a["req"],
                author=author)
            st["created"] = True
            self._end_write(c, st, rec)
        return self._action_out(row, "created"), True

    @staticmethod
    def _action_out(row, status):
        return {"status": status, "id": row["id"], "seq": row["seq"], "kind": row["kind"],
                "recorded_at": iso(row["recorded_at"]), "hash": row["hash"],
                "snapshot": json.loads(row["snapshot"])}

    def retract(self, agent_id, event_id, reason, author, now=None):
        reason = _v_text(lambda n: n, "reason", reason, config.max_reason(), required=True)
        with self.tx() as c:
            t = c.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            if t is None or t["agent_id"] != agent_id:
                raise ApiError(404, f"no event {event_id}", "event_id")
            if t["type"] == "action":
                raise ApiError(400, "actions cannot be retracted", "event_id", None)
            if author == "agent" and t["author"] != "agent":
                raise ApiError(403, "agents may only retract events they wrote", "event_id", None)
            evs = self._key_events(agent_id, t["key"])
            killed, _ = analyze(evs)
            if t["id"] in killed:
                raise ApiError(409, "already retracted", "event_id", f"{event_id} is retracted by {killed[t['id']]}")
            before = make_belief(evs)
            st, rec = self._begin_write(c, agent_id, now, author)
            row = self._append(c, st, rec, type="retract", key=t["key"], reason=reason, target=t["id"],
                               key_version=before["version"] + 1, author=author)
            st["created"] = True
            self._end_write(c, st, rec)
            after = make_belief(self._key_events(agent_id, t["key"]))
        return {"id": row["id"], "seq": row["seq"], "key": t["key"], "target": t["id"], "version": row["key_version"],
                "recorded_at": iso(rec), "hash": row["hash"], "before": before, "after": after}

    def log_rejected(self, agent_id, err, endpoint, now=None):
        with self.tx() as c:
            c.execute("INSERT INTO rejected(recorded_at, agent_id, status, error, field, detail, endpoint) "
                      "VALUES(?,?,?,?,?,?,?)",
                      (now or now_ms(), agent_id, err.status, err.error, err.field, err.detail, endpoint))

    # ------------------------------------------------------------- analysis
    def diff(self, agent, s1, s2):
        c1, a1, _ = self.cutoff_for(agent["id"], s1)
        c2, a2, _ = self.cutoff_for(agent["id"], s2)
        swapped = c1 > c2
        if swapped:
            c1, c2 = c2, c1
        b1 = {k: b for k, b in self.beliefs(agent["id"], c1).items() if b["present"]}
        b2 = {k: b for k, b in self.beliefs(agent["id"], c2).items() if b["present"]}
        added = [{"key": k, "new": b2[k]["value"], "new_event": b2[k]["event_id"]} for k in sorted(b2) if k not in b1]
        removed = [{"key": k, "old": b1[k]["value"], "old_event": b1[k]["event_id"]} for k in sorted(b1) if k not in b2]
        changed = [{"key": k, "old": b1[k]["value"], "new": b2[k]["value"], "old_event": b1[k]["event_id"],
                    "new_event": b2[k]["event_id"]}
                   for k in sorted(b1) if k in b2 and canon(b1[k]["value"]) != canon(b2[k]["value"])]
        return {"agent": agent["name"], "from_seq": c1, "to_seq": c2, "swapped": swapped,
                "added": added, "removed": removed, "changed": changed}

    def report(self, agent, frm, to):
        """Events recorded in [frm, to)."""
        aid = agent["id"]
        rows = self.c.execute("SELECT * FROM events WHERE agent_id=? AND recorded_at>=? AND recorded_at<? ORDER BY seq",
                              (aid, frm, to)).fetchall()
        counts = {"set": 0, "delete": 0, "retract": 0, "action": 0}
        keys, deletes, retractions, actions = {}, [], [], []
        for r in rows:
            counts[r["type"]] += 1
            d = row_dict(r)
            if r["type"] in ("set", "delete"):
                ent = keys.setdefault(r["key"], {"key": r["key"], "changes": 0, "first": None})
                ent["changes"] += 1
                snap = {"type": r["type"], "value": d["value"], "event_id": r["id"], "recorded_at": d["recorded_at"],
                        "reason": r["reason"]}
                ent["first"] = ent["first"] or snap
                ent["last"] = snap
                if r["type"] == "delete":
                    deletes.append({"key": r["key"], "event_id": r["id"], "recorded_at": d["recorded_at"],
                                    "reason": r["reason"]})
            elif r["type"] == "retract":
                retractions.append({"id": r["id"], "target": r["target"], "key": r["key"], "reason": r["reason"],
                                    "author": r["author"], "recorded_at": d["recorded_at"]})
            else:
                actions.append({"id": r["id"], "kind": r["kind"], "summary": r["summary"],
                                "recorded_at": d["recorded_at"], "read_keys": d["read_keys"]})
        first_seq = rows[0]["seq"] if rows else None
        for k, ent in keys.items():
            b = make_belief(self._key_events(aid, k, first_seq - 1)) if first_seq else None
            ent["before"] = {"present": b["present"], "value": b["value"]} if b and b["version"] else None
        rej = [{"recorded_at": iso(r["recorded_at"]), "status": r["status"], "error": r["error"], "field": r["field"],
                "detail": r["detail"], "endpoint": r["endpoint"]}
               for r in self.c.execute("SELECT * FROM rejected WHERE agent_id=? AND recorded_at>=? AND recorded_at<? "
                                       "ORDER BY id", (aid, frm, to))]
        return {"agent": agent["name"], "from": iso(frm), "to": iso(to), "total": len(rows), "counts": counts,
                "keys_changed": list(keys.values()), "deletes": deletes, "retractions": retractions,
                "actions": actions, "rejected": rej}

    def export_lines(self, agent_name=None, frm=None, to=None):
        q = ("SELECT e.*, a.name AS agent_name FROM events e JOIN agents a ON a.id=e.agent_id WHERE 1=1")
        args = []
        if agent_name:
            q += " AND a.id=?"
            args.append(self.agent(agent_name)["id"])
        if frm is not None:
            q += " AND e.recorded_at>=?"
            args.append(frm)
        if to is not None:
            q += " AND e.recorded_at<=?"
            args.append(to)
        for r in self.c.execute(q + " ORDER BY e.agent_id, e.seq", args):
            d = row_dict(r)
            d["agent"] = r["agent_name"]
            d["prev_hash"], d["hash"] = r["prev_hash"], r["hash"]
            yield json.dumps(d, sort_keys=True, ensure_ascii=False)

    def status(self):
        n_agents = self.c.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        n_events = self.c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return {"service": "up", "schema_version": self.schema_version(), "agents": n_agents, "events": n_events,
                "rejected_writes": self.c.execute("SELECT COUNT(*) FROM rejected").fetchone()[0],
                "data_dir": str(self.path.parent), "settings": self.settings()}

    def verify(self, agent_name=None):
        """Recompute every hash chain plus derived data (versions, snapshots)."""
        agents = [self.agent(agent_name)] if agent_name else self.c.execute("SELECT * FROM agents ORDER BY id").fetchall()
        report, total, first_problem = [], 0, None
        for a in agents:
            n, problem = self._verify_agent(a)
            total += n
            report.append({"agent": a["name"], "events": n, "ok": problem is None, "problem": problem})
            if problem and first_problem is None:
                first_problem = {"agent": a["name"], **problem}
        return {"ok": first_problem is None, "events": total, "agents": report, "problem": first_problem}

    def _verify_agent(self, a):
        prev, expect, last_ms, n = ZERO_HASH, 1, 0, 0
        versions, by_key, seen = {}, {}, {}
        for r in self.c.execute("SELECT * FROM events WHERE agent_id=? ORDER BY seq", (a["id"],)):
            def bad(why, r=r):
                return n, {"seq": r["seq"], "reason": why}
            if r["seq"] != expect:
                return n, {"seq": expect, "reason": f"sequence gap (found #{r['seq']})"}
            n += 1
            if r["prev_hash"] != prev:
                return bad("prev_hash does not match the previous event")
            if event_hash(prev, row_dict(r)) != r["hash"]:
                return bad("hash mismatch (event content was modified)")
            if r["recorded_at"] < last_ms:
                return bad("recorded_at decreases")
            for cid in json.loads(r["caused_by"]):
                if cid not in seen:
                    return bad(f"caused_by {cid} is not an earlier event")
            if r["type"] != "action":
                k = r["key"]
                if r["key_version"] != versions.get(k, 0) + 1:
                    return bad("key version is not previous + 1")
                if r["type"] == "retract":
                    t = seen.get(r["target"])
                    if t is None or t["type"] == "action" or t["key"] != k:
                        return bad("retract target is invalid")
                versions[k] = r["key_version"]
                by_key.setdefault(k, []).append(r)
            else:
                want = [snapshot_entry(k, make_belief(by_key.get(k, []))) for k in json.loads(r["read_keys"] or "[]")]
                if canon(want) != canon(json.loads(r["snapshot"] or "[]")):
                    return bad("action snapshot does not match a replay of the log")
            seen[r["id"]] = r
            prev, last_ms, expect = r["hash"], r["recorded_at"], expect + 1
        if a["last_seq"] != n or a["last_hash"] != prev:
            return n, {"seq": n + 1, "reason": "agent head does not match the event log (events missing at the tail?)"}
        return n, None
