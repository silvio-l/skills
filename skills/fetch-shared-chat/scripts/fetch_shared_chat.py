#!/usr/bin/env python3
"""Fetch and extract the full conversation text from a shared AI chat link.

Supports:
  - chatgpt.com/share/<id>              — plain HTTP, no browser needed
  - gemini.google.com/share/<id>        — headless-rendered (JS SPA)
  - share.gemini.google/<id>            — headless-rendered (JS SPA)
  - claude.ai/share/<id>                — attempted; Cloudflare currently
                                           blocks automated access, reported
                                           explicitly rather than faked

Each backend returns {"ok": True, "title": ..., "text": ...} on success or
{"ok": False, "reason": "..."} with a concrete, non-fabricated explanation
of why extraction failed — never a silent empty result.
"""

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from turbo_stream_decode import decode_first_line  # noqa: E402

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def detect_host(url: str) -> str | None:
    if "chatgpt.com/share/" in url or "chat.openai.com/share/" in url:
        return "chatgpt"
    if "gemini.google.com/share/" in url or "share.gemini.google/" in url:
        return "gemini"
    if "claude.ai/share/" in url:
        return "claude"
    return None


def fetch_chatgpt(url: str) -> dict:
    """React Router single-fetch data endpoint: no browser, no login, and the
    server states plainly why a share is unreachable (deleted vs. access-scoped)
    instead of an ambiguous client-side redirect."""
    data_url = url.rstrip("/") + ".data"
    req = urllib.request.Request(
        data_url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/x-turbo-stream, */*"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        return {"ok": False, "reason": f"Network error fetching {data_url}: {e}"}

    first_line = body.split("\n", 1)[0]
    try:
        decoded = decode_first_line(first_line)
    except Exception as e:
        return {
            "ok": False,
            "reason": f"Could not decode ChatGPT's response (wire format may have changed): {e}",
        }

    route_key = next((k for k in decoded if k.startswith("routes/share")), None)
    if route_key is None:
        return {"ok": False, "reason": "Unexpected response shape: no share route in payload"}

    server_response = decoded[route_key]["data"]["serverResponse"]
    if server_response.get("type") == "error":
        message = server_response.get("error") or server_response.get("toastMessage") or "unknown error"
        return {
            "ok": False,
            "reason": (
                f'ChatGPT denied access to this share: "{message}". '
                'The link may be scoped to a Business/Enterprise workspace, or its '
                'visibility may not be set to "Anyone with the link" in the share dialog.'
            ),
        }

    conv = server_response["data"]
    title = conv.get("title") or "Untitled"
    lines = [f"# {title}\n"]
    for item in conv.get("linear_conversation", []):
        msg = item.get("message")
        if not msg:
            continue
        role = (msg.get("author") or {}).get("role")
        if role in (None, "system"):
            continue
        if (msg.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
            continue
        parts = (msg.get("content") or {}).get("parts") or []
        text = "\n".join(p for p in parts if isinstance(p, str)).strip()
        if not text:
            continue
        lines.append(f"## {role.upper()}\n{text}\n")

    return {"ok": True, "title": title, "text": "\n".join(lines)}


async def _render(url: str, wait_ms: int = 4000, scroll_passes: int = 5):
    """Shared headless-Chromium render step for JS-SPA share pages."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
        await page.wait_for_timeout(wait_ms)
        for _ in range(scroll_passes):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(600)
        title = await page.title()
        final_url = page.url
        text = await page.inner_text("body")
        await browser.close()
    return title, final_url, text


def fetch_gemini(url: str) -> dict:
    """Gemini share pages render conversation content client-side; no proven
    server-side data endpoint is known, so this renders with headless Chromium."""
    title, _final_url, text = asyncio.run(_render(url))
    lowered = text.lower()
    if len(text) < 200 or ("sign in" in lowered and "gemini" in lowered and len(text) < 800):
        return {
            "ok": False,
            "reason": (
                f"Rendered page looks like a login wall or empty shell (only {len(text)} chars), "
                "not conversation content. The share link may require sign-in, or Gemini's "
                "page structure may have changed."
            ),
        }
    return {"ok": True, "title": title, "text": text}


def fetch_claude(url: str) -> dict:
    """claude.ai currently serves a Cloudflare bot-verification challenge to
    headless browsers on /share/ URLs. Detected and reported, not bypassed."""
    title, final_url, text = asyncio.run(_render(url, wait_ms=3000, scroll_passes=1))
    lowered = text.lower()
    if "security verification" in lowered or "challenge_redirect" in final_url:
        return {
            "ok": False,
            "reason": (
                "claude.ai served a Cloudflare bot-verification challenge to this automated "
                "request. This is not bypassable without a real, logged-in browser session — "
                "ask the user to open the link themselves if the content is needed."
            ),
        }
    if len(text) < 200:
        return {"ok": False, "reason": f"Rendered page looks empty or gated (only {len(text)} chars)."}
    return {"ok": True, "title": title, "text": text}


def main():
    parser = argparse.ArgumentParser(description="Fetch a shared AI chat conversation's full text.")
    parser.add_argument("url", help="Share URL (chatgpt.com/share/..., gemini.google.com/share/..., share.gemini.google/..., or claude.ai/share/...)")
    parser.add_argument("--output", "-o", help="File path to save the extracted text.")
    parser.add_argument("--json", action="store_true", help="Output result as a JSON object instead of plain text.")
    args = parser.parse_args()

    host = detect_host(args.url)
    if host is None:
        print(
            "Error: unrecognized share URL. Supported hosts: chatgpt.com/share/..., "
            "gemini.google.com/share/... or share.gemini.google/..., claude.ai/share/...",
            file=sys.stderr,
        )
        sys.exit(1)

    result = {"chatgpt": fetch_chatgpt, "gemini": fetch_gemini, "claude": fetch_claude}[host](args.url)

    if not result["ok"]:
        print(f"FAILED: {result['reason']}", file=sys.stderr)
        sys.exit(2)

    if args.output:
        abs_out = str(Path(args.output).resolve())
        Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
        Path(abs_out).write_text(result["text"], encoding="utf-8")
        print(f"Saved conversation text ({len(result['text'])} chars) to: {abs_out}", file=sys.stderr)
        result["saved_file"] = abs_out

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif not args.output:
        print(result["text"])


if __name__ == "__main__":
    main()
