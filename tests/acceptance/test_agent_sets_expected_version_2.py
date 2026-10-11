"""Agent sets it with expected_version 2.

Expected: 409 including current version 3 and the current value; no event written; next successful write gets the next sequence number with no gap
Source: "`expected_version` mismatch: 409 with the current version and value. Nothing is written."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sets_expected_version_2():
    e = mk()
    try:
        k=e.agent("a1")
        for i in range(3): e.ev("a",k,value=i)
        c,b=e.ev("a",k,value=9,expected_version=2)
        assert c==409 and b["current_version"]==3 and b["current_value"]==2,(c,b)
        c,b=e.ev("a",k,value=9,expected_version=3); assert c==201 and b["results"][0]["seq"]==4,b
    finally:
        e.stop()
