"""Operator asks asof at a time between t2 and t3.

Expected: "yes" is shown, and the later retraction is listed as not yet recorded at that moment
Source: "Past `asof` answers before the retraction are unchanged."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_asks_asof_time_between_t2_t3():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("k",k,value="no"); time.sleep(0.05)
        y=e.ev("k",k,value="yes")[1]["results"][0]; time.sleep(0.1)
        mid=e.ev("z",k,value=0)[1]["results"][0]["recorded_at"]; time.sleep(0.1)
        assert e.cli("retract",y["id"],"--reason","bad").returncode==0
        r=e.cli("asof","a1",mid,"--key","k"); assert '"yes"' in r.stdout and "evt_" in r.stdout.split("Retractions")[1] and "bad" in r.stdout,r.stdout
    finally:
        e.stop()
