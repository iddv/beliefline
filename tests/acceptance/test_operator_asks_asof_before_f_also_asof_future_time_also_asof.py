"""Operator asks asof before F; also asof a future time; also asof with text 'blah'.

Expected: "agent had no beliefs yet (first event at F)"; future treated as now with a note; "cannot read time; examples: …" with non-zero exit
Source: "Time in the future: treated as now, with a note."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_asks_asof_before_f_also_asof_future_time_also_asof():
    e = mk()
    try:
        k=e.agent("a1"); e.advance(0)
        e.ev("k",k,value=1)
        r=e.cli("asof","a1","2000-01-01 00:00"); assert "agent had no beliefs yet (first event at" in (r.stdout+r.stderr),(r.stdout,r.stderr)
        r=e.cli("asof","a1","2099-01-01 00:00","--key","k"); assert r.returncode==0 and "k = 1" in r.stdout and "future" in r.stdout.lower() or "now" in r.stdout.lower(),(r.stdout,r.stderr)
        r=e.cli("asof","a1","blah"); assert r.returncode!=0 and "cannot read time" in r.stderr and "examples" in r.stderr,r.stderr
    finally:
        e.stop()
