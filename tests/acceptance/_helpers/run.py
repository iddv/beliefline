"""Minimal runner (pytest unavailable here): python3 _helpers/run.py [pattern]"""
import os as _os
# These helpers find the repository from their own location. They live in
# tests/acceptance/_helpers/; paths are computed as if they sat one level below
# the repository root.
_HERE = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))), '_helpers', 'run.py')
import glob, importlib.util, os, sys, traceback, time
root = os.path.dirname(os.path.dirname(os.path.abspath(_HERE))); sys.path.insert(0, root)
pat = sys.argv[1] if len(sys.argv) > 1 else ""
res = {}
for f in sorted(glob.glob(os.path.join(root, "tests/acceptance/_helpers/scenarios/test_*.py"))):
    if pat not in os.path.basename(f): continue
    sp = importlib.util.spec_from_file_location("m", f); m = importlib.util.module_from_spec(sp)
    t = time.time()
    try:
        sp.loader.exec_module(m)
        for n in dir(m):
            if n.startswith("test_"):
                fn = getattr(m, n)
                if fn.__code__.co_argcount:
                    class MP:
                        def __init__(s): s.u = []
                        def setenv(s, k, v): s.u.append((k, os.environ.get(k))); os.environ[k] = v
                    mp = MP()
                    try: fn(mp)
                    finally:
                        for k, o in mp.u:
                            os.environ.pop(k, None) if o is None else os.environ.__setitem__(k, o)
                else: fn()
        st = "pass"; msg = ""
    except BaseException as ex:
        st = "FAIL"; msg = "".join(traceback.format_exception_only(type(ex), ex))[:600] + traceback.format_exc()[-500:]
    print(os.path.basename(f), st, "%.1fs" % (time.time() - t)); 
    if st != "pass": print("   ", msg.replace("\n", "\n    "))
