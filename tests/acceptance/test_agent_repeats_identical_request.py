"""Agent repeats the identical request.

Expected: 200 with the original sequence number, version and event id; no new event; agent's event count unchanged
Source: "Repeated `idempotency_key`: 200 with the original result and no new event."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_repeats_identical_request():
    e = mk()
    try:
        k=e.agent("a1")
        c1,b1=e.ev("a",k,value=1,idempotency_key="K")
        c2,b2=e.ev("a",k,value=1,idempotency_key="K")
        assert c1==201 and c2==200,(c1,c2,b2)
        r1,r2=b1["results"][0],b2["results"][0]
        assert (r1["id"],r1["seq"],r1["version"])==(r2["id"],r2["seq"],r2["version"]),(r1,r2)
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==1
    finally:
        e.stop()
