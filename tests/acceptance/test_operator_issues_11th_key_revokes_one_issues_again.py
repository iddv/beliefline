"""Operator issues an 11th key, then revokes one and issues again.

Expected: The 11th is refused "key limit reached; revoke one first"; after revoking, issuing succeeds
Source: "More than 10 active keys per agent (default): "key limit reached; revoke one first"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_issues_11th_key_revokes_one_issues_again():
    e = mk()
    try:
        k=e.agent("a1"); ids=[e.last_key_id]
        for i in range(9):
            r=e.cli("key","issue","a1","--json"); assert r.returncode==0,r.stderr; ids.append(json.loads(r.stdout)["id"])
        r=e.cli("key","issue","a1"); assert r.returncode!=0 and "key limit reached; revoke one first" in r.stderr,r.stderr
        assert e.cli("key","revoke",ids[0]).returncode==0
        assert e.cli("key","issue","a1").returncode==0
    finally:
        e.stop()
