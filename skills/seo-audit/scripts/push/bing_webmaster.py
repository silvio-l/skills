#!/usr/bin/env python3
"""Bing Webmaster URL Submission push adapter.

Endpoint:
    https://ssw.live.com/webmaster/api.svc/json/SubmitUrl?apikey=<key>

Per the Bing Webmaster API, one URL is submitted per request via a
JSON body:
    {"siteUrl": "<site>", "url": "<url>"}

Rate-limit safety:
* Default daily limit assumed at 10 URLs/day (Bing's published default
  for unverified sites). Override via `BING_DAILY_LIMIT` env.
* The adapter persists a per-day counter at
  `<state_dir>/seo-audit-bing-counter-<YYYY-MM-DD>.json`. If today's
  count + planned URLs exceeds the limit, the batch is clipped to the
  remaining budget and a warning is attached.

`plan()` returns a structured plan. `execute()` performs the actual
POSTs only when `plan["ready"]` and the caller passes `confirmed=True`.
"""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import Callable, Dict, List, Optional


BING_ENDPOINT_BASE = (
    "https://ssw.live.com/webmaster/api.svc/json/SubmitUrl"
)

DEFAULT_DAILY_LIMIT = 10


def _today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def _counter_path(state_dir: pathlib.Path, day: str) -> pathlib.Path:
    return state_dir / f"seo-audit-bing-counter-{day}.json"


def _read_counter(state_dir: pathlib.Path, day: str) -> int:
    p = _counter_path(state_dir, day)
    if not p.is_file():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return int(data.get("count", 0))
    except (json.JSONDecodeError, ValueError, OSError):
        return 0


def _write_counter(state_dir: pathlib.Path, day: str, count: int) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    _counter_path(state_dir, day).write_text(
        json.dumps({"count": int(count)}), encoding="utf-8"
    )


def plan(
    *,
    site_url: str,
    urls: List[str],
    state_dir,
    env: Optional[Dict] = None,
) -> Dict:
    """Build a structured plan dict for Bing Webmaster submission.

    Returns:
        {
          "module":       "bing",
          "ready":        bool,
          "reason":       str,
          "site_url":     str,
          "items":        list[str],   # URLs to submit (after clipping)
          "dropped":      list[str],   # URLs dropped due to quota
          "used_today":   int,
          "daily_limit":  int,
          "state_dir":    str,
          "day":          str,
          "warnings":     list[str],
        }
    """
    env = env if env is not None else {}
    state_dir = pathlib.Path(state_dir)
    urls = list(urls or [])

    api_key = env.get("BING_WEBMASTER_API_KEY")
    if not api_key:
        return {
            "module": "bing",
            "ready": False,
            "reason": "BING_WEBMASTER_API_KEY not set in environment.",
            "site_url": site_url,
            "items": [],
            "dropped": urls,
            "used_today": 0,
            "daily_limit": DEFAULT_DAILY_LIMIT,
            "state_dir": str(state_dir),
            "day": _today(),
            "warnings": [],
        }

    try:
        daily_limit = int(env.get("BING_DAILY_LIMIT") or DEFAULT_DAILY_LIMIT)
    except ValueError:
        daily_limit = DEFAULT_DAILY_LIMIT

    day = _today()
    used = _read_counter(state_dir, day)
    remaining = max(daily_limit - used, 0)

    items: List[str] = []
    dropped: List[str] = []
    warnings: List[str] = []

    if len(urls) <= remaining:
        items = urls
    else:
        items = urls[:remaining]
        dropped = urls[remaining:]
        warnings.append(
            f"Bing quota: {used}/{daily_limit} already used today; "
            f"batch clipped to remaining {remaining}. "
            f"Set BING_DAILY_LIMIT if your site is verified for 10000/day."
        )

    return {
        "module": "bing",
        "ready": True,
        "reason": (
            f"Submit {len(items)} URL(s) to Bing Webmaster "
            f"(used {used}/{daily_limit} today)."
        ),
        "site_url": site_url,
        "items": items,
        "dropped": dropped,
        "used_today": used,
        "daily_limit": daily_limit,
        "api_key": api_key,
        "state_dir": str(state_dir),
        "day": day,
        "warnings": warnings,
    }


def execute(
    plan_dict: Dict,
    *,
    client: Callable,
    confirmed: bool,
) -> Dict:
    """Perform the per-URL POSTs.

    `client` signature: `(method, url, headers, body) -> (status, text)`.

    Returns:
        {
          "module": "bing",
          "submitted": bool,
          "responses": [{"url": str, "status": int, "body": str}],
          "errors":    list[str],
        }
    """
    if not plan_dict.get("ready"):
        return {
            "module": "bing",
            "submitted": False,
            "responses": [],
            "errors": [plan_dict.get("reason", "plan not ready")],
        }
    if not confirmed:
        return {
            "module": "bing",
            "submitted": False,
            "responses": [],
            "errors": ["not confirmed by user"],
        }
    items = plan_dict.get("items") or []
    if not items:
        return {
            "module": "bing",
            "submitted": False,
            "responses": [],
            "errors": ["no items to submit (quota exhausted?)"],
        }

    api_key = plan_dict["api_key"]
    site_url = plan_dict["site_url"]
    endpoint = f"{BING_ENDPOINT_BASE}?apikey={api_key}"
    headers = {"Content-Type": "application/json; charset=utf-8"}

    responses: List[Dict] = []
    errors: List[str] = []

    for url in items:
        payload = {"siteUrl": site_url, "url": url}
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        try:
            status, text = client("POST", endpoint, headers, body)
            responses.append({"url": url, "status": status, "body": text})
        except Exception as exc:  # pragma: no cover
            errors.append(f"Bing POST for {url} failed: {exc}")

    # Update counter — only on a real execute path.
    state_dir = pathlib.Path(plan_dict["state_dir"])
    day = plan_dict["day"]
    new_count = _read_counter(state_dir, day) + len(responses)
    _write_counter(state_dir, day, new_count)

    return {
        "module": "bing",
        "submitted": bool(responses) and not errors,
        "responses": responses,
        "errors": errors,
    }
