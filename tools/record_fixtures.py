"""Record the API responses the offline tests replay (tests/fixtures/).

Point it at a local server (`cargo run -p diurn-api -- --bind 127.0.0.1:8099`
in diurn-platform, which needs no key) and rerun when the data or the wire
format changes:

    python tools/record_fixtures.py http://127.0.0.1:8099
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures"

REQUESTS = [
    "/health",
    "/v1/venues/XNYS",
    "/v1/venues/XTKS",
    "/v1/venues/XHKG",
    "/v1/venues/XNYS/sessions?from=2026-01-01&to=2026-12-31",
    "/v1/venues/XNYS/sessions?from=2027-01-01&to=2027-12-31",
    "/v1/venues/XTKS/sessions?from=2026-01-01&to=2026-12-31",
    "/v1/venues/XHKG/sessions?from=2026-01-01&to=2026-12-31",
]


def name(path: str) -> str:
    """The fixture file for a request path; the tests' fake transport uses it too."""
    return path.strip("/").replace("/", "_").replace("?", "__").replace("&", "_").replace("=", "-") + ".json"


def main() -> int:
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8099"
    OUT.mkdir(parents=True, exist_ok=True)
    for path in REQUESTS:
        with urllib.request.urlopen(base + path, timeout=30) as r:
            body = json.load(r)
        (OUT / name(path)).write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
        print("recorded", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
