"""Display zone handling and flexible time input."""
import os
import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

TIME_EXAMPLES = "2026-10-09T03:14:00+02:00, '2026-10-09 03:14', 'yesterday 03:14', '#42'"


class Zone:
    """A display zone: 'utc', 'local' (machine zone) or an IANA name."""

    def __init__(self, spec="local"):
        self.spec = spec
        s = spec.lower()
        if s == "utc":
            self.z = timezone.utc
        elif s == "local":
            self.z = None
        else:
            try:
                self.z = ZoneInfo(spec)
            except Exception:
                raise ValueError(f"unknown time zone {spec!r}; use utc, local or an IANA name")

    def localize(self, naive):
        if self.z is None:
            return naive.astimezone()
        return naive.replace(tzinfo=self.z)

    def to_dt(self, ms):
        if self.z is None:
            return datetime.fromtimestamp(ms / 1000).astimezone()
        return datetime.fromtimestamp(ms / 1000, self.z)

    def fmt(self, ms):
        d = self.to_dt(ms)
        return d.strftime("%Y-%m-%d %H:%M:%S") + f".{ms % 1000:03d} " + (d.tzname() or "")

    def midnight(self, day):
        """Epoch ms of local midnight of a date."""
        return dt_ms(self.localize(datetime(day.year, day.month, day.day)))

    def today(self, now_ms):
        return self.to_dt(now_ms).date()


def resolve_zone(setting="local"):
    """BELIEFLINE_TZ overrides the display.time_zone setting."""
    return Zone(os.environ.get("BELIEFLINE_TZ") or setting)


def dt_ms(d):
    return int(round(d.timestamp() * 1000))


def iso_to_ms(s):
    return dt_ms(datetime.fromisoformat(s.replace("Z", "+00:00")))


_OFFSET = re.compile(r"(Z|[+-]\d\d:?\d\d)$")
_DATE_TIME = re.compile(r"^(\d{4})-(\d\d)-(\d\d)(?:[T ](\d\d):(\d\d)(?::(\d\d)(?:\.(\d{1,6}))?)?)?$")
_REL = re.compile(r"^(today|yesterday|tomorrow|(\d+) days? ago)(?:\s+(\d\d?):(\d\d)(?::(\d\d))?)?$")
_HM = re.compile(r"^(\d\d?):(\d\d)(?::(\d\d))?$")


def parse_time(text, zone, now_ms, allow_seq=True):
    """Return ('at', ms) or ('seq', n). Raises ValueError with examples."""
    s = text.strip()
    bad = ValueError(f"cannot read time {text!r}; examples: {TIME_EXAMPLES}")
    if s.startswith("#"):
        if not allow_seq:
            raise ValueError("sequence numbers (#N) are not accepted here; use a time")
        if not s[1:].isdigit():
            raise bad
        return ("seq", int(s[1:]))
    if s.lower() == "now":
        return ("at", now_ms)
    try:
        if _OFFSET.search(s) and re.match(r"^\d{4}-\d\d-\d\d[T ]", s):
            return ("at", iso_to_ms(s.replace(" ", "T", 1)))
        m = _DATE_TIME.match(s)
        if m:
            y, mo, d, h, mi, sec, frac = m.groups()
            naive = datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(sec or 0),
                             int((frac or "0").ljust(6, "0")))
            return ("at", dt_ms(zone.localize(naive)))
        low = s.lower()
        m = _REL.match(low)
        if m:
            word = m.group(1)
            back = {"today": 0, "yesterday": 1, "tomorrow": -1}.get(word)
            if back is None:
                back = int(m.group(2))
            day = zone.today(now_ms) - timedelta(days=back)
            h, mi, sec = m.group(3), m.group(4), m.group(5)
            naive = datetime(day.year, day.month, day.day, int(h or 0), int(mi or 0), int(sec or 0))
            return ("at", dt_ms(zone.localize(naive)))
        m = _HM.match(low)
        if m:
            day = zone.today(now_ms)
            naive = datetime(day.year, day.month, day.day, int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
            return ("at", dt_ms(zone.localize(naive)))
    except (ValueError, OverflowError):
        raise bad
    raise bad
