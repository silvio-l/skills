#!/usr/bin/env python3
"""Run state and finish gate for website-creator.

A run lives in <project>/.website-creator/state.json. While a run is active, the Stop hook (`run.py hook`) blocks the
agent from ending its turn until every gate condition holds, at most MAX_ROUNDS times per run; after that it
logs the exhaustion and lets the agent stop. While the run waits for a user decision, the hook stays silent.

Commands:
  start --page NAME [--src DIR ...]   begin a run (src: source folders whose changes make reports stale)
  phase NAME                          record the current phase
  wait copy|direction                 pause at a decision point (the hook allows stopping)
  decide copy|direction CHOICE        record the user's decision and leave the waiting state
  waive RULE --reason TEXT            accept a lint/render rule or a gate check as a documented exception
  status [--json]                     show the run and the open gate conditions
  finish                              end the run; refused while gate conditions are open
  abort --reason TEXT                 end the run without the gate (logged)
  hook                                Stop hook entry point (reads the hook JSON on stdin)

The project folder is --project, else $CLAUDE_PROJECT_DIR, else the hook input's cwd, else the current folder.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

MAX_ROUNDS = 3
DECISIONS = ("copy", "direction")
MIN_COMPETITORS = 3
MIN_WIDTHS = 3
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".output", ".astro", ".svelte-kit",
             ".website-creator", "out", "coverage", ".turbo", ".vercel", ".cache"}
SOURCE_SUFFIXES = {".html", ".htm", ".css", ".scss", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".astro",
                   ".md", ".mdx", ".json", ".php", ".twig", ".liquid", ".njk"}
GATE_CHECKS = ("decisions", "research", "lint", "render", "design-md", "fresh")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def project_dir(explicit=None, hook_input=None):
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    if hook_input and hook_input.get("cwd"):
        return Path(hook_input["cwd"]).resolve()
    return Path.cwd().resolve()


class Run:
    def __init__(self, root):
        self.root = Path(root)
        self.dir = self.root / ".website-creator"
        self.state_path = self.dir / "state.json"
        self.waivers_path = self.dir / "waivers.json"

    # -- storage -------------------------------------------------------------
    def load(self):
        if not self.state_path.exists():
            return None
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save(self, state):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.state_path)

    def waivers(self):
        if not self.waivers_path.exists():
            return []
        return json.loads(self.waivers_path.read_text(encoding="utf-8"))

    def waived_rules(self):
        return {w["rule"] for w in self.waivers()}

    def log(self, state, event, **data):
        state.setdefault("log", []).append({"at": now(), "event": event, **data})

    # -- gate ----------------------------------------------------------------
    def open_conditions(self, state):
        """Return a list of (check, message) for every gate condition that does not hold."""
        waived = self.waived_rules()
        problems = []

        missing = [d for d in DECISIONS if not state.get("decisions", {}).get(d)]
        if missing and "decisions" not in waived:
            problems.append(("decisions", "user decision missing: " + ", ".join(missing)
                             + " (present the options, `run.py wait <name>`, then `run.py decide <name> <choice>`)"))

        research = self.dir / "research.md"
        if "research" not in waived:
            if not research.exists():
                problems.append(("research", ".website-creator/research.md is missing (competitor research, see references/research.md)"))
            else:
                hosts = competitor_hosts(research.read_text(encoding="utf-8"))
                if len(hosts) < MIN_COMPETITORS:
                    problems.append(("research", f".website-creator/research.md names {len(hosts)} competitor sites, needs {MIN_COMPETITORS}"))

        lint = self.dir / "lint.json"
        if "lint" not in waived:
            problems += report_problems("lint", lint, waived, "run scripts/slop_lint.py <src> --out .website-creator/lint.json")

        render = self.dir / "render" / "report.json"
        if "render" not in waived:
            problems += report_problems("render", render, waived, "run scripts/render_check.py <url>")
            if render.exists():
                widths = json.loads(render.read_text(encoding="utf-8")).get("widths", [])
                if len(widths) < MIN_WIDTHS:
                    problems.append(("render", f"render check covered {len(widths)} widths, needs {MIN_WIDTHS}"))

        if "design-md" not in waived:
            design = self.root / state.get("design", "DESIGN.md")
            if not design.exists():
                problems.append(("design-md", f"{design.name} is missing (see references/design-system.md)"))
            else:
                front = front_matter(design.read_text(encoding="utf-8"))
                for key in ("colors", "typography"):
                    if not re.search(rf"^{key}\s*:", front, re.M):
                        problems.append(("design-md", f"{design.name} front matter has no `{key}:` block"))

        if "fresh" not in waived:
            newest = newest_source(self.root, state.get("src") or ["."])
            for name, path in (("lint", lint), ("render", render)):
                if path.exists() and newest and path.stat().st_mtime + 1 < newest[0]:
                    problems.append(("fresh", f"{name} report is older than {newest[1]}; run it again"))
        return problems


def competitor_hosts(text):
    hosts = set()
    for m in re.finditer(r"https?://([^/\s)>\]\"']+)", text):
        host = m.group(1).lower().split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        if host in {"localhost", "127.0.0.1"}:
            continue
        hosts.add(host)
    return hosts


def report_problems(name, path, waived, hint):
    if not path.exists():
        return [(name, f"{path.name} for {name} is missing ({hint})")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [(name, f"{name} report is not valid JSON ({hint})")]
    errors = [f for f in data.get("findings", []) if f.get("severity") == "error" and f.get("rule") not in waived]
    if not errors:
        return []
    rules = sorted({f["rule"] for f in errors})
    return [(name, f"{len(errors)} unwaived {name} errors ({', '.join(rules[:8])}); fix them or `run.py waive <rule> --reason ...`")]


def front_matter(text):
    m = re.match(r"\A---\s*\n(.*?)\n---\s*(\n|\Z)", text, re.S)
    return m.group(1) if m else ""


def newest_source(root, src_list):
    best = None
    for src in src_list:
        base = (root / src).resolve()
        if base.is_file():
            candidates = [base]
        elif base.is_dir():
            candidates = walk(base)
        else:
            continue
        for p in candidates:
            try:
                mt = p.stat().st_mtime
            except OSError:
                continue
            if best is None or mt > best[0]:
                best = (mt, str(p.relative_to(root)) if p.is_relative_to(root) else str(p))
    return best


def walk(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            p = Path(dirpath) / f
            if p.suffix.lower() in SOURCE_SUFFIXES and p.name != "DESIGN.md":
                yield p


# -- commands -----------------------------------------------------------------

def cmd_start(run, args):
    state = run.load()
    if state and state.get("active"):
        print(f"a run for '{state.get('page')}' is already active; finish or abort it first", file=sys.stderr)
        return 1
    state = {"active": True, "page": args.page, "src": args.src or ["."], "design": args.design,
             "phase": "brief", "waiting": None, "decisions": {}, "rounds": 0, "started": now(),
             "log": (state or {}).get("log", [])[-50:]}
    run.log(state, "start", page=args.page)
    run.save(state)
    gi = run.dir / ".gitignore"
    if not gi.exists():
        gi.write_text("render/\nstate.json\n", encoding="utf-8")
    print(f"website-creator run started for '{args.page}' in {run.root}")
    return 0


def require_active(run):
    state = run.load()
    if not state or not state.get("active"):
        print("no active website-creator run (start one with `run.py start --page NAME`)", file=sys.stderr)
        return None
    return state


def cmd_phase(run, args):
    state = require_active(run)
    if state is None:
        return 1
    state["phase"] = args.name
    run.log(state, "phase", name=args.name)
    run.save(state)
    print(f"phase: {args.name}")
    return 0


def cmd_wait(run, args):
    state = require_active(run)
    if state is None:
        return 1
    state["waiting"] = args.decision
    run.log(state, "wait", decision=args.decision)
    run.save(state)
    print(f"waiting for the user's {args.decision} decision; stopping is allowed now")
    return 0


def cmd_decide(run, args):
    state = require_active(run)
    if state is None:
        return 1
    state.setdefault("decisions", {})[args.decision] = args.choice
    if state.get("waiting") == args.decision:
        state["waiting"] = None
    state["rounds"] = 0
    run.log(state, "decide", decision=args.decision, choice=args.choice)
    run.save(state)
    print(f"{args.decision}: {args.choice}")
    return 0


def cmd_waive(run, args):
    if not args.reason or len(args.reason.strip()) < 10:
        print("a waiver needs a real reason (at least 10 characters)", file=sys.stderr)
        return 2
    waivers = run.waivers()
    waivers = [w for w in waivers if w["rule"] != args.rule]
    waivers.append({"rule": args.rule, "reason": args.reason.strip(), "at": now()})
    run.dir.mkdir(parents=True, exist_ok=True)
    run.waivers_path.write_text(json.dumps(waivers, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    state = run.load()
    if state:
        run.log(state, "waive", rule=args.rule, reason=args.reason.strip())
        run.save(state)
    print(f"waived {args.rule}: {args.reason.strip()}")
    return 0


def cmd_status(run, args):
    state = run.load()
    if not state:
        out = {"active": False}
    else:
        out = {"active": state.get("active", False), "page": state.get("page"), "phase": state.get("phase"),
               "waiting": state.get("waiting"), "decisions": state.get("decisions", {}),
               "rounds": state.get("rounds", 0), "waivers": run.waivers(),
               "open": [{"check": c, "message": m} for c, m in run.open_conditions(state)]}
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if not out["active"]:
        print("no active run")
        return 0
    print(f"page {out['page']} | phase {out['phase']} | waiting {out['waiting'] or '-'} | stop rounds {out['rounds']}/{MAX_ROUNDS}")
    for d in DECISIONS:
        print(f"  decision {d}: {out['decisions'].get(d) or '(open)'}")
    for w in out["waivers"]:
        print(f"  waiver {w['rule']}: {w['reason']}")
    for o in out["open"]:
        print(f"  OPEN [{o['check']}] {o['message']}")
    if not out["open"]:
        print("  gate: all conditions hold")
    return 0


def cmd_finish(run, args):
    state = require_active(run)
    if state is None:
        return 1
    problems = run.open_conditions(state)
    if problems:
        for check, msg in problems:
            print(f"OPEN [{check}] {msg}", file=sys.stderr)
        return 1
    state["active"] = False
    state["waiting"] = None
    run.log(state, "finish", waivers=[w["rule"] for w in run.waivers()])
    run.save(state)
    print("website-creator run finished; gate passed")
    return 0


def cmd_abort(run, args):
    state = require_active(run)
    if state is None:
        return 1
    state["active"] = False
    state["waiting"] = None
    run.log(state, "abort", reason=args.reason)
    run.save(state)
    print(f"website-creator run aborted: {args.reason}")
    return 0


def cmd_hook(args, stdin):
    try:
        hook_input = json.loads(stdin.read() or "{}")
    except json.JSONDecodeError:
        hook_input = {}
    run = Run(project_dir(args.project, hook_input))
    try:
        state = run.load()
    except (OSError, json.JSONDecodeError):
        return 0  # a broken state file must never trap the agent
    if not state or not state.get("active") or state.get("waiting"):
        return 0
    problems = run.open_conditions(state)
    if not problems:
        return 0
    rounds = state.get("rounds", 0)
    if rounds >= MAX_ROUNDS:
        run.log(state, "gate-exhausted", open=[c for c, _ in problems])
        state["active"] = False
        run.save(state)
        print(f"website-creator: stop gate exhausted after {MAX_ROUNDS} rounds; run closed with open checks "
              f"({', '.join(sorted({c for c, _ in problems}))}). Report them to the user as unfinished.", file=sys.stderr)
        return 0
    state["rounds"] = rounds + 1
    run.log(state, "gate-block", round=rounds + 1, open=[c for c, _ in problems])
    run.save(state)
    lines = [f"website-creator run '{state.get('page')}' is not finished (stop round {rounds + 1}/{MAX_ROUNDS}). Open:"]
    lines += [f"- [{c}] {m}" for c, m in problems]
    lines.append("Resolve them, or `run.py wait <decision>` if you need the user, or `run.py abort --reason ...`.")
    print(json.dumps({"decision": "block", "reason": "\n".join(lines)}))
    return 0


def main(argv=None, stdin=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start")
    p.add_argument("--page", required=True)
    p.add_argument("--src", action="append")
    p.add_argument("--design", default="DESIGN.md")
    p = sub.add_parser("phase")
    p.add_argument("name")
    p = sub.add_parser("wait")
    p.add_argument("decision", choices=DECISIONS)
    p = sub.add_parser("decide")
    p.add_argument("decision", choices=DECISIONS)
    p.add_argument("choice")
    p = sub.add_parser("waive")
    p.add_argument("rule")
    p.add_argument("--reason", required=True)
    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")
    sub.add_parser("finish")
    p = sub.add_parser("abort")
    p.add_argument("--reason", required=True)
    sub.add_parser("hook")
    args = ap.parse_args(argv)
    if args.cmd == "hook":
        return cmd_hook(args, stdin or sys.stdin)
    run = Run(project_dir(args.project))
    return {"start": cmd_start, "phase": cmd_phase, "wait": cmd_wait, "decide": cmd_decide, "waive": cmd_waive,
            "status": cmd_status, "finish": cmd_finish, "abort": cmd_abort}[args.cmd](run, args)


if __name__ == "__main__":
    sys.exit(main())
