"""The same calendar in pandas and StaticFrame types."""

from __future__ import annotations

import numpy as np
import pandas as pd
import static_frame as sf

import diurn
import diurn.sf as dsf
from diurn.client import Client


def test_pandas_flavor_matches_exchange_calendars_types(client: Client) -> None:
    x = diurn.get_calendar("XNYS", client=client, cache=False)
    assert x.next_session("2026-11-25") == pd.Timestamp("2026-11-27")
    assert x.next_session(pd.Timestamp("2026-11-25")) == pd.Timestamp("2026-11-27")
    idx = x.sessions_in_range("2026-11-24", "2026-11-30")
    assert isinstance(idx, pd.DatetimeIndex) and len(idx) == 4
    close = x.next_close(pd.Timestamp("2026-11-27 15:00", tz="UTC"))
    assert close == pd.Timestamp("2026-11-27 18:00", tz="UTC")  # 13:00 New York
    assert str(close.tz) == "America/New_York"


def test_pandas_schedule(client: Client) -> None:
    x = diurn.get_calendar("XTKS", client=client, cache=False)
    frame = x.schedule("2026-11-02", "2026-11-06")
    assert list(frame.columns) == [
        "open", "break_start", "break_end", "close", "kind", "verification", "reason"
    ]
    assert frame.index.name == "session"
    assert pd.Timestamp("2026-11-03") not in frame.index  # Culture Day
    assert str(frame["open"].dtype) == "datetime64[ns, Asia/Tokyo]"
    assert frame.loc["2026-11-02", "break_start"].hour == 11
    every = x.schedule("2026-11-02", "2026-11-06", all_days=True)
    assert every.loc["2026-11-03", "kind"] == "holiday"
    assert pd.isna(every.loc["2026-11-03", "open"])


def test_static_frame_flavor(client: Client) -> None:
    x = dsf.get_calendar("XNYS", client=client, cache=False)
    assert x.next_session("2026-11-25") == np.datetime64("2026-11-27")
    idx = x.sessions_in_range("2026-11-24", "2026-11-30")
    assert isinstance(idx, sf.IndexDate) and len(idx) == 4
    frame = x.schedule("2026-11-27", "2026-11-27")
    assert isinstance(frame, sf.Frame)
    assert frame.loc[np.datetime64("2026-11-27"), "close"] == np.datetime64("2026-11-27T18:00:00")
    assert frame.loc[np.datetime64("2026-11-27"), "kind"] == "early_close"
    assert x.next_close("2026-11-27T15:00:00Z") == np.datetime64("2026-11-27T18:00:00")
