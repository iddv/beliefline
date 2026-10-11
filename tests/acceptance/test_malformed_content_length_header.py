"""Malformed Content-Length header.

Expected: 400 JSON error, not 500
Source: "spec: errors are JSON with the right HTTP status"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_malformed_content_length_header():
    e = mk()
    try:
        import socket
        k=e.agent("a1")
        s=socket.create_connection(("127.0.0.1",e.port)); s.settimeout(5)
        s.sendall(b"POST /v1/events HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer "+k.encode()+b"\r\nContent-Length: abc\r\n\r\n")
        line=s.recv(200).split(b"\r\n")[0]
        assert b" 400 " in line,line
    finally:
        e.stop()
