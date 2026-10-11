"""Operator writes on archived.

Expected: as setting
Source: "ambiguity s3"
Runs with the operator setting `archive.operator_writes` = `refused` (environment variable ARCHIVE_OPERATOR_WRITES).
"""

import pytest as _pytest_setting


@_pytest_setting.fixture(autouse=True)
def _operator_setting(monkeypatch):
    monkeypatch.setenv('ARCHIVE_OPERATOR_WRITES', 'refused')


import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_writes_archived_2(monkeypatch):
    monkeypatch.setenv("ARCHIVE_OPERATOR_WRITES", "refused")
    e = mk()
    try:
        k = e.agent("a1")
        eid = e.ev("k", k, value=1)[1]["results"][0]["id"]
        e.cli("agent","archive","a1")
        r1 = e.cli("set","a1","k","2","--reason","op")
        r2 = e.cli("retract",eid,"--reason","op")
        if "refused" == "allowed":
            assert r1.returncode == 0 and r2.returncode == 0, (r1.stderr, r2.stderr)
        else:
            assert r1.returncode != 0 and r2.returncode != 0, (r1.stdout, r2.stdout)
            assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"] == 1
            e.cli("agent","reactivate","a1")
            assert e.cli("set","a1","k","2","--reason","op").returncode == 0
    finally:
        e.stop()
