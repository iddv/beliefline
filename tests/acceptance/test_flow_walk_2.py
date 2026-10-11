"""Flow walk.

Expected: flow completes as SCOPE.md definition of done
Source: "SCOPE.md definition of done"
Flow: F2 in SCOPE.md.
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_flow_walk_2():
    e = mk()
    try:
        r=e.cli("agent","create","assistant"); assert r.returncode==0 and "agt_" in r.stdout
        r=e.cli("key","issue","assistant","--label","prod"); assert r.returncode==0
        tok=[l.strip() for l in r.stdout.splitlines() if l.strip().startswith("blk_")]
        assert tok, r.stdout
        tok=tok[0]
        c,b=e.http("GET","/v1/whoami",token=tok); assert c==200 and b["agent"]=="assistant",(c,b)
        r=e.cli("agent","list"); assert "assistant" in r.stdout and "active" in r.stdout
        r=e.cli("key","list","assistant"); assert "prod" in r.stdout and tok not in r.stdout
        kid=json.loads(e.cli("key","list","assistant","--json").stdout)
        kid=(kid.get("keys",kid))[0]["id"]
        assert e.cli("key","revoke",kid).returncode==0
        c,b=e.http("GET","/v1/whoami",token=tok); assert c==401,(c,b)
        assert e.cli("agent","rename","assistant","helper").returncode==0
        assert e.cli("agent","archive","helper").returncode==0
        assert e.cli("agent","reactivate","helper").returncode==0
        r=e.cli("key","issue","nobody"); assert r.returncode!=0 and "no agent named nobody" in r.stderr,r.stderr
    finally:
        e.stop()
