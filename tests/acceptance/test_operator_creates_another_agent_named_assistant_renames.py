"""Operator creates another agent named 'assistant', or renames a different agent to 'assistant'.

Expected: Refused with "name taken"; the existing agent is unchanged
Source: "Duplicate or invalid name: "name taken""
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_creates_another_agent_named_assistant_renames():
    e = mk()
    try:
        assert e.cli("agent","create","assistant").returncode==0
        assert e.cli("agent","create","other").returncode==0
        r=e.cli("agent","create","assistant"); assert r.returncode!=0 and "name taken" in r.stderr, r.stderr
        r=e.cli("agent","rename","other","assistant"); assert r.returncode!=0 and "name taken" in r.stderr, r.stderr
        e.cli("agent","archive","assistant")
        r=e.cli("agent","create","assistant"); assert r.returncode!=0 and "name taken" in r.stderr, r.stderr
        names=sorted(a["name"] for a in json.loads(e.cli("agent","list","--json").stdout)["agents"])
        assert names==["assistant","other"], names
    finally:
        e.stop()
