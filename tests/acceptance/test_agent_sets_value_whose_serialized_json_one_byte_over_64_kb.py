"""Agent sets a value whose serialized JSON is one byte over 64 KB.

Expected: 400 naming the event index and the value field; nothing written
Source: "Invalid key, value too large or bad JSON: 400 naming the event index and field."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sets_value_whose_serialized_json_one_byte_over_64_kb():
    e = mk()
    try:
        k=e.agent("a1")
        v="x"*(65536-1)
        assert len(json.dumps(v).encode())==65537
        c,b=e.ev("big",k,value=v); assert c==400 and "value" in str(b.get("field")),(c,str(b)[:200])
        assert e.http("GET","/v1/beliefs",token=k)[1]["count"]==0
    finally:
        e.stop()
