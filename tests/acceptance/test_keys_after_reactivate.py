"""Keys after reactivate.

Expected: as setting
Source: "ambiguity s2"
Runs with the operator setting `agent.reactivate_keys` = `disabled` (environment variable AGENT_REACTIVATE_KEYS).
"""

import pytest as _pytest_setting


@_pytest_setting.fixture(autouse=True)
def _operator_setting(monkeypatch):
    monkeypatch.setenv('AGENT_REACTIVATE_KEYS', 'disabled')


import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_keys_after_reactivate(monkeypatch):
    monkeypatch.setenv("AGENT_REACTIVATE_KEYS", "disabled")
    e = mk()
    try:
        k = e.agent("a1")
        e.ev("k", k, value=1)
        e.cli("agent","archive","a1"); assert e.http("GET","/v1/whoami",token=k)[0] == 401
        assert e.cli("agent","reactivate","a1").returncode == 0
        c, b = e.http("GET","/v1/whoami",token=k)
        if "disabled" == "restored":
            assert c == 200, (c, b)
        else:
            assert c == 401, (c, b)
            k2 = json.loads(e.cli("key","issue","a1","--json").stdout)["key"]
            assert e.http("GET","/v1/whoami",token=k2)[0] == 200
    finally:
        e.stop()
