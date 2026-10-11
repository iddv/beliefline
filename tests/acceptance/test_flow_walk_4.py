"""Flow walk.

Expected: flow completes as SCOPE.md definition of done
Source: "SCOPE.md definition of done"
Flow: F4 in SCOPE.md.
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_flow_walk_4():
    e = mk()
    try:
        k=e.agent("assistant")
        e.ev("rsvp/a",k,value="no"); e.ev("rsvp/a",k,value="yes"); y=e.ev("rsvp/b",k,value=1)[1]["results"][0]["id"]; e.ev("other",k,value=1)
        c,b=e.http("GET","/v1/beliefs?prefix=rsvp/",token=k); assert c==200
        m={x["key"]:x for x in b["beliefs"]}
        assert set(m)=={"rsvp/a","rsvp/b"} and m["rsvp/a"]["value"]=="yes" and m["rsvp/a"]["version"]==2 and m["rsvp/a"]["event_id"]=="evt_2" and m["rsvp/a"]["recorded_at"]
        assert e.cli("retract","evt_2","--reason","x").returncode==0
        b=e.http("GET","/v1/beliefs?prefix=rsvp/",token=k)[1]; m={x["key"]:x for x in b["beliefs"]}
        assert m["rsvp/a"]["value"]=="no" and m["rsvp/a"]["event_id"]=="evt_1"
        assert e.http("GET","/v1/beliefs",token=k)[1]["count"]==3
        r=e.cli("beliefs","assistant","--prefix","rsvp/"); assert r.returncode==0 and "rsvp/a" in r.stdout
        assert e.http("GET","/v1/beliefs?key=zzz",token=k)[0]==404
    finally:
        e.stop()
