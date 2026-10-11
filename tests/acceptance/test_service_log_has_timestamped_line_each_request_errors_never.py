"""The service log has a timestamped line for each request and for errors, and never contains keys, tokens or values.

Expected: after a good request and a rejected one, the log shows both with timestamps; the bearer key and owner token are absent
Source: the readiness checks (READINESS.md).
"""

import os, re, signal, time
from _helpers.driver import Env


def test_logs_have_requests_with_timestamps_and_no_secrets():
    e = Env()
    r = e.cli("start", "-d")
    assert r.returncode == 0, r.stderr
    m = re.search(r"blo_\S+", r.stdout)
    e.token = m.group(0)
    pid = int(re.search(r"pid (\d+)", r.stdout).group(1))
    try:
        for _ in range(50):
            code, _b = e.http("GET", "/v1/health", token=None)
            if code == 200:
                break
            time.sleep(0.1)
        e.cli("agent", "create", "a1")
        import json
        key = json.loads(e.cli("key", "issue", "a1", "--json").stdout)["key"]
        e.ev("rsvp/dana", key, value="PERSONAL-VALUE-xyz@example.com")
        e.http("POST", "/v1/events", {"type": "bogus", "key": "k"}, token=key)
        time.sleep(0.3)
        log = open(os.path.join(e.data, "beliefline.log")).read()
        assert re.search(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d", log), "no timestamps in log: %r" % log
        assert "/v1/events" in log, "requests are not logged: %r" % log
        assert re.search(r"\b400\b", log), "rejected request not logged: %r" % log
        for secret in (key, e.token, "PERSONAL-VALUE"):
            assert secret not in log
    finally:
        try: os.kill(pid, signal.SIGTERM)
        except OSError: pass
