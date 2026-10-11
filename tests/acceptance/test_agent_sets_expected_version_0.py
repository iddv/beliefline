"""Agent sets it with expected_version 0.

Expected: 409 with the current version and value; nothing written
Source: "`expected_version: 0` means "key must not currently exist"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sets_expected_version_0():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("a",k,value=1)
        c,b=e.ev("a",k,value=2,expected_version=0); assert c==409 and b["current_version"]==1 and b["current_value"]==1,(c,b)
        assert e.http("GET","/v1/whoami",token=k)[0]==200
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==1
    finally:
        e.stop()
