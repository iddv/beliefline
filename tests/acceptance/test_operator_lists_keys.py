"""Operator lists keys.

Expected: Each key shows label, created time, last used time and revoked flag, but never the key itself; the key value was shown only at issue
Source: "The system generates a key, shows it once, stores only its hash"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_lists_keys():
    e = mk()
    try:
        k=e.agent("a1",label="prod")
        r=e.cli("key","list","a1","--json"); assert r.returncode==0
        assert k not in r.stdout
        d_=json.loads(r.stdout); ks=d_.get("keys",d_)
        x=ks[0]; assert x["label"]=="prod" and x.get("created_at") and "last_used_at" in x and "revoked" in json.dumps(x),x
        r=e.cli("key","list","a1"); assert k not in r.stdout and "prod" in r.stdout
    finally:
        e.stop()
