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
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional

import cache as CACHE

# The Node helper is shipped inline so there is no second file to keep in
# sync. It loads google-play-scraper from the npx-installed package, reads a
# JSON ``{cmd, args}`` blob from argv, and prints a JSON result on stdout.
# Using async/await because every gplay.* method returns a Promise.
_NODE_HELPER = r"""
const gplay = require('google-play-scraper');
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
    case 'list':
      return gplay.list({category: a.category || gplay.category.GAME, collection: a.collection || gplay.collection.TOP_FREE, num: a.num || 40, lang: LANG, country: COUNTRY});
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


def _run_node(cmd: str, args: Dict[str, Any], *, country: str = "de") -> Any:
    """Spawn the google-play-scraper helper via npx; return parsed payload.

    Raises ``RuntimeError`` on any non-zero exit or ``{ok:false}`` payload —
    callers wrap this in the never-blocking ``_safe`` posture. ``npx -p``
    installs the package ephemerally into the run environment so
    ``require('google-play-scraper')`` resolves without a global install.
    """
    payload = json.dumps({"cmd": cmd, "args": {**args, "country": country}})
    proc = subprocess.run(
        ["npx", "--yes", "-p", "google-play-scraper", "node", "-e", _NODE_HELPER, payload],
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
