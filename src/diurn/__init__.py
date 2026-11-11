"""Diurn: exchange calendars and trading hours, from the Diurn API.

    import diurn
    xnys = diurn.get_calendar("XNYS")        # key from DIURN_API_KEY
    xnys.is_session("2026-11-26")            # False: Thanksgiving
    xnys.next_session("2026-11-25")          # Timestamp('2026-11-27 00:00:00')

The top level is the pandas flavor, shaped like `exchange_calendars`
(`pip install diurn[pd]`). The same calendar comes in two other flavors, with
the same methods:

    import diurn.py as dpy     # datetime.date, aware datetime, lists (no extras)
    import diurn.sf as dsf     # np.datetime64, sf.IndexDate, sf.Frame (diurn[sf])

`diurn.Client` is the API itself, one method per operation.

**Nothing here imports pandas** until the pandas flavor is used:
`diurn.get_calendar` and `diurn.Calendar` load `diurn.pd` on first access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import errors
from ._core import Day, ScheduleRow, Session
from ._version import __version__
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

if TYPE_CHECKING:
    from .pd import Calendar, get_calendar

# The pandas flavor's names, loaded when first asked for (PEP 562).
_PANDAS = ("Calendar", "get_calendar")


def __getattr__(name: str) -> Any:
    if name in _PANDAS:
        from . import pd

        return getattr(pd, name)
    raise AttributeError(f"module 'diurn' has no attribute {name!r}")


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
    "__version__",
    "errors",
    "get_calendar",
]
