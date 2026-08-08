#!/usr/bin/env python3
"""Extract the full conversation text from the chat currently open in
Safari's frontmost tab — for ChatGPT, Claude.ai, or Gemini sessions that
cannot be shared (no share link, or sharing disabled/unavailable).

Unlike fetch_shared_chat.py, this never touches the network: it drives the
user's own already-authenticated Safari tab via `do JavaScript` (through a
JXA driver, safari_driver.js) and reads the live, JS-rendered DOM directly —
no headless browser, no login, no screenshots/OCR.

Exit codes:
  0 - structured extraction succeeded (site recognized, messages found)
  2 - hard failure: no usable content at all (reason printed to stderr)
  3 - partial success: site/structure not recognized, but a generic
      unstructured text fallback was captured and saved instead
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DRIVER = SCRIPT_DIR / "safari_driver.js"
EXTRACT_DOM = SCRIPT_DIR / "extract_dom.js"


def run_driver() -> dict:
    proc = subprocess.run(
        ["osascript", "-l", "JavaScript", str(DRIVER), str(EXTRACT_DOM)],
        capture_output=True,
        text=True,
        timeout=110,
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "reason": f"osascript failed (exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}",
        }
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "reason": f"Driver produced non-JSON output (unexpected — please report): {e}. Raw output: {proc.stdout[:500]!r}",
        }


def render_markdown(result: dict) -> str:
    title = result.get("title") or "Untitled"
    lines = [f"# {title}\n"]
    lines.append(f"_Source: {result.get('host', 'unknown host')} ({result.get('site', 'unrecognized')}), extracted from the live Safari tab._\n")
    for msg in result.get("messages", []):
        lines.append(f"## {msg['role'].upper()}\n{msg['text']}\n")
    return "\n".join(lines)


def render_fallback_markdown(result: dict) -> str:
    title = result.get("title") or "Untitled"
    lines = [
        f"# {title}",
        "",
        "> **UNSTRUCTURED FALLBACK** — the page structure was not recognized "
        "(unsupported site, or the chat UI changed), so this is a raw text dump "
        "of the page body, not a clean role-tagged transcript. Read it critically.",
        "",
        f"_Source: {result.get('host', 'unknown host')}_",
        "",
        result.get("fallbackText", ""),
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Extract the conversation from the chat open in Safari's frontmost tab."
    )
    parser.add_argument("--output", "-o", help="File path to save the extracted text.")
    parser.add_argument("--json", action="store_true", help="Output result as a JSON object instead of plain text.")
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Fail with exit code 2 instead of falling back to a raw unstructured text dump.",
    )
    args = parser.parse_args()

    try:
        result = run_driver()
    except subprocess.TimeoutExpired:
        print("FAILED: Timed out waiting for Safari (osascript did not return within 110s).", file=sys.stderr)
        sys.exit(2)

    exit_code = 0
    if result.get("ok"):
        text = render_markdown(result)
        if result.get("partial"):
            print(
                "WARNING: extraction hit its time budget before the whole conversation "
                "was swept — the saved text may be missing some messages from a very long chat.",
                file=sys.stderr,
            )
    else:
        fallback_text = result.get("fallbackText", "")
        if not args.no_fallback and fallback_text and len(fallback_text) > 200:
            text = render_fallback_markdown(result)
            exit_code = 3
            print(f"WARNING: structured extraction failed ({result.get('reason')}). Using unstructured fallback text.", file=sys.stderr)
        else:
            print(f"FAILED: {result.get('reason', 'unknown error')}", file=sys.stderr)
            sys.exit(2)

    if args.output:
        abs_out = str(Path(args.output).resolve())
        Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
        Path(abs_out).write_text(text, encoding="utf-8")
        print(f"Saved conversation text ({len(text)} chars) to: {abs_out}", file=sys.stderr)
        result["saved_file"] = abs_out

    if args.json:
        result["rendered_text"] = text
        print(json.dumps(result, ensure_ascii=False))
    elif not args.output:
        print(text)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
