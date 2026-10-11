"""Each appends its first event.

Expected: Both events get sequence number 1
Source: "per-agent sequence number (gap-free, starting at 1)"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_each_appends_first_event():
    e = mk()
    try:
        ka=e.agent("a1"); kb=e.agent("b1")
        assert e.ev("x",ka,value=1)[1]["results"][0]["seq"]==1
        assert e.ev("x",kb,value=1)[1]["results"][0]["seq"]==1
    finally:
        e.stop()
