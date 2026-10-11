"""Many clients concurrently append events to the same agent.

Expected: All accepted events have unique, gap-free sequence numbers and verify reports OK
Source: "two writes to the same agent at the same moment are serialized, so sequence numbers are never duplicated or skipped."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_many_clients_concurrently_append_events_same_agent():
    e = mk()
    try:
        import threading
        k=e.agent("a1")
        res=[]
        def w(i):
            for j in range(5):
                c,b=e.ev("k%d_%d"%(i,j),k,value=j); res.append((c,b["results"][0]["seq"] if c==201 else None))
        ts=[threading.Thread(target=w,args=(i,)) for i in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]
        seqs=sorted(s for c,s in res if c==201)
        assert len(seqs)==40 and seqs==list(range(1,41)),(len(seqs),seqs)
        r=e.cli("verify"); assert r.returncode==0 and "OK" in r.stdout,r.stdout+r.stderr
    finally:
        e.stop()
