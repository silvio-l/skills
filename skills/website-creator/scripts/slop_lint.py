#!/usr/bin/env python3
"""Slop linter for website-creator: static checks for generated-looking code and copy in a website source tree.

Usage:
  slop_lint.py PATH [PATH ...] [--design DESIGN.md] [--out .website-creator/lint.json] [--json] [--rules]

Scans markup, styles, scripts, Markdown and locale JSON. Errors are defects the run must fix or waive;
warnings are taste calls to review. Suppress one line with a comment containing `wc-ignore: <rule>[, <rule>]`
on the same or the previous line (`all` suppresses every rule there). Fonts and colors declared in DESIGN.md front
matter are allowed and become the reference for the design-system checks. Exit 1 when errors remain.
"""
import argparse
import colorsys
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".output", ".astro", ".svelte-kit",
             ".website-creator", "out", "coverage", ".turbo", ".vercel", ".cache", "vendor"}
MARKUP = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".php", ".twig", ".liquid", ".njk", ".mdx"}
STYLE = {".css", ".scss", ".sass", ".less"}
SCRIPT = {".js", ".mjs", ".ts"}
TEXT = {".md", ".json"}
SKIP_FILES = {"DESIGN.md", "TASTE.md", "package.json", "package-lock.json", "tsconfig.json", "composer.json",
              "README.md", "CHANGELOG.md", "CLAUDE.md", "AGENTS.md"}
MAX_BYTES = 1_000_000

RULES = {
    # code, errors
    "overused-font": ("error", "Font is on the overused list; pick a less common pairing or declare it in DESIGN.md."),
    "gradient-text": ("error", "Gradient-clipped text is decoration, not meaning; use a solid color."),
    "ai-color-palette": ("error", "Purple/violet/indigo gradient: the most recognizable generated-UI palette."),
    "side-tab": ("error", "Thick colored border on one side of a card; use spacing, weight or a full outline."),
    "bounce-easing": ("error", "Bounce/elastic or strongly overshooting easing; use ease-out or a damped spring."),
    "scale-zero": ("error", "Animating from scale(0) pops; start near 0.9-0.96 with opacity instead."),
    "missing-testid": ("error", "Interactive element or form without data-testid (or testID)."),
    "img-alt": ("error", "Image without alt attribute (use alt=\"\" for decoration)."),
    "broken-image": ("error", "Image with an empty or placeholder src."),
    "placeholder-image": ("error", "Placeholder image service; use a licensed photo, a project asset or a drawn graphic."),
    "lorem-ipsum": ("error", "Lorem ipsum placeholder text."),
    "no-reduced-motion": ("error", "Animation in the project but no prefers-reduced-motion handling anywhere."),
    # copy, errors
    "marketing-buzzword": ("error", "Inflated marketing word; say what the product concretely does."),
    # code, warnings
    "ease-in": ("warning", "ease-in starts slow and feels sluggish for UI; use ease-out or a custom curve."),
    "transition-all": ("warning", "transition: all animates layout and color alike; list the properties."),
    "layout-animation": ("warning", "Animating width/height/top/left/margin/padding triggers layout; use transform."),
    "pulsing-dot": ("warning", "Pulse/ping animation simulating liveness; keep it only for real live status."),
    "blinking-cursor": ("warning", "Typing-cursor animation where no input exists."),
    "marquee": ("warning", "Auto-scrolling marquee hides half its content and demands attention."),
    "overshoot-easing": ("warning", "Overshooting easing: fine on small controls, never on large surfaces or sections."),
    "uniform-sections": ("warning", "Three or more consecutive sections with the same shape; vary form or merge them."),
    "text-heavy": ("warning", "Text-heavy page; let a demo, image or motion carry part of it and cut sections."),
    "long-paragraph": ("warning", "Paragraph over about 70 words; split it or show the point instead."),
    "eyebrow-label": ("warning", "Tiny tracked uppercase label above a heading (eyebrow/kicker) is a generated-UI tell."),
    "numbered-section-labels": ("warning", "Numbered section labels (01, 02, ...) repeated as decoration."),
    "radial-halo": ("warning", "Chromatic radial-gradient glow behind content."),
    "dark-glow": ("warning", "Colored glow shadow (zero offset, chromatic blur)."),
    "grid-background": ("warning", "Decorative hairline grid or stripe background."),
    "tiny-text": ("warning", "Font size below 12px."),
    "wide-tracking": ("warning", "Letter spacing of 0.1em or more; reserve for very short labels."),
    "extreme-negative-tracking": ("warning", "Letter spacing tighter than -0.04em damages letter shapes."),
    "justified-text": ("warning", "Justified text without hyphenation creates rivers on narrow columns."),
    "design-system-color": ("warning", "Color literal outside the DESIGN.md palette."),
    "design-system-font": ("warning", "Font family not declared in DESIGN.md typography."),
    # copy, warnings
    "soft-buzzword": ("warning", "Vague benefit word; replace with the concrete effect."),
    "two-beat-slogan": ("warning", "Two-beat slogan cadence (\"X. Y.\") used three or more times."),
    "theater-phrase": ("warning", "Dismissing something as \"theater\" is a generated-copy tic."),
    "em-dash-overuse": ("warning", "Em-dash saturation in copy."),
    "rhetorical-questions": ("warning", "Chain of rhetorical questions."),
    "vague-cta": ("warning", "CTA does not say what the click does."),
    "exclamation-heading": ("warning", "Exclamation mark in a heading."),
}

OVERUSED_FONTS = ["Inter", "Roboto", "Open Sans", "Lato", "Montserrat", "Poppins", "Fraunces", "Geist",
                  "Plus Jakarta Sans", "Space Grotesk", "DM Sans", "Manrope", "Outfit", "Playfair Display",
                  "Instrument Serif", "Nunito"]

STRONG_BUZZ = [r"revolution\w*", r"revolutionär\w*", r"nahtlos\w*", r"seamless\w*", r"bahnbrechend\w*",
               r"groundbreaking", r"game[- ]?changer\w*", r"supercharg\w*", r"empower\w*", r"cutting[- ]edge",
               r"world[- ]class", r"weltklasse", r"unleash\w*", r"entfessel\w*", r"next[- ]level", r"next[- ]gen\w*",
               r"state[- ]of[- ]the[- ]art", r"blazing[- ]fast", r"unlock the (?:full )?power", r"elevate your",
               r"best[- ]in[- ]class", r"disrupt\w*", r"synerg\w*"]
SOFT_BUZZ = [r"ermöglich\w*", r"optimier\w*", r"effizient\w*", r"innovativ\w*", r"innovation\w*",
             r"leistungsstark\w*", r"intuitiv\w*", r"streamlin\w*", r"robust\w*", r"mühelos\w*", r"effortless\w*",
             r"leverag\w*", r"all[- ]in[- ]one", r"ganzheitlich\w*", r"mehrwert\w*", r"maßgeschneidert\w*",
             r"powerful", r"intuitive"]
VAGUE_CTA = ["mehr erfahren", "jetzt entdecken", "jetzt starten", "hier klicken", "mehr dazu", "los geht's",
             "learn more", "get started", "click here", "read more", "discover more", "find out more", "explore"]
PLACEHOLDER_HOSTS = r"placehold\.co|placeholder\.com|picsum\.photos|placekitten|dummyimage\.com|loremflickr|" \
                    r"source\.unsplash\.com|fakeimg\.pl|placeimg\.com"
GENERIC_FAMILIES = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-sans-serif",
                    "ui-serif", "ui-monospace", "ui-rounded", "-apple-system", "blinkmacsystemfont", "inherit",
                    "initial", "unset", "emoji", "math", "segoe ui", "helvetica", "arial", "apple color emoji",
                    "segoe ui emoji", "noto color emoji", "sfmono-regular", "menlo", "consolas", "monaco"}

ANIMATION_MARK = re.compile(r"@keyframes|\banimation\s*:|\btransition\s*:|\banimate-[a-z]|\bgsap\b|ScrollTrigger|"
                            r"framer-motion|\bmotion\.|animation-timeline|useSpring|lottie", re.I)
REDUCED_MARK = re.compile(r"prefers-reduced-motion|useReducedMotion|motion-reduce:|motion-safe:|reducedMotion", re.I)
IGNORE = re.compile(r"wc-ignore:\s*([a-z0-9_,\- ]+)", re.I)


def font_pattern(name):
    parts = [re.escape(p) for p in name.split()]
    return re.compile(r"(?<![\w-])" + r"[ +_-]".join(parts) + r"(?![\w-])", re.I)


FONT_PATTERNS = [(f, font_pattern(f)) for f in OVERUSED_FONTS]
STRONG_OVERSHOOT = (-0.6, 1.6)  # cubic-bezier y outside this range reads as bounce, not settle
PAGE_WORDS = 800  # visible words per page (markup file) before text-heavy fires
LOCALE_WORDS = 1500  # a locale file usually holds several pages
PARAGRAPH_WORDS = 70
MEDIA_TAG = re.compile(r"<(img|picture|video|canvas|svg|iframe|model-viewer)\b", re.I)
INTERACTIVE_TAG = re.compile(r"<(button|input|select|textarea|details|form)\b|role\s*=\s*[\"'](tab|slider|switch)", re.I)
FONT_CONTEXT = re.compile(r"font|family|fontsource|next/font|typeface", re.I)


# -- DESIGN.md ----------------------------------------------------------------

def read_design(path):
    info = {"colors": set(), "fonts": set(), "found": False}
    if not path or not path.exists():
        return info
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---", text, re.S)
    front = m.group(1) if m else ""
    info["found"] = bool(front)
    info["colors"] = {norm_hex(h) for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", front)}
    for fam in re.findall(r"(?:fontFamily|font-family|family|font)\s*:\s*[\"']?([^\"'\n,]+)", front, re.I):
        info["fonts"].add(fam.strip().lower())
    for f in OVERUSED_FONTS:
        if font_pattern(f).search(front):
            info["fonts"].add(f.lower())
    return info


def norm_hex(h):
    h = h.lower().lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    return "#" + h[:6]


def hue_of(hex_value):
    h = norm_hex(hex_value)[1:]
    if len(h) < 6:
        return None
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    return hue * 360, sat, light


def is_violet(hex_value):
    res = hue_of(hex_value)
    if not res:
        return False
    hue, sat, light = res
    return 245 <= hue <= 300 and sat > 0.35 and 0.2 < light < 0.85


# -- scanning helpers -----------------------------------------------------------

def iter_files(paths):
    for p in paths:
        p = Path(p)
        if p.is_file():
            yield p
            continue
        for f in sorted(p.rglob("*")):
            if any(part in SKIP_DIRS for part in f.relative_to(p).parts[:-1]):
                continue
            if f.is_file():
                yield f


def kind_of(path, text):
    s = path.suffix.lower()
    if path.name in SKIP_FILES or ".min." in path.name:
        return None
    if s in MARKUP:
        return "markup"
    if s in STYLE:
        return "style"
    if s == ".js" and "</" in text and re.search(r"return\s*\(?\s*<|=>\s*\(?\s*<", text):
        return "markup"
    if s in SCRIPT:
        return "script"
    if s == ".md":
        return "text"
    if s == ".json" and re.search(r"(^|/)(locales?|i18n|lang|messages|translations?)(/|$)", path.as_posix()):
        return "locale"
    if s == ".json" and re.fullmatch(r"[a-z]{2}(-[A-Za-z]{2})?\.json", path.name):
        return "locale"
    return None


def tag_spans(text, names):
    """Yield (tag, attrs, offset) for opening tags, honoring quotes and JSX braces inside the tag."""
    pat = re.compile(r"<(" + "|".join(names) + r")(?=[\s/>])", re.I)
    for m in pat.finditer(text):
        i, depth, quote = m.end(), 0, None
        while i < len(text):
            c = text[i]
            if quote:
                if c == quote:
                    quote = None
            elif c in "\"'`":
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth = max(0, depth - 1)
            elif c == ">" and depth == 0:
                break
            i += 1
        yield m.group(1).lower(), text[m.end():i], m.start()


def visible_text(markup):
    t = re.sub(r"<(script|style|svg|template)\b.*?</\1\s*>", " ", markup, flags=re.I | re.S)
    t = re.sub(r"<!--.*?-->|\{/\*.*?\*/\}", " ", t, flags=re.S)
    t = re.sub(r"\A---\n.*?\n---", " ", t, flags=re.S)  # Astro/MDX front matter
    t = re.sub(r"<[^>]*>", " ", t)
    t = re.sub(r"\{[^{}]*\}", " ", t)
    return re.sub(r"&\w+;", " ", t)


def visible_words(markup):
    body = re.search(r"<body\b.*", markup, re.I | re.S)
    return sum(1 for w in visible_text(body.group(0) if body else markup).split() if re.search(r"[A-Za-zÄÖÜäöüß]{2}", w))


def json_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from json_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from json_strings(v)


def section_signature(body):
    """Coarse shape of a section: heading level, paragraph and item buckets, media, interaction."""
    inner = re.sub(r"\A<section\b[^>]*>", "", body, flags=re.I)
    h = re.search(r"<h([1-6])\b", inner, re.I)
    paras = len(re.findall(r"<p\b", inner, re.I))
    items = len(re.findall(r"<(li|article)\b", inner, re.I))
    return (h.group(1) if h else "-", min(paras, 3), 0 if items == 0 else 1 if items < 3 else 3,
            bool(MEDIA_TAG.search(inner)), bool(INTERACTIVE_TAG.search(inner)))


def describe(sig):
    h, paras, items, media, inter = sig
    return (f"h{h}" if h != "-" else "no heading") + f", {paras}{'+' if paras == 3 else ''} paragraphs, " \
        + f"{'no' if not items else '1-2' if items == 1 else '3+'} items, " \
        + ("media" if media else "no media") + ", " + ("interactive" if inter else "static")


class Linter:
    def __init__(self, design):
        self.design = design
        self.findings = []
        self.slogans = []
        self.anim_first = None
        self.reduced = False

    def add(self, rule, path, line, detail, lines):
        ctx = lines[line - 1] if 0 < line <= len(lines) else ""
        prev = lines[line - 2] if 1 < line <= len(lines) else ""
        for src in (ctx, prev):
            m = IGNORE.search(src)
            if m:
                names = {n.strip().lower() for n in m.group(1).split(",")}
                if rule in names or "all" in names:
                    return
        sev, msg = RULES[rule]
        self.findings.append({"rule": rule, "severity": sev, "file": str(path), "line": line,
                              "message": msg, "detail": detail[:160]})

    def lint_file(self, path, display):
        try:
            if path.stat().st_size > MAX_BYTES:
                return
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        kind = kind_of(path, text)
        if not kind:
            return
        lines = text.splitlines()
        if REDUCED_MARK.search(text):
            self.reduced = True
        if kind in ("markup", "style", "script"):
            self.code_rules(display, text, lines, kind)
        if kind in ("markup", "text", "locale", "script"):
            self.copy_rules(display, text, lines, kind)

    # -- code ---------------------------------------------------------------
    def code_rules(self, path, text, lines, kind):
        num_labels = 0
        for n, line in enumerate(lines, 1):
            low = line.lower()
            if self.anim_first is None and ANIMATION_MARK.search(line) and not REDUCED_MARK.search(line):
                self.anim_first = (path, n, line.strip(), lines)
            if FONT_CONTEXT.search(line):
                for name, pat in FONT_PATTERNS:
                    if pat.search(line) and name.lower() not in self.design["fonts"]:
                        self.add("overused-font", path, n, name, lines)
            if re.search(r"background-clip\s*:\s*text|\bbg-clip-text\b", low):
                self.add("gradient-text", path, n, line.strip(), lines)
            if "gradient" in low or re.search(r"\b(from|via|to)-[a-z]+-\d", low):
                if re.search(r"\b(from|via|to)-(purple|violet|indigo|fuchsia)-\d", low) or \
                        any(is_violet(h) for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", line)):
                    self.add("ai-color-palette", path, n, line.strip(), lines)
            if re.search(r"border-(left|right|inline-start|inline-end)\s*:\s*([3-9]|\d{2})px\s+solid", low) or \
                    re.search(r"\bborder-[lrse]-([4-8])\b", low):
                self.add("side-tab", path, n, line.strip(), lines)
            for args in re.findall(r"cubic-bezier\(([^)]*)\)", low):
                try:
                    vals = [float(v) for v in args.split(",")]
                except ValueError:
                    continue
                if len(vals) != 4:
                    continue
                ys = (vals[1], vals[3])
                if any(y > STRONG_OVERSHOOT[1] or y < STRONG_OVERSHOOT[0] for y in ys):
                    self.add("bounce-easing", path, n, "cubic-bezier(" + args + ")", lines)
                elif any(not 0 <= y <= 1 for y in ys):
                    self.add("overshoot-easing", path, n, "cubic-bezier(" + args + ")", lines)
            if re.search(r"ease|easing|animation|transition|gsap|timing", low):
                if re.search(r"\b(bounce|elastic)(\.\w+)?\b|\bease(in|out|inout)?(bounce|elastic)\b", low):
                    self.add("bounce-easing", path, n, line.strip(), lines)
                elif re.search(r"\b(ease(in|out|inout)?back|backout|back\.(out|in|inout))\b", low):
                    self.add("overshoot-easing", path, n, line.strip(), lines)
            if re.search(r"scale\(\s*0\s*\)|\bscale\s*:\s*0\s*[;,}\n]|scale-0\b", low):
                self.add("scale-zero", path, n, line.strip(), lines)
            if re.search(r"\bease-in\b(?!-)", low) and "ease-in-out" not in low:
                self.add("ease-in", path, n, line.strip(), lines)
            if re.search(r"transition\s*:\s*all\b|\btransition-all\b", low):
                self.add("transition-all", path, n, line.strip(), lines)
            m = re.search(r"transition(?:-property)?\s*:\s*([^;]+)", low)
            if m and re.search(r"(^|[\s,])(width|height|top|left|right|bottom|margin|padding)\b", m.group(1)):
                self.add("layout-animation", path, n, line.strip(), lines)
            if re.search(r"\banimate-(ping|pulse)\b|@keyframes\s+(pulse|ping)", low):
                self.add("pulsing-dot", path, n, line.strip(), lines)
            if re.search(r"@keyframes\s+(blink|caret|cursor)|typewriter", low):
                self.add("blinking-cursor", path, n, line.strip(), lines)
            if re.search(r"<marquee|@keyframes\s+(marquee|scroll-x|ticker)|\bmarquee\b", low):
                self.add("marquee", path, n, line.strip(), lines)
            if re.search(r"class(name)?=[\"'{][^\"'}]*\b(eyebrow|kicker|overline)\b", low) or \
                    (re.search(r"\buppercase\b", low) and re.search(r"\btracking-(wide|wider|widest|\[0\.[1-9])", low)
                     and re.search(r"\btext-(xs|sm|\[1[0-3]px\])", low)):
                self.add("eyebrow-label", path, n, line.strip(), lines)
            if re.search(r">\s*(0[1-9]|[1-9])\s*(/|—|–|\.)?\s*<", line) or re.search(r">\s*0[1-9]\s*[/—–.]", line):
                num_labels += 1
                if num_labels == 3:
                    self.add("numbered-section-labels", path, n, line.strip(), lines)
            if "radial-gradient" in low and re.search(r"transparent|rgba\([^)]*,\s*0(\.0+)?\)|/\s*0(\.0+)?\)", low) \
                    and re.search(r"#[0-9a-f]{3,8}|rgba?\(|hsla?\(|oklch\(", low):
                self.add("radial-halo", path, n, line.strip(), lines)
            m = re.search(r"(box|text)-shadow\s*:\s*0(px)?\s+0(px)?\s+(\d+)px[^;]*", low)
            if m and int(m.group(4)) >= 12 and not re.search(r"rgba?\(\s*0\s*,\s*0\s*,\s*0|#000\b|black", m.group(0)):
                self.add("dark-glow", path, n, line.strip(), lines)
            if "repeating-linear-gradient" in low or \
                    (re.search(r"linear-gradient\([^)]*\b1px\b", low) and "background-size" in text.lower()):
                self.add("grid-background", path, n, line.strip(), lines)
            for px in re.findall(r"font-size\s*:\s*(\d+(?:\.\d+)?)px|text-\[(\d+(?:\.\d+)?)px\]", low):
                v = float(px[0] or px[1])
                if v < 12:
                    self.add("tiny-text", path, n, f"{v}px", lines)
            for em in re.findall(r"letter-spacing\s*:\s*(-?\d*\.?\d+)em|tracking-\[(-?\d*\.?\d+)em\]", low):
                v = float(em[0] or em[1])
                if v >= 0.1:
                    self.add("wide-tracking", path, n, f"{v}em", lines)
                elif v < -0.04:
                    self.add("extreme-negative-tracking", path, n, f"{v}em", lines)
            if re.search(r"text-align\s*:\s*justify|\btext-justify\b", low):
                self.add("justified-text", path, n, line.strip(), lines)
            if self.design["colors"] and kind in ("style", "markup"):
                for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", line):
                    if len(h) - 1 in (3, 4, 6, 8) and norm_hex(h) not in self.design["colors"] | {"#ffffff", "#000000"}:
                        self.add("design-system-color", path, n, h, lines)
            if self.design["fonts"]:
                m = re.search(r"font-family\s*:\s*([^;}{]+)", line, re.I)
                if m:
                    first = m.group(1).split(",")[0].strip().strip("\"'").lower()
                    if first and not first.startswith("var(") and first not in GENERIC_FAMILIES \
                            and first not in self.design["fonts"]:
                        self.add("design-system-font", path, n, first, lines)
        if kind == "markup":
            self.tag_rules(path, text, lines)
            self.section_rules(path, text, lines)

    def tag_rules(self, path, text, lines):
        def line_of(offset):
            return text.count("\n", 0, offset) + 1
        for tag, attrs, off in tag_spans(text, ["button", "a", "input", "select", "textarea", "form", "img"]):
            n = line_of(off)
            if tag == "img":
                if not re.search(r"(?<![\w-])alt\s*=|(?<![\w-])alt(?=[\s/>]|$)", attrs):
                    self.add("img-alt", path, n, "<img" + attrs[:80], lines)
                if re.search(r"(?<![\w-])src\s*=\s*(\"\"|''|\{\s*\}|\{\s*[\"']{2}\s*\})", attrs) or \
                        re.search(r"(?<![\w-])src\s*=\s*[\"'](#|about:blank)", attrs):
                    self.add("broken-image", path, n, "<img" + attrs[:80], lines)
                continue
            if tag == "input" and re.search(r"type\s*=\s*[\"']hidden", attrs, re.I):
                continue
            if "{..." in attrs.replace(" ", ""):
                continue  # spread props may carry the test id
            if not re.search(r"\b(data-testid|data-test-id|testID)\s*=", attrs):
                self.add("missing-testid", path, n, "<" + tag + attrs[:80], lines)
        for n, line in enumerate(lines, 1):
            if re.search(PLACEHOLDER_HOSTS, line, re.I):
                self.add("placeholder-image", path, n, line.strip(), lines)

    def section_rules(self, path, text, lines):
        """uniform-sections, text-heavy and long-paragraph for one markup file."""
        def line_of(offset):
            return text.count("\n", 0, offset) + 1
        blocks, depth, start = [], 0, None
        for m in re.finditer(r"<(/?)section\b[^>]*>", text, re.I):
            if not m.group(1):
                if depth == 0:
                    start = m.start()
                depth += 1
            elif depth:
                depth -= 1
                if depth == 0:
                    blocks.append((start, text[start:m.end()]))
        run, prev = 0, None
        for off, body in blocks:
            sig = section_signature(body)
            run = run + 1 if sig == prev else 1
            prev = sig
            if run == 3:
                self.add("uniform-sections", path, line_of(off), "same shape: " + describe(sig), lines)
        words = visible_words(text)
        if words > PAGE_WORDS:
            self.add("text-heavy", path, 1, f"{words} visible words (tendency: under {PAGE_WORDS})", lines)
        for m in re.finditer(r"<p\b[^>]*>(.*?)</p>", text, re.I | re.S):
            count = len(visible_text(m.group(1)).split())
            if count > PARAGRAPH_WORDS:
                self.add("long-paragraph", path, line_of(m.start()), f"{count} words", lines)

    # -- copy ---------------------------------------------------------------
    def copy_rules(self, path, text, lines, kind):
        prose_chars, dashes = 0, 0
        for n, raw in enumerate(lines, 1):
            line = raw.strip()
            if not line or line.startswith(("//", "/*", "*", "import ", "export ", "@")):
                continue
            if kind == "script" and not re.search(r"[\"'`][^\"'`]*[a-zäöü]{3,}\s[^\"'`]*[\"'`]", line):
                continue  # only string literals with words carry copy in plain scripts
            low = line.lower()
            # locale JSON may be minified into one line, so braces there are structure, not template code
            prose = line if kind == "locale" else re.sub(r"<[^>]+>|\{[^}]*\}|class(Name)?=\"[^\"]*\"", " ", line)
            prose_chars += len(prose)
            dashes += prose.count("—")
            if re.search(r"lorem ipsum|dolor sit amet", low):
                self.add("lorem-ipsum", path, n, line, lines)
            for pat in STRONG_BUZZ:
                m = re.search(r"\b" + pat + r"\b", prose, re.I)
                if m:
                    self.add("marketing-buzzword", path, n, m.group(0), lines)
            for pat in SOFT_BUZZ:
                m = re.search(r"\b" + pat + r"\b", prose, re.I)
                if m:
                    self.add("soft-buzzword", path, n, m.group(0), lines)
            if re.search(r"\w+theater\b|\btheater\b|\btheatre\b", prose, re.I) and \
                    not re.search(r"\b(kino|bühne|stage|schauspiel)", prose, re.I):
                self.add("theater-phrase", path, n, line, lines)
            if re.search(r"\?[\s\"'<>/a-z]*[^?.!]{3,90}\?[\s\"'<>/a-z]*[^?.!]{3,90}\?", prose, re.I):
                self.add("rhetorical-questions", path, n, line, lines)
            for cta in VAGUE_CTA:
                if re.search(r"(>|[\"':]\s*[\"']?)\s*" + re.escape(cta) + r"\s*(→|->|›|»)?\s*(<|[\"'])", low):
                    self.add("vague-cta", path, n, cta, lines)
                    break
            if re.search(r"<h[1-6][^>]*>[^<]*!\s*</h[1-6]>", line, re.I) or \
                    (kind == "text" and re.match(r"#{1,6}\s.*!\s*$", line)):
                self.add("exclamation-heading", path, n, line, lines)
            for seg in re.findall(r"(?:>|[\"'])\s*([^<>\"']{3,70})\s*(?:<|[\"'])", line) or [prose]:
                seg = seg.strip()
                if re.fullmatch(r"[A-ZÄÖÜ][^.!?]{1,30}[.!]\s+[A-ZÄÖÜ][^.!?]{1,40}[.!]", seg) or \
                        re.fullmatch(r"[A-ZÄÖÜ][^.!?]{1,30}\.\s+(?:Kein|Keine|Nur|Just|No|Not)\b[^.!?]{1,40}\.", seg):
                    self.slogans.append((path, n, seg, lines))
        if kind == "locale":
            try:
                words = sum(len(v.split()) for v in json_strings(json.loads(text)))
            except ValueError:
                words = 0
            if words > LOCALE_WORDS:
                self.add("text-heavy", path, 1, f"{words} words in this locale file (tendency: under {LOCALE_WORDS})",
                         lines)
        if dashes >= 4 and prose_chars and dashes / prose_chars > 1 / 350:
            self.add("em-dash-overuse", path, 1, f"{dashes} em dashes in {prose_chars} characters", lines)

    def finish(self):
        if self.anim_first and not self.reduced:
            path, n, detail, lines = self.anim_first
            self.add("no-reduced-motion", path, n, detail, lines)
        if len(self.slogans) >= 3:
            for path, n, seg, lines in self.slogans:
                self.add("two-beat-slogan", path, n, seg, lines)


def lint(paths, design_path=None):
    roots = [Path(p) for p in paths]
    if design_path is None:
        for cand in [Path("DESIGN.md")] + [r / "DESIGN.md" for r in roots if r.is_dir()]:
            if cand.exists():
                design_path = cand
                break
    design = read_design(Path(design_path) if design_path else None)
    linter = Linter(design)
    for f in iter_files(roots):
        linter.lint_file(f, f.as_posix())
    linter.finish()
    seen, unique = set(), []
    for f in linter.findings:
        key = (f["rule"], f["file"], f["line"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    unique.sort(key=lambda f: (f["severity"] != "error", f["file"], f["line"]))
    return {
        "tool": "website-creator-lint", "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "paths": [str(p) for p in roots], "design": str(design_path) if design["found"] else None,
        "findings": unique,
        "summary": {"errors": sum(f["severity"] == "error" for f in unique),
                    "warnings": sum(f["severity"] == "warning" for f in unique)},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--design", help="DESIGN.md to read fonts and colors from (default: ./DESIGN.md)")
    ap.add_argument("--out", help="write the JSON report here (the run gate reads .website-creator/lint.json)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--rules", action="store_true", help="list the rules and exit")
    args = ap.parse_args(argv)
    if args.rules:
        for name, (sev, msg) in RULES.items():
            print(f"{sev:7} {name:26} {msg}")
        return 0
    report = lint(args.paths or ["."], args.design)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for f in report["findings"]:
            print(f"{f['file']}:{f['line']}: {f['severity']} {f['rule']}: {f['detail']}")
        s = report["summary"]
        print(f"lint: {s['errors']} errors, {s['warnings']} warnings")
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
