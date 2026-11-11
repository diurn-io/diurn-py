"""Offline tests: a fake transport replays responses recorded from the API
(tools/record_fixtures.py), so nothing here needs a network or a key."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from record_fixtures import name  # noqa: E402

from diurn._transport import Response  # noqa: E402
from diurn.client import Client  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


class FakeSend:
    """Answers from tests/fixtures/, or from `overrides` (path -> (status, body)).
    Records every request, so tests can count what reached the network."""

    def __init__(self, overrides: Mapping[str, tuple[int, Any]] | None = None):
        self.overrides = dict(overrides or {})
        self.requests: list[str] = []

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
    ) -> Response:
        path = url.split("://", 1)[1].split("/", 1)[1]
        path = "/" + path
        self.requests.append(path)
        if path in self.overrides:
            status, payload = self.overrides[path]
            return Response(status, {}, json.dumps(payload).encode())
        if path == "/v1/usage":
            return Response(404, {}, b'{"error":"not_metered","message":"no key store"}')
        file = FIXTURES / name(path)
        if file.exists():
            return Response(200, {}, file.read_bytes())
        part = self.range_of_a_recorded_year(path)
        if part is not None:
            return Response(200, {}, json.dumps(part).encode())
        return Response(404, {}, json.dumps({"error": "not_found", "message": path}).encode())

    @staticmethod
    def range_of_a_recorded_year(path: str) -> Any:
        """A sessions range inside one recorded year, cut from that year."""
        if "/sessions?" not in path:
            return None
        prefix, query = path.split("?", 1)
        params = dict(p.split("=", 1) for p in query.split("&"))
        start, end = params.get("from", ""), params.get("to", "")
        year = start[:4]
        file = FIXTURES / name(f"{prefix}?from={year}-01-01&to={year}-12-31")
        if not file.exists() or end[:4] != year:
            return None
        whole = json.loads(file.read_text())
        return {**whole, "days": [d for d in whole["days"] if start <= d["date"] <= end]}


@pytest.fixture
def send() -> FakeSend:
    return FakeSend()


@pytest.fixture
def client(send: FakeSend) -> Client:
    return Client(api_key="diurn_key_test", base_url="https://api.test", send=send)
