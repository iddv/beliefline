"""Operator creates an agent whose name is exactly 64 characters from lowercase letters, digits, '_' and '-'.

Expected: Agent is created and its id is shown
Source: "Agent names: 1–64 chars from `[a-z0-9_-]`, unique."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_creates_agent_whose_name_exactly_64_characters():
    e = mk()
    try:
        name = "a"*32 + "0"*16 + "_"*8 + "-"*8
        assert len(name)==64
        r = e.cli("agent","create",name)
        assert r.returncode==0, r.stderr
        assert "agt_" in r.stdout
    finally:
        e.stop()
