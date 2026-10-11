"""Asof #N mid-batch.

Expected: as setting
Source: "ambiguity s4"
Runs with the operator setting `asof.seq_in_batch` = `through_seq` (environment variable ASOF_SEQ_IN_BATCH).
"""

import pytest as _pytest_setting


@_pytest_setting.fixture(autouse=True)
def _operator_setting(monkeypatch):
    monkeypatch.setenv('ASOF_SEQ_IN_BATCH', 'through_seq')


import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_asof_n_mid_batch(monkeypatch):
    monkeypatch.setenv("ASOF_SEQ_IN_BATCH", "through_seq")
    e = mk()
    try:
        k = e.agent("a1")
        c, b = e.http("POST","/v1/events",[{"type":"set","key":"b%d" % i,"value":i} for i in range(3)], token=k)
        assert c == 201
        o = e.cli("asof","a1","#2").stdout
        if "through_seq" == "through_seq":
            assert "b1 =" in o and "b2 =" not in o, o
        else:
            assert "b2 =" in o, o
        o = e.cli("asof","a1","#3").stdout; assert "b2 =" in o
    finally:
        e.stop()
