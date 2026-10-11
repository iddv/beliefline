"""Operator runs verify.

Expected: Exits non-zero naming the agent and the first broken sequence number
Source: "Chain broken: `verify` exits non-zero naming the agent and sequence number."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_runs_verify():
    e = mk()
    try:
        import sqlite3
        k=e.agent("a1")
        for i in range(4): e.ev("k%d"%i,k,value=i)
        e.stop()
        db=sqlite3.connect(os.path.join(e.data,"beliefline.db"))
        for t in [r[0] for r in db.execute("select name from sqlite_master where type='trigger'")]: db.execute("drop trigger "+t)
        db.execute("update events set value_json='999' where seq=3"); db.commit(); db.close()
        e.start()
        r=e.cli("verify"); assert r.returncode!=0 and "a1" in (r.stdout+r.stderr) and "3" in (r.stdout+r.stderr),(r.stdout,r.stderr)
    finally:
        e.stop()
