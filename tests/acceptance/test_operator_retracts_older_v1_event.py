"""Operator retracts the older v1 event.

Expected: Current value stays the v2 value, but the key's version increases by 1
Source: "increases by 1 on every `set`, `delete` or `retract` affecting it."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_retracts_older_v1_event():
    e = mk()
    try:
        k=e.agent("a1")
        v1=e.ev("k",k,value="a")[1]["results"][0]["id"]; e.ev("k",k,value="b")
        r=e.cli("retract",v1,"--reason","old"); assert r.returncode==0,r.stderr
        c,b=e.http("GET","/v1/beliefs?key=k",token=k); assert b["beliefs"][0]["value"]=="b" and b["beliefs"][0]["version"]==3,b
    finally:
        e.stop()
