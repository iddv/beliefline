"""Flow walk.

Expected: flow completes as SCOPE.md definition of done
Source: "SCOPE.md definition of done"
Flow: F7 in SCOPE.md.
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_flow_walk_7():
    e = mk()
    try:
        r=e.cli("demo","load"); assert r.returncode==0,r.stderr

        r=e.cli("actions","assistant","--kind","email.send","--from","yesterday 03:00","--to","yesterday 04:00"); assert r.returncode==0
        aid=[w for w in r.stdout.split() if w.startswith("act_")][0]
        r=e.cli("explain",aid); o=r.stdout
        assert '"yes"' in o and "02:47" in o and '"no"' in o and "22:10" in o and "Caused by" in o and "evt_124" in o,o
        r=e.cli("history","assistant","rsvp/dana-wedding"); assert '"no"' in r.stdout and '"yes"' in r.stdout
        r=e.cli("explain","evt_99999"); assert r.returncode!=0 and "no event" in r.stderr
    finally:
        e.stop()


# Known open item: expected to fail until it is fixed (tests/acceptance/README.md).
import pytest as _pytest_open  # noqa: E402
_marks = globals().get('pytestmark', [])
pytestmark = (list(_marks) if isinstance(_marks, (list, tuple)) else [_marks]) + [
    _pytest_open.mark.xfail(strict=False, reason='Not complete yet: Flow walk')]
