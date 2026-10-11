"""Agent logs an action with 51 read keys; then with exactly 50.

Expected: 51 gets 400 and nothing recorded; 50 is accepted
Source: "More than 50 read keys (default): 400."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_logs_action_51_read_keys_exactly_50():
    e = mk()
    try:
        k=e.agent("a1")
        c,b=e.http("POST","/v1/actions",{"kind":"x","summary":"s","read_keys":["k%d"%i for i in range(51)]},token=k); assert c==400,(c,b)
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==0
        c,b=e.http("POST","/v1/actions",{"kind":"x","summary":"s","read_keys":["k%d"%i for i in range(50)]},token=k); assert c==201,(c,b)
    finally:
        e.stop()
