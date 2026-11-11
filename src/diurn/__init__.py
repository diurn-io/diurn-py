"""Diurn: exchange calendars and trading hours, from the Diurn API.

    import diurn
    xnys = diurn.get_calendar("XNYS")        # key from DIURN_API_KEY
    xnys.is_session("2026-11-26")            # False: Thanksgiving
    xnys.next_session("2026-11-25")          # Timestamp('2026-11-27 00:00:00')

The top level is the pandas flavor, shaped like `exchange_calendars`. The same
calendar comes in two other flavors, with the same methods:

    import diurn.py as dpy     # datetime.date, aware datetime, lists
    import diurn.sf as dsf     # np.datetime64, sf.IndexDate, sf.Frame (diurn[sf])

`diurn.Client` is the API itself, one method per operation.
"""

from __future__ import annotations

from . import errors
from ._core import Day, ScheduleRow, Session
from .client import Client
from .errors import (
    ApiError,
    AuthError,
    DiurnError,
    Indeterminate,
    MicCapExceeded,
    NotInPlan,
    OutOfWindow,
    OverLimit,
    RateLimited,
    TransportError,
    UnknownVenue,
)
from .pd import Calendar, get_calendar

__version__ = "0.1.0"

__all__ = [
    "ApiError",
    "AuthError",
    "Calendar",
    "Client",
    "Day",
    "DiurnError",
    "Indeterminate",
    "MicCapExceeded",
    "NotInPlan",
    "OutOfWindow",
    "OverLimit",
    "RateLimited",
    "ScheduleRow",
    "Session",
    "TransportError",
    "UnknownVenue",
    "errors",
    "get_calendar",
    "__version__",
]
