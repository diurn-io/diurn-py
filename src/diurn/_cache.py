"""Responses cached on disk by (API, MIC, range, dataset id).

An answer is a pure function of the dataset the server serves, so a cached
answer is good for exactly as long as the server serves the same dataset. The
dataset's id comes from `/health`, which is free and unmetered, checked at most
once per `check_every` seconds; when it changes, every answer from the old one
is dropped. This needs no changes feed: the feed (SPEC-api-additions §7) would
only let a client keep the answers a new dataset did not change.

The directory is `DIURN_CACHE_DIR`, else `$XDG_CACHE_HOME/diurn`, else
`~/.cache/diurn`. Pass `cache=False` to a calendar to bypass it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import errors

__all__ = ["DiskCache", "default_dir"]


def default_dir() -> Path:
    explicit = os.environ.get("DIURN_CACHE_DIR")
    if explicit:
        return Path(explicit)
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "diurn"


class DiskCache:
    def __init__(
        self,
        base_url: str,
        dataset: Callable[[], str | None],
        directory: Path | None = None,
        check_every: float = 300.0,
    ):
        site = hashlib.sha256(base_url.encode()).hexdigest()[:12]
        self.root = (directory or default_dir()) / site
        self._dataset = dataset
        self.check_every = check_every
        self._id: str | None = None
        self._checked = 0.0

    def dataset_id(self) -> str | None:
        """The served dataset, rechecked at most every `check_every` seconds.
        None when it cannot be learned, which turns caching off."""
        now = time.monotonic()
        if self._id is None or now - self._checked > self.check_every:
            try:
                current = self._dataset()
            except errors.DiurnError:
                current = None
            if current and current != self._id:
                self._prune(keep=current)
            self._id, self._checked = current, now
        return self._id

    def get_or_fetch(self, key: str, fetch: Callable[[], Any]) -> Any:
        dataset = self.dataset_id()
        if dataset is None:
            return fetch()
        path = self.root / dataset / f"{hashlib.sha256(key.encode()).hexdigest()}.json"
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            pass
        value = fetch()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(value))
            tmp.replace(path)
        except OSError:
            pass  # an unwritable cache costs a request, never an answer
        return value

    def _prune(self, keep: str) -> None:
        """Drop the answers of datasets no longer served."""
        if not self.root.is_dir():
            return
        for child in self.root.iterdir():
            if child.is_dir() and child.name != keep:
                shutil.rmtree(child, ignore_errors=True)
