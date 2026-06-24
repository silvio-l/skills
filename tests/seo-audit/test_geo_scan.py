#!/usr/bin/env python3
"""Tests for seo-audit/scripts/geo_scan.py.

The scanner walks a built HTML directory, checks GEO/AEO signals, and
returns Finding dicts with dimension='geo'.

Checked signals:
  - About/Entity-page presence (who-is-X)
  - Citable prose blocks (< MIN_PROSE_CHARS chars → thin)
  - FAQ/Q&A structures in visible HTML
  - Heading structure (H1 count, hierarchy, styled div/span)
  - llms.txt / llms-full.txt presence

Run from the repo root:
    python3 tests/seo-audit/test_geo_scan.py
"""

import json
import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURES_DIR = REPO_ROOT / "tests" / "seo-audit" / "fixtures" / "geo"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import geo_scan as G  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def scan(tmp: str, quick: bool = False):
    """Shorthand for G.scan_directory."""
    return G.scan_directory(tmp, quick=quick)


def matches(findings, match_substr: str) -> list:
    """Return findings whose 'match' contains match_substr."""
    return [f for f in findings if match_substr in f["match"]]


# ---------------------------------------------------------------------------
# AC1: dimension="geo" on all findings; deterministic (byte-identical)
# ---------------------------------------------------------------------------

class TestDimensionAndDeterminism(unittest.TestCase):
    def test_all_findings_have_dimension_geo(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><p>Kurz.</p></body></html>\n")
            findings = scan(tmp)
            for f in findings:
                self.assertEqual(f.get("dimension"), "geo",
                                 f"finding {f['match']!r} missing dimension=geo")

    def test_determinism_two_runs_byte_identical(self):
        dist = str(FIXTURES_DIR / "dist")
        out1 = json.dumps(G.scan_directory(dist), ensure_ascii=False)
        out2 = json.dumps(G.scan_directory(dist), ensure_ascii=False)
        self.assertEqual(out1, out2, "Two runs over the same fixture differ")

    def test_findings_sorted_by_path_line_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "z.html"),
                  "<html><body></body></html>\n")
            write(os.path.join(tmp, "a.html"),
                  "<html><body></body></html>\n")
            findings = scan(tmp)
            keys = [(f["file_path"], f["line_number"], f["match"].lower())
                    for f in findings]
            self.assertEqual(keys, sorted(keys))


# ---------------------------------------------------------------------------
# AC2: About/Entity page presence
# ---------------------------------------------------------------------------

class TestAboutPagePresence(unittest.TestCase):
    def test_no_about_page_emits_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            findings = scan(tmp)
            self.assertTrue(
                matches(findings, "About"),
                "Expected about-page finding, got: " + str([f["match"] for f in findings]),
            )

    def test_about_page_by_path_suppresses_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "about.html"),
                  "<html><body><h1>Über uns</h1></body></html>\n")
            findings = scan(tmp)
            self.assertFalse(
                matches(findings, "About"),
                "Unexpected about-page finding when about.html exists",
            )

    def test_about_page_by_ueber_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "ueber-uns.html"),
                  "<html><body><h1>Über uns</h1></body></html>\n")
            findings = scan(tmp)
            self.assertFalse(matches(findings, "About"))

    def test_about_page_by_wir_are_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body>"
                  "<h1>Start</h1>"
                  "<h2>Wer wir sind</h2>"
                  "</body></html>\n")
            findings = scan(tmp)
            self.assertFalse(
                matches(findings, "About"),
                "Should detect who-is-X heading as about-page signal",
            )

    def test_about_finding_has_geo_dimension_and_strategic_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            findings = scan(tmp)
            about = [f for f in findings if "About" in f["match"]]
            self.assertEqual(len(about), 1)
            self.assertEqual(about[0]["dimension"], "geo")
            self.assertEqual(about[0]["track"], "strategic")


# ---------------------------------------------------------------------------
# AC3: Citable prose blocks
# ---------------------------------------------------------------------------

class TestCitableProse(unittest.TestCase):
    def test_no_paragraphs_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            findings = scan(tmp)
            self.assertTrue(
                matches(findings, "Absatz") or matches(findings, "Inhalt"),
                "Expected thin-content finding",
            )

    def test_only_short_paragraphs_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body>"
                  "<h1>Start</h1>"
                  "<p>Kurz.</p>"
                  "<p>Auch kurz.</p>"
                  "</body></html>\n")
            findings = scan(tmp)
            self.assertTrue(
                matches(findings, "Absatz") or matches(findings, "Inhalt"),
                "Expected thin-content finding for short paragraphs",
            )

    def test_long_paragraph_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65  # > MIN_PROSE_CHARS
            write(os.path.join(tmp, "index.html"),
                  f"<html><body><h1>Start</h1><p>{long_p}</p></body></html>\n")
            findings = scan(tmp)
            thin = matches(findings, "Absatz") + matches(findings, "Inhalt")
            self.assertFalse(thin, "Should not flag page with citable prose")

    def test_thin_finding_dimension_and_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            findings = scan(tmp)
            thin = matches(findings, "Absatz") + matches(findings, "Inhalt")
            if thin:
                self.assertEqual(thin[0]["dimension"], "geo")
                self.assertEqual(thin[0]["track"], "strategic")


# ---------------------------------------------------------------------------
# AC4: FAQ/Q&A structures
# ---------------------------------------------------------------------------

class TestFAQSignals(unittest.TestCase):
    def test_no_faq_emits_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65
            write(os.path.join(tmp, "index.html"),
                  f"<html><body><h1>Start</h1><p>{long_p}</p></body></html>\n")
            findings = scan(tmp)
            self.assertTrue(
                matches(findings, "FAQ") or matches(findings, "Q&A"),
                "Expected FAQ finding when no FAQ structure present",
            )

    def test_faq_via_details_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65
            write(os.path.join(tmp, "index.html"),
                  f"<html><body><h1>Start</h1><p>{long_p}</p>"
                  f"<details><summary>Frage?</summary><p>Antwort.</p></details>"
                  f"</body></html>\n")
            findings = scan(tmp)
            self.assertFalse(
                matches(findings, "FAQ") + matches(findings, "Q&A"),
                "Should not flag FAQ when details/summary present",
            )

    def test_faq_via_heading_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65
            write(os.path.join(tmp, "index.html"),
                  f"<html><body><h1>Start</h1><p>{long_p}</p>"
                  f"<h2>FAQ</h2>"
                  f"</body></html>\n")
            findings = scan(tmp)
            self.assertFalse(
                matches(findings, "FAQ") + matches(findings, "Q&A"),
                "Should not flag FAQ when FAQ heading present",
            )

    def test_faq_via_dl_dt(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65
            write(os.path.join(tmp, "index.html"),
                  f"<html><body><h1>Start</h1><p>{long_p}</p>"
                  f"<dl><dt>Frage?</dt><dd>Antwort.</dd></dl>"
                  f"</body></html>\n")
            findings = scan(tmp)
            self.assertFalse(
                matches(findings, "FAQ") + matches(findings, "Q&A"),
                "Should not flag FAQ when dl/dt present",
            )

    def test_faq_finding_dimension_and_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65
            write(os.path.join(tmp, "index.html"),
                  f"<html><body><h1>Start</h1><p>{long_p}</p></body></html>\n")
            findings = scan(tmp)
            faq = matches(findings, "FAQ") + matches(findings, "Q&A")
            if faq:
                self.assertEqual(faq[0]["dimension"], "geo")
                self.assertEqual(faq[0]["track"], "strategic")


# ---------------------------------------------------------------------------
# AC5: Heading structure
# ---------------------------------------------------------------------------

class TestHeadingStructure(unittest.TestCase):
    def test_multiple_h1_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body>"
                  "<h1>Erster Titel</h1>"
                  "<h2>Abschnitt</h2>"
                  "<h1>Zweiter Titel</h1>"
                  "</body></html>\n")
            findings = scan(tmp)
            self.assertTrue(
                matches(findings, "H1") or matches(findings, "h1"),
                "Expected multiple-H1 finding",
            )

    def test_no_h1_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h2>Abschnitt</h2></body></html>\n")
            findings = scan(tmp)
            self.assertTrue(
                matches(findings, "H1") or matches(findings, "h1"),
                "Expected missing-H1 finding",
            )

    def test_single_h1_not_flagged_for_h1_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65
            write(os.path.join(tmp, "index.html"),
                  f"<html><body><h1>Titel</h1><p>{long_p}</p></body></html>\n")
            findings = scan(tmp)
            # H1 count findings should be absent
            h1_count_findings = [
                f for f in findings
                if ("mehrfache H1" in f["match"] or "kein H1" in f["match"])
            ]
            self.assertFalse(h1_count_findings, "Should not flag single H1")

    def test_heading_hierarchy_skip_h3_without_h2_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body>"
                  "<h1>Titel</h1>"
                  "<h3>Unterabschnitt</h3>"
                  "</body></html>\n")
            findings = scan(tmp)
            self.assertTrue(
                any("Hierarchie" in f["match"] or "h3" in f["match"].lower()
                    for f in findings),
                "Expected hierarchy-skip finding for h3 without h2",
            )

    def test_proper_hierarchy_h1_h2_h3_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65
            write(os.path.join(tmp, "index.html"),
                  f"<html><body>"
                  f"<h1>Titel</h1>"
                  f"<h2>Abschnitt</h2>"
                  f"<h3>Unterabschnitt</h3>"
                  f"<p>{long_p}</p>"
                  f"</body></html>\n")
            findings = scan(tmp)
            hier_findings = [
                f for f in findings
                if "Hierarchie" in f["match"] or "Sprung" in f["match"]
            ]
            self.assertFalse(hier_findings, "Should not flag proper h1→h2→h3")

    def test_styled_div_heading_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  '<html><body>'
                  '<h1>Titel</h1>'
                  '<div class="h2">Pseudo-Heading</div>'
                  '</body></html>\n')
            findings = scan(tmp)
            self.assertTrue(
                any("div" in f["match"].lower() or "span" in f["match"].lower()
                    or "gestyl" in f["match"].lower()
                    for f in findings),
                "Expected styled-div finding",
            )

    def test_real_h2_not_flagged_as_styled(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65
            write(os.path.join(tmp, "index.html"),
                  f"<html><body>"
                  f"<h1>Titel</h1><h2>Abschnitt</h2><p>{long_p}</p>"
                  f"</body></html>\n")
            findings = scan(tmp)
            styled = [f for f in findings if "gestyl" in f["match"].lower()]
            self.assertFalse(styled)

    def test_heading_findings_have_geo_dimension_and_technical_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h2>Abschnitt</h2></body></html>\n")
            findings = scan(tmp)
            h_findings = [f for f in findings
                          if "H1" in f["match"] or "h1" in f["match"]]
            if h_findings:
                self.assertEqual(h_findings[0]["dimension"], "geo")
                self.assertEqual(h_findings[0]["track"], "technical")


# ---------------------------------------------------------------------------
# AC6: llms.txt presence
# ---------------------------------------------------------------------------

class TestLLMsTxt(unittest.TestCase):
    def test_missing_llms_txt_emits_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            findings = scan(tmp)
            self.assertTrue(
                matches(findings, "llms.txt"),
                "Expected llms.txt finding when absent",
            )

    def test_llms_txt_present_suppresses_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            with open(os.path.join(tmp, "llms.txt"), "w") as fh:
                fh.write("# Site\n")
            findings = scan(tmp)
            self.assertFalse(matches(findings, "llms.txt"),
                             "Should not flag llms.txt when present")

    def test_llms_full_txt_also_suppresses_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            with open(os.path.join(tmp, "llms-full.txt"), "w") as fh:
                fh.write("# Site full\n")
            findings = scan(tmp)
            self.assertFalse(matches(findings, "llms.txt"),
                             "Should not flag llms.txt when llms-full.txt present")

    def test_llms_finding_dimension_and_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            findings = scan(tmp)
            llms = matches(findings, "llms.txt")
            if llms:
                self.assertEqual(llms[0]["dimension"], "geo")
                self.assertEqual(llms[0]["track"], "technical")


# ---------------------------------------------------------------------------
# AC7: runs without --url; reduced under --quick
# ---------------------------------------------------------------------------

class TestQuickMode(unittest.TestCase):
    def test_quick_mode_omits_prose_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Page with no paragraphs → prose finding in normal mode
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            normal = scan(tmp, quick=False)
            quick = scan(tmp, quick=True)
            prose_normal = matches(normal, "Absatz") + matches(normal, "Inhalt")
            prose_quick = matches(quick, "Absatz") + matches(quick, "Inhalt")
            self.assertTrue(prose_normal,
                            "Normal mode should flag thin prose")
            self.assertFalse(prose_quick,
                             "Quick mode should skip prose check")

    def test_quick_mode_omits_faq_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_p = "a" * 65
            write(os.path.join(tmp, "index.html"),
                  f"<html><body><h1>Start</h1><p>{long_p}</p></body></html>\n")
            normal = scan(tmp, quick=False)
            quick = scan(tmp, quick=True)
            faq_normal = matches(normal, "FAQ") + matches(normal, "Q&A")
            faq_quick = matches(quick, "FAQ") + matches(quick, "Q&A")
            self.assertTrue(faq_normal, "Normal mode should flag missing FAQ")
            self.assertFalse(faq_quick, "Quick mode should skip FAQ check")

    def test_quick_mode_still_runs_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body></body></html>\n")
            quick = scan(tmp, quick=True)
            # No H1 finding should still appear in quick mode
            self.assertTrue(
                any("H1" in f["match"] or "h1" in f["match"] for f in quick),
                "Quick mode should still check headings",
            )

    def test_quick_mode_still_checks_about_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            quick = scan(tmp, quick=True)
            self.assertTrue(
                matches(quick, "About"),
                "Quick mode should still check about-page presence",
            )


# ---------------------------------------------------------------------------
# AC8: standalone CLI emits JSON
# ---------------------------------------------------------------------------

class TestStandaloneCLI(unittest.TestCase):
    def test_cli_outputs_json_list(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            script = str(SCRIPTS_DIR / "geo_scan.py")
            result = subprocess.run(
                [sys.executable, script, tmp],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(result.returncode, 0,
                             f"CLI exited {result.returncode}: {result.stderr}")
            parsed = json.loads(result.stdout)
            self.assertIsInstance(parsed, list)

    def test_cli_quick_flag(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            script = str(SCRIPTS_DIR / "geo_scan.py")
            result = subprocess.run(
                [sys.executable, script, tmp, "--quick"],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(result.returncode, 0)
            parsed = json.loads(result.stdout)
            self.assertIsInstance(parsed, list)


# ---------------------------------------------------------------------------
# AC9: fixture-based determinism (full site roundtrip)
# ---------------------------------------------------------------------------

class TestFixtureDeterminism(unittest.TestCase):
    def test_fixture_site_two_runs_byte_identical(self):
        dist = str(FIXTURES_DIR / "dist")
        out1 = json.dumps(G.scan_directory(dist), ensure_ascii=False)
        out2 = json.dumps(G.scan_directory(dist), ensure_ascii=False)
        self.assertEqual(out1, out2)

    def test_fixture_site_clean_site_has_few_findings(self):
        """The reference fixture has an about page, llms.txt, FAQ, and prose —
        so it should have very few or no major GEO findings."""
        dist = str(FIXTURES_DIR / "dist")
        findings = G.scan_directory(dist)
        # Dimension check
        for f in findings:
            self.assertEqual(f["dimension"], "geo")
        # About-page finding must be absent (about.html exists)
        self.assertFalse(matches(findings, "About"))
        # llms.txt finding must be absent
        self.assertFalse(matches(findings, "llms.txt"))


# ---------------------------------------------------------------------------
# AC10: output texts in German (finding text spot-check)
# ---------------------------------------------------------------------------

class TestGermanOutput(unittest.TestCase):
    def test_about_finding_text_is_german(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            findings = scan(tmp)
            about = [f for f in findings if "About" in f["match"]]
            if about:
                rationale = about[0].get("rationale", "")
                # Spot-check for German word
                self.assertTrue(
                    any(w in rationale for w in
                        ("Seite", "KI", "Entität", "Suchmaschinen", "zitierbare")),
                    f"Rationale should be in German: {rationale!r}",
                )

    def test_llms_finding_text_is_german(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "index.html"),
                  "<html><body><h1>Start</h1></body></html>\n")
            findings = scan(tmp)
            llms = matches(findings, "llms.txt")
            if llms:
                rationale = llms[0].get("rationale", "")
                self.assertTrue(
                    any(w in rationale for w in
                        ("KI", "Agenten", "Site", "Übersicht", "strukturierte")),
                    f"Rationale should be in German: {rationale!r}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
