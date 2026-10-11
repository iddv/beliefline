"""Agent logs an action with read_keys [k1, k2].

Expected: Action recorded; snapshot lists k1 with its current event id and version and k2 as "absent"
Source: "Read key with no belief: recorded as "absent" in the snapshot, not an error."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_logs_action_read_keys_k1_k2():
    e = mk()
    try:
        k=e.agent("a1")
        eid=e.ev("k1",k,value="v")[1]["results"][0]["id"]
        c,b=e.http("POST","/v1/actions",{"kind":"x","summary":"s","read_keys":["k1","k2"]},token=k)
        assert c==201,(c,b)
        s={x["key"]:x for x in b["snapshot"]}
        assert s["k1"]["event_id"]==eid and s["k1"]["version"]==1 and s["k1"]["status"]!="absent",s
        assert s["k2"]["status"]=="absent",s
    finally:
        e.stop()
