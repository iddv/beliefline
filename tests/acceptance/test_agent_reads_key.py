"""Agent reads that key.

Expected: 404 "no belief for key" with no delete time
Source: "Key never set, or deleted: 404 "no belief for key", plus the time of the last delete if there was one."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_reads_key():
    e = mk()
    try:
        k=e.agent("a1")
        c,b=e.http("GET","/v1/beliefs?key=nope",token=k)
        assert c==404 and "no belief for key" in b["error"] and not b.get("deleted_at"),(c,b)
    finally:
        e.stop()
