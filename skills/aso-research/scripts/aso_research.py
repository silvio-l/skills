#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""aso-research dispatcher — skeleton slice (01).

Single entry point that turns a structured app-idea input into a written
report end to end:

    parse input → discover (iTunes Search, cached) → extract+score
      → serialize keywords.json / competition.json / run-config.yaml
      → write report.md

Run via ``uv run`` (pulls PyYAML so YAML input works) or plain
``python3`` (JSON input only when PyYAML is absent). Prints the absolute
path of the written run directory on stdout.

Usage:
    uv run scripts/aso_research.py --input seed.yaml
    python3 scripts/aso_research.py --app-name "Habit Hero" \
        --description "Gamified habit tracker" --seed-keyword habit \
        --seed-keyword tracker --output-dir /tmp/aso
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import cache as CACHE  # noqa: E402
import input_config  # noqa: E402
import itunes  # noqa: E402
import report  # noqa: E402
import run_id  # noqa: E402
import serialize  # noqa: E402


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aso-research",
        description="ASO research — Apple-only skeleton pipeline (slice 01).",
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
    p.add_argument("--max-queries", type=int, default=3, help="cap on iTunes queries (default: 3)")
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


def run(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)
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

    data = itunes.discover(
        config,
        cache_dir=args.cache_dir,
        fresh=args.fresh,
        max_queries=args.max_queries,
    )

    competitors = data["competitors"]
    keywords = data["keywords"]
    print(f"[aso-research] discovered {len(competitors)} competitor(s)", file=sys.stderr)

    # --- side artefacts (deterministic; no timestamp inside) ---
    serialize.dump_json(keywords, os.path.join(run_dir, "keywords.json"))
    serialize.dump_json(competitors, os.path.join(run_dir, "competition.json"))
    serialize.dump_json(
        {
            "run_id": run_id_str,
            "platforms": ["apple"],
            "channels": ["itunes_search"],
            "competitor_count": len(competitors),
            "keyword_count": len(keywords),
        },
        os.path.join(run_dir, "run-summary.json"),
    )

    # --- run-config.yaml echoes the resolved input ---
    run_config = {k: config[k] for k in input_config.CANONICAL_KEYS}
    with open(os.path.join(run_dir, "run-config.yaml"), "w", encoding="utf-8") as fh:
        fh.write(serialize.dumps_yaml(run_config))

    # --- report.md (timestamp differs between runs by design) ---
    report_md = report.build_report(config, competitors, keywords, now=now)
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report_md)

    # Absolute path on stdout (machine-parseable).
    print(os.path.abspath(run_dir))
    return 0


if __name__ == "__main__":
    sys.exit(run())
