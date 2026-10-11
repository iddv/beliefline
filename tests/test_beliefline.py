"""Run: python3 -m unittest discover -s tests -v"""
import contextlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from beliefline import cli, config  # noqa: E402
from beliefline import server as server_mod  # noqa: E402
from beliefline.server import make_server  # noqa: E402
from beliefline.store import ApiError, Store, norm_action, norm_batch, now_ms  # noqa: E402
from beliefline.tz import Zone, parse_time  # noqa: E402


def ev(typ, key, value=None, **kw):
    d = {"type": typ, "key": key, **kw}
    if typ == "set":
        d["value"] = value
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._env = dict(os.environ)
        os.environ["BELIEFLINE_DATA_DIR"] = self.tmp
        os.environ["BELIEFLINE_TZ"] = "utc"
        for k in list(os.environ):
            if k.startswith("BELIEFLINE_") and k not in ("BELIEFLINE_DATA_DIR", "BELIEFLINE_TZ"):
                del os.environ[k]
        self.store = Store()
        self.store.init()
        self.token = self.store.ensure_owner_token()
        self.aid = self.store.create_agent("bot")["id"]
        self.aid = int(self.aid[4:])

    def tearDown(self):
        self.store.close()
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def w(self, *events, now=None, author="agent"):
        return self.store.append_events(self.aid, norm_batch(list(events)), author=author, now=now)[0]

    def val(self, key, cutoff=None):
        b = self.store.belief(self.aid, key, cutoff)
        return b["value"] if b["present"] else "<absent>"


class BeliefRule(Base):
    def test_d6_retraction_of_retraction(self):
        no = self.w(ev("set", "k", "no"))[0]
        yes = self.w(ev("set", "k", "yes"))[0]
        self.assertEqual(self.val("k"), "yes")
        r1 = self.store.retract(self.aid, yes["id"], "bad", "operator")
        self.assertEqual(self.val("k"), "no")
        self.assertEqual(r1["before"]["value"], "yes")
        self.assertEqual(r1["after"]["value"], "no")
        r2 = self.store.retract(self.aid, r1["id"], "undo", "operator")  # retract the retraction
        self.assertEqual(self.val("k"), "yes")
        r3 = self.store.retract(self.aid, r2["id"], "undo undo", "operator")
        self.assertEqual(self.val("k"), "no")
        # as-of: before the retractions, "yes"; between r1 and r2, "no"
        self.assertEqual(self.val("k", yes["seq"]), "yes")
        self.assertEqual(self.val("k", r1["seq"]), "no")
        self.assertEqual(self.val("k", r2["seq"]), "yes")
        self.assertEqual(self.val("k", r3["seq"]), "no")
        self.assertEqual(self.store.belief(self.aid, "k")["version"], 5)

    def test_retract_all_and_delete(self):
        a = self.w(ev("set", "k", 1))[0]
        d = self.w(ev("delete", "k"))[0]
        self.assertEqual(self.val("k"), "<absent>")
        self.store.retract(self.aid, d["id"], "oops", "operator")
        self.assertEqual(self.val("k"), 1)
        self.store.retract(self.aid, a["id"], "no", "operator")
        self.assertEqual(self.val("k"), "<absent>")

    def test_retract_errors(self):
        a = self.w(ev("set", "k", 1))[0]
        act, _ = self.store.append_action(self.aid, norm_action({"kind": "x", "summary": "y"}))
        for args, status in [((a["id"], "", "operator"), 400), ((act["id"], "r", "operator"), 400),
                             (("evt_9999", "r", "operator"), 404)]:
            with self.assertRaises(ApiError) as cm:
                self.store.retract(self.aid, *args)
            self.assertEqual(cm.exception.status, status)
        self.store.retract(self.aid, a["id"], "r", "operator")
        with self.assertRaises(ApiError) as cm:
            self.store.retract(self.aid, a["id"], "again", "operator")
        self.assertEqual(cm.exception.status, 409)
        other = int(self.store.create_agent("other")["id"][4:])
        with self.assertRaises(ApiError) as cm:  # another agent's event
            self.store.retract(other, a["id"], "r", "operator")
        self.assertEqual(cm.exception.status, 404)

    def test_asof_exact_boundaries(self):
        self.w(ev("set", "k", "a"), now=1_000)
        self.w(ev("set", "k", "b"), now=2_000)
        c = lambda t: self.store.cutoff_for(self.aid, {"at": t})[0]
        self.assertEqual(c(999), 0)
        self.assertEqual(c(1_000), 1)  # at-or-before includes the exact instant
        self.assertEqual(c(1_999), 1)
        self.assertEqual(c(2_000), 2)
        ag = self.store.agent("bot")
        self.assertTrue(self.store.asof(ag, {"at": 999})["no_beliefs_yet"])
        self.assertEqual(self.store.asof(ag, {"seq": 1})["beliefs"][0]["value"], "a")
        # a retraction recorded exactly at T is applied; one recorded after is only listed
        t = self.w(ev("set", "k", "c"), now=3_000)[0]
        self.store.retract(self.aid, t["id"], "r", "operator", now=4_000)
        a4 = self.store.asof(ag, {"at": 4_000})
        self.assertEqual(a4["beliefs"][0]["value"], "b")
        a3 = self.store.asof(ag, {"at": 3_999})
        self.assertEqual(a3["beliefs"][0]["value"], "c")
        self.assertEqual(len(a3["later_retractions"]), 1)

    def test_seq_in_batch_setting(self):
        self.w(ev("set", "a", 1), now=1_000)
        self.w(ev("set", "b", 1), ev("set", "b", 2), ev("set", "b", 3), now=2_000)  # seqs 2-4
        self.w(ev("set", "c", 1), now=3_000)
        ag = self.store.agent("bot")
        for mode, want in (("through_seq", {3: 3, 2: 2, 1: 1, 5: 5}), ("whole_batch", {3: 4, 2: 4, 4: 4, 1: 1, 5: 5})):
            os.environ["ASOF_SEQ_IN_BATCH"] = mode
            for n, cut in want.items():
                self.assertEqual(self.store.asof(ag, {"seq": n})["cutoff_seq"], cut, (mode, n))
        os.environ["ASOF_SEQ_IN_BATCH"] = "through_seq"
        self.assertEqual({b["key"]: b["value"] for b in self.store.asof(ag, {"seq": 3})["beliefs"]}["b"], 2)
        os.environ["ASOF_SEQ_IN_BATCH"] = "whole_batch"
        self.assertEqual({b["key"]: b["value"] for b in self.store.asof(ag, {"seq": 3})["beliefs"]}["b"], 3)

    def test_clock_going_back_reuses_previous(self):
        self.w(ev("set", "k", 1), now=10_000)
        r = self.w(ev("set", "k", 2), now=5_000)[0]
        self.assertEqual(r["recorded_at"], "1970-01-01T00:00:10.000Z")

    def test_future_is_clamped(self):
        self.w(ev("set", "k", 1))
        r = self.store.asof(self.store.agent("bot"), {"at": now_ms() + 10**9})
        self.assertIn("future", r["note"])


class Writes(Base):
    def test_batch_atomic_and_sequence(self):
        res = self.w(ev("set", "a", 1), ev("set", "b", 2), ev("delete", "a"))
        self.assertEqual([r["seq"] for r in res], [1, 2, 3])
        self.assertEqual(len({r["recorded_at"] for r in res}), 1)  # shared recorded time
        self.assertEqual([r["version"] for r in res], [1, 1, 2])
        n = self.store.status()["events"]
        with self.assertRaises(ApiError) as cm:  # validation failure: nothing written
            self.w(ev("set", "c", 1), ev("set", "bad key!", 1))
        self.assertEqual(cm.exception.field, "events[1].key")
        with self.assertRaises(ApiError) as cm:  # conflict mid-batch: nothing written
            self.w(ev("set", "c", 1), ev("set", "a", 5, expected_version=7))
        self.assertEqual(cm.exception.status, 409)
        with self.assertRaises(ApiError) as cm:
            self.w(ev("set", "c", 1), ev("set", "d", 1, caused_by=["evt_999"]))
        self.assertIn("unknown cause", cm.exception.error)
        self.assertEqual(self.store.status()["events"], n)
        self.assertEqual(self.val("c"), "<absent>")
        with self.assertRaises(ApiError) as cm:
            norm_batch([ev("set", "k", 1)] * 101)
        self.assertEqual((cm.exception.status, cm.exception.error), (413, "max 100 events per batch"))

    def test_validation(self):
        bad = [ev("set", "k"), {"type": "set", "key": "k", "value": "x" * 70000}, ev("set", "k", 1, reason="r" * 2001),
               ev("set", "k", 1, source="s" * 201), ev("set", "k", 1, bogus=1), ev("set", "", 1),
               ev("set", "k", 1, expected_version=-1), ev("set", "k", 1, occurred_at="yesterday"),
               {"type": "set", "key": "k"}]
        bad[0].pop("value", None)
        for b in bad:
            with self.assertRaises(ApiError) as cm:
                norm_batch([b])
            self.assertEqual(cm.exception.status, 400, b)

    def test_trailing_newline_rejected(self):
        for b in (ev("set", "abc\n", 1), ev("delete", "abc\n")):
            with self.assertRaises(ApiError) as cm:
                norm_batch([b])
            self.assertEqual(cm.exception.field, "events[0].key")
        for bad in ("bad\n", "x\n"):
            with self.assertRaises(ApiError) as cm:
                self.store.create_agent(bad)
            self.assertEqual(cm.exception.error, "invalid name")
        with self.assertRaises(ApiError):
            self.store.read_beliefs(self.aid, prefix="ab\n")

    def test_expected_version(self):
        self.w(ev("set", "k", 1, expected_version=0))
        with self.assertRaises(ApiError) as cm:
            self.w(ev("set", "k", 2, expected_version=0))
        self.assertEqual(cm.exception.extra["current_version"], 1)
        self.w(ev("set", "k", 2, expected_version=1))
        self.w(ev("delete", "k", expected_version=2))
        self.w(ev("set", "k", 3, expected_version=0))  # deleted counts as "does not currently exist"

    def test_concurrent_same_expected_version(self):
        self.w(ev("set", "k", 0))
        outcomes, barrier = [], threading.Barrier(8)

        def go(i):
            s = Store()
            try:
                barrier.wait()
                s.append_events(self.aid, norm_batch([ev("set", "k", i, expected_version=1)]))
                outcomes.append("ok")
            except ApiError as e:
                outcomes.append(e.status)
            finally:
                s.close()
        ts = [threading.Thread(target=go, args=(i,)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(map(str, outcomes)), ["409"] * 7 + ["ok"])

    def test_concurrent_sequences_gap_free(self):
        def go(i):
            s = Store()
            for j in range(10):
                s.append_events(self.aid, norm_batch([ev("set", f"k{i}", j)]))
            s.close()
        ts = [threading.Thread(target=go, args=(i,)) for i in range(6)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        seqs = [r[0] for r in self.store.c.execute("SELECT seq FROM events ORDER BY seq")]
        self.assertEqual(seqs, list(range(1, 61)))
        self.assertTrue(self.store.verify()["ok"])

    def test_idempotency(self):
        a = self.w(ev("set", "k", 1, idempotency_key="x"))[0]
        b = self.w(ev("set", "k", 1, idempotency_key="x"))[0]
        self.assertEqual((b["status"], b["id"]), ("duplicate", a["id"]))
        self.assertEqual(self.store.status()["events"], 1)
        with self.assertRaises(ApiError) as cm:
            self.w(ev("set", "k", 2, idempotency_key="x"))
        self.assertEqual((cm.exception.status, cm.exception.error), (409, "idempotency key reused with different content"))
        # a retry with expected_version does not re-run the check
        c = self.w(ev("set", "k", 5, expected_version=1, idempotency_key="y"))[0]
        d = self.w(ev("set", "k", 5, expected_version=1, idempotency_key="y"))[0]
        self.assertEqual((d["status"], d["id"]), ("duplicate", c["id"]))

    def test_settings(self):
        self.w(ev("set", "k", 1))
        os.environ["BELIEFLINE_WRITES_UNCHANGED_SET"] = "skip"
        r = self.w(ev("set", "k", 1))[0]
        self.assertEqual((r["status"], r["version"]), ("skipped", 1))
        self.assertEqual(self.store.status()["events"], 1)
        self.w(ev("set", "k", 2))
        self.store.put_setting("writes.unchanged_set", "record")
        self.assertEqual(self.w(ev("set", "k", 2))[0]["status"], "created")
        self.store.put_setting("writes.version_check", "required")
        with self.assertRaises(ApiError) as cm:
            self.w(ev("set", "k", 3))
        self.assertEqual(cm.exception.status, 400)
        self.w(ev("set", "k", 3), author="operator")  # operator writes are exempt
        with self.assertRaises(ApiError):
            self.store.put_setting("retract.allowed_by", "everyone")

    def test_delete_absent_setting(self):
        os.environ["WRITES_DELETE_ABSENT"] = "recorded"
        r = self.w(ev("delete", "ghost"))[0]
        self.assertEqual((r["status"], r["version"]), ("created", 1))
        self.w(ev("set", "k", 1))
        self.w(ev("delete", "k"))
        self.assertEqual(self.w(ev("delete", "k"))[0]["version"], 3)  # already deleted: recorded
        os.environ["WRITES_DELETE_ABSENT"] = "refused"
        n = self.store.status()["events"]
        for key in ("ghost", "k", "never"):
            with self.assertRaises(ApiError) as cm:
                self.w(ev("set", "other", 1), ev("delete", key))
            self.assertEqual((cm.exception.status, cm.exception.field), (400, "events[1].key"))
        self.assertEqual(self.store.status()["events"], n)  # nothing written, even the batch's first event
        self.w(ev("set", "k", 2))
        self.w(ev("delete", "k"))  # present keys can still be deleted
        # the env var overrides a value stored with `config set`
        os.environ.pop("WRITES_DELETE_ABSENT")
        self.store.put_setting("writes.delete_absent", "refused")
        with self.assertRaises(ApiError):
            self.w(ev("delete", "k"))
        os.environ["WRITES_DELETE_ABSENT"] = "recorded"
        self.w(ev("delete", "k"))

    def test_reactivate_keys_setting(self):
        old = self.store.issue_key("bot")
        revoked = self.store.issue_key("bot")
        self.store.revoke_key(revoked["id"])
        for mode in ("restored", "disabled"):
            os.environ["AGENT_REACTIVATE_KEYS"] = mode
            self.store.set_status("bot", "archived")
            with self.assertRaises(ApiError) as cm:
                self.store.auth_agent(old["key"])
            self.assertEqual(cm.exception.error, "agent archived")
            time.sleep(0.01)
            self.store.set_status("bot", "active")
            time.sleep(0.01)
            new = self.store.issue_key("bot")
            if mode == "restored":
                self.assertEqual(self.store.auth_agent(old["key"])[0]["name"], "bot")
            else:
                with self.assertRaises(ApiError) as cm:
                    self.store.auth_agent(old["key"])
                self.assertIn("reactivated", cm.exception.error)
            self.assertEqual(self.store.auth_agent(new["key"])[0]["name"], "bot")
            with self.assertRaises(ApiError) as cm:  # explicit revocation always sticks
                self.store.auth_agent(revoked["key"])
            self.assertEqual(cm.exception.error, "key revoked")
            self.store.revoke_key(new["id"])

    def test_archive_operator_writes_setting(self):
        t = self.w(ev("set", "k", 1))[0]
        self.store.set_status("bot", "archived")
        os.environ["ARCHIVE_OPERATOR_WRITES"] = "allowed"
        self.w(ev("set", "k", 2), author="operator")
        self.store.retract(self.aid, t["id"], "r", "operator")
        os.environ["ARCHIVE_OPERATOR_WRITES"] = "refused"
        n = self.store.status()["events"]
        t2 = self.store.c.execute("SELECT id FROM events WHERE seq=2").fetchone()[0]
        with self.assertRaises(ApiError) as cm:
            self.w(ev("set", "k", 3), author="operator")
        self.assertEqual((cm.exception.status, cm.exception.error), (409, "agent archived"))
        with self.assertRaises(ApiError) as cm:
            self.store.retract(self.aid, t2, "r", "operator")
        self.assertEqual(cm.exception.error, "agent archived")
        self.assertEqual(self.store.status()["events"], n)
        self.assertEqual(self.store.history(self.store.agent("bot"), "k")["key"], "k")  # reads still fine
        self.store.set_status("bot", "active")
        self.w(ev("set", "k", 3), author="operator")

    def test_key_limit_and_revocation(self):
        for _ in range(10):
            k = self.store.issue_key("bot")
        with self.assertRaises(ApiError) as cm:
            self.store.issue_key("bot")
        self.assertEqual(cm.exception.error, "key limit reached; revoke one first")
        self.assertEqual(self.store.auth_agent(k["key"])[0]["name"], "bot")
        self.store.revoke_key(k["id"])
        with self.assertRaises(ApiError) as cm:
            self.store.auth_agent(k["key"])
        self.assertEqual(cm.exception.error, "key revoked")
        k2 = self.store.issue_key("bot")
        self.store.set_status("bot", "archived")
        with self.assertRaises(ApiError) as cm:
            self.store.auth_agent(k2["key"])
        self.assertEqual(cm.exception.error, "agent archived")
        self.assertEqual(self.store.history(self.store.agent("bot"), "k")["events"], [])  # operator reads still work
        # keys are stored hashed
        self.assertNotIn(k2["key"], json.dumps([tuple(r) for r in self.store.c.execute("SELECT * FROM api_keys")]))
        with self.assertRaises(ApiError):
            self.store.create_agent("Bad Name")
        with self.assertRaises(ApiError) as cm:
            self.store.create_agent("bot")
        self.assertEqual(cm.exception.error, "name taken")


class Actions(Base):
    def test_snapshot(self):
        a = self.w(ev("set", "rsvp", "no"))[0]
        b = self.w(ev("set", "rsvp", "yes"))[0]
        out, _ = self.store.append_action(self.aid, norm_action(
            {"kind": "email.send", "summary": "Sent", "read_keys": ["rsvp", "ghost"], "caused_by": [b["id"]]}))
        s = {x["key"]: x for x in out["snapshot"]}
        self.assertEqual((s["rsvp"]["event_id"], s["rsvp"]["version"], s["rsvp"]["value"]), (b["id"], 2, "yes"))
        self.assertEqual(s["ghost"]["status"], "absent")
        self.store.retract(self.aid, b["id"], "bad", "operator")
        # the stored snapshot is unchanged; explain shows it with history up to the action
        x = self.store.explain(out["id"])
        self.assertEqual(x["reads"][0]["event_id"], b["id"])
        self.assertEqual([h["id"] for h in x["reads"][0]["history"]], [a["id"], b["id"]])
        self.assertEqual(x["causes"][0]["event"]["id"], b["id"])
        with self.assertRaises(ApiError) as cm:
            self.store.explain("evt_nope")
        self.assertEqual(cm.exception.error, "no event evt_nope")
        self.assertTrue(self.store.verify()["ok"])

    def test_validation_and_cause_depth(self):
        for bad in [{"summary": "s"}, {"kind": "k"}, {"kind": "k", "summary": "s", "read_keys": ["a"] * 1 + [f"k{i}" for i in range(60)]}]:
            with self.assertRaises(ApiError) as cm:
                norm_action(bad)
            self.assertEqual(cm.exception.status, 400)
        prev = []
        ids = []
        for i in range(14):
            r = self.w(ev("set", f"c{i}", i, caused_by=prev))[0]
            prev = [r["id"]]
            ids.append(r["id"])
        x = self.store.explain(ids[-1])
        self.assertEqual(len(x["causes"]), 10)
        self.assertEqual(x["more_causes"], 3)

    def test_action_search(self):
        for k in ("email.send", "email.draft", "calendar.add"):
            self.store.append_action(self.aid, norm_action({"kind": k, "summary": "s"}))
        ag = self.store.agent("bot")
        self.assertEqual(len(self.store.actions(ag, kind="email")["actions"]), 2)
        self.assertEqual(len(self.store.actions(ag, kind="email.send")["actions"]), 1)
        self.assertEqual(len(self.store.actions(ag)["actions"]), 3)


class Integrity(Base):
    def _fill(self):
        self.w(ev("set", "a", 1), ev("set", "b", {"x": [1, 2]}))
        self.w(ev("set", "a", 2))
        self.store.append_action(self.aid, norm_action({"kind": "k", "summary": "s", "read_keys": ["a"]}))

    def test_tamper_detection(self):
        self._fill()
        self.assertEqual(self.store.verify(), {**self.store.verify(), "ok": True, "events": 4})
        # append-only triggers block edits ...
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.c.execute("UPDATE events SET value_json='9' WHERE seq=3")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.c.execute("DELETE FROM events WHERE seq=4")
        # ... and an attacker who drops them is still caught by verify
        self.store.c.execute("DROP TRIGGER events_no_update")
        self.store.c.execute("DROP TRIGGER events_no_delete")
        self.store.c.execute("UPDATE events SET value_json='99' WHERE seq=2")
        v = self.store.verify()
        self.assertFalse(v["ok"])
        self.assertEqual((v["problem"]["agent"], v["problem"]["seq"]), ("bot", 2))

    def test_deleted_event_and_tail_truncation(self):
        self._fill()
        self.store.c.execute("DROP TRIGGER events_no_delete")
        self.store.c.execute("DELETE FROM events WHERE seq=4")
        v = self.store.verify()
        self.assertFalse(v["ok"])
        self.assertEqual(v["problem"]["seq"], 4)
        self.store.c.execute("DELETE FROM events WHERE seq=2")
        self.assertEqual(self.store.verify()["problem"]["seq"], 2)

    def test_backup_restore_round_trip(self):
        self._fill()
        dest = os.path.join(self.tmp, "b", "snap.db")
        self.store.backup(dest)
        with self.assertRaises(ApiError):
            self.store.backup(dest)  # never overwrites
        os.environ["BELIEFLINE_DATA_DIR"] = new = tempfile.mkdtemp()
        os.environ["BELIEFLINE_PORT"] = "1"  # nothing listens there
        try:
            rc = cli.main(["restore", dest])
            self.assertEqual(rc, 0)
            s2 = Store()
            v = s2.verify()
            self.assertTrue(v["ok"])
            self.assertEqual(v["events"], 4)
            self.assertEqual(s2.belief(self.aid, "a")["value"], 2)
            s2.close()
            self.assertEqual(cli.main(["restore", dest]), 1)  # data dir no longer empty
        finally:
            shutil.rmtree(new, ignore_errors=True)

    def test_migration_backup_and_newer_schema(self):
        self._fill()
        self.store.c.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
        with self.assertRaises(ApiError):
            self.store.migrate()


class TimeInput(unittest.TestCase):
    def test_formats(self):
        z = Zone("utc")
        now = 1_760_000_000_000  # 2025-10-09T08:53:20Z
        self.assertEqual(parse_time("#42", z, now), ("seq", 42))
        self.assertEqual(parse_time("2026-10-09T03:14:00+02:00", z, now)[1], parse_time("2026-10-09T01:14:00Z", z, now)[1])
        self.assertEqual(parse_time("2025-10-08 03:14", z, now)[1], parse_time("yesterday 03:14", z, now)[1])
        self.assertEqual(parse_time("2025-10-09", z, now)[1], parse_time("today", z, now)[1])
        self.assertEqual(parse_time("2025-10-07 00:00", z, now)[1], parse_time("2 days ago", z, now)[1])
        ny = Zone("America/New_York")
        self.assertEqual(parse_time("2025-10-08 03:14", ny, now)[1] - parse_time("2025-10-08 03:14", z, now)[1], 4 * 3600_000)
        for bad in ("", "soon", "2026-13-45 99:99", "#x"):
            with self.assertRaises(ValueError) as cm:
                parse_time(bad, z, now)
            self.assertIn("examples", str(cm.exception))


class Http(Base):
    """Live server: agent API and every operator CLI command's happy path."""

    def setUp(self):
        super().setUp()
        server_mod.THROTTLE.fails.clear()
        self.srv = make_server(Store(), "127.0.0.1", 0)
        self.port = self.srv.server_address[1]
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.t.start()
        os.environ["BELIEFLINE_URL"] = f"http://127.0.0.1:{self.port}"
        os.environ["BELIEFLINE_OWNER_TOKEN"] = self.token

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def http(self, method, path, key=None, body=None, tok=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Authorization", "Bearer " + (tok or key or ""))
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def cli(self, *argv):
        o, e = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            rc = cli.main(list(argv))
        return rc, o.getvalue(), e.getvalue()

    def test_bad_credentials_are_throttled(self):
        key = self.store.issue_key("bot")["key"]
        codes = [self.http("GET", "/v1/status", tok="bad%d" % i)[0] for i in range(server_mod.AUTH_FAIL_LIMIT + 5)]
        self.assertEqual(codes[0], 401)
        self.assertEqual(codes[-1], 429)
        self.assertEqual(self.http("GET", "/v1/status", tok=self.token)[0], 200)  # valid credentials still work
        self.assertEqual(self.http("GET", "/v1/whoami", key)[0], 200)

    def test_idle_partial_request_times_out(self):
        import socket
        self.srv.RequestHandlerClass.timeout = 0.5
        s = socket.create_connection(("127.0.0.1", self.port))
        s.sendall(b"POST /v1/events HTTP/1.1\r\nHost: x\r\nContent-Length: 100\r\n")
        s.settimeout(5)
        self.assertEqual(s.recv(100), b"")  # server closed the connection
        s.close()

    def test_slow_body_gets_408_and_request_is_logged(self):
        import socket
        key = self.store.issue_key("bot")["key"]
        self.srv.RequestHandlerClass.timeout = 0.5
        err = io.StringIO()
        s = socket.create_connection(("127.0.0.1", self.port))
        s.sendall(("POST /v1/events?secret=zzz HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer %s\r\n"
                   "Content-Length: 100\r\n\r\n{" % key).encode())
        s.settimeout(5)
        with contextlib.redirect_stderr(err):
            data = s.recv(1000)
            time.sleep(0.2)
        s.close()
        self.assertIn(b" 408 ", data.split(b"\r\n")[0])
        self.assertRegex(err.getvalue(), r"\d{4}-\d\d-\d\dT.* POST /v1/events 408")
        self.assertNotIn(key, err.getvalue())
        self.assertNotIn("zzz", err.getvalue())

    def test_agent_api(self):
        key = self.store.issue_key("bot")["key"]
        self.assertEqual(self.http("GET", "/v1/whoami", key)[1]["agent"], "bot")
        self.assertEqual(self.http("GET", "/v1/whoami", self.token)[0], 401)
        self.assertEqual(self.http("GET", "/v1/whoami")[0], 401)
        self.assertEqual(self.http("GET", "/v1/status", key)[0], 401)  # keys cannot use operator routes
        st, r = self.http("POST", "/v1/events", key, {"events": [ev("set", "rsvp/a", "no"), ev("set", "rsvp/b", 1)]})
        self.assertEqual((st, [x["seq"] for x in r["results"]]), (201, [1, 2]))
        st, r = self.http("GET", "/v1/beliefs?prefix=rsvp/", key)
        self.assertEqual([(b["key"], b["value"], b["version"]) for b in r["beliefs"]], [("rsvp/a", "no", 1), ("rsvp/b", 1, 1)])
        self.assertEqual(self.http("GET", "/v1/beliefs?prefix=bad%20prefix", key)[0], 400)
        self.assertEqual(self.http("GET", "/v1/beliefs?key=zz", key)[0], 404)
        st, r = self.http("POST", "/v1/events", key, ev("set", "rsvp/a", "yes", expected_version=9))
        self.assertEqual((st, r["current_version"]), (409, 1))
        self.assertEqual(self.http("POST", "/v1/events", key, {"events": [ev("set", "k", 1)] * 101})[0], 413)
        self.assertEqual(self.http("POST", "/v1/actions", key, {"kind": "x"})[0], 400)
        st, r = self.http("POST", "/v1/actions", key, {"kind": "email.send", "summary": "s", "read_keys": ["rsvp/a"]})
        self.assertEqual((st, r["snapshot"][0]["version"]), (201, 1))
        # rejected-writes log recorded the 400/409/413s (not the 404)
        self.assertEqual(self.store.status()["rejected_writes"], 4)
        # retraction by agent is forbidden by default (403), allowed when the setting says so
        eid = self.http("GET", "/v1/history?key=rsvp/a", key)[1]["events"][0]["id"]
        self.assertEqual(self.http("POST", "/v1/retract", key, {"event_id": eid, "reason": "r"})[0], 403)
        self.store.put_setting("retract.allowed_by", "operator_and_agent")
        self.assertEqual(self.http("POST", "/v1/retract", key, {"event_id": eid, "reason": "r"})[0], 201)
        self.assertEqual(self.http("GET", "/v1/beliefs?key=rsvp/a", key)[0], 404)
        # another agent cannot see this agent's events
        self.store.create_agent("other")
        k2 = self.store.issue_key("other")["key"]
        self.assertEqual(self.http("GET", f"/v1/events/{eid}", k2)[0], 404)
        # revoke -> 401
        kid = self.store.list_keys("bot")[0]["id"]
        self.store.revoke_key(kid)
        self.assertEqual(self.http("GET", "/v1/whoami", key)[1]["error"], "key revoked")

    def test_malformed_content_length(self):
        import socket
        key = self.store.issue_key("bot")["key"]
        s = socket.create_connection(("127.0.0.1", self.port))
        s.sendall(b"POST /v1/events HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer " + key.encode()
                  + b"\r\nContent-Length: abc\r\n\r\n")
        data = b""
        while chunk := s.recv(2000):  # server closes the connection after the error
            data += chunk
        s.close()
        self.assertIn(b" 400 ", data.split(b"\r\n")[0])
        self.assertIn(b"invalid Content-Length", data)

    def test_cli_happy_paths(self):
        c = self.cli
        rc, o, _ = c("status")
        self.assertIn("agents: 1", o)
        self.assertEqual(c("agent", "create", "mailer")[0], 0)
        self.assertEqual(c("agent", "rename", "mailer", "mailer2")[0], 0)
        rc, o, _ = c("agent", "list")
        self.assertIn("mailer2", o)
        rc, o, _ = c("key", "issue", "mailer2", "--label", "prod")
        key = [l for l in o.splitlines() if l.strip().startswith("blk_")][0].strip()
        self.assertEqual(c("key", "list", "mailer2")[0], 0)
        self.assertEqual(self.http("GET", "/v1/whoami", key)[1]["agent"], "mailer2")
        self.assertIn("revoked", c("key", "revoke", self.store.list_keys("mailer2")[0]["id"])[1].lower())
        self.assertEqual(self.http("GET", "/v1/whoami", key)[0], 401)
        self.assertEqual(c("agent", "archive", "mailer2")[0], 0)
        self.assertEqual(c("agent", "reactivate", "mailer2")[0], 0)
        self.assertEqual(c("agent", "create", "mailer2")[0], 1)
        # data
        self.w(ev("set", "rsvp/dana", "no", reason="said no"), now=now_ms() - 3 * 86400_000)
        yes = self.w(ev("set", "rsvp/dana", "yes", reason="old thread"), now=now_ms() - 3600_000)[0]
        act, _ = self.store.append_action(self.aid, norm_action(
            {"kind": "email.send", "summary": "Sent RSVP yes", "read_keys": ["rsvp/dana"], "caused_by": [yes["id"]]}))
        rc, o, _ = c("beliefs", "bot")
        self.assertIn('rsvp/dana = "yes"', o)
        self.assertIn('"no"', c("asof", "bot", "#1", "--key", "rsvp/dana")[1])
        self.assertIn("yes", c("asof", "bot", "now")[1])
        self.assertEqual(c("asof", "bot", "garbage")[0], 1)
        self.assertEqual(c("asof", "bot", "2000-01-01 00:00")[0], 1)
        self.assertIn("old thread", c("history", "bot", "rsvp/dana")[1])
        self.assertIn(act["id"], c("actions", "bot", "--from", "2 days ago", "--kind", "email")[1])
        rc, o, _ = c("explain", act["id"])
        self.assertIn("Beliefs it read", o)
        self.assertIn(yes["id"], o)
        self.assertIn('Set rsvp/x = "maybe"', c("set", "bot", "rsvp/x", '"maybe"', "--reason", "operator fix")[1])
        rc, o, _ = c("retract", yes["id"], "--reason", "bad summary")
        self.assertIn('before: "yes"', o)
        self.assertIn('after:  "no"', o)
        self.assertEqual(c("retract", yes["id"], "--reason", "again")[0], 1)
        self.assertIn('rsvp/dana = "no"', c("beliefs", "bot", "--prefix", "rsvp/")[1])
        self.assertIn("RETRACTED", c("history", "bot", "rsvp/dana")[1])
        today = c("report", "bot", "--day", __import__("datetime").date.today().isoformat())[1]
        self.assertIn("Retractions: 1", today)
        self.assertIn("Actions: 1", today)
        self.assertIn("no events", c("report", "bot", "--day", "2000-01-01")[1])
        rc, o, _ = c("diff", "bot", "#1", "#2")
        self.assertIn('"no" -> "yes"', o)
        self.assertIn("swapped", c("diff", "bot", "#2", "#1")[1])
        rc, o, _ = c("export", "bot")
        lines = [json.loads(l) for l in o.splitlines()]
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0]["prev_hash"], "0" * 64)
        self.assertEqual(c("export", "--all", "--from", "2000-01-01", "--to", "2000-01-02")[1], "")
        self.assertIn("OK, 5 events", c("verify")[1])
        self.assertIn("writes.version_check = optional", c("config", "list")[1])
        self.assertEqual(c("config", "set", "writes.unchanged_set", "skip")[0], 0)
        self.assertEqual(c("config", "set", "writes.unchanged_set", "bogus")[0], 1)
        dest = os.path.join(self.tmp, "bk.db")
        self.assertEqual(c("backup", dest)[0], 0)
        self.assertTrue(os.path.exists(dest))
        rc, o, _ = c("verify", "--json")
        self.assertTrue(json.loads(o)["ok"])
        # wrong owner token
        os.environ["BELIEFLINE_OWNER_TOKEN"] = "nope"
        rc, o, e = c("status")
        self.assertEqual((rc, e.strip().splitlines()[-1]), (1, "error: invalid owner token"))
        os.environ["BELIEFLINE_OWNER_TOKEN"] = self.token
        # tamper -> verify exits non-zero naming the sequence number
        self.store.c.execute("DROP TRIGGER events_no_update")
        self.store.c.execute("UPDATE events SET reason='edited' WHERE seq=2")
        rc, o, _ = c("verify")
        self.assertEqual(rc, 1)
        self.assertIn("agent bot at sequence 2", o)
        # token rotate invalidates the old token
        os.environ.pop("BELIEFLINE_OWNER_TOKEN")
        cli.save_cfg(self.token)
        self.assertEqual(c("token", "rotate")[0], 0)
        self.assertEqual(self.http("GET", "/v1/status", tok=self.token)[0], 401)
        self.assertEqual(c("status")[0], 0)  # CLI picked up the new token from its config file
        self.assertEqual(oct(os.stat(cli.cfg_path()).st_mode & 0o777), "0o600")

    def test_demo(self):
        s2 = tempfile.mkdtemp()
        try:
            os.environ["BELIEFLINE_DATA_DIR"] = s2
            ds = Store()
            ds.init()
            from beliefline import demo
            r = demo.load(ds)
            self.assertEqual(sorted(r["agents"]), ["assistant", "scheduler"])
            self.assertTrue(250 <= r["events"] <= 350, r["events"])
            self.assertTrue(ds.verify()["ok"])
            with self.assertRaises(ApiError) as cm:
                demo.load(ds)
            self.assertIn("store not empty", cm.exception.error)
            a = ds.agent("assistant")
            story = ds.read_beliefs(a["id"], key="rsvp/dana-wedding")
            self.assertEqual(story[0]["value"], "yes")
            self.assertEqual(ds.status()["rejected_writes"], 1)
            ds.close()
        finally:
            shutil.rmtree(s2, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
