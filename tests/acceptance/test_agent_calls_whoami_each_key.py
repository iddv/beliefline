"""Agent calls whoami with each key.

Expected: Revoked key gets 401 "key revoked"; the other key still works
Source: "Revoked key, or key for an archived agent: 401 "key revoked" or "agent archived"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_calls_whoami_each_key():
    e = mk()
    try:
        k1=e.agent("a1"); id1=e.last_key_id
        k2=e.cli("key","issue","a1","--json"); k2=json.loads(k2.stdout)["key"]
        assert e.cli("key","revoke",id1).returncode==0
        c,b=e.http("GET","/v1/whoami",token=k1); assert c==401 and "key revoked" in json.dumps(b),(c,b)
        c,b=e.http("GET","/v1/whoami",token=k2); assert c==200 and b["agent"]=="a1"
    finally:
        e.stop()
