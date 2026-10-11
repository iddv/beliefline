"""Agent sends a batch of exactly 100 valid events.

Expected: All accepted with sequence numbers 8 through 107 and one identical recorded time
Source: "A batch is atomic, takes consecutive sequence numbers and shares one recorded time."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sends_batch_exactly_100_valid_events():
    e = mk()
    try:
        k=e.agent("a1")
        for i in range(7): assert e.ev("p%d"%i,k,value=i)[0]==201
        c,b=e.http("POST","/v1/events",[{"type":"set","key":"k%d"%i,"value":i} for i in range(100)],token=k)
        assert c==201,(c,str(b)[:200])
        seqs=[r["seq"] for r in b["results"]]; assert seqs==list(range(8,108)),seqs
        assert len({r["recorded_at"] for r in b["results"]})==1
    finally:
        e.stop()
