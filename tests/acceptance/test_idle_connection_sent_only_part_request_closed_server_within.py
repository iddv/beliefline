"""An idle connection that sent only part of a request is closed by the server within 25 seconds.

Expected: server times out (408 or close); a correct build sets a socket read timeout
Source: the security review (SECURITY.md).
"""

import os, socket, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import Env

def test_idle_partial_request_is_closed():
    e = Env().start()
    try:
        s = socket.create_connection(("127.0.0.1", e.port))
        s.sendall(b"POST /v1/events HTTP/1.1\r\nHost: x\r\nContent-Length: 100\r\n")
        s.settimeout(25)
        try:
            data = s.recv(100)
        except socket.timeout:
            data = None
        assert data is not None, "server still holds the idle connection after 25s"
    finally:
        e.stop()
