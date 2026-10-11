"""Agent reads beliefs with prefix 'rsvp/'.

Expected: Only rsvp/a is returned, with value, version, setting event id and recorded time
Source: "The response shows, per key: value, version, the id of the event that set it, and its recorded time."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_reads_beliefs_prefix_rsvp():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("rsvp/a",k,value=1); e.ev("rsvp/b",k,value=2); e.ev("rsvp/b",k,"delete"); e.ev("rsvpx",k,value=3); e.ev("todo/1",k,value=4)
        c,b=e.http("GET","/v1/beliefs?prefix=rsvp/",token=k)
        assert c==200 and [x["key"] for x in b["beliefs"]]==["rsvp/a"],b
        x=b["beliefs"][0]; assert x["value"]==1 and x["version"]==1 and x["event_id"] and x["recorded_at"],x
    finally:
        e.stop()
