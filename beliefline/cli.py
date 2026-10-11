"""Operator command line. Talks to the local service with the owner token."""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from . import __version__, config
from .store import ApiError, Store, now_ms
from .tz import Zone, iso_to_ms, parse_time, resolve_zone


class CliError(Exception):
    pass


# ------------------------------------------------------------------ config

def cfg_path():
    return config.data_dir() / "cli.json"


def load_cfg():
    try:
        return json.loads(cfg_path().read_text())
    except (OSError, ValueError):
        return {}


def save_cfg(token):
    p = cfg_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    host = config.host()
    host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    data = json.dumps({"url": f"http://{host}:{config.port()}", "owner_token": token}, indent=2)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(data + "\n")
    os.chmod(p, 0o600)


def base_url():
    host = config.host()
    host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    return (config.url() or load_cfg().get("url") or f"http://{host}:{config.port()}").rstrip("/")


class Client:
    def __init__(self):
        self.url = base_url()
        self.token = os.environ.get("BELIEFLINE_OWNER_TOKEN") or load_cfg().get("owner_token") or ""
        self._zone = None

    def call(self, method, path, params=None, body=None, raw=False):
        if params:
            path += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self.token)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                text = r.read().decode()
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode())
            except ValueError:
                err = {"error": f"HTTP {e.code}"}
            msg = err.get("error", f"HTTP {e.code}")
            if err.get("detail") and err["detail"] not in msg:
                msg += f": {err['detail']}"
            elif err.get("field"):
                msg += f" ({err['field']})"
            raise CliError(msg)
        except (urllib.error.URLError, ConnectionError, OSError):
            raise CliError(f"cannot reach Beliefline at {self.url}; is it running? start it with: beliefline start -d")
        return text if raw else (json.loads(text) if text else None)

    @property
    def zone(self):
        if self._zone is None:
            env = os.environ.get("BELIEFLINE_TZ")
            try:
                if env:
                    self._zone = Zone(env)
                else:
                    self._zone = resolve_zone(self.call("GET", "/v1/settings")["display.time_zone"])
            except ValueError as e:
                raise CliError(str(e))
        return self._zone


# ------------------------------------------------------------------ output

def out(s=""):
    print(s)


def V(v, n=160):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 1] + "…"


def table(rows, headers):
    rows = [[("" if c is None else str(c)) for c in r] for r in rows]
    w = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    out("  ".join(h.ljust(w[i]) for i, h in enumerate(headers)).rstrip())
    for r in rows:
        out("  ".join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip())


class R:
    """Rendering helpers bound to a client's display zone."""
    def __init__(self, cl):
        self.cl = cl

    def t(self, s):
        return "-" if not s else self.cl.zone.fmt(iso_to_ms(s))

    def belief(self, b, indent="  "):
        if b["present"]:
            out(f"{indent}{b['key']} = {V(b['value'])}   (v{b['version']})")
            out(f"{indent}  set by {b['event_id']} (event v{b['event_version']}) recorded {self.t(b['recorded_at'])}")
            if b.get("reason"):
                out(f"{indent}  reason: {b['reason']}" + (f"   source: {b['source']}" if b.get("source") else ""))
        else:
            why = (f"deleted by {b['event_id']} at {self.t(b['deleted_at'])}" if b.get("deleted_at")
                   else "no live events (all retracted)")
            out(f"{indent}{b['key']}  (absent; {why}) (v{b['version']})")

    def event_line(self, e):
        v = ""
        if e["type"] == "set":
            v = V(e["value"], 80)
        elif e["type"] == "delete":
            v = "(deleted)"
        elif e["type"] == "retract":
            v = f"retracts {e['target']}"
        elif e["type"] == "action":
            v = f"{e['kind']}: {e['summary']}"
        key = e["key"] or ""
        ver = f"v{e['key_version']}" if e.get("key_version") else ""
        extra = ""
        if e.get("reason"):
            extra += f"  reason: {e['reason']}"
        if e.get("source"):
            extra += f"  source: {e['source']}"
        if e.get("retracted"):
            extra += f"  [RETRACTED by {e['retracted_by']}]"
        return f"#{e['seq']} {e['id']} {self.t(e['recorded_at'])} {e['type']} {key} {ver} {v}{extra}".replace("  ", " ", 0)


# --------------------------------------------------------------- lifecycle

def banner_token(tok):
    out("Owner token (shown once, saved to " + str(cfg_path()) + "):")
    out("  " + tok)


def init_store(show=True):
    store = Store()
    try:
        store.init()
        tok = store.ensure_owner_token()
    except ApiError as e:
        raise CliError(e.error)
    except sqlite3.OperationalError as e:
        raise CliError(f"cannot open store at {store.path}: {e}")
    store.close()
    if tok:
        save_cfg(tok)
        if show:
            banner_token(tok)
    return tok


def healthy(url):
    try:
        with urllib.request.urlopen(url + "/v1/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def cmd_init(a, cl):
    tok = init_store()
    if not tok:
        out(f"Already initialized at {config.data_dir()} (owner token unchanged).")


def cmd_start(a, cl):
    from .server import make_server, port_free
    host, port = config.host(), config.port()
    if a.daemon:
        if healthy(base_url()):
            out(f"Beliefline is already running at {base_url()}")
            return
        init_store()
        if not port_free(host, port):
            raise CliError(f"port {port} in use; set BELIEFLINE_PORT")
        log = config.data_dir() / "beliefline.log"
        with open(log, "ab") as lf:
            p = subprocess.Popen([sys.executable, "-m", "beliefline", "start"], stdout=lf, stderr=lf,
                                 stdin=subprocess.DEVNULL, start_new_session=True,
                                 env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)})
        for _ in range(100):
            if healthy(base_url()):
                out(f"Beliefline running at {base_url()} (pid {p.pid}, log {log})")
                out("Next: beliefline status")
                return
            if p.poll() is not None:
                break
            time.sleep(0.1)
        tail = log.read_text()[-400:].strip().splitlines()
        raise CliError("service failed to start: " + (tail[-1] if tail else f"see {log}"))
    init_store()
    if not port_free(host, port):
        raise CliError(f"port {port} in use; set BELIEFLINE_PORT")
    store = Store()
    try:
        srv = make_server(store, host, port)
    except OSError:
        raise CliError(f"port {port} in use; set BELIEFLINE_PORT")
    out(f"Beliefline {__version__} listening on http://{host}:{port} (data dir {config.data_dir()})")
    sys.stdout.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        out("stopping")


def cmd_status(a, cl):
    s = cl.call("GET", "/v1/status")
    if a.json:
        return s
    out(f"Beliefline {s['version']}: service up at {cl.url}")
    out(f"schema version: {s['schema_version']}")
    out(f"agents: {s['agents']}")
    out(f"events: {s['events']}")
    out("chain: verified" if s["chain_verified"] else
        f"chain: BROKEN at {s['chain_problem']['agent']} seq {s['chain_problem']['seq']}")
    out(f"rejected writes logged: {s['rejected_writes']}")
    out(f"time zone: {s['time_zone']}")
    out(f"data dir: {s['data_dir']}")


def cmd_demo(a, cl):
    d = cl.call("POST", "/v1/demo/load")
    if a.json:
        return d
    out(f"Loaded demo data: {len(d['agents'])} agents, {d['events']} events.")
    out("Demo API keys (shown once):")
    for n, k in d["keys"].items():
        out(f"  {n}: {k}")
    out("Try: beliefline asof assistant \"yesterday 03:14\" --key rsvp/dana-wedding")


def cmd_token(a, cl):
    if a.what == "rotate":
        tok = cl.call("POST", "/v1/token/rotate")["owner_token"]
    else:
        if not (config.data_dir() / "beliefline.db").exists():
            raise CliError(f"no store at {config.data_dir()}")
        tok = Store().rotate_owner_token()
    save_cfg(tok)
    if a.json:
        return {"owner_token": tok}
    out("New owner token (shown once, saved to " + str(cfg_path()) + "):")
    out("  " + tok)


# ---------------------------------------------------------------- agents/keys

def cmd_agent(a, cl):
    p = urllib.parse.quote
    if a.sub == "create":
        d = cl.call("POST", "/v1/agents", body={"name": a.name})
        if a.json:
            return d
        out(f"Created agent {d['name']} (id {d['id']}). Next: beliefline key issue {d['name']}")
    elif a.sub == "list":
        d = cl.call("GET", "/v1/agents")
        if a.json:
            return d
        R_ = R(cl)
        table([[x["name"], x["status"], x["events"], R_.t(x["last_event_at"])] for x in d["agents"]],
              ["NAME", "STATUS", "EVENTS", "LAST EVENT"])
    elif a.sub == "rename":
        d = cl.call("POST", f"/v1/agents/{p(a.name)}/rename", body={"name": a.new})
        if not a.json:
            out(f"Renamed {a.name} to {d['name']}")
        return d if a.json else None
    else:
        d = cl.call("POST", f"/v1/agents/{p(a.name)}/{a.sub}")
        if not a.json:
            out(f"Agent {d['name']} is now {d['status']}" + (" (its keys stop working; history stays queryable)" if d["status"] == "archived" else ""))
        return d if a.json else None


def cmd_key(a, cl):
    if a.sub == "issue":
        d = cl.call("POST", f"/v1/agents/{urllib.parse.quote(a.agent)}/keys", body={"label": a.label})
        if a.json:
            return d
        out(f"Key {d['id']} for agent {d['agent']} (shown once):")
        out("  " + d["key"])
        out("Agent usage: Authorization: Bearer <key>  (GET /v1/whoami to test)")
    elif a.sub == "list":
        d = cl.call("GET", f"/v1/agents/{urllib.parse.quote(a.agent)}/keys" if a.agent else "/v1/keys")
        if a.json:
            return d
        R_ = R(cl)
        table([[k["id"], k["agent"], k["label"], R_.t(k["created_at"]), R_.t(k["last_used_at"]),
                "yes" if k["revoked"] else "no"] for k in d["keys"]],
              ["ID", "AGENT", "LABEL", "CREATED", "LAST USED", "REVOKED"])
    else:
        d = cl.call("POST", f"/v1/keys/{a.key_id}/revoke")
        if a.json:
            return d
        out(f"Revoked {d['id']} (agent {d['agent']})")


# ------------------------------------------------------------------ reading

def time_args(cl, text):
    try:
        kind, v = parse_time(text, cl.zone, now_ms())
    except ValueError as e:
        raise CliError(str(e))
    return kind, v


def cmd_beliefs(a, cl):
    d = cl.call("GET", f"/v1/agents/{urllib.parse.quote(a.agent)}/beliefs", {"key": a.key, "prefix": a.prefix})
    if a.json:
        return d
    if not d["beliefs"]:
        out(f"{a.agent} holds no beliefs" + (f" under prefix {a.prefix}" if a.prefix else "") + ".")
    R_ = R(cl)
    for b in d["beliefs"]:
        R_.belief(b, "")


def cmd_asof(a, cl):
    kind, v = time_args(cl, a.time)
    d = cl.call("GET", f"/v1/agents/{urllib.parse.quote(a.agent)}/asof",
                {"at" if kind == "at" else "seq": v, "key": a.key, "prefix": a.prefix})
    if a.json:
        return d
    R_ = R(cl)
    if d["no_beliefs_yet"]:
        if d["first_event_at"]:
            raise CliError(f"agent had no beliefs yet (first event at {R_.t(d['first_event_at'])})")
        raise CliError("agent had no beliefs yet (it has no events)")
    when = f"as of {R_.t(d['at'])}" if d["at"] else "as of"
    out(f"{d['agent']} {when} (events up to #{d['cutoff_seq']})")
    if d["note"]:
        out(f"note: {d['note']}")
    if not d["beliefs"]:
        out("  no matching beliefs")
    for b in d["beliefs"]:
        R_.belief(b)
    if d["later_retractions"]:
        out("Retractions recorded after this moment (not applied here):")
        for r in d["later_retractions"]:
            out(f"  {r['id']} retracted {r['target']} ({r['key']}) at {R_.t(r['recorded_at'])}: {r['reason']}")


def cmd_history(a, cl):
    d = cl.call("GET", f"/v1/agents/{urllib.parse.quote(a.agent)}/history", {"key": a.key})
    if a.json:
        return d
    R_ = R(cl)
    if not d["events"]:
        out(f"no events for key {a.key}")
    for e in d["events"]:
        out(R_.event_line(e))


def cmd_explain(a, cl):
    d = cl.call("GET", f"/v1/explain/{urllib.parse.quote(a.id)}")
    if a.json:
        return d
    R_ = R(cl)
    e = d["event"]
    out(f"{e['type'].upper()} {e['id']} by agent {e['agent']} (author: {e['author']})")
    out(f"  #{e['seq']} recorded {R_.t(e['recorded_at'])}" + (f", occurred_at {e['occurred_at']}" if e["occurred_at"] else ""))
    if e["type"] == "action":
        out(f"  {e['kind']}: {e['summary']}")
        if e["payload"] is not None:
            out(f"  payload: {V(e['payload'])}")
        out("Beliefs it read:")
        if not d["reads"]:
            out("  (no read keys)")
        for r in d["reads"]:
            state = f"= {V(r['value'])}" if r["status"] == "present" else "(absent)"
            out(f"  {r['key']} {state}  [{r['event_id'] or 'no event'}, key v{r['version']}]")
            out("    history up to this action:")
            for h in r["history"]:
                out("      " + R_.event_line(h))
    elif e["type"] in ("set", "delete"):
        out(f"  {e['key']} {'= ' + V(e['value']) if e['type'] == 'set' else 'deleted'} (v{e['key_version']})")
        if e["reason"]:
            out(f"  reason: {e['reason']}" + (f"   source: {e['source']}" if e["source"] else ""))
        rp = d["replaced"]
        if rp["event_id"]:
            out(f"  replaced: {V(rp['value']) if rp['present'] else '(absent)'} from {rp['event_id']}")
    elif e["type"] == "retract":
        out(f"  retracts {e['target']} ({e['key']}): {e['reason']}")
    out("Caused by:" if d["causes"] else "Caused by: nothing recorded")
    for c in d["causes"]:
        out("  " + "  " * (c["depth"] - 1) + f"<- {R_.event_line(c['event'])}")
    if d["more_causes"]:
        out(f"  … {d['more_causes']} more causes")


def cmd_actions(a, cl):
    p = {}
    for name in ("from", "to"):
        v = getattr(a, name)
        if v:
            try:
                p[name] = parse_time(v, cl.zone, now_ms(), allow_seq=False)[1]
            except ValueError as e:
                raise CliError(str(e))
    p["kind"] = a.kind
    d = cl.call("GET", f"/v1/agents/{urllib.parse.quote(a.agent)}/actions", p)
    if a.json:
        return d
    R_ = R(cl)
    if not d["actions"]:
        out("no actions")
    for x in d["actions"]:
        out(f"{x['id']}  {R_.t(x['recorded_at'])}  {x['kind']}  {x['summary']}")


# ----------------------------------------------------------------- writing

def cmd_set(a, cl):
    try:
        value = json.loads(a.value)
    except ValueError:
        raise CliError(f"value must be JSON (e.g. '\"yes\"', 42, '{{\"a\":1}}'); got {a.value!r}")
    d = cl.call("POST", f"/v1/agents/{urllib.parse.quote(a.agent)}/events",
                body={"key": a.key, "value": value, "reason": a.reason or "", "source": a.source})
    if a.json:
        return d
    out(f"Set {a.key} = {V(value)} as {d['id']} (key v{d['version']})")


def cmd_retract(a, cl):
    ev = cl.call("GET", f"/v1/events/{urllib.parse.quote(a.id)}")
    if ev["type"] == "action":
        raise CliError("actions cannot be retracted")
    d = cl.call("POST", f"/v1/agents/{urllib.parse.quote(ev['agent'])}/retract",
                body={"event_id": a.id, "reason": a.reason or ""})
    if a.json:
        return d
    f = lambda b: V(b["value"]) if b["present"] else "(absent)"
    out(f"Retracted {a.id} as {d['id']} on {d['key']} (agent {ev['agent']})")
    out(f"  before: {f(d['before'])}")
    out(f"  after:  {f(d['after'])}")
    out("  earlier as-of answers are unchanged; undo with: beliefline retract " + d["id"] + " --reason ...")


# ---------------------------------------------------------------- analysis

def cmd_report(a, cl):
    z = cl.zone
    try:
        day = date.fromisoformat(a.day) if a.day else z.today(now_ms()) - timedelta(days=1)
    except ValueError:
        raise CliError("cannot read day; use YYYY-MM-DD")
    d = cl.call("GET", f"/v1/agents/{urllib.parse.quote(a.agent)}/report",
                {"from": z.midnight(day), "to": z.midnight(day + timedelta(days=1))})
    if a.json:
        return d
    R_ = R(cl)
    out(f"Report for {d['agent']} on {day} ({z.spec})")
    if not d["total"] and not d["rejected"]:
        out("  no events")
        return
    c = d["counts"]
    out(f"Events: {d['total']}  (set {c['set']}, delete {c['delete']}, retract {c['retract']}, action {c['action']})")
    out(f"Keys changed: {len(d['keys_changed'])}")
    for k in d["keys_changed"]:
        fv = lambda s: "(deleted)" if s["type"] == "delete" else V(s["value"], 60)
        b = k["before"]
        was = f"was {V(b['value'], 60) if b['present'] else '(absent)'}; " if b else "new; "
        out(f"  {k['key']}: {was}first {fv(k['first'])} -> last {fv(k['last'])}  ({k['changes']} change{'s' if k['changes'] != 1 else ''}, last {k['last']['event_id']} at {R_.t(k['last']['recorded_at'])})")
    out(f"Deletes: {len(d['deletes'])}")
    for x in d["deletes"]:
        out(f"  {x['key']} deleted at {R_.t(x['recorded_at'])} ({x['event_id']})")
    out(f"Retractions: {len(d['retractions'])}")
    for x in d["retractions"]:
        out(f"  {x['id']} retracted {x['target']} ({x['key']}) at {R_.t(x['recorded_at'])}: {x['reason']}")
    out(f"Actions: {len(d['actions'])}")
    for x in d["actions"]:
        out(f"  {R_.t(x['recorded_at'])} {x['id']} {x['kind']}: {x['summary']}")
    out(f"Conflicts and rejected writes: {len(d['rejected'])}")
    for x in d["rejected"]:
        out(f"  {R_.t(x['recorded_at'])} {x['status']} {x['error']}" + (f" - {x['detail']}" if x["detail"] else "")
            + (f" [{x['field']}]" if x["field"] else ""))


def cmd_diff(a, cl):
    p = {}
    for pre, t in (("a_", a.t1), ("b_", a.t2)):
        kind, v = time_args(cl, t)
        p[pre + ("at" if kind == "at" else "seq")] = v
    d = cl.call("GET", f"/v1/agents/{urllib.parse.quote(a.agent)}/diff", p)
    if a.json:
        return d
    if d["swapped"]:
        out("note: t1 is after t2; swapped")
    out(f"{d['agent']}: changes between events #{d['from_seq']} and #{d['to_seq']}")
    for x in d["added"]:
        out(f"  + {x['key']} = {V(x['new'])}")
    for x in d["removed"]:
        out(f"  - {x['key']} (was {V(x['old'])})")
    for x in d["changed"]:
        out(f"  ~ {x['key']}: {V(x['old'])} -> {V(x['new'])}")
    if not (d["added"] or d["removed"] or d["changed"]):
        out("  no differences")


def cmd_export(a, cl):
    if not a.agent and not a.all:
        raise CliError("give an agent name or --all")
    p = {"agent": None if a.all else a.agent}
    for name in ("from", "to"):
        v = getattr(a, name)
        if v:
            try:
                p[name] = parse_time(v, cl.zone, now_ms(), allow_seq=False)[1]
            except ValueError as e:
                raise CliError(str(e))
    sys.stdout.write(cl.call("GET", "/v1/export", p, raw=True))


def cmd_verify(a, cl):
    d = cl.call("GET", "/v1/verify", {"agent": a.agent})
    if a.json:
        out(json.dumps(d, indent=2))
        return 0 if d["ok"] else 1
    if d["ok"]:
        out(f"OK, {d['events']} events")
        return 0
    for x in d["agents"]:
        if x["problem"]:
            out(f"BROKEN: agent {x['agent']} at sequence {x['problem']['seq']}: {x['problem']['reason']}")
    return 1


def cmd_config(a, cl):
    if a.sub == "set":
        d = cl.call("PUT", "/v1/settings", body={"key": a.key, "value": a.value})
    else:
        d = cl.call("GET", "/v1/settings")
    if a.json:
        return d
    for k, v in d.items():
        out(f"{k} = {v}")


def cmd_backup(a, cl):
    d = cl.call("POST", "/v1/backup", body={"path": str(Path(a.file).expanduser().resolve())})
    if a.json:
        return d
    out(f"Backup written to {d['path']}")


def cmd_restore(a, cl):
    src = Path(a.file).expanduser()
    if not src.is_file():
        raise CliError(f"no such backup file: {src}")
    d = config.data_dir()
    db = d / "beliefline.db"
    if healthy(base_url()):
        raise CliError("service is running; stop it before restoring")
    if db.exists():
        c = sqlite3.connect(db)
        try:
            n = c.execute("SELECT (SELECT COUNT(*) FROM agents) + (SELECT COUNT(*) FROM events)").fetchone()[0]
        except sqlite3.Error:
            n = 0
        c.close()
        if n:
            raise CliError(f"data dir is not empty ({db}); restore works only into an empty data dir")
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "restore.tmp.db"
    tmp.unlink(missing_ok=True)
    try:
        s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        t = sqlite3.connect(tmp)
        s.backup(t)
        s.close()
        t.close()
        store = Store(db_path=tmp)
        v = store.verify()
        store.close()
    except sqlite3.Error as e:
        tmp.unlink(missing_ok=True)
        raise CliError(f"not a valid Beliefline backup: {e}")
    if not v["ok"]:
        tmp.unlink(missing_ok=True)
        p = v["problem"]
        raise CliError(f"backup failed verification: agent {p['agent']} sequence {p['seq']}: {p['reason']}; nothing restored")
    for suffix in ("", "-wal", "-shm"):
        Path(str(db) + suffix).unlink(missing_ok=True)
        Path(str(tmp) + suffix).unlink(missing_ok=True) if suffix else None
    os.replace(tmp, db)
    st = Store()
    st.init()
    st.close()
    if a.json:
        return {"ok": True, "events": v["events"]}
    out(f"Restored {v['events']} events from {src}; verify: OK, {v['events']} events")
    out("The owner token is the one the backup was taken with; if you no longer have it run: beliefline token reset")


# --------------------------------------------------------------------- main

def build_parser():
    P = argparse.ArgumentParser(prog="beliefline", description="Append-only memory log for AI agents. Add --json for JSON output.")
    sp = P.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    def add(name, fn, help, **kw):
        s = sp.add_parser(name, help=help, **kw)
        s.set_defaults(fn=fn)
        return s

    add("init", cmd_init, "create the data dir, schema and owner token (start does this too)")
    s = add("start", cmd_start, "initialize if needed and run the service")
    s.add_argument("-d", "--daemon", action="store_true", help="run in the background")
    add("status", cmd_status, "show service state, schema version, counts and chain check")
    s = add("demo", cmd_demo, "load demo data into an empty store")
    s.add_argument("sub", choices=["load"])
    s = add("token", cmd_token, "replace the owner token")
    s.add_argument("what", choices=["rotate", "reset"], help="rotate: via service; reset: offline, if the token is lost")
    s = add("agent", cmd_agent, "create, list, rename, archive, reactivate agents")
    ss = s.add_subparsers(dest="sub", required=True)
    ss.add_parser("create").add_argument("name")
    ss.add_parser("list")
    r = ss.add_parser("rename")
    r.add_argument("name")
    r.add_argument("new")
    ss.add_parser("archive").add_argument("name")
    ss.add_parser("reactivate").add_argument("name")
    s = add("key", cmd_key, "issue, list, revoke agent API keys")
    ss = s.add_subparsers(dest="sub", required=True)
    k = ss.add_parser("issue")
    k.add_argument("agent")
    k.add_argument("--label", default="")
    ss.add_parser("list").add_argument("agent", nargs="?")
    ss.add_parser("revoke").add_argument("key_id")
    s = add("beliefs", cmd_beliefs, "current beliefs of an agent")
    s.add_argument("agent")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--key")
    g.add_argument("--prefix")
    s = add("asof", cmd_asof, "what the agent believed at a past moment")
    s.add_argument("agent")
    s.add_argument("time", help="ISO 8601, '2026-10-09 03:14', 'yesterday 03:14', or #<seq>")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--key")
    g.add_argument("--prefix")
    s = add("history", cmd_history, "every event on a key")
    s.add_argument("agent")
    s.add_argument("key")
    s = add("explain", cmd_explain, "explain an event or action: beliefs read and cause chain")
    s.add_argument("id")
    s = add("actions", cmd_actions, "find actions")
    s.add_argument("agent")
    s.add_argument("--from")
    s.add_argument("--to")
    s.add_argument("--kind")
    s = add("set", cmd_set, "operator-authored set event (use -- before negative numbers)")
    s.add_argument("agent")
    s.add_argument("key")
    s.add_argument("value", help="JSON value")
    s.add_argument("--reason", required=True)
    s.add_argument("--source")
    s = add("retract", cmd_retract, "retract a set/delete/retract event")
    s.add_argument("id")
    s.add_argument("--reason", required=True)
    s = add("report", cmd_report, "daily report (default: yesterday)")
    s.add_argument("agent")
    s.add_argument("--day", help="YYYY-MM-DD in the display zone")
    s = add("diff", cmd_diff, "keys added/removed/changed between two moments")
    s.add_argument("agent")
    s.add_argument("t1")
    s.add_argument("t2")
    s = add("export", cmd_export, "write events as JSONL to stdout")
    s.add_argument("agent", nargs="?")
    s.add_argument("--all", action="store_true")
    s.add_argument("--from")
    s.add_argument("--to")
    s = add("verify", cmd_verify, "recompute hash chains and derived data")
    s.add_argument("agent", nargs="?")
    s = add("config", cmd_config, "show or change operator settings")
    ss = s.add_subparsers(dest="sub", required=True)
    ss.add_parser("list")
    c = ss.add_parser("set")
    c.add_argument("key")
    c.add_argument("value")
    s = add("backup", cmd_backup, "consistent snapshot while the service runs")
    s.add_argument("file")
    s = add("restore", cmd_restore, "restore a backup into an empty data dir")
    s.add_argument("file")
    return P


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [x for x in argv if x != "--json"]
    try:
        a = build_parser().parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2
    a.json = as_json
    try:
        res = a.fn(a, Client())
    except CliError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ApiError as e:
        print(f"error: {e.error}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0
    if isinstance(res, int):
        return res
    if as_json and res is not None:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0
