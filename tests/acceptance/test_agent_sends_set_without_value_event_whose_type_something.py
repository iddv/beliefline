"""Agent sends a set without a value, or an event whose type is something other than set or delete (e.g. 'update' or 'retract' through the event write).

Expected: 400 naming the event index and field; nothing written
Source: "`type`: `set` or `delete`"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sends_set_without_value_event_whose_type_something():
    e = mk()
    try:
        k=e.agent("a1")
        for ev_ in [{"type":"set","key":"a"},{"type":"update","key":"a","value":1},{"type":"retract","key":"a","value":1}]:
            c,b=e.http("POST","/v1/events",[ev_],token=k)
            assert c==400 and "events[0]" in str(b.get("field")),(ev_,c,b)
        assert e.http("GET","/v1/beliefs",token=k)[1]["count"]==0
    finally:
        e.stop()
