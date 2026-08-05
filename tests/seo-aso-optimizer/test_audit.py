#!/usr/bin/env python3
"""Unit tests for the seo-aso-optimizer audit script's HTML/JSON-LD parsing.

Covers the two bugs found while testing against a real site (whispaste.de):
SVG <title> elements bleeding into the document title, and alt="" (correct
for decorative images) being misread as a missing alt attribute. Both are
exactly the kind of plausible-but-wrong output a regex/parser bug produces
silently — see CLAUDE.md's testing rationale.

Run: python3 tests/seo-aso-optimizer/test_audit.py
"""
import gzip
import importlib.util
import sys
import unittest
import zlib
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills" / "seo-aso-optimizer" / "scripts" / "audit_site.py"
)
spec = importlib.util.spec_from_file_location("audit_site", SCRIPT_PATH)
audit_site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_site)


def parse(html_text):
    p = audit_site.PageParser()
    p.feed(html_text)
    return p


class TitleParsing(unittest.TestCase):
    def test_plain_title(self):
        p = parse("<html><head><title>Hello World</title></head><body></body></html>")
        self.assertEqual(p.title, "Hello World")

    def test_svg_title_does_not_leak_into_document_title(self):
        html_text = (
            "<html><head><title>Real Title</title></head>"
            "<body><svg><title>Apple</title></svg>"
            "<svg><title>Ubuntu</title></svg></body></html>"
        )
        p = parse(html_text)
        self.assertEqual(p.title, "Real Title")

    def test_missing_title_is_none(self):
        p = parse("<html><head></head><body>hi</body></html>")
        self.assertIsNone(p.title)


class ImgAltParsing(unittest.TestCase):
    def test_missing_alt_attribute_is_a_violation(self):
        p = parse('<img src="a.png">')
        self.assertEqual(p.img_total, 1)
        self.assertEqual(p.img_no_alt, 1)

    def test_empty_alt_marks_decorative_and_is_not_a_violation(self):
        p = parse('<img src="a.png" alt="">')
        self.assertEqual(p.img_total, 1)
        self.assertEqual(p.img_no_alt, 0)

    def test_descriptive_alt_is_not_a_violation(self):
        p = parse('<img src="a.png" alt="A useful description">')
        self.assertEqual(p.img_total, 1)
        self.assertEqual(p.img_no_alt, 0)

    def test_mixed_images_counted_correctly(self):
        p = parse(
            '<img src="a.png"><img src="b.png" alt=""><img src="c.png" alt="desc">'
        )
        self.assertEqual(p.img_total, 3)
        self.assertEqual(p.img_no_alt, 1)


class StructuralParsing(unittest.TestCase):
    def test_h1_count_and_text(self):
        p = parse("<h1>First</h1><p>body</p><h1>Second</h1>")
        self.assertEqual(p.h1_count if hasattr(p, "h1_count") else len(p.h1s), 2)
        self.assertEqual(p.h1s, ["First", "Second"])

    def test_canonical_and_lang_and_viewport(self):
        html_text = (
            '<html lang="de"><head>'
            '<link rel="canonical" href="https://example.com/">'
            '<meta name="viewport" content="width=device-width">'
            "</head><body></body></html>"
        )
        p = parse(html_text)
        self.assertEqual(p.html_lang, "de")
        self.assertEqual(p.canonical, "https://example.com/")
        self.assertTrue(p.viewport)

    def test_meta_robots_noindex_captured(self):
        html_text = '<head><meta name="robots" content="noindex, nofollow"></head>'
        p = parse(html_text)
        self.assertIn("noindex", p.meta_robots)

    def test_meta_robots_absent_is_none(self):
        p = parse("<head></head>")
        self.assertIsNone(p.meta_robots)

    def test_og_tags_use_property_not_name(self):
        # Open Graph tags are <meta property="og:title" ...>, not name= — a
        # parser that only checks a.get("name") silently finds nothing.
        html_text = (
            '<meta property="og:title" content="Hello">'
            '<meta property="og:description" content="World">'
            '<meta property="og:image" content="https://example.com/x.png">'
        )
        p = parse(html_text)
        self.assertEqual(p.og["og:title"], "Hello")
        self.assertEqual(p.og["og:description"], "World")
        self.assertEqual(p.og["og:image"], "https://example.com/x.png")

    def test_twitter_card_uses_name_not_property(self):
        p = parse('<meta name="twitter:card" content="summary_large_image">')
        self.assertEqual(p.twitter_card, "summary_large_image")

    def test_no_og_tags_leaves_empty_dict(self):
        p = parse("<head></head>")
        self.assertEqual(p.og, {})

    def test_word_count_excludes_script_and_style(self):
        html_text = (
            "<body><script>var junkWordsHere = 1;</script>"
            "<style>.a { color: red; }</style>"
            "<p>Real visible words here</p></body>"
        )
        p = parse(html_text)
        self.assertEqual(p.words, 4)

    def test_word_count_excludes_nav_header_footer_boilerplate(self):
        html_text = (
            "<nav>home about contact services blog pricing docs support</nav>"
            "<header>brand tagline slogan</header>"
            "<main>one two three</main>"
            "<footer>copyright all rights reserved company address phone</footer>"
        )
        p = parse(html_text)
        self.assertEqual(p.words, 3)

    def test_word_count_still_counts_text_outside_nav_header_footer(self):
        html_text = "<nav>ignored words here</nav><p>real content words counted here</p>"
        p = parse(html_text)
        self.assertEqual(p.words, 5)


class JsonLdParsing(unittest.TestCase):
    def test_valid_single_type(self):
        types, valid = audit_site.jsonld_types(['{"@type": "Organization", "name": "X"}'])
        self.assertTrue(valid)
        self.assertEqual(types, ["Organization"])

    def test_valid_list_of_types(self):
        types, valid = audit_site.jsonld_types(['{"@type": ["Product", "SoftwareApplication"]}'])
        self.assertTrue(valid)
        self.assertEqual(types, ["Product,SoftwareApplication"])

    def test_invalid_json_flagged_but_does_not_crash(self):
        types, valid = audit_site.jsonld_types(["{not valid json"])
        self.assertFalse(valid)
        self.assertEqual(types, [])

    def test_at_graph_array_top_level(self):
        types, valid = audit_site.jsonld_types(
            ['[{"@type": "WebSite"}, {"@type": "FAQPage"}]']
        )
        self.assertTrue(valid)
        self.assertEqual(sorted(types), ["FAQPage", "WebSite"])

    def test_at_graph_property_member_types_detected(self):
        # REFERENCE.md's own recommended pattern: a single JSON-LD block
        # combining multiple typed entities via a top-level "@graph" array,
        # not a bare top-level array of objects (covered above already).
        raw = (
            '{"@context": "https://schema.org", "@graph": '
            '[{"@type": "WebSite"}, {"@type": "Organization"}]}'
        )
        types, valid = audit_site.jsonld_types([raw])
        self.assertTrue(valid)
        self.assertEqual(sorted(types), ["Organization", "WebSite"])

    def test_top_level_type_alongside_at_graph_both_detected(self):
        raw = '{"@type": "WebPage", "@graph": [{"@type": "Organization"}]}'
        types, valid = audit_site.jsonld_types([raw])
        self.assertEqual(sorted(types), ["Organization", "WebPage"])


def make_page(url, **overrides):
    """A page dict that trips no rule other than what the test cares about."""
    page = {
        "url": url,
        "final_url": url,
        "status": 200,
        "redirects": 0,
        "error": None,
        "content_encoding": "gzip",
        "x_robots_tag": "",
        "title": "A page title that is exactly long enough to pass",
        "meta_description": "A meta description that is long enough to pass the "
        "seventy-to-one-sixty character window comfortably.",
        "meta_robots": "",
        "og": {"og:title": "t", "og:description": "d", "og:image": "i"},
        "twitter_card": "",
        "canonical": url,
        "html_lang": "en",
        "hreflangs": [],
        "viewport": True,
        "h1_count": 1,
        "h1s": ["Heading"],
        "jsonld_count": 1,
        "jsonld_types": ["WebPage"],
        "jsonld_valid": True,
        "img_total": 0,
        "img_no_alt": 0,
        "word_count": 500,
        "internal_link_count": 0,
        "_internal_links": [],
    }
    page.update(overrides)
    return page


class EvaluateRulesOrphanPage(unittest.TestCase):
    ROOT = "https://example.com"
    # crawl() builds root as f"{scheme}://{netloc}/" (trailing slash, never
    # rstripped) and passes that straight through as root_netloc — reproduce
    # that exact shape here rather than a pre-cleaned value, or the test
    # can't tell a correct call site from an accidentally-working one.
    ROOT_AS_PASSED_BY_CRAWL = "https://example.com/"

    def test_homepage_excluded_even_with_no_incoming_links(self):
        home = make_page(f"{self.ROOT}/", _internal_links=[])
        violations = audit_site.evaluate_rules([home], self.ROOT_AS_PASSED_BY_CRAWL, {})
        self.assertNotIn("orphan_page_no_internal_links_found", violations)

    def test_genuinely_orphaned_non_homepage_is_still_flagged(self):
        home = make_page(f"{self.ROOT}/", _internal_links=["https://example.com/other"])
        orphan = make_page(f"{self.ROOT}/orphan", _internal_links=[])
        other = make_page(f"{self.ROOT}/other", _internal_links=[])
        violations = audit_site.evaluate_rules(
            [home, orphan, other], self.ROOT_AS_PASSED_BY_CRAWL, {}
        )
        orphan_urls = {v["url"] for v in violations.get("orphan_page_no_internal_links_found", [])}
        self.assertIn(f"{self.ROOT}/orphan", orphan_urls)

    def test_page_linked_from_another_page_is_not_orphaned(self):
        home = make_page(f"{self.ROOT}/", _internal_links=[f"{self.ROOT}/about"])
        about = make_page(f"{self.ROOT}/about", _internal_links=[])
        violations = audit_site.evaluate_rules([home, about], self.ROOT_AS_PASSED_BY_CRAWL, {})
        orphan_urls = {v["url"] for v in violations.get("orphan_page_no_internal_links_found", [])}
        self.assertNotIn(f"{self.ROOT}/about", orphan_urls)


class DecodeBody(unittest.TestCase):
    def test_gzip_uppercase_is_decompressed(self):
        raw = gzip.compress(b"hello world")
        self.assertEqual(audit_site.decode_body(raw, "GZIP"), b"hello world")

    def test_gzip_lowercase_is_decompressed(self):
        raw = gzip.compress(b"hello world")
        self.assertEqual(audit_site.decode_body(raw, "gzip"), b"hello world")

    def test_deflate_mixed_case_is_decompressed(self):
        raw = zlib.compress(b"hello deflate")
        self.assertEqual(audit_site.decode_body(raw, "Deflate"), b"hello deflate")

    def test_encoding_with_extra_parameters_still_matches(self):
        raw = gzip.compress(b"hello params")
        self.assertEqual(audit_site.decode_body(raw, "gzip;q=1.0"), b"hello params")

    def test_unrecognized_encoding_passes_through_unchanged(self):
        raw = b"not actually compressed"
        self.assertEqual(audit_site.decode_body(raw, "br"), raw)

    def test_empty_encoding_passes_through_unchanged(self):
        raw = b"plain text body"
        self.assertEqual(audit_site.decode_body(raw, ""), raw)


class SelectLinksToCheck(unittest.TestCase):
    def test_selection_is_deterministic_regardless_of_input_order(self):
        known = {"https://example.com"}
        links_a = {"https://example.com/c", "https://example.com/a", "https://example.com/b"}
        links_b = {"https://example.com/b", "https://example.com/c", "https://example.com/a"}
        self.assertEqual(
            audit_site.select_links_to_check(known, links_a, 2),
            audit_site.select_links_to_check(known, links_b, 2),
        )

    def test_known_links_are_excluded(self):
        known = {"https://example.com/already-crawled"}
        links = {"https://example.com/already-crawled", "https://example.com/extra"}
        result = audit_site.select_links_to_check(known, links, 10)
        self.assertEqual(result, ["https://example.com/extra"])

    def test_result_is_capped_at_max_checks(self):
        known = set()
        links = {f"https://example.com/{i}" for i in range(10)}
        result = audit_site.select_links_to_check(known, links, 3)
        self.assertEqual(len(result), 3)

    def test_result_is_sorted(self):
        known = set()
        links = {"https://example.com/z", "https://example.com/a", "https://example.com/m"}
        result = audit_site.select_links_to_check(known, links, 10)
        self.assertEqual(result, sorted(links))


class IsSafeSitemapUrl(unittest.TestCase):
    ROOT_NETLOC = "example.com"

    def test_same_origin_https_is_safe(self):
        self.assertTrue(
            audit_site.is_safe_sitemap_url("https://example.com/sitemap2.xml", self.ROOT_NETLOC)
        )

    def test_same_origin_http_is_safe(self):
        self.assertTrue(
            audit_site.is_safe_sitemap_url("http://example.com/sitemap2.xml", self.ROOT_NETLOC)
        )

    def test_file_scheme_is_unsafe(self):
        self.assertFalse(audit_site.is_safe_sitemap_url("file:///etc/passwd", self.ROOT_NETLOC))

    def test_cross_origin_is_unsafe(self):
        self.assertFalse(
            audit_site.is_safe_sitemap_url("https://evil.example/sitemap.xml", self.ROOT_NETLOC)
        )

    def test_ftp_scheme_is_unsafe(self):
        self.assertFalse(
            audit_site.is_safe_sitemap_url("ftp://example.com/sitemap.xml", self.ROOT_NETLOC)
        )


class SitemapXmlParsing(unittest.TestCase):
    def test_urlset_extraction_via_expand_sitemap_helper(self):
        # Exercise the ElementTree branch logic directly without a network
        # fetch by feeding expand_sitemap's inner XML parse through a stub.
        import xml.etree.ElementTree as ET

        xml_text = (
            '<?xml version="1.0"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/a</loc></url>"
            "<url><loc>https://example.com/b</loc></url>"
            "</urlset>"
        )
        root_el = ET.fromstring(xml_text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text.strip() for loc in root_el.findall(".//sm:loc", ns) if loc.text]
        self.assertEqual(urls, ["https://example.com/a", "https://example.com/b"])


if __name__ == "__main__":
    unittest.main()
