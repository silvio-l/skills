#!/usr/bin/env python3
"""Shared HTTP response cache for aso-research.

Establishes the cache contract that resumability (slice 06) builds on:
every network collector consults this cache before going live, and
writes the raw response back so a second run within TTL makes no
duplicate live call.

Layout: ``<cache_dir>/<sha256>.json`` — one file per canonical
(method, url, params) tuple, holding the raw response bytes. Freshness
is mtime-based against a caller-injected ``now`` so tests are
deterministic (set a file's mtime with ``os.utime`` and assert).

HTTP TTL is 24h (PRD "File layout, cache, resumability").
"""

from __future__ import annotations

import hashlib
import os
import urllib.parse
from typing import Dict, Mapping, Optional

DEFAULT_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "aso-research")
HTTP_TTL = 24 * 60 * 60  # 24 hours, in seconds


def _canonical_query(params: Mapping[str, object]) -> str:
    """Stable query string: sorted keys, explicitly-encoded values."""
    items = sorted((str(k), str(v)) for k, v in params.items())
    return urllib.parse.urlencode(items)


def cache_key(method: str, url: str, params: Optional[Mapping[str, object]] = None) -> str:
    """Derive a stable SHA-256 cache key for a request."""
    canonical = method.upper() + "\n" + url + "\n" + _canonical_query(params or {})
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_path(cache_dir: str, key: str) -> str:
    return os.path.join(cache_dir, key + ".json")


def is_fresh(path: str, ttl: float, now: float) -> bool:
    """True when ``path`` exists and its mtime is within ``ttl`` of ``now``."""
    if not path or not os.path.isfile(path):
        return False
    age = now - os.path.getmtime(path)
    return age >= 0 and age < ttl


def read_cache(path: str) -> Optional[bytes]:
    """Return cached raw bytes, or ``None`` when the entry is absent."""
    if not path or not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()


def write_cache(path: str, payload: bytes, *, now: Optional[float] = None) -> None:
    """Persist raw bytes to ``path`` and (optionally) stamp a known mtime."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(payload)
    os.replace(tmp, path)
    if now is not None:
        os.utime(path, (now, now))


def cache_stats() -> Dict[str, int]:
    """Cheap diagnostic: how many entries the cache currently holds."""
    if not os.path.isdir(DEFAULT_CACHE_DIR):
        return {"entries": 0}
    return {"entries": len([f for f in os.listdir(DEFAULT_CACHE_DIR) if f.endswith(".json")])}
