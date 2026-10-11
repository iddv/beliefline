"""Agent A appends an event with caused_by naming one of B's event ids.

Expected: 400 "unknown cause <id>", same as for a non-existent id; nothing written
Source: "`caused_by` id not found, belonging to another agent, or not earlier: 400 "unknown cause <id>"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_appends_event_caused_naming_one_b_event_ids():
    e = mk()
    try:
        ka=e.agent("a1"); kb=e.agent("b1")
        c,b=e.ev("x",kb,value=1); bid=b["results"][0]["id"]
        c,b=e.ev("y",ka,value=1,caused_by=[bid]); assert c==400 and "unknown cause "+bid in json.dumps(b),(c,b)
        assert e.http("GET","/v1/beliefs",token=ka)[1]["count"]==0
    finally:
        e.stop()
