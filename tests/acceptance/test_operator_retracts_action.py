"""Operator retracts the action.

Expected: Refused "actions cannot be retracted"; nothing written
Source: "Target is an action: "actions cannot be retracted"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_retracts_action():
    e = mk()
    try:
        k=e.agent("a1")
        aid=e.http("POST","/v1/actions",{"kind":"x","summary":"s"},token=k)[1]["id"]
        r=e.cli("retract",aid,"--reason","oops"); assert r.returncode!=0 and "actions cannot be retracted" in r.stderr,r.stderr
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==1
    finally:
        e.stop()
