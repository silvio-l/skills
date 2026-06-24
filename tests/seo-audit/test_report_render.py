#!/usr/bin/env python3
"""Tests for the report-renderer layer in seo-audit/scripts/audit.py.

Checks:
  AC1: Executive Summary shows headline_score/100 + dimensions breakdown
       with finding counts per dimension.
  AC2: Recommendations split into Strategisch/Technisch by track field.
  AC3: Technical findings with derivable fixes carry copy-paste snippet blocks.
  AC4: Render functions are purely additive — no file writes to dist.
  AC5: Two renders over identical inputs produce byte-identical output.
  AC6: Report output is in German; code/template comments in English.

Run from the repo root:
    PYTHONDONTWRITEBYTECODE=1 python3 tests/seo-audit/test_report_render.py
"""

import os
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
TEMPLATE_PATH = REPO_ROOT / "skills" / "seo-audit" / "templates" / "report.md"

sys.path.insert(0, str(SCRIPTS_DIR))

import audit as A     # noqa: E402
import synthesis as S  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(
    file_path="dist/index.html",
    line_number=1,
    match="kein JSON-LD",
    suggested_replacement="JSON-LD ergänzen",
    rationale="Ohne strukturierte Daten…",
    category="schema-missing",
    severity="high",
    user_impact=3,
    fix_effort=2,
    dimension="schema",
    track="technical",
):
    """Build a minimal Finding dict."""
    return {
        "file_path": file_path,
        "line_number": line_number,
        "match": match,
        "suggested_replacement": suggested_replacement,
        "rationale": rationale,
        "category": category,
        "severity": severity,
        "user_impact": user_impact,
        "fix_effort": fix_effort,
        "dimension": dimension,
        "track": track,
    }


def _synth(*raw_findings):
    """Run synthesis.synthesize and return the result."""
    return S.synthesize(list(raw_findings))


def _build_ctx(synth, date="2026-06-24"):
    """Build a minimal ctx dict matching the template slots."""
    return {
        "date": date,
        "root": "/repo",
        "framework": "astro",
        "domain_doc": "(none)",
        "pages_count": 3,
        "glossary_count": 5,
        "findings_count": len(synth["findings"]),
        "top_category": "schema",
        "headline_score": synth.get("headline_score", 100.0),
        "dimensions_breakdown": A._render_dimensions_breakdown(synth),
        "summary_prose": "Top-Befund: test.",
        "findings_by_category": A._render_findings_by_category(synth),
        "diff_section": "_Kein vorheriger Lauf._",
        "recommendations_strategic": A._render_recommendations_strategic(synth),
        "recommendations_technical": A._render_recommendations_technical(synth),
        "fix_snippets": A._render_fix_snippets(synth),
        "generator_version": "v-test",
        "brief_status": "nicht geladen",
        "brief_content": "_Kein Brief._",
    }


def _render(synth, date="2026-06-24"):
    """Render the full report template with the given synth output."""
    template = TEMPLATE_PATH.read_text("utf-8")
    ctx = _build_ctx(synth, date=date)
    return A._render(template, ctx)


# ---------------------------------------------------------------------------
# AC1: Executive Summary shows headline_score + dimensions breakdown
# ---------------------------------------------------------------------------

class TestAC1ExecutiveSummary(unittest.TestCase):

    def test_headline_score_appears_in_report(self):
        synth = _synth(_finding(dimension="schema", track="technical"))
        report = _render(synth)
        self.assertIn("## Executive Summary", report)
        score_str = str(synth["headline_score"])
        self.assertIn(score_str, report)
        self.assertIn("/100", report)

    def test_dimensions_breakdown_table_in_report(self):
        synth = _synth(_finding(dimension="schema", track="technical"))
        report = _render(synth)
        self.assertIn("### Dimensions-Breakdown", report)
        # Table header in German (AC6)
        self.assertIn("| Dimension |", report)
        self.assertIn("| Befunde |", report)

    def test_dimensions_breakdown_includes_finding_count(self):
        """Each dimension row must include the count of its findings."""
        f1 = _finding(dimension="schema", track="technical",
                      file_path="a.html", line_number=1, match="kein JSON-LD",
                      category="schema-missing")
        f2 = _finding(dimension="geo", track="strategic",
                      file_path="b.html", line_number=0,
                      match="keine About-Seite", category="geo-entity",
                      severity="high", user_impact=3, fix_effort=3)
        synth = _synth(f1, f2)
        breakdown = A._render_dimensions_breakdown(synth)
        # schema dimension has 1 finding
        self.assertIn("| schema |", breakdown)
        self.assertIn("| 1 |", breakdown)
        # geo dimension has 1 finding
        self.assertIn("| geo |", breakdown)

    def test_no_findings_gives_perfect_score_in_report(self):
        synth = _synth()
        report = _render(synth)
        self.assertIn("100.0/100", report)

    def test_dimensions_all_known_keys_present(self):
        """All DIMENSION_WEIGHTS_V1 dimensions appear in breakdown."""
        synth = _synth()
        breakdown = A._render_dimensions_breakdown(synth)
        for dim in S.DIMENSION_WEIGHTS_V1:
            self.assertIn(dim, breakdown)


# ---------------------------------------------------------------------------
# AC2: Recommendations split into Strategisch / Technisch
# ---------------------------------------------------------------------------

class TestAC2TrackSplit(unittest.TestCase):

    def setUp(self):
        self.strategic = _finding(
            file_path="dist/index.html",
            line_number=0,
            match="keine About-/Entity-Seite",
            suggested_replacement="About-Seite erstellen",
            category="geo-entity",
            dimension="geo",
            track="strategic",
            severity="high",
            user_impact=3,
            fix_effort=3,
        )
        self.technical = _finding(
            file_path="dist/index.html",
            line_number=0,
            match="kein JSON-LD",
            suggested_replacement="JSON-LD ergänzen",
            category="schema-missing",
            dimension="schema",
            track="technical",
            severity="high",
            user_impact=3,
            fix_effort=2,
        )

    def test_strategic_section_contains_strategic_finding(self):
        synth = _synth(self.strategic, self.technical)
        section = A._render_recommendations_strategic(synth)
        self.assertIn("keine About-/Entity-Seite", section)
        self.assertNotIn("kein JSON-LD", section)

    def test_technical_section_contains_technical_finding(self):
        synth = _synth(self.strategic, self.technical)
        section = A._render_recommendations_technical(synth)
        self.assertIn("kein JSON-LD", section)
        self.assertNotIn("keine About-/Entity-Seite", section)

    def test_report_has_both_section_headers(self):
        synth = _synth(self.strategic, self.technical)
        report = _render(synth)
        self.assertIn("### Strategisch (du entscheidest)", report)
        self.assertIn("### Technisch (umsetzbar)", report)

    def test_empty_strategic_yields_placeholder(self):
        synth = _synth(self.technical)
        section = A._render_recommendations_strategic(synth)
        self.assertIn("Keine Befunde", section)

    def test_empty_technical_yields_placeholder(self):
        synth = _synth(self.strategic)
        section = A._render_recommendations_technical(synth)
        self.assertIn("Keine Befunde", section)

    def test_default_track_is_treated_as_technical(self):
        """A finding without an explicit track must land in the technical section."""
        no_track = {
            "file_path": "dist/x.html",
            "line_number": 1,
            "match": "brand-match",
            "suggested_replacement": "fix",
            "rationale": "r",
            "category": "brand",
            "severity": "med",
            "user_impact": 2,
            "fix_effort": 1,
        }
        synth = _synth(no_track)
        tech_section = A._render_recommendations_technical(synth)
        self.assertIn("brand-match", tech_section)
        strat_section = A._render_recommendations_strategic(synth)
        self.assertNotIn("brand-match", strat_section)


# ---------------------------------------------------------------------------
# AC3: Fix-Snippet derivation
# ---------------------------------------------------------------------------

class TestAC3FixSnippets(unittest.TestCase):

    def _schema_missing_finding(self, fp="dist/index.html"):
        return _finding(
            file_path=fp,
            line_number=0,
            match="kein JSON-LD",
            category="schema-missing",
            dimension="schema",
            track="technical",
            severity="high",
            user_impact=3,
            fix_effort=2,
        )

    def _schema_incomplete_finding(
        self,
        schema_type="Organization",
        field="url",
        fp="dist/index.html",
    ):
        return _finding(
            file_path=fp,
            line_number=5,
            match=f"{schema_type}: Pflichtfeld „{field}“ fehlt",
            category="schema-incomplete",
            dimension="schema",
            track="technical",
            severity="high",
            user_impact=3,
            fix_effort=2,
        )

    def _llms_txt_finding(self, dist_root="dist"):
        return _finding(
            file_path=dist_root,
            line_number=0,
            match="llms.txt fehlt",
            category="geo-llms",
            dimension="geo",
            track="technical",
            severity="low",
            user_impact=1,
            fix_effort=1,
        )

    # ---- _derive_fix_snippet -------------------------------------------------

    def test_schema_missing_yields_snippet(self):
        key, snippet = A._derive_fix_snippet(self._schema_missing_finding())
        self.assertEqual(key, "schema-missing")
        self.assertIn("@context", snippet)
        self.assertIn("WebSite", snippet)

    def test_schema_incomplete_yields_snippet_with_field(self):
        key, snippet = A._derive_fix_snippet(
            self._schema_incomplete_finding("Organization", "url")
        )
        self.assertIsNotNone(key)
        self.assertIn("Organization", snippet)
        self.assertIn("url", snippet)

    def test_schema_incomplete_key_encodes_type_and_field(self):
        key, _ = A._derive_fix_snippet(
            self._schema_incomplete_finding("Article", "author")
        )
        self.assertIn("Article", key)
        self.assertIn("author", key)

    def test_llms_txt_yields_snippet(self):
        key, snippet = A._derive_fix_snippet(self._llms_txt_finding())
        self.assertEqual(key, "geo-llms")
        self.assertIn("llms.txt", snippet)
        self.assertIn("llmstxt.org", snippet)

    def test_strategic_finding_yields_no_snippet(self):
        strategic = _finding(
            match="keine About-Seite",
            category="geo-entity",
            track="strategic",
        )
        key, snippet = A._derive_fix_snippet(strategic)
        self.assertIsNone(key)
        self.assertIsNone(snippet)

    def test_brand_finding_yields_no_snippet(self):
        brand = _finding(
            match="App",
            category="brand",
            track="technical",
        )
        key, snippet = A._derive_fix_snippet(brand)
        self.assertIsNone(key)
        self.assertIsNone(snippet)

    # ---- _render_fix_snippets ------------------------------------------------

    def test_render_fix_snippets_includes_json_ld_for_schema_missing(self):
        synth = _synth(self._schema_missing_finding())
        rendered = A._render_fix_snippets(synth)
        self.assertIn("```json", rendered)
        self.assertIn("@context", rendered)

    def test_render_fix_snippets_includes_llms_txt_skeleton(self):
        synth = _synth(self._llms_txt_finding())
        rendered = A._render_fix_snippets(synth)
        self.assertIn("llms.txt", rendered)

    def test_deduplication_schema_missing_shown_once(self):
        """Multiple files with kein-JSON-LD → snippet shown only once."""
        f1 = self._schema_missing_finding("dist/index.html")
        f2 = self._schema_missing_finding("dist/about.html")
        synth = _synth(f1, f2)
        rendered = A._render_fix_snippets(synth)
        # The snippet marker must appear exactly once.
        self.assertEqual(rendered.count('"@type": "WebSite"'), 1)

    def test_deduplication_schema_incomplete_per_type_and_field(self):
        """Same type+field missing in two files → snippet shown once."""
        f1 = self._schema_incomplete_finding("Organization", "url", "dist/a.html")
        f2 = self._schema_incomplete_finding("Organization", "url", "dist/b.html")
        synth = _synth(f1, f2)
        rendered = A._render_fix_snippets(synth)
        self.assertEqual(rendered.count('"@type": "Organization"'), 1)

    def test_no_snippets_placeholder_in_german(self):
        """Pure strategic findings → German placeholder (AC6)."""
        strategic = _finding(
            match="keine About-Seite",
            category="geo-entity",
            track="strategic",
        )
        synth = _synth(strategic)
        rendered = A._render_fix_snippets(synth)
        self.assertIn("Keine", rendered)

    def test_fix_snippets_section_in_report(self):
        synth = _synth(self._schema_missing_finding())
        report = _render(synth)
        self.assertIn("### Fix-Snippets", report)
        self.assertIn("```json", report)

    def test_schema_incomplete_snippet_contains_placeholder(self):
        f = self._schema_incomplete_finding("WebSite", "url")
        synth = _synth(f)
        rendered = A._render_fix_snippets(synth)
        self.assertIn("PLACEHOLDER", rendered)


# ---------------------------------------------------------------------------
# AC4: Report-only — render functions do not write to dist
# ---------------------------------------------------------------------------

class TestAC4ReportOnly(unittest.TestCase):

    def test_render_functions_return_strings_not_none(self):
        """All renderer functions must return str, never None or write files."""
        synth = _synth(
            _finding(dimension="schema", track="technical"),
            _finding(
                match="keine About-Seite",
                category="geo-entity",
                track="strategic",
                dimension="geo",
            ),
        )
        self.assertIsInstance(A._render_dimensions_breakdown(synth), str)
        self.assertIsInstance(A._render_recommendations_strategic(synth), str)
        self.assertIsInstance(A._render_recommendations_technical(synth), str)
        self.assertIsInstance(A._render_fix_snippets(synth), str)

    def test_render_fix_snippets_does_not_write_files(self):
        """_render_fix_snippets must be a pure function (no file I/O)."""
        import builtins
        import io

        writes: list = []
        original_open = builtins.open

        def guarded_open(file, mode="r", **kwargs):
            if "w" in str(mode) or "a" in str(mode):
                writes.append(file)
                raise AssertionError(f"Unexpected file write: {file}")
            return original_open(file, mode, **kwargs)

        synth = _synth(_finding(category="schema-missing", track="technical"))
        builtins.open = guarded_open
        try:
            A._render_fix_snippets(synth)
        finally:
            builtins.open = original_open

        self.assertEqual(writes, [], "render_fix_snippets must not write any files")

    def test_full_render_pipeline_no_dist_writes(self):
        """Run full report render into a temp dir; verify dist dir is untouched."""
        with tempfile.TemporaryDirectory() as dist_tmp:
            # Plant a sentinel file.
            sentinel = os.path.join(dist_tmp, "sentinel.html")
            with open(sentinel, "w") as fh:
                fh.write("<html></html>")
            mtime_before = os.path.getmtime(sentinel)

            # Build ctx manually (simulating the render path without running audit.py
            # end-to-end so we don't need a real root).
            synth = _synth(
                _finding(file_path=sentinel, category="schema-missing",
                         track="technical", dimension="schema"),
            )
            template = TEMPLATE_PATH.read_text("utf-8")
            ctx = _build_ctx(synth)
            A._render(template, ctx)   # must not touch dist_tmp

            mtime_after = os.path.getmtime(sentinel)
            self.assertEqual(mtime_before, mtime_after,
                             "Render pipeline must not modify dist files")


# ---------------------------------------------------------------------------
# AC5: Idempotency — byte-identical output on repeated calls
# ---------------------------------------------------------------------------

class TestAC5Idempotency(unittest.TestCase):

    def _mixed_synth(self):
        return _synth(
            _finding(
                file_path="dist/index.html",
                line_number=0,
                match="kein JSON-LD",
                category="schema-missing",
                dimension="schema",
                track="technical",
                severity="high",
                user_impact=3,
                fix_effort=2,
            ),
            _finding(
                file_path="dist/index.html",
                line_number=0,
                match="keine About-/Entity-Seite",
                category="geo-entity",
                dimension="geo",
                track="strategic",
                severity="high",
                user_impact=3,
                fix_effort=3,
            ),
            _finding(
                file_path="dist/index.html",
                line_number=0,
                match="llms.txt fehlt",
                category="geo-llms",
                dimension="geo",
                track="technical",
                severity="low",
                user_impact=1,
                fix_effort=1,
            ),
        )

    def test_two_renders_are_byte_identical(self):
        synth = self._mixed_synth()
        # Pin the date so both calls are identical.
        report1 = _render(synth, date="2026-06-24")
        report2 = _render(synth, date="2026-06-24")
        self.assertEqual(report1, report2)

    def test_render_fix_snippets_is_idempotent(self):
        synth = self._mixed_synth()
        out1 = A._render_fix_snippets(synth)
        out2 = A._render_fix_snippets(synth)
        self.assertEqual(out1, out2)

    def test_render_recommendations_is_idempotent(self):
        synth = self._mixed_synth()
        strat1 = A._render_recommendations_strategic(synth)
        strat2 = A._render_recommendations_strategic(synth)
        self.assertEqual(strat1, strat2)
        tech1 = A._render_recommendations_technical(synth)
        tech2 = A._render_recommendations_technical(synth)
        self.assertEqual(tech1, tech2)

    def test_dimensions_breakdown_is_idempotent(self):
        synth = self._mixed_synth()
        bd1 = A._render_dimensions_breakdown(synth)
        bd2 = A._render_dimensions_breakdown(synth)
        self.assertEqual(bd1, bd2)

    def test_reversed_input_findings_same_output(self):
        """Synthesis determinism: reversed input → same rendered report."""
        findings = [
            _finding(
                file_path="dist/b.html",
                line_number=1,
                match="kein JSON-LD",
                category="schema-missing",
                dimension="schema",
                track="technical",
                severity="high",
                user_impact=3,
                fix_effort=2,
            ),
            _finding(
                file_path="dist/a.html",
                line_number=0,
                match="keine About-Seite",
                category="geo-entity",
                dimension="geo",
                track="strategic",
                severity="high",
                user_impact=3,
                fix_effort=3,
            ),
        ]
        synth1 = S.synthesize(list(findings))
        synth2 = S.synthesize(list(reversed(findings)))
        report1 = _render(synth1, date="2026-06-24")
        report2 = _render(synth2, date="2026-06-24")
        self.assertEqual(report1, report2)


# ---------------------------------------------------------------------------
# AC6: German output text
# ---------------------------------------------------------------------------

class TestAC6GermanOutput(unittest.TestCase):

    def test_report_section_headers_in_german(self):
        synth = _synth()
        report = _render(synth)
        self.assertIn("## Executive Summary", report)
        self.assertIn("## Findings nach Kategorie", report)
        self.assertIn("## Empfehlungen", report)
        self.assertIn("### Strategisch (du entscheidest)", report)
        self.assertIn("### Technisch (umsetzbar)", report)
        self.assertIn("### Fix-Snippets (copy-paste-fertig)", report)

    def test_empty_track_placeholder_in_german(self):
        synth = _synth()
        strat = A._render_recommendations_strategic(synth)
        tech = A._render_recommendations_technical(synth)
        # "Keine Befunde" is German for "No findings"
        self.assertIn("Keine Befunde", strat)
        self.assertIn("Keine Befunde", tech)

    def test_no_snippets_message_in_german(self):
        synth = _synth()
        snippets = A._render_fix_snippets(synth)
        # German placeholder must appear
        self.assertIn("Keine", snippets)

    def test_dimensions_table_header_in_german(self):
        synth = _synth()
        bd = A._render_dimensions_breakdown(synth)
        self.assertIn("Befunde", bd)
        self.assertIn("Score", bd)

    def test_llms_txt_snippet_contains_german_section_header(self):
        llms_f = _finding(
            match="llms.txt fehlt",
            category="geo-llms",
            track="technical",
        )
        _, snippet = A._derive_fix_snippet(llms_f)
        self.assertIn("Über diese Site", snippet)
        self.assertIn("Wichtige Seiten", snippet)


if __name__ == "__main__":
    unittest.main(verbosity=2)
