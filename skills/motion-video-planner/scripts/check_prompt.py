#!/usr/bin/env python3
"""Check a motion-video-planner production prompt before hand-over.

Verifies what a fresh production agent cannot recover from on its own:
required sections present and non-empty, no leftover placeholders or
references to the planning chat, a contiguous planned timeline that adds up
to the planned duration, a detail block with every field for each scene,
existing assets that really exist, and a BRIEF.md appendix HyperFrames can
read. Reading-speed problems are reported as warnings.

It cannot judge whether the story is good. That stays a human-style review.

Usage:
    python3 check_prompt.py <production-prompt.md> [--assets-root <dir>]
Exit code: 0 = no errors (warnings allowed), 1 = errors, 2 = usage error.
"""

import argparse
import os
import re
import sys

REQUIRED_SECTIONS = [
    "0. Start here",
    "1. Goal and context",
    "2. Story",
    "3. Format",
    "4. Look",
    "5. Timeline",
    "6. Audio",
    "7. Assets",
    "8. Technical execution",
    "9. Quality and delivery",
    "Appendix A: BRIEF.md",
    "Appendix B: Sources",
    "Appendix C: frame.md",
]
SCENE_FIELDS = ["Composition", "Assets", "Action", "Camera", "Motion/easing",
                "Transition out", "Audio cues"]
TIMELINE_HEADER = ["#", "start", "end", "purpose", "voiceover", "on-screen text"]
ASSET_STATUSES = {"exists", "user", "create", "source", "generate"}
WORKFLOWS = {"general-video", "motion-graphics", "product-launch-video", "faceless-explainer",
             "music-to-video", "pr-to-video", "embedded-captions", "talking-head-recut",
             "slideshow", "remotion-to-hyperframes"}

PLACEHOLDER_PATTERNS = [
    (r"[«»]", "unfilled template slot («…»)"),
    (r"\b(TODO|TBD|FIXME|XXX)\b", "placeholder marker"),
    (r"\?\?\?", "placeholder marker '???'"),
    (r"\[(insert|placeholder|tbd|todo)[^\]]*\]", "bracket placeholder"),
    (r"<(your|insert|placeholder)[^>]*>", "angle-bracket placeholder"),
    (r"lorem ipsum", "lorem ipsum filler"),
]
CHAT_REFERENCE_PATTERNS = [
    r"as discussed", r"as mentioned (above|earlier|before)", r"see above",
    r"earlier in (the|this) (chat|conversation)", r"wie besprochen", r"wie oben",
    r"siehe oben", r"oben genannt", r"wie vereinbart", r"concepts\.md",
]

MAX_TEXT_WORDS_PER_SEC = 3.5
MAX_VO_WORDS_PER_SEC = 3.0
TIME_TOLERANCE = 0.05


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def split_sections(text):
    """Map '## ' headings outside code fences to their bodies (fences kept in bodies)."""
    sections = {}
    order = []
    current = None
    fence = None
    for line in text.splitlines():
        m = re.match(r"^(`{3,}|~{3,})", line)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and line.strip() == marker:
                fence = None
        if fence is None and line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            order.append(current)
            continue
        if current is not None:
            sections[current].append(line)
    return {k: "\n".join(v) for k, v in sections.items()}, order


def strip_fences(text):
    return re.sub(r"(?ms)^(`{3,}|~{3,}).*?^\1\s*$", "", text)


def parse_time(raw):
    s = raw.strip().strip("*").strip().rstrip("s").strip()
    m = re.fullmatch(r"(\d+):(\d+(?:\.\d+)?)", s)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.fullmatch(r"\d+(?:\.\d+)?", s)
    if m:
        return float(s)
    return None


def table_rows(body, header_prefixes):
    """Return data rows (lists of cells) of the first table whose header matches the prefixes."""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if len(cells) < len(header_prefixes):
            continue
        if all(cells[j].startswith(p) for j, p in enumerate(header_prefixes)):
            rows = []
            for row in lines[i + 2:]:
                if not row.strip().startswith("|"):
                    break
                rows.append([c.strip() for c in row.strip().strip("|").split("|")])
            return rows
    return None


def word_count(cell):
    cleaned = re.sub(r"[\"“”„'`*_/—–-]", " ", cell)
    if cleaned.strip() in ("", "none", "keine", "kein"):
        return 0
    return len(cleaned.split())


def check_placeholders(text, rep):
    for lineno, line in enumerate(text.splitlines(), 1):
        for pattern, label in PLACEHOLDER_PATTERNS:
            if re.search(pattern, line, re.I if label != "placeholder marker" else 0):
                rep.error(f"line {lineno}: {label}: {line.strip()[:100]}")
        for pattern in CHAT_REFERENCE_PATTERNS:
            if re.search(pattern, line, re.I):
                rep.error(f"line {lineno}: refers to the planning chat or files the executor lacks: "
                          f"{line.strip()[:100]}")


def check_sections(sections, rep):
    for name in REQUIRED_SECTIONS:
        if name not in sections:
            rep.error(f"missing section '## {name}'")
        elif not strip_fences(sections[name]).strip() and not sections[name].strip():
            rep.error(f"section '## {name}' is empty")


def planned_duration(sections, rep):
    body = sections.get("3. Format", "")
    m = re.search(r"Duration \(planned\):\s*(\d+(?:\.\d+)?)\s*s\b", body)
    if not m:
        rep.error("section 3 lacks a 'Duration (planned): <n> s' line")
        return None
    return float(m.group(1))


def check_timeline(sections, duration, rep):
    body = sections.get("5. Timeline", "")
    if not re.search(r"planned", body, re.I):
        rep.error("section 5 does not mark its timings as PLANNED")
    rows = table_rows(body, TIMELINE_HEADER)
    if rows is None:
        rep.error("section 5 has no scene table with header "
                  "'# | Start | End | Purpose | Voiceover (exact) | On-screen text (exact)'")
        return []
    if not rows:
        rep.error("scene table in section 5 has no rows")
        return []
    scenes = []
    prev_end = None
    for idx, cells in enumerate(rows, 1):
        if len(cells) < 6:
            rep.error(f"scene row {idx} has {len(cells)} cells, expected 6")
            continue
        num, start_raw, end_raw, purpose, vo, onscreen = cells[:6]
        start, end = parse_time(start_raw), parse_time(end_raw)
        label = f"scene {num or idx}"
        if start is None or end is None:
            rep.error(f"{label}: unreadable start/end '{start_raw}'/'{end_raw}' (use seconds or m:ss)")
            continue
        if end <= start:
            rep.error(f"{label}: end {end} is not after start {start}")
        if prev_end is None and abs(start) > TIME_TOLERANCE:
            rep.error(f"{label}: first scene must start at 0, starts at {start}")
        if prev_end is not None and abs(start - prev_end) > TIME_TOLERANCE:
            kind = "gap" if start > prev_end else "overlap"
            rep.error(f"{label}: {kind} of {abs(start - prev_end):.2f} s after previous scene")
        if not purpose.strip():
            rep.error(f"{label}: purpose is empty")
        span = end - start
        if span > 0:
            tw = word_count(onscreen)
            vw = word_count(vo)
            if tw / span > MAX_TEXT_WORDS_PER_SEC:
                rep.warn(f"{label}: {tw} on-screen words in {span:.1f} s may be too fast to read")
            if vw / span > MAX_VO_WORDS_PER_SEC:
                rep.warn(f"{label}: {vw} voiceover words in {span:.1f} s exceeds "
                         f"{MAX_VO_WORDS_PER_SEC} words/s")
        prev_end = end
        scenes.append(num.strip() or str(idx))
    if duration is not None and prev_end is not None and abs(prev_end - duration) > TIME_TOLERANCE:
        rep.error(f"timeline ends at {prev_end} s but planned duration is {duration} s")
    return scenes


def check_scene_blocks(sections, scenes, rep):
    body = sections.get("5. Timeline", "")
    blocks = {}
    current = None
    for line in body.splitlines():
        m = re.match(r"^###\s+Scene\s+(\S+?)\b", line)
        if m:
            current = m.group(1)
            blocks[current] = []
            continue
        if current is not None:
            blocks[current].append(line)
    for num in scenes:
        if num not in blocks:
            rep.error(f"scene {num}: no '### Scene {num}' detail block")
            continue
        text = "\n".join(blocks[num])
        for field in SCENE_FIELDS:
            m = re.search(r"^\s*-\s*" + re.escape(field) + r":(.*)$", text, re.M)
            if not m:
                rep.error(f"scene {num}: missing field '{field}:'")
            elif not m.group(1).strip():
                rep.error(f"scene {num}: field '{field}:' is empty")


def check_assets(sections, assets_root, rep):
    body = sections.get("7. Assets", "")
    rows = table_rows(body, ["path", "status", "use", "notes"])
    if rows is None:
        rep.error("section 7 has no asset table with header 'Path | Status | Use | Notes'")
        return
    has_generate = False
    for cells in rows:
        if len(cells) < 4:
            rep.error(f"asset row has {len(cells)} cells, expected 4: {'|'.join(cells)[:80]}")
            continue
        path_cell, status = cells[0], cells[1].strip().lower()
        if status not in ASSET_STATUSES:
            rep.error(f"asset {path_cell}: status '{cells[1]}' not one of {sorted(ASSET_STATUSES)}")
            continue
        if status == "generate":
            has_generate = True
        m = re.search(r"`([^`]+)`", path_cell)
        rel = m.group(1) if m else path_cell.strip()
        if status == "user":
            # Promised by the user but not delivered yet: a blocker the
            # executor has to stop on, so it is surfaced on every run.
            if assets_root is None or not os.path.exists(os.path.join(assets_root, rel)):
                rep.warn(f"asset {rel}: supplied by the user and not present yet; "
                         "production must stop before the final render until it arrives")
        if status == "exists":
            if assets_root is None:
                rep.warn(f"asset {rel}: existence not checked (pass --assets-root)")
            elif not os.path.exists(os.path.join(assets_root, rel)):
                rep.error(f"asset {rel}: marked 'exists' but not found under {assets_root}")
    if has_generate and not re.search(r"Budget for paid generation:\s*\S", body):
        rep.error("section 7 has 'generate' assets but no 'Budget for paid generation:' line")


def frontmatter(block_text):
    m = re.search(r"(?ms)^---\s*$(.*?)^---\s*$", block_text)
    return m.group(1) if m else None


def check_brief(sections, rep):
    body = sections.get("Appendix A: BRIEF.md", "")
    fm = frontmatter(body)
    if fm is None:
        rep.error("Appendix A has no BRIEF.md frontmatter block")
        return None
    values = dict(re.findall(r"(?m)^([a-z_]+):\s*(.+?)\s*$", fm))
    for key in ("workflow", "flow", "storyboard", "message"):
        if key not in values:
            rep.error(f"Appendix A frontmatter lacks '{key}'")
    wf = values.get("workflow", "").strip()
    if wf and wf not in WORKFLOWS:
        rep.error(f"Appendix A workflow '{wf}' is not a known HyperFrames route")
    if values.get("flow") and values["flow"] not in ("automation", "companion"):
        rep.error(f"Appendix A flow '{values['flow']}' must be automation or companion")
    if values.get("storyboard") and values["storyboard"] not in ("yes", "no"):
        rep.error(f"Appendix A storyboard '{values['storyboard']}' must be yes or no")
    if wf == "motion-graphics" and values.get("narration", "no").strip() not in ("no", "none"):
        rep.error("motion-graphics does not take narration; use general-video or set narration: no")
    tech = sections.get("8. Technical execution", "")
    if wf and ("/" + wf) not in tech:
        rep.error(f"section 8 does not name the workflow '/{wf}' from Appendix A")
    return values


def check_look_and_frame(sections, rep):
    look = sections.get("4. Look", "")
    if not re.search(r"#[0-9a-fA-F]{6}\b", look):
        rep.error("section 4 names no exact hex color")
    fm = frontmatter(sections.get("Appendix C: frame.md", ""))
    if fm is None:
        rep.error("Appendix C has no frame.md frontmatter block")
        return
    for key in ("colors", "typography"):
        if not re.search(rf"(?m)^{key}:", fm):
            rep.error(f"Appendix C frontmatter lacks '{key}:'")


def check_sources(sections, rep):
    rows = table_rows(sections.get("Appendix B: Sources", ""), ["#", "claim", "evidence"])
    if rows is None:
        rep.error("Appendix B has no table with header '# | Claim … | Evidence'")
    elif not rows:
        rep.error("Appendix B lists no sources")
    else:
        for cells in rows:
            if len(cells) < 3 or not cells[2].strip():
                rep.error(f"Appendix B row without evidence: {'|'.join(cells)[:80]}")


def check(text, assets_root=None):
    rep = Report()
    sections, _ = split_sections(text)
    check_placeholders(text, rep)
    check_sections(sections, rep)
    duration = planned_duration(sections, rep)
    scenes = check_timeline(sections, duration, rep)
    check_scene_blocks(sections, scenes, rep)
    check_assets(sections, assets_root, rep)
    check_brief(sections, rep)
    check_look_and_frame(sections, rep)
    check_sources(sections, rep)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("prompt")
    ap.add_argument("--assets-root", help="base directory for 'exists' asset paths")
    args = ap.parse_args(argv)
    try:
        with open(args.prompt, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rep = check(text, args.assets_root)
    for e in rep.errors:
        print(f"ERROR  {e}")
    for w in rep.warnings:
        print(f"WARN   {w}")
    print(f"\n{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
