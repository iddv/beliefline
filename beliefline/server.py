"""Local HTTP JSON API."""
import json
import os
import re
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import config
from .store import ApiError, Store, norm_action, norm_batch, now_ms, parse_json, v_key


class Ctx:
    def __init__(self, store, role, agent, key, params, q, handler):
        self.store, self.role, self.agent, self.key = store, role, agent, key
        self.params, self.q, self.h = params, q, handler
        self._body = None

    @property
    def owner(self):
        return self.role == "owner"

    def body(self, default=None):
        if self._body is None:
            raw = self.h.raw_body
            if not raw.strip():
                if default is not None:
                    return default
                raise ApiError(400, "bad JSON", None, "request body is empty")
            try:
                self._body = parse_json(raw.decode("utf-8"))
            except (ValueError, RecursionError) as e:
                raise ApiError(400, "bad JSON", None, str(e))
        return self._body

    def named_agent(self):
        return self.store.agent(unquote(self.params[0]))

    def spec(self, prefix=""):
        """at=<ms> or seq=<n> from the query string."""
        q = self.q
        try:
            if q.get(prefix + "seq") is not None:
                n = int(q[prefix + "seq"])
                if not 0 <= n <= MAX_EPOCH_MS:
                    raise ValueError
                return {"seq": n}
            if q.get(prefix + "at") is not None:
                n = int(q[prefix + "at"])
                if not 0 <= n <= MAX_EPOCH_MS:
                    raise ValueError
                return {"at": n}
        except ValueError:
            raise ApiError(400, "invalid time", prefix + "at", "at must be epoch milliseconds, seq an integer")
        return None

    def int_q(self, name):
        if self.q.get(name) in (None, ""):
            return None
        try:
            n = int(self.q[name])
        except ValueError:
            raise ApiError(400, f"invalid {name}", name, "must be an integer")
        if not 0 <= n <= MAX_EPOCH_MS:
            raise ApiError(400, f"invalid {name}", name, f"must be between 0 and {MAX_EPOCH_MS} (epoch ms, up to year 9999)")
        return n


MAX_EPOCH_MS = 253402300799999  # 9999-12-31T23:59:59.999Z


# ------------------------------------------------------------------ handlers
# Agent-facing

def h_health(x):
    return 200, {"ok": True}


def h_whoami(x):
    return 200, {"agent": x.agent["name"], "agent_id": f"agt_{x.agent['id']}", "key_id": x.key["id"]}


def h_post_events(x):
    items = norm_batch(x.body())
    results, created = x.store.append_events(x.agent["id"], items, author="agent")
    out = {"results": results}
    if len(results) == 1 and not isinstance(x.body(), list) and "events" not in (x.body() or {}):
        out.update(results[0])
    return (201 if created else 200), out


def h_post_actions(x):
    a = norm_action(x.body())
    out, created = x.store.append_action(x.agent["id"], a, author="agent")
    return (201 if created else 200), out


def _beliefs(x, agent, spec=None, include_absent=False):
    q = x.q
    bs = x.store.read_beliefs(agent["id"], q.get("key"), q.get("prefix"), spec, include_absent)
    return 200, {"agent": agent["name"], "beliefs": bs, "count": len(bs)}


def h_agent_beliefs(x):
    return _beliefs(x, x.agent)


def h_agent_history(x):
    return 200, x.store.history(x.agent, x.q.get("key", ""))


def h_event(x):
    aid = x.agent["id"] if x.agent is not None else None
    return 200, x.store.event(unquote(x.params[0]), aid)


def _retract(x, agent, author):
    body = x.body()
    if not isinstance(body, dict) or not isinstance(body.get("event_id"), str):
        raise ApiError(400, "invalid event_id", "event_id", "event_id (string) and reason are required")
    return 201, x.store.retract(agent["id"], body["event_id"], body.get("reason"), author)


def h_agent_retract(x):
    if x.store.settings()["retract.allowed_by"] != "operator_and_agent":
        raise ApiError(403, "agents may not retract", None, "retract.allowed_by is operator_only")
    return _retract(x, x.agent, "agent")


# Operator-facing

def h_status(x):
    st = x.store.status()
    v = x.store.verify()
    st.update(chain_verified=v["ok"], chain_problem=v["problem"], host=config.host(), port=config.port(),
              time_zone=os.environ.get("BELIEFLINE_TZ") or st["settings"]["display.time_zone"],
              version=__import__("beliefline").__version__)
    return 200, st


def h_agents_list(x):
    return 200, {"agents": x.store.list_agents()}


def h_agents_create(x):
    b = x.body()
    return 201, x.store.create_agent(b.get("name") if isinstance(b, dict) else None)


def h_agent_rename(x):
    b = x.body()
    return 200, x.store.rename_agent(unquote(x.params[0]), b.get("name") if isinstance(b, dict) else None)


def h_archive(x):
    return 200, x.store.set_status(unquote(x.params[0]), "archived")


def h_reactivate(x):
    return 200, x.store.set_status(unquote(x.params[0]), "active")


def h_key_issue(x):
    b = x.body(default={})
    return 201, x.store.issue_key(unquote(x.params[0]), b.get("label", "") if isinstance(b, dict) else "")


def h_keys_list(x):
    return 200, {"keys": x.store.list_keys(unquote(x.params[0]) if x.params else None)}


def h_key_revoke(x):
    return 200, x.store.revoke_key(unquote(x.params[0]))


def h_op_beliefs(x):
    return _beliefs(x, x.named_agent(), x.spec())


def h_op_asof(x):
    spec = x.spec()
    if spec is None:
        raise ApiError(400, "missing time", "at", "give at=<epoch ms> or seq=<n>")
    return 200, x.store.asof(x.named_agent(), spec, x.q.get("key"), x.q.get("prefix"))


def h_op_history(x):
    return 200, x.store.history(x.named_agent(), x.q.get("key", ""))


def h_op_set(x):
    a = x.named_agent()
    body = x.body()
    if isinstance(body, dict):
        body = {"type": "set", **body}
        if not (body.get("reason") or "").strip():
            raise ApiError(400, "reason required", "reason", "operator-authored sets need a reason")
        body.setdefault("source", "operator")
    items = norm_batch(body)
    results, created = x.store.append_events(a["id"], items, author="operator")
    return 201, results[0]


def h_op_retract(x):
    return _retract(x, x.named_agent(), "operator")


def h_op_actions(x):
    a = x.named_agent()
    return 200, x.store.actions(a, x.int_q("from"), x.int_q("to"), x.q.get("kind"))


def h_explain(x):
    return 200, x.store.explain(unquote(x.params[0]))


def h_report(x):
    a = x.named_agent()
    frm, to = x.int_q("from"), x.int_q("to")
    if frm is None or to is None:
        raise ApiError(400, "missing range", "from", "from and to (epoch ms) are required")
    return 200, x.store.report(a, frm, to)


def h_diff(x):
    a = x.named_agent()
    s1, s2 = x.spec("a_"), x.spec("b_")
    if s1 is None or s2 is None:
        raise ApiError(400, "missing time", "a_at", "give a_at/a_seq and b_at/b_seq")
    return 200, x.store.diff(a, s1, s2)


def h_export(x):
    lines = list(x.store.export_lines(x.q.get("agent") or None, x.int_q("from"), x.int_q("to")))
    return 200, ("\n".join(lines) + "\n") if lines else ""


def h_verify(x):
    return 200, x.store.verify(x.q.get("agent") or None)


def h_heads(x):
    return 200, x.store.heads()


def h_verify_anchor(x):
    return 200, x.store.verify_anchor(x.body())


def h_backup(x):
    b = x.body()
    if not isinstance(b, dict) or not isinstance(b.get("path"), str) or not b["path"]:
        raise ApiError(400, "invalid path", "path", "path is required")
    return 200, {"path": x.store.backup(b["path"])}


def h_settings(x):
    return 200, x.store.settings()


def h_settings_put(x):
    b = x.body()
    if not isinstance(b, dict):
        raise ApiError(400, "invalid body", None, "expected {key, value}")
    return 200, x.store.put_setting(b.get("key"), b.get("value"))


def h_rotate(x):
    return 200, {"owner_token": x.store.rotate_owner_token()}


def h_demo(x):
    from . import demo
    return 201, demo.load(x.store)


A, O, B, N = "agent", "owner", "both", "none"
ROUTES = [
    ("GET", r"/v1/health", N, h_health),
    ("GET", r"/v1/whoami", A, h_whoami),
    ("POST", r"/v1/events", A, h_post_events),
    ("GET", r"/v1/beliefs", A, h_agent_beliefs),
    ("POST", r"/v1/actions", A, h_post_actions),
    ("GET", r"/v1/history", A, h_agent_history),
    ("POST", r"/v1/retract", A, h_agent_retract),
    ("GET", r"/v1/events/([^/]+)", B, h_event),
    ("GET", r"/v1/status", O, h_status),
    ("GET", r"/v1/agents", O, h_agents_list),
    ("POST", r"/v1/agents", O, h_agents_create),
    ("POST", r"/v1/agents/([^/]+)/rename", O, h_agent_rename),
    ("POST", r"/v1/agents/([^/]+)/archive", O, h_archive),
    ("POST", r"/v1/agents/([^/]+)/reactivate", O, h_reactivate),
    ("POST", r"/v1/agents/([^/]+)/keys", O, h_key_issue),
    ("GET", r"/v1/agents/([^/]+)/keys", O, h_keys_list),
    ("GET", r"/v1/keys", O, h_keys_list),
    ("POST", r"/v1/keys/([^/]+)/revoke", O, h_key_revoke),
    ("GET", r"/v1/agents/([^/]+)/beliefs", O, h_op_beliefs),
    ("GET", r"/v1/agents/([^/]+)/asof", O, h_op_asof),
    ("GET", r"/v1/agents/([^/]+)/history", O, h_op_history),
    ("POST", r"/v1/agents/([^/]+)/events", O, h_op_set),
    ("POST", r"/v1/agents/([^/]+)/retract", O, h_op_retract),
    ("GET", r"/v1/agents/([^/]+)/actions", O, h_op_actions),
    ("GET", r"/v1/agents/([^/]+)/report", O, h_report),
    ("GET", r"/v1/agents/([^/]+)/diff", O, h_diff),
    ("GET", r"/v1/explain/([^/]+)", O, h_explain),
    ("GET", r"/v1/export", O, h_export),
    ("GET", r"/v1/verify", O, h_verify),
    ("GET", r"/v1/heads", O, h_heads),
    ("POST", r"/v1/verify/anchor", O, h_verify_anchor),
    ("POST", r"/v1/backup", O, h_backup),
    ("GET", r"/v1/settings", O, h_settings),
    ("PUT", r"/v1/settings", O, h_settings_put),
    ("POST", r"/v1/token/rotate", O, h_rotate),
    ("POST", r"/v1/demo/load", O, h_demo),
]
ROUTES = [(m, re.compile("^" + p + "$"), role, fn) for m, p, role, fn in ROUTES]


SOCKET_TIMEOUT = 15  # seconds an idle or slow connection may hold a server thread
AUTH_FAIL_LIMIT = 10  # failed credentials per client address within the window, then 429
AUTH_FAIL_WINDOW = 60


class AuthThrottle:
    def __init__(self):
        self.lock = threading.Lock()
        self.fails = {}

    def _recent(self, addr, now):
        lst = [t for t in self.fails.get(addr, ()) if now - t < AUTH_FAIL_WINDOW]
        if lst:
            self.fails[addr] = lst
        else:
            self.fails.pop(addr, None)
        return lst

    def blocked(self, addr):
        with self.lock:
            return len(self._recent(addr, time.monotonic())) >= AUTH_FAIL_LIMIT

    def fail(self, addr):
        with self.lock:
            now = time.monotonic()
            lst = self._recent(addr, now)
            lst.append(now)
            self.fails[addr] = lst
            if len(self.fails) > 10000:
                for a in list(self.fails):
                    self._recent(a, now)


THROTTLE = AuthThrottle()


def log_line(msg):
    sys.stderr.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), msg))
    sys.stderr.flush()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Beliefline"
    timeout = SOCKET_TIMEOUT
    store = None
    raw_body = b""
    status_sent = None
    error_note = None

    def log_request(self, code="-", size="-"):
        pass  # requests are logged by _handle (path only, never the query string)

    def log_message(self, fmt, *args):
        log_line("%s %s" % (self.address_string(), fmt % args))

    def _send(self, status, body, ctype="application/json"):
        self.status_sent = status
        data = body if isinstance(body, bytes) else (
            body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode())
        self.send_response(status)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _handle(self):
        ctx = None
        self.status_sent = self.error_note = None
        try:
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}
            route = None
            path_known = False
            for m, rx, role, fn in ROUTES:
                mt = rx.match(u.path)
                if mt:
                    path_known = True
                    if m == self.command:
                        route = (role, fn, mt.groups())
                        break
            if route is None:
                self._drain()
                raise ApiError(405 if path_known else 404, "method not allowed" if path_known else "not found",
                               None, f"{self.command} {u.path}")
            role, fn, groups = route
            tok = None
            auth = self.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                tok = auth[7:].strip()
            agent = key = None
            eff = role
            try:
                if role == O:
                    if not self.store.check_owner_token(tok):
                        raise ApiError(401, "invalid owner token")
                elif role == A:
                    agent, key = self.store.auth_agent(tok)
                elif role == B:
                    if self.store.check_owner_token(tok):
                        eff = O
                    else:
                        agent, key = self.store.auth_agent(tok)
                        eff = A
            except ApiError as e:
                self._drain()
                if e.status == 401:
                    THROTTLE.fail(self.client_address[0])
                    if THROTTLE.blocked(self.client_address[0]):
                        raise ApiError(429, "too many failed attempts", None, "wait a minute and retry")
                raise
            ctx = Ctx(self.store, eff if role != N else N, agent, key, groups, q, self)
            self._read_body()
            status, body = fn(ctx)
            if isinstance(body, str):
                self._send(status, body, "application/x-ndjson")
            else:
                self._send(status, body)
        except (socket.timeout, TimeoutError):
            self.close_connection = True
            self.error_note = "read timeout"
            try:
                self._send(408, {"error": "request timeout", "field": None, "detail": "request not received in time"})
            except OSError:
                pass
        except ApiError as e:
            self.error_note = e.error if isinstance(getattr(e, "error", None), str) else None
            if ctx is not None and ctx.agent is not None and e.status in (400, 409, 413):
                try:
                    self.store.log_rejected(ctx.agent["id"], e, f"{self.command} {urlparse(self.path).path}")
                except Exception:
                    traceback.print_exc()
            self._send(e.status, e.body())
        except Exception:
            self.error_note = "internal error"
            traceback.print_exc()
            self._send(500, {"error": "internal error", "field": None, "detail": "see service log"})
        finally:
            self.store.close()
            note = getattr(self, "error_note", None)
            log_line("%s %s %s %s%s" % (self.client_address[0], self.command, urlparse(self.path).path,
                                        self.status_sent, f" error: {note}" if note else ""))

    def _drain(self):
        # body not consumed on early errors: don't reuse this connection
        self.close_connection = True

    def _read_body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n < 0:
                raise ValueError
        except ValueError:
            self.close_connection = True
            raise ApiError(400, "invalid Content-Length", "Content-Length", "must be a non-negative integer")
        if n > config.max_body():
            self.close_connection = True
            raise ApiError(413, "request body too large", None, f"max {config.max_body()} bytes")
        self.raw_body = self.rfile.read(n) if n else b""

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _handle


def make_server(store, host=None, port=None):
    handler = type("BoundHandler", (Handler,), {"store": store})
    return ThreadingHTTPServer((host or config.host(), port if port is not None else config.port()), handler)


ThreadingHTTPServer.daemon_threads = True


def port_free(host, port):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()
