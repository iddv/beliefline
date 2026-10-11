"""Key with trailing newline must be rejected.

Expected: 400 on events[0].key
Source: "convention (spec D1: keys 1-200 chars from [A-Za-z0-9._:/-])"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_key_trailing_newline_must_rejected():
    e = mk()
    try:
        k=e.agent("a1")
        c,b=e.ev("abc\n",k,value=1)
        assert c==400 and "key" in str(b.get("field")),(c,b)
        c,b=e.http("GET","/v1/beliefs?prefix=ab%0A",token=k); assert c==400,(c,b)
    finally:
        e.stop()
