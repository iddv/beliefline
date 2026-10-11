"""Flow walk.

Expected: flow completes as SCOPE.md definition of done
Source: "SCOPE.md definition of done"
Flow: F5 in SCOPE.md.
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_flow_walk_5():
    e = mk()
    try:
        k=e.agent("assistant")
        a=e.ev("rsvp/a",k,value="yes")[1]["results"][0]
        c,b=e.http("POST","/v1/actions",{"kind":"email.send","summary":"Sent RSVP yes to Dana","payload":{"to":"d"},"read_keys":["rsvp/a","nokey"],"caused_by":[a["id"]]},token=k)
        assert c==201 and b["id"].startswith("act_"),(c,b)
        s={x["key"]:x for x in b["snapshot"]}
        assert s["rsvp/a"]["event_id"]==a["id"] and s["rsvp/a"]["version"]==1 and s["nokey"]["status"]=="absent"
        r=e.cli("actions","assistant","--kind","email.send"); assert b["id"] in r.stdout,r.stdout
    finally:
        e.stop()
