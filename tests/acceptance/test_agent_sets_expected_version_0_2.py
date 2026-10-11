"""Agent sets it with expected_version 0.

Expected: Accepted with version 3
Source: "`expected_version: 0` means "key must not currently exist"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_sets_expected_version_0_2():
    e = mk()
    try:
        k=e.agent("a1")
        e.ev("a",k,value=1); e.ev("a",k,"delete")
        c,b=e.ev("a",k,value=5,expected_version=0); assert c==201 and b["results"][0]["version"]==3,(c,b)
    finally:
        e.stop()
