"""Agent sets the key, sets it again, deletes it, then sets it again.

Expected: Versions returned are 1, 2, 3, 4
Source: "Each key's version starts at 1 and increases by 1 on every `set`, `delete` or `retract` affecting it."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sets_key_sets_again_deletes_sets_again():
    e = mk()
    try:
        k=e.agent("a1")
        vs=[]
        vs.append(e.ev("a",k,value=1)[1]["results"][0]["version"])
        vs.append(e.ev("a",k,value=2)[1]["results"][0]["version"])
        vs.append(e.ev("a",k,"delete")[1]["results"][0]["version"])
        vs.append(e.ev("a",k,value=3)[1]["results"][0]["version"])
        assert vs==[1,2,3,4],vs
    finally:
        e.stop()
