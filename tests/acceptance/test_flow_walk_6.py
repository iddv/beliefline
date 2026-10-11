"""Flow walk.

Expected: flow completes as SCOPE.md definition of done
Source: "SCOPE.md definition of done"
Flow: F6 in SCOPE.md.
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_flow_walk_6():
    e = mk()
    try:
        r=e.cli("demo","load"); assert r.returncode==0,r.stderr

        r=e.cli("asof","assistant","yesterday 03:14","--key","rsvp/dana-wedding"); assert r.returncode==0
        assert '"yes"' in r.stdout and "02:47" in r.stdout and "summarized from old thread" in r.stdout,r.stdout
        r=e.cli("asof","assistant","2 days ago 23:00","--key","rsvp/dana-wedding")
        assert '"no"' in r.stdout and "22:10" in r.stdout,r.stdout
    finally:
        e.stop()
