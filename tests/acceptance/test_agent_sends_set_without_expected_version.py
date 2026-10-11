"""Agent sends a set without expected_version.

Expected: 400; nothing written
Source: "when required, writes without one get 400."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sends_set_without_expected_version():
    e = mk(BELIEFLINE_WRITES_VERSION_CHECK="required")
    try:
        k=e.agent("a1")
        c,b=e.ev("a",k,value=1); assert c==400,(c,b)
        assert e.http("GET","/v1/beliefs",token=k)[1]["count"]==0
        c,b=e.ev("a",k,value=1,expected_version=0); assert c==201,(c,b)
    finally:
        e.stop()
