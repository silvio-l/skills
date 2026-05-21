#!/usr/bin/env python3
"""External-probes orchestrator.

Runs all configured adapters in parallel against the given URL list,
collects Finding-shaped dicts, and folds them into the synthesis
pipeline. A failure in one adapter does not affect the others.

`--quick` (passed through from `audit.py`) skips the heavy adapters
(Lighthouse and pa11y) so a fast iteration loop is still useful.
"""

from __future__ import annotations

import concurrent.futures
import sys
from typing import Callable, Dict, Iterable, List, Optional

from . import (
    lighthouse_adapter,
    pa11y_adapter,
    w3c_adapter,
    schema_adapter,
    observatory_adapter,
    gsc_adapter,
    pagespeed_adapter,
)

# Adapter signature: `adapter(url: str) -> list[Finding-dict]`.
DEFAULT_ADAPTERS: Dict[str, Callable] = {
    "lighthouse":  lighthouse_adapter.run,
    "pa11y":       pa11y_adapter.run,
    "w3c":         w3c_adapter.run,
    "schema":      schema_adapter.run,
    "observatory": observatory_adapter.run,
    "gsc":         gsc_adapter.run,
    "pagespeed":   pagespeed_adapter.run,
}

# Heavy adapters skipped when `quick=True`.
HEAVY = {"lighthouse", "pa11y"}


def run(
    urls: Iterable[str],
    adapters: Optional[Dict[str, Callable]] = None,
    quick: bool = False,
    max_workers: int = 8,
) -> List[Dict]:
    """Run every adapter against every URL in parallel.

    * `adapters`: mapping of name → callable(url) → list[dict]. Defaults
      to `DEFAULT_ADAPTERS`.
    * `quick=True` skips adapters in `HEAVY`.
    * One adapter raising is logged on stderr and contributes `[]`.
    """
    if adapters is None:
        adapters = DEFAULT_ADAPTERS
    url_list = [u for u in (urls or [])]
    if not url_list:
        return []

    active = {
        name: fn for name, fn in adapters.items()
        if not (quick and name in HEAVY)
    }
    if not active:
        return []

    tasks = []
    for url in url_list:
        for name, fn in active.items():
            tasks.append((name, url, fn))

    findings: List[Dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_label = {
            pool.submit(_safe_call, fn, url, name): (name, url)
            for (name, url, fn) in tasks
        }
        for fut in concurrent.futures.as_completed(future_to_label):
            name, url = future_to_label[fut]
            try:
                result = fut.result()
            except Exception as exc:  # pragma: no cover — _safe_call already wraps
                print(
                    f"probe[{name}] on {url} failed: {exc}",
                    file=sys.stderr,
                )
                result = []
            if result:
                findings.extend(result)
    return findings


def _safe_call(fn: Callable, url: str, name: str) -> List[Dict]:
    try:
        out = fn(url)
        return out or []
    except Exception as exc:
        print(f"probe[{name}] on {url} failed: {exc}", file=sys.stderr)
        return []
