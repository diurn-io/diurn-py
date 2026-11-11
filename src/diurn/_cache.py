"""Responses cached on disk by (API, MIC, range, dataset id).

An answer is a pure function of the dataset the server serves, so a cached
answer is good for exactly as long as the server serves the same dataset. The
dataset's id comes from `/health`, which is free and unmetered, checked at most
once per `check_every` seconds; when it changes, every answer from the old one
is dropped. This needs no changes feed: the feed (SPEC-api-additions §7) would
only let a client keep the answers a new dataset did not change.

The directory is `DIURN_CACHE_DIR`; else `$XDG_CACHE_HOME/diurn`, on any
platform, when that is set; else the platform's own place for caches:
`~/Library/Caches/diurn` on macOS, `%LOCALAPPDATA%\\diurn\\Cache` on Windows,
and `~/.cache/diurn` elsewhere. Pass `cache=False` to a calendar to bypass it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from . import errors

__all__ = ['DiskCache', 'default_dir']


def default_dir(
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Where the cache lives. The arguments default to this process's
    platform, environment and home, and exist so every platform's answer can
    be tested on one."""
    platform = sys.platform if platform is None else platform
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else home
    explicit = env.get('DIURN_CACHE_DIR')
    if explicit:
        return Path(explicit)
    # Set by the user, so honoured wherever it is set, as uv and others do.
    xdg = env.get('XDG_CACHE_HOME')
    if xdg:
        return Path(xdg) / 'diurn'
    if platform == 'darwin':
        # Where macOS expects caches: skipped by Time Machine, and cleared by
        # the tools that reclaim space.
        return home / 'Library' / 'Caches' / 'diurn'
    if platform == 'win32':
        # Local, not roaming: a cache should not follow a profile around.
        local = env.get('LOCALAPPDATA')
        base = Path(local) if local else home / 'AppData' / 'Local'
        return base / 'diurn' / 'Cache'
    return home / '.cache' / 'diurn'


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
        path = self.root / dataset / f'{hashlib.sha256(key.encode()).hexdigest()}.json'
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            pass
        value = fetch()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # A temporary file of its own, so processes sharing the cache
            # cannot write into one another's before the rename.
            with tempfile.NamedTemporaryFile('w', dir=path.parent, suffix='.tmp', delete=False) as tmp:
                tmp.write(json.dumps(value))
            Path(tmp.name).replace(path)
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
