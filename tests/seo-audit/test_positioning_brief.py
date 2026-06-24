#!/usr/bin/env python3
"""Tests for seo-audit/scripts/positioning_brief.py.

Covers all six acceptance criteria for issue 04 — Positioning-Brief-Input:

  AC1  --brief <invalid-path> does not hard-fail; falls back gracefully.
  AC2  Auto-discovery finds .seo/positioning.md or a marked CONTEXT.md section.
  AC3  Brief NEVER alters the deterministic Finding list or headline score.
  AC4  render_status() produces the correct German header string.
  AC5  Brief content is available as recommendation context.
  AC6  (structural) Code/comments in English; output strings in German.

Run from the repo root:
    PYTHONDONTWRITEBYTECODE=1 python3 tests/seo-audit/test_positioning_brief.py
"""

import os
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURES_DIR = REPO_ROOT / "tests" / "seo-audit" / "fixtures"

sys.path.insert(0, str(SCRIPTS_DIR))

import positioning_brief as PB  # noqa: E402
import synthesis as SY           # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmpdir():
    """Create a fresh temp directory; caller must clean up."""
    return tempfile.mkdtemp()


# ---------------------------------------------------------------------------
# AC1 — Graceful fallback on invalid / missing --brief path
# ---------------------------------------------------------------------------

class TestExplicitPath(unittest.TestCase):

    def setUp(self):
        self.tmp = _tmpdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_explicit_valid_path_loads_content(self):
        """A valid --brief path returns content and source."""
        brief_path = str(FIXTURES_DIR / "seo_positioning.md")
        result = PB.load_brief(brief_path, self.tmp)
        self.assertIsNotNone(result["source"])
        self.assertIn("Positioning line", result["content"])

    def test_explicit_invalid_path_does_not_raise(self):
        """AC1: An invalid path must not hard-fail — returns empty result."""
        result = PB.load_brief("/nonexistent/does_not_exist.md", self.tmp)
        # No exception raised; graceful empty result.
        self.assertIsNone(result["source"])
        self.assertEqual(result["content"], "")

    def test_explicit_invalid_path_then_auto_discovers_seo_md(self):
        """AC1: After invalid path, auto-discovery still runs."""
        seo_dir = os.path.join(self.tmp, ".seo")
        os.makedirs(seo_dir)
        brief_file = os.path.join(seo_dir, "positioning.md")
        with open(brief_file, "w", encoding="utf-8") as fh:
            fh.write("# Fallback Brief\nVia auto-discovery.")

        result = PB.load_brief("/nonexistent/brief.md", self.tmp)
        self.assertIsNotNone(result["source"])
        self.assertIn("Fallback Brief", result["content"])


# ---------------------------------------------------------------------------
# AC2 — Auto-discovery
# ---------------------------------------------------------------------------

class TestAutoDiscovery(unittest.TestCase):

    def setUp(self):
        self.tmp = _tmpdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_brief_no_auto_discovery_returns_empty(self):
        """Empty root with no brief files returns content="" source=None."""
        result = PB.load_brief(None, self.tmp)
        self.assertIsNone(result["source"])
        self.assertEqual(result["content"], "")

    def test_auto_discovers_seo_positioning_md(self):
        """AC2: .seo/positioning.md is found without --brief."""
        seo_dir = os.path.join(self.tmp, ".seo")
        os.makedirs(seo_dir)
        brief_file = os.path.join(seo_dir, "positioning.md")
        with open(brief_file, "w", encoding="utf-8") as fh:
            fh.write("# Brand Brief\nPositioning line: Fast and offline.")

        result = PB.load_brief(None, self.tmp)

        self.assertIsNotNone(result["source"])
        self.assertTrue(result["source"].endswith("positioning.md"))
        self.assertIn("Brand Brief", result["content"])

    def test_auto_discovers_context_md_marked_section(self):
        """AC2: Marked <!-- seo:brief --> section in CONTEXT.md is extracted."""
        context_path = os.path.join(self.tmp, "CONTEXT.md")
        with open(context_path, "w", encoding="utf-8") as fh:
            fh.write(
                "# Context\n\nSome preamble.\n\n"
                "<!-- seo:brief -->\n"
                "Positioning line: Audit tool for solo devs.\n"
                "<!-- /seo:brief -->\n"
                "\nTrailing content that must be excluded."
            )

        result = PB.load_brief(None, self.tmp)

        self.assertIsNotNone(result["source"])
        self.assertTrue(result["source"].endswith("CONTEXT.md"))
        self.assertIn("Positioning line", result["content"])
        self.assertNotIn("Trailing content", result["content"])

    def test_context_md_without_marker_is_ignored(self):
        """CONTEXT.md without seo:brief fences yields no brief."""
        context_path = os.path.join(self.tmp, "CONTEXT.md")
        with open(context_path, "w", encoding="utf-8") as fh:
            fh.write("# Context\n\nJust prose, no brief marker here.\n")

        result = PB.load_brief(None, self.tmp)
        self.assertIsNone(result["source"])
        self.assertEqual(result["content"], "")

    def test_seo_positioning_takes_priority_over_context_md(self):
        """AC2: .seo/positioning.md has higher priority than CONTEXT.md."""
        seo_dir = os.path.join(self.tmp, ".seo")
        os.makedirs(seo_dir)
        with open(os.path.join(seo_dir, "positioning.md"), "w", encoding="utf-8") as fh:
            fh.write("# SEO Brief (priority)")
        with open(os.path.join(self.tmp, "CONTEXT.md"), "w", encoding="utf-8") as fh:
            fh.write("<!-- seo:brief -->CONTEXT brief<!-- /seo:brief -->")

        result = PB.load_brief(None, self.tmp)

        self.assertIn(".seo", result["source"])
        self.assertIn("SEO Brief (priority)", result["content"])

    def test_auto_discovers_from_fixture_context_md(self):
        """AC2: The fixtures/context_with_brief.md fixture is parseable."""
        text = (FIXTURES_DIR / "context_with_brief.md").read_text(encoding="utf-8")
        section = PB._extract_context_md_section(text)
        self.assertIsNotNone(section)
        self.assertIn("Positioning line", section)
        self.assertNotIn("Further notes", section)


# ---------------------------------------------------------------------------
# AC3 — Brief never alters Finding list or headline score
# ---------------------------------------------------------------------------

class TestIdempotency(unittest.TestCase):

    def setUp(self):
        self.tmp = _tmpdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _sample_findings(self):
        return [
            {
                "file_path": "index.html",
                "line_number": 1,
                "match": "App",
                "category": "brand",
                "severity": "med",
                "user_impact": 2,
                "fix_effort": 1,
                "dimension": "brand",
                "track": "technical",
            },
            {
                "file_path": "about.html",
                "line_number": 5,
                "match": "Tool",
                "category": "brand",
                "severity": "high",
                "user_impact": 3,
                "fix_effort": 2,
                "dimension": "brand",
                "track": "technical",
            },
        ]

    def test_findings_identical_without_any_brief(self):
        """AC3: synthesize is deterministic on its own."""
        findings = self._sample_findings()
        out1 = SY.synthesize(list(findings))
        out2 = SY.synthesize(list(findings))
        self.assertEqual(out1["findings"], out2["findings"])

    def test_findings_identical_regardless_of_brief_presence(self):
        """AC3: Loading a brief must not change the Finding list or score."""
        findings = self._sample_findings()

        # Run synthesis without any brief involvement.
        synth_without = SY.synthesize(list(findings))

        # Load a brief (would come from --brief or auto-discovery in audit.py).
        brief = PB.load_brief(str(FIXTURES_DIR / "seo_positioning.md"), self.tmp)
        self.assertIsNotNone(brief["source"])  # brief was actually loaded

        # Run synthesis again — brief is never passed to synthesize().
        synth_with = SY.synthesize(list(findings))

        self.assertEqual(
            synth_without["findings"],
            synth_with["findings"],
            "Finding list must be identical with or without a brief.",
        )
        self.assertEqual(
            synth_without.get("headline_score"),
            synth_with.get("headline_score"),
            "headline_score must be identical with or without a brief.",
        )

    def test_brief_content_not_present_in_finding_fields(self):
        """AC3: Brief content must not appear in any Finding field."""
        brief = PB.load_brief(str(FIXTURES_DIR / "seo_positioning.md"), self.tmp)
        findings = self._sample_findings()

        # Synthesize and check no finding contains brief text.
        synth = SY.synthesize(findings)
        brief_content = brief["content"]
        for finding in synth["findings"]:
            for value in finding.values():
                self.assertNotIn(
                    brief_content[:20],  # first 20 chars as a fingerprint
                    str(value),
                    f"Brief content leaked into finding field: {value!r}",
                )


# ---------------------------------------------------------------------------
# AC4 — Report header brief status (render_status)
# ---------------------------------------------------------------------------

class TestRenderStatus(unittest.TestCase):

    def test_loaded_status_is_german_with_path(self):
        """AC4: Status string when loaded is German and includes the path."""
        brief = {"content": "some text", "source": "/repo/.seo/positioning.md"}
        status = PB.render_status(brief)
        self.assertIn("geladen aus", status)
        self.assertIn("positioning.md", status)

    def test_not_found_status_is_german(self):
        """AC4: Status string when not found is German 'nicht gefunden'."""
        brief = {"content": "", "source": None}
        status = PB.render_status(brief)
        self.assertEqual(status, "nicht gefunden")

    def test_loaded_status_contains_backtick_path(self):
        """AC4: Source path is rendered in backticks (Markdown inline code)."""
        brief = {"content": "text", "source": "/some/path.md"}
        status = PB.render_status(brief)
        self.assertIn("`/some/path.md`", status)


# ---------------------------------------------------------------------------
# AC5 — Brief content available as recommendation context
# ---------------------------------------------------------------------------

class TestBriefContentAvailability(unittest.TestCase):

    def test_content_is_non_empty_string_when_loaded(self):
        """AC5: load_brief returns a non-empty content string for real files."""
        brief_path = str(FIXTURES_DIR / "seo_positioning.md")
        result = PB.load_brief(brief_path, str(FIXTURES_DIR))
        self.assertIsInstance(result["content"], str)
        self.assertGreater(len(result["content"]), 0)

    def test_content_contains_positioning_data(self):
        """AC5: Loaded content carries the full brief text for agent context."""
        brief_path = str(FIXTURES_DIR / "seo_positioning.md")
        result = PB.load_brief(brief_path, str(FIXTURES_DIR))
        # The fixture contains known keys from a positioning brief.
        self.assertIn("Positioning line", result["content"])
        self.assertIn("Moat", result["content"])
        self.assertIn("Voice", result["content"])

    def test_content_empty_string_when_no_brief(self):
        """AC5: Empty string (not None) is returned when no brief is found."""
        tmp = tempfile.mkdtemp()
        try:
            result = PB.load_brief(None, tmp)
            self.assertIsInstance(result["content"], str)
            self.assertEqual(result["content"], "")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# AC6 — Output language (structural check)
# ---------------------------------------------------------------------------

class TestOutputLanguage(unittest.TestCase):

    def test_render_status_output_is_german(self):
        """AC6: render_status produces German strings (not found case)."""
        status = PB.render_status({"content": "", "source": None})
        # "nicht gefunden" is the German phrase for "not found"
        self.assertEqual(status, "nicht gefunden")

    def test_render_status_loaded_uses_german_verb(self):
        """AC6: render_status uses 'geladen aus' (German for 'loaded from')."""
        status = PB.render_status({"content": "x", "source": "/p.md"})
        self.assertTrue(
            status.startswith("geladen aus"),
            f"Expected German prefix 'geladen aus', got: {status!r}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
