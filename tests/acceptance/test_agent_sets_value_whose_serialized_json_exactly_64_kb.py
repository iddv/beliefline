"""Agent sets a value whose serialized JSON is exactly 64 KB.

Expected: Accepted and returned unchanged on read
Source: "any JSON value, at most 64 KB serialized (default)"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sets_value_whose_serialized_json_exactly_64_kb():
    e = mk()
    try:
        k=e.agent("a1")
        n=65536-2
        v="x"*n
        assert len(json.dumps(v).encode())==65536
        c,b=e.ev("big",k,value=v); assert c==201,(c,str(b)[:200])
        c,b=e.http("GET","/v1/beliefs?key=big",token=k); assert b["beliefs"][0]["value"]==v
    finally:
        e.stop()
