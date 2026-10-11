"""A CLI/API call for an operator operation is made with no token, a wrong token, or an agent key.

Expected: 401 "invalid owner token" (or refusal for the agent key); no change made
Source: "Wrong or missing owner token: 401 "invalid owner token"."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_cli_api_call_operator_operation_made_no_token_wrong_token():
    e = mk()
    try:
        k=e.agent("a1")
        for tok in [None,"blo_wrong",k]:
            c,b=e.http("GET","/v1/agents",token=tok); assert c==401,(tok,c,b)
            if tok!=k: assert "invalid owner token" in json.dumps(b),b
            c,b=e.http("POST","/v1/agents",{"name":"zz"},token=tok); assert c==401
        assert [a["name"] for a in e.http("GET","/v1/agents")[1]["agents"]]==["a1"]
    finally:
        e.stop()
