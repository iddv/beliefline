"""Agent sets key 'Rsvp/x' to "no" and key 'rsvp/x' to "yes", then reads both.

Expected: Two separate beliefs, each with its own value and version 1
Source: "case-sensitive"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sets_key_rsvp_x_no_key_rsvp_x_yes_reads_both():
    e = mk()
    try:
        k=e.agent("a1")
        assert e.ev("Rsvp/x",k,value="no")[0]==201
        assert e.ev("rsvp/x",k,value="yes")[0]==201
        c,b=e.http("GET","/v1/beliefs",token=k)
        m={x["key"]:x for x in b["beliefs"]}
        assert m["Rsvp/x"]["value"]=="no" and m["Rsvp/x"]["version"]==1 and m["rsvp/x"]["value"]=="yes" and m["rsvp/x"]["version"]==1, m
    finally:
        e.stop()
