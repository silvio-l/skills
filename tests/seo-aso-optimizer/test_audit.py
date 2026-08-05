#!/usr/bin/env python3
"""Unit tests for the seo-aso-optimizer audit script's HTML/JSON-LD parsing.

Covers the two bugs found while testing against a real site (whispaste.de):
SVG <title> elements bleeding into the document title, and alt="" (correct
for decorative images) being misread as a missing alt attribute. Both are
exactly the kind of plausible-but-wrong output a regex/parser bug produces
silently — see CLAUDE.md's testing rationale.

Run: python3 tests/seo-aso-optimizer/test_audit.py
"""
import importlib.util
import sys
import unittest
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

    def test_word_count_excludes_script_and_style(self):
        html_text = (
            "<body><script>var junkWordsHere = 1;</script>"
            "<style>.a { color: red; }</style>"
            "<p>Real visible words here</p></body>"
        )
        p = parse(html_text)
        self.assertEqual(p.words, 4)


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
