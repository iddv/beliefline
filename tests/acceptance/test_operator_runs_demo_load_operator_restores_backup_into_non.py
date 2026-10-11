"""Operator runs demo load; operator restores a backup into the non-empty data dir.

Expected: Demo load refused "store not empty; demo data only loads into an empty store"; restore refused; existing data unchanged
Source: "`beliefline restore <file>` works only into an empty data dir"
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_operator_runs_demo_load_operator_restores_backup_into_non():
    e = mk()
    try:
        k=e.agent("a1"); e.ev("k",k,value=1)
        r=e.cli("demo","load"); assert r.returncode!=0 and "store not empty; demo data only loads into an empty store" in r.stderr,r.stderr
        b=os.path.join(e.dir,"bk.db"); assert e.cli("backup",b).returncode==0
        e.stop()
        r=e.cli("restore",b); assert r.returncode!=0,r.stdout
        e.start()
        assert json.loads(e.cli("agent","list","--json").stdout)["agents"][0]["events"]==1
    finally:
        e.stop()
