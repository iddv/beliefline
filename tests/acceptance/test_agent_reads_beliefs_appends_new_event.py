"""Agent reads beliefs and appends a new event.

Expected: Beliefs are unchanged; the new event gets the next sequence number and a recorded time not earlier than the previous one; verify OK
Source: "everything survives restarts and crashes. Acknowledged writes are never lost."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_reads_beliefs_appends_new_event():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("k",k,value=1); last=e.ev("j",k,value=2)[1]["results"][0]["recorded_at"]
        e.advance(4*86400*1000); e.restart()
        assert e.http("GET","/v1/beliefs",token=k)[1]["count"]==2
        c,b=e.ev("j",k,value=3); r=b["results"][0]
        assert r["seq"]==3 and r["recorded_at"]>=last,(r,last)
        assert e.cli("verify").returncode==0
    finally:
        e.stop()
