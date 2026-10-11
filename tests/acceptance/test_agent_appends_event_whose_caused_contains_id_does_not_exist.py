"""Agent appends an event whose caused_by contains an id that does not exist.

Expected: 400 "unknown cause <id>"; nothing written
Source: "`caused_by` id not found, belonging to another agent, or not earlier: 400 "unknown cause <id>"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_appends_event_whose_caused_contains_id_does_not_exist():
    e = mk()
    try:
        k=e.agent("a1")
        c,b=e.ev("a",k,value=1,caused_by=["evt_999"]); assert c==400 and "unknown cause evt_999" in json.dumps(b),(c,b)
        assert e.http("GET","/v1/beliefs",token=k)[1]["count"]==0
    finally:
        e.stop()
