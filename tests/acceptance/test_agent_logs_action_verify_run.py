"""Agent logs an action, then verify is run.

Expected: The action takes sequence 10 in the same chain and verify reports OK including it
Source: "The system records the action as an event in the same chain."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_logs_action_verify_run():
    e = mk()
    try:
        k=e.agent("a1")
        for i in range(9): e.ev("k%d"%i,k,value=i)
        c,b=e.http("POST","/v1/actions",{"kind":"x","summary":"s","read_keys":["k1"]},token=k)
        assert b["seq"]==10,b
        r=e.cli("verify"); assert r.returncode==0 and "OK, 10 events" in r.stdout,r.stdout
    finally:
        e.stop()
