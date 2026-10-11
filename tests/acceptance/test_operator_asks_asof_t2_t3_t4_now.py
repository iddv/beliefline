"""Operator asks asof at t2, t3, t4 and now.

Expected: "yes" at t2, "no" at t3, "yes" at t4 and now
Source: "Drop every event whose retraction (itself not retracted as of T) was recorded at or before T."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_asks_asof_t2_t3_t4_now():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("k",k,value="no"); time.sleep(0.05)
        y=e.ev("k",k,value="yes")[1]["results"][0]; time.sleep(0.05); t2=y["recorded_at"]
        r1=json.loads(e.cli("retract",y["id"],"--reason","r1","--json").stdout); time.sleep(0.05)
        rid=r1.get("retract_id") or r1.get("id") or r1.get("event",{}).get("id")
        assert rid,r1
        r2=json.loads(e.cli("retract",rid,"--reason","undo","--json").stdout)
        def at(t):
            r=e.cli("asof","a1",t,"--key","k"); return r.stdout
        t3=r1.get("recorded_at") or r1["event"]["recorded_at"]; t4=r2.get("recorded_at") or r2["event"]["recorded_at"]
        assert '"yes"' in at(t2) ; assert '"no"' in at(t3) and '"yes"' not in at(t3).split("Retractions")[0]; assert '"yes"' in at(t4)
        assert e.http("GET","/v1/beliefs?key=k",token=k)[1]["beliefs"][0]["value"]=="yes"
    finally:
        e.stop()
