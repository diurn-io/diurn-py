"""HTTP on the standard library: `urllib`, JSON, and the API's errors.

The sending function is swappable (`Transport(send=...)`), which is how the
tests run without a network and how a caller could put their own HTTP stack
underneath.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from . import errors
from ._version import __version__

__all__ = ["DEFAULT_URL", "Response", "Send", "Transport"]

DEFAULT_URL = "https://api.diurn.io"
USER_AGENT = f"diurn-py/{__version__}"


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]  # lower-cased names
    body: bytes


# (method, url, headers, body, timeout) -> Response
Send = Callable[[str, str, Mapping[str, str], bytes | None, float], Response]


def urllib_send(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
) -> Response:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            return Response(r.status, {k.lower(): v for k, v in r.headers.items()}, r.read())
    except urllib.error.HTTPError as e:
        return Response(e.code, {k.lower(): v for k, v in e.headers.items()}, e.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise errors.TransportError(f"{method} {url}: {e}") from e


class Transport:
    """Sends requests to the API and turns its answers into JSON or errors."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        send: Send | None = None,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("DIURN_API_KEY")
        self.base_url = (base_url or os.environ.get("DIURN_API_URL") or DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        self.send = send or urllib_send
        self.last_headers: Mapping[str, str] = {}

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode({k: _param(v) for k, v in (params or {}).items() if v is not None})
        return self.request("GET", path + (f"?{query}" if query else ""), None)

    def post(self, path: str, body: Mapping[str, Any]) -> Any:
        data = json.dumps({k: _body(v) for k, v in body.items() if v is not None}).encode()
        return self.request("POST", path, data)

    def request(self, method: str, path_and_query: str, body: bytes | None) -> Any:
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = self.base_url + path_and_query
        r = self.send(method, url, headers, body, self.timeout)
        self.last_headers = r.headers
        parsed = _json(r.body)
        if 200 <= r.status < 300:
            if parsed is _NOT_JSON:
                raise errors.TransportError(f"{method} {url}: answered {r.status} without JSON")
            return parsed
        if parsed is _NOT_JSON or not isinstance(parsed, dict):
            if r.status >= 500:
                raise errors.TransportError(f"{method} {url}: answered {r.status}")
            parsed = {}
        raise errors.from_response(r.status, parsed, _retry_after(r.headers))


_NOT_JSON = object()


def _json(body: bytes) -> Any:
    try:
        return json.loads(body) if body else _NOT_JSON
    except ValueError:
        return _NOT_JSON


def _retry_after(headers: Mapping[str, str]) -> float | None:
    value = headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _param(value: Any) -> Any:
    """Query and body values as the API spells them."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    isoformat = getattr(value, "isoformat", None)
    if isoformat is not None:
        return isoformat()
    return value


def _body(value: Any) -> Any:
    """JSON body values: arrays and booleans stay themselves; dates and
    instants become ISO strings."""
    if isinstance(value, (list, tuple)):
        return [_body(v) for v in value]
    if isinstance(value, (bool, int, float, str)):
        return value
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if isoformat is not None else value
