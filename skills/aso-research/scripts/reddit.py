#!/usr/bin/env python3
"""Reddit OAuth search collector.

Reddit **blocks anonymous ``.json`` access** (HTTP 403) from non-browser
clients, so the old ``www.reddit.com/search.json`` path always returned 0.
This collector uses Reddit's official **application-only OAuth** API instead:
it reads a free app's ``REDDIT_CLIENT_ID`` / ``REDDIT_CLIENT_SECRET`` (env or
``~/.config/reddit/api.env``), fetches a bearer token, and queries
``oauth.reddit.com/search``. Threads (titles + selftext) are qualitative
material for positioning *and* a user-language keyword signal.

Without credentials the collector raises a clear ``RedditAuthError`` so the
pipeline marks the source **"unavailable"** with an actionable reason — never
a misleading "ok (0)". Politeness: descriptive UA, <= 1 req/s + jitter, the
shared HTTP cache, exponential backoff on 429/503. Never-blocking upstream.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

import cache as CACHE
import politeness as POLITE

SEARCH_URL = "https://oauth.reddit.com/search"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
DEFAULT_LIMIT = 25  # threads per query
MAX_QUERIES = 5  # deckel
# Reddit asks for a descriptive UA: platform:appid:version (by /u/user).
USER_AGENT = "python:aso-research:0.2 (keyword research; local)"
_CREDS_ENV = os.path.join(os.path.expanduser("~"), ".config", "reddit", "api.env")

_RATE = POLITE.RateLimiter(seed=7)
_token_cache: Dict[str, object] = {}  # {"token": str, "expires": float}


class RedditAuthError(RuntimeError):
    """Raised when Reddit cannot be queried because no API credentials exist."""


def _load_credentials() -> Optional[tuple]:
    """Return ``(client_id, client_secret)`` from env or the creds file, else None."""
    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if cid and secret:
        return cid.strip(), secret.strip()
    if os.path.isfile(_CREDS_ENV):
        vals: Dict[str, str] = {}
        try:
            with open(_CREDS_ENV, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    vals[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            return None
        cid = vals.get("REDDIT_CLIENT_ID")
        secret = vals.get("REDDIT_CLIENT_SECRET")
        if cid and secret:
            return cid, secret
    return None


REDDIT_APPS_URL = "https://www.reddit.com/prefs/apps"


def credentials_status() -> Dict:
    """Report whether Reddit credentials are configured (for preflight).

    ``{"ok": bool, "source": "env"|"file"|None, "path": <creds file>,
       "register_url": ..., "reason": <when not ok>}``.
    """
    creds = _load_credentials()
    if creds:
        src = "env" if os.environ.get("REDDIT_CLIENT_ID") else "file"
        return {"ok": True, "source": src, "path": _CREDS_ENV}
    return {
        "ok": False,
        "source": None,
        "path": _CREDS_ENV,
        "register_url": REDDIT_APPS_URL,
        "reason": "no REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET (anonymous Reddit is 403-blocked)",
    }


def save_credentials(client_id: str, client_secret: str, *, path: str = None) -> str:
    """Write Reddit credentials to the creds file (0600). Returns the path.

    Used by the preflight setup helper so the user only pastes the two values
    once; the skill writes the file for them.
    """
    target = path or _CREDS_ENV
    cid = (client_id or "").strip()
    secret = (client_secret or "").strip()
    if not cid or not secret:
        raise ValueError("both client_id and client_secret are required")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    body = (
        "# Reddit application-only OAuth credentials for aso-research\n"
        "# Registered as a 'script' app at https://www.reddit.com/prefs/apps\n"
        f"REDDIT_CLIENT_ID={cid}\n"
        f"REDDIT_CLIENT_SECRET={secret}\n"
    )
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(body)
    try:
        os.chmod(target, 0o600)
    except Exception:
        pass
    # invalidate any cached token so the next call re-auths with the new creds
    _token_cache.clear()
    return target


def _get_token(now_ts: float) -> str:
    """Fetch (and process-cache) an application-only bearer token."""
    cached = _token_cache.get("token")
    if cached and float(_token_cache.get("expires", 0)) > now_ts + 30:
        return str(cached)
    creds = _load_credentials()
    if not creds:
        raise RedditAuthError(
            "Reddit needs free API credentials (anonymous .json is 403-blocked): "
            "register a 'script' app at https://www.reddit.com/prefs/apps and set "
            "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in ~/.config/reddit/api.env"
        )
    cid, secret = creds
    basic = base64.b64encode(f"{cid}:{secret}".encode("utf-8")).decode("ascii")
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("ascii")
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Authorization": f"Basic {basic}", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    token = payload.get("access_token")
    if not token:
        raise RedditAuthError(f"Reddit token request returned no access_token: {payload}")
    _token_cache["token"] = token
    _token_cache["expires"] = now_ts + float(payload.get("expires_in", 3600))
    return token


def fetch_search(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = CACHE.HTTP_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
    rate_limiter: Optional[POLITE.RateLimiter] = None,
) -> Dict:
    """One Reddit OAuth search call, cache-backed.

    Raises ``RedditAuthError`` when no credentials are configured (so the source
    is honestly marked unavailable). Other transient failures return an empty
    payload.
    """
    params = {"q": query, "limit": str(limit), "sort": "relevance", "t": "year", "raw_json": "1"}
    key = CACHE.cache_key("GET", SEARCH_URL, params)
    path = CACHE.cache_path(cache_dir, key)
    now_ts = time.time() if now is None else now

    if not fresh and CACHE.is_fresh(path, ttl, now_ts):
        cached = CACHE.read_cache(path)
        if cached is not None:
            return json.loads(cached.decode("utf-8"))

    token = _get_token(now_ts)  # raises RedditAuthError without creds
    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    rl = rate_limiter or _RATE
    headers = {"Authorization": f"bearer {token}", "User-Agent": USER_AGENT}
    payload = None
    for attempt in range(POLITE.MAX_RETRIES):
        try:
            rl.wait(url)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = getattr(resp, "status", resp.getcode())
                raw = resp.read()
            if status in POLITE.RETRY_STATUS:
                time.sleep(POLITE.backoff_delay(attempt, rng=rl._rng))
                continue
            payload = raw
            break
        except Exception:
            if attempt == POLITE.MAX_RETRIES - 1:
                return {"data": {"children": []}}
            time.sleep(POLITE.backoff_delay(attempt, rng=rl._rng))

    if payload is None:
        return {"data": {"children": []}}
    CACHE.write_cache(path, payload, now=now_ts)
    return json.loads(payload.decode("utf-8"))


def parse_threads(raw: Dict) -> List[Dict]:
    """Pull lightweight qualitative records from a Reddit search payload."""
    out: List[Dict] = []
    children = (raw.get("data") or {}).get("children") or []
    for ch in children:
        d = ch.get("data") or {}
        out.append(
            {
                "title": d.get("title") or "",
                "subreddit": d.get("subreddit") or "",
                "score": d.get("score") or 0,
                "url": d.get("url") or "",
                "selftext": (d.get("selftext") or "")[:500],
            }
        )
    return out


def user_language_terms(threads: List[Dict], *, min_freq: int = 2, top: int = 40) -> List[str]:
    """Distinctive single terms users repeat across Reddit threads.

    Reddit titles + selftext are *what real users say* about the niche — the
    same kind of real-demand signal as store autocomplete. The pipeline folds
    these into the Search-Suggest boost set so a term people actually discuss
    gains relevance. Filtering (stopwords, generics, min-frequency) is delegated
    to :func:`extract.tokenize`; only terms seen in >= ``min_freq`` threads are
    kept, capped at ``top`` (deterministic: sorted by -count then term).
    """
    import extract  # local import (extract is a pure module)

    counts: Dict[str, int] = {}
    for t in threads or []:
        text = f"{t.get('title', '')} {t.get('selftext', '')}"
        for tok in set(extract.tokenize(text)):  # once per thread
            counts[tok] = counts.get(tok, 0) + 1
    terms = [w for w, n in counts.items() if n >= min_freq]
    terms.sort(key=lambda w: (-counts[w], w))
    return terms[:top]


def collect(
    queries: List[str],
    *,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., Dict]] = None,
    max_queries: int = MAX_QUERIES,
) -> List[Dict]:
    """Run up to ``max_queries`` Reddit searches, merge + de-dupe threads."""
    do_fetch = fetch_fn or fetch_search
    seen: set = set()
    merged: List[Dict] = []
    for q in queries[:max_queries]:
        try:
            raw = do_fetch(q, cache_dir=cache_dir, fresh=fresh)
        except RedditAuthError:
            # No credentials → surface as unavailable (with the actionable
            # reason) rather than a misleading "ok (0)". Re-raise to the caller.
            raise
        except Exception:
            continue
        for t in parse_threads(raw):
            key = (t.get("subreddit"), t.get("title"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(t)
    return merged
