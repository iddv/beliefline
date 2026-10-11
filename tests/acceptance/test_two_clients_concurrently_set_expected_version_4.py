"""Two clients concurrently set it with expected_version 4.

Expected: Exactly one gets success with version 5; the other gets 409
Source: "Two writers with the same `expected_version` result in exactly one success and one 409."
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from _helpers.driver import *


def test_two_clients_concurrently_set_expected_version_4():
    e = mk()
    try:
        import threading
        k=e.agent("a1")
        for i in range(4): e.ev("a",k,value=i)
        res=[]
        def w(i):
            res.append(e.ev("a",k,value=100+i,expected_version=4)[0])
        ts=[threading.Thread(target=w,args=(i,)) for i in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]
        assert sorted(res)==[201]+[409]*7,res
        c,b=e.http("GET","/v1/beliefs?key=a",token=k); assert b["beliefs"][0]["version"]==5
    finally:
        e.stop()
