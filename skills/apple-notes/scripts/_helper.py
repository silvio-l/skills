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
        sys.exit("usage: _helper.py {to-text|strip-base64|extract-images <dir>}")
    cmd = sys.argv[1]
    data = sys.stdin.read()
    if cmd == "to-text":
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
