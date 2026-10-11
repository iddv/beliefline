"""Agent appends events with an empty key, a key containing a space, or a key with a non-ASCII character.

Expected: Each is refused with 400 naming the key field; nothing is written
Source: "Memory keys: 1–200 chars from `[A-Za-z0-9._:/-]`"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_appends_events_empty_key_key_containing_space_key_non():
    e = mk()
    try:
        k=e.agent("a1")
        for key in ["", "a b", "caf\u00e9"]:
            c,b=e.ev(key,k,value=1)
            assert c==400 and "key" in str(b.get("field")),(key,c,b)
        assert e.http("GET","/v1/beliefs",token=k)[1]["count"]==0
    finally:
        e.stop()
