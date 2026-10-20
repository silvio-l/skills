#!/usr/bin/env python3
"""Inventory a repository for video planning (phase A of motion-video-planner).

Walks the whole repository once, classifies every file by role (code, docs,
tests, UI strings, design tokens, marketing, media, generated, dependency
lock, binary, ...), and surfaces the leads a video planner needs: brand and
logo candidates, fonts, frequent colors, media assets with pixel sizes, key
docs, and marketing material. It never prints file contents; it tells the
agent where to read next and what it deliberately did not read.

Stdlib only. Read-only. Classification is heuristic by design - the report
says so, and the agent must verify every lead it relies on.

Usage:
    python3 inventory_repo.py <repo-root> [--json out.json] [--max-list 40]
"""

import argparse
import collections
import json
import os
import re
import struct
import subprocess
import sys

# Directories never descended into; reported as excluded with a reason.
EXCLUDED_DIRS = {
    ".git": "VCS metadata",
    "node_modules": "installed dependencies",
    "bower_components": "installed dependencies",
    "vendor": "vendored dependencies",
    "Pods": "installed CocoaPods dependencies",
    ".venv": "Python virtualenv",
    "venv": "Python virtualenv",
    "__pycache__": "bytecode cache",
    ".gradle": "build cache",
    "DerivedData": "Xcode build output",
    ".next": "build output",
    ".nuxt": "build output",
    ".svelte-kit": "build output",
    ".expo": "Expo cache",
    ".turbo": "build cache",
    ".cache": "cache",
    ".dart_tool": "build cache",
    "target": "build output",
    "dist": "build output",
    "build": "build output",
    "out": "build output",
    "coverage": "test coverage output",
    ".transcode-cache": "HyperFrames media proxies",
}

LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock",
    "Podfile.lock", "composer.lock", "Cargo.lock", "poetry.lock", "Gemfile.lock",
    "pubspec.lock", "uv.lock", "go.sum", "Package.resolved", "skills-lock.json",
}

EXT_GROUPS = {
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".icns",
              ".avif", ".heic", ".bmp", ".tif", ".tiff"},
    "video": {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi"},
    "audio": {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".aif", ".aiff"},
    "font": {".ttf", ".otf", ".woff", ".woff2"},
    "3d": {".glb", ".gltf", ".fbx", ".obj", ".blend", ".usdz", ".stl"},
    "animation": {".lottie", ".riv"},
    "design-source": {".fig", ".sketch", ".psd", ".ai", ".xd", ".afdesign", ".pdf"},
    "docs": {".md", ".mdx", ".rst", ".adoc", ".txt"},
    "code": {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".swift", ".kt",
             ".kts", ".java", ".dart", ".go", ".rs", ".rb", ".php", ".cs", ".cpp",
             ".c", ".h", ".hpp", ".m", ".mm", ".vue", ".svelte", ".astro", ".gd",
             ".lua", ".sh", ".ps1", ".sql", ".html", ".css", ".scss", ".sass", ".less"},
    "config": {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".plist",
               ".gradle", ".properties", ".env.example"},
}
MEDIA_GROUPS = ("image", "video", "audio", "font", "3d", "animation", "design-source")

I18N_EXTS = {".arb", ".strings", ".stringsdict", ".xliff", ".xlf", ".po", ".pot", ".resx"}
I18N_DIR_RE = re.compile(r"(^|/)(locales?|i18n|l10n|lang|langs|translations|messages)(/|$)", re.I)
TEST_RE = re.compile(
    r"(^|/)(tests?|__tests__|spec|e2e|integration_test|androidTest|XCTest\w*)(/|$)"
    r"|(\.|_)(test|spec)\.\w+$|(^|/)test_[^/]+\.py$|Tests?\.(swift|kt|java)$", re.I)
MARKETING_RE = re.compile(
    r"(^|/)(marketing|press|press-?kit|media-?kit|brand(ing)?|website|landing|site|"
    r"store|app-?store|play-?store|fastlane|screenshots?|promo|social|campaigns?|"
    r"blog|docs/marketing)(/|$)", re.I)
TOKEN_RE = re.compile(
    r"(^|/)(tailwind\.config\.\w+|[^/]*theme\.\w+|[^/]*tokens?(\.\w+)?\.\w+|"
    r"colors?\.\w+|palette\.\w+|frame\.md|design\.md|styles?/variables\.\w+)$"
    r"|(^|/)(design-?system|design-?tokens|tokens|theme)(/|$)", re.I)
BRAND_NAME_RE = re.compile(r"logo|brand|wordmark|mascot|icon|favicon|lockup|emblem|badge", re.I)
GENERATED_RE = re.compile(r"\.min\.(js|css)$|\.map$|\.g\.dart$|\.generated\.\w+$|\.pb\.\w+$|"
                          r"(^|/)generated(/|$)|(^|/)__generated__(/|$)", re.I)
KEY_DOC_RE = re.compile(r"(^|/)(README|CHANGELOG|ROADMAP|CONTEXT|PRODUCT|FEATURES|"
                        r"CLAUDE|AGENTS|SPEC|PRD|BRAND)[^/]*\.(md|mdx|txt)$", re.I)

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
FONT_RE = re.compile(r"font-family\s*:\s*([^;}{\n]+)|fontFamily\s*[:=]\s*['\"\[]([^'\"\]\n]+)", re.I)
COLOR_SCAN_EXTS = {".css", ".scss", ".sass", ".less", ".ts", ".tsx", ".js", ".jsx",
                   ".json", ".dart", ".swift", ".kt", ".md", ".svg", ".vue", ".svelte", ".astro"}
COLOR_SCAN_MAX_BYTES = 200_000
BINARY_SNIFF_BYTES = 8192
LARGE_FILE_BYTES = 5_000_000


def list_files(root):
    """Return (relative paths, excluded dir counts, source of the listing)."""
    excluded = collections.Counter()
    if os.path.isdir(os.path.join(root, ".git")):
        try:
            out = subprocess.run(
                ["git", "-C", root, "ls-files", "-co", "--exclude-standard", "-z"],
                capture_output=True, check=True).stdout
            paths = [p for p in out.decode("utf-8", "replace").split("\0") if p]
            kept = []
            for p in paths:
                parts = p.split("/")
                hit = next((d for d in parts[:-1] if d in EXCLUDED_DIRS), None)
                if hit:
                    excluded[hit] += 1
                else:
                    kept.append(p)
            for name in EXCLUDED_DIRS:
                if name != ".git" and os.path.isdir(os.path.join(root, name)) and name not in excluded:
                    excluded[name] += 0  # present on disk but gitignored
            return sorted(kept), excluded, "git ls-files (tracked + untracked, .gitignore respected)"
        except (OSError, subprocess.CalledProcessError):
            pass
    kept = []
    for dirpath, dirnames, filenames in os.walk(root):
        for d in list(dirnames):
            if d in EXCLUDED_DIRS:
                excluded[d] += 1
                dirnames.remove(d)
        for f in filenames:
            kept.append(os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/"))
    return sorted(kept), excluded, "filesystem walk (no git; default exclusions applied)"


def ext_of(path):
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".env.example"):
        return ".env.example"
    return os.path.splitext(name)[1].lower()


def is_binary(abs_path):
    try:
        with open(abs_path, "rb") as fh:
            return b"\0" in fh.read(BINARY_SNIFF_BYTES)
    except OSError:
        return False


def classify(path, abs_path):
    """Return (primary category, set of tags)."""
    name = path.rsplit("/", 1)[-1]
    ext = ext_of(path)
    tags = set()
    if MARKETING_RE.search(path):
        tags.add("marketing")
    if TOKEN_RE.search(path):
        tags.add("design-tokens")
    if I18N_DIR_RE.search(path) or ext in I18N_EXTS:
        tags.add("ui-strings")
    if KEY_DOC_RE.search(path):
        tags.add("key-doc")
    if name in LOCKFILES:
        return "dependency-lock", tags
    if GENERATED_RE.search(path):
        return "generated", tags
    for group in MEDIA_GROUPS:
        if ext in EXT_GROUPS[group]:
            if BRAND_NAME_RE.search(path):
                tags.add("brand-candidate")
            return group, tags
    if TEST_RE.search(path):
        return "tests", tags
    if ext in I18N_EXTS:
        return "ui-strings", tags
    if ext in EXT_GROUPS["docs"]:
        return "docs", tags
    if ext in EXT_GROUPS["code"]:
        return "code", tags
    if ext in EXT_GROUPS["config"]:
        return ("ui-strings" if "ui-strings" in tags else "config"), tags
    if is_binary(abs_path):
        return "binary-other", tags
    return "other-text", tags


def image_size(abs_path, ext):
    """Pixel size from the file header (PNG, GIF, JPEG, SVG viewBox); None if unknown."""
    try:
        with open(abs_path, "rb") as fh:
            head = fh.read(65536)
    except OSError:
        return None
    if ext == ".png" and head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 24:
        return struct.unpack(">II", head[16:24])
    if ext == ".gif" and head[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", head[6:10])
    if ext in (".jpg", ".jpeg") and head[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(head):
            if head[i] != 0xFF:
                i += 1
                continue
            marker = head[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", head[i + 5:i + 9])
                return (w, h)
            seg_len = struct.unpack(">H", head[i + 2:i + 4])[0]
            i += 2 + seg_len
        return None
    if ext == ".svg":
        text = head.decode("utf-8", "replace")
        m = re.search(r'viewBox\s*=\s*["\']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', text)
        if m:
            return (round(float(m.group(1))), round(float(m.group(2))))
    return None


def normalize_hex(h):
    h = h.lower()
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    return h


def scan_colors_and_fonts(root, files_by_cat):
    """Map hex colors and font families to the files that mention them."""
    colors = collections.defaultdict(set)
    fonts = collections.defaultdict(set)
    skipped = 0
    candidates = [p for cat in ("code", "config", "docs", "image", "other-text")
                  for p in files_by_cat.get(cat, []) if ext_of(p) in COLOR_SCAN_EXTS]
    for p in candidates:
        abs_path = os.path.join(root, p)
        try:
            if os.path.getsize(abs_path) > COLOR_SCAN_MAX_BYTES:
                skipped += 1
                continue
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        prose = ext_of(p) in (".md", ".txt")
        for h in HEX_RE.findall(text):
            if prose and h[1:].isdigit():
                continue  # "#123" in prose is an issue/PR reference, not a color
            colors[normalize_hex(h)].add(p)
        for m in FONT_RE.finditer(text):
            raw = (m.group(1) or m.group(2) or "").strip()
            first = raw.split(",")[0].strip().strip("'\"")
            if first and not first.startswith(("var(", "inherit", "$", "{")):
                fonts[first].add(p)
    return colors, fonts, skipped


def build_inventory(root, max_list=40):
    root = os.path.abspath(root)
    files, excluded, source = list_files(root)
    files_by_cat = collections.defaultdict(list)
    tagged = collections.defaultdict(list)
    sizes = {}
    unreadable = []
    for p in files:
        abs_path = os.path.join(root, p)
        if not os.path.isfile(abs_path):
            unreadable.append(p)  # deleted-but-tracked, broken symlink, submodule
            continue
        cat, tags = classify(p, abs_path)
        files_by_cat[cat].append(p)
        for t in tags:
            tagged[t].append(p)
        try:
            sizes[p] = os.path.getsize(abs_path)
        except OSError:
            sizes[p] = 0

    media = []
    for group in MEDIA_GROUPS:
        for p in files_by_cat.get(group, []):
            entry = {"path": p, "kind": group, "bytes": sizes.get(p, 0)}
            if group == "image":
                dims = image_size(os.path.join(root, p), ext_of(p))
                if dims:
                    entry["px"] = list(dims)
            media.append(entry)

    colors, fonts, color_skipped = scan_colors_and_fonts(root, files_by_cat)
    token_files = set(tagged.get("design-tokens", []))
    # Colors defined in token/theme files outrank colors that merely recur elsewhere.
    top_colors = sorted(colors.items(),
                        key=lambda kv: (-len(kv[1] & token_files), -len(kv[1]), kv[0]))[:max_list]
    top_fonts = sorted(fonts.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:max_list]
    top_level = collections.Counter(p.split("/")[0] if "/" in p else "(root files)" for p in files)

    return {
        "root": root,
        "listing_source": source,
        "total_files": len(files),
        "counts": {k: len(v) for k, v in sorted(files_by_cat.items())},
        "excluded_dirs": {k: {"files_skipped": v, "reason": EXCLUDED_DIRS[k]}
                          for k, v in sorted(excluded.items())},
        "unreadable": unreadable,
        "top_level": dict(top_level.most_common()),
        "key_docs": sorted(tagged.get("key-doc", [])),
        "docs": files_by_cat.get("docs", []),
        "marketing": sorted(tagged.get("marketing", [])),
        "design_tokens": sorted(tagged.get("design-tokens", [])),
        "ui_strings": sorted(tagged.get("ui-strings", [])),
        "brand_candidates": sorted(tagged.get("brand-candidate", [])),
        "tests": files_by_cat.get("tests", []),
        "media": media,
        "large_files": sorted(([p, s] for p, s in sizes.items() if s >= LARGE_FILE_BYTES),
                              key=lambda x: -x[1]),
        "generated": files_by_cat.get("generated", []),
        "dependency_locks": files_by_cat.get("dependency-lock", []),
        "binary_other": files_by_cat.get("binary-other", []),
        "colors": [{"hex": h, "files": len(ps), "token_files": len(ps & token_files),
                    "examples": sorted(ps)[:3]} for h, ps in top_colors],
        "fonts": [{"family": f, "files": len(ps), "examples": sorted(ps)[:3]} for f, ps in top_fonts],
        "color_scan_skipped_large_files": color_skipped,
    }


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n} B"


def capped(items, limit):
    shown = items[:limit]
    rest = len(items) - len(shown)
    return shown, rest


def render_markdown(inv, max_list=40):
    out = []
    w = out.append
    w(f"# Repository inventory: `{inv['root']}`\n")
    w(f"- Listing: {inv['listing_source']}")
    w(f"- Files inventoried: {inv['total_files']}")
    w("- Classification is path/extension heuristic. Verify every lead before relying on it.\n")
    w("## Counts by category\n")
    for k, v in inv["counts"].items():
        w(f"- {k}: {v}")
    w("\n## Top-level layout\n")
    for k, v in inv["top_level"].items():
        w(f"- `{k}`: {v}")
    w("\n## Excluded from the walk (not read)\n")
    if inv["excluded_dirs"]:
        for k, v in inv["excluded_dirs"].items():
            note = f"{v['files_skipped']} files skipped" if v["files_skipped"] else "present, gitignored or empty"
            w(f"- `{k}/` - {v['reason']} ({note})")
    else:
        w("- none")
    if inv["unreadable"]:
        w(f"- {len(inv['unreadable'])} listed paths not readable as files (deleted, broken link, submodule)")

    def section(title, items, fmt=lambda x: f"`{x}`"):
        w(f"\n## {title}\n")
        shown, rest = capped(items, max_list)
        if not shown:
            w("- none found")
        for x in shown:
            w(f"- {fmt(x)}")
        if rest:
            w(f"- ... {rest} more (see --json output)")

    section("Key docs (read these first)", inv["key_docs"])
    section("Marketing / store / website material", inv["marketing"])
    section("Design tokens / theme files", inv["design_tokens"])
    section("Brand candidates (logo, icon, mascot ...)", inv["brand_candidates"])
    section("UI strings / localization", inv["ui_strings"])
    section("Media assets", inv["media"],
            lambda m: f"`{m['path']}` - {m['kind']}, {human_bytes(m['bytes'])}"
                      + (f", {m['px'][0]}x{m['px'][1]} px" if m.get("px") else ""))
    section("Frequent hex colors (candidates, not brand truth)", inv["colors"],
            lambda c: f"`{c['hex']}` in {c['files']} file(s) ({c['token_files']} token/theme), e.g. " + ", ".join(f"`{e}`" for e in c["examples"]))
    section("Font families referenced", inv["fonts"],
            lambda f: f"{f['family']} in {f['files']} file(s), e.g. " + ", ".join(f"`{e}`" for e in f["examples"]))
    w(f"\n## Tests\n\n- {len(inv['tests'])} test files (read the ones covering the features the video will claim)")
    w("\n## Deliberately not read\n")
    w(f"- generated files: {len(inv['generated'])}")
    w(f"- dependency lockfiles: {len(inv['dependency_locks'])}")
    w(f"- other binary files: {len(inv['binary_other'])}")
    w(f"- color/font scan skipped {inv['color_scan_skipped_large_files']} text files over "
      f"{COLOR_SCAN_MAX_BYTES // 1000} KB")
    if inv["large_files"]:
        w("- large files (>= 5 MB): " + ", ".join(f"`{p}` ({human_bytes(s)})" for p, s in inv["large_files"][:10]))
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("root")
    ap.add_argument("--json", dest="json_out", help="write the full inventory as JSON to this path")
    ap.add_argument("--max-list", type=int, default=40, help="max entries per Markdown section")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        print(f"error: not a directory: {args.root}", file=sys.stderr)
        return 2
    inv = build_inventory(args.root, args.max_list)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(inv, fh, indent=2, ensure_ascii=False)
    sys.stdout.write(render_markdown(inv, args.max_list))
    return 0


if __name__ == "__main__":
    sys.exit(main())
