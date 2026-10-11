"""Agent tries to read beliefs and to write an event; operator runs asof and history for it.

Expected: Agent calls get 401 "agent archived" and nothing is written; operator queries return the full history
Source: "Archived agents: reads by the operator still work. Agent writes and reads return 401."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_tries_read_beliefs_write_event_operator_runs_asof():
    e = mk()
    try:
        k=e.agent("a1"); e.ev("rsvp",k,value="no")
        assert e.cli("agent","archive","a1").returncode==0
        c,b=e.http("GET","/v1/beliefs",token=k); assert c==401 and "agent archived" in json.dumps(b),(c,b)
        c,b=e.ev("rsvp",k,value="yes"); assert c==401,(c,b)
        r=e.cli("asof","a1","#1"); assert r.returncode==0 and "no" in r.stdout,r.stdout+r.stderr
        r=e.cli("history","a1","rsvp"); assert r.returncode==0 and "evt_1" in r.stdout
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==1
    finally:
        e.stop()
