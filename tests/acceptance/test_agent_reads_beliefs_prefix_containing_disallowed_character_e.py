"""Agent reads beliefs with a prefix containing a disallowed character (e.g. a space).

Expected: 400
Source: "Invalid prefix: 400."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_reads_beliefs_prefix_containing_disallowed_character_e():
    e = mk()
    try:
        k=e.agent("a1")
        c,b=e.http("GET","/v1/beliefs?prefix=rsvp%20x",token=k); assert c==400,(c,b)
    finally:
        e.stop()
