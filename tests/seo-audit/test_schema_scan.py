#!/usr/bin/env python3
"""Tests for seo-audit/scripts/schema_scan.py.

Checks:
  AC1: tolerant JSON-LD extraction (broken block → finding, no crash)
  AC2: missing JSON-LD → finding
  AC3: required-field completeness (REQUIRED_FIELDS_V1)
  AC4: deprecated type detection (DEPRECATED_TYPES_V1)
  AC5: sameAs consistency (JSON-LD vs HTML anchor links)
  AC6: dimension=schema, deterministic sort
  AC7: standalone CLI emits JSON
  AC8: fixture-based tests for AC3 + AC5 with determinism assertions
  AC9: German output text (spot checks)

Run from the repo root:
    PYTHONDONTWRITEBYTECODE=1 python3 tests/seo-audit/test_schema_scan.py
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURES_DIR = REPO_ROOT / "tests" / "seo-audit" / "fixtures" / "schema"

sys.path.insert(0, str(SCRIPTS_DIR))

import schema_scan as S  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def by_category(findings, category: str) -> list:
    return [f for f in findings if f.get("category") == category]


def contains(findings, substr: str) -> list:
    return [f for f in findings if substr in f.get("match", "")]


# ---------------------------------------------------------------------------
# AC1: tolerant JSON-LD extraction
# ---------------------------------------------------------------------------

class TestBrokenJsonLd(unittest.TestCase):

    def test_broken_block_does_not_crash(self):
        """Broken JSON-LD must produce a finding, not raise an exception."""
        html = (FIXTURES_DIR / "schema_broken.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_broken.html")
        result = S.scan_file(path, html)
        self.assertIsInstance(result, list)

    def test_broken_block_emits_finding(self):
        html = (FIXTURES_DIR / "schema_broken.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_broken.html")
        findings = S.scan_file(path, html)
        broken = by_category(findings, "schema-broken")
        self.assertTrue(broken, "Expected schema-broken finding")
        self.assertEqual(broken[0]["dimension"], "schema")
        self.assertIn("ungültig", broken[0]["match"].lower())

    def test_valid_block_no_broken_finding(self):
        html = (FIXTURES_DIR / "schema_valid.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_valid.html")
        findings = S.scan_file(path, html)
        broken = by_category(findings, "schema-broken")
        self.assertFalse(broken, "Should not flag valid JSON-LD as broken")

    def test_inline_broken_json_no_crash(self):
        """Inline broken JSON must not raise."""
        html = '<script type="application/ld+json">{ bad json }</script>'
        result = S.scan_file("test.html", html)
        self.assertIsInstance(result, list)
        broken = by_category(result, "schema-broken")
        self.assertTrue(broken)


# ---------------------------------------------------------------------------
# AC2: missing JSON-LD
# ---------------------------------------------------------------------------

class TestMissingJsonLd(unittest.TestCase):

    def test_missing_emits_finding(self):
        html = (FIXTURES_DIR / "schema_missing.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_missing.html")
        findings = S.scan_file(path, html)
        missing = by_category(findings, "schema-missing")
        self.assertTrue(missing, "Expected schema-missing finding")
        self.assertEqual(missing[0]["dimension"], "schema")

    def test_present_suppresses_missing_finding(self):
        html = (FIXTURES_DIR / "schema_valid.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_valid.html")
        findings = S.scan_file(path, html)
        missing = by_category(findings, "schema-missing")
        self.assertFalse(missing, "Should not flag missing JSON-LD when it is present")

    def test_inline_missing_no_ld(self):
        html = "<html><body><p>Kein JSON-LD.</p></body></html>"
        findings = S.scan_file("test.html", html)
        missing = by_category(findings, "schema-missing")
        self.assertTrue(missing)


# ---------------------------------------------------------------------------
# AC3: required-field completeness (fixture + inline)
# ---------------------------------------------------------------------------

class TestRequiredFields(unittest.TestCase):

    def test_incomplete_article_missing_author_and_date(self):
        """schema_incomplete.html has Article with only headline — author and
        datePublished must be flagged."""
        html = (FIXTURES_DIR / "schema_incomplete.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_incomplete.html")
        findings = S.scan_file(path, html)
        incomplete = by_category(findings, "schema-incomplete")
        self.assertTrue(incomplete, "Expected schema-incomplete findings for Article")
        fields = {f["match"] for f in incomplete}
        self.assertTrue(
            any("author" in m for m in fields),
            f"Expected missing-author finding; got: {fields}",
        )
        self.assertTrue(
            any("datePublished" in m for m in fields),
            f"Expected missing-datePublished finding; got: {fields}",
        )

    def test_complete_organization_not_flagged(self):
        """schema_valid.html has Organization with name + url — no incomplete."""
        html = (FIXTURES_DIR / "schema_valid.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_valid.html")
        findings = S.scan_file(path, html)
        incomplete = by_category(findings, "schema-incomplete")
        self.assertFalse(incomplete, "Should not flag complete Organization")

    def test_required_fields_table_covers_all_core_types(self):
        """Versioned table must cover exactly the seven required core types."""
        core = {
            "Organization", "Person", "Article", "Product",
            "WebSite", "WebPage", "FAQPage",
        }
        self.assertEqual(core, set(S.REQUIRED_FIELDS_V1.keys()))

    def test_inline_missing_person_name(self):
        html = '<script type="application/ld+json">{"@type":"Person"}</script>'
        findings = S.scan_file("test.html", html)
        incomplete = by_category(findings, "schema-incomplete")
        self.assertTrue(incomplete)
        self.assertIn("name", incomplete[0]["match"])

    def test_inline_faqpage_missing_mainentity(self):
        html = '<script type="application/ld+json">{"@type":"FAQPage"}</script>'
        findings = S.scan_file("test.html", html)
        incomplete = by_category(findings, "schema-incomplete")
        self.assertTrue(incomplete)
        self.assertIn("mainEntity", incomplete[0]["match"])

    def test_website_requires_name_and_url(self):
        html = '<script type="application/ld+json">{"@type":"WebSite","name":"X"}</script>'
        findings = S.scan_file("test.html", html)
        incomplete = by_category(findings, "schema-incomplete")
        # name is present; url is missing
        self.assertTrue(incomplete)
        self.assertIn("url", incomplete[0]["match"])


# ---------------------------------------------------------------------------
# AC4: deprecated types
# ---------------------------------------------------------------------------

class TestDeprecatedTypes(unittest.TestCase):

    def test_deprecated_wpfooter_flagged(self):
        """schema_deprecated.html uses WPFooter — must be flagged."""
        html = (FIXTURES_DIR / "schema_deprecated.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_deprecated.html")
        findings = S.scan_file(path, html)
        deprecated = by_category(findings, "schema-deprecated")
        self.assertTrue(deprecated, "Expected schema-deprecated finding")
        self.assertIn("WPFooter", deprecated[0]["match"])
        self.assertEqual(deprecated[0]["dimension"], "schema")

    def test_non_deprecated_organization_not_flagged(self):
        html = (FIXTURES_DIR / "schema_valid.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_valid.html")
        findings = S.scan_file(path, html)
        deprecated = by_category(findings, "schema-deprecated")
        self.assertFalse(deprecated, "Should not flag non-deprecated Organization")

    def test_deprecated_types_table_has_expected_entries(self):
        for t in ("WPFooter", "WPHeader", "WPSideBar", "WPAdBlock",
                  "DataFeedItem", "UserComments"):
            self.assertIn(t, S.DEPRECATED_TYPES_V1, f"{t!r} missing from table")

    def test_inline_datafeeditem_flagged(self):
        html = (
            '<script type="application/ld+json">'
            '{"@type":"DataFeedItem","name":"x"}'
            '</script>'
        )
        findings = S.scan_file("test.html", html)
        deprecated = by_category(findings, "schema-deprecated")
        self.assertTrue(deprecated)
        self.assertIn("DataFeedItem", deprecated[0]["match"])


# ---------------------------------------------------------------------------
# AC5: sameAs consistency
# ---------------------------------------------------------------------------

class TestSameAsConsistency(unittest.TestCase):

    def test_sameas_mismatch_emits_finding(self):
        """schema_sameas_mismatch.html: facebook in sameAs but not linked."""
        html = (FIXTURES_DIR / "schema_sameas_mismatch.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_sameas_mismatch.html")
        findings = S.scan_file(path, html)
        sameas = by_category(findings, "schema-sameas")
        self.assertTrue(sameas, "Expected sameAs mismatch finding")
        urls = " ".join(f["match"] for f in sameas)
        self.assertIn("facebook.com", urls)

    def test_sameas_linked_suppresses_finding(self):
        """schema_valid.html: all sameAs URLs linked in HTML — no mismatch."""
        html = (FIXTURES_DIR / "schema_valid.html").read_text("utf-8")
        path = str(FIXTURES_DIR / "schema_valid.html")
        findings = S.scan_file(path, html)
        sameas = by_category(findings, "schema-sameas")
        self.assertFalse(sameas,
                         "Should not flag sameAs when all URLs are linked in HTML")

    def test_sameas_non_social_url_not_flagged(self):
        """Non-social sameAs (e.g. Wikidata) must not be reported."""
        html = (
            '<a href="https://wikidata.org/wiki/Q123">wiki</a>'
            '<script type="application/ld+json">'
            '{"@type":"Organization","name":"X","url":"https://x.com",'
            '"sameAs":["https://wikidata.org/wiki/Q123"]}'
            '</script>'
        )
        findings = S.scan_file("test.html", html)
        sameas = by_category(findings, "schema-sameas")
        self.assertFalse(sameas,
                         "Non-social sameAs entries must not be flagged")

    def test_sameas_missing_json_ld_no_sameas_finding(self):
        """No sameAs finding when there is no JSON-LD at all."""
        html = "<html><body><h1>Test</h1></body></html>"
        findings = S.scan_file("test.html", html)
        sameas = by_category(findings, "schema-sameas")
        self.assertFalse(sameas)

    def test_sameas_twitter_linked_not_flagged(self):
        """Linked Twitter profile is not reported as a mismatch."""
        html = (
            '<a href="https://twitter.com/example">Twitter</a>'
            '<script type="application/ld+json">'
            '{"@type":"Organization","name":"X","url":"https://x.com",'
            '"sameAs":["https://twitter.com/example"]}'
            '</script>'
        )
        findings = S.scan_file("test.html", html)
        sameas = by_category(findings, "schema-sameas")
        self.assertFalse(sameas, "Linked Twitter must not be flagged")


# ---------------------------------------------------------------------------
# AC6: dimension=schema, deterministic sort
# ---------------------------------------------------------------------------

class TestDimensionAndDeterminism(unittest.TestCase):

    def test_all_findings_have_dimension_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Test</h1></body></html>")
            findings = S.scan_directory(tmp)
            for f in findings:
                self.assertEqual(
                    f.get("dimension"), "schema",
                    f"Finding missing dimension=schema: {f!r}",
                )

    def test_deterministic_two_runs_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "a.html"),
                  "<html><body><p>Test A</p></body></html>")
            write(os.path.join(tmp, "b.html"),
                  "<html><body><p>Test B</p></body></html>")
            out1 = json.dumps(S.scan_directory(tmp), ensure_ascii=False)
            out2 = json.dumps(S.scan_directory(tmp), ensure_ascii=False)
            self.assertEqual(out1, out2,
                             "Two scan_directory runs over the same dir differ")

    def test_findings_sorted_by_path_line_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "z.html"),
                  "<html><body></body></html>")
            write(os.path.join(tmp, "a.html"),
                  "<html><body></body></html>")
            findings = S.scan_directory(tmp)
            keys = [
                (f["file_path"], f["line_number"], f["match"].lower())
                for f in findings
            ]
            self.assertEqual(keys, sorted(keys),
                             "Findings not sorted by (file_path, line_number, match)")

    def test_nonexistent_dir_returns_empty_list(self):
        self.assertEqual(S.scan_directory("/nonexistent/path/xyz"), [])


# ---------------------------------------------------------------------------
# AC7: standalone CLI emits JSON
# ---------------------------------------------------------------------------

class TestStandaloneCLI(unittest.TestCase):

    def test_cli_outputs_json_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Test</h1></body></html>")
            script = str(SCRIPTS_DIR / "schema_scan.py")
            result = subprocess.run(
                [sys.executable, script, tmp],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(result.returncode, 0,
                             f"CLI error: {result.stderr}")
            parsed = json.loads(result.stdout)
            self.assertIsInstance(parsed, list)

    def test_cli_nonexistent_dir_returns_empty_json_array(self):
        script = str(SCRIPTS_DIR / "schema_scan.py")
        result = subprocess.run(
            [sys.executable, script, "/nonexistent/path/xyz"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed, [])

    def test_cli_findings_have_dimension_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Test</h1></body></html>")
            script = str(SCRIPTS_DIR / "schema_scan.py")
            result = subprocess.run(
                [sys.executable, script, tmp],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            findings = json.loads(result.stdout)
            for f in findings:
                self.assertEqual(f.get("dimension"), "schema")


# ---------------------------------------------------------------------------
# AC8: fixture-based tests for AC3 + AC5 with determinism assertions
# ---------------------------------------------------------------------------

class TestFixtureRequiredFields(unittest.TestCase):
    """Fixture-based required-field check with determinism assertion."""

    def test_fixture_incomplete_two_runs_identical(self):
        path = str(FIXTURES_DIR / "schema_incomplete.html")
        html = pathlib.Path(path).read_text("utf-8")
        run1 = json.dumps(S.scan_file(path, html), ensure_ascii=False)
        run2 = json.dumps(S.scan_file(path, html), ensure_ascii=False)
        self.assertEqual(run1, run2, "Two scan_file runs on same fixture differ")

    def test_fixture_incomplete_all_findings_schema_dimension(self):
        path = str(FIXTURES_DIR / "schema_incomplete.html")
        html = pathlib.Path(path).read_text("utf-8")
        findings = S.scan_file(path, html)
        for f in findings:
            self.assertEqual(f["dimension"], "schema")

    def test_fixture_incomplete_missing_fields_match_expected(self):
        """Article in schema_incomplete.html is missing author and datePublished."""
        path = str(FIXTURES_DIR / "schema_incomplete.html")
        html = pathlib.Path(path).read_text("utf-8")
        findings = S.scan_file(path, html)
        incomplete = by_category(findings, "schema-incomplete")
        missing_fields = {f["match"] for f in incomplete}
        self.assertTrue(any("author" in m for m in missing_fields))
        self.assertTrue(any("datePublished" in m for m in missing_fields))


class TestFixtureSameAs(unittest.TestCase):
    """Fixture-based sameAs consistency check with determinism assertion."""

    def test_fixture_sameas_mismatch_two_runs_identical(self):
        path = str(FIXTURES_DIR / "schema_sameas_mismatch.html")
        html = pathlib.Path(path).read_text("utf-8")
        run1 = json.dumps(S.scan_file(path, html), ensure_ascii=False)
        run2 = json.dumps(S.scan_file(path, html), ensure_ascii=False)
        self.assertEqual(run1, run2, "Two scan_file runs on same fixture differ")

    def test_fixture_sameas_mismatch_exactly_one_finding(self):
        """Only the unlinked facebook URL must be reported, not the linked twitter."""
        path = str(FIXTURES_DIR / "schema_sameas_mismatch.html")
        html = pathlib.Path(path).read_text("utf-8")
        findings = S.scan_file(path, html)
        sameas = by_category(findings, "schema-sameas")
        self.assertEqual(
            len(sameas), 1,
            f"Expected exactly 1 sameAs mismatch; got {len(sameas)}: {sameas}",
        )

    def test_fixture_valid_no_sameas_mismatch(self):
        """schema_valid.html has all sameAs URLs linked — no finding expected."""
        path = str(FIXTURES_DIR / "schema_valid.html")
        html = pathlib.Path(path).read_text("utf-8")
        findings = S.scan_file(path, html)
        sameas = by_category(findings, "schema-sameas")
        self.assertFalse(sameas)


# ---------------------------------------------------------------------------
# AC9: German output text (spot checks)
# ---------------------------------------------------------------------------

class TestGermanOutput(unittest.TestCase):

    def test_missing_finding_rationale_is_german(self):
        html = "<html><body><p>Kein JSON-LD hier.</p></body></html>"
        findings = S.scan_file("test.html", html)
        missing = by_category(findings, "schema-missing")
        if missing:
            r = missing[0]["rationale"]
            self.assertTrue(
                any(w in r for w in ("Suchmaschinen", "strukturierte", "Seite")),
                f"Rationale should contain German words: {r!r}",
            )

    def test_incomplete_finding_match_says_fehlt(self):
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Organization","name":"X"}'
            '</script>'
        )
        findings = S.scan_file("test.html", html)
        incomplete = by_category(findings, "schema-incomplete")
        if incomplete:
            self.assertIn("fehlt", incomplete[0]["match"],
                          f"match should say 'fehlt': {incomplete[0]['match']!r}")

    def test_broken_finding_match_says_ungueltig(self):
        html = '<script type="application/ld+json">{ invalid }</script>'
        findings = S.scan_file("test.html", html)
        broken = by_category(findings, "schema-broken")
        if broken:
            self.assertIn("ungültig", broken[0]["match"].lower())

    def test_deprecated_finding_match_says_veraltet(self):
        html = (
            '<script type="application/ld+json">'
            '{"@type":"WPHeader","name":"x"}'
            '</script>'
        )
        findings = S.scan_file("test.html", html)
        deprecated = by_category(findings, "schema-deprecated")
        if deprecated:
            self.assertIn("veraltet", deprecated[0]["match"].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
