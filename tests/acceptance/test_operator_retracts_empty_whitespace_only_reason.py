"""Operator retracts it with an empty or whitespace-only reason.

Expected: 400 "reason required"; nothing written
Source: "Empty reason: 400 "reason required"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_retracts_empty_whitespace_only_reason():
    e = mk()
    try:
        k=e.agent("a1")
        eid=e.ev("k",k,value=1)[1]["results"][0]["id"]
        for rs in ["", "   "]:
            r=e.cli("retract",eid,"--reason",rs); assert r.returncode!=0 and "reason required" in r.stderr,(rs,r.stderr)
        c,b=e.http("POST","/v1/agents/a1/retract",{"event_id":eid,"reason":"  "}); assert c==400,(c,b)
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==1
    finally:
        e.stop()
