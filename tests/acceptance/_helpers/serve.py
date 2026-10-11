"""Launcher: runs the real server with a file-controlled clock offset (the build has no clock hook)."""
import os as _os
# These helpers find the repository from their own location. They live in
# tests/acceptance/_helpers/; paths are computed as if they sat one level below
# the repository root.
_HERE = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))), '_helpers', 'serve.py')
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(_HERE)))
sys.path.insert(0, ROOT)
from beliefline import store, server, cli  # noqa
OFF = os.environ["BL_CLOCK_FILE"]
def _now():
    try:
        off = int(open(OFF).read().strip() or 0)
    except Exception:
        off = 0
    return int(time.time() * 1000) + off
store.now_ms = _now
server.now_ms = _now
sys.argv = ["beliefline", "start"]
sys.exit(cli.main())
