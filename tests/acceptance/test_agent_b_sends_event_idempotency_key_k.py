"""Agent B sends an event with idempotency key K.

Expected: B's event is written normally as a new event
Source: "Idempotency keys are unique per agent forever."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_b_sends_event_idempotency_key_k():
    e = mk()
    try:
        ka=e.agent("a1"); kb=e.agent("b1")
        assert e.ev("a",ka,value=1,idempotency_key="K")[0]==201
        c,b=e.ev("a",kb,value=1,idempotency_key="K"); assert c==201 and b["results"][0]["seq"]==1,(c,b)
    finally:
        e.stop()
