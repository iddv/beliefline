"""In-batch caused_by.

Expected: refused as unknown cause (literal)
Source: "ambiguity a2"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_batch_caused():
    e = mk()
    try:
        k=e.agent("a1")
        c,b=e.http("POST","/v1/events",[{"type":"set","key":"a","value":1},{"type":"set","key":"b","value":1,"caused_by":["0"]}],token=k)
        assert c==400,(c,b)
    finally:
        e.stop()
