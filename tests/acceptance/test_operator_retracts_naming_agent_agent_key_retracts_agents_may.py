"""Operator retracts it naming agent A (or agent A's key retracts it when agents may retract).

Expected: 404; nothing written
Source: "Target belongs to another agent: 404."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_retracts_naming_agent_agent_key_retracts_agents_may():
    e = mk()
    try:
        ka=e.agent("a1"); kb=e.agent("b1")
        bid=e.ev("k",kb,value=1)[1]["results"][0]["id"]
        c,b=e.http("POST","/v1/agents/a1/retract",{"event_id":bid,"reason":"x"}); assert c==404,(c,b)
        e.cli("config","set","retract.allowed_by","operator_and_agent")
        c,b=e.http("POST","/v1/retract",{"event_id":bid,"reason":"x"},token=ka); assert c==404,(c,b)
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][1]["events"]==1
    finally:
        e.stop()
