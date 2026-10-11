import os as _os
# These helpers find the repository from their own location. They live in
# tests/acceptance/_helpers/; paths are computed as if they sat one level below
# the repository root.
_HERE = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))), '_helpers', 'driver.py')
import json, os, socket, subprocess, sys, tempfile, time, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(_HERE)))
BIN = os.path.join(ROOT, "bin", "beliefline")


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Env:
    def __init__(self, **env):
        self.dir = tempfile.mkdtemp(prefix="blv_")
        self.data = os.path.join(self.dir, "data")
        self.port = free_port()
        self.clockfile = os.path.join(self.dir, "clock")
        open(self.clockfile, "w").write("0")
        self.extra = {k: str(v) for k, v in env.items()}
        self.proc = None
        self.token = None
        self.url = f"http://127.0.0.1:{self.port}"

    def env(self):
        e = dict(os.environ)
        e.update(HOME=self.dir, BELIEFLINE_DATA_DIR=self.data, BELIEFLINE_PORT=str(self.port),
                 BELIEFLINE_HOST="127.0.0.1", BELIEFLINE_TZ="utc", BL_CLOCK_FILE=self.clockfile)
        e.pop("BELIEFLINE_URL", None); e.pop("BELIEFLINE_OWNER_TOKEN", None)
        e.update(self.extra)
        return e

    def start(self):
        if self.token is None:
            r = self.cli("init", check=False)
            for ln in r.stdout.splitlines():
                if ln.strip().startswith("blo_"):
                    self.token = ln.strip()
        self.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "tests/acceptance/_helpers", "serve.py")], env=self.env(),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(self.url + "/v1/status", timeout=1)
            except urllib.error.HTTPError:
                break
            except Exception:
                time.sleep(0.1)
            else:
                break
        if self.token is None:
            self.token = json.load(open(os.path.join(self.data, "cli.json")))["owner_token"]
        return self

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try: self.proc.wait(5)
            except Exception: self.proc.kill()
            self.proc = None

    def restart(self):
        self.stop(); self.start()

    def advance(self, ms):
        cur = int(open(self.clockfile).read() or 0)
        open(self.clockfile, "w").write(str(cur + int(ms)))

    def cli(self, *args, check=True, input=None):
        r = subprocess.run([sys.executable, BIN, *args], env=self.env(), capture_output=True, text=True, input=input, timeout=60)
        return r

    def http(self, method, path, body=None, token="owner", raw=None):
        tok = self.token if token == "owner" else token
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.url + path, data=data, method=method)
        if tok:
            req.add_header("Authorization", "Bearer " + tok)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                t = r.read().decode(); code = r.status
        except urllib.error.HTTPError as e:
            t = e.read().decode(); code = e.code
        try:
            return code, json.loads(t)
        except ValueError:
            return code, t

    def agent(self, name="a1", label=None):
        r = self.cli("agent", "create", name)
        assert r.returncode == 0, r.stderr
        r = self.cli("key", "issue", name, *(["--label", label] if label else []), "--json")
        assert r.returncode == 0, r.stderr
        d = json.loads(r.stdout); self.last_key_id = d["id"]
        return d["key"]

    def ev(self, key, tok, typ="set", value=None, **kw):
        e = {"type": typ, "key": key}
        if typ == "set": e["value"] = value
        e.update(kw)
        return self.http("POST", "/v1/events", e, token=tok)


def mk(**env):
    return Env(**env).start()
