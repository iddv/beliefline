"""Operator asks asof at exactly R and at R minus 1 ms.

Expected: At R the value is shown; at R minus 1 ms it is not
Source: "Take that key's events with `recorded_at` ≤ T."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_asks_asof_exactly_r_r_minus_1_ms():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("p",k,value=0)
        R=e.ev("k",k,value=1)[1]["results"][0]["recorded_at"]
        import datetime
        dt=datetime.datetime.strptime(R,"%Y-%m-%dT%H:%M:%S.%fZ")
        prev=(dt-datetime.timedelta(milliseconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]+"Z"
        r=e.cli("asof","a1",R,"--key","k"); assert r.returncode==0 and "k = 1" in r.stdout,(r.stdout,r.stderr)
        r=e.cli("asof","a1",prev,"--key","k"); assert "k = 1" not in r.stdout,r.stdout
    finally:
        e.stop()
