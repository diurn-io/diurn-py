"""The API, one method per operation, returning the generated models.

This is the lower layer. Most callers want a calendar (`diurn.get_calendar`),
which is built on it; `Client` is for the operations a calendar does not cover
(venue search, multi-venue status, usage) and for callers who want the API's
own shapes.

Dates are `datetime.date` and instants aware `datetime` objects on the way in
(ISO strings are accepted too); on the way out they are as the models declare.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any, Literal

from ._generated import models as m
from ._instant import to_date, to_instant
from ._transport import Send, Transport

__all__ = ['Client']

DateLike = datetime.date | str
InstantLike = datetime.datetime | str
Mode = Literal['all', 'any']
OnUnknown = Literal['error', 'skip']

# A GET whose MIC list would be longer than this is sent as the POST form.
_POST_ABOVE = 40


class Client:
    """A connection to the Diurn API.

    `api_key` defaults to `DIURN_API_KEY`, and `base_url` to `DIURN_API_URL`
    or https://api.diurn.io. Every endpoint but the registry record, `/health`
    and the OpenAPI document needs a key; a free one is at
    https://diurn.io/signin/.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        send: Send | None = None,
    ):
        self.transport = Transport(api_key=api_key, base_url=base_url, timeout=timeout, send=send)

    @property
    def last_headers(self) -> dict[str, str]:
        """The headers of the last response, lower-cased: the usage headers
        (`diurn-mics-day`, `ratelimit-remaining`, ...) and `x-diurn-dataset`."""
        return dict(self.transport.last_headers)

    # --- free ----------------------------------------------------------------

    def health(self) -> m.Health:
        return m.Health.from_json(self.transport.get('/health'))

    def venue(self, mic: str) -> m.VenueResponse:
        """The ISO 10383 record, with the venue's zone and how it is answered.
        Free and unmetered."""
        return m.VenueResponse.from_json(self.transport.get(f'/v1/venues/{_mic(mic)}'))

    def venues(
        self,
        q: str | None = None,
        country: str | None = None,
        resolution: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> m.VenuesResponse:
        """List and search venues. Free and unmetered."""
        params = dict(q=q, country=country, resolution=resolution, status=status, limit=limit, cursor=cursor)
        return m.VenuesResponse.from_json(self.transport.get('/v1/venues', params))

    def usage(self) -> m.UsageView:
        """Your usage against your plan. Needs a key; never metered."""
        return m.UsageView.from_json(self.transport.get('/v1/usage'))

    # --- one venue -------------------------------------------------------------

    def sessions(
        self,
        mic: str,
        start: DateLike,
        end: DateLike,
        *,
        kinds: Sequence[str] | None = None,
        provenance: bool = False,
        as_of: InstantLike | None = None,
    ) -> m.DaysResponse:
        """Every day from `start` to `end`, inclusive, with its sessions."""
        params = {
            'from': to_date(start),
            'to': to_date(end),
            'kinds': kinds,
            'expand': 'provenance' if provenance else None,
            'as_of': _instant(as_of),
        }
        return m.DaysResponse.from_json(self.transport.get(f'/v1/venues/{_mic(mic)}/sessions', params))

    def day(self, mic: str, date: DateLike, *, as_of: InstantLike | None = None) -> m.DayResponse:
        """One day, with its provenance in full."""
        path = f'/v1/venues/{_mic(mic)}/days/{to_date(date).isoformat()}'
        return m.DayResponse.from_json(self.transport.get(path, {'as_of': _instant(as_of)}))

    def status(
        self, mic: str, at: InstantLike | None = None, *, as_of: InstantLike | None = None
    ) -> m.StatusResponse:
        """Whether the venue is trading at an instant (now, if `at` is None)."""
        when = to_instant(at) if at is not None else datetime.datetime.now(datetime.UTC)
        params = {'at': when, 'as_of': _instant(as_of)}
        return m.StatusResponse.from_json(self.transport.get(f'/v1/venues/{_mic(mic)}/status', params))

    def next_open(
        self, mic: str, start: InstantLike, *, as_of: InstantLike | None = None
    ) -> m.InstantResponse:
        params = {'from': to_instant(start), 'as_of': _instant(as_of)}
        return m.InstantResponse.from_json(self.transport.get(f'/v1/venues/{_mic(mic)}/next-open', params))

    def next_close(
        self, mic: str, start: InstantLike, *, as_of: InstantLike | None = None
    ) -> m.InstantResponse:
        params = {'from': to_instant(start), 'as_of': _instant(as_of)}
        return m.InstantResponse.from_json(self.transport.get(f'/v1/venues/{_mic(mic)}/next-close', params))

    def next_trading_day(
        self,
        mic: str,
        start: DateLike,
        n: int = 1,
        *,
        inclusive: bool = False,
        on_unknown: OnUnknown = 'error',
        as_of: InstantLike | None = None,
    ) -> m.StepResponse:
        return self._step(mic, 'next', start, n, inclusive, on_unknown, as_of)

    def previous_trading_day(
        self,
        mic: str,
        start: DateLike,
        n: int = 1,
        *,
        inclusive: bool = False,
        on_unknown: OnUnknown = 'error',
        as_of: InstantLike | None = None,
    ) -> m.StepResponse:
        return self._step(mic, 'previous', start, n, inclusive, on_unknown, as_of)

    def count_trading_days(
        self, mic: str, start: DateLike, end: DateLike, *, as_of: InstantLike | None = None
    ) -> m.CountResponse:
        """Trading days from `start` to `end`, inclusive; a lower bound where
        `unknown` is above zero."""
        params = {'from': to_date(start), 'to': to_date(end), 'as_of': _instant(as_of)}
        path = f'/v1/venues/{_mic(mic)}/trading-days/count'
        return m.CountResponse.from_json(self.transport.get(path, params))

    def _step(
        self,
        mic: str,
        direction: str,
        start: DateLike,
        n: int,
        inclusive: bool,
        on_unknown: str,
        as_of: InstantLike | None,
    ) -> m.StepResponse:
        params = {
            'from': to_date(start),
            'n': n,
            'inclusive': inclusive,
            'on_unknown': on_unknown,
            'as_of': _instant(as_of),
        }
        path = f'/v1/venues/{_mic(mic)}/trading-days/{direction}'
        return m.StepResponse.from_json(self.transport.get(path, params))

    # --- many venues -------------------------------------------------------------

    def statuses(
        self, mics: Sequence[str], at: InstantLike | None = None, *, as_of: InstantLike | None = None
    ) -> m.StatusesResponse:
        """Whether several venues are trading at an instant (now, if None)."""
        body = {'mics': _mics(mics), 'at': _instant(at), 'as_of': _instant(as_of)}
        return m.StatusesResponse.from_json(self._many('/v1/status', body))

    def exceptions(
        self,
        mics: Sequence[str],
        start: DateLike,
        end: DateLike,
        *,
        kinds: Sequence[str] | None = None,
        as_of: InstantLike | None = None,
    ) -> m.ExceptionsResponse:
        """Holidays and irregular days across venues, one row each."""
        body = {
            'mics': _mics(mics),
            'from': to_date(start),
            'to': to_date(end),
            'kinds': list(kinds) if kinds else None,
            'as_of': _instant(as_of),
        }
        return m.ExceptionsResponse.from_json(self._many('/v1/exceptions', body))

    def sessions_bulk(
        self,
        mics: Sequence[str],
        start: DateLike,
        end: DateLike,
        *,
        as_of: InstantLike | None = None,
    ) -> m.BulkResponse:
        """Many venues over a range, column-oriented."""
        body = {'mics': _mics(mics), 'from': to_date(start), 'to': to_date(end), 'as_of': _instant(as_of)}
        return m.BulkResponse.from_json(self._many('/v1/sessions', body))

    def trading_days(
        self,
        mics: Sequence[str],
        start: DateLike,
        end: DateLike,
        *,
        as_of: InstantLike | None = None,
    ) -> m.TradingDaysResponse:
        """A date-and-boolean series per venue; `None` where it cannot say."""
        body = {'mics': _mics(mics), 'from': to_date(start), 'to': to_date(end), 'as_of': _instant(as_of)}
        return m.TradingDaysResponse.from_json(self._many('/v1/trading-days', body))

    def joint_next_trading_day(
        self,
        mics: Sequence[str],
        start: DateLike,
        n: int = 1,
        *,
        mode: Mode = 'all',
        inclusive: bool = False,
        on_unknown: OnUnknown = 'error',
        as_of: InstantLike | None = None,
    ) -> m.JointStepResponse:
        """The nth date after `start` on which all (or any) of the venues trade."""
        return self._joint('next', mics, start, n, mode, inclusive, on_unknown, as_of)

    def joint_previous_trading_day(
        self,
        mics: Sequence[str],
        start: DateLike,
        n: int = 1,
        *,
        mode: Mode = 'all',
        inclusive: bool = False,
        on_unknown: OnUnknown = 'error',
        as_of: InstantLike | None = None,
    ) -> m.JointStepResponse:
        return self._joint('previous', mics, start, n, mode, inclusive, on_unknown, as_of)

    def _joint(
        self,
        direction: str,
        mics: Sequence[str],
        start: DateLike,
        n: int,
        mode: str,
        inclusive: bool,
        on_unknown: str,
        as_of: InstantLike | None,
    ) -> m.JointStepResponse:
        body = {
            'mics': _mics(mics),
            'from': to_date(start),
            'n': n,
            'mode': mode,
            'inclusive': inclusive,
            'on_unknown': on_unknown,
            'as_of': _instant(as_of),
        }
        return m.JointStepResponse.from_json(self._many(f'/v1/trading-days/{direction}', body))

    def _many(self, path: str, body: dict[str, Any]) -> Any:
        """GET for a short MIC list; the POST form when it would be long."""
        if len(body['mics']) > _POST_ABOVE:
            return self.transport.post(path, body)
        return self.transport.get(path, body)


def _mic(mic: str) -> str:
    code = mic.strip().upper()
    if len(code) != 4 or not code.isalnum():
        raise ValueError(f'not a MIC: {mic!r}')
    return code


def _mics(mics: Sequence[str]) -> list[str]:
    if isinstance(mics, str):
        mics = [m for m in mics.split(',') if m.strip()]
    return [_mic(x) for x in mics]


def _instant(value: InstantLike | None) -> datetime.datetime | None:
    return None if value is None else to_instant(value)
