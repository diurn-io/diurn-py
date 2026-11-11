"""The calendar in plain Python types: `datetime.date` for sessions, aware
`datetime` for instants (in the venue's zone), lists for ranges, and a list of
`ScheduleRow` for a schedule. No dependency beyond the standard library:
importing this, or `diurn` itself, never imports pandas or NumPy.

    import diurn.py as dpy
    xnys = dpy.get_calendar("XNYS")
    xnys.next_session("2026-11-25")       # datetime.date(2026, 11, 27)
"""

from __future__ import annotations

import datetime

from ._core import Calendar, Day, OnUnknown, ScheduleRow, Session
from .client import Client

__all__ = ['Calendar', 'Day', 'ScheduleRow', 'Session', 'get_calendar']


def get_calendar(
    mic: str,
    *,
    client: Client | None = None,
    on_unknown: OnUnknown = 'raise',
    product: str | None = None,
    cache: bool = True,
    as_of: datetime.datetime | str | None = None,
) -> Calendar:
    """The calendar for a MIC. The key is `DIURN_API_KEY` unless `client`
    carries one."""
    return Calendar(mic, client, on_unknown=on_unknown, product=product, cache=cache, as_of=as_of)
