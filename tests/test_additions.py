"""Retries, the async client, and exchange_calendars' per-session methods."""

from __future__ import annotations

import asyncio
import datetime
import inspect

import numpy as np
import pandas as pd
import pytest

import diurn
import diurn.py as dpy
import diurn.sf as dsf
from diurn.client import AsyncClient, Client

from .conftest import FakeSend

D = datetime.date
VENUE = '/v1/venues/XNYS'
RATE = (429, {'error': 'rate_limited', 'message': 'slow down'})
CAP = (429, {'error': 'mic_cap_exceeded', 'message': '', 'mics_in_use': ['XLON']})
DOWN = (503, {'error': 'as_of_unavailable', 'message': 'try again shortly'})


def retrying(send: FakeSend, retries: int = 3, max_wait: float = 60.0) -> tuple[Client, list[float]]:
    slept: list[float] = []
    client = Client(api_key='k', base_url='https://api.test', send=send, retries=retries, max_wait=max_wait)
    client.transport.sleep = slept.append
    return client, slept


def recorded_venue() -> tuple[int, object]:
    return (200, diurn.Client(api_key='k', base_url='https://api.test', send=FakeSend()).transport.get(VENUE))


# --- retries ------------------------------------------------------------------


def test_a_rate_limit_is_waited_out_as_the_server_says(send: FakeSend) -> None:
    send.overrides[VENUE] = [(*RATE, {'retry-after': '2'}), recorded_venue()]
    client, slept = retrying(send)
    assert client.venue('XNYS').mic == 'XNYS'
    assert slept == [2.0]


def test_failures_in_transit_back_off(send: FakeSend) -> None:
    send.overrides[VENUE] = [DOWN, DOWN, recorded_venue()]
    client, slept = retrying(send)
    assert client.venue('XNYS').mic == 'XNYS'
    assert slept == [0.5, 1.0]


def test_a_dropped_connection_is_retried() -> None:
    calls = []

    def flaky(*args: object) -> object:
        calls.append(1)
        if len(calls) == 1:
            raise diurn.TransportError('connection reset')
        return FakeSend()(*args)  # type: ignore[arg-type]

    client = Client(api_key='k', base_url='https://api.test', send=flaky, retries=1)  # type: ignore[arg-type]
    client.transport.sleep = lambda s: None
    assert client.venue('XNYS').mic == 'XNYS' and len(calls) == 2


def test_no_retry_unless_asked(send: FakeSend) -> None:
    send.overrides[VENUE] = [RATE, recorded_venue()]
    client, slept = retrying(send, retries=0)
    with pytest.raises(diurn.RateLimited):
        client.venue('XNYS')
    assert slept == []


def test_a_plans_refusal_is_never_retried(send: FakeSend) -> None:
    send.overrides[VENUE] = [CAP, recorded_venue()]
    client, slept = retrying(send)
    with pytest.raises(diurn.MicCapExceeded):
        client.venue('XNYS')
    assert slept == [] and send.requests.count(VENUE) == 1


def test_a_wait_longer_than_max_wait_is_raised_not_slept(send: FakeSend) -> None:
    send.overrides[VENUE] = [(*RATE, {'retry-after': '120'}), recorded_venue()]
    client, slept = retrying(send, max_wait=60)
    with pytest.raises(diurn.RateLimited) as e:
        client.venue('XNYS')
    assert e.value.retry_after == 120.0 and slept == []


def test_retries_run_out(send: FakeSend) -> None:
    send.overrides[VENUE] = [DOWN]
    client, slept = retrying(send, retries=2)
    with pytest.raises(diurn.errors.Unavailable):
        client.venue('XNYS')
    assert slept == [0.5, 1.0] and send.requests.count(VENUE) == 3


# --- the async client -----------------------------------------------------------


def test_every_client_operation_has_an_async_one() -> None:
    public = {n for n, f in inspect.getmembers(Client, inspect.isfunction) if not n.startswith('_')}
    for name in public:
        method = getattr(AsyncClient, name, None)
        assert method is not None and inspect.iscoroutinefunction(method), name
        assert method.__doc__ == getattr(Client, name).__doc__, name
        # What help() and an IDE show at runtime: the real parameters, not
        # *args and **kwargs, under AsyncClient's name.
        assert inspect.signature(method) == inspect.signature(getattr(Client, name)), name
        assert method.__qualname__ == f'AsyncClient.{name}', name


def test_async_calls_run_together(send: FakeSend) -> None:
    client = AsyncClient(api_key='k', base_url='https://api.test', send=send)

    async def main() -> list[str]:
        venues = await asyncio.gather(*(client.venue(m) for m in ('XNYS', 'XTKS', 'XHKG')))
        return [v.timezone or '' for v in venues]

    assert asyncio.run(main()) == ['America/New_York', 'Asia/Tokyo', 'Asia/Hong_Kong']


def test_async_errors_are_the_same_errors(send: FakeSend) -> None:
    client = AsyncClient(api_key='k', base_url='https://api.test', send=send)
    with pytest.raises(diurn.UnknownVenue):
        asyncio.run(client.venue('ZZZZ'))


# --- one session's times ----------------------------------------------------------


def cal(client: Client, mic: str = 'XNYS') -> dpy.Calendar:
    return dpy.get_calendar(mic, client=client, cache=False)


def test_a_sessions_open_close_and_break(client: Client) -> None:
    tokyo = cal(client, 'XTKS')
    assert tokyo.session_open('2026-11-02').strftime('%H:%M') == '09:00'  # type: ignore[union-attr]
    assert tokyo.session_break_start('2026-11-02').strftime('%H:%M') == '11:30'  # type: ignore[union-attr]
    assert tokyo.session_break_end('2026-11-02').strftime('%H:%M') == '12:30'  # type: ignore[union-attr]
    assert tokyo.session_close('2026-11-02').strftime('%H:%M') == '15:30'  # type: ignore[union-attr]
    nyse = cal(client)
    assert nyse.session_close('2026-11-27').isoformat() == '2026-11-27T13:00:00-05:00'  # type: ignore[union-attr]
    assert nyse.session_break_start('2026-11-27') is None  # no lunch in New York
    with pytest.raises(ValueError, match='not a session'):
        nyse.session_open('2026-11-26')  # Thanksgiving


def test_sessions_distance(client: Client) -> None:
    nyse = cal(client)
    assert nyse.sessions_distance('2026-11-01', '2026-11-30') == 20  # 21 weekdays, less Thanksgiving
    assert nyse.sessions_distance('2026-11-30', '2026-11-01') == -20
    assert nyse.sessions_distance('2026-11-26', '2026-11-26') == 0
    assert nyse.sessions_distance('2026-11-27', '2026-11-27') == 1


def test_the_flavors_give_session_times_in_their_types(client: Client) -> None:
    p = diurn.get_calendar('XNYS', client=client, cache=False)
    assert p.session_close('2026-11-27') == pd.Timestamp('2026-11-27 18:00', tz='UTC')
    assert str(p.session_close('2026-11-27').tz) == 'America/New_York'
    assert pd.isna(p.session_break_start('2026-11-27'))
    s = dsf.get_calendar('XNYS', client=client, cache=False)
    assert s.session_close('2026-11-27') == np.datetime64('2026-11-27T18:00:00')
    assert np.isnat(s.session_break_start('2026-11-27'))
    november = ('2026-11-01', '2026-11-30')
    assert p.sessions_distance(*november) == s.sessions_distance(*november) == 20
