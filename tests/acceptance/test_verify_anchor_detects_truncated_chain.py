"""Operator exports chain heads to a file and checks them later with `verify --anchor`.

Checks: `anchor FILE` writes each agent's (last_seq, last_hash) to FILE. After more events are
appended, `verify --anchor FILE` passes. After the tail of the chain is cut off directly in the
database (agent head rewritten to match, so plain `verify` cannot see it), `verify --anchor FILE`
exits non-zero naming the agent and the sequence number. Both commands support --json.
Source: issue #8, "Add `verify --anchor`: export and check chain heads outside the database".
"""

import json, os, sys, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_verify_anchor_detects_truncated_chain():
    e = mk()
    try:
        k = e.agent("a1")
        for i in range(4): e.ev("k%d" % i, k, value=i)
        anchor = os.path.join(e.data, "heads.anchor")
        r = e.cli("anchor", anchor, check=False)
        assert r.returncode == 0 and os.path.exists(anchor), (r.stdout, r.stderr)
        r = e.cli("anchor", anchor + ".json", "--json", check=False)
        assert r.returncode == 0, (r.stdout, r.stderr)

        e.ev("k4", k, value=4)
        r = e.cli("verify", "--anchor", anchor, check=False)
        assert r.returncode == 0, (r.stdout, r.stderr)
        r = e.cli("verify", "--anchor", anchor, "--json", check=False)
        assert r.returncode == 0 and json.loads(r.stdout)["ok"] is True, (r.stdout, r.stderr)

        e.stop()
        db = sqlite3.connect(os.path.join(e.data, "beliefline.db"))
        for t in [x[0] for x in db.execute("select name from sqlite_master where type='trigger'")]:
            db.execute("drop trigger " + t)
        db.execute("delete from events where seq>=4")
        h = db.execute("select hash from events where seq=3").fetchone()[0]
        db.execute("update agents set last_seq=3, last_hash=?", (h,))
        db.commit(); db.close()
        e.start()

        assert e.cli("verify", check=False).returncode == 0
        r = e.cli("verify", "--anchor", anchor, check=False)
        text = r.stdout + r.stderr
        assert r.returncode != 0 and "a1" in text and "4" in text, (r.stdout, r.stderr)
        r = e.cli("verify", "--anchor", anchor, "--json", check=False)
        assert r.returncode != 0 and json.loads(r.stdout)["ok"] is False, (r.stdout, r.stderr)
    finally:
        e.stop()
