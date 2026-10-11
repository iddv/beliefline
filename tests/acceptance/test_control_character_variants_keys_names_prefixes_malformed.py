"""Control-character variants of keys/names/prefixes and malformed Content-Length.

Expected: all rejected with 400; valid boundary values still accepted
Source: "spec D1"
"""

import json, os, sys, socket
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_control_character_variants_keys_names_prefixes_malformed():
    e = mk()
    try:
        k = e.agent("a1")
        for key in ["a\n", "\na", "a\r", "a\n\n", "a\tb", "a\x00"]:
            assert e.ev(key, k, value=1)[0] == 400, key
        assert e.http("GET", "/v1/beliefs?prefix=ab%0A", token=k)[0] == 400
        for n in ["x\n", "\nx", "X"]:
            assert e.http("POST", "/v1/agents", {"name": n})[0] == 400, n
        assert e.http("POST", "/v1/agents/a1/rename", {"name": "x\n"})[0] == 400
        assert e.ev("a" * 200, k, value=1)[0] == 201
        for cl in [b"abc", b"-5", b"1e3", b""]:
            s = socket.create_connection(("127.0.0.1", e.port)); s.settimeout(3)
            s.sendall(b"POST /v1/events HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer " + k.encode() + b"\r\nContent-Length: " + cl + b"\r\n\r\n")
            assert b" 400 " in s.recv(200).split(b"\r\n")[0], cl
        assert e.cli("verify").returncode == 0
    finally:
        e.stop()
