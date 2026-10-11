"""README test command runs.

Expected: documented command passes
Source: "README: python3 -m unittest discover -s tests -v"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_readme_test_command_runs():
    e = mk()
    try:
        import subprocess
        root=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        R=open(os.path.join(root,"README.md")).read()
        assert "python3 -m unittest discover -s tests -v" in R
        assert os.path.isdir(os.path.join(root,"tests"))
        r=subprocess.run([sys.executable,"-m","unittest","discover","-s","tests"],cwd=root,capture_output=True,text=True)
        assert r.returncode==0 and "OK" in r.stderr,r.stderr[-300:]
    finally:
        e.stop()
