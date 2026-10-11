"""Flow walk.

Expected: flow completes as SCOPE.md definition of done
Source: "SCOPE.md definition of done"
Flow: F3 in SCOPE.md.
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_flow_walk_3():
    e = mk()
    try:
        k=e.agent("assistant")
        c,b=e.http("POST","/v1/events",[{"type":"set","key":"a","value":1,"reason":"r"},{"type":"set","key":"a","value":2},{"type":"delete","key":"a"},{"type":"set","key":"b","value":{"x":[1]}}],token=k)
        assert c==201
        assert [r["seq"] for r in b["results"]]==[1,2,3,4] and [r["version"] for r in b["results"]]==[1,2,3,1],b
        assert b["results"][3]["belief"]["value"]=={"x":[1]}
        c,b=e.ev("a",k,value=9,expected_version=1); assert c==409 and b["current_version"]==3
        c,b=e.ev("a",k,value=9,idempotency_key="id1"); assert c==201
        c,b2=e.ev("a",k,value=9,idempotency_key="id1"); assert c==200 and b2["results"][0]["id"]==b["results"][0]["id"]
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==5
        c,b=e.ev("z",k,value=1); assert b["results"][0]["seq"]==6
    finally:
        e.stop()
