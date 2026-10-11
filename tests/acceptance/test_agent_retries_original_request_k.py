"""Agent retries the original request with K.

Expected: 200 with the original result; no new event, even though state has moved on
Source: "Idempotency keys are unique per agent forever."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_retries_original_request_k():
    e = mk()
    try:
        k=e.agent("a1")
        c,b0=e.ev("a",k,value=1,idempotency_key="K")
        e.advance(3*86400*1000)
        for i in range(5): e.ev("a",k,value=10+i)
        e.restart()
        c,b=e.ev("a",k,value=1,idempotency_key="K")
        assert c==200 and b["results"][0]["id"]==b0["results"][0]["id"],(c,b)
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==6
    finally:
        e.stop()
