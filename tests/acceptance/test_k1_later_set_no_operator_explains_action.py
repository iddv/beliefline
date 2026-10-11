"""K1 is later set to "no" and the operator explains the action.

Expected: Explain still shows the snapshot with "yes", v2 and the setting event id, plus k1's history up to the action only
Source: "for actions, the belief snapshot of each read key with that belief's history up to the action"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_k1_later_set_no_operator_explains_action():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("k1",k,value="no"); eid=e.ev("k1",k,value="yes")[1]["results"][0]["id"]
        aid=e.http("POST","/v1/actions",{"kind":"x","summary":"s","read_keys":["k1"]},token=k)[1]["id"]
        e.ev("k1",k,value="later")
        r=e.cli("explain",aid); assert r.returncode==0,r.stderr
        assert '"yes"' in r.stdout and eid in r.stdout and "later" not in r.stdout and '"no"' in r.stdout,r.stdout
    finally:
        e.stop()
