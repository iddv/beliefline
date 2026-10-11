"""Agent then sets it to "yes" with an occurred_at far in the past (before the "no").

Expected: Current belief is "yes"; the occurred_at is stored and shown but does not change ordering
Source: "`occurred_at` (agent-supplied) is stored and shown but never used for ordering."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sets_yes_occurred_far_past_before_no():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("k",k,value="no",occurred_at="2026-01-01T00:00:00Z")
        c,b=e.ev("k",k,value="yes",occurred_at="2020-01-01T00:00:00Z"); assert c==201,(c,b)
        assert e.http("GET","/v1/beliefs?key=k",token=k)[1]["beliefs"][0]["value"]=="yes"
        r=e.cli("history","a1","k"); r=e.cli("explain","evt_2"); assert "2020" in r.stdout,r.stdout
    finally:
        e.stop()
