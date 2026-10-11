"""Flow walk.

Expected: flow completes as SCOPE.md definition of done
Source: "SCOPE.md definition of done"
Flow: F9 in SCOPE.md.
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_flow_walk_9():
    e = mk()
    try:
        r=e.cli("demo","load"); assert r.returncode==0,r.stderr

        r=e.cli("report","assistant"); o=r.stdout; assert r.returncode==0
        assert "rsvp/dana-wedding" in o and "email.send: Sent RSVP yes to Dana" in o and "409" in o,o[-1500:]
        r=e.cli("diff","assistant","2 days ago 23:00","yesterday 04:00"); assert 'rsvp/dana-wedding: "no" -> "yes"' in r.stdout,r.stdout
        r=e.cli("export","assistant"); assert r.returncode==0
        lines=r.stdout.splitlines(); assert len(lines)>100
        for l in lines: j=json.loads(l); assert j["hash"]
        r=e.cli("verify"); assert r.returncode==0 and "OK" in r.stdout,r.stdout
        import sqlite3
        e.stop()
        db=sqlite3.connect(os.path.join(e.data,"beliefline.db"))
        for t in [x[0] for x in db.execute("select name from sqlite_master where type='trigger'")]: db.execute("drop trigger "+t)
        db.execute("update events set reason='tampered' where agent_id=1 and seq=20"); db.commit(); db.close()
        e.start()
        r=e.cli("verify"); assert r.returncode!=0 and "20" in r.stdout+r.stderr and "assistant" in r.stdout+r.stderr,(r.stdout,r.stderr)
    finally:
        e.stop()
