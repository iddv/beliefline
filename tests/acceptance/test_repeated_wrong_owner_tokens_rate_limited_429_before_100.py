"""Repeated wrong owner tokens are rate limited (429) before 100 attempts.

Expected: a 429 or lockout appears
Source: the security review (SECURITY.md).
"""

import os, sys, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import Env

def test_bad_token_rate_limit():
    e = Env().start()
    try:
        codes = set()
        for i in range(100):
            try:
                urllib.request.urlopen(urllib.request.Request(e.url + "/v1/status", headers={"Authorization": "Bearer bad%d" % i}))
            except urllib.error.HTTPError as ex:
                codes.add(ex.code)
        assert 429 in codes, codes
    finally:
        e.stop()
