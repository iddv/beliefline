"""Agent appends a set event whose key is exactly 200 allowed characters.

Expected: Accepted; the belief can be read back under that exact key
Source: "Memory keys: 1–200 chars from `[A-Za-z0-9._:/-]`, case-sensitive."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_appends_set_event_whose_key_exactly_200_allowed():
    e = mk()
    try:
        k=e.agent("a1")
        key="a"*100+"/"+"B"*50+".:-_"+"z"*45
        key=key[:200]; assert len(key)==200
        c,b=e.ev(key,k,value=1); assert c==201,(c,b)
        c,b=e.http("GET","/v1/beliefs?key="+key,token=k); assert c==200 and b["beliefs"][0]["value"]==1,(c,b)
    finally:
        e.stop()
