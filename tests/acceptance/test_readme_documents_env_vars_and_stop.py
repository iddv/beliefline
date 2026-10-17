"""Checks that the README documents every BELIEFLINE_* variable the code reads, the health
endpoint and how to stop the service, and that the documented stop (SIGTERM) really stops it.
Expected: each variable appears in the README; /v1/health answers 200; SIGTERM ends the process.
Rule from: READINESS.md (configuration, graceful shutdown, health endpoint, README rows)."""
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _readme():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        return f.read()


def test_every_env_variable_is_in_the_readme():
    readme = _readme()
    names = set()
    for fn in os.listdir(os.path.join(ROOT, "beliefline")):
        if fn.endswith(".py"):
            with open(os.path.join(ROOT, "beliefline", fn), encoding="utf-8") as f:
                names |= set(re.findall(r"BELIEFLINE_[A-Z][A-Z_]*[A-Z]", f.read()))
    missing = sorted(n for n in names if n not in readme)
    assert not missing, f"not in README: {missing}"
    assert "BELIEFLINE_ACCESS_LOG" in readme


def test_readme_documents_health_and_stop():
    readme = _readme()
    assert "/v1/health" in readme
    assert "SIGTERM" in readme
    assert "## Troubleshooting" in readme and "## Limitations" in readme


def test_sigterm_stops_the_service():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with tempfile.TemporaryDirectory() as d:
        env = {**os.environ, "BELIEFLINE_DATA_DIR": d, "BELIEFLINE_PORT": str(port), "PYTHONPATH": ROOT}
        p = subprocess.Popen([sys.executable, "-m", "beliefline", "start"], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            url = f"http://127.0.0.1:{port}/v1/health"
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url, timeout=1) as r:
                        body = json.load(r)
                        assert r.status == 200 and body["ok"] is True
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise AssertionError("service did not come up")
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=10)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
