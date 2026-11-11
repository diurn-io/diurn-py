# diurn

Exchange calendars and trading hours for the world's markets, from the
[Diurn API](https://diurn.io), with an
[`exchange_calendars`](https://github.com/gerrymanoim/exchange_calendars)-style
interface.

```sh
pip install diurn            # the client and diurn.py: standard library only
pip install 'diurn[pd]'      # the pandas flavor, also diurn.get_calendar
pip install 'diurn[sf]'      # the StaticFrame flavor
```

Nothing imports Pandas, StaticFrame, or NumPy until its flavor is used.

A key is free at <https://diurn.io/signin/>; set `DIURN_API_KEY`.

```python
import diurn

xnys = diurn.get_calendar("XNYS")
xnys.is_session("2026-11-26")  # False: Thanksgiving
xnys.next_session("2026-11-25")  # Timestamp('2026-11-27 00:00:00')
xnys.sessions_in_range("2026-11-01", "2026-11-30")  # DatetimeIndex
xnys.is_open_at_time("2026-11-27T18:30:00Z")  # False: an early close at 13:00
xnys.next_close("2026-11-27T15:00:00Z")  # Timestamp('2026-11-27 13:00:00-0500', tz='America/New_York')
xnys.schedule("2026-11-01", "2026-11-30")  # open, break_start, break_end, close, kind, verification, reason
```

## Three flavors, one calendar

The same calendar, with the same methods, in three sets of types:

| | session | range of sessions | `schedule` | instants |
|---|---|---|---|---|
| `diurn` / `diurn.pd` (`diurn[pd]`) | `pd.Timestamp` | `pd.DatetimeIndex` | `pd.DataFrame` | aware `pd.Timestamp`, venue's zone |
| `diurn.sf` (`diurn[sf]`) | `np.datetime64[D]` | `sf.IndexDate` | `sf.Frame` | `np.datetime64[s]`, UTC |
| `diurn.py` | `datetime.date` | `list[date]` | `list[ScheduleRow]` | aware `datetime`, venue's zone |

```python
import diurn.sf as dsf

dsf.get_calendar("XTKS").schedule("2026-11-02", "2026-11-06")  # sf.Frame

import diurn.py as dpy

dpy.get_calendar("XHKG").next_session("2026-12-24")  # datetime.date(2026, 12, 28)
```

Every method accepts dates as `datetime.date`, ISO strings, pandas Timestamps
or NumPy datetime64, and instants as aware `datetime`s, aware Timestamps, or
ISO strings with an offset. A naive datetime is refused: it is not an instant.

## The interface

`is_session`, `sessions_in_range`, `next_session`, `previous_session`,
`date_to_session(direction=)`, `sessions_window`, `next_open`, `next_close`,
`is_open_at_time` and `schedule`, as in `exchange_calendars`, with these
differences:

- **A session is a day the venue trades,** as the API's `/v1/trading-days`
  counts one: `open`, `early_close`, `open_for_some`, and a `holiday` that
  carries a session, such as NSE's Muhurat.
- **`unknown` is neither open nor closed.** Past what Diurn can answer, a
  method that depends on such a day raises `diurn.Indeterminate`. Pass
  `on_unknown="missing"` to get `None` (or `NaT`) instead; ranges then leave
  the day out.
- **Instants keep the venue's zone**, in the Pandas and plain flavors. They
  compare equal to UTC ones.
- **`schedule(start, end)` is a method over a range**, since the calendar is
  answered by an API rather than precomputed. It adds `kind`, `verification`
  and `reason`; `all_days=True` keeps holidays and unknown days as rows.
- **`next_session` and `previous_session` take any date**, not only a session.
- **Product schedules.** Where a venue keeps several (`calendar.products`),
  `get_calendar(mic, product=...)` picks one; by default the whole venue's
  sessions are used. A product with no hours of its own has none: it is never
  given another product's.
- **`name` is the MIC**, as `exchange_calendars` names a calendar by its code;
  the registry's name is `market_name`. **`tz` is the IANA name**, a string,
  where `exchange_calendars` has a `ZoneInfo`.

## The API itself

`diurn.Client` has one method per API operation and returns typed models:
venue search, multi-venue status, exceptions, trading-day arithmetic, usage.

```python
client = diurn.Client()  # DIURN_API_KEY, DIURN_API_URL
client.statuses(["XNYS", "XLON", "XTKS"])  # whether each is trading now
client.usage()  # your plan's meters
```

## Errors

Typed, never prose: `AuthError` (no or inactive key), `UnknownVenue`,
`OutOfWindow` (with `allowed_from` and `allowed_to`), `NotInPlan`,
`MicCapExceeded` (with `mics_in_use` and `resets_at`), `RateLimited` (with
`retry_after`), `Indeterminate` and `TransportError`, all under
`diurn.DiurnError`. Every plan refusal is an `OverLimit` with `limit` and
`resets_at`. `Indeterminate` is raised the same whether the calendar met an
unknown day or the API did (its `422`, as `IndeterminateResponse`, also an
`ApiError`); a stepping method that finds no session within 800 days raises
it too.

## Caching

Responses are cached on disk by MIC, range and the dataset the server serves.
The dataset is checked against the free `/health` endpoint every few minutes,
so a cached answer is reused exactly as long as it is still the answer, and a
repeat query makes no metered request. The directory is `DIURN_CACHE_DIR`, or
the platform's own cache directory: `~/Library/Caches/diurn` on macOS,
`%LOCALAPPDATA%\diurn\Cache` on Windows, and `$XDG_CACHE_HOME/diurn` or
`~/.cache/diurn` elsewhere (`XDG_CACHE_HOME` is honoured on any platform where
it is set). `get_calendar(..., cache=False)` turns it off.

## Development

Python 3.12 or later; nothing beyond the standard library is required to build.

```sh
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m mypy
.venv/bin/python -m ruff check .
```

The wire layer (`src/diurn/_generated/`) is generated from the API's OpenAPI
document and committed. To refresh it, from a checkout of `diurn-platform`:

```sh
cargo run -p diurn-api -- --openapi > ../diurn-py/openapi.json
python tools/generate.py           # CI runs it with --check
```

The tests replay responses recorded from a local API server
(`python tools/record_fixtures.py http://127.0.0.1:8099`), so they need no
network or key.

## License

MIT or Apache-2.0, at your option.
