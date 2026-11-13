#!/usr/bin/env python3
"""Render check for website-creator: load a served page at several widths in a headless browser and measure it.

Drives Playwright CLI as a subprocess (no Python Playwright needed). Browser command, in order:
$WEBSITE_CREATOR_BROWSER (e.g. "pwc --headless"), `pwc --headless` if on PATH, else `playwright-cli -s=website-creator`.

Usage:
  render_check.py URL [URL ...] [--widths 320,375,...] [--out .website-creator/render] [--json] [--no-shots]

Writes <out>/report.json and one full-page screenshot per URL and width. Exit 1 when any error-level
finding exists, 0 otherwise. Serve local builds over HTTP (python3 -m http.server); file:// misreports widths.
"""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

DEFAULT_WIDTHS = [320, 375, 414, 768, 1024, 1280, 1440, 1920]
HEIGHT = 900

# Runs in the page. Returns a JSON string with measurements; kept free of template literals so it survives
# shell-free argv passing unchanged.
PROBE = r"""() => {
  const out = {width: innerWidth, scrollWidth: document.documentElement.scrollWidth, findings: []};
  const add = (rule, severity, detail) => { if (out.findings.length < 400) out.findings.push({rule, severity, detail}); };
  const label = (el) => {
    const id = el.getAttribute('data-testid');
    if (id) return '[data-testid=' + id + ']';
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    const cls = (el.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).slice(0, 2);
    if (cls.length) s += '.' + cls.join('.');
    return s;
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity) > 0.01;
  };
  // WCAG contrast of text against the first opaque ancestor background; null when it cannot be known
  // (background image or gradient, a color space other than rgb, or translucent text).
  const rgba = (s) => {
    const m = /^rgba?\(([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)(?:[,/ ]+([\d.]+%?))?\)$/.exec(s.trim());
    if (!m) return null;
    let a = m[4] === undefined ? 1 : parseFloat(m[4]);
    if (m[4] && m[4].endsWith('%')) a /= 100;
    return [+m[1], +m[2], +m[3], a];
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const contrastOf = (el, cs) => {
    const fg = rgba(cs.color);
    if (!fg || fg[3] < 1) return null;
    for (let p = el; p; p = p.parentElement) {
      const ps = getComputedStyle(p);
      if (ps.backgroundImage && ps.backgroundImage !== 'none') return null;
      const bg = rgba(ps.backgroundColor);
      if (!bg) return null;
      if (bg[3] >= 1) {
        const a = lum(fg), b = lum(bg);
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      }
      if (bg[3] > 0) return null;
    }
    const a = lum(fg);
    return (Math.max(a, 1) + 0.05) / (Math.min(a, 1) + 0.05);  // canvas default: white
  };
  if (out.scrollWidth > out.width + 1) add('horizontal-overflow', 'error', 'page is ' + out.scrollWidth + 'px wide at ' + out.width + 'px');
  const all = Array.from(document.body ? document.body.querySelectorAll('*') : []);
  for (const el of all) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.right > out.width + 1 && getComputedStyle(el).position !== 'fixed') {
      let clipped = false;
      for (let p = el.parentElement; p; p = p.parentElement) {
        const ox = getComputedStyle(p).overflowX;
        if (ox === 'hidden' || ox === 'clip' || ox === 'auto' || ox === 'scroll') { clipped = true; break; }
      }
      if (!clipped && r.width < out.width * 3) add('element-overflow', 'error', label(el) + ' ends at ' + Math.round(r.right) + 'px');
    }
    const ownText = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (!ownText) continue;
    const cs = getComputedStyle(el);
    const fs = parseFloat(cs.fontSize);
    if (fs < 12) add('tiny-text', 'error', label(el) + ' ' + fs + 'px');
    const ratio = contrastOf(el, cs);
    if (ratio !== null) {
      const large = fs >= 24 || (fs >= 18.66 && parseInt(cs.fontWeight, 10) >= 700);
      if (ratio < (large ? 3 : 4.5)) add('low-contrast', 'error', label(el) + ' ' + ratio.toFixed(2) + ':1');
    }
    const text = el.textContent.trim();
    if (text.length > 120 && /^(P|LI|DD|BLOCKQUOTE)$/.test(el.tagName)) {
      const lh = cs.lineHeight === 'normal' ? fs * 1.2 : parseFloat(cs.lineHeight);
      if (lh / fs < 1.3) add('tight-leading', 'warning', label(el) + ' line-height ' + (lh / fs).toFixed(2));
      const chars = r.width / (fs * 0.5);
      if (chars > 90) add('line-length', 'warning', label(el) + ' ~' + Math.round(chars) + ' characters per line');
      if (cs.textAlign === 'justify') add('justified-text', 'warning', label(el));
      if (r.left < 8 || out.width - r.right < 8) add('body-text-viewport-edge', 'error', label(el) + ' touches the viewport edge');
    }
    if (cs.textTransform === 'uppercase' && text.length > 60) add('all-caps-body', 'warning', label(el));
  }
  const interactive = document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [tabindex]:not([tabindex="-1"])');
  for (const el of interactive) {
    if (!visible(el)) continue;
    if (!el.closest('[data-testid]')) add('missing-testid', 'error', label(el) + ' has no data-testid');
    const r = el.getBoundingClientRect();
    const inline = el.tagName === 'A' && el.closest('p, li') && getComputedStyle(el).display === 'inline';
    if (!inline && out.width <= 768 && (r.width < 44 || r.height < 44)) add('tap-target', 'warning', label(el) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
  }
  for (const img of document.images) {
    if (!img.hasAttribute('alt')) add('img-alt', 'error', (img.currentSrc || img.src || '(no src)').slice(0, 120));
    if (img.complete && img.naturalWidth === 0 && visible(img)) add('broken-image', 'error', (img.currentSrc || img.src || '(no src)').slice(0, 120));
  }
  const levels = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6')).filter(visible).map((h) => +h.tagName[1]);
  if (levels.filter((l) => l === 1).length !== 1) add('h1-count', 'error', levels.filter((l) => l === 1).length + ' visible h1');
  for (let i = 1; i < levels.length; i++) if (levels[i] > levels[i - 1] + 1) { add('skipped-heading', 'warning', 'h' + levels[i - 1] + ' -> h' + levels[i]); break; }
  if (!document.documentElement.getAttribute('lang')) add('html-lang', 'error', '<html> has no lang');
  const textEls = all.filter((el) => Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim().length > 1));
  const hidden = textEls.filter((el) => { const cs = getComputedStyle(el); return parseFloat(cs.opacity) < 0.05 || cs.visibility === 'hidden'; });
  if (textEls.length > 10 && hidden.length / textEls.length > 0.3) add('content-hidden-at-rest', 'error', hidden.length + ' of ' + textEls.length + ' text elements invisible');
  return JSON.stringify(out);
}"""


def browser_cmd():
    env = os.environ.get("WEBSITE_CREATOR_BROWSER")
    if env:
        return shlex.split(env)
    if shutil.which("pwc"):
        return ["pwc", "--headless"]
    return ["playwright-cli", "-s=website-creator"]


def call(cmd, *args, timeout=90):
    proc = subprocess.run([*cmd, *args], capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout + proc.stderr


def parse_result(text):
    """Return the value after the '### Result' marker of a playwright-cli eval (a JSON-encoded string)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "### Result" and i + 1 < len(lines):
            raw = lines[i + 1].strip()
            value = json.loads(raw)
            return json.loads(value) if isinstance(value, str) else value
    raise ValueError("no '### Result' block in browser output")


def console_findings(text):
    found = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[ERROR]"):
            if "favicon" in s:
                continue
            rule = "failed-resource" if "Failed to load resource" in s else "console-error"
            found.append({"rule": rule, "severity": "error", "detail": s[8:200]})
        elif re.match(r"^[A-Z][A-Za-z]*Error: ", s):
            found.append({"rule": "script-error", "severity": "error", "detail": s[:200]})
    return found


def check(urls, widths, out_dir, shots, cmd):
    report = {"tool": "website-creator-render", "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "widths": widths, "urls": urls, "findings": [], "screenshots": []}
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        for u_index, url in enumerate(urls):
            code, text = call(cmd, "goto", url)
            if code != 0:
                report["findings"].append({"rule": "load-failed", "severity": "error", "url": url, "detail": text[-300:]})
                continue
            _, text = call(cmd, "console")
            for f in console_findings(text):
                report["findings"].append({**f, "url": url})
            for w in widths:
                call(cmd, "resize", str(w), str(HEIGHT))
                _, text = call(cmd, "eval", PROBE)
                try:
                    data = parse_result(text)
                except (ValueError, json.JSONDecodeError) as exc:
                    report["findings"].append({"rule": "probe-failed", "severity": "error", "url": url, "width": w,
                                               "detail": f"{exc}: {text[-200:]}"})
                    continue
                for f in data.get("findings", []):
                    report["findings"].append({**f, "url": url, "width": w})
                if shots:
                    shot = (out_dir / f"u{u_index}-w{w}.png").resolve()
                    call(cmd, "screenshot", f"--filename={shot}", "--full-page")
                    if shot.exists():
                        report["screenshots"].append(str(shot))
    finally:
        call(cmd, "stop", timeout=30)
    report["summary"] = {
        "errors": sum(1 for f in report["findings"] if f["severity"] == "error"),
        "warnings": sum(1 for f in report["findings"] if f["severity"] == "warning"),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--widths", default=",".join(map(str, DEFAULT_WIDTHS)))
    ap.add_argument("--out", default=".website-creator/render")
    ap.add_argument("--json", action="store_true", help="print the full report instead of a summary")
    ap.add_argument("--no-shots", action="store_true")
    args = ap.parse_args(argv)
    for u in args.urls:
        if u.startswith("file:"):
            ap.error("serve the page over http(s); file:// misreports viewport widths")
    widths = [int(w) for w in args.widths.split(",") if w.strip()]
    report = check(args.urls, widths, Path(args.out), not args.no_shots, browser_cmd())
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        seen = {}
        for f in report["findings"]:
            key = (f["severity"], f["rule"], f.get("detail"))
            seen.setdefault(key, []).append(f.get("width"))
        for (sev, rule, detail), ws in sorted(seen.items()):
            wtxt = ",".join(str(w) for w in ws if w) or "-"
            print(f"{sev:7} {rule:24} [{wtxt}] {detail}")
        s = report["summary"]
        print(f"render: {s['errors']} errors, {s['warnings']} warnings, report {Path(args.out) / 'report.json'}")
    return 1 if report["summary"]["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
