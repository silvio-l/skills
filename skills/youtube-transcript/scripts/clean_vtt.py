#!/usr/bin/env python3
"""Convert a YouTube VTT subtitle file into clean, deduplicated plain text.

YouTube's auto-generated VTT files use "rolling captions": each line of text
appears twice in a row (once as a preview of the next block, once as the
current block) and carries inline word-level timing tags like
`<00:00:00.320><c>word</c>`. Reading the file naively duplicates or triples
the transcript. This script strips the tags and drops consecutive duplicate
lines to recover the real transcript.
"""
import re
import sys


def clean_vtt(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise SystemExit(f"error: subtitle file not found: {path}")
    except UnicodeDecodeError:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()

    if not text.strip():
        raise SystemExit(f"error: subtitle file is empty: {path}")

    text = re.sub(r"<[^>]+>", "", text)  # strip inline timing/style tags

    out = []
    prev = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if "-->" in line:
            continue
        if line == prev:
            continue
        out.append(line)
        prev = line

    if not out:
        raise SystemExit(f"error: no caption text found in {path} (empty or malformed VTT)")

    return " ".join(out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: clean_vtt.py <file.vtt>")
    print(clean_vtt(sys.argv[1]))
