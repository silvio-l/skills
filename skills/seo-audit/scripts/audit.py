#!/usr/bin/env python3
"""seo-audit dispatcher.

Phase order: inventory → brand-konsistenz → (external probes) →
synthesis → write report → (push, opt-in).

External probes run when `--url <url>` is passed. Push (slice 03) runs
when `--push` is passed; `--push --dry-run` only renders the plan.

Usage:
    python3 audit.py --root <repo-root> [--report-dir <dir>]
                     [--dist <dist-dir>] [--quick] [--push]
                     [--dry-run] [--compare-last]

Defaults:
    --report-dir defaults to `<root>/.scratch/seo-audit/`
    --dist       defaults to `<root>/dist/`
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import inventory as INV  # noqa: E402
import glossary_parser as GP  # noqa: E402
import positioning_brief as PB  # noqa: E402
import brand_scan as BS  # noqa: E402
import geo_scan as GS  # noqa: E402
import schema_scan as SS  # noqa: E402
import synthesis as SY  # noqa: E402
from probes import probe as PROBE  # noqa: E402
from push import push as PUSH  # noqa: E402
from setup import doctor as DOCTOR  # noqa: E402
from setup import verify as VERIFY  # noqa: E402
from setup import setup_indexnow as SETUP_INDEXNOW  # noqa: E402
from setup import setup_pagespeed as SETUP_PAGESPEED  # noqa: E402
from setup import setup_bing as SETUP_BING  # noqa: E402
from setup import setup_gsc as SETUP_GSC  # noqa: E402

SETUP_TOOLS = ("indexnow", "pagespeed", "bing", "gsc")

GENERATOR_VERSION = "v1.1.0"
TEMPLATE_PATH = os.path.join(
    os.path.dirname(HERE), "templates", "report.md"
)


# --- dotenv auto-loader ----------------------------------------------------
#
# Lets users keep API keys in `<root>/admin.env` instead of remembering to
# `source admin.env` before every audit. Keys already present in the live
# environment always win — the loader never overrides the shell.

DEFAULT_DOTENV_FILES = ("admin.env", ".env")


def _parse_dotenv(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines from dotenv-style text.

    Ignores blank lines and full-line `#` comments, strips an optional
    `export ` prefix and one layer of surrounding single/double quotes,
    and splits on the first `=` only — so `=` and inline `#` inside a value
    survive. Lines without `=` and lines with an empty key are skipped.
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


def _load_dotenv_files(root, extra_files=None, env=None):
    """Load dotenv files into `env`, returning ``[(path, keys_added), ...]``.

    Order of precedence: explicit `extra_files` (e.g. ``--env-file``) first,
    then the fixed `DEFAULT_DOTENV_FILES` resolved under `root`. Each existing
    file is parsed exactly once (duplicate paths are de-duplicated). A key is
    only set when it is not already present in `env`, so live shell values and
    earlier files both win over later ones. Missing or unreadable files are
    skipped silently. `env` defaults to ``os.environ``.
    """
    if env is None:
        env = os.environ
    candidates = [os.path.abspath(p) for p in (extra_files or [])]
    candidates += [
        os.path.abspath(os.path.join(root, name))
        for name in DEFAULT_DOTENV_FILES
    ]

    loaded = []
    seen: set[str] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                pairs = _parse_dotenv(f.read())
        except OSError:
            continue
        added = 0
        for key, value in pairs.items():
            if key not in env:
                env[key] = value
                added += 1
        loaded.append((path, added))
    return loaded


def _load_template() -> str:
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _render_findings_by_category(synth: dict) -> str:
    if not synth["findings"]:
        return "_Keine Findings._"
    by_cat: dict = {}
    for f in synth["findings"]:
        by_cat.setdefault(f["category"], []).append(f)
    parts = []
    for cat in sorted(by_cat):
        parts.append(f"### {cat}\n")
        parts.append(
            "| Score | Datei:Zeile | Match | Vorschlag | Begründung |\n"
            "| ----- | ----------- | ----- | --------- | ---------- |"
        )
        for f in by_cat[cat]:
            loc = f"`{f['file_path']}:{f['line_number']}`"
            parts.append(
                f"| {f['score']} | {loc} | `{f['match']}` | "
                f"{f.get('suggested_replacement', '')} | "
                f"{f.get('rationale', '')} |"
            )
        parts.append("")
    return "\n".join(parts).rstrip()


def _render_recommendations(synth: dict) -> str:
    if not synth["findings"]:
        return "_Nichts zu tun — sauberer Lauf._"
    lines = []
    for i, f in enumerate(synth["findings"][:10], start=1):
        lines.append(
            f"{i}. **{f['match']}** in `{f['file_path']}:{f['line_number']}` "
            f"(Score {f['score']}) — ersetzen durch "
            f"**{f.get('suggested_replacement', '?')}**."
        )
    if len(synth["findings"]) > 10:
        lines.append(f"\n_(+{len(synth['findings']) - 10} weitere Findings.)_")
    return "\n".join(lines)


def _render_dimensions_breakdown(synth: dict) -> str:
    """Render the dimensions breakdown as a Markdown table (German header)."""
    bd = synth.get("dimensions_breakdown", {})
    if not bd:
        return "_Keine Dimensions-Daten._"
    lines = [
        "| Dimension | Score |",
        "| --------- | ----- |",
    ]
    for dim in sorted(bd):
        lines.append(f"| {dim} | {bd[dim]}/100 |")
    return "\n".join(lines)


def _render_diff(prior_path: str | None) -> str:
    if not prior_path:
        return "_Kein vorheriger Lauf zum Vergleich._"
    return f"_Vergleich gegen `{os.path.basename(prior_path)}` (TBD)._"


def _summary_prose(synth: dict, inv: dict) -> str:
    if not synth["findings"]:
        return (
            f"Der Lauf gegen `{inv['root']}` ist sauber — kein Anti-Vokabular "
            f"im gebauten HTML."
        )
    top = synth["findings"][0]
    return (
        f"Top-Befund: `{top['match']}` in "
        f"`{top['file_path']}:{top['line_number']}` (Score {top['score']}). "
        f"Empfohlener Ersatz: **{top.get('suggested_replacement', '?')}**."
    )


def _previous_report(report_dir: str, today: str) -> str | None:
    if not os.path.isdir(report_dir):
        return None
    prior = sorted(
        f for f in os.listdir(report_dir)
        if f.startswith("seo-audit-") and f.endswith(".md")
        and not f.startswith(f"seo-audit-{today}")
    )
    return os.path.join(report_dir, prior[-1]) if prior else None


def _render(template: str, ctx: dict) -> str:
    out = template
    for key, val in ctx.items():
        out = out.replace("{{" + key + "}}", str(val))
    return out


def _resolve_public_dir(root: str, dist: str) -> str:
    """Return the framework-appropriate `public/` path for push output.

    Astro builds to `dist/`, Next to `out/`, static sites use a
    top-level `public/`. We prefer dist if it exists (matches the
    brand-scan input), falling back to `public/`, then `out/`, then
    the dist path itself even if missing.
    """
    candidates = [
        dist,
        os.path.join(root, "public"),
        os.path.join(root, "out"),
    ]
    for p in candidates:
        if p and os.path.isdir(p):
            return p
    return dist


def _domain_doc_path(root: str, inv: dict) -> str | None:
    """Resolve the domain doc to an absolute path."""
    doc = inv.get("domain_doc") or ""
    if not doc:
        return None
    full = os.path.join(root, doc)
    return full if os.path.isfile(full) else None


def _public_host_from_urls(urls) -> str:
    """Extract bare host from the first --url for IndexNow verify."""
    if not urls:
        return ""
    from urllib.parse import urlparse
    parsed = urlparse(urls[0])
    return parsed.netloc


def _run_setup_mode(args: argparse.Namespace, root: str, dist: str) -> int:
    """Dispatch a single --setup wizard. Idempotent; no input()."""
    inv = INV.inventory(root)
    public_dir = _resolve_public_dir(root, dist)
    tool = args.setup
    platform = sys.platform
    browser_opener = _real_browser_opener if platform == "darwin" else None

    if tool == "indexnow":
        plan = SETUP_INDEXNOW.plan(
            os.environ,
            public_dir=pathlib_path(public_dir) if public_dir else None,
            force=args.force,
        )
        result = SETUP_INDEXNOW.execute(plan)
        print(SETUP_INDEXNOW.render(plan, result))
    elif tool == "pagespeed":
        plan = SETUP_PAGESPEED.plan(os.environ)
        result = SETUP_PAGESPEED.execute(
            plan, platform=platform, browser_opener=browser_opener,
        )
        print(SETUP_PAGESPEED.render(plan, result))
    elif tool == "bing":
        plan = SETUP_BING.plan(os.environ)
        result = SETUP_BING.execute(
            plan, platform=platform, browser_opener=browser_opener,
        )
        print(SETUP_BING.render(plan, result))
    elif tool == "gsc":
        plan = SETUP_GSC.plan(os.environ)
        result = SETUP_GSC.execute(
            plan, platform=platform, browser_opener=browser_opener,
        )
        print(SETUP_GSC.render(plan, result))
    else:  # pragma: no cover — argparse already rejects unknown values
        print(f"error: unknown setup tool: {tool}", file=sys.stderr)
        return 2
    return 0


def pathlib_path(p):
    import pathlib
    return pathlib.Path(p)


def _real_browser_opener(url: str) -> None:  # pragma: no cover — live only
    import subprocess
    subprocess.run(["open", url], check=False)


def _real_http_client(method, url, headers, body):  # pragma: no cover — live only
    from push import _http
    return _http.real_client(method, url, headers, body)


def run(args: argparse.Namespace) -> int:
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"error: --root does not exist: {root}", file=sys.stderr)
        return 2

    # Auto-load API keys from <root>/admin.env (and any --env-file) before any
    # mode reads os.environ. Out-of-band on stderr; never overrides the shell.
    for path, added in _load_dotenv_files(root, extra_files=args.env_file):
        print(
            f"seo-audit: loaded {added} key(s) from "
            f"{os.path.relpath(path, root)}",
            file=sys.stderr,
        )

    if args.dry_run and not args.push:
        print("error: --dry-run is only meaningful with --push.",
              file=sys.stderr)
        return 2

    if args.setup and (args.doctor or args.verify):
        print(
            "error: --setup is a single-tool wizard; "
            "run --doctor / --verify separately.",
            file=sys.stderr,
        )
        return 2

    if args.force and not args.setup:
        print("error: --force only applies to --setup indexnow.",
              file=sys.stderr)
        return 2

    dist = args.dist or os.path.join(root, "dist")

    # ----- Setup wizard (single-tool, no audit flow) -----
    if args.setup:
        return _run_setup_mode(args, root, dist)

    report_dir = args.report_dir or os.path.join(root, ".scratch", "seo-audit")
    os.makedirs(report_dir, exist_ok=True)

    # ----- Doctor mode -----
    if args.doctor:
        public_dir = _resolve_public_dir(root, dist)
        report = DOCTOR.run(
            env=os.environ,
            root=pathlib_path(root),
            public_dir=pathlib_path(public_dir) if public_dir else None,
        )
        print(DOCTOR.render(report))

    # ----- Verify mode (may run together with --doctor) -----
    if args.verify:
        clients = {
            "pagespeed": _real_http_client,
            "bing": _real_http_client,
            "indexnow": _real_http_client,
            # gsc client stays unwired — the agent calls the MCP tool itself.
        }
        results = VERIFY.run(
            env=os.environ,
            public_host=_public_host_from_urls(args.url),
            clients=clients,
        )
        print(VERIFY.render(results))

    if args.doctor or args.verify:
        return 0

    inv = INV.inventory(root)
    glossary = GP.load_glossary_from_repo(root)

    # Load positioning brief BEFORE any finding-producing phase.
    # The brief NEVER touches the Finding list — it only flows into report ctx.
    brief = PB.load_brief(getattr(args, "brief", None), root)

    findings = []
    if os.path.isdir(dist):
        for f in BS.scan_directory(dist, glossary):
            f = dict(f)
            f.setdefault("category", "brand")
            f.setdefault("severity", "med")
            f.setdefault("user_impact", 2)
            f.setdefault("fix_effort", 1)
            f.setdefault("dimension", "brand")
            f.setdefault("track", "technical")
            findings.append(f)

    # GEO/AEO phase — slice 02. Runs fully offline over built HTML.
    # Reduced to fast subset when --quick is passed.
    if os.path.isdir(dist):
        for f in GS.scan_directory(dist, quick=args.quick):
            f = dict(f)
            f.setdefault("category", "geo")
            f.setdefault("severity", "med")
            f.setdefault("user_impact", 2)
            f.setdefault("fix_effort", 2)
            f.setdefault("dimension", "geo")
            f.setdefault("track", "strategic")
            findings.append(f)

    # Schema phase — slice 03. Runs fully offline over built HTML.
    # Checks JSON-LD presence, tolerant extraction, required fields,
    # deprecated types, and sameAs consistency (GEO signal).
    if os.path.isdir(dist):
        for f in SS.scan_directory(dist):
            f = dict(f)
            f.setdefault("category", "schema")
            f.setdefault("severity", "med")
            f.setdefault("user_impact", 2)
            f.setdefault("fix_effort", 2)
            f.setdefault("dimension", "schema")
            f.setdefault("track", "technical")
            findings.append(f)

    # External probes — slice 04. Run only when at least one URL is
    # supplied; the rest of the pipeline is offline-friendly.
    if args.url:
        probe_findings = PROBE.run(args.url, quick=args.quick) or []
        findings.extend(probe_findings)

    synth = SY.synthesize(findings)

    today = datetime.date.today().strftime("%Y-%m-%d")
    prior = _previous_report(report_dir, today) if args.compare_last else None

    if not synth["groups"]:
        top_category = "-"
    else:
        top_category = max(synth["groups"], key=lambda g: g["count"])["category"]

    ctx = {
        "date": today,
        "root": inv["root"],
        "framework": inv["framework"] or "unknown",
        "domain_doc": inv["domain_doc"] or "(none)",
        "pages_count": len(inv["pages"]),
        "glossary_count": len(glossary),
        "findings_count": len(synth["findings"]),
        "top_category": top_category,
        "headline_score": synth.get("headline_score", 100.0),
        "dimensions_breakdown": _render_dimensions_breakdown(synth),
        "summary_prose": _summary_prose(synth, inv),
        "findings_by_category": _render_findings_by_category(synth),
        "diff_section": _render_diff(prior),
        "recommendations": _render_recommendations(synth),
        "generator_version": GENERATOR_VERSION,
        # Positioning-brief context — purely additive; never alters findings.
        "brief_status": PB.render_status(brief),
        "brief_content": (
            brief["content"]
            if brief["content"]
            else "_Kein Positioning-Brief geladen — Empfehlungen ohne Marken-Kontext._"
        ),
    }

    rendered = _render(_load_template(), ctx)
    out_path = os.path.join(report_dir, f"seo-audit-{today}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(out_path)

    if args.push:
        public_dir = _resolve_public_dir(root, dist)
        ctx_path = _domain_doc_path(root, inv)
        site_url = args.url[0] if args.url else ""
        urls = list(args.url) if args.url else []
        state_dir = report_dir  # reuse report dir for the rate-limit counter
        plans = PUSH.plan_all(
            public_dir=public_dir,
            urls=urls,
            site_url=site_url,
            context_path=ctx_path or os.path.join(root, "CONTEXT.md"),
            state_dir=state_dir,
            env=os.environ,
        )
        if args.dry_run:
            print(PUSH.render_dry_run(plans))
        else:
            print(
                "push plan ready. Confirm operations interactively, "
                "then call push.execute_all(...) with the chosen confirmations. "
                "See skills/seo-audit/push.md §Live-Smoke for the shell snippet.",
                file=sys.stderr,
            )
            print(PUSH.render_dry_run(plans))

    return 0


def parse_args(argv) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="seo-audit",
        description="Local-first SEO audit: inventory, brand-konsistenz, "
                    "synthesis, report.",
    )
    p.add_argument("--root", required=True,
                   help="Repository root to audit.")
    p.add_argument("--brief", default=None, metavar="PATH",
                   help="Path to a Markdown positioning brief. Provides brand "
                        "context for recommendations without affecting findings. "
                        "Auto-discovered from <root>/.seo/positioning.md or a "
                        "<!-- seo:brief --> section in <root>/CONTEXT.md when "
                        "absent or unreadable.")
    p.add_argument("--env-file", dest="env_file", action="append", default=[],
                   metavar="PATH",
                   help="Extra dotenv file to load before the audit "
                        "(repeatable). Loaded ahead of the auto-detected "
                        "<root>/admin.env and <root>/.env; live shell values "
                        "always win.")
    p.add_argument("--dist", default=None,
                   help="Built HTML directory (default: <root>/dist).")
    p.add_argument("--report-dir", default=None,
                   help="Directory the report is written into "
                        "(default: <root>/.scratch/seo-audit).")
    p.add_argument("--quick", action="store_true",
                   help="Skip heavy external probes (Lighthouse, pa11y).")
    p.add_argument("--url", action="append", default=[],
                   help="Probe a live URL with the external adapters "
                        "(repeatable). Slice 02. Requires network.")
    p.add_argument("--push", action="store_true",
                   help="Enable push module — IndexNow, Bing Webmaster, "
                        "llms.txt. Opt-in; confirmation per operation.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true",
                   help="Only valid with --push: render the push plan "
                        "without performing any submissions or writes.")
    p.add_argument("--compare-last", action="store_true",
                   help="Diff against the most recent prior report.")
    p.add_argument("--doctor", action="store_true",
                   help="Doctor mode — diagnose env / file / probe readiness.")
    p.add_argument("--verify", action="store_true",
                   help="Verify mode — one minimal probe call per "
                        "configured tool.")
    p.add_argument("--setup", choices=SETUP_TOOLS, default=None,
                   metavar="TOOL",
                   help=f"Setup wizard for a single tool "
                        f"({'/'.join(SETUP_TOOLS)}).")
    p.add_argument("--force", action="store_true",
                   help="Force-regenerate setup artefacts (currently only "
                        "honoured by `--setup indexnow`).")
    return p.parse_args(argv)


def main(argv=None) -> int:
    return run(parse_args(argv if argv is not None else sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
