#!/usr/bin/env python3
"""Google Play collector via google-play-scraper (Node, slice 04).

Wraps the ``google-play-scraper`` Node library (invoked through ``npx`` so no
global install is needed) for the four Play channels the pipeline needs:

* **search**        — seed-keyword search (discovery channel 1, Play side).
* **app/lookup**    — Play Core + Slots metadata for one appId (channel 2).
* **list/charts**   — category top charts (channel 2, Play side).
* **similar**       — the similar-apps graph, 1 hop (channel 3, Play side).
* **suggest**       — Play autocomplete (the only free real-search signal,
                      channel 6, Play side).

Like the iTunes/Reddit collectors this is an **external library collector** —
it is **NOT unit-tested** (repo convention: external collectors fail loud and
their output formats would rot tests). It is verified by the dispatcher's
manual live-smoke run. The pure transforms (raw JSON -> Core + Slots) live in
:mod:`schema` and ARE tested; the orchestration that wires these collectors
lives in :mod:`collect.collect_play` and is tested with injectable fakes.

google-play-scraper goes through the library's own HTTP transport, so we do
**not** impose the Playwright rate limiter here (the PRD's "google-play-scraper
goes through the library's own transport" note). We do cache responses (24h)
so a second run within TTL makes no duplicate live call, and every call is
wrapped **never-blocking**: any failure returns a safe empty (``[]`` / ``{}``)
and the caller marks the source ``"unavailable"``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional

import cache as CACHE

# google-play-scraper is an **ESM-only** library (v10+, ``"type": "module"``),
# so ``require()`` cannot load it and ``npx -p … node -e`` leaves it off Node's
# resolution path. We therefore vendor it once into a stable home-cache dir and
# run an ESM helper file **from that dir** (so Node resolves ``node_modules``
# relative to the script). The install is idempotent and mirrors the Chromium
# bootstrap in :mod:`apple_browser`.
_GPS_HOME = os.environ.get("ASO_GPS_DIR") or os.path.join(
    os.path.expanduser("~"), ".cache", "aso-research", "node"
)
_HELPER_NAME = "gps_helper.mjs"

# ESM helper: reads a JSON ``{cmd, args}`` blob from argv, prints a JSON result
# on stdout. ``gplay.default || gplay`` handles the default export shape.
_NODE_HELPER = r"""
import _gplay from 'google-play-scraper';
const gplay = _gplay.default || _gplay;
const input = JSON.parse(process.argv[2]);
const LANG = (input.args && input.args.lang) || 'de';
const COUNTRY = (input.args && input.args.country) || 'de';
function run() {
  const cmd = input.cmd;
  const a = input.args || {};
  switch (cmd) {
    case 'search':
      return gplay.search({term: a.term, num: a.num || 30, lang: LANG, country: COUNTRY});
    case 'app':
      return gplay.app({appId: a.appId, lang: LANG, country: COUNTRY});
    case 'list': {
      // Map the unified category slug → Play's category enum (PRODUCTIVITY,
      // BUSINESS, …); an unknown slug omits the category → overall top-free.
      const key = String(a.category || '').toUpperCase();
      const cat = gplay.category[key];
      const opts = {collection: a.collection || gplay.collection.TOP_FREE, num: a.num || 40, lang: LANG, country: COUNTRY};
      if (cat) opts.category = cat;
      return gplay.list(opts);
    }
    case 'similar':
      return gplay.similar({appId: a.appId, lang: LANG, country: COUNTRY});
    case 'suggest':
      return gplay.suggest({term: a.term, lang: LANG, country: COUNTRY});
    default:
      return Promise.reject(new Error('unknown cmd: ' + cmd));
  }
}
run().then(function (out) {
  process.stdout.write(JSON.stringify({ok: true, data: out}));
}).catch(function (err) {
  process.stdout.write(JSON.stringify({ok: false, error: String(err && err.message || err)}));
});
"""

# Idempotent per-process: ensure the vendored install exists exactly once.
_ensure_gps_done = False
_ensure_gps_result: Optional[bool] = None


def _ensure_gps() -> bool:
    """Vendor google-play-scraper into ``_GPS_HOME`` once; return availability.

    Idempotent per process. Writes a minimal ``package.json`` + the ESM helper,
    then ``npm install``s the library if it is not already resolvable. A
    ``False`` return is a never-blocking degradation — the caller marks the
    Play sources "unavailable" and the pipeline continues (Apple-only result).
    """
    global _ensure_gps_done, _ensure_gps_result
    if _ensure_gps_done:
        return bool(_ensure_gps_result)
    _ensure_gps_done = True
    try:
        os.makedirs(_GPS_HOME, exist_ok=True)
        pkg = os.path.join(_GPS_HOME, "package.json")
        if not os.path.exists(pkg):
            with open(pkg, "w", encoding="utf-8") as fh:
                fh.write('{"name":"aso-gps","private":true,"type":"module"}\n')
        # (Re)write the helper so a code change here always reaches disk.
        with open(os.path.join(_GPS_HOME, _HELPER_NAME), "w", encoding="utf-8") as fh:
            fh.write(_NODE_HELPER)
        installed = os.path.isdir(os.path.join(_GPS_HOME, "node_modules", "google-play-scraper"))
        if not installed:
            print("[play] installing google-play-scraper (one-time)…", file=sys.stderr)
            proc = subprocess.run(
                ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error",
                 "google-play-scraper@^10"],
                cwd=_GPS_HOME, capture_output=True, text=True, timeout=300,
            )
            if proc.returncode != 0:
                print(f"[play] npm install failed: {(proc.stderr or '').strip()[:160]}", file=sys.stderr)
                _ensure_gps_result = False
                return False
        _ensure_gps_result = True
    except Exception as exc:  # never-blocking
        print(f"[play] bootstrap error: {type(exc).__name__}: {exc}", file=sys.stderr)
        _ensure_gps_result = False
    return bool(_ensure_gps_result)


def _run_node(cmd: str, args: Dict[str, Any], *, country: str = "de") -> Any:
    """Run the google-play-scraper ESM helper from the vendored dir.

    Raises ``RuntimeError`` on a missing install, non-zero exit, or
    ``{ok:false}`` payload — callers wrap this in the never-blocking ``_safe``
    posture.
    """
    if not _ensure_gps():
        raise RuntimeError("google-play-scraper not available (bootstrap failed)")
    payload = json.dumps({"cmd": cmd, "args": {**args, "country": country}})
    proc = subprocess.run(
        ["node", _HELPER_NAME, payload],
        cwd=_GPS_HOME,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"google-play-scraper '{cmd}' exited {proc.returncode}: "
            f"{(proc.stderr or '').strip()[:200]}"
        )
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"google-play-scraper '{cmd}' returned non-JSON: {exc}") from exc
    if not envelope.get("ok"):
        raise RuntimeError(f"google-play-scraper '{cmd}' failed: {envelope.get('error')}")
    return envelope.get("data")


def _cached(
    key_args: Dict[str, Any],
    compute: Callable[[], Any],
    *,
    cache_dir: str,
    fresh: bool,
    ttl: float = CACHE.HTTP_TTL,
) -> Any:
    """Cache-backed wrapper: consult the response cache before ``compute``."""
    key = CACHE.cache_key("PLAY", str(sorted(key_args.items())))
    path = CACHE.cache_path(cache_dir, key) if cache_dir else ""
    if path and not fresh and CACHE.is_fresh(path, ttl, __import__("time").time()):
        cached = CACHE.read_cache(path)
        if cached is not None:
            try:
                return json.loads(cached.decode("utf-8"))
            except Exception:
                pass
    data = compute()
    if path and data is not None:
        try:
            CACHE.write_cache(path, json.dumps(data).encode("utf-8"))
        except Exception:
            pass
    return data


# ---------------------------------------------------------------------------
# Public collectors (NOT unit-tested — external; fail loud, wrapped upstream)
# ---------------------------------------------------------------------------

def search(
    term: str,
    *,
    country: str = "de",
    cache_dir: str = "",
    fresh: bool = False,
    num: int = 30,
) -> List[Dict]:
    """Play seed-keyword search. Returns raw google-play-scraper result dicts."""
    return _cached(
        {"cmd": "search", "term": term, "num": num, "country": country},
        lambda: _run_node("search", {"term": term, "num": num}, country=country),
        cache_dir=cache_dir, fresh=fresh,
    ) or []


def lookup(
    app_id: str,
    *,
    country: str = "de",
    cache_dir: str = "",
    fresh: bool = False,
) -> Dict:
    """Play app() metadata for one appId. Returns ``{}`` when nothing resolves."""
    data = _cached(
        {"cmd": "app", "appId": app_id, "country": country},
        lambda: _run_node("app", {"appId": app_id}, country=country),
        cache_dir=cache_dir, fresh=fresh,
    )
    return data or {}


def charts(
    category: str,
    *,
    country: str = "de",
    cache_dir: str = "",
    fresh: bool = False,
    num: int = 40,
) -> List[Dict]:
    """Play category top charts (deckel-limited). Returns raw result dicts."""
    return _cached(
        {"cmd": "list", "category": category, "num": num, "country": country},
        lambda: _run_node("list", {"category": category or "", "num": num}, country=country),
        cache_dir=cache_dir, fresh=fresh,
    ) or []


def similar(
    app_id: str,
    *,
    country: str = "de",
    cache_dir: str = "",
    fresh: bool = False,
) -> List[str]:
    """Play similar-apps graph (1 hop). Returns a list of appId strings."""
    data = _cached(
        {"cmd": "similar", "appId": app_id, "country": country},
        lambda: _run_node("similar", {"appId": app_id}, country=country),
        cache_dir=cache_dir, fresh=fresh,
    )
    # gplay.similar returns a list of app objects (or sometimes bare ids);
    # normalise to a stable list of appId strings.
    out: List[str] = []
    for entry in data or []:
        aid = entry.get("appId") if isinstance(entry, dict) else entry
        if aid:
            out.append(str(aid))
    return out


def fetch_suggest(
    term: str,
    *,
    country: str = "de",
    cache_dir: str = "",
    fresh: bool = False,
) -> List[str]:
    """One Play autocomplete call. Returns suggestion strings; ``[]`` on failure."""
    data = _cached(
        {"cmd": "suggest", "term": term, "country": country},
        lambda: _run_node("suggest", {"term": term}, country=country),
        cache_dir=cache_dir, fresh=fresh,
    )
    return [str(s).strip() for s in (data or []) if s and str(s).strip()]


def collect_suggest(
    seed_terms: List[str],
    *,
    country: str = "de",
    cache_dir: str = "",
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., List[str]]] = None,
) -> List[str]:
    """Probe Play autocomplete for each seed term; merge + de-dupe suggestions.

    Never-blocking: any per-term failure is skipped. The result is unioned
    with Apple's autocomplete upstream so the scorer's +15 relevance boost
    applies to terms users actually type on either store.
    """
    do_fetch = fetch_fn or fetch_suggest
    seen: set = set()
    out: List[str] = []
    for term in seed_terms:
        try:
            suggestions = do_fetch(term, country=country, cache_dir=cache_dir, fresh=fresh)
        except Exception:
            continue
        for s in suggestions or []:
            s = (s or "").strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
    return out


if __name__ == "__main__":  # pragma: no cover — manual live-smoke entry
    cmd = sys.argv[1] if len(sys.argv) > 1 else "search"
    arg = sys.argv[2] if len(sys.argv) > 2 else "habit tracker"
    if cmd == "search":
        print(json.dumps(search(arg), indent=2, ensure_ascii=False))
    elif cmd == "app":
        print(json.dumps(lookup(arg), indent=2, ensure_ascii=False))
    elif cmd == "suggest":
        print(json.dumps(fetch_suggest(arg), indent=2, ensure_ascii=False))
    else:
        print(f"usage: {sys.argv[0]} [search|app|suggest] <arg>", file=sys.stderr)
