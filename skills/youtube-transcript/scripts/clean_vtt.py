#!/usr/bin/env python3
"""Convert a YouTube VTT subtitle file into clean, deduplicated text.

YouTube's auto-generated VTT files use "rolling captions": each cue repeats
one or more lines already shown by an earlier cue (a plain, untagged carry-
over) before adding new content, and word-level timing is embedded as inline
tags like `<00:00:00.320><c>word</c>`. Reading the file naively duplicates or
triples the transcript. This script strips the tags and drops lines that
were already emitted by a recent cue to recover the real spoken content,
each attached to the timestamp of the cue that first introduced it.

Dedup uses a small trailing window (not just "equals the previous line")
because a cue can carry over more than one prior line unchanged — comparing
only against the immediately preceding line misses that case.
"""
import re
import sys
from collections import deque

CUE_TIME_RE = re.compile(
    r"^(\d\d:\d\d:\d\d\.\d\d\d)\s*-->\s*(\d\d:\d\d:\d\d\.\d\d\d)"
)
DEDUP_WINDOW = 4


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise SystemExit(f"error: subtitle file not found: {path}")
    except UnicodeDecodeError:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()


def _parse_cues(text: str):
    """Yield (start_timestamp, [text_lines]) per VTT cue, tags stripped."""
    cue_start = None
    cue_lines: list[str] = []

    def flush():
        if cue_start is not None and cue_lines:
            yield_list.append((cue_start, cue_lines[:]))

    yield_list: list[tuple[str, list[str]]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        m = CUE_TIME_RE.match(line)
        if m:
            if cue_start is not None and cue_lines:
                yield_list.append((cue_start, cue_lines[:]))
            cue_start = m.group(1)
            cue_lines = []
            continue
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if clean:
            cue_lines.append(clean)
    if cue_start is not None and cue_lines:
        yield_list.append((cue_start, cue_lines[:]))
    return yield_list


def _to_mmss(ts: str) -> str:
    h, m, s = ts.split(":")
    total_seconds = int(h) * 3600 + int(m) * 60 + int(float(s))
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


def clean_vtt(path: str, with_timestamps: bool = False) -> str:
    text = _read(path)
    if not text.strip():
        raise SystemExit(f"error: subtitle file is empty: {path}")

    cues = _parse_cues(text)
    if not cues:
        raise SystemExit(f"error: no caption text found in {path} (empty or malformed VTT)")

    recent: deque[str] = deque(maxlen=DEDUP_WINDOW)
    out: list[str] = []
    for start, lines in cues:
        for line in lines:
            if line in recent:
                continue
            recent.append(line)
            out.append(f"[{_to_mmss(start)}] {line}" if with_timestamps else line)

    sep = "\n" if with_timestamps else " "
    return sep.join(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    timestamps = "--timestamps" in args
    files = [a for a in args if not a.startswith("--")]
    if len(files) != 1:
        raise SystemExit("usage: clean_vtt.py <file.vtt> [--timestamps]")
    print(clean_vtt(files[0], with_timestamps=timestamps))
