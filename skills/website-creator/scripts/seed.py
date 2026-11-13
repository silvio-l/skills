#!/usr/bin/env python3
"""Seeded direction generator for website-creator: three distinct visual starting points per run.

Usage:
  seed.py [--project .] roll [--seed TEXT] [--brand #hex] [--count 3] [--json]
  seed.py [--project .] pick N [--out DESIGN.md] [--force]
  seed.py [--project .] history

`roll` derives layout archetype, type pairing, surface mode, OKLCH palette and a motion tier from a SHA-256 seed,
skipping combinations used in recent runs (.website-creator/history.json), and stores them in
.website-creator/directions.json. `pick` records the chosen direction and writes a DESIGN.md skeleton from it.
Without --brand a hue is derived from the seed (never violet). Stdlib only.
"""
import argparse
import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

STATE_DIR = ".website-creator"
RECENT = 6

ARCHETYPES = [
    ("editorial-column", "One strong reading column, generous margins, headline set large and left; sections separated by type, not boxes."),
    ("split-statement", "Hero split asymmetrically (roughly 7/5): statement on one side, product proof on the other; alternating weight below."),
    ("product-stage", "The product UI is the hero, shown large and real; copy frames it from above and below, sparse chrome."),
    ("index-list", "Content as a typographic index: numbered or ruled rows, dense and scannable, like a good table of contents."),
    ("poster-blocks", "Few large full-bleed blocks with one idea each; big type, hard color changes between blocks."),
    ("narrative-scroll", "A guided sequence: each viewport advances one step of the story; pinned visual with changing captions."),
    ("catalog-grid", "An uneven grid of concrete items (features, use cases, screens) with varied cell sizes and no icon tiles."),
    ("letter", "Reads like a personal letter from the maker: narrow measure, first person, signature, few but precise visuals."),
]

FONT_PAIRS = [
    ("Bricolage Grotesque", "Source Sans 3"),
    ("Familjen Grotesk", "Literata"),
    ("Schibsted Grotesk", "Source Serif 4"),
    ("Hanken Grotesk", "Newsreader"),
    ("IBM Plex Sans Condensed", "IBM Plex Serif"),
    ("Syne", "Work Sans"),
    ("Unbounded", "Onest"),
    ("Young Serif", "Figtree"),
    ("Big Shoulders Display", "Public Sans"),
    ("Gloock", "Atkinson Hyperlegible Next"),
]

SURFACES = ["light", "dark", "brand"]
MOTION = ["restrained", "signature", "video"]
MOTION_TEXT = {
    "restrained": "CSS transitions and scroll-driven animation (animation-timeline: view()), no JS animation library.",
    "signature": "One signature moment with GSAP/ScrollTrigger, a shader or Three.js; everything else restrained.",
    "video": "A HyperFrames-rendered product video as the centerpiece; page motion otherwise minimal.",
}
RATIOS = [1.2, 1.25, 1.333, 1.414, 1.5]
VIOLET = (265.0, 330.0)  # OKLCH hue range treated as violet/purple


# ---------- color math (OKLab, Björn Ottosson) ----------

def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_rgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"not a hex color: {h!r}")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in rgb)


def rgb_to_oklch(rgb):
    r, g, b = (srgb_to_linear(c) for c in rgb)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    bb = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def oklch_to_linear(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def in_gamut(lin, eps=1e-4):
    return all(-eps <= c <= 1 + eps for c in lin)


def oklch_to_hex(L, C, H):
    """Clamp chroma (binary search) until the color fits sRGB, then encode."""
    L = max(0.0, min(1.0, L))
    if not in_gamut(oklch_to_linear(L, C, H)):
        lo, hi = 0.0, C
        for _ in range(30):
            mid = (lo + hi) / 2
            if in_gamut(oklch_to_linear(L, mid, H)):
                lo = mid
            else:
                hi = mid
        C = lo
    return rgb_to_hex(tuple(linear_to_srgb(max(0.0, min(1.0, c))) for c in oklch_to_linear(L, C, H)))


def luminance(hex_value):
    r, g, b = (srgb_to_linear(c) for c in hex_to_rgb(hex_value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def is_violet(h):
    return VIOLET[0] <= h % 360 <= VIOLET[1]


def is_cream(hex_value):
    """Warm, light, slightly saturated surface: the reflexive 'tasteful' AI background."""
    L, C, H = rgb_to_oklch(hex_to_rgb(hex_value))
    return L > 0.88 and C > 0.012 and 50 <= H <= 110


def away_from_violet(h):
    h %= 360
    if not is_violet(h):
        return h
    return VIOLET[0] - 10 if h - VIOLET[0] < VIOLET[1] - h else (VIOLET[1] + 10) % 360


def fit_lightness(L, C, H, against, target, step):
    """Move lightness in `step` direction until contrast against `against` reaches `target`."""
    for _ in range(100):
        hx = oklch_to_hex(L, C, H)
        if contrast(hx, against) >= target or not 0.0 < L < 1.0:
            return hx
        L += step
    return oklch_to_hex(L, C, H)


# ---------- generation ----------

class Rng:
    """Deterministic stream of integers from SHA-256(seed:counter)."""

    def __init__(self, seed):
        self.seed, self.n = seed, 0

    def int(self, k):
        self.n += 1
        return int.from_bytes(hashlib.sha256(f"{self.seed}:{self.n}".encode()).digest()[:8], "big") % k

    def shuffled(self, items):
        items = list(items)
        for i in range(len(items) - 1, 0, -1):
            j = self.int(i + 1)
            items[i], items[j] = items[j], items[i]
        return items


def palette(brand_hex, surface, rng):
    bL, bC, bH = rgb_to_oklch(hex_to_rgb(brand_hex))
    tint_c = min(0.02, max(0.006, bC * 0.12))
    if 50 <= bH <= 110:  # warm brand: keep light neutrals from drifting into cream
        tint_c = min(tint_c, 0.008)
    if surface == "light":
        bg = oklch_to_hex(0.985, tint_c * 0.5, bH)
        bg2 = oklch_to_hex(0.955, tint_c, bH)
        ink = fit_lightness(0.24, tint_c * 1.5, bH, bg, 12.0, -0.02)
        muted = fit_lightness(0.48, tint_c, bH, bg, 4.8, -0.02)
        line = oklch_to_hex(0.88, tint_c, bH)
    elif surface == "dark":
        bg = oklch_to_hex(0.17, tint_c * 1.5, bH)
        bg2 = oklch_to_hex(0.22, tint_c * 1.5, bH)
        ink = fit_lightness(0.94, tint_c * 0.5, bH, bg, 12.0, 0.01)
        muted = fit_lightness(0.72, tint_c, bH, bg, 4.8, 0.02)
        line = oklch_to_hex(0.32, tint_c, bH)
    else:  # brand-colored surface
        L = 0.3 if bL < 0.6 else 0.9
        bg = oklch_to_hex(L, min(bC, 0.14), bH)
        bg2 = oklch_to_hex(L + (0.05 if L < 0.5 else -0.05), min(bC, 0.12), bH)
        step = 0.02 if L < 0.5 else -0.02
        ink = fit_lightness(0.97 if L < 0.5 else 0.2, 0.01, bH, bg, 10.0, step)
        muted = fit_lightness(0.85 if L < 0.5 else 0.35, 0.02, bH, bg, 4.8, step)
        line = oklch_to_hex(L + (0.12 if L < 0.5 else -0.12), min(bC, 0.08), bH)
    rotation = [150, 180, 210, 35, -35, 120][rng.int(6)]
    aH = away_from_violet(bH + rotation)
    dark_bg = luminance(bg) < 0.18
    accent = fit_lightness(0.72 if dark_bg else 0.55, 0.16, aH, bg, 3.0, 0.02 if dark_bg else -0.02)
    brand_ink = brand_hex.lower() if contrast(brand_hex, bg) >= 4.5 else \
        fit_lightness(bL, bC, bH, bg, 4.5, 0.02 if dark_bg else -0.02)
    colors = {"surface": bg, "surface-2": bg2, "ink": ink, "ink-muted": muted, "line": line,
              "brand": brand_hex.lower(), "brand-ink": brand_ink, "accent": accent}
    checks = {"ink/surface": round(contrast(ink, bg), 2), "ink-muted/surface": round(contrast(muted, bg), 2),
              "brand-ink/surface": round(contrast(brand_ink, bg), 2), "accent/surface": round(contrast(accent, bg), 2)}
    return colors, checks


def seed_brand(seed):
    h = int.from_bytes(hashlib.sha256(f"{seed}:brand".encode()).digest()[:4], "big") % 360
    return oklch_to_hex(0.55, 0.15, away_from_violet(h))


def combo_key(arch, pair):
    return f"{arch}|{pair}"


def roll(seed, brand, count, recent):
    rng = Rng(seed)
    brand = brand or seed_brand(seed)
    hex_to_rgb(brand)  # validate
    used = set(recent)
    archs = rng.shuffled(range(len(ARCHETYPES)))
    pairs = rng.shuffled(range(len(FONT_PAIRS)))
    surfaces = rng.shuffled(SURFACES)
    motions = rng.shuffled(MOTION)
    chosen = []
    candidates = [(a, p) for a in archs for p in pairs]
    taken_a, taken_p = set(), set()
    for strict in (True, False):
        for a, p in candidates:
            if len(chosen) >= count:
                break
            if a in taken_a or p in taken_p:
                continue
            if strict and combo_key(ARCHETYPES[a][0], " + ".join(FONT_PAIRS[p])) in used:
                continue
            chosen.append((a, p))
            taken_a.add(a)
            taken_p.add(p)
    out = []
    for i, (a, p) in enumerate(chosen):
        surface = surfaces[i % len(surfaces)]
        colors, checks = palette(brand, surface, rng)
        display, body = FONT_PAIRS[p]
        out.append({
            "n": i + 1,
            "key": combo_key(ARCHETYPES[a][0], f"{display} + {body}"),
            "archetype": {"name": ARCHETYPES[a][0], "brief": ARCHETYPES[a][1]},
            "type": {"display": display, "body": body, "ratio": RATIOS[rng.int(len(RATIOS))]},
            "surface": surface,
            "colors": colors,
            "contrast": checks,
            "motion": {"tier": motions[i % len(motions)], "brief": MOTION_TEXT[motions[i % len(motions)]]},
            "radius": [0, 2, 4, 8, 14][rng.int(5)],
            "space-base": [4, 6, 8][rng.int(3)],
        })
    return {"seed": seed, "brand": brand.lower(), "directions": out}


# ---------- files ----------

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def design_md(d, brand):
    c, t = d["colors"], d["type"]
    sizes = [round(16 * t["ratio"] ** k) for k in range(-1, 5)]
    lines = ["---", f"# Generated by website-creator seed.py from direction {d['n']} ({d['key']}); edit freely.",
             "colors:"]
    lines += [f"  {k}: \"{v}\"" for k, v in c.items()]
    lines += ["typography:",
              f"  display: {{fontFamily: \"{t['display']}\", weight: 700}}",
              f"  body: {{fontFamily: \"{t['body']}\", weight: 400, lineHeight: 1.55}}",
              f"  scale: [{', '.join(str(s) for s in sizes)}]",
              f"rounded: [0, {d['radius']}, {d['radius'] * 2}, 999]",
              f"spacing: {{base: {d['space-base']}}}",
              f"motion: {d['motion']['tier']}",
              "---", "",
              "# Design system", "",
              f"Layout archetype: **{d['archetype']['name']}**. {d['archetype']['brief']}", "",
              f"Surface: {d['surface']}. Brand color {brand} is binding; `brand-ink` is its text-safe variant.", "",
              f"Motion: {d['motion']['brief']}", "",
              "## Contrast", ""]
    lines += [f"- {k}: {v}:1" for k, v in d["contrast"].items()]
    lines += ["", "## Decisions", "", "Record every deviation from this file here, with the reason.", ""]
    return "\n".join(lines)


def cmd_roll(args, root):
    history = load_json(root / STATE_DIR / "history.json", [])
    recent = [h["key"] for h in history[-RECENT:]]
    seed = args.seed or f"{root.resolve().name}:{date.today().isoformat()}"
    result = roll(seed, args.brand, args.count, recent)
    (root / STATE_DIR).mkdir(parents=True, exist_ok=True)
    (root / STATE_DIR / "directions.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"seed {result['seed']!r}, brand {result['brand']}")
    for d in result["directions"]:
        c = d["colors"]
        print(f"\n[{d['n']}] {d['archetype']['name']} · {d['type']['display']} / {d['type']['body']} · "
              f"{d['surface']} · motion {d['motion']['tier']}")
        print(f"    {d['archetype']['brief']}")
        print(f"    surface {c['surface']} ink {c['ink']} brand-ink {c['brand-ink']} accent {c['accent']} "
              f"· ratio {d['type']['ratio']} · radius {d['radius']}px")
    print(f"\nstored in {STATE_DIR}/directions.json; choose with `seed.py pick N`")
    return 0


def cmd_pick(args, root):
    data = load_json(root / STATE_DIR / "directions.json", None)
    if not data:
        print("no directions rolled yet (run `seed.py roll`)", file=sys.stderr)
        return 2
    match = [d for d in data["directions"] if d["n"] == args.n]
    if not match:
        print(f"no direction {args.n}", file=sys.stderr)
        return 2
    d = match[0]
    if args.motion:  # the user picks the motion tier independently of the direction
        d = {**d, "motion": {"tier": args.motion, "brief": MOTION_TEXT[args.motion]}}
    out = root / args.out
    if out.exists() and not args.force:
        print(f"{out} exists; merge the direction by hand or pass --force", file=sys.stderr)
    else:
        out.write_text(design_md(d, data["brand"]), encoding="utf-8")
        print(f"wrote {out}")
    history_path = root / STATE_DIR / "history.json"
    history = load_json(history_path, [])
    history.append({"key": d["key"], "seed": data["seed"],
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    print(f"recorded {d['key']}")
    return 0


def cmd_history(args, root):
    for h in load_json(root / STATE_DIR / "history.json", []):
        print(f"{h.get('at', '?')}  {h['key']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("roll")
    r.add_argument("--seed")
    r.add_argument("--brand", help="binding brand color as #hex")
    r.add_argument("--count", type=int, default=3)
    r.add_argument("--json", action="store_true")
    p = sub.add_parser("pick")
    p.add_argument("n", type=int)
    p.add_argument("--out", default="DESIGN.md")
    p.add_argument("--force", action="store_true")
    p.add_argument("--motion", choices=MOTION, help="override the direction's motion tier with the user's choice")
    sub.add_parser("history")
    args = ap.parse_args(argv)
    root = Path(args.project)
    try:
        return {"roll": cmd_roll, "pick": cmd_pick, "history": cmd_history}[args.cmd](args, root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
