#!/usr/bin/env python3
"""apple-notes helper: HTML → text conversion and base64 image extraction.

Apple Notes stores bodies as HTML with images either inlined as
`data:image/...;base64,...` URLs or referenced as <object> tags pointing
to attachments. This helper handles the inline case (the common one when
reading body via AppleScript); attachments without inline data are
reported but not extracted (AppleScript provides no file path API).
"""

import base64
import hashlib
import html as htmllib
import json
import os
import re
import sys

INLINE_IMG_RE = re.compile(
    r'<img[^>]*src=["\']data:image/([a-zA-Z0-9+.\-]+);base64,([^"\']+)["\'][^>]*>',
    re.IGNORECASE,
)

MIME_EXT = {
    "jpeg": "jpg", "jpg": "jpg", "png": "png", "gif": "gif",
    "webp": "webp", "heic": "heic", "heif": "heif", "tiff": "tiff",
    "svg+xml": "svg", "bmp": "bmp",
}


def strip_base64(html: str) -> str:
    """Replace inline base64 images with a compact placeholder, keep other HTML."""
    counter = [0]

    def repl(m: re.Match) -> str:
        counter[0] += 1
        return f"[image:{counter[0]}]"

    return INLINE_IMG_RE.sub(repl, html)


def to_text(html: str) -> str:
    """Lossy HTML → plaintext for LLM consumption. Drops base64 entirely."""
    # Surround image placeholders with newlines so they sit on their own
    # line after tag-stripping, rather than gluing to adjacent text.
    counter = [0]

    def repl(m: re.Match) -> str:
        counter[0] += 1
        return f"\n[image:{counter[0]}]\n"

    html = INLINE_IMG_RE.sub(repl, html)
    # Convert line-level closing tags to newlines
    html = re.sub(r"</(div|p|li|h[1-6]|tr)>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    # Strip remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # HTML entities
    html = htmllib.unescape(html)
    # Normalize whitespace
    html = re.sub(r"[ \t]+\n", "\n", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


# ── tolerant note-title matching ─────────────────────────────────────────
# Apple Notes derives a note's `name` (title) from the first body line and
# truncates it to ~64 chars + an ellipsis (U+2026). The full text still lives
# in the body. Exact `whose name is t` matching breaks whenever the caller
# passes the full line, a differently-cut prefix, or "..." instead of "…".
# This resolver tolerates all of those, and matches a raw `x-coredata://` id
# directly so callers can address a note by its stable handle.

_TRAILING_DOTS_RE = re.compile(r"[\s.…‥]+$")


def _norm_title(s: str) -> str:
    """Trim surrounding whitespace and any trailing ellipsis/dot run."""
    return _TRAILING_DOTS_RE.sub("", s.strip())


def _looks_truncated(name: str) -> bool:
    """True if `name` ends in an ellipsis (so it is a truncated first line)."""
    t = name.rstrip()
    return t.endswith("…") or t.endswith("‥") or t.endswith("...")


def _match_tier(name: str, query: str, nq: str, nql: str) -> int:
    """Lower tier = better match. 99 = no match.

    0 exact · 1 normalized-equal · 2 query is prefix of name (caller cut short)
    · 3 truncated name is prefix of query (caller gave the full line)
    · 4-6 = case-insensitive variants of 1-3.
    Prefix-from-name tiers (3/6) only fire when `name` is visibly truncated,
    so a note literally titled "BUG" cannot swallow "BUG: login broken".
    """
    nn = _norm_title(name)
    nnl = nn.lower()
    trunc = _looks_truncated(name)
    if name == query:
        return 0
    if nq and nn == nq:
        return 1
    if nq and nn.startswith(nq):
        return 2
    if trunc and nq and nn and nq.startswith(nn):
        return 3
    if nql and nnl == nql:
        return 4
    if nql and nnl.startswith(nql):
        return 5
    if trunc and nql and nnl and nql.startswith(nnl):
        return 6
    return 99


def match_title(query: str, rows: list[tuple]) -> tuple:
    """Resolve a title query against (status, id, name) rows.

    Returns ("OK", (status, id, name)) | ("AMBIG", [rows…]) | ("NONE", None).
    A raw `x-coredata://…` query is matched against the id column exactly.
    """
    if query.startswith("x-coredata://"):
        hits = [r for r in rows if r[1] == query]
        if len(hits) == 1:
            return ("OK", hits[0])
        if not hits:
            return ("NONE", None)
        return ("AMBIG", hits)

    nq = _norm_title(query)
    nql = nq.lower()
    scored = []
    for (status, nid, name) in rows:
        tier = _match_tier(name, query, nq, nql)
        if tier < 99:
            scored.append((tier, status, nid, name))
    if not scored:
        return ("NONE", None)
    best = min(s[0] for s in scored)
    top = [s for s in scored if s[0] == best]
    if len(top) > 1:
        return ("AMBIG", [(s[1], s[2], s[3]) for s in top])
    _, status, nid, name = top[0]
    return ("OK", (status, nid, name))


def extract_images(html: str, out_dir: str) -> list[dict]:
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for i, m in enumerate(INLINE_IMG_RE.finditer(html), start=1):
        mime = m.group(1).lower()
        ext = MIME_EXT.get(mime, "bin")
        b64 = re.sub(r"\s+", "", m.group(2))
        try:
            data = base64.b64decode(b64, validate=False)
        except Exception as exc:
            sys.stderr.write(f"skip image {i}: {exc}\n")
            continue
        digest = hashlib.sha256(data).hexdigest()[:8]
        fname = f"image-{i:02d}-{digest}.{ext}"
        path = os.path.join(out_dir, fname)
        with open(path, "wb") as f:
            f.write(data)
        saved.append({
            "index": i,
            "path": path,
            "bytes": len(data),
            "mime": f"image/{mime}",
        })
    return saved


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("usage: _helper.py {to-text|strip-base64|extract-images <dir>|match-title <query>}")
    cmd = sys.argv[1]
    data = sys.stdin.read()
    if cmd == "match-title":
        if len(sys.argv) < 3:
            sys.exit("match-title requires <query>")
        rows = []
        for line in data.splitlines():
            if not line:
                continue
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue
            rows.append((parts[0], parts[1], parts[2]))
        kind, payload = match_title(sys.argv[2], rows)
        if kind == "OK":
            print("OK\t%s\t%s\t%s" % payload)
        elif kind == "AMBIG":
            print("AMBIG\t" + " | ".join(p[2] for p in payload))
        else:
            print("NONE")
    elif cmd == "to-text":
        print(to_text(data))
    elif cmd == "strip-base64":
        print(strip_base64(data))
    elif cmd == "extract-images":
        if len(sys.argv) < 3:
            sys.exit("extract-images requires <out-dir>")
        result = extract_images(data, sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        sys.exit(f"unknown subcommand: {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
