"""Agent appends a set with a reason of 2,001 characters (or a source of 201 characters).

Expected: 400 naming the reason (or source) field; a reason of exactly 2,000 and a source of exactly 200 characters are accepted
Source: "`reason` is at most 2,000 chars (default). `source` is at most 200 chars (default)."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_appends_set_reason_2_001_characters_source_201():
    e = mk()
    try:
        k=e.agent("a1")
        assert e.ev("a",k,value=1,reason="r"*2000,source="s"*200)[0]==201
        c,b=e.ev("a",k,value=1,reason="r"*2001); assert c==400 and "reason" in b["field"],b
        c,b=e.ev("a",k,value=1,source="s"*201); assert c==400 and "source" in b["field"],b
    finally:
        e.stop()
