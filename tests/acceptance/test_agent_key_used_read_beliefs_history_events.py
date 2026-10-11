"""Agent A's key is used to read beliefs, history or events.

Expected: Only A's data is ever returned; B's keys and event ids are not visible; whoami returns A's name
Source: "A key can only touch its own agent's data."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_key_used_read_beliefs_history_events():
    e = mk()
    try:
        ka=e.agent("a1"); kb=e.agent("b1")
        bid=e.ev("secret",kb,value="s")[1]["results"][0]["id"]; e.ev("mine",ka,value=1)
        assert e.http("GET","/v1/whoami",token=ka)[1]["agent"]=="a1"
        c,b=e.http("GET","/v1/beliefs",token=ka); assert [x["key"] for x in b["beliefs"]]==["mine"]
        c,b=e.http("GET","/v1/beliefs?key=secret",token=ka); assert c==404
        c,b=e.http("GET","/v1/history?key=secret",token=ka); assert "secret" not in json.dumps(b) or c==404 or b.get("events")==[],(c,b)
        c,b=e.http("GET","/v1/events/"+bid,token=ka); assert c==404,(c,b)
    finally:
        e.stop()
