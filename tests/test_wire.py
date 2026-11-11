"""The wire layer: generated models, instants, errors, and the generator."""

from __future__ import annotations

import datetime
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import diurn
from diurn import errors
from diurn._instant import parse_instant, to_date, to_instant
from diurn.client import Client

from .conftest import FakeSend

ROOT = Path(__file__).resolve().parent.parent


def test_generated_models_are_current() -> None:
    r = subprocess.run([sys.executable, "tools/generate.py", "--check"], cwd=ROOT)
    assert r.returncode == 0, "run python tools/generate.py"


def test_instants_keep_their_iana_zone() -> None:
    t = parse_instant("2026-11-27T13:00:00-05:00[America/New_York]")
    assert str(t.tzinfo) == "America/New_York"
    assert t.utcoffset() == datetime.timedelta(hours=-5)
    assert parse_instant("2026-11-27T18:00:00+00:00") == t


def test_dates_from_anything_reasonable() -> None:
    expected = datetime.date(2026, 11, 27)
    for value in (
        expected,
        "2026-11-27",
        pd.Timestamp("2026-11-27"),
        np.datetime64("2026-11-27"),
        np.datetime64("2026-11-27T00:00:00.000000000"),
    ):
        assert to_date(value) == expected, value
    with pytest.raises(ValueError):
        to_instant("2026-11-27T12:00:00")  # no zone


def test_typed_models_from_a_real_response(client: Client) -> None:
    days = client.sessions("XNYS", "2026-01-01", "2026-12-31").days
    thanksgiving = next(d for d in days if d.date == datetime.date(2026, 11, 26))
    assert thanksgiving.kind == "holiday" and thanksgiving.sessions == ()
    assert thanksgiving.verification == "verified"
    venue = client.venue("xnys")
    assert venue.mic == "XNYS" and venue.timezone == "America/New_York"


def test_errors_carry_their_numbers(send: FakeSend) -> None:
    send.overrides["/v1/venues/XNYS/status?at=2026-11-27T15%3A00%3A00%2B00%3A00"] = (
        429,
        {
            "error": "mic_cap_exceeded",
            "message": "XNYS would be unique MIC number 3",
            "limit": {"kind": "mics_day", "used": 2, "max": 2},
            "mics_in_use": ["XLON", "XTKS"],
            "resets_at": "2026-11-28T09:00:00Z",
            "upgrade": "https://diurn.io/pricing",
        },
    )
    client = Client(api_key="k", base_url="https://api.test", send=send)
    with pytest.raises(diurn.MicCapExceeded) as e:
        client.status("XNYS", "2026-11-27T15:00:00Z")
    assert e.value.mics_in_use == ["XLON", "XTKS"]
    assert e.value.limit == {"kind": "mics_day", "used": 2, "max": 2}
    assert e.value.resets_at == "2026-11-28T09:00:00Z"


def test_error_classes_by_tag() -> None:
    assert isinstance(errors.from_response(401, {"error": "needs_key", "message": ""}), diurn.AuthError)
    out = errors.from_response(
        403, {"error": "out_of_window", "message": "", "allowed": {"from": "2026-01-01", "to": None}}
    )
    assert isinstance(out, diurn.OutOfWindow) and out.allowed_from == datetime.date(2026, 1, 1)
    assert out.allowed_to is None
    limited = errors.from_response(429, {"error": "rate_limited", "message": ""}, retry_after=2.0)
    assert isinstance(limited, diurn.RateLimited) and limited.retry_after == 2.0
    assert isinstance(errors.from_response(404, {"error": "unknown_mic", "message": ""}), diurn.UnknownVenue)


def test_a_mic_is_checked_before_any_request(client: Client) -> None:
    with pytest.raises(ValueError):
        client.venue("NYSE!")
