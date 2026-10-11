"""Agent sends a different event body with the same idempotency key K.

Expected: 409 "idempotency key reused with different content"; nothing written
Source: "A retry with the same key but a different body returns 409 "idempotency key reused with different content"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sends_different_event_body_same_idempotency_key_k():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("a",k,value=1,idempotency_key="K")
        c,b=e.ev("a",k,value=2,idempotency_key="K")
        assert c==409 and "idempotency key reused with different content" in json.dumps(b),(c,b)
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==1
    finally:
        e.stop()
