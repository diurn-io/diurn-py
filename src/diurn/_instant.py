"""Instants as the API writes them, and dates as callers pass them.

The API writes an instant in the venue's own zone with the IANA name in
brackets (RFC 9557): `2026-11-27T13:00:00-05:00[America/New_York]`. Python's
`fromisoformat` takes the offset but not the bracket, so the zone is attached
here, and a session's close stays a zoned instant rather than a UTC one.
"""

from __future__ import annotations

import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

__all__ = ['parse_instant', 'to_date', 'to_instant']


@lru_cache(maxsize=512)
def _zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def parse_instant(text: str) -> datetime.datetime:
    """An API instant as an aware `datetime` in the venue's zone."""
    zone = None
    if text.endswith(']') and '[' in text:
        text, _, name = text[:-1].partition('[')
        zone = _zone(name)
    value = datetime.datetime.fromisoformat(text)
    if value.tzinfo is None:
        raise ValueError(f'instant without an offset: {text!r}')
    return value.astimezone(zone) if zone is not None else value


def to_date(value: object) -> datetime.date:
    """A date from a `date`, an ISO string, or anything with `.date()` that is
    not timezone-aware (a midnight pandas Timestamp, a numpy datetime64)."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        return datetime.date.fromisoformat(value[:10])
    to_py = getattr(value, 'to_pydatetime', None)  # pandas
    if to_py is not None:
        return to_date(to_py())
    if _is_datetime64(value):
        return to_date(_datetime64_item(value))
    raise TypeError(f'not a date: {value!r}')


def to_instant(value: object) -> datetime.datetime:
    """An aware `datetime` from an aware `datetime`, a pandas Timestamp, or an
    ISO string with an offset or `Z`. A naive value is refused: an instant
    without a zone is not one."""
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    to_py = getattr(value, 'to_pydatetime', None)
    if to_py is not None:
        value = to_py()
    if _is_datetime64(value):
        # numpy datetime64 carries no zone; it is UTC by convention.
        item = _datetime64_item(value)
        if isinstance(item, datetime.datetime):
            value = item.replace(tzinfo=datetime.UTC)
        elif isinstance(item, datetime.date):
            value = datetime.datetime.combine(item, datetime.time(), datetime.UTC)
    if not isinstance(value, datetime.datetime):
        raise TypeError(f'not an instant: {value!r}')
    if value.tzinfo is None:
        raise ValueError('a naive datetime is not an instant: give it a time zone')
    return value


def _is_datetime64(value: object) -> bool:
    dtype = getattr(value, 'dtype', None)
    return dtype is not None and getattr(dtype, 'kind', '') == 'M'


# The units `.item()` returns as an `int` rather than a `date` or `datetime`:
# finer than Python's microsecond.
_FINER_THAN_US = frozenset({'ns', 'ps', 'fs', 'as'})


def _datetime64_item(value: object) -> object:
    """A numpy datetime64 as `date` (units of a day or longer) or `datetime`.

    NumPy is imported here, not at the top: this runs only when a caller has
    handed over a datetime64, so NumPy is already loaded and the import costs
    a lookup, while `import diurn` stays free of it."""
    import numpy as np

    if np.isnat(value):  # type: ignore[call-overload]
        raise ValueError('NaT is not a date or an instant')
    unit, _ = np.datetime_data(value.dtype)  # type: ignore[attr-defined]
    if unit in _FINER_THAN_US:
        value = value.astype('datetime64[us]')  # type: ignore[attr-defined]
    return value.item()  # type: ignore[attr-defined]
