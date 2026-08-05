#!/usr/bin/env python3
"""Deterministic technical SEO/AEO audit: crawls a sitemap, checks fixed rules,
prints a findings-first report, writes findings.md + audit-data.json.

No LLM judgment calls (no score, no content-quality ratings) — pure rule checks
so the same site always yields the same findings. Stdlib only.

Usage:
    python3 audit_site.py https://example.com [--max-pages 150] [--out-dir .]
"""
import argparse
import gzip
import html.parser
import json
import re
import sys
import urllib.error
import urllib.request
import zlib
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

USER_AGENT = "Mozilla/5.0 (compatible; seo-aso-optimizer/1.0; +https://github.com/)"
TIMEOUT = 12
TITLE_MIN, TITLE_MAX = 30, 65
DESC_MIN, DESC_MAX = 70, 160
THIN_WORDS = 300
MAX_EXTRA_LINK_CHECKS = 40


class _RedirectCounter(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    counter = _RedirectCounter()
    opener = urllib.request.build_opener(counter)
    # Advertise gzip/deflate so Content-Encoding reflects what the server
    # actually offers (Python's urllib sends no Accept-Encoding by default,
    # which would make every server look "uncompressed").
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    )
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            raw = resp.read(2_000_000)
            encoding = resp.headers.get("Content-Encoding", "")
            if encoding == "gzip":
                body = gzip.decompress(raw)
            elif encoding == "deflate":
                body = zlib.decompress(raw)
            else:
                body = raw
            return {
                "status": resp.status,
                "final_url": resp.geturl(),
                "redirects": counter.count,
                "body": body,
                "content_type": resp.headers.get("Content-Type", ""),
                "content_encoding": encoding,
                "x_robots_tag": resp.headers.get("X-Robots-Tag", ""),
                "error": None,
            }
    except urllib.error.HTTPError as e:
        return {"status": e.code, "final_url": url, "redirects": counter.count,
                "body": b"", "content_type": "", "content_encoding": "", "x_robots_tag": "",
                "error": str(e)}
    except Exception as e:
        return {"status": None, "final_url": url, "redirects": counter.count,
                "body": b"", "content_type": "", "content_encoding": "", "x_robots_tag": "",
                "error": str(e)}


def fetch_text(url):
    r = fetch(url)
    return r, (r["body"].decode("utf-8", errors="replace") if r["body"] else "")


def get_robots(root):
    r, text = fetch_text(urljoin(root, "/robots.txt"))
    sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", text)
    return {"present": r["status"] == 200, "sitemaps": sitemaps}


def get_llms_txt(root):
    r, _ = fetch_text(urljoin(root, "/llms.txt"))
    return r["status"] == 200


def expand_sitemap(url, seen=None, depth=0):
    seen = seen if seen is not None else set()
    if url in seen or depth > 2:
        return []
    seen.add(url)
    r, text = fetch_text(url)
    if r["status"] != 200 or not text.strip():
        return []
    try:
        root_el = ET.fromstring(text)
    except ET.ParseError:
        return []
    tag = root_el.tag.split("}")[-1]
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    if tag == "sitemapindex":
        urls = []
        for loc in root_el.findall(".//sm:sitemap/sm:loc", ns):
            if loc.text:
                urls.extend(expand_sitemap(loc.text.strip(), seen, depth + 1))
        return urls
    if tag == "urlset":
        return [loc.text.strip() for loc in root_el.findall(".//sm:loc", ns) if loc.text]
    return []


class PageParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = None
        self.meta_description = None
        self.meta_robots = None
        self.og = {}
        self.twitter_card = None
        self.canonical = None
        self.html_lang = None
        self.hreflangs = []
        self.viewport = False
        self.h1s = []
        self.jsonld_raw = []
        self.img_total = 0
        self.img_no_alt = 0
        self.links = []
        self.words = 0
        self._in_title = False
        self._title_done = False
        self._in_h1 = False
        self._in_jsonld = False
        self._jsonld_buf = []
        self._skip_text_tags = 0
        self._skip_tags = {"script", "style", "noscript"}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html" and "lang" in a:
            self.html_lang = a["lang"]
        elif tag == "title" and not self._title_done:
            # Only the document <head><title> — SVG icons legitimately carry
            # their own <title> elements later in the body for accessibility.
            self._in_title = True
        elif tag == "meta":
            name = (a.get("name") or "").lower()
            prop = (a.get("property") or "").lower()  # og:* tags use property=, not name=
            if name == "description":
                self.meta_description = a.get("content", "")
            elif name == "viewport":
                self.viewport = True
            elif name == "robots":
                self.meta_robots = (a.get("content") or "").lower()
            elif name == "twitter:card":
                self.twitter_card = a.get("content", "")
            elif prop.startswith("og:"):
                self.og[prop] = a.get("content", "")
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if rel == "canonical":
                self.canonical = a.get("href")
            elif rel == "alternate" and a.get("hreflang"):
                self.hreflangs.append(a["hreflang"])
        elif tag == "h1":
            self._in_h1 = True
            self.h1s.append("")
        elif tag == "img":
            self.img_total += 1
            if "alt" not in a:
                # alt="" (present, empty) correctly marks a decorative image —
                # only a missing attribute is a real violation.
                self.img_no_alt += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script":
            t = (a.get("type") or "").lower()
            if t == "application/ld+json":
                self._in_jsonld = True
                self._jsonld_buf = []
        if tag in self._skip_tags:
            self._skip_text_tags += 1

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            self._title_done = True
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "script" and self._in_jsonld:
            self.jsonld_raw.append("".join(self._jsonld_buf))
            self._in_jsonld = False
        if tag in self._skip_tags and self._skip_text_tags > 0:
            self._skip_text_tags -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data
        if self._in_h1 and self.h1s:
            self.h1s[-1] += data
        if self._in_jsonld:
            self._jsonld_buf.append(data)
        elif self._skip_text_tags == 0:
            self.words += len(data.split())


def jsonld_types(raw_blocks):
    types = []
    valid = True
    for raw in raw_blocks:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            valid = False
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict):
                t = item.get("@type")
                if t:
                    types.append(t if isinstance(t, str) else ",".join(t))
    return types, valid


def audit_page(url, root_netloc):
    r = fetch(url)
    page = {
        "url": url, "final_url": r["final_url"], "status": r["status"],
        "redirects": r["redirects"], "error": r["error"],
        "content_encoding": r.get("content_encoding", ""),
        "x_robots_tag": r.get("x_robots_tag", ""),
    }
    if r["status"] != 200 or not r["body"]:
        return page, []
    text = r["body"].decode("utf-8", errors="replace")
    p = PageParser()
    try:
        p.feed(text)
    except Exception:
        pass
    types, jsonld_valid = jsonld_types(p.jsonld_raw)
    internal_links, external_links = [], []
    for href in p.links:
        absu = urljoin(url, href).split("#")[0]
        if urlparse(absu).netloc == root_netloc:
            internal_links.append(absu)
        else:
            external_links.append(absu)
    page.update({
        "title": (p.title or "").strip(),
        "meta_description": (p.meta_description or "").strip(),
        "meta_robots": p.meta_robots or "",
        "og": p.og,
        "twitter_card": p.twitter_card or "",
        "canonical": p.canonical,
        "html_lang": p.html_lang,
        "hreflangs": p.hreflangs,
        "viewport": p.viewport,
        "h1_count": len(p.h1s),
        "h1s": [h.strip() for h in p.h1s],
        "jsonld_count": len(p.jsonld_raw),
        "jsonld_types": types,
        "jsonld_valid": jsonld_valid,
        "img_total": p.img_total,
        "img_no_alt": p.img_no_alt,
        "word_count": p.words,
        "internal_link_count": len(set(internal_links)),
    })
    return page, sorted(set(internal_links))


def evaluate_rules(pages, root_netloc, extra_link_status):
    v = {}

    def add(rule, url, detail=""):
        v.setdefault(rule, []).append({"url": url, "detail": detail})

    linked_targets = set()
    for pg in pages:
        for link in pg.get("_internal_links", []):
            linked_targets.add(link.rstrip("/"))

    for pg in pages:
        url = pg["url"]
        if pg.get("status") != 200:
            add("non_200_status", url, f"status={pg.get('status')} error={pg.get('error')}")
            continue
        if pg["redirects"] > 0:
            add("sitemap_url_redirects", url, f"-> {pg['final_url']} ({pg['redirects']} hop(s))")
        noindex_sources = []
        if "noindex" in pg.get("meta_robots", ""):
            noindex_sources.append("meta robots")
        if "noindex" in pg.get("x_robots_tag", "").lower():
            noindex_sources.append("X-Robots-Tag header")
        if noindex_sources:
            add("noindex_directive_on_sitemap_page", url, f"via {', '.join(noindex_sources)} — page is in the sitemap but tells Google not to index it")
        if not pg.get("content_encoding"):
            add("missing_compression", url, "no Content-Encoding despite Accept-Encoding: gzip, deflate — page is served uncompressed")
        og = pg.get("og", {})
        missing_og = [t for t in ("og:title", "og:description", "og:image") if not og.get(t)]
        if missing_og:
            add("missing_og_tags", url, f"missing: {', '.join(missing_og)} — link previews on social/chat apps will be blank or generic")
        if not pg["title"]:
            add("missing_title", url)
        elif not (TITLE_MIN <= len(pg["title"]) <= TITLE_MAX):
            add("title_length_out_of_range", url, f"{len(pg['title'])} chars: {pg['title']!r}")
        if not pg["meta_description"]:
            add("missing_meta_description", url)
        elif not (DESC_MIN <= len(pg["meta_description"]) <= DESC_MAX):
            add("meta_description_length_out_of_range", url, f"{len(pg['meta_description'])} chars")
        if pg["h1_count"] == 0:
            add("missing_h1", url)
        elif pg["h1_count"] > 1:
            add("multiple_h1", url, f"{pg['h1_count']} H1s")
        if not pg["canonical"]:
            add("missing_canonical", url)
        if not pg["html_lang"]:
            add("missing_html_lang", url)
        if not pg["viewport"]:
            add("missing_viewport_meta", url)
        if pg["jsonld_count"] == 0:
            add("missing_structured_data", url)
        elif not pg["jsonld_valid"]:
            add("invalid_structured_data_json", url)
        if pg["img_no_alt"] > 0:
            add("images_missing_alt", url, f"{pg['img_no_alt']}/{pg['img_total']} images")
        if pg["word_count"] < THIN_WORDS:
            add("thin_content", url, f"{pg['word_count']} words (< {THIN_WORDS})")
        norm = url.rstrip("/")
        if norm not in linked_targets and norm != root_netloc:
            add("orphan_page_no_internal_links_found", url)

    for target, status in extra_link_status.items():
        if status not in (200, None) or status is None:
            add("broken_internal_link_target", target, f"status={status}")

    return v


def crawl(base_url, max_pages):
    parsed = urlparse(base_url if "://" in base_url else "https://" + base_url)
    root = f"{parsed.scheme}://{parsed.netloc}/"
    root_netloc = parsed.netloc

    robots = get_robots(root)
    llms_txt = get_llms_txt(root)
    # robots.txt's Sitemap: line is authoritative when present. The fallback list
    # covers the common defaults across static-site generators, WordPress's core
    # sitemap (since 5.5, wp-sitemap.xml — easy to miss and a silent-zero-findings
    # trap if skipped), and Yoast/other plugins' sitemap_index.xml.
    sitemap_candidates = robots["sitemaps"] or [
        urljoin(root, "/sitemap.xml"),
        urljoin(root, "/sitemap_index.xml"),
        urljoin(root, "/sitemap-index.xml"),
        urljoin(root, "/wp-sitemap.xml"),
    ]

    sitemap_urls = []
    used_sitemap = None
    for cand in sitemap_candidates:
        urls = expand_sitemap(cand)
        if urls:
            sitemap_urls = urls
            used_sitemap = cand
            break

    truncated = len(sitemap_urls) > max_pages
    crawl_set = sitemap_urls[:max_pages]

    pages = []
    all_internal_links = set()
    for url in crawl_set:
        page, internal_links = audit_page(url, root_netloc)
        page["_internal_links"] = internal_links
        pages.append(page)
        all_internal_links.update(internal_links)

    known = {u.rstrip("/") for u in crawl_set}
    to_check = [u for u in all_internal_links if u.rstrip("/") not in known][:MAX_EXTRA_LINK_CHECKS]
    extra_link_status = {}
    for u in to_check:
        r = fetch(u)
        extra_link_status[u] = r["status"]

    violations = evaluate_rules(pages, root, extra_link_status)
    for pg in pages:
        pg.pop("_internal_links", None)

    return {
        "root": root,
        "robots_txt_present": robots["present"],
        "llms_txt_present": llms_txt,
        "sitemap_used": used_sitemap,
        "sitemap_url_count": len(sitemap_urls),
        "pages_crawled": len(pages),
        "truncated": truncated,
        "violations": violations,
        "pages": pages,
    }


def render_findings(result):
    lines = []
    lines.append(f"# SEO/AEO technical audit — {result['root']}")
    lines.append("")
    lines.append(f"- robots.txt present: {result['robots_txt_present']}")
    lines.append(f"- llms.txt present: {result['llms_txt_present']}")
    lines.append(f"- sitemap used: {result['sitemap_used'] or 'NONE FOUND'}")
    lines.append(f"- pages in sitemap: {result['sitemap_url_count']}, crawled: {result['pages_crawled']}"
                  + (" (TRUNCATED — raise --max-pages)" if result["truncated"] else ""))
    total_violations = sum(len(v) for v in result["violations"].values())
    lines.append(f"- rules failing: {len(result['violations'])}, total findings: {total_violations}")
    lines.append("")
    if not result["violations"]:
        lines.append("No rule violations found.")
    for rule in sorted(result["violations"], key=lambda r: -len(result["violations"][r])):
        items = result["violations"][rule]
        lines.append(f"## {rule} ({len(items)})")
        for it in items[:15]:
            detail = f" — {it['detail']}" if it["detail"] else ""
            lines.append(f"- {it['url']}{detail}")
        if len(items) > 15:
            lines.append(f"- … +{len(items) - 15} more (see audit-data.json)")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url", help="Site root, e.g. https://example.com")
    ap.add_argument("--max-pages", type=int, default=150)
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    result = crawl(args.url, args.max_pages)
    findings_md = render_findings(result)
    print(findings_md)

    import os
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "findings.md"), "w") as f:
        f.write(findings_md)
    with open(os.path.join(args.out_dir, "audit-data.json"), "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n(full per-page data: {os.path.join(args.out_dir, 'audit-data.json')} — read only when drilling into a specific rule/page)", file=sys.stderr)


if __name__ == "__main__":
    main()
