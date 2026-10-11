"""Flow walk.

Expected: flow completes as SCOPE.md definition of done
Source: "SCOPE.md definition of done"
Flow: F1 in SCOPE.md.
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_flow_walk():
    e = mk()
    try:
        e.stop(); e=Env()
        r=e.cli("start","-d"); assert r.returncode==0,r.stderr
        assert "blo_" in r.stdout, r.stdout
        cj=os.path.join(e.data,"cli.json"); assert oct(os.stat(cj).st_mode&0o777)=="0o600"
        import signal,subprocess
        try:
            r=e.cli("status"); assert r.returncode==0
            for s in ["service up","agents: 0","events: 0","chain: verified"]: assert s in r.stdout,r.stdout
            assert "127.0.0.1:%d"%e.port in r.stdout
            r=e.cli("demo","load"); assert r.returncode==0 and "2 agents" in r.stdout and "blk_" in r.stdout,r.stdout
            r=e.cli("status"); assert "agents: 2" in r.stdout
            n=int(r.stdout.split("events: ")[1].split()[0]); assert 250<=n<=350,n
            assert "chain: verified" in r.stdout
            r=e.cli("demo","load"); assert r.returncode!=0 and "store not empty" in r.stderr
            assert e.http("GET","/v1/status",token="wrong")[0]==401
        finally:
            out=subprocess.run(["bash","-c","ss -ltnp 'sport = :%d' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2"%e.port],capture_output=True,text=True).stdout.strip()
            if out: os.kill(int(out),signal.SIGTERM)
    finally:
        e.stop()
