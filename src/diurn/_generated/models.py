"""Generated from openapi.json by tools/generate.py. Do not edit."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Literal

__all__ = [
    "DayKindDto",
    "OverLimitError",
    "OverLimitLimitKind",
    "StateDto",
    "VerificationDto",
    "ApiError",
    "BreakDto",
    "BulkBody",
    "BulkCalendar",
    "BulkResponse",
    "CountResponse",
    "DataWindow",
    "DatasetServed",
    "DayDto",
    "DayResponse",
    "DaysResponse",
    "ExceptionsBody",
    "ExceptionsResponse",
    "Health",
    "InstantResponse",
    "JointSkipped",
    "JointStepBody",
    "JointStepResponse",
    "Legend",
    "MicWindow",
    "OverLimit",
    "OverLimitAllowed",
    "OverLimitLimit",
    "ProductSplitDto",
    "Provenance",
    "Rate",
    "ResolutionDto",
    "RunningSession",
    "SessionDto",
    "SkippedDay",
    "StatusResponse",
    "StatusesBody",
    "StatusesResponse",
    "StepResponse",
    "TradingDaysResponse",
    "TradingSeries",
    "UsageView",
    "VenueDay",
    "VenueDays",
    "VenueResponse",
    "VenueStatus",
    "VenuesResponse",
]

DayKindDto = Literal["open", "weekend", "holiday", "early_close", "open_for_some", "unknown"]

OverLimitError = Literal["not_in_plan", "out_of_window", "mic_cap_exceeded", "rate_limited"]

OverLimitLimitKind = Literal["mics_day", "mics_month", "rate"]

StateDto = Literal["running", "closed", "unknown"]

VerificationDto = Literal["verified", "corroborated", "inferreddefinitional", "inferredpredictive", "inferredadvisory"]


@dataclass(frozen=True, slots=True)
class ApiError:
    """Typed, because SPEC: client-shared-surface requires every client to
    distinguish auth failure from an unknown calendar from an out-of-range
    query, and it cannot if the server returns prose.
    """

    error: str
    message: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ApiError:
        return cls(
            error=data["error"],
            message=data["message"],
        )


@dataclass(frozen=True, slots=True)
class BreakDto:
    end: str
    start: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BreakDto:
        return cls(
            end=data["end"],
            start=data["start"],
        )


@dataclass(frozen=True, slots=True)
class BulkBody:
    from_: datetime.date
    to: datetime.date
    as_of: str | None = None
    mics: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BulkBody:
        return cls(
            from_=datetime.date.fromisoformat(data["from"]),
            to=datetime.date.fromisoformat(data["to"]),
            as_of=data.get("as_of"),
            mics=() if data.get("mics") is None else tuple(x1 for x1 in data["mics"]),
        )


@dataclass(frozen=True, slots=True)
class BulkCalendar:
    kinds: str
    verification: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BulkCalendar:
        return cls(
            kinds=data["kinds"],
            verification=data["verification"],
        )


@dataclass(frozen=True, slots=True)
class BulkResponse:
    """Column-oriented: the dates once, then one short code per day per calendar."""

    dates: tuple[datetime.date, ...]
    from_: datetime.date
    legend: Legend
    to: datetime.date
    venues: dict[str, BulkCalendar]
    as_of: str | None = None
    dataset: DatasetServed | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> BulkResponse:
        return cls(
            dates=tuple(datetime.date.fromisoformat(x2) for x2 in data["dates"]),
            from_=datetime.date.fromisoformat(data["from"]),
            legend=Legend.from_json(data["legend"]),
            to=datetime.date.fromisoformat(data["to"]),
            venues={k: BulkCalendar.from_json(x3) for k, x3 in data["venues"].items()},
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
        )


@dataclass(frozen=True, slots=True)
class CountResponse:
    count: int
    from_: datetime.date
    mic: str
    to: datetime.date
    unknown: int
    as_of: str | None = None
    dataset: DatasetServed | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CountResponse:
        return cls(
            count=data["count"],
            from_=datetime.date.fromisoformat(data["from"]),
            mic=data["mic"],
            to=datetime.date.fromisoformat(data["to"]),
            unknown=data["unknown"],
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
        )


@dataclass(frozen=True, slots=True)
class DataWindow:
    """The dates the plan may ask about, from today (UTC). Null is unbounded."""

    from_: datetime.date | None = None
    to: datetime.date | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> DataWindow:
        return cls(
            from_=None if data.get("from") is None else datetime.date.fromisoformat(data["from"]),
            to=None if data.get("to") is None else datetime.date.fromisoformat(data["to"]),
        )


@dataclass(frozen=True, slots=True)
class DatasetServed:
    """The dataset that answered an `as_of` request (SPEC-pricing §5.1)."""

    id: str
    reconstructed: bool
    served_from: str
    served_until: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> DatasetServed:
        return cls(
            id=data["id"],
            reconstructed=data["reconstructed"],
            served_from=data["served_from"],
            served_until=data.get("served_until"),
        )


@dataclass(frozen=True, slots=True)
class DayDto:
    date: datetime.date
    kind: DayKindDto
    verification: VerificationDto
    products: ProductSplitDto | None = None
    provenance: Provenance | None = None
    reason: str | None = None
    sessions: tuple[SessionDto, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> DayDto:
        return cls(
            date=datetime.date.fromisoformat(data["date"]),
            kind=data["kind"],
            verification=data["verification"],
            products=None if data.get("products") is None else ProductSplitDto.from_json(data["products"]),
            provenance=None if data.get("provenance") is None else Provenance.from_json(data["provenance"]),
            reason=data.get("reason"),
            sessions=() if data.get("sessions") is None else tuple(SessionDto.from_json(x4) for x4 in data["sessions"]),
        )


@dataclass(frozen=True, slots=True)
class DayResponse:
    """One day, and with `as_of`, which dataset answered."""

    date: datetime.date
    kind: DayKindDto
    verification: VerificationDto
    products: ProductSplitDto | None = None
    provenance: Provenance | None = None
    reason: str | None = None
    sessions: tuple[SessionDto, ...] = ()
    as_of: str | None = None
    dataset: DatasetServed | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> DayResponse:
        return cls(
            date=datetime.date.fromisoformat(data["date"]),
            kind=data["kind"],
            verification=data["verification"],
            products=None if data.get("products") is None else ProductSplitDto.from_json(data["products"]),
            provenance=None if data.get("provenance") is None else Provenance.from_json(data["provenance"]),
            reason=data.get("reason"),
            sessions=() if data.get("sessions") is None else tuple(SessionDto.from_json(x5) for x5 in data["sessions"]),
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
        )


@dataclass(frozen=True, slots=True)
class DaysResponse:
    days: tuple[DayDto, ...]
    as_of: str | None = None
    dataset: DatasetServed | None = None
    mic: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> DaysResponse:
        return cls(
            days=tuple(DayDto.from_json(x6) for x6 in data["days"]),
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
            mic=data.get("mic"),
        )


@dataclass(frozen=True, slots=True)
class ExceptionsBody:
    from_: datetime.date
    to: datetime.date
    as_of: str | None = None
    kinds: tuple[str, ...] = ()
    mics: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ExceptionsBody:
        return cls(
            from_=datetime.date.fromisoformat(data["from"]),
            to=datetime.date.fromisoformat(data["to"]),
            as_of=data.get("as_of"),
            kinds=() if data.get("kinds") is None else tuple(x7 for x7 in data["kinds"]),
            mics=() if data.get("mics") is None else tuple(x8 for x8 in data["mics"]),
        )


@dataclass(frozen=True, slots=True)
class ExceptionsResponse:
    days: tuple[VenueDay, ...]
    from_: datetime.date
    to: datetime.date
    as_of: str | None = None
    dataset: DatasetServed | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ExceptionsResponse:
        return cls(
            days=tuple(VenueDay.from_json(x9) for x9 in data["days"]),
            from_=datetime.date.fromisoformat(data["from"]),
            to=datetime.date.fromisoformat(data["to"]),
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
        )


@dataclass(frozen=True, slots=True)
class Health:
    artifact: str
    built_at: str
    dataset: str
    mapped_venues: int
    registry_published: datetime.date
    status: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Health:
        return cls(
            artifact=data["artifact"],
            built_at=data["built_at"],
            dataset=data["dataset"],
            mapped_venues=data["mapped_venues"],
            registry_published=datetime.date.fromisoformat(data["registry_published"]),
            status=data["status"],
        )


@dataclass(frozen=True, slots=True)
class InstantResponse:
    from_: str
    as_of: str | None = None
    at: str | None = None
    dataset: DatasetServed | None = None
    mic: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> InstantResponse:
        return cls(
            from_=data["from"],
            as_of=data.get("as_of"),
            at=data.get("at"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
            mic=data.get("mic"),
        )


@dataclass(frozen=True, slots=True)
class JointSkipped:
    """A date passed over: the venues that did not trade it, other than for a
    weekend.
    """

    closed: dict[str, SkippedDay]
    date: datetime.date

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> JointSkipped:
        return cls(
            closed={k: SkippedDay.from_json(x10) for k, x10 in data["closed"].items()},
            date=datetime.date.fromisoformat(data["date"]),
        )


@dataclass(frozen=True, slots=True)
class JointStepBody:
    from_: datetime.date
    as_of: str | None = None
    inclusive: bool | None = None
    mics: tuple[str, ...] = ()
    mode: str | None = None
    n: int | None = None
    on_unknown: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> JointStepBody:
        return cls(
            from_=datetime.date.fromisoformat(data["from"]),
            as_of=data.get("as_of"),
            inclusive=data.get("inclusive"),
            mics=() if data.get("mics") is None else tuple(x11 for x11 in data["mics"]),
            mode=data.get("mode"),
            n=data.get("n"),
            on_unknown=data.get("on_unknown"),
        )


@dataclass(frozen=True, slots=True)
class JointStepResponse:
    date: datetime.date
    from_: datetime.date
    mics: tuple[str, ...]
    mode: str
    n: int
    skipped: tuple[JointSkipped, ...]
    venues: dict[str, DayKindDto]
    as_of: str | None = None
    dataset: DatasetServed | None = None
    unknown_skipped: tuple[datetime.date, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> JointStepResponse:
        return cls(
            date=datetime.date.fromisoformat(data["date"]),
            from_=datetime.date.fromisoformat(data["from"]),
            mics=tuple(x12 for x12 in data["mics"]),
            mode=data["mode"],
            n=data["n"],
            skipped=tuple(JointSkipped.from_json(x13) for x13 in data["skipped"]),
            venues={k: x15 for k, x15 in data["venues"].items()},
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
            unknown_skipped=() if data.get("unknown_skipped") is None else tuple(datetime.date.fromisoformat(x14) for x14 in data["unknown_skipped"]),
        )


@dataclass(frozen=True, slots=True)
class Legend:
    kinds: dict[str, str]
    verification: dict[str, str]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Legend:
        return cls(
            kinds={k: x16 for k, x16 in data["kinds"].items()},
            verification={k: x17 for k, x17 in data["verification"].items()},
        )


@dataclass(frozen=True, slots=True)
class MicWindow:
    """One MIC cap's count (SPEC-pricing §6.4). `max` is null on a plan with
    every MIC.
    """

    used: int
    window: str
    max: int | None = None
    mics: tuple[str, ...] | None = None
    resets_at: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> MicWindow:
        return cls(
            used=data["used"],
            window=data["window"],
            max=data.get("max"),
            mics=None if data.get("mics") is None else tuple(x18 for x18 in data["mics"]),
            resets_at=data.get("resets_at"),
        )


@dataclass(frozen=True, slots=True)
class OverLimit:
    error: OverLimitError
    message: str
    allowed: OverLimitAllowed | None = None
    limit: OverLimitLimit | None = None
    mics_in_use: tuple[str, ...] = ()
    resets_at: str | None = None
    upgrade: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> OverLimit:
        return cls(
            error=data["error"],
            message=data["message"],
            allowed=None if data.get("allowed") is None else OverLimitAllowed.from_json(data["allowed"]),
            limit=None if data.get("limit") is None else OverLimitLimit.from_json(data["limit"]),
            mics_in_use=() if data.get("mics_in_use") is None else tuple(x19 for x19 in data["mics_in_use"]),
            resets_at=data.get("resets_at"),
            upgrade=data.get("upgrade"),
        )


@dataclass(frozen=True, slots=True)
class OverLimitAllowed:
    """For `out_of_window`: the dates the plan may ask about; null is unbounded"""

    from_: datetime.date | None = None
    to: datetime.date | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> OverLimitAllowed:
        return cls(
            from_=None if data.get("from") is None else datetime.date.fromisoformat(data["from"]),
            to=None if data.get("to") is None else datetime.date.fromisoformat(data["to"]),
        )


@dataclass(frozen=True, slots=True)
class OverLimitLimit:
    kind: OverLimitLimitKind | None = None
    max: int | None = None
    used: int | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> OverLimitLimit:
        return cls(
            kind=data.get("kind"),
            max=data.get("max"),
            used=data.get("used"),
        )


@dataclass(frozen=True, slots=True)
class ProductSplitDto:
    """Which products traded on a day that did not treat them alike."""

    closed: tuple[str, ...] = ()
    note: str | None = None
    open: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ProductSplitDto:
        return cls(
            closed=() if data.get("closed") is None else tuple(x20 for x20 in data["closed"]),
            note=data.get("note"),
            open=() if data.get("open") is None else tuple(x21 for x21 in data["open"]),
        )


@dataclass(frozen=True, slots=True)
class Provenance:
    """The evidence behind a day. Only ever sent when asked for."""

    retrieved: datetime.date | None = None
    source: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Provenance:
        return cls(
            retrieved=None if data.get("retrieved") is None else datetime.date.fromisoformat(data["retrieved"]),
            source=data.get("source"),
        )


@dataclass(frozen=True, slots=True)
class Rate:
    bulk_per_minute: int
    per_minute: int

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Rate:
        return cls(
            bulk_per_minute=data["bulk_per_minute"],
            per_minute=data["per_minute"],
        )


@dataclass(frozen=True, slots=True)
class ResolutionDto:
    """How a MIC reaches its answer (SPEC: calendar-membership). The MIC pages
    state the same.
    """

    kind: str
    via: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ResolutionDto:
        return cls(
            kind=data["kind"],
            via=data["via"],
        )


@dataclass(frozen=True, slots=True)
class RunningSession:
    close: str
    name: str
    open: str
    trade_date: datetime.date
    verification: VerificationDto
    products: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> RunningSession:
        return cls(
            close=data["close"],
            name=data["name"],
            open=data["open"],
            trade_date=datetime.date.fromisoformat(data["trade_date"]),
            verification=data["verification"],
            products=data.get("products"),
        )


@dataclass(frozen=True, slots=True)
class SessionDto:
    close: str
    name: str
    open: str
    verification: VerificationDto
    breaks: tuple[BreakDto, ...] = ()
    products: str | None = None
    provenance: Provenance | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> SessionDto:
        return cls(
            close=data["close"],
            name=data["name"],
            open=data["open"],
            verification=data["verification"],
            breaks=() if data.get("breaks") is None else tuple(BreakDto.from_json(x22) for x22 in data["breaks"]),
            products=data.get("products"),
            provenance=None if data.get("provenance") is None else Provenance.from_json(data["provenance"]),
        )


@dataclass(frozen=True, slots=True)
class SkippedDay:
    """A day stepped over: not a weekend, and not trading."""

    date: datetime.date
    kind: DayKindDto
    reason: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> SkippedDay:
        return cls(
            date=datetime.date.fromisoformat(data["date"]),
            kind=data["kind"],
            reason=data.get("reason"),
        )


@dataclass(frozen=True, slots=True)
class StatusResponse:
    at: str
    day: DayDto
    state: StateDto
    as_of: str | None = None
    dataset: DatasetServed | None = None
    mic: str | None = None
    next_close: str | None = None
    next_open: str | None = None
    running: RunningSession | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> StatusResponse:
        return cls(
            at=data["at"],
            day=DayDto.from_json(data["day"]),
            state=data["state"],
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
            mic=data.get("mic"),
            next_close=data.get("next_close"),
            next_open=data.get("next_open"),
            running=None if data.get("running") is None else RunningSession.from_json(data["running"]),
        )


@dataclass(frozen=True, slots=True)
class StatusesBody:
    as_of: str | None = None
    at: str | None = None
    mics: tuple[str, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> StatusesBody:
        return cls(
            as_of=data.get("as_of"),
            at=data.get("at"),
            mics=() if data.get("mics") is None else tuple(x23 for x23 in data["mics"]),
        )


@dataclass(frozen=True, slots=True)
class StatusesResponse:
    at: str
    venues: dict[str, VenueStatus]
    as_of: str | None = None
    dataset: DatasetServed | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> StatusesResponse:
        return cls(
            at=data["at"],
            venues={k: VenueStatus.from_json(x24) for k, x24 in data["venues"].items()},
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
        )


@dataclass(frozen=True, slots=True)
class StepResponse:
    date: datetime.date
    from_: datetime.date
    kind: DayKindDto
    mic: str
    n: int
    skipped: tuple[SkippedDay, ...]
    as_of: str | None = None
    dataset: DatasetServed | None = None
    unknown_skipped: tuple[datetime.date, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> StepResponse:
        return cls(
            date=datetime.date.fromisoformat(data["date"]),
            from_=datetime.date.fromisoformat(data["from"]),
            kind=data["kind"],
            mic=data["mic"],
            n=data["n"],
            skipped=tuple(SkippedDay.from_json(x25) for x25 in data["skipped"]),
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
            unknown_skipped=() if data.get("unknown_skipped") is None else tuple(datetime.date.fromisoformat(x26) for x26 in data["unknown_skipped"]),
        )


@dataclass(frozen=True, slots=True)
class TradingDaysResponse:
    """A date and whether the venue trades on it, and nothing else."""

    dates: tuple[datetime.date, ...]
    from_: datetime.date
    to: datetime.date
    venues: dict[str, TradingSeries]
    as_of: str | None = None
    dataset: DatasetServed | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> TradingDaysResponse:
        return cls(
            dates=tuple(datetime.date.fromisoformat(x27) for x27 in data["dates"]),
            from_=datetime.date.fromisoformat(data["from"]),
            to=datetime.date.fromisoformat(data["to"]),
            venues={k: TradingSeries.from_json(x28) for k, x28 in data["venues"].items()},
            as_of=data.get("as_of"),
            dataset=None if data.get("dataset") is None else DatasetServed.from_json(data["dataset"]),
        )


@dataclass(frozen=True, slots=True)
class TradingSeries:
    trading: tuple[bool | None, ...]
    unknown: int

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> TradingSeries:
        return cls(
            trading=tuple(x29 for x29 in data["trading"]),
            unknown=data["unknown"],
        )


@dataclass(frozen=True, slots=True)
class UsageView:
    """An account's usage against its plan (SPEC-pricing §6.4): what
    `GET /v1/usage` answers, and what the account page shows.
    """

    horizon: DataWindow
    mics_day: MicWindow
    mics_month: MicWindow
    plan: str
    rate: Rate
    venue_days: VenueDays | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> UsageView:
        return cls(
            horizon=DataWindow.from_json(data["horizon"]),
            mics_day=MicWindow.from_json(data["mics_day"]),
            mics_month=MicWindow.from_json(data["mics_month"]),
            plan=data["plan"],
            rate=Rate.from_json(data["rate"]),
            venue_days=None if data.get("venue_days") is None else VenueDays.from_json(data["venue_days"]),
        )


@dataclass(frozen=True, slots=True)
class VenueDay:
    """One venue's day, in a row-oriented list."""

    date: datetime.date
    kind: DayKindDto
    verification: VerificationDto
    mic: str
    products: ProductSplitDto | None = None
    provenance: Provenance | None = None
    reason: str | None = None
    sessions: tuple[SessionDto, ...] = ()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> VenueDay:
        return cls(
            date=datetime.date.fromisoformat(data["date"]),
            kind=data["kind"],
            verification=data["verification"],
            mic=data["mic"],
            products=None if data.get("products") is None else ProductSplitDto.from_json(data["products"]),
            provenance=None if data.get("provenance") is None else Provenance.from_json(data["provenance"]),
            reason=data.get("reason"),
            sessions=() if data.get("sessions") is None else tuple(SessionDto.from_json(x30) for x30 in data["sessions"]),
        )


@dataclass(frozen=True, slots=True)
class VenueDays:
    max: int
    used: int
    resets_at: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> VenueDays:
        return cls(
            max=data["max"],
            used=data["used"],
            resets_at=data.get("resets_at"),
        )


@dataclass(frozen=True, slots=True)
class VenueResponse:
    mic: str
    name: str
    operating_mic: str
    products: tuple[str, ...]
    status: str
    country: str | None = None
    resolution: ResolutionDto | None = None
    timezone: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> VenueResponse:
        return cls(
            mic=data["mic"],
            name=data["name"],
            operating_mic=data["operating_mic"],
            products=tuple(x31 for x31 in data["products"]),
            status=data["status"],
            country=data.get("country"),
            resolution=None if data.get("resolution") is None else ResolutionDto.from_json(data["resolution"]),
            timezone=data.get("timezone"),
        )


@dataclass(frozen=True, slots=True)
class VenueStatus:
    """One venue's entry: `StatusResponse` without the `at` the response states
    once.
    """

    day: DayDto
    state: StateDto
    next_close: str | None = None
    next_open: str | None = None
    running: RunningSession | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> VenueStatus:
        return cls(
            day=DayDto.from_json(data["day"]),
            state=data["state"],
            next_close=data.get("next_close"),
            next_open=data.get("next_open"),
            running=None if data.get("running") is None else RunningSession.from_json(data["running"]),
        )


@dataclass(frozen=True, slots=True)
class VenuesResponse:
    venues: tuple[VenueResponse, ...]
    next_cursor: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> VenuesResponse:
        return cls(
            venues=tuple(VenueResponse.from_json(x32) for x32 in data["venues"]),
            next_cursor=data.get("next_cursor"),
        )
