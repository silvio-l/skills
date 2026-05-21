#!/usr/bin/env python3
"""IndexNow push adapter.

Submits a URL list to https://api.indexnow.org/IndexNow as a single
POST per IndexNow spec.

Setup contract:
* `INDEXNOW_KEY` must be set in the environment.
* `<public_dir>/<key>.txt` must exist and contain exactly the key.

If either is missing, `plan()` returns `ready=False` with a
`first_setup_hint` so the agent can guide the user through setup.
The adapter never writes the key file itself — that is a one-time
human action per site.

`execute()` performs the actual POST only when both `plan["ready"]`
and the caller passes `confirmed=True`. The HTTP client is injected
for testing; the real client lives in `_http.py`.
"""

from __future__ import annotations

import json
import pathlib
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse


INDEXNOW_ENDPOINT = "https://api.indexnow.org/IndexNow"


def _host_of(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc


def plan(public_dir, urls: List[str], *, env: Optional[Dict] = None) -> Dict:
    """Build a structured plan dict for IndexNow submission.

    Returns:
        {
          "module":   "indexnow",
          "ready":    bool,
          "reason":   str,        # human-readable status / skip reason
          "items":    list[str],  # URLs that would be submitted
          "host":     str,        # derived from first URL
          "key":      str|None,   # the env key (only when ready)
          "key_location": str|None,
          "first_setup_hint": str (only when missing setup),
          "warnings": list[str],
        }
    """
    env = env if env is not None else {}
    public_dir = pathlib.Path(public_dir)
    urls = list(urls or [])

    key = env.get("INDEXNOW_KEY")
    if not key:
        return {
            "module": "indexnow",
            "ready": False,
            "reason": "INDEXNOW_KEY not set in environment.",
            "items": urls,
            "host": _host_of(urls[0]) if urls else "",
            "key": None,
            "key_location": None,
            "warnings": [],
        }

    key_file = public_dir / f"{key}.txt"
    if not key_file.is_file():
        return {
            "module": "indexnow",
            "ready": False,
            "reason": (
                f"IndexNow key file missing at {key_file}. "
                "Run first-setup before pushing."
            ),
            "items": urls,
            "host": _host_of(urls[0]) if urls else "",
            "key": key,
            "key_location": None,
            "first_setup_hint": (
                f"Create {key_file} containing exactly the key '{key}'. "
                "After your next deploy, the file is reachable at "
                f"https://<your-host>/{key}.txt and IndexNow can verify it."
            ),
            "warnings": [],
        }

    actual = key_file.read_text(encoding="utf-8").strip()
    if actual != key:
        return {
            "module": "indexnow",
            "ready": False,
            "reason": (
                f"IndexNow key file content mismatch at {key_file}. "
                "Expected the same value as $INDEXNOW_KEY."
            ),
            "items": urls,
            "host": _host_of(urls[0]) if urls else "",
            "key": key,
            "key_location": None,
            "warnings": [],
        }

    host = _host_of(urls[0]) if urls else ""
    key_location = f"https://{host}/{key}.txt" if host else ""
    return {
        "module": "indexnow",
        "ready": True,
        "reason": f"Submit {len(urls)} URL(s) to IndexNow.",
        "items": urls,
        "host": host,
        "key": key,
        "key_location": key_location,
        "warnings": [],
    }


def execute(
    plan_dict: Dict,
    *,
    client: Callable,
    confirmed: bool,
) -> Dict:
    """Perform the IndexNow POST.

    `client` signature: `(method, url, headers, body) -> (status, text)`.

    Returns a result dict:
        {
          "module": "indexnow",
          "submitted": bool,
          "responses": [{"status": int, "body": str}, ...],
          "errors":    list[str],
        }
    """
    if not plan_dict.get("ready"):
        return {
            "module": "indexnow",
            "submitted": False,
            "responses": [],
            "errors": [plan_dict.get("reason", "plan not ready")],
        }
    if not confirmed:
        return {
            "module": "indexnow",
            "submitted": False,
            "responses": [],
            "errors": ["not confirmed by user"],
        }

    payload = {
        "host":        plan_dict["host"],
        "key":         plan_dict["key"],
        "keyLocation": plan_dict["key_location"],
        "urlList":     list(plan_dict["items"]),
    }
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    headers = {"Content-Type": "application/json"}

    responses: List[Dict] = []
    errors: List[str] = []
    try:
        status, text = client("POST", INDEXNOW_ENDPOINT, headers, body)
        responses.append({"status": status, "body": text})
    except Exception as exc:  # pragma: no cover — exercised by integration only
        errors.append(f"IndexNow POST failed: {exc}")

    return {
        "module": "indexnow",
        "submitted": bool(responses) and not errors,
        "responses": responses,
        "errors": errors,
    }
