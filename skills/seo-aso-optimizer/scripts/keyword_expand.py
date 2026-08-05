#!/usr/bin/env python3
"""Free, no-signup long-tail keyword harvest via Google's and YouTube's public
(undocumented but widely used) autocomplete endpoints. Sweeps each seed with
an a-z suffix, question-word prefixes, and common modifier suffixes — the
same "alphabet soup" technique paid keyword tools charge for, built on a data
source that's free.

Judgment-free by design: harvests and dedupes, nothing else. Intent
classification and prioritization stay a human/LLM step (SKILL.md Step 4).

This is an undocumented endpoint, not a published API with usage terms for
this — treat it as a courtesy, not a guarantee. Mitigations built in: a
realistic User-Agent, a fixed delay between requests (~0.35s), a hard cap of
3 seeds per run (100 requests/seed, up to 300 total, not thousands), and an
early abort if several requests in a row fail outright (signals blocking,
not just a query with no suggestions) rather than hammering a wall. Don't
run this in a scheduled/looped job or raise MAX_SEEDS without good reason —
it's an occasional research tool, not a monitoring pipeline.

Usage:
    python3 keyword_expand.py "whisper desktop" ["whispaste" ...]
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

USER_AGENT = "Mozilla/5.0 (compatible; seo-aso-optimizer/1.0)"
DELAY_SECONDS = 0.35
MAX_SEEDS = 3

QUESTION_WORDS = ["how", "what", "why", "when", "where", "who", "can", "does", "is", "will", "which"]
MODIFIERS = [
    "vs", "alternative", "free", "download", "price", "review", "reddit",
    "github", "open source", "for windows", "for mac", "for linux",
]
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_google_response(raw):
    """Firefox client shape: ["<seed>", ["sugg1", "sugg2", ...], [], {...}]"""
    data = json.loads(raw)
    return [s for s in data[1] if isinstance(s, str)]


def parse_youtube_response(raw):
    """JSONP: window.google.ac.h([...]) wrapping [text, [[text, weight, [codes]], ...], {...}] —
    a different item shape than the Firefox client, not a flat string list."""
    start = raw.index("(") + 1
    end = raw.rindex(")")
    data = json.loads(raw[start:end])
    return [item[0] for item in data[1] if isinstance(item, list) and item and isinstance(item[0], str)]


def google_autocomplete(query):
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "firefox", "q": query}
    )
    return parse_google_response(_get(url))


def youtube_autocomplete(query):
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "youtube", "ds": "yt", "q": query}
    )
    return parse_youtube_response(_get(url))


def build_queries(seed):
    queries = [seed]
    queries += [f"{seed} {letter}" for letter in LETTERS]
    queries += [f"{w} {seed}" for w in QUESTION_WORDS]
    queries += [f"{seed} {m}" for m in MODIFIERS]
    return queries


MAX_CONSECUTIVE_FAILURES = 4  # stop hammering an endpoint that looks blocked/down


def harvest(seed, sources=("google", "youtube")):
    found = set()
    consecutive_failures = 0
    made_a_request = False
    for query in build_queries(seed):
        ok = False
        for source, fn in (("google", google_autocomplete), ("youtube", youtube_autocomplete)):
            if source not in sources:
                continue
            # Pace every actual request, not just every query — two source
            # calls within the same query are still two requests to the
            # same endpoint family.
            if made_a_request:
                time.sleep(DELAY_SECONDS)
            made_a_request = True
            try:
                found.update(fn(query))
                ok = True  # a real response, even an empty suggestion list, counts as reachable
            except Exception:
                pass
        consecutive_failures = 0 if ok else consecutive_failures + 1
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            print(
                f"Stopping early: {consecutive_failures} consecutive fetch failures — "
                "the endpoint looks blocked or unreachable, not just query-specific. "
                "Don't retry in a tight loop; try again later.",
                file=sys.stderr,
            )
            break
    found.discard(seed)
    return sorted(found)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("seeds", nargs="+", help=f"up to {MAX_SEEDS} seed phrases")
    ap.add_argument("--sources", default="google,youtube")
    args = ap.parse_args()

    seeds = args.seeds[:MAX_SEEDS]
    requests_per_seed = len(build_queries("x")) * 2  # google + youtube; count is seed-independent
    if len(args.seeds) > MAX_SEEDS:
        print(
            f"Only using the first {MAX_SEEDS} seeds "
            f"({MAX_SEEDS * requests_per_seed} requests total is already the runtime budget).",
            file=sys.stderr,
        )
    sources = tuple(s.strip() for s in args.sources.split(","))

    for seed in seeds:
        results = harvest(seed, sources)
        print(f"# {seed} ({len(results)} unique suggestions)")
        for r in results:
            print(f"- {r}")
        print()


if __name__ == "__main__":
    main()
