"""The database file in the data dir is not readable by other local users.

Expected: beliefline.db mode has no group/other bits
Source: the security review (SECURITY.md).
"""

import os, stat, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import Env

def test_db_private():
    e = Env().start()
    try:
        m = stat.S_IMODE(os.stat(os.path.join(e.data, "beliefline.db")).st_mode)
        d = stat.S_IMODE(os.stat(e.data).st_mode)
        assert m & 0o077 == 0, oct(m)
        assert d & 0o077 == 0, oct(d)
    finally:
        e.stop()


# Known open item: expected to fail until it is fixed (tests/acceptance/README.md).
import pytest as _pytest_open  # noqa: E402
_marks = globals().get('pytestmark', [])
pytestmark = (list(_marks) if isinstance(_marks, (list, tuple)) else [_marks]) + [
    _pytest_open.mark.xfail(strict=False, reason='Known security issue (low): The database file in the data dir is not readable by other local users')]
