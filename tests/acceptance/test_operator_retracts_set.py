"""Operator retracts that set.

Expected: Key now has no belief (read gives 404)
Source: "The last remaining event decides the belief: `set` means its value, `delete` means absent."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_retracts_set():
    e = mk()
    try:
        k=e.agent("a1")
        eid=e.ev("k",k,value="no")[1]["results"][0]["id"]
        assert e.cli("retract",eid,"--reason","bad").returncode==0
        assert e.http("GET","/v1/beliefs?key=k",token=k)[0]==404
    finally:
        e.stop()
