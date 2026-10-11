"""Operator creates an agent with an empty name, a name containing uppercase letters, a space, or '/'.

Expected: Each is refused with "invalid name"; nothing is created
Source: "Agent names: 1–64 chars from `[a-z0-9_-]`, unique."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_creates_agent_empty_name_name_containing_uppercase():
    e = mk()
    try:
        for n in ["", "Abc", "a b", "a/b"]:
            r = e.cli("agent","create",n)
            assert r.returncode!=0 and "invalid name" in (r.stderr+r.stdout).lower(), (n, r.stderr)
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"]==[]
    finally:
        e.stop()
