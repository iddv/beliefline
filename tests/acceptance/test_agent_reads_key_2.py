"""Agent reads that key.

Expected: 404 "no belief for key" including the recorded time of the delete
Source: "plus the time of the last delete if there was one."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_reads_key_2():
    e = mk()
    try:
        k=e.agent("a1")
        c,b=e.ev("a",k,value=1); c,b=e.ev("a",k,"delete"); t=b["results"][0]["recorded_at"]
        c,b=e.http("GET","/v1/beliefs?key=a",token=k)
        assert c==404 and b.get("deleted_at")==t,(c,b,t)
    finally:
        e.stop()
