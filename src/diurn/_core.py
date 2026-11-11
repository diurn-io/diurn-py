"""The calendar, in plain Python types. The flavors (`diurn.pd`, `diurn.sf`,
`diurn.py`) wrap this and differ only in the types they return.

A calendar loads a venue's days from the API a calendar year at a time,
trimmed to the dates the plan may ask about, and answers every method from
them. A "session" is a trading day, as in `exchange_calendars`: a day whose
kind is `open`, `early_close` or `open_for_some`.

**`unknown` is never a session and never a closure.** Past what Diurn can
answer, a method that would depend on such a day raises `Indeterminate`, or,
with `on_unknown="missing"`, returns `None` where it would have answered.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Literal

from . import errors
from ._cache import DiskCache
from ._instant import parse_instant, to_date, to_instant
from .client import Client

__all__ = ["Calendar", "Day", "Session", "ScheduleRow", "TRADING_KINDS", "OnUnknown"]

TRADING_KINDS = frozenset({"open", "early_close", "open_for_some"})
OnUnknown = Literal["raise", "missing"]

# How far a stepping method looks before giving up: past this, nothing was
# found, which on a real venue means the answer is beyond what Diurn serves.
_SCAN_DAYS = 800


@dataclass(frozen=True, slots=True)
class Session:
    """One session: its open and close as aware datetimes in the venue's
    zone, its breaks, and the products it is for (`None`: the whole venue)."""

    name: str
    open: datetime.datetime
    close: datetime.datetime
    breaks: tuple[tuple[datetime.datetime, datetime.datetime], ...]
    products: tuple[str, ...] | None
    verification: str


@dataclass(frozen=True, slots=True)
class Day:
    date: datetime.date
    kind: str
    verification: str
    reason: str | None
    sessions: tuple[Session, ...]

    @property
    def is_unknown(self) -> bool:
        return self.kind == "unknown"

    @property
    def is_session(self) -> bool:
        return self.kind in TRADING_KINDS


@dataclass(frozen=True, slots=True)
class ScheduleRow:
    """A day's schedule, as `exchange_calendars` lays it out: the first open,
    the last close, and the first break between them; plus Diurn's `kind`,
    `verification` and `reason`."""

    date: datetime.date
    open: datetime.datetime | None
    break_start: datetime.datetime | None
    break_end: datetime.datetime | None
    close: datetime.datetime | None
    kind: str
    verification: str
    reason: str | None


class Calendar:
    """One venue's trading calendar, answered by the Diurn API.

    `product` picks one product schedule where a venue keeps several (see
    `products`); by default the sessions for the whole venue are used, or, on
    a venue whose every session is scoped to products, all of them.
    """

    def __init__(
        self,
        mic: str,
        client: Client | None = None,
        *,
        on_unknown: OnUnknown = "raise",
        product: str | None = None,
        cache: bool | DiskCache = True,
        as_of: datetime.datetime | str | None = None,
    ):
        if on_unknown not in ("raise", "missing"):
            raise ValueError("on_unknown is 'raise' or 'missing'")
        self.client = client or Client()
        record = self.client.venue(mic)
        if record.timezone is None or record.resolution is None:
            raise errors.UnknownVenue(404, "no_calendar", f"no calendar answers {record.mic}")
        self.mic = record.mic
        self.name = record.name
        self.tz = record.timezone
        self.products: tuple[str, ...] = tuple(record.products)
        if product is not None and product not in self.products:
            raise ValueError(f"{self.mic} has no product {product!r}; it has {self.products}")
        self.product = product
        self.on_unknown = on_unknown
        self.as_of = None if as_of is None else to_instant(as_of)
        if cache is True and self.as_of is None:
            transport = self.client.transport
            self._cache: DiskCache | None = DiskCache(
                transport.base_url, lambda: self.client.health().dataset
            )
        else:
            self._cache = cache if isinstance(cache, DiskCache) else None
        self._days: dict[datetime.date, Day] = {}
        self._years: set[int] = set()
        self._window: tuple[datetime.date | None, datetime.date | None] | None = None

    def __repr__(self) -> str:
        return f"<Calendar {self.mic} {self.name} ({self.tz})>"

    # --- days ------------------------------------------------------------------

    def day(self, date: object) -> Day:
        """The day, whatever its kind."""
        d = to_date(date)
        self._load(d, d)
        return self._days[d]

    def days_in_range(self, start: object, end: object) -> list[Day]:
        """Every day from `start` to `end`, inclusive."""
        a, b = to_date(start), to_date(end)
        if b < a:
            return []
        self._load(a, b)
        return [self._days[d] for d in _dates(a, b)]

    # --- the exchange_calendars interface ------------------------------------------

    def is_session(self, date: object) -> bool | None:
        day = self.day(date)
        if day.is_unknown:
            self._unknown(day)
            return None
        return day.is_session

    def sessions_in_range(self, start: object, end: object) -> list[datetime.date]:
        """The sessions from `start` to `end`, inclusive. An unknown day raises,
        or with `on_unknown="missing"` is left out (it is not a session, and
        not a closure either)."""
        out = []
        for day in self.days_in_range(start, end):
            if day.is_unknown:
                self._unknown(day)
            elif day.is_session:
                out.append(day.date)
        return out

    def next_session(self, date: object) -> datetime.date | None:
        """The first session after `date`. Unlike `exchange_calendars`,
        `date` need not be a session."""
        return self._step(to_date(date), 1)

    def previous_session(self, date: object) -> datetime.date | None:
        """The last session before `date`; `date` need not be a session."""
        return self._step(to_date(date), -1)

    def date_to_session(
        self, date: object, direction: Literal["none", "next", "previous"] = "none"
    ) -> datetime.date | None:
        """`date` if it is a session; otherwise the next or previous one, or
        (`direction="none"`) a `ValueError`."""
        d = to_date(date)
        here = self.is_session(d)
        if here is None:
            return None
        if here:
            return d
        if direction == "next":
            return self._step(d, 1)
        if direction == "previous":
            return self._step(d, -1)
        raise ValueError(f"{d} is not a session of {self.mic}; pass direction='next' or 'previous'")

    def sessions_window(self, session: object, count: int) -> list[datetime.date]:
        """`abs(count)` sessions from `session`: forwards for a positive count,
        backwards (ending at `session`) for a negative one. `session` must be
        a session."""
        d = to_date(session)
        if not self.is_session(d):
            raise ValueError(f"{d} is not a session of {self.mic}")
        if count == 0:
            raise ValueError("count is not zero")
        out = [d]
        step = 1 if count > 0 else -1
        while len(out) < abs(count):
            nxt = self._step(out[-1], step)
            if nxt is None:
                break
            out.append(nxt)
        return out if step > 0 else out[::-1]

    def is_open_at_time(self, when: object) -> bool | None:
        """Whether a session is running at the instant, outside its breaks."""
        t = to_instant(when)
        local = t.astimezone(_zone(self.tz)).date()
        days = self.days_in_range(local - datetime.timedelta(days=1), local + datetime.timedelta(days=1))
        for day in days:
            if day.date == local and day.is_unknown:
                self._unknown(day)
                return None
            for s in self._sessions(day):
                if s.open <= t < s.close and not any(b0 <= t < b1 for b0, b1 in s.breaks):
                    return True
        return False

    def next_open(self, when: object) -> datetime.datetime | None:
        """The first session open after the instant."""
        return self._next_edge(to_instant(when), "open")

    def next_close(self, when: object) -> datetime.datetime | None:
        """The first session close after the instant."""
        return self._next_edge(to_instant(when), "close")

    def schedule(self, start: object, end: object, *, all_days: bool = False) -> list[ScheduleRow]:
        """One row per session from `start` to `end`; with `all_days=True`, one
        per day, so holidays and unknown days appear with their kind and no
        times."""
        rows = []
        for day in self.days_in_range(start, end):
            if day.is_unknown and not all_days:
                self._unknown(day)
                continue
            if not day.is_session and not all_days:
                continue
            rows.append(self._row(day))
        return rows

    # --- internals -------------------------------------------------------------

    def _unknown(self, day: Day) -> None:
        """Raise for an unknown day, unless the calendar was asked for a
        missing value instead; then the caller answers None."""
        if self.on_unknown != "missing":
            raise errors.Indeterminate(self.mic, day.date)

    def _sessions(self, day: Day) -> tuple[Session, ...]:
        if self.product is not None:
            return tuple(
                s for s in day.sessions if s.products is None or self.product in s.products
            )
        whole = tuple(s for s in day.sessions if s.products is None)
        return whole or day.sessions

    def _row(self, day: Day) -> ScheduleRow:
        sessions = sorted(self._sessions(day), key=lambda s: s.open)
        if not sessions:
            return ScheduleRow(day.date, None, None, None, None, day.kind, day.verification, day.reason)
        first, last = sessions[0], sessions[-1]
        b0: datetime.datetime | None
        b1: datetime.datetime | None
        if len(sessions) > 1:
            b0, b1 = first.close, sessions[1].open
        elif first.breaks:
            b0, b1 = first.breaks[0]
        else:
            b0 = b1 = None
        return ScheduleRow(
            day.date, first.open, b0, b1, last.close, day.kind, day.verification, day.reason
        )

    def _step(self, start: datetime.date, direction: int) -> datetime.date | None:
        d = start
        for _ in range(_SCAN_DAYS):
            d += datetime.timedelta(days=direction)
            day = self.day(d)
            if day.is_unknown:
                self._unknown(day)
                return None
            if day.is_session:
                return d
        return None

    def _next_edge(self, t: datetime.datetime, edge: str) -> datetime.datetime | None:
        d = t.astimezone(_zone(self.tz)).date() - datetime.timedelta(days=1)
        for _ in range(_SCAN_DAYS):
            day = self.day(d)
            if day.is_unknown and d >= t.date():
                self._unknown(day)
                return None
            found: list[datetime.datetime] = sorted(
                s.open if edge == "open" else s.close for s in self._sessions(day)
            )
            for x in found:
                if x > t:
                    return x
            d += datetime.timedelta(days=1)
        return None

    def _plan_window(self) -> tuple[datetime.date | None, datetime.date | None]:
        """The dates the plan may ask about, from `/v1/usage` (free). Unbounded
        when there is no plan to ask, as on a server without keys."""
        if self._window is None:
            try:
                h = self.client.usage().horizon
                self._window = (h.from_, h.to)
            except errors.ApiError:
                self._window = (None, None)
        return self._window

    def _load(self, start: datetime.date, end: datetime.date) -> None:
        lo, hi = self._plan_window()
        if (lo is not None and start < lo) or (hi is not None and end > hi):
            raise errors.OutOfWindow(
                403,
                "out_of_window",
                f"{start}..{end} is outside the dates your plan may ask about",
                {"allowed": {"from": lo and lo.isoformat(), "to": hi and hi.isoformat()}},
            )
        for year in range(start.year, end.year + 1):
            if year in self._years:
                continue
            a = max(datetime.date(year, 1, 1), lo) if lo else datetime.date(year, 1, 1)
            b = min(datetime.date(year, 12, 31), hi) if hi else datetime.date(year, 12, 31)
            for day in self._fetch(a, b):
                self._days[day.date] = day
            self._years.add(year)

    def _fetch(self, a: datetime.date, b: datetime.date) -> list[Day]:
        def fetch() -> Any:
            params = {"from": a, "to": b, "as_of": self.as_of}
            return self.client.transport.get(f"/v1/venues/{self.mic}/sessions", params)

        if self._cache is not None:
            raw = self._cache.get_or_fetch(f"sessions {self.mic} {a} {b}", fetch)
        else:
            raw = fetch()
        return [_day(d) for d in raw["days"]]


def _day(raw: dict[str, Any]) -> Day:
    sessions = tuple(
        Session(
            name=s["name"],
            open=parse_instant(s["open"]),
            close=parse_instant(s["close"]),
            breaks=tuple(
                (parse_instant(b["start"]), parse_instant(b["end"])) for b in s.get("breaks") or ()
            ),
            products=tuple(s["products"]) if s.get("products") is not None else None,
            verification=s["verification"],
        )
        for s in raw.get("sessions") or ()
    )
    return Day(
        date=datetime.date.fromisoformat(raw["date"]),
        kind=raw["kind"],
        verification=raw["verification"],
        reason=raw.get("reason"),
        sessions=sessions,
    )


def _dates(a: datetime.date, b: datetime.date) -> list[datetime.date]:
    return [a + datetime.timedelta(days=i) for i in range((b - a).days + 1)]


def _zone(name: str) -> datetime.tzinfo:
    from zoneinfo import ZoneInfo

    return ZoneInfo(name)
