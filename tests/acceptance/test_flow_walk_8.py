"""Flow walk.

Expected: flow completes as SCOPE.md definition of done
Source: "SCOPE.md definition of done"
Flow: F8 in SCOPE.md.
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_flow_walk_8():
    e = mk()
    try:
        r=e.cli("demo","load"); assert r.returncode==0,r.stderr

        r=e.cli("history","assistant","rsvp/dana-wedding"); eid=[l.split()[1] for l in r.stdout.splitlines() if "02:47" in l][0]
        r=e.cli("retract",eid,"--reason","bad summary"); assert r.returncode==0,r.stderr
        r=e.cli("beliefs","assistant","--key","rsvp/dana-wedding"); assert '"no"' in r.stdout and '"yes"' not in r.stdout,r.stdout
        r=e.cli("asof","assistant","yesterday 03:14","--key","rsvp/dana-wedding"); assert '"yes"' in r.stdout.split("Retractions")[0]
        r=e.cli("history","assistant","rsvp/dana-wedding"); assert "RETRACTED" in r.stdout and "retract" in r.stdout and "bad summary" in r.stdout
        r=e.cli("set","assistant","rsvp/dana-wedding",'"no"',"--reason","restore"); assert r.returncode==0,r.stderr
    finally:
        e.stop()
