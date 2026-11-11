"""The calendar in StaticFrame and NumPy types: a session is a
`np.datetime64[D]`, a range of sessions an `sf.IndexDate`, and a schedule an
`sf.Frame` indexed by session. Needs `pip install diurn[sf]`.

    import diurn.sf as dsf
    xnys = dsf.get_calendar("XNYS")
    xnys.schedule("2026-11-01", "2026-11-30")         # sf.Frame

NumPy's datetime64 has no time zone, so instants (`next_open`, `next_close`,
the schedule's `open`, `break_start`, `break_end` and `close`) are UTC, at
second resolution; the venue's zone is the calendar's `tz`.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence

try:
    import numpy as np
    import static_frame as sf
except ImportError as e:  # pragma: no cover - depends on the environment
    raise ImportError("the StaticFrame flavor needs static-frame: pip install 'diurn[sf]'") from e

from . import _core
from ._core import OnUnknown, ScheduleRow
from .client import Client

__all__ = ["Calendar", "get_calendar"]

NAT = np.datetime64("NaT", "s")


class Calendar:
    """A venue's trading calendar in StaticFrame types. `core` is the
    plain-Python calendar underneath."""

    def __init__(self, core: _core.Calendar):
        self.core = core

    def __repr__(self) -> str:
        return repr(self.core).replace("<Calendar", "<diurn.sf.Calendar", 1)

    @property
    def mic(self) -> str:
        return self.core.mic

    @property
    def name(self) -> str:
        """The MIC, as `exchange_calendars` names a calendar by its code."""
        return self.core.name

    @property
    def market_name(self) -> str:
        return self.core.market_name

    @property
    def products(self) -> tuple[str, ...]:
        """The product schedules the venue keeps; empty for almost every one."""
        return self.core.products

    @property
    def tz(self) -> str:
        return self.core.tz

    def is_session(self, date: object) -> bool | None:
        return self.core.is_session(date)

    def sessions_in_range(self, start: object, end: object) -> sf.IndexDate:
        return _index(self.core.sessions_in_range(start, end))

    def next_session(self, date: object) -> np.datetime64:
        return _date(self.core.next_session(date))

    def previous_session(self, date: object) -> np.datetime64:
        return _date(self.core.previous_session(date))

    def date_to_session(self, date: object, direction: str = "none") -> np.datetime64:
        return _date(self.core.date_to_session(date, direction))  # type: ignore[arg-type]

    def sessions_window(self, session: object, count: int) -> sf.IndexDate:
        return _index(self.core.sessions_window(session, count))

    def is_open_at_time(self, when: object) -> bool | None:
        return self.core.is_open_at_time(when)

    def next_open(self, when: object) -> np.datetime64:
        return _utc(self.core.next_open(when))

    def next_close(self, when: object) -> np.datetime64:
        return _utc(self.core.next_close(when))

    def schedule(self, start: object, end: object, *, all_days: bool = False) -> sf.Frame:
        """One row per session (or per day, with `all_days=True`): `open`,
        `break_start`, `break_end`, `close` in UTC, then `kind`,
        `verification` and `reason`."""
        return _schedule(self.core.schedule(start, end, all_days=all_days))


def get_calendar(
    mic: str,
    *,
    client: Client | None = None,
    on_unknown: OnUnknown = "raise",
    product: str | None = None,
    cache: bool = True,
    as_of: datetime.datetime | str | None = None,
) -> Calendar:
    """The calendar for a MIC, in StaticFrame types."""
    core = _core.Calendar(mic, client, on_unknown=on_unknown, product=product, cache=cache, as_of=as_of)
    return Calendar(core)


def _date(d: datetime.date | None) -> np.datetime64:
    return np.datetime64("NaT", "D") if d is None else np.datetime64(d, "D")


def _index(dates: Sequence[datetime.date]) -> sf.IndexDate:
    array = np.array([np.datetime64(d, "D") for d in dates], dtype="datetime64[D]")
    array.flags.writeable = False
    return sf.IndexDate(array)


def _utc(t: datetime.datetime | None) -> np.datetime64:
    if t is None:
        return NAT
    return np.datetime64(t.astimezone(datetime.UTC).replace(tzinfo=None), "s")


def _schedule(rows: Sequence[ScheduleRow]) -> sf.Frame:
    columns = {}
    for col in ("open", "break_start", "break_end", "close"):
        columns[col] = np.array([_utc(getattr(r, col)) for r in rows], dtype="datetime64[s]")
    for col in ("kind", "verification"):
        columns[col] = np.array([getattr(r, col) for r in rows], dtype=str)
    columns["reason"] = np.array([r.reason for r in rows], dtype=object)
    return sf.Frame.from_dict(columns, index=_index([r.date for r in rows]), name="schedule").rename(
        index="session"
    )
