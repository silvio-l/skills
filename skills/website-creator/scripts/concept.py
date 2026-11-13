#!/usr/bin/env python3
"""Concept image for the direction phase: Codex CLI on the subscription, with a fallback and a recorded gap.

Before the three directions are written, an image model drafts its own picture of the page from the reference
board and a short description. That picture is a second opinion that pulls the directions away from the
assistant's defaults. Codex CLI is used only when it is logged in with a ChatGPT subscription; an API key is
never used (the key variables are removed from the call's environment, and an API-key login is refused).

Commands:
  check                                   which route is available (codex, local, mockup) as JSON
  codex --prompt-file F [--ref IMG ...]   draft concept images via `codex exec`; writes concept.md
  record --route local|mockup|gap ...     record a fallback image or the gap in concept.md

Output lives in <project>/.website-creator/concept/: the images plus concept.md, which run.py's gate reads.
Exit codes: 0 ok, 2 usage, 3 route not available or no image produced (use the fallback).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

ROUTES = ("codex", "local", "mockup", "gap")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".avif"}
KEY_VARS = ("OPENAI_API_KEY", "CODEX_API_KEY", "AZURE_OPENAI_API_KEY")
LOCAL_TOOLS = ("mflux-generate", "draw-things-cli")
CODEX_TIMEOUT = 900
MIN_REASON = 10

WRAPPER = """You are drafting a concept image for a website, not building it.
Use your built-in image generation tool. Do not write code, do not call any API with a key.
Generate {count} distinct image(s) of the page's first viewport at 1440x900 (landscape), each a different
interpretation, and save them in the current directory as concept-1.png, concept-2.png, ...
Attached images are the reference board: borrow principles, never copy a layout or a logo.
Reply only with the saved file names.

Description of the page:
{prompt}
"""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def project_dir(explicit=None):
    return Path(explicit or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


def concept_dir(root):
    return root / ".website-creator" / "concept"


def clean_env(env=None):
    """The call's environment without any API key, so Codex can only use the subscription login."""
    env = dict(os.environ if env is None else env)
    for key in KEY_VARS:
        env.pop(key, None)
    return env


def codex_status(which=None, runner=subprocess.run):
    """('ok'|'missing'|'api-key'|'logged-out', detail). Only a ChatGPT login counts as available."""
    exe = (which or shutil.which)("codex")  # resolved per call, so a patched shutil.which is honored
    if not exe:
        return "missing", "codex CLI not found on PATH"
    try:
        res = runner([exe, "login", "status"], capture_output=True, text=True, timeout=30, env=clean_env())
    except (OSError, subprocess.SubprocessError) as exc:
        return "logged-out", f"codex login status failed: {exc}"
    text = (res.stdout or "") + (res.stderr or "")
    if re.search(r"chatgpt", text, re.I):
        return "ok", text.strip().splitlines()[0] if text.strip() else "logged in using ChatGPT"
    if re.search(r"api key", text, re.I):
        return "api-key", "codex is logged in with an API key; only the subscription login is allowed"
    return "logged-out", text.strip() or "not logged in"


def images_in(folder):
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


def write_record(folder, route, files, prompt="", refs=(), reason="", tool=""):
    lines = ["# Concept image", "", f"route: {route}", f"date: {now()}"]
    if tool:
        lines.append(f"tool: {tool}")
    if reason:
        lines.append(f"reason: {reason}")
    lines += ["", "## Files"] + ([f"- {f}" for f in files] or ["- (none)"])
    if refs:
        lines += ["", "## References"] + [f"- {r}" for r in refs]
    if prompt:
        lines += ["", "## Prompt", "", prompt.strip()]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "concept.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_record(folder):
    """Parse concept.md into {'route', 'reason', 'files'}; None when it does not exist."""
    path = folder / "concept.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    field = lambda name: (re.search(rf"^{name}:\s*(.+)$", text, re.M) or [None, ""])[1].strip()
    files_block = re.search(r"^## Files\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    files = re.findall(r"^-\s+(\S.*?)\s*$", files_block.group(1), re.M) if files_block else []
    return {"route": field("route").lower(), "reason": field("reason"), "files": [f for f in files if f != "(none)"]}


def record_problems(folder):
    """Gate messages for the concept step; an empty list means the step is done (image or recorded gap)."""
    rec = read_record(folder)
    if rec is None:
        return [".website-creator/concept/concept.md is missing (concept image or recorded gap, see references/concept.md)"]
    if rec["route"] not in ROUTES:
        return [f"concept.md route '{rec['route'] or '-'}' is not one of {', '.join(ROUTES)}"]
    if rec["route"] == "gap":
        if len(rec["reason"]) < MIN_REASON:
            return ["concept.md records a gap without a real reason (`reason:` line, at least 10 characters)"]
        return []
    present = [f for f in rec["files"] if (folder / f).exists()]
    if not present:
        return [f"concept.md (route {rec['route']}) lists no image that exists in .website-creator/concept/"]
    return []


def cmd_check(root, args):
    status, detail = codex_status()
    local = [t for t in LOCAL_TOOLS if shutil.which(t)]
    route = "codex" if status == "ok" else ("local" if local else "mockup")
    print(json.dumps({"route": route, "codex": status, "codex_detail": detail, "local_tools": local,
                      "concept_dir": str(concept_dir(root))}, indent=2))
    return 0


def cmd_codex(root, args, runner=subprocess.run):
    status, detail = codex_status(runner=runner)
    if status != "ok":
        print(f"codex not usable ({status}): {detail}. Use the fallback: concept.py record --route local|mockup|gap",
              file=sys.stderr)
        return 3
    prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if not prompt:
        print("the prompt file is empty", file=sys.stderr)
        return 2
    refs = [str(Path(r).resolve()) for r in args.ref or []]
    for r in refs:
        if not Path(r).exists():
            print(f"reference image not found: {r}", file=sys.stderr)
            return 2
    folder = concept_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in images_in(folder)}
    cmd = [shutil.which("codex"), "exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(folder)]
    for r in refs:
        cmd += ["-i", r]
    cmd.append("-")  # prompt on stdin: -i takes several values and would swallow a positional prompt
    try:
        res = runner(cmd, input=WRAPPER.format(count=args.count, prompt=prompt), capture_output=True, text=True,
                     timeout=args.timeout, env=clean_env())
    except subprocess.TimeoutExpired:
        print(f"codex exec timed out after {args.timeout}s; use the fallback", file=sys.stderr)
        return 3
    new = [p.name for p in images_in(folder) if p.name not in before]
    if not new:
        tail = "\n".join(((res.stdout or "") + (res.stderr or "")).strip().splitlines()[-5:])
        print(f"codex produced no image (exit {res.returncode}; quota or tool unavailable?). Use the fallback.\n{tail}",
              file=sys.stderr)
        return 3
    write_record(folder, "codex", new, prompt=prompt, refs=refs, tool="codex exec (ChatGPT subscription)")
    print(json.dumps({"route": "codex", "files": [str(folder / n) for n in new]}, indent=2))
    return 0


def cmd_record(root, args):
    folder = concept_dir(root)
    if args.route == "gap":
        if not args.reason or len(args.reason.strip()) < MIN_REASON:
            print("a gap needs a real reason (at least 10 characters)", file=sys.stderr)
            return 2
        write_record(folder, "gap", [], reason=args.reason.strip())
        print("recorded concept gap; name it in the report")
        return 0
    if not args.file:
        print(f"route {args.route} needs --file IMAGE", file=sys.stderr)
        return 2
    folder.mkdir(parents=True, exist_ok=True)
    names = []
    for f in args.file:
        src = Path(f).resolve()
        if not src.exists() or src.suffix.lower() not in IMAGE_SUFFIXES:
            print(f"not an image file: {f}", file=sys.stderr)
            return 2
        dest = folder / src.name
        if src != dest:
            shutil.copy2(src, dest)
        names.append(src.name)
    prompt = Path(args.prompt_file).read_text(encoding="utf-8") if args.prompt_file else ""
    write_record(folder, args.route, names, prompt=prompt, reason=(args.reason or "").strip(), tool=args.tool or "")
    print(json.dumps({"route": args.route, "files": names}, indent=2))
    return 0


def main(argv=None, runner=subprocess.run):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    p = sub.add_parser("codex")
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--ref", action="append", help="reference image (repeatable)")
    p.add_argument("--count", type=int, default=2, choices=range(1, 5))
    p.add_argument("--timeout", type=int, default=CODEX_TIMEOUT)
    p = sub.add_parser("record")
    p.add_argument("--route", required=True, choices=("local", "mockup", "gap"))
    p.add_argument("--file", action="append")
    p.add_argument("--tool")
    p.add_argument("--prompt-file")
    p.add_argument("--reason")
    args = ap.parse_args(argv)
    root = project_dir(args.project)
    if args.cmd == "check":
        return cmd_check(root, args)
    if args.cmd == "codex":
        return cmd_codex(root, args, runner=runner)
    return cmd_record(root, args)


if __name__ == "__main__":
    sys.exit(main())
