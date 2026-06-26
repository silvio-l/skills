#!/usr/bin/env python3
"""Stage-level idempotency + crash-resume for aso-research (slice 06).

Promotes the cache scaffolding (slice 01) into full stage-level
idempotency. Each pipeline stage writes a single **checkpoint artefact**
(``<run-dir>/stages/<stage>.json``) holding its serializable result. On a
re-run, a stage whose checkpoint exists AND is fresh (mtime within its
TTL) is **skipped** — its callable is not re-invoked and its result is
reused as-is (byte-identical). A crash at stage N means stages 1..N-1
already wrote fresh checkpoints; the next run **resumes at N** without
re-crawling or re-scoring the finished stages (US9). ``--fresh`` bypasses
every freshness check so all stages re-run and overwrite (US9).

This is deliberately **not** a job DAG: stages are an ordered list, each
gated on its own checkpoint. The inter-stage data flow is carried inside
each checkpoint (the bundle the stage returns), so a skipped stage's
output is loaded straight from disk and fed to the next stage. The
human-facing artefacts (``keywords.json`` etc.) are written as a side
effect *inside* the stage callable, so a skipped stage leaves them
untouched — they stay byte-identical across a warm re-run (AC1, US18).

Per-stage wall-clock is recorded (``status`` + ``elapsed_seconds``) so the
≤30-min soft target (US12) is **observable** in ``run-summary.json``; a
skipped stage records ``elapsed_seconds: 0.0`` honestly.

Freshness reuses :func:`cache.is_fresh` (mtime-based, ``now``-injectable)
so the skip/resume logic is fully offline-testable with a temp artefact
store + injected fake stage callables + an injected clock.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Dict, Optional, Tuple

import cache as CACHE
import serialize

# Default TTLs mirror the response cache (PRD "File layout, cache,
# resumability"): collection (crawl) stages are the most fragile and use
# the browser TTL; pure-compute stages use the longer HTTP TTL.
DEFAULT_COLLECT_TTL = CACHE.BROWSER_TTL
DEFAULT_COMPUTE_TTL = CACHE.HTTP_TTL


class StageRunner:
    """Run an ordered list of idempotent stages against a run directory.

    Each stage is a ``(name, fn, ttl)`` triple. The runner decides run vs
    skip from the checkpoint's freshness, executes the callable when
    needed, persists the checkpoint atomically (tmp + replace, so a crash
    mid-write never leaves a half checkpoint that would break resume),
    and records per-stage timing.
    """

    def __init__(
        self,
        run_dir: str,
        *,
        fresh: bool = False,
        now: Optional[float] = None,
    ) -> None:
        self.run_dir = run_dir
        self.fresh = fresh
        self._now = now
        self._timing: Dict[str, Dict[str, Any]] = {}
        self._checkpoint_dir = os.path.join(run_dir, "stages")

    # -- internals -------------------------------------------------------

    def _clock(self) -> float:
        # Freshness uses the injected clock (tests); wall-clock of the
        # callable itself always uses the real clock (that is the point).
        return self._now if self._now is not None else time.time()

    def _checkpoint_path(self, name: str) -> str:
        return os.path.join(self._checkpoint_dir, name + ".json")

    def _atomic_write_json(self, path: str, obj: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(serialize.dumps_json(obj))
        os.replace(tmp, path)
        # When a clock is injected (tests), stamp the mtime to that clock so
        # the freshness check — which compares against the same clock — stays
        # consistent. Real runs leave the natural mtime and read time.time().
        if self._now is not None:
            os.utime(path, (self._now, self._now))

    # -- public API ------------------------------------------------------

    def stage(
        self,
        name: str,
        fn: Callable[[], Any],
        *,
        ttl: float,
        skippable: bool = True,
    ) -> Tuple[Any, str]:
        """Run (or skip) one stage.

        Returns ``(result, status)`` where ``status`` is ``"ran"`` or
        ``"skipped"``. A stage is skipped iff it is ``skippable``, the
        runner was not constructed with ``fresh=True``, and its checkpoint
        is fresh within ``ttl``. ``skippable=False`` always runs (used for
        the terminal report stage whose timestamp differs by design) but
        still records timing and writes no checkpoint.
        """
        path = self._checkpoint_path(name)
        if skippable and not self.fresh and CACHE.is_fresh(path, ttl, self._clock()):
            with open(path, "r", encoding="utf-8") as fh:
                result = json.load(fh)
            self._timing[name] = {"status": "skipped", "elapsed_seconds": 0.0}
            return result, "skipped"

        start = time.time()
        result = fn()
        elapsed = time.time() - start
        if skippable:
            self._atomic_write_json(path, result)
        self._timing[name] = {"status": "ran", "elapsed_seconds": round(elapsed, 4)}
        return result, "ran"

    def timing(self) -> Dict[str, Dict[str, Any]]:
        """Per-stage ``{status, elapsed_seconds}`` for run-summary (US12)."""
        return {name: dict(entry) for name, entry in self._timing.items()}
