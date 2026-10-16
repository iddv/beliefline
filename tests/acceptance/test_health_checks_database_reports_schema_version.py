"""/v1/health reads the database and reports its schema version.

Checks: with a healthy database /v1/health answers 200 with ok and schema_version, without any
authentication; with the database file replaced by something unreadable it answers 503, not ok.
Expected: a broken store never looks healthy.
Source: READINESS.md, health endpoint (issue #5).
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import Env


def test_health_checks_database():
    e = Env().start()
    try:
        code, body = e.http("GET", "/v1/health", token=None)
        assert code == 200 and body.get("ok") is True, (code, body)
        assert "schema_version" in body, f"health reports no schema_version: {body}"

        db = os.path.join(e.data, "beliefline.db")
        for suffix in ("-wal", "-shm"):
            if os.path.exists(db + suffix):
                os.remove(db + suffix)
        with open(db, "wb") as f:
            f.write(b"this is not a database " * 200)
        code, body = e.http("GET", "/v1/health", token=None)
        assert code == 503, f"unreadable database: expected 503, got {code} {body}"
    finally:
        e.stop()
