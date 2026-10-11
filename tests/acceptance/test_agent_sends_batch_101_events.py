"""Agent sends a batch of 101 events.

Expected: 413 "max 100 events per batch"; no events written
Source: "Batch too large: 413 "max 100 events per batch"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sends_batch_101_events():
    e = mk()
    try:
        k=e.agent("a1")
        c,b=e.http("POST","/v1/events",[{"type":"set","key":"k%d"%i,"value":i} for i in range(101)],token=k)
        assert c==413 and "max 100 events per batch" in json.dumps(b),(c,b)
        assert e.http("GET","/v1/beliefs",token=k)[1]["count"]==0
    finally:
        e.stop()
