#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0", "playwright>=1.40"]
# ///
"""aso-research dispatcher — deep Apple spine + LLM phase (slice 03).

Single entry point that turns a structured app-idea input into a written
report end to end:

    parse input → iTunes discovery → deep Apple channels
      (subtitle via Playwright, similar-apps hop, RSS charts, Reddit,
       Search-Suggest) → extract (YAKE + TF-IDF) → score
      (Competition/Relevance proxy) → serialize keywords.json /
      competition.json / run-config.yaml → prepare the LLM-input
      artefacts (H1 raw profiles + token-gated S1 representation) →
      write report.md

The **LLM subagent steps (H1/S1/S2/H2) are performed by the running agent**
(Claude-native — no external paid API, US19). Python only prepares,
constrains, measures, and assembles. Two extra stages wire the hybrid:

* ``--gate <run_dir>``    — deterministic: build the token-gated S1
  representation from the agent's H1 output + the score table + Reddit,
  measure/trim it, write ``llm/s1-input.json`` + ``llm/gate-report.json``.
* ``--assemble <run_dir>`` — deterministic: stitch the full 8-section
  ``report.md`` from the artefacts + the agent's ``llm/*.json`` subagent
  outputs (graceful fallback to deterministic sections when absent).

Every deep channel is never-blocking: a failing source is marked
"unavailable" and the pipeline continues. Run via ``uv run`` (pulls
PyYAML so YAML input works; Playwright is already installed locally).
Prints the absolute path of the written run directory on stdout.

Usage:
    uv run scripts/aso_research.py --input seed.yaml
    python3 scripts/aso_research.py --app-name "Habit Hero" \
        --description "Gamified habit tracker" --seed-keyword habit \
        --seed-keyword tracker --output-dir /tmp/aso
    python3 scripts/aso_research.py --gate /tmp/aso/<run-id>
    python3 scripts/aso_research.py --assemble /tmp/aso/<run-id>
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import brand as BRAND  # noqa: E402
import cache as CACHE  # noqa: E402
import collect  # noqa: E402
import condense  # noqa: E402
import diff as DIFF  # noqa: E402
import input_config  # noqa: E402
import itunes  # noqa: E402
import llm_gate  # noqa: E402
import report  # noqa: E402
import run_id  # noqa: E402
import serialize  # noqa: E402
import stages  # noqa: E402


# Subagent-output filenames the agent writes (read by --gate / --assemble).
_H1_CONDENSED = "llm/h1-condensed.json"
_S1_INPUT = "llm/s1-input.json"
_S1_ANALYSIS = "llm/s1-analysis.json"
_S2_LISTING = "llm/s2-listing.json"
_H2_CROSSCHECK = "llm/h2-crosscheck.json"
# Slice 04: Play listing (separate store model, same S2/H2 mechanism).
_S2_LISTING_PLAY = "llm/s2-listing-play.json"
_H2_CROSSCHECK_PLAY = "llm/h2-crosscheck-play.json"


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aso-research",
        description="ASO research — deep Apple spine + LLM phase (slice 03).",
    )
    p.add_argument("--input", help="structured input file (YAML or JSON)")
    p.add_argument("--app-name", help="app name (required unless --input)")
    p.add_argument("--description", help="app description (required unless --input)")
    p.add_argument("--category", default=None, help="category guess (default: other)")
    p.add_argument("--country", default=None, help="store country (default: de)")
    p.add_argument("--language", default=None, help="listing language (default: de)")
    p.add_argument("--own-app-id", default=None, help="Modus A: your own app store id")
    p.add_argument(
        "--seed-keyword",
        action="append",
        dest="seed_keywords",
        default=None,
        help="seed keyword (repeatable, up to 5)",
    )
    p.add_argument("--gate-token-limit", type=int, default=None)
    p.add_argument("--output-dir", default=None, help="run-output root (default: <cwd>/.aso-research)")
    p.add_argument("--cache-dir", default=CACHE.DEFAULT_CACHE_DIR, help=f"HTTP cache dir (default: {CACHE.DEFAULT_CACHE_DIR})")
    p.add_argument("--fresh", action="store_true", help="ignore cache, re-pull live")
    p.add_argument(
        "--compare-last",
        action="store_true",
        help="after the run, diff against the most recent prior run of the "
             "same app in the output dir (writes diff-vs-last.md)",
    )
    p.add_argument("--max-queries", type=int, default=3, help="cap on iTunes queries (default: 3)")
    p.add_argument(
        "--brand-glossary", metavar="PATH",
        dest="brand_glossary",
        default=None,
        help="path to a brand glossar (overrides convention discovery)",
    )
    # --- slice 03 LLM-phase stages ---
    p.add_argument(
        "--gate", metavar="RUN_DIR",
        help="build the token-gated S1 representation from the agent's H1 output",
    )
    p.add_argument(
        "--assemble", metavar="RUN_DIR",
        help="assemble the full 8-section report.md from artefacts + llm/*.json",
    )
    return p


def _merge_file_and_flags(args: argparse.Namespace) -> dict:
    raw: dict = {}
    if args.input:
        raw = input_config.load_input_file(args.input)
    # Flags override / supplement the file.
    if args.app_name is not None:
        raw["app_name"] = args.app_name
    if args.description is not None:
        raw["description"] = args.description
    if args.category is not None:
        raw["category"] = args.category
    if args.country is not None:
        raw["country"] = args.country
    if args.language is not None:
        raw["language"] = args.language
    if args.own_app_id is not None:
        raw["own_app_id"] = args.own_app_id
    if args.seed_keywords:
        raw["seed_keywords"] = args.seed_keywords
    if args.gate_token_limit is not None:
        raw["gate_token_limit"] = args.gate_token_limit
    if args.output_dir is not None:
        raw["output_dir"] = args.output_dir
    return raw


def _load_json(path: str):
    """Load JSON if the file exists, else None."""
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _gate_token_limit(config: dict) -> int:
    gtl = config.get("gate_token_limit")
    if isinstance(gtl, int) and gtl > 0:
        return gtl
    return llm_gate.DEFAULT_GATE_TOKEN_LIMIT


def _run_gate(run_dir: str) -> int:
    """Stage 50: build the token-gated S1 representation deterministically.

    Reads the agent's H1 output (``llm/h1-condensed.json``) + the scored
    keywords + Reddit summaries + the resolved config, assembles the
    representation, measures/trims it under the token limit, and writes
    ``llm/s1-input.json`` + ``llm/gate-report.json``.
    """
    condensed_profiles = _load_json(os.path.join(run_dir, _H1_CONDENSED))
    if not condensed_profiles:
        print(
            f"error: {_H1_CONDENSED} not found in {run_dir} — run the H1 "
            f"Metadata-Condenser (Haiku) subagent first.",
            file=sys.stderr,
        )
        return 2
    keywords = _load_json(os.path.join(run_dir, "keywords.json")) or []
    reddit_threads = _load_json(os.path.join(run_dir, "reddit-threads.json")) or []
    ms_entries = _load_json(os.path.join(run_dir, "ms-entries.json")) or []
    brand_conflicts = _load_json(os.path.join(run_dir, "brand-conflicts.json")) or []
    config = _load_json(os.path.join(run_dir, "run-config.json")) or {}

    rep = condense.build_llm_input(
        condensed_profiles, keywords, reddit_threads, config=config, ms_entries=ms_entries,
        brand_conflicts=brand_conflicts,
    )
    trimmed, gate_report = llm_gate.apply_token_gate(rep, _gate_token_limit(config))
    os.makedirs(os.path.join(run_dir, "llm"), exist_ok=True)
    serialize.dump_json(trimmed, os.path.join(run_dir, _S1_INPUT))
    serialize.dump_json(gate_report, os.path.join(run_dir, "llm/gate-report.json"))

    tag = "trimmed" if gate_report["trimmed"] else "within budget"
    print(
        f"[aso-research] gate: {tag} "
        f"({gate_report['measured_before']} -> {gate_report['measured_after']} "
        f"tokens, limit {gate_report['limit']}, "
        f"{gate_report['profiles_kept']}/{gate_report['profiles_before']} profiles)",
        file=sys.stderr,
    )
    print(os.path.abspath(os.path.join(run_dir, _S1_INPUT)))
    return 0


def _assemble(run_dir: str) -> int:
    """Stage 80: stitch the full 8-section report from artefacts + llm/*.json."""
    keywords = _load_json(os.path.join(run_dir, "keywords.json")) or []
    competitors = _load_json(os.path.join(run_dir, "competition.json")) or []
    config = _load_json(os.path.join(run_dir, "run-config.json")) or {}
    summary = _load_json(os.path.join(run_dir, "run-summary.json")) or {}
    reddit_threads = _load_json(os.path.join(run_dir, "reddit-threads.json")) or []
    ms_entries = _load_json(os.path.join(run_dir, "ms-entries.json")) or []
    source_status = summary.get("source_status") or {}
    brand_conflicts = _load_json(os.path.join(run_dir, "brand-conflicts.json")) or []

    # Agent-produced subagent outputs (all optional → deterministic fallback).
    s1_input = _load_json(os.path.join(run_dir, _S1_INPUT)) or {}
    condensed_profiles = (
        _load_json(os.path.join(run_dir, _H1_CONDENSED))
        or s1_input.get("condensed_profiles")
        or []
    )
    s1_output = _load_json(os.path.join(run_dir, _S1_ANALYSIS))
    s2_output = _load_json(os.path.join(run_dir, _S2_LISTING))
    h2_output = _load_json(os.path.join(run_dir, _H2_CROSSCHECK))
    s2_play_output = _load_json(os.path.join(run_dir, _S2_LISTING_PLAY))
    h2_play_output = _load_json(os.path.join(run_dir, _H2_CROSSCHECK_PLAY))

    now = datetime.datetime.now()
    report_md = report.build_report(
        config, competitors, keywords,
        now=now, source_status=source_status, reddit_threads=reddit_threads,
        condensed_profiles=condensed_profiles,
        s1_output=s1_output, s2_output=s2_output, h2_output=h2_output,
        s2_play_output=s2_play_output, h2_play_output=h2_play_output,
        ms_entries=ms_entries,
        brand_conflicts=brand_conflicts,
    )
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report_md)
    print(f"[aso-research] assembled report.md in {run_dir}", file=sys.stderr)
    print(os.path.abspath(os.path.join(run_dir, "report.md")))
    return 0


def _write_report(run_dir, config, competitors, keywords, source_status, reddit_threads, now, ms_entries=None, brand_conflicts=None):
    """Write report.md from whatever subagent outputs already exist (if any)."""
    condensed_profiles = _load_json(os.path.join(run_dir, _H1_CONDENSED)) or []
    s1_output = _load_json(os.path.join(run_dir, _S1_ANALYSIS))
    s2_output = _load_json(os.path.join(run_dir, _S2_LISTING))
    h2_output = _load_json(os.path.join(run_dir, _H2_CROSSCHECK))
    s2_play_output = _load_json(os.path.join(run_dir, _S2_LISTING_PLAY))
    h2_play_output = _load_json(os.path.join(run_dir, _H2_CROSSCHECK_PLAY))
    report_md = report.build_report(
        config, competitors, keywords,
        now=now, source_status=source_status, reddit_threads=reddit_threads,
        condensed_profiles=condensed_profiles,
        s1_output=s1_output, s2_output=s2_output, h2_output=h2_output,
        s2_play_output=s2_play_output, h2_play_output=h2_play_output,
        ms_entries=ms_entries or [],
        brand_conflicts=brand_conflicts or [],
    )
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report_md)


# Channels the pipeline exercised (kept stable for run-summary consumers:
# --assemble reads source_status, --compare-last reads keywords/competition).
_RUN_CHANNELS = [
    "itunes_search",
    "apple_subtitle",
    "apple_similar",
    "apple_rss_charts",
    "reddit",
    "apple_search_suggest",
    "play_search",
    "play_charts",
    "play_similar",
    "play_search_suggest",
    "ms_best_effort",
]


def _build_run_summary(
    run_id_str, competitors, keywords, ms_entries, source_status, has_play, stage_timing
):
    """Pure run-summary builder (testable without network).

    Carries the existing machine-readable fields plus ``stage_timing`` so
    the ≤30-min soft target (US12) is observable per stage.
    """
    return {
        "run_id": run_id_str,
        "platforms": (["apple", "play"] if has_play else ["apple"]),
        "channels": list(_RUN_CHANNELS),
        "competitor_count": len(competitors),
        "keyword_count": len(keywords),
        "ms_qualitative_count": len(ms_entries),
        "source_status": source_status,
        "stage_timing": stage_timing,
    }


def run(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)

    # --- slice 03 LLM-phase stages (no collection) ---
    if args.gate:
        return _run_gate(args.gate)
    if args.assemble:
        return _assemble(args.assemble)

    raw = _merge_file_and_flags(args)
    try:
        config = input_config.parse_input(raw)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    now = datetime.datetime.now()
    run_id_str = run_id.generate_run_id(now, config["app_name"])
    output_root = config["output_dir"] or os.path.join(os.getcwd(), ".aso-research")
    run_dir = os.path.join(output_root, run_id_str)
    os.makedirs(run_dir, exist_ok=True)

    print(f"[aso-research] run-id: {run_id_str}", file=sys.stderr)
    print(f"[aso-research] run-dir: {run_dir}", file=sys.stderr)
    print(f"[aso-research] cache-dir: {args.cache_dir}", file=sys.stderr)
    if args.fresh:
        print("[aso-research] --fresh: bypassing cache + stage checkpoints", file=sys.stderr)

    # Stages are idempotent (slice 06): each skips if its checkpoint is fresh,
    # so a crash at stage N resumes at N (US9). --fresh bypasses every check.
    runner = stages.StageRunner(run_dir, fresh=args.fresh)
    seed_terms = config.get("seed_keywords") or []
    country = config.get("country", "de")

    # --- Stage: collect (the crawl — Apple + Play + MS; never-blocking) ---
    def _collect():
        data = itunes.discover(
            config, cache_dir=args.cache_dir, fresh=args.fresh,
            max_queries=args.max_queries,
        )
        competitors = data["competitors"]
        print(
            f"[aso-research] iTunes discovered {len(competitors)} competitor(s)",
            file=sys.stderr,
        )
        deep = collect.collect_apple(
            config, competitors, seed_terms=seed_terms, country=country,
            cache_dir=args.cache_dir, fresh=args.fresh,
        )
        competitors = deep["competitors"]
        suggest = deep["suggest_terms"]
        src_status = deep["source_status"]
        reddit_threads = deep["reddit_threads"]
        for src, entry in src_status.items():
            if not collect._status_is_ok(entry):
                reason = entry.get("reason", "unavailable") if isinstance(entry, dict) else entry
                print(f"[aso-research] source {src}: unavailable — {reason}", file=sys.stderr)
        print(
            f"[aso-research] deep apple: {len(competitors)} competitors "
            f"({sum(1 for c in competitors if c.get('discovery') == 'niche_similar')} niche), "
            f"{len(suggest)} suggest terms",
            file=sys.stderr,
        )
        play = collect.collect_play(
            config, seed_terms=seed_terms, country=country,
            cache_dir=args.cache_dir, fresh=args.fresh,
        )
        play_competitors = play["competitors"]
        play_suggest = play["suggest_terms"]
        for src, entry in play["source_status"].items():
            src_status[src] = entry
            if not collect._status_is_ok(entry):
                reason = entry.get("reason", "unavailable") if isinstance(entry, dict) else entry
                print(f"[aso-research] source {src}: unavailable — {reason}", file=sys.stderr)
        competitors = competitors + play_competitors
        suggest = suggest + [s for s in play_suggest if s not in suggest]
        print(
            f"[aso-research] deep play: {len(play_competitors)} competitors, "
            f"{len(play_suggest)} play suggest terms "
            f"({len(competitors)} total competitors, {len(suggest)} suggest)",
            file=sys.stderr,
        )
        ms = collect.collect_ms(
            config, seed_terms=seed_terms, country=country,
            cache_dir=args.cache_dir, fresh=args.fresh,
        )
        ms_entries = ms["ms_entries"]
        for src, entry in ms["source_status"].items():
            src_status[src] = entry
            if not collect._status_is_ok(entry):
                reason = entry.get("reason", "unavailable") if isinstance(entry, dict) else entry
                print(f"[aso-research] source {src}: unavailable — {reason}", file=sys.stderr)
        print(
            f"[aso-research] ms best-effort: {len(ms_entries)} qualitative entr(y/ies) "
            f"(not scored; feeds S1 as qualitative context)",
            file=sys.stderr,
        )
        # Human-facing artefacts: written when the stage runs and left
        # untouched on a skip (so a warm re-run keeps them byte-identical).
        serialize.dump_json(competitors, os.path.join(run_dir, "competition.json"))
        serialize.dump_json(reddit_threads, os.path.join(run_dir, "reddit-threads.json"))
        serialize.dump_json(ms_entries, os.path.join(run_dir, "ms-entries.json"))
        return {
            "competitors": competitors,
            "suggest_terms": suggest,
            "reddit_threads": reddit_threads,
            "ms_entries": ms_entries,
            "source_status": src_status,
            "has_play": bool(play_competitors),
        }

    collect_out, collect_status = runner.stage(
        "collect", _collect, ttl=stages.DEFAULT_COLLECT_TTL
    )
    competitors = collect_out["competitors"]
    suggest_terms = collect_out["suggest_terms"]
    reddit_threads = collect_out["reddit_threads"]
    ms_entries = collect_out["ms_entries"]
    source_status = collect_out["source_status"]
    has_play = collect_out["has_play"]
    print(f"[aso-research] collect stage: {collect_status}", file=sys.stderr)

    # --- Stage: score (deterministic extract -> score over the corpus) ---
    def _score():
        scored = collect.extract_and_score(competitors, config, suggest_terms=suggest_terms)
        serialize.dump_json(scored["keywords"], os.path.join(run_dir, "keywords.json"))
        return {"keywords": scored["keywords"]}

    score_out, score_status = runner.stage("score", _score, ttl=stages.DEFAULT_COMPUTE_TTL)
    keywords = score_out["keywords"]
    print(
        f"[aso-research] scored {len(keywords)} keyword(s) ({score_status})",
        file=sys.stderr,
    )

    # --- Brand conflict detection (pure, no stage checkpoint) ---
    brand_conflicts: list = []
    glossar_path = BRAND.resolve_glossar(
        os.getcwd(), flag_path=args.brand_glossary,
    )
    if glossar_path:
        glossar = BRAND.parse_glossar(glossar_path)
        brand_conflicts = BRAND.detect_conflicts(keywords, glossar)
        serialize.dump_json(
            brand_conflicts, os.path.join(run_dir, "brand-conflicts.json"),
        )
        print(
            f"[aso-research] brand: {len(brand_conflicts)} conflict(s) "
            f"in {glossar_path}",
            file=sys.stderr,
        )
    else:
        print("[aso-research] brand: no glossar found — skipping", file=sys.stderr)

    # --- Stage: llm-inputs (run-config + H1 raw profiles) ---
    def _llm_inputs():
        run_config = {k: config[k] for k in input_config.CANONICAL_KEYS}
        with open(os.path.join(run_dir, "run-config.yaml"), "w", encoding="utf-8") as fh:
            fh.write(serialize.dumps_yaml(run_config))
        serialize.dump_json(run_config, os.path.join(run_dir, "run-config.json"))
        h1_input = condense.prepare_h1_input(competitors, own_app_id=config.get("own_app_id"))
        serialize.dump_json(h1_input, os.path.join(run_dir, "llm-input/h1-input.json"))
        return {"h1_input_count": len(h1_input)}

    runner.stage("llm-inputs", _llm_inputs, ttl=stages.DEFAULT_COMPUTE_TTL)

    # --- Stage: report (terminal; always runs — timestamp differs by design) ---
    def _report():
        _write_report(
            run_dir, config, competitors, keywords, source_status,
            reddit_threads, now, ms_entries=ms_entries,
            brand_conflicts=brand_conflicts,
        )
        return {}

    runner.stage("report", _report, ttl=stages.DEFAULT_COMPUTE_TTL, skippable=False)
    if not os.path.exists(os.path.join(run_dir, _H1_CONDENSED)):
        print(
            "[aso-research] next: run H1 → `--gate <run-dir>` → S1 → S2 → H2 "
            "→ `--assemble <run-dir>` (see pipeline.md LLM phase)",
            file=sys.stderr,
        )

    # --- run-summary.json (machine-readable; carries per-stage timing) ---
    summary = _build_run_summary(
        run_id_str, competitors, keywords, ms_entries, source_status,
        has_play, runner.timing(),
    )
    serialize.dump_json(summary, os.path.join(run_dir, "run-summary.json"))

    # --- --compare-last: diff vs the most recent prior run of this app ---
    if args.compare_last:
        diff_md = DIFF.compare_last(run_dir, output_root, run_id_str)
        with open(os.path.join(run_dir, "diff-vs-last.md"), "w", encoding="utf-8") as fh:
            fh.write(diff_md)
        has_deltas = "no prior run" not in diff_md.lower()
        tag = "deltas written" if has_deltas else "no prior run to diff"
        print(f"[aso-research] diff-vs-last.md: {tag}", file=sys.stderr)

    # Absolute path on stdout (machine-parseable).
    print(os.path.abspath(run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(run())
