"""The calendar's answers, from recorded XNYS, XTKS and XHKG responses."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import pytest

import diurn
import diurn.py as dpy
from diurn._cache import DiskCache
from diurn.client import Client

from .conftest import FakeSend

D = datetime.date


def cal(client: Client, mic: str = "XNYS", **kw: Any) -> dpy.Calendar:
    return dpy.get_calendar(mic, client=client, cache=False, **kw)


def test_sessions_around_thanksgiving(client: Client) -> None:
    x = cal(client)
    assert x.is_session("2026-11-26") is False  # Thanksgiving
    assert x.is_session(D(2026, 11, 27)) is True  # early close, still a session
    assert x.next_session("2026-11-25") == D(2026, 11, 27)
    assert x.previous_session("2026-11-27") == D(2026, 11, 25)
    assert x.next_session("2026-11-26") == D(2026, 11, 27)  # need not be a session
    assert x.sessions_in_range("2026-11-24", "2026-11-30") == [
        D(2026, 11, 24),
        D(2026, 11, 25),
        D(2026, 11, 27),
        D(2026, 11, 30),
    ]


def test_date_to_session_and_window(client: Client) -> None:
    x = cal(client)
    assert x.date_to_session("2026-11-27") == D(2026, 11, 27)
    assert x.date_to_session("2026-11-26", "next") == D(2026, 11, 27)
    assert x.date_to_session("2026-11-26", "previous") == D(2026, 11, 25)
    with pytest.raises(ValueError):
        x.date_to_session("2026-11-26")
    assert x.sessions_window("2026-11-25", 3) == [D(2026, 11, 25), D(2026, 11, 27), D(2026, 11, 30)]
    assert x.sessions_window("2026-11-27", -2) == [D(2026, 11, 25), D(2026, 11, 27)]


def test_stepping_crosses_the_year(client: Client) -> None:
    x = cal(client)
    assert x.next_session("2026-12-31") == D(2027, 1, 4)  # New Year's Day, then a weekend


def test_instants_keep_the_venue_zone(client: Client) -> None:
    x = cal(client)
    close = x.next_close("2026-11-27T15:00:00Z")
    assert close is not None
    assert close.isoformat() == "2026-11-27T13:00:00-05:00"
    assert str(close.tzinfo) == "America/New_York"
    opens = x.next_open("2026-11-26T12:00:00Z")  # Thanksgiving: the next open is Friday's
    assert opens is not None and opens.date() == D(2026, 11, 27)
    assert x.is_open_at_time("2026-11-27T17:30:00Z") is True
    assert x.is_open_at_time("2026-11-27T18:30:00Z") is False  # after the 13:00 close
    with pytest.raises(ValueError):
        x.is_open_at_time(datetime.datetime(2026, 11, 27, 12))  # naive is not an instant


def test_schedule_lays_out_breaks_like_exchange_calendars(client: Client) -> None:
    tokyo = cal(client, "XTKS")
    (row,) = tokyo.schedule("2026-11-02", "2026-11-02")
    assert (row.open.hour, row.break_start.hour, row.break_end.hour, row.close.hour) == (9, 11, 12, 15)  # type: ignore[union-attr]
    # Culture Day is not a session; with all_days it is a row with its reason.
    assert tokyo.schedule("2026-11-03", "2026-11-03") == []
    (holiday,) = tokyo.schedule("2026-11-03", "2026-11-03", all_days=True)
    assert holiday.kind == "holiday" and holiday.open is None and holiday.reason


def test_a_close_inside_the_lunch_break_has_no_break(client: Client) -> None:
    hk = cal(client, "XHKG")
    (eve,) = hk.schedule("2026-12-24", "2026-12-24")
    assert eve.kind == "early_close"
    assert eve.break_start is None and eve.close.strftime("%H:%M") == "12:10"  # type: ignore[union-attr]


def test_unknown_is_neither_a_session_nor_a_closure(send: FakeSend) -> None:
    unknown = {
        "mic": "XNYS",
        "days": [
            {"date": "2026-11-25", "kind": "open", "verification": "inferreddefinitional"},
            {"date": "2026-11-26", "kind": "unknown", "verification": "inferredadvisory"},
        ],
    }
    path = "/v1/venues/XNYS/sessions?from=2026-01-01&to=2026-12-31"
    send.overrides[path] = (200, {**unknown, "days": _year_with(unknown["days"])})
    client = Client(api_key="k", base_url="https://api.test", send=send)
    strict = cal(client)
    with pytest.raises(diurn.Indeterminate) as e:
        strict.is_session("2026-11-26")
    assert e.value.date == D(2026, 11, 26)
    with pytest.raises(diurn.Indeterminate):
        strict.next_session("2026-11-25")
    lenient = cal(client, on_unknown="missing")
    assert lenient.is_session("2026-11-26") is None
    assert lenient.next_session("2026-11-25") is None
    assert D(2026, 11, 26) not in lenient.sessions_in_range("2026-11-20", "2026-11-30")


def _year_with(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A whole year of ordinary days, with `days` substituted."""
    given = {d["date"]: d for d in days}
    out = []
    d = D(2026, 1, 1)
    while d.year == 2026:
        key = d.isoformat()
        kind = "weekend" if d.weekday() >= 5 else "open"
        out.append(given.get(key, {"date": key, "kind": kind, "verification": "inferreddefinitional"}))
        d += datetime.timedelta(days=1)
    return out


def test_the_cache_answers_without_a_request(send: FakeSend, tmp_path: Path) -> None:
    client = Client(api_key="k", base_url="https://api.test", send=send)
    cache = DiskCache(client.transport.base_url, lambda: client.health().dataset, tmp_path)
    first = dpy.get_calendar("XNYS", client=client, cache=cache)  # type: ignore[arg-type]
    assert first.is_session("2026-11-26") is False
    fetched = [r for r in send.requests if "/sessions" in r]
    second = dpy.get_calendar("XNYS", client=client, cache=cache)  # type: ignore[arg-type]
    assert second.is_session("2026-11-26") is False
    assert [r for r in send.requests if "/sessions" in r] == fetched, "answered from disk"


def test_a_new_dataset_drops_the_old_answers(send: FakeSend, tmp_path: Path) -> None:
    client = Client(api_key="k", base_url="https://api.test", send=send)
    served = ["aaaaaaaaaaaa"]
    cache = DiskCache(client.transport.base_url, lambda: served[0], tmp_path, check_every=0)
    dpy.get_calendar("XNYS", client=client, cache=cache).is_session("2026-11-26")  # type: ignore[arg-type]
    assert (cache.root / "aaaaaaaaaaaa").is_dir()
    served[0] = "bbbbbbbbbbbb"
    dpy.get_calendar("XNYS", client=client, cache=cache).is_session("2026-11-26")  # type: ignore[arg-type]
    assert not (cache.root / "aaaaaaaaaaaa").exists()
    assert (cache.root / "bbbbbbbbbbbb").is_dir()


def test_a_plan_window_is_refused_not_trimmed(send: FakeSend) -> None:
    send.overrides["/v1/usage"] = (
        200,
        {
            "plan": "free",
            "mics_day": {"used": 0, "max": 2, "window": "rolling_24h"},
            "mics_month": {"used": 0, "max": 3, "window": "rolling_30d"},
            "horizon": {"from": "2026-01-01", "to": "2026-12-10"},
            "rate": {"per_minute": 10, "bulk_per_minute": 1},
        },
    )
    client = Client(api_key="k", base_url="https://api.test", send=send)
    x = cal(client)
    assert x.is_session("2026-11-26") is False
    with pytest.raises(diurn.OutOfWindow) as e:
        x.is_session("2026-12-24")
    assert e.value.allowed_to == D(2026, 12, 10)
    # The chunk was trimmed to the window, so nothing past it was asked for.
    assert any("to=2026-12-10" in r for r in send.requests)


def test_a_product_must_exist(client: Client) -> None:
    with pytest.raises(ValueError):
        cal(client, product="no such product")


def test_an_unknown_mic_is_refused(client: Client) -> None:
    with pytest.raises(diurn.UnknownVenue):
        cal(client, "ZZZZ")


def test_a_product_picks_its_own_sessions(client: Client) -> None:
    # COMEX, answered through NYMEX: every session is scoped to a product, and
    # the API names it in the venue's words, as a string.
    whole = cal(client, "XCEC")
    assert "Equity Index" in whole.products
    (globex,) = whole.day("2026-11-03").sessions
    assert globex.products == "Equity Index"
    equity = cal(client, "XCEC", product="Equity Index")
    (row,) = equity.schedule("2026-11-03", "2026-11-03")
    assert row.open is not None and row.open.strftime("%a %H:%M") == "Mon 17:00"
    assert equity.is_open_at_time("2026-11-03T15:00:00Z") is True
    # A product with no hours of its own is never handed another's.
    metals = cal(client, "XCEC", product="Energy and Metals")
    (row,) = metals.schedule("2026-11-03", "2026-11-03")
    assert row.open is None and row.close is None
    assert metals.is_open_at_time("2026-11-03T15:00:00Z") is False


def test_a_holiday_that_trades_is_a_session(client: Client) -> None:
    # NSE's Muhurat: 8 November is a holiday carrying one evening session,
    # and trades, as /v1/trading-days counts it.
    nse = cal(client, "XNSE")
    assert nse.day("2026-11-08").kind == "holiday"
    assert nse.is_session("2026-11-08") is True
    assert nse.is_open_at_time("2026-11-08T09:30:00Z") is True  # 15:00 in Mumbai
    assert nse.is_session("2026-11-10") is False  # a holiday without one
    assert D(2026, 11, 8) in nse.sessions_in_range("2026-11-06", "2026-11-10")
    assert nse.next_session("2026-11-07") == D(2026, 11, 8)


def test_a_calendar_is_named_by_its_code(client: Client) -> None:
    x = cal(client)
    assert x.name == "XNYS"  # as exchange_calendars names one
    assert x.market_name == "NEW YORK STOCK EXCHANGE, INC."
    assert diurn.get_calendar("XNYS", client=client, cache=False).market_name == x.market_name


def test_a_scan_that_finds_nothing_says_so(send: FakeSend) -> None:
    # Three years with no session: the stepping methods give up, and say so
    # rather than return a missing value nobody asked for.
    for year in (2026, 2027, 2028, 2029):
        path = f"/v1/venues/XNYS/sessions?from={year}-01-01&to={year}-12-31"
        send.overrides[path] = (200, {"mic": "XNYS", "days": _closed_year(year)})
    client = Client(api_key="k", base_url="https://api.test", send=send)
    with pytest.raises(diurn.Indeterminate, match="no session within"):
        cal(client).next_session("2026-01-01")
    assert cal(client, on_unknown="missing").next_session("2026-01-01") is None


def _closed_year(year: int) -> list[dict[str, Any]]:
    out = []
    d = D(year, 1, 1)
    while d.year == year:
        out.append({"date": d.isoformat(), "kind": "holiday", "verification": "verified"})
        d += datetime.timedelta(days=1)
    return out


def test_the_plan_window_is_asked_again_the_next_day(send: FakeSend) -> None:
    client = Client(api_key="k", base_url="https://api.test", send=send)
    x = cal(client)
    x.is_session("2026-11-26")
    x.is_session("2026-11-25")
    assert send.requests.count("/v1/usage") == 1, "once a day"
    x._window_day = D(2000, 1, 1)  # as if the calendar had been open since then
    x.is_session("2026-11-24")
    assert send.requests.count("/v1/usage") == 2


def test_a_schedule_row_exports_to_utc_seconds(client: Client) -> None:
    (row,) = cal(client).schedule("2026-11-27", "2026-11-27")  # an early close
    utc = row.to_utc()
    assert row.close is not None and utc.close == int(row.close.timestamp())
    assert datetime.datetime.fromtimestamp(utc.close, datetime.UTC).isoformat() == "2026-11-27T18:00:00+00:00"
    assert utc.break_start is None and utc.kind == "early_close"


HOME = Path("/home/someone")


@pytest.mark.parametrize(
    ("platform", "environ", "expected"),
    [
        ("linux", {}, HOME / ".cache" / "diurn"),
        ("darwin", {}, HOME / "Library" / "Caches" / "diurn"),
        ("win32", {"LOCALAPPDATA": "C:/Users/someone/AppData/Local"},
         Path("C:/Users/someone/AppData/Local") / "diurn" / "Cache"),
        # Without LOCALAPPDATA, where it would have pointed.
        ("win32", {}, HOME / "AppData" / "Local" / "diurn" / "Cache"),
        # XDG_CACHE_HOME, set by the user, wins on any platform...
        ("linux", {"XDG_CACHE_HOME": "/xdg"}, Path("/xdg/diurn")),
        ("darwin", {"XDG_CACHE_HOME": "/xdg"}, Path("/xdg/diurn")),
        # ...and DIURN_CACHE_DIR over everything.
        ("darwin", {"DIURN_CACHE_DIR": "/mine", "XDG_CACHE_HOME": "/xdg"}, Path("/mine")),
        # Set but empty is not set.
        ("darwin", {"DIURN_CACHE_DIR": "", "XDG_CACHE_HOME": ""}, HOME / "Library" / "Caches" / "diurn"),
    ],
)
def test_the_cache_lives_where_each_platform_keeps_caches(
    platform: str, environ: dict[str, str], expected: Path
) -> None:
    from diurn._cache import default_dir

    assert default_dir(platform, environ, HOME) == expected
