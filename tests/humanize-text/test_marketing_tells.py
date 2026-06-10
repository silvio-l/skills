#!/usr/bin/env python3
"""Tests for the 2026 marketing-slop rework of humanize-text.

Covers the high-confidence structural detectors and the soft frequency
scoring added so the skill actually fires on modern AI landing-page copy
(the kind that previously scored 50/50 despite obvious tells):

  - struct_anaphora      — "Kein X. Kein Y. Nur Z." / "No X. No Y."
  - struct_adj_tricolon  — "— groß, klar, motivierend" / bare 3-adjective segment
  - em-dash DENSITY       — soft penalty on the Density dimension
  - rhythm neutralisation — fragment (.ts) files don't get a free burstiness 10
  - prose extraction      — UI labels excluded from scoring denominators
  - always-surface gating — anaphora/adj-tricolon bypass the tier-2 cluster gate

These detectors are regex/heuristic driven and can fail SILENTLY (a missed
match produces a plausible "clean" verdict), which is exactly the case
CLAUDE.md says warrants tests.

Run from repo root:
    python3 tests/humanize-text/test_marketing_tells.py
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "humanize-text" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import slop_scanner  # noqa: E402
import slop_scorer   # noqa: E402


def _write(tmpdir: str, text: str, name: str = "input.md") -> str:
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _scan(self, text: str, name: str = "input.md", lang: str = "auto") -> list:
        path = _write(self._tmpdir.name, text, name)
        return slop_scanner.scan_file_with_language(path, lang)["findings"]

    def _ids(self, findings, pattern_id):
        return [f for f in findings if f["pattern_id"] == pattern_id]


# ---------------------------------------------------------------------------
# Anaphora
# ---------------------------------------------------------------------------

class TestAnaphora(_Tmp):
    def test_negation_anaphora_two_run_de(self):
        """Two consecutive 'Kein …' sentences are enough (negation opener)."""
        f = self._scan("Kein Tracking. Kein Stress. Nur ein klarer Plan.\n")
        self.assertEqual(1, len(self._ids(f, "struct_anaphora")))

    def test_negation_anaphora_three_run_de(self):
        f = self._scan("Kein Beleg. Kein Bank. Kein Pfennig.\n")
        hits = self._ids(f, "struct_anaphora")
        self.assertEqual(1, len(hits))
        self.assertEqual(2, hits[0]["tier"])

    def test_negation_anaphora_en(self):
        f = self._scan("No tracking. No stress. Just a clear plan.\n", lang="en")
        self.assertEqual(1, len(self._ids(f, "struct_anaphora")))

    def test_generic_anaphora_needs_three(self):
        """Non-negation opener needs a run of >=3 to count."""
        two = self._scan("Heute regnet es. Heute bleibt kalt.\n")
        self.assertEqual([], self._ids(two, "struct_anaphora"))
        three = self._scan("Heute regnet es. Heute ist kalt. Heute kommt Wind.\n")
        self.assertEqual(1, len(self._ids(three, "struct_anaphora")))

    def test_ordinary_enumeration_is_not_anaphora(self):
        """A single sentence listing items must NOT be flagged as anaphora."""
        f = self._scan("Wir nutzen Python, JavaScript und TypeScript taeglich.\n")
        self.assertEqual([], self._ids(f, "struct_anaphora"))

    def test_generic_article_opener_ignored(self):
        """Stop-listed generic openers (der/die/das) never count, even repeated."""
        f = self._scan("Die App ist gut. Die Daten sind sicher. Die Zukunft ist hell.\n")
        self.assertEqual([], self._ids(f, "struct_anaphora"))


# ---------------------------------------------------------------------------
# Adjective tricolon
# ---------------------------------------------------------------------------

class TestAdjTricolon(_Tmp):
    def test_after_dash_de(self):
        f = self._scan("Dein Betrag — gross, klar, motivierend. Jeden Monat.\n")
        hits = self._ids(f, "struct_adj_tricolon")
        self.assertEqual(1, len(hits))
        self.assertEqual(2, hits[0]["tier"])

    def test_after_colon(self):
        f = self._scan("So fuehlt es sich an: einfach, visuell, motivierend.\n")
        self.assertEqual(1, len(self._ids(f, "struct_adj_tricolon")))

    def test_whole_segment_triple_de(self):
        """A bare three-ADJECTIVE comma list as a whole German string (lowercase 2/3)."""
        f = self._scan('const x = "Einfach, visuell, motivierend";\n',
                       name="x.ts", lang="de")
        self.assertEqual(1, len(self._ids(f, "struct_adj_tricolon")))

    def test_german_noun_enumeration_not_flagged(self):
        """Regression: a capitalised German NOUN list is an enumeration, not a tell."""
        f = self._scan('const x = "Lebensmittel, Mobilität, Freizeit";\n',
                       name="x.ts", lang="de")
        self.assertEqual([], self._ids(f, "struct_adj_tricolon"))

    def test_german_noun_list_after_colon_not_flagged(self):
        """Regression: 'Kategorien: Noun, Noun, Noun' must not be a tell."""
        f = self._scan("Deine Kategorien: Lebensmittel, Mobilität, Freizeit.\n",
                       lang="de")
        self.assertEqual([], self._ids(f, "struct_adj_tricolon"))

    def test_english_bare_list_not_flagged(self):
        """English bare triples are skipped (no caps signal to tell noun from adj)."""
        f = self._scan('const x = "Groceries, transport, leisure";\n',
                       name="x.ts", lang="en")
        self.assertEqual([], self._ids(f, "struct_adj_tricolon"))

    def test_english_dash_triple_still_flagged(self):
        """English relies on the dash/colon form, which still fires."""
        f = self._scan("Your amount — big, clear, motivating. Every month.\n",
                       lang="en")
        self.assertEqual(1, len(self._ids(f, "struct_adj_tricolon")))

    def test_real_enumeration_in_phrase_not_flagged(self):
        """An enumeration embedded in a longer phrase is not a clause-final triple."""
        f = self._scan("Verfuegbar fuer iPhone, iPad und Android in deiner Tasche.\n")
        self.assertEqual([], self._ids(f, "struct_adj_tricolon"))

    def test_dash_followed_by_two_items_not_flagged(self):
        f = self._scan("Sichere Daten lokal — verschluesselt, mit Passwort.\n")
        self.assertEqual([], self._ids(f, "struct_adj_tricolon"))


# ---------------------------------------------------------------------------
# Em-dash density (soft scoring) + always-surface gating
# ---------------------------------------------------------------------------

class TestEmDashDensityScoring(unittest.TestCase):
    def _findings(self, n_emdash, n_words):
        f = [{"pattern_id": "punct_em_dash", "tier": 3, "line_number": 1}
             for _ in range(n_emdash)]
        return f, n_words

    def test_low_density_no_penalty(self):
        f, wc = self._findings(1, 200)  # 0.5 / 100 words, below floor
        self.assertEqual(10.0, slop_scorer._score_density(f, wc))

    def test_high_density_penalised(self):
        f, wc = self._findings(20, 500)  # 4.0 / 100 words, well above floor
        self.assertLess(slop_scorer._score_density(f, wc), 8.0)

    def test_penalty_is_capped(self):
        f, wc = self._findings(200, 200)  # absurd density
        self.assertGreaterEqual(slop_scorer._score_density(f, wc), 1.0)


class TestAlwaysSurface(unittest.TestCase):
    def test_anaphora_surfaces_without_cluster(self):
        """A lone anaphora finding surfaces even though it is tier-2 and isolated."""
        findings = [{
            "pattern_id": "struct_anaphora", "tier": 2, "line_number": 5,
            "file_path": "x", "match": "Kein A. Kein B",
        }]
        out = slop_scorer.apply_tier_gating(findings, word_count=100)
        self.assertEqual(1, len(out["surfaced_findings"]))

    def test_lone_neg_parallelism_does_not_surface(self):
        """Softer neg-parallelism still needs a cluster to surface."""
        findings = [{
            "pattern_id": "struct_neg_parallelism", "tier": 2, "line_number": 5,
            "file_path": "x", "match": "not just A but B",
        }]
        out = slop_scorer.apply_tier_gating(findings, word_count=100)
        self.assertEqual([], out["surfaced_findings"])


# ---------------------------------------------------------------------------
# Rhythm neutralisation + prose extraction
# ---------------------------------------------------------------------------

class TestRhythmNeutral(unittest.TestCase):
    def test_neutral_flag_overrides_burstiness(self):
        text = "Short. A considerably longer sentence with many more words here.\n"
        normal = slop_scorer.score(text, [])["dimensions"]["rhythm"]
        neutral = slop_scorer.score(text, [], rhythm_neutral=True)["dimensions"]["rhythm"]
        self.assertEqual(slop_scorer.NEUTRAL_RHYTHM, neutral)
        self.assertNotEqual(normal, neutral)


class TestProseExtraction(_Tmp):
    def test_short_labels_excluded(self):
        ts = (
            'const t = {\n'
            '  nav: "EN",\n'
            '  cta: "App laden",\n'
            '  body: "Dies ist ein echter Satz mit vielen Woertern fuer die Prosa.",\n'
            '};\n'
        )
        path = _write(self._tmpdir.name, ts, "t.ts")
        prose = slop_scanner.extract_prose_text(path)
        self.assertIn("echter Satz", prose)
        self.assertNotIn("App laden", prose)
        self.assertNotIn("EN", prose.split())


if __name__ == "__main__":
    unittest.main(verbosity=2)
