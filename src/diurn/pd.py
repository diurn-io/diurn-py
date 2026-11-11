"""The calendar in pandas types, as `exchange_calendars` returns them: a session
is a `pd.Timestamp` at midnight, a range of sessions a `pd.DatetimeIndex`, and
a schedule a `pd.DataFrame` indexed by session. This is what `diurn.get_calendar`
returns.

    import diurn
    xnys = diurn.get_calendar("XNYS")
    xnys.sessions_in_range("2026-11-01", "2026-11-30")   # DatetimeIndex

**Where it differs from `exchange_calendars`, on purpose:**

- Instants (`next_open`, `next_close`, the schedule's columns) are aware
  Timestamps in the venue's own zone, not UTC: the zone is never dropped. They
  compare equal to the UTC ones.
- `next_session` and `previous_session` accept any date, not only a session.
- `schedule` is a method over a range, `schedule(start, end)`, since the
  calendar is answered by an API rather than precomputed; it adds `kind`,
  `verification` and `reason` columns, and `all_days=True` keeps holidays and
  unknown days.
- A day Diurn cannot answer raises `diurn.Indeterminate`; with
  `on_unknown="missing"` the answer is `None` (or `NaT`) instead.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence

try:
    import pandas as pd
except ImportError as e:  # pragma: no cover - depends on the environment
    raise ImportError(
        "the pandas flavor needs pandas: pip install 'diurn[pd]' (or use diurn.py, which needs nothing)"
    ) from e

from . import _core
from ._core import OnUnknown, ScheduleRow
from .client import Client

__all__ = ["Calendar", "get_calendar"]

SCHEDULE_COLUMNS = ["open", "break_start", "break_end", "close", "kind", "verification", "reason"]


class Calendar:
    """A venue's trading calendar in pandas types. `core` is the plain-Python
    calendar underneath, for its `Day` objects and anything not wrapped here."""

    def __init__(self, core: _core.Calendar):
        self.core = core

    def __repr__(self) -> str:
        return repr(self.core).replace("<Calendar", "<diurn.pd.Calendar", 1)

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

    def sessions_in_range(self, start: object, end: object) -> pd.DatetimeIndex:
        return _index(self.core.sessions_in_range(start, end))

    def next_session(self, date: object) -> pd.Timestamp:
        return _ts(self.core.next_session(date))

    def previous_session(self, date: object) -> pd.Timestamp:
        return _ts(self.core.previous_session(date))

    def date_to_session(self, date: object, direction: str = "none") -> pd.Timestamp:
        return _ts(self.core.date_to_session(date, direction))  # type: ignore[arg-type]

    def sessions_window(self, session: object, count: int) -> pd.DatetimeIndex:
        return _index(self.core.sessions_window(session, count))

    def is_open_at_time(self, when: object) -> bool | None:
        return self.core.is_open_at_time(when)

    def next_open(self, when: object) -> pd.Timestamp:
        return _instant(self.core.next_open(when))

    def next_close(self, when: object) -> pd.Timestamp:
        return _instant(self.core.next_close(when))

    def schedule(self, start: object, end: object, *, all_days: bool = False) -> pd.DataFrame:
        """One row per session (or per day, with `all_days=True`): `open`,
        `break_start`, `break_end`, `close` as aware Timestamps in the venue's
        zone, then `kind`, `verification` and `reason`."""
        return _schedule(self.core.schedule(start, end, all_days=all_days), self.tz)


def get_calendar(
    mic: str,
    *,
    client: Client | None = None,
    on_unknown: OnUnknown = "raise",
    product: str | None = None,
    cache: bool = True,
    as_of: datetime.datetime | str | None = None,
) -> Calendar:
    """The calendar for a MIC, in pandas types. The key is `DIURN_API_KEY`
    unless `client` carries one."""
    core = _core.Calendar(mic, client, on_unknown=on_unknown, product=product, cache=cache, as_of=as_of)
    return Calendar(core)


def _ts(d: datetime.date | None) -> pd.Timestamp:
    return pd.NaT if d is None else pd.Timestamp(d)  # type: ignore[return-value]


def _index(dates: Sequence[datetime.date]) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([pd.Timestamp(d) for d in dates], dtype="datetime64[ns]")


def _instant(t: datetime.datetime | None) -> pd.Timestamp:
    return pd.NaT if t is None else pd.Timestamp(t)  # type: ignore[return-value]


def _schedule(rows: Sequence[ScheduleRow], tz: str) -> pd.DataFrame:
    index = _index([r.date for r in rows])
    data: dict[str, object] = {}
    for col in ("open", "break_start", "break_end", "close"):
        data[col] = pd.DatetimeIndex(
            [pd.NaT if getattr(r, col) is None else pd.Timestamp(getattr(r, col)) for r in rows],
            dtype=f"datetime64[ns, {tz}]",
        )
    for col in ("kind", "verification", "reason"):
        data[col] = [getattr(r, col) for r in rows]
    frame = pd.DataFrame(data, index=index, columns=SCHEDULE_COLUMNS)
    frame.index.name = "session"
    return frame
