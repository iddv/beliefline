"""Delete of absent key.

Expected: as setting
Source: "ambiguity s1"
Runs with the operator setting `writes.delete_absent` = `refused` (environment variable WRITES_DELETE_ABSENT).
"""

import pytest as _pytest_setting


@_pytest_setting.fixture(autouse=True)
def _operator_setting(monkeypatch):
    monkeypatch.setenv('WRITES_DELETE_ABSENT', 'refused')


import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_delete_absent_key_2(monkeypatch):
    monkeypatch.setenv("WRITES_DELETE_ABSENT", "refused")
    e = mk()
    try:
        k = e.agent("a1")
        c, b = e.ev("never", k, "delete")
        if "refused" == "recorded":
            assert c == 201 and b["results"][0]["version"] == 1, (c, b)
            assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"] == 1
            c, b = e.ev("never", k, "delete"); assert c == 201 and b["results"][0]["version"] == 2
        else:
            assert 400 <= c < 500, (c, b)
            assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"] == 0
            e.ev("x", k, value=1); assert e.ev("x", k, "delete")[0] == 201
            c, b = e.ev("x", k, "delete"); assert 400 <= c < 500, (c, b)
    finally:
        e.stop()
