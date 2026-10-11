"""Agent posts a body that is not valid JSON, an empty body, or an empty batch.

Expected: A 400 JSON error with error, field and detail; the service keeps running
Source: "errors are JSON `{error, field, detail}` with the right HTTP status."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_agent_posts_body_not_valid_json_empty_body_empty_batch():
    e = mk()
    try:
        k=e.agent("a1")
        for raw in [b"{not json", b"", b"[]"]:
            c,b=e.http("POST","/v1/events",raw=raw,token=k)
            assert c==400 and isinstance(b,dict) and {"error","field","detail"}<=set(b),(raw,c,b)
        assert e.http("GET","/v1/whoami",token=k)[0]==200
    finally:
        e.stop()
