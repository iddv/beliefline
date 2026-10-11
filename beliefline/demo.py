"""Demo data: two agents, ~300 events over the last 3 days, and the RSVP story."""
import random
from datetime import datetime, timedelta

from .store import ApiError, norm_action, norm_event, now_ms
from .tz import resolve_zone


def load(store):
    st = store.status()
    if st["agents"] or st["events"]:
        raise ApiError(409, "store not empty; demo data only loads into an empty store", None, None)
    zone = resolve_zone(st["settings"]["display.time_zone"])
    now = now_ms()
    today = zone.today(now)

    def at(days_ago, h, m, s=0):
        d = today - timedelta(days=days_ago)
        return zone.midnight(d) + ((h * 60 + m) * 60 + s) * 1000

    agents = {n: store.create_agent(n, now=at(2, 0, 0)) for n in ("assistant", "scheduler")}
    ids = {n: int(a["id"][4:]) for n, a in agents.items()}
    ref = {}

    def put(agent, ts, key, value, reason=None, source=None, caused=(), exp=None, save=None):
        raw = {"type": "set", "key": key, "value": value, "reason": reason, "source": source,
               "caused_by": [ref[c] for c in caused]}
        if exp is not None:
            raw["expected_version"] = exp
        res, _ = store.append_events(ids[agent], [norm_event(0, raw)], now=ts)
        if save:
            ref[save] = res[0]["id"]
        return res[0]["id"]

    def delete(agent, ts, key, reason):
        store.append_events(ids[agent], [norm_event(0, {"type": "delete", "key": key, "reason": reason})], now=ts)

    def act(agent, ts, kind, summary, read_keys, caused=(), payload=None, save=None):
        raw = {"kind": kind, "summary": summary, "read_keys": read_keys, "caused_by": [ref[c] for c in caused]}
        if payload is not None:
            raw["payload"] = payload
        out, _ = store.append_action(ids[agent], norm_action(raw), now=ts)
        if save:
            ref[save] = out["id"]

    # ---- the RSVP story (assistant)
    def s_no():
        put("assistant", at(2, 22, 9), "chat/last-message", "I can't make Dana's wedding, sorry",
            "user message received", "chat", save="msg")
        put("assistant", at(2, 22, 10), "rsvp/dana-wedding", "no", "user said can't make it", "chat",
            caused=["msg"], save="no")

    def s_yes():
        put("assistant", at(1, 2, 40), "threads/dana-wedding/import", "old thread 2025-03 (14 messages)",
            "re-indexed mailbox", "mail-sync", save="imp")
        put("assistant", at(1, 2, 46), "threads/dana-wedding/summary", "Thread says: Dana is waiting for a yes.",
            "summarized old thread", "summarizer", caused=["imp"], save="sum")
        put("assistant", at(1, 2, 47), "rsvp/dana-wedding", "yes", "summarized from old thread", "summarizer",
            caused=["sum"], save="yes")

    def s_email():
        put("assistant", at(1, 3, 13), "contacts/dana/email", "dana@example.com", "looked up in address book",
            "contacts", save="mail")
        act("assistant", at(1, 3, 14), "email.send", "Sent RSVP yes to Dana",
            ["rsvp/dana-wedding", "contacts/dana/email"], caused=["yes"],
            payload={"to": "dana@example.com", "subject": "RSVP: Dana's wedding", "body": "Yes, we'll be there!"})

    def s_conflict():
        put("assistant", at(1, 8, 55), "tasks/book-venue", "todo", "planning", "planner")
        put("assistant", at(1, 9, 5), "tasks/book-venue", "in progress", "planning", "planner", exp=1)
        try:  # a stale writer: expected v1 but the key is at v2 -> 409 recorded in the rejected-writes log
            store.append_events(ids["assistant"], [norm_event(0, {
                "type": "set", "key": "tasks/book-venue", "value": "done", "reason": "stale copy of the task",
                "source": "planner-b", "expected_version": 1})], now=at(1, 9, 12))
        except ApiError as e:
            store.log_rejected(ids["assistant"], e, "POST /v1/events", now=at(1, 9, 12))

    def s_bad_phone():
        put("scheduler", at(1, 14, 0), "contacts/sam/phone", "555-0000", "imported", "csv-import", save="phone")
        store.retract(ids["scheduler"], ref["phone"], "wrong number from import", "operator", now=at(1, 15, 30))

    story = [(at(2, 22, 9), "assistant", s_no), (at(1, 2, 40), "assistant", s_yes),
             (at(1, 3, 13), "assistant", s_email), (at(1, 8, 55), "assistant", s_conflict),
             (at(1, 14, 0), "scheduler", s_bad_phone)]

    # ---- filler
    rnd = random.Random(7)
    start, end = at(2, 0, 30), now - 60_000
    people = ["alex", "bo", "casey", "drew", "eli", "fran", "gus", "hana"]
    topics = ["meeting-length", "language", "tone", "signature", "quiet-hours", "currency"]
    plans = {
        "assistant": (146, lambda: rnd.choice([
            lambda: (f"prefs/{rnd.choice(topics)}", rnd.choice(["short", "long", "formal", "casual", "en", "nl", True, False, 30, 45])),
            lambda: (f"contacts/{rnd.choice(people)}/email", f"{rnd.choice(people)}{rnd.randint(1, 9)}@example.com"),
            lambda: (f"notes/{rnd.randint(1, 25)}", {"text": rnd.choice(["call back", "send invoice", "book table"]), "prio": rnd.randint(1, 3)}),
            lambda: (f"rsvp/event-{rnd.randint(1, 6)}", rnd.choice(["yes", "no", "maybe"])),
        ])(), ("email.send", "Sent follow-up to {p}", "contacts/{p}/email")),
        "scheduler": (148, lambda: rnd.choice([
            lambda: (f"calendar/{rnd.randint(1, 20)}", {"title": rnd.choice(["standup", "1:1", "review"]), "mins": rnd.choice([15, 30, 60])}),
            lambda: (f"jobs/{rnd.choice(['sync', 'cleanup', 'digest'])}/status", rnd.choice(["queued", "running", "ok", "failed"])),
            lambda: (f"reminders/{rnd.randint(1, 15)}", rnd.choice(["09:00", "13:30", "17:45"])),
        ])(), ("calendar.hold", "Held a slot for {p}", "calendar/{n}")),
    }
    filler = []
    for name, (count, gen, (kind, summ, rk)) in plans.items():
        for ts in sorted(rnd.randint(start, end) for _ in range(count)):
            filler.append((ts, name, gen, kind, summ, rk))
    ops = [(ts, 0, i, ("story", fn)) for i, (ts, _, fn) in enumerate(story)]
    ops += [(f[0], 1, i, ("filler", f)) for i, f in enumerate(filler)]
    ops.sort(key=lambda o: o[:3])
    live = {n: [] for n in plans}
    for ts, _, _, (what, f) in ops:
        if what == "story":
            f()
            continue
        _, name, gen, kind, summ, rk = f
        r = rnd.random()
        if r < 0.08:
            p = rnd.choice(people)
            keys = [rk.format(p=p, n=rnd.randint(1, 20))] + rnd.sample(live[name], min(1, len(live[name])))
            act(name, ts, kind, summ.format(p=p), keys)
        elif r < 0.16 and live[name]:
            k = live[name].pop(rnd.randrange(len(live[name])))
            delete(name, ts, k, "no longer relevant")
        else:
            k, v = gen()
            put(name, ts, k, v, rnd.choice(["observed", "user request", "sync", None]), name)
            if k not in live[name]:
                live[name].append(k)
    keys = {n: store.issue_key(n, "demo")["key"] for n in agents}
    return {"agents": list(agents), "keys": keys, "events": store.status()["events"]}
