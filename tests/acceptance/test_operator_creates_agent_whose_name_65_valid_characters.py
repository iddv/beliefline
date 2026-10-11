"""Operator creates an agent whose name is 65 valid characters.

Expected: Refused with "invalid name" and the rule; no agent is created
Source: "Duplicate or invalid name: "name taken" or "invalid name" with the rule."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_creates_agent_whose_name_65_valid_characters():
    e = mk()
    try:
        r = e.cli("agent","create","a"*65)
        assert r.returncode!=0 and "invalid name" in (r.stderr+r.stdout).lower(), r.stderr
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"]==[]
    finally:
        e.stop()
