"""Operator retracts it again.

Expected: 409; nothing written
Source: "Target is already retracted: 409."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_retracts_again():
    e = mk()
    try:
        k=e.agent("a1")
        eid=e.ev("k",k,value=1)[1]["results"][0]["id"]
        assert e.cli("retract",eid,"--reason","x").returncode==0
        c,b=e.http("POST","/v1/agents/a1/retract",{"event_id":eid,"reason":"again"}); assert c==409,(c,b)
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==2
    finally:
        e.stop()
