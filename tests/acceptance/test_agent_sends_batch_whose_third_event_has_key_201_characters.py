"""Agent sends a batch whose third event has a key of 201 characters.

Expected: 400 naming event index 2 (the third event) and the key field; no event from the batch is written
Source: "Invalid key, value too large or bad JSON: 400 naming the event index and field."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sends_batch_whose_third_event_has_key_201_characters():
    e = mk()
    try:
        k=e.agent("a1")
        c,b=e.http("POST","/v1/events",[{"type":"set","key":"a","value":1},{"type":"set","key":"b","value":1},{"type":"set","key":"k"*201,"value":1}],token=k)
        assert c==400,(c,b)
        s=json.dumps(b); assert "2" in b.get("field","") and "key" in b["field"], b
        assert e.http("GET","/v1/beliefs",token=k)[1]["count"]==0
    finally:
        e.stop()
