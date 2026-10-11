"""Version after retract fallback.

Expected: running counter
Source: "ambiguity a1"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_version_after_retract_fallback():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("k",k,value="a"); v2=e.ev("k",k,value="b")[1]["results"][0]["id"]
        assert e.cli("retract",v2,"--reason","x").returncode==0
        b=e.http("GET","/v1/beliefs?key=k",token=k)[1]["beliefs"][0]
        assert b["value"]=="a" and b["version"]==3 and b["event_version"]==1,b
        c,r=e.ev("k",k,value="c",expected_version=3); assert c==201
    finally:
        e.stop()
