"""Agent sends a batch of 3 events where only the last is invalid, then sends one valid event.

Expected: The batch gets 400 and none of its events exist; the following valid event gets sequence 6 (no gap)
Source: "If any event fails, the whole batch is rejected and nothing is written."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sends_batch_3_events_where_only_last_invalid_sends_one():
    e = mk()
    try:
        k=e.agent("a1")
        for i in range(5): e.ev("p%d"%i,k,value=i)
        c,b=e.http("POST","/v1/events",[{"type":"set","key":"a","value":1},{"type":"set","key":"b","value":1},{"type":"set","key":"bad key","value":1}],token=k)
        assert c==400
        c,b=e.ev("z",k,value=1); assert c==201 and b["results"][0]["seq"]==6,b
        assert e.http("GET","/v1/beliefs?key=a",token=k)[0]==404
    finally:
        e.stop()
