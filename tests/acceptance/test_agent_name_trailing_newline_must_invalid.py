"""Agent name with trailing newline must be invalid.

Expected: 400 invalid name
Source: "spec D1: agent names [a-z0-9_-]"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_name_trailing_newline_must_invalid():
    e = mk()
    try:
        c,b=e.http("POST","/v1/agents",{"name":"bad\n"}); assert c==400,(c,b)
    finally:
        e.stop()
