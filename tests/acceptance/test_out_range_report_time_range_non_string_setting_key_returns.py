"""An out-of-range report time range or a non-string setting key returns 400, never 500.

Expected: 400 for both
Source: the security review (SECURITY.md).
"""

import json, os, sys, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import Env

def call(e, m, p, body=None):
    r = urllib.request.Request(e.url + p, method=m, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Authorization": "Bearer " + e.token, "Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(r).status
    except urllib.error.HTTPError as ex:
        return ex.code

def test_no_500():
    e = Env().start()
    try:
        call(e, "POST", "/v1/agents", {"name": "a1"})
        assert call(e, "GET", "/v1/agents/a1/report?from=0&to=99999999999999999") == 400
        assert call(e, "PUT", "/v1/settings", {"key": ["x"], "value": "y"}) == 400
    finally:
        e.stop()
