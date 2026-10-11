"""Agent logs an action missing kind, or missing summary.

Expected: 400; no action recorded
Source: "Missing `kind` or `summary`: 400."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_logs_action_missing_kind_missing_summary():
    e = mk()
    try:
        k=e.agent("a1")
        for b_ in [{"summary":"s"},{"kind":"k"},{"kind":"","summary":"s"}]:
            c,b=e.http("POST","/v1/actions",b_,token=k); assert c==400,(b_,c,b)
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==0
    finally:
        e.stop()
