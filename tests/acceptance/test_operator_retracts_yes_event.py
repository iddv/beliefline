"""Operator retracts the "yes" event.

Expected: Output shows before "yes" and after "no"; current beliefs show "no"
Source: "the key falls back to its previous non-retracted value."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_retracts_yes_event():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("k",k,value="no"); eid=e.ev("k",k,value="yes")[1]["results"][0]["id"]
        r=e.cli("retract",eid,"--reason","bad"); assert r.returncode==0,r.stderr
        assert 'before: "yes"' in r.stdout and 'after:  "no"' in r.stdout,r.stdout
        assert e.http("GET","/v1/beliefs?key=k",token=k)[1]["beliefs"][0]["value"]=="no"
    finally:
        e.stop()
