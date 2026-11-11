"""The same calendar in pandas and StaticFrame types."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
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
        "open",
        "break_start",
        "break_end",
        "close",
        "kind",
        "verification",
        "reason",
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


# The three instants in UTC seconds, as the StaticFrame flavor gives them.
INSTANTS = ("open", "break_start", "break_end", "close")


def _as_static_frame(frame: pd.DataFrame) -> sf.Frame:
    """The pandas schedule, carried to the StaticFrame flavor's conventions:
    instants from the venue's zone to naive UTC at second resolution, and the
    sessions as an `IndexDate`. What is left to differ is the data."""
    norm = frame.copy()
    for col in INSTANTS:
        norm[col] = norm[col].dt.tz_convert("UTC").dt.tz_localize(None).astype("datetime64[s]")
    return sf.Frame.from_pandas(norm, index_constructor=sf.IndexDate, name="schedule").rename(
        index="session"
    )


@pytest.mark.parametrize("mic", ["XNYS", "XTKS", "XHKG", "XCEC", "XNSE"])
@pytest.mark.parametrize("all_days", [False, True])
def test_the_pandas_and_static_frame_schedules_agree(client: Client, mic: str, all_days: bool) -> None:
    # A year of each recorded venue: holidays (with all_days, rows of NaT),
    # lunch breaks, early closes, product sessions and Muhurat.
    p = diurn.get_calendar(mic, client=client, cache=False).schedule(
        "2026-01-01", "2026-12-31", all_days=all_days
    )
    s = dsf.get_calendar(mic, client=client, cache=False).schedule(
        "2026-01-01", "2026-12-31", all_days=all_days
    )
    converted = _as_static_frame(p)
    # Not the dtypes: the string columns differ only in Unicode width, and the
    # column labels in object against str. The instants' dtypes are checked
    # directly instead, since they are the ones that mean something.
    assert converted.equals(s, compare_dtype=False, compare_class=True, compare_name=True)
    for col in INSTANTS:
        assert converted[col].dtype == s[col].dtype == np.dtype("datetime64[s]")

    # And the comparison can fail: one close a second late is a difference.
    late = p.copy()
    first = late["close"].first_valid_index()
    late.loc[first, "close"] = late.loc[first, "close"] + pd.Timedelta(seconds=1)
    assert not _as_static_frame(late).equals(s, compare_dtype=False)


def test_the_flavors_agree_on_sessions(client: Client) -> None:
    p = diurn.get_calendar("XNSE", client=client, cache=False).sessions_in_range("2026-01-01", "2026-12-31")
    s = dsf.get_calendar("XNSE", client=client, cache=False).sessions_in_range("2026-01-01", "2026-12-31")
    assert sf.IndexDate(p.values.astype("datetime64[D]")).equals(s)


def test_the_static_frame_dtypes_follow_the_record() -> None:
    # `from_records` takes the columns from ScheduleRowUTC's fields and the
    # dtypes by name: the two must name the same columns, in the same order.
    assert tuple(dsf.SCHEDULE_DTYPES) == dsf.SCHEDULE_COLUMNS


def test_an_empty_static_frame_schedule_keeps_its_shape(client: Client) -> None:
    # Culture Day alone: no sessions, so no records, and still every column.
    frame = dsf.get_calendar("XTKS", client=client, cache=False).schedule("2026-11-03", "2026-11-03")
    assert frame.shape == (0, 7)
    assert frame.index.name == "session" and frame.name == "schedule"
    assert frame["open"].dtype == np.dtype("datetime64[s]")
