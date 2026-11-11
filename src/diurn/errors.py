"""Typed errors. Callers switch on the class, never on a message.

Every error the API returns carries a stable tag (`error`), and each tag has a
class here. Refusals from a plan's limits carry their numbers as attributes,
so a script can act on them (wait until `resets_at`, narrow to `allowed`)
rather than retry blindly.
"""

from __future__ import annotations

import datetime
from typing import Any

__all__ = [
    "ApiError",
    "AuthError",
    "BadRequest",
    "DiurnError",
    "Indeterminate",
    "IndeterminateResponse",
    "MicCapExceeded",
    "NotInPlan",
    "OutOfWindow",
    "OverLimit",
    "RateLimited",
    "TransportError",
    "Unavailable",
    "UnknownVenue",
]


class DiurnError(Exception):
    """Every error this package raises."""


class TransportError(DiurnError):
    """The API could not be reached, or answered with something that is not
    the API (a proxy's page, a broken connection)."""


class ApiError(DiurnError):
    """The API answered with an error.

    `error` is the API's stable tag; `status` the HTTP status; `body` the
    response as sent, for anything not lifted into an attribute.
    """

    def __init__(self, status: int, error: str, message: str, body: dict[str, Any] | None = None):
        super().__init__(f"{error}: {message}" if message else error)
        self.status = status
        self.error = error
        self.message = message
        self.body = body or {}


class AuthError(ApiError):
    """No key (`needs_key`), or a key that is not active (`unauthorized`).

    Keys are free at https://diurn.io/signin/; set `DIURN_API_KEY` or pass
    `api_key=`.
    """


class UnknownVenue(ApiError):
    """No such MIC, or no calendar answers it."""


class BadRequest(ApiError):
    """The request could not be understood: a malformed date, too many days, or
    `as_of` outside the archive's record."""


class Indeterminate(DiurnError):
    """Diurn cannot say whether the market trades on a date.

    Raised when an answer would depend on an `unknown` day (past what Diurn can
    answer). Diurn never reports such a day as closed or open; pass
    `on_unknown="missing"` to get a missing value instead of this error.
    """

    def __init__(self, mic: str, date: datetime.date, message: str = ""):
        super().__init__(message or f"{mic} cannot be answered for {date.isoformat()}")
        self.mic = mic
        self.date = date


class IndeterminateResponse(ApiError, Indeterminate):
    """The API's `422 indeterminate`: a trading-day walk reached a date it
    cannot answer (`Client.next_trading_day` and the joint steps, with
    `on_unknown="error"`). An `Indeterminate`, so one `except` catches it
    whether the calendar or the API found the day; `date` is that day, and
    `mic` is empty, since the API names the date only."""

    def __init__(self, status: int, error: str, message: str, body: dict[str, Any] | None = None):
        # Both parents set attributes and call `super().__init__` with
        # different arguments, so neither initialiser is chained: the fields
        # of each are set here.
        Exception.__init__(self, f"{error}: {message}" if message else error)
        self.status = status
        self.error = error
        self.message = message
        self.body = body or {}
        self.mic = ""
        self.date = _date(self.body.get("date"))  # type: ignore[assignment]


class Unavailable(ApiError):
    """The service could not answer just now (`503`), for example an `as_of`
    dataset that could not be loaded."""


class OverLimit(ApiError):
    """A refusal from the plan's limits. `limit` is `{kind, used, max}` where
    the API sends it; `resets_at` when the limit eases; `upgrade` where to get
    more."""

    def __init__(self, status: int, error: str, message: str, body: dict[str, Any] | None = None):
        super().__init__(status, error, message, body)
        b = self.body
        self.limit: dict[str, Any] | None = b.get("limit")
        self.resets_at: str | None = b.get("resets_at")
        self.upgrade: str | None = b.get("upgrade")


class NotInPlan(OverLimit):
    """The plan does not include this: an endpoint, provenance or `as_of` (403)."""


class OutOfWindow(OverLimit):
    """Dates outside the plan's window (403). `allowed_from` and `allowed_to`
    are the dates the plan may ask about; `None` is unbounded."""

    def __init__(self, status: int, error: str, message: str, body: dict[str, Any] | None = None):
        super().__init__(status, error, message, body)
        allowed = self.body.get("allowed") or {}
        self.allowed_from = _date(allowed.get("from"))
        self.allowed_to = _date(allowed.get("to"))


class MicCapExceeded(OverLimit):
    """Asking for this MIC would exceed a unique-MIC cap (429). `mics_in_use`
    are the MICs holding the window's slots; asking again for one of them is
    free."""

    def __init__(self, status: int, error: str, message: str, body: dict[str, Any] | None = None):
        super().__init__(status, error, message, body)
        self.mics_in_use: list[str] = list(self.body.get("mics_in_use") or [])


class RateLimited(OverLimit):
    """Too many requests a minute (429). `retry_after` is the server's
    `Retry-After`, in seconds, where it sent one."""

    def __init__(
        self,
        status: int,
        error: str,
        message: str,
        body: dict[str, Any] | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(status, error, message, body)
        self.retry_after = retry_after


def _date(value: Any) -> datetime.date | None:
    return datetime.date.fromisoformat(value) if isinstance(value, str) else None


_BY_TAG: dict[str, type[ApiError]] = {
    "needs_key": AuthError,
    "unauthorized": AuthError,
    "not_in_plan": NotInPlan,
    "out_of_window": OutOfWindow,
    "mic_cap_exceeded": MicCapExceeded,
    "rate_limited": RateLimited,
    "indeterminate": IndeterminateResponse,
    # A server without a key store (a local one) meters nothing.
    "not_metered": ApiError,
}

_BY_STATUS: dict[int, type[ApiError]] = {
    400: BadRequest,
    401: AuthError,
    404: UnknownVenue,
    422: IndeterminateResponse,
    # A plan's refusal this version does not name yet (`venue_days_exceeded`,
    # if budgets return) still carries `limit` and `resets_at`.
    429: OverLimit,
    503: Unavailable,
}


def from_response(
    status: int, body: dict[str, Any] | None, retry_after: float | None = None
) -> ApiError:
    """The error class for an API error response."""
    body = body or {}
    tag = str(body.get("error") or f"http_{status}")
    message = str(body.get("message") or "")
    cls = _BY_TAG.get(tag) or _BY_STATUS.get(status) or ApiError
    if cls is RateLimited:
        return RateLimited(status, tag, message, body, retry_after)
    return cls(status, tag, message, body)
