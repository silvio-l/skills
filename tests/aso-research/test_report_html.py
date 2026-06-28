#!/usr/bin/env python3
"""Tests for the HTML report builder (slice 06 + 09) — report.build_report_html().

Run from the repo root:
    python3 -m unittest discover -s tests/aso-research -q

Covers: self-contained HTML, German localisation, glossary, score bars,
visual design elements, brand conflicts, source health, determinism.
"""

import datetime
import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import report  # noqa: E402

NOW = datetime.datetime(2026, 6, 26, 12, 0, 0)


def _config(*, own_app_id=None, country="de", language="de"):
    return {
        "app_name": "Habit Hero",
        "description": "A gamified habit tracker app",
        "category": "health_fitness",
        "country": country,
        "language": language,
        "own_app_id": own_app_id,
        "seed_keywords": ["habit", "tracker"],
    }


def _competitors():
    return [
        {"id": "1", "title": "Habit Tracker", "developer": "DevA",
         "category": "health_fitness", "rating_avg": 4.5, "rating_count": 1000,
         "price_model": "free", "subtitle": "Daily Routine",
         "discovery": "chart/search", "platform": "apple"},
        {"id": "2", "title": "Streak Buddy", "developer": "DevB",
         "category": "health_fitness", "rating_avg": 4.7, "rating_count": 500,
         "price_model": "paid", "subtitle": "",
         "discovery": "niche_similar", "platform": "apple"},
    ]


def _keywords():
    return [
        {"term": "habit", "competition": 20, "relevance": 80, "opportunity": 64,
         "split": "primary-candidate", "is_gap": False, "suggest": True},
        {"term": "tracker", "competition": 40, "relevance": 70, "opportunity": 42,
         "split": "primary-candidate", "is_gap": False, "suggest": False},
        {"term": "routine", "competition": 10, "relevance": 60, "opportunity": 54,
         "split": "primary-candidate", "is_gap": True, "suggest": False},
        {"term": "daily streak", "competition": 60, "relevance": 50, "opportunity": 20,
         "split": "long-tail-candidate", "is_gap": False, "suggest": False},
        {"term": "gamified", "competition": 5, "relevance": 55, "opportunity": 52,
         "split": "long-tail-candidate", "is_gap": False, "suggest": True},
    ]


def _s1():
    return {
        "niches": ["gamified habits", "streak motivation"],
        "dominant_themes": ["routine building", "daily reminders"],
        "leader_positioning": ["Spotify-style gamification"],
        "audiences": ["students", "professionals"],
        "missing_themes": ["accountability partners"],
        "threats": ["Apple native Reminders integration"],
    }


def _s2():
    title = "Habit Hero Tracker"
    subtitle = "Build Daily Routines"
    kw = "habit,tracker,routine,streak"
    return {
        "store": "apple",
        "slots": [
            {"slot": "title", "recommended": {"text": title, "char_count": len(title)},
             "alternatives": [{"text": "Habit Hero", "char_count": 10},
                              {"text": "Daily Habit", "char_count": 10}]},
            {"slot": "subtitle", "recommended": {"text": subtitle, "char_count": len(subtitle)},
             "alternatives": [{"text": "Routine Builder", "char_count": 14},
                              {"text": "Streak & Habit", "char_count": 14}]},
            {"slot": "keyword_field", "recommended": {"text": kw, "char_count": len(kw)},
             "alternatives": [{"text": "habit,routine,daily", "char_count": 19},
                              {"text": "tracker,streak", "char_count": 14}]},
        ],
    }


def _play_s2():
    title = "Habit Hero Tracker"
    short = "Build daily habits & routines that stick"
    long_text = "Habit Hero is the best habit tracker."
    return {
        "store": "play",
        "slots": [
            {"slot": "title", "recommended": {"text": title, "char_count": len(title)},
             "alternatives": [{"text": "Habit Hero", "char_count": 10},
                              {"text": "Daily Habit", "char_count": 10}]},
            {"slot": "short", "recommended": {"text": short, "char_count": len(short)},
             "alternatives": [{"text": "Track routines daily", "char_count": 20},
                              {"text": "Build streaks now", "char_count": 17}]},
            {"slot": "long", "recommended": {"text": long_text, "char_count": len(long_text)},
             "alternatives": [{"text": "alt long one", "char_count": 11},
                              {"text": "alt long two", "char_count": 11}]},
        ],
    }


def _play_competitors():
    return [
        {"id": "com.a", "platform": "play", "title": "Habit Hero", "developer": "DevA",
         "category": "health_fitness", "rating_avg": 4.5, "rating_count": 1000,
         "price_model": "free", "discovery": "chart/search"},
    ]


def _h2_ok():
    return {"status": "ok", "findings": [], "note": "every keyword evidence-conform."}


def _brand_conflicts():
    return [
        {
            "term": "diktieren zu text",
            "forbidden_match": "diktieren",
            "replacement": "Spracheingabe",
            "opportunity": 80,
            "relevance": 70,
            "platform": "apple",
            "strategies": ["keyword-field-only", "alternative phrasing",
                           "non-brand landingpage", "accept deliberately"],
        },
        {
            "term": "dictate app",
            "forbidden_match": "dictate",
            "replacement": "speak",
            "opportunity": 60,
            "relevance": 55,
            "platform": "apple",
            "strategies": ["keyword-field-only", "alternative phrasing",
                           "non-brand landingpage", "accept deliberately"],
        },
    ]


# ---------------------------------------------------------------------------
# AC1/AC2 — Self-contained HTML
# ---------------------------------------------------------------------------

class SelfContainedHTMLTests(unittest.TestCase):
    """AC1: build_report_html returns self-contained HTML string."""

    def test_returns_string(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 500)

    def test_single_html_document(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertEqual(html.lower().count("<html"), 1)
        self.assertIn("</html>", html)

    def test_has_doctype(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertTrue(html.strip().lower().startswith("<!doctype html"))

    def test_uses_german_lang(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn('lang="de"', html)

    def test_has_inline_style_block(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("<style>", html)
        self.assertIn("</style>", html)

    def test_no_external_assets(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertNotIn('src="http', html)
        self.assertNotIn("src='http", html)
        self.assertNotIn('href="http', html)
        self.assertNotIn("href='http", html)
        self.assertNotIn('rel="stylesheet"', html.lower())

    def test_no_external_fonts(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertNotIn("@import url(", html)
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("fonts.gstatic.com", html)

    def test_no_script_tags(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertNotIn("<script", html.lower())


# ---------------------------------------------------------------------------
# German localisation
# ---------------------------------------------------------------------------

class GermanLocalisationTests(unittest.TestCase):
    """AC: German text strings and section headings."""

    def test_german_section_headings(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok(),
        )
        de_sections = [
            "Quellen-Signal",
            "Zusammenfassung",
            "Wettbewerbslandschaft",
            "Positionierungsmap",
            "Keyword-Bericht",
            "Chancen",
            "Risiken",
            "Listing-Empfehlung",
            "Methodik",
            "Glossar",
        ]
        for name in de_sections:
            with self.subTest(section=name):
                self.assertIn(name, html, f"missing German section heading: {name}")

    def test_german_table_headers(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Wettbewerb", html)
        self.assertIn("Relevanz", html)
        self.assertIn("Chance", html)
        self.assertIn("Kategorie", html)
        self.assertIn("Lücke", html)
        self.assertIn("Titel", html)
        self.assertIn("Entwickler", html)
        self.assertIn("Bewertung", html)
        self.assertIn("Quelle", html)

    def test_german_kpi_labels(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Apple", html)
        self.assertIn("Nische", html)
        self.assertIn("Primär", html)
        self.assertIn("Long-Tail", html)
        self.assertIn("Gaps", html)

    def test_german_bucket_labels(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Schnelle Gewinne", html)
        self.assertIn("Nischen-Hebel", html)
        self.assertIn("Abdeckungslücken", html)

    def test_german_source_labels(self):
        status = {
            "apple_subtitle": {"status": "ok", "result_count": 3},
            "apple_similar": {"status": "unavailable", "reason": "timeout"},
        }
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            source_status=status,
        )
        self.assertIn("Treffer", html)
        self.assertIn("nicht verfügbar", html)
        self.assertIn("Aktiv", html)

    def test_german_generated_label(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("2026-06-26 12:00:00", html)

    def test_german_brand_conflict_panel(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            brand_conflicts=_brand_conflicts(),
        )
        self.assertIn("Markenkonflikte", html)
        self.assertIn("Verbotener Treffer", html)
        self.assertIn("Ersetzung", html)
        self.assertIn("Anti-Vokabular", html)
        self.assertIn("Projektinhaber", html)

    def test_german_honesty_section(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Ehrlichkeit", html)
        self.assertIn("Proxy-Signale", html)
        self.assertIn("kein echtes suchvolumen", html.lower())


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------

class GlossaryTests(unittest.TestCase):
    """AC: ## Glossar section with required terms."""

    def test_glossary_section_present(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Glossar", html)

    REQUIRED_TERMS = [
        "Relevanz",
        "Chance",
        "Wettbewerb",
        "Suchvolumen",
        "Primärkandidat",
        "Long-Tail-Kandidat",
        "Search-Suggest",
        "Qualitativer Kanal",
        "Markenkonflikt",
        "Anti-Vokabular",
    ]

    def test_glossary_contains_all_required_terms(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        for term in self.REQUIRED_TERMS:
            with self.subTest(term=term):
                self.assertIn(term, html, f"glossary missing term: {term}")

    def test_glossary_uses_grid_layout(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn('class="glossary"', html)
        self.assertIn("<dl", html)
        self.assertIn("<dt>", html)
        self.assertIn("<dd>", html)

    def test_glossary_renders_even_with_minimal_data(self):
        html = report.build_report_html(
            _config(), [], [], now=NOW)
        self.assertIn("Glossar", html)


# ---------------------------------------------------------------------------
# Visual design elements
# ---------------------------------------------------------------------------

class VisualDesignTests(unittest.TestCase):
    """AC: Visual design improvements — score bars, cards, colour palette."""

    def test_score_bars_in_keyword_table(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("bar__fill", html)
        self.assertIn("bar__num", html)
        self.assertIn("bar--", html)

    def test_score_bar_has_style_width(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn('style="width:', html)

    def test_card_sections_have_shadows(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("box-shadow", html)

    def test_accent_color_used(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("#5B5BD6", html)  # Astro indigo accent

    def test_danger_color_for_brand_conflicts(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            brand_conflicts=_brand_conflicts(),
        )
        self.assertIn('class="brand"', html)
        self.assertIn("#B23B33", html)  # brand-conflict danger tone

    def test_responsive_media_query(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("max-width:640px", html)

    def test_reduced_motion_respected(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("prefers-reduced-motion", html)

    def test_system_font_stack(self):
        # Astro-style native look: a system font stack, no serif display face.
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("-apple-system", html)


# ---------------------------------------------------------------------------
# Data parity (section contents)
# ---------------------------------------------------------------------------

class DataParityTests(unittest.TestCase):
    """HTML contains expected data."""

    def test_keyword_table_contains_terms(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        for term in ["habit", "tracker", "routine"]:
            with self.subTest(term=term):
                self.assertIn(term, html)

    def test_competitor_data_in_html(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Habit Tracker", html)
        self.assertIn("Streak Buddy", html)
        self.assertIn("DevA", html)
        self.assertIn("DevB", html)

    def test_run_meta_present(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Habit Hero", html)
        self.assertIn("2026-06-26", html)

    def test_listing_slots_in_html(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            s2_output=_s2(), h2_output=_h2_ok(),
        )
        self.assertIn("Habit Hero Tracker", html)
        self.assertIn("Build Daily Routines", html)
        self.assertIn("Zeichen", html)

    def test_play_listing_when_play_present(self):
        html = report.build_report_html(
            _config(), _play_competitors(), _keywords(), now=NOW,
            s2_output=_s2(), h2_output=_h2_ok(),
            s2_play_output=_play_s2(), h2_play_output=_h2_ok(),
        )
        self.assertIn("Google Play", html)
        self.assertIn("Titel 30", html)
        self.assertIn("Kurz 80", html)
        self.assertIn("Lang 4000", html)

    def test_modus_a_renders_self_audit(self):
        s1 = _s1()
        s1["own_app_audit"] = ["own subtitle is generic"]
        html = report.build_report_html(
            _config(own_app_id="1"), _competitors(), _keywords(), now=NOW,
            s1_output=s1, s2_output=_s2(), h2_output=_h2_ok(),
        )
        self.assertIn("Selbstaudit", html)
        self.assertIn("own subtitle is generic", html)


# ---------------------------------------------------------------------------
# Brand conflict visibility
# ---------------------------------------------------------------------------

class BrandConflictVisibilityTests(unittest.TestCase):
    """Brand conflicts are visually prominent."""

    def test_brand_conflicts_section_present_when_conflicts_exist(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            brand_conflicts=_brand_conflicts(),
        )
        self.assertIn("Markenkonflikt", html)

    def test_conflict_terms_visible(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            brand_conflicts=_brand_conflicts(),
        )
        self.assertIn("diktieren", html)
        self.assertIn("dictate", html)

    def test_conflict_replacements_visible(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            brand_conflicts=_brand_conflicts(),
        )
        self.assertIn("Spracheingabe", html)
        self.assertIn("speak", html)

    def test_strategies_visible(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            brand_conflicts=_brand_conflicts(),
        )
        self.assertIn("keyword-field-only", html)
        self.assertIn("alternative phrasing", html)

    def test_brand_conflict_uses_badge_or_warning_class(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            brand_conflicts=_brand_conflicts(),
        )
        has_visual = (
            'class="badge' in html
            or 'class="conflict' in html
            or 'class="brand' in html
            or "class='brand" in html
            or 'brand-conflict' in html.lower()
        )
        self.assertTrue(has_visual, "brand conflicts must have visual prominence markers")


# ---------------------------------------------------------------------------
# Source health board
# ---------------------------------------------------------------------------

class SourceHealthBoardTests(unittest.TestCase):
    """Source-health board distinguishes ok / unavailable-with-reason / ok-empty."""

    def test_source_health_board_present(self):
        status = {
            "apple_subtitle": {"status": "ok", "result_count": 3},
            "apple_similar": {"status": "unavailable",
                              "reason": "RuntimeError: browser timeout"},
        }
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            source_status=status,
        )
        self.assertIn("Quellen-Signal", html)
        self.assertIn("Apple Subtitle", html)
        self.assertIn("Apple Similar", html)

    def test_ok_source_shows_count(self):
        status = {
            "apple_subtitle": {"status": "ok", "result_count": 3},
        }
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            source_status=status,
        )
        self.assertIn("3", html)

    def test_unavailable_source_shows_reason(self):
        status = {
            "apple_similar": {"status": "unavailable",
                              "reason": "RuntimeError: browser timeout"},
        }
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            source_status=status,
        )
        self.assertIn("nicht verfügbar", html)
        self.assertIn("browser timeout", html)

    def test_ok_empty_source_shows_zero_result(self):
        status = {
            "apple_search_suggest": {"status": "ok", "result_count": 0},
        }
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            source_status=status,
        )
        self.assertIn("0", html)

    def test_source_health_uses_distinct_status_classes(self):
        status = {
            "apple_subtitle": {"status": "ok", "result_count": 3},
            "apple_similar": {"status": "unavailable",
                              "reason": "RuntimeError: browser timeout"},
            "apple_rss_charts": {"status": "ok", "result_count": 0},
        }
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            source_status=status,
        )
        self.assertIn("channel--ok", html)       # available source
        self.assertIn("channel--down", html)      # unavailable source
        self.assertIn("channel--empty", html)     # ran but 0 results


# ---------------------------------------------------------------------------
# Methodology / honesty
# ---------------------------------------------------------------------------

class MethodologyHonestyTests(unittest.TestCase):
    """Methodology/honesty section renders correctly in German."""

    def test_proxy_explanation_in_html(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Proxy", html)

    def test_en_without_en_market_caveat(self):
        html = report.build_report_html(
            _config(country="de", language="en"),
            _competitors(), _keywords(), now=NOW)
        self.assertIn("EN", html)
        self.assertIn("nicht US", html)

    def test_no_caveat_when_us_en(self):
        html = report.build_report_html(
            _config(country="us", language="en"),
            _competitors(), _keywords(), now=NOW)
        self.assertNotIn("nicht US", html)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class DeterminismTests(unittest.TestCase):
    """HTML output is deterministic for identical input."""

    def test_identical_input_produces_identical_html(self):
        a = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok(),
            brand_conflicts=_brand_conflicts(),
            source_status={"apple_subtitle": {"status": "ok", "result_count": 3}},
        )
        b = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok(),
            brand_conflicts=_brand_conflicts(),
            source_status={"apple_subtitle": {"status": "ok", "result_count": 3}},
        )
        self.assertEqual(a, b)

    def test_no_subagent_output_still_produces_valid_html(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("<html", html.lower())
        self.assertIn("Zusammenfassung", html)


# ---------------------------------------------------------------------------
# MS qualitative
# ---------------------------------------------------------------------------

class MSQualitativeTests(unittest.TestCase):
    """MS Store qualitative data renders in HTML."""

    def test_ms_entries_rendered_when_present_and_ok(self):
        ms_entries = [
            {"title": "Habit Tracker Pro", "platform": "ms",
             "developer": "MsDev", "category": "health_fitness",
             "rating_avg": 4.2, "rating_count": 200, "price_model": "free"},
        ]
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            ms_entries=ms_entries,
            source_status={"ms": {"status": "ok", "result_count": 1}},
        )
        self.assertIn("Microsoft Store", html)
        self.assertIn("Habit Tracker Pro", html)

    def test_ms_not_rendered_when_unavailable(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            source_status={"ms": {"status": "unavailable",
                                  "reason": "SPA not reachable"}},
        )
        self.assertIn("Microsoft Store", html)
        self.assertIn("nicht verfügbar", html)


# ---------------------------------------------------------------------------
# Full landscape
# ---------------------------------------------------------------------------

class FullLandscapeTests(unittest.TestCase):
    """All sections present with German headings."""

    def test_all_sections_present(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok(),
        )
        sections = [
            "Quellen-Signal",
            "Zusammenfassung",
            "Wettbewerbslandschaft",
            "Positionierungsmap",
            "Keyword-Bericht",
            "Chancen",
            "Risiken",
            "Listing-Empfehlung",
            "Methodik",
            "Glossar",
        ]
        for name in sections:
            with self.subTest(section=name):
                self.assertIn(name, html, f"missing section: {name}")


# ---------------------------------------------------------------------------
# Assemble step — report.html file output
# ---------------------------------------------------------------------------

class AssembleStepTests(unittest.TestCase):
    """AC: assemble step writes report.html to disk."""

    def test_assemble_writes_report_html_file(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok(),
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "report.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            self.assertTrue(os.path.isfile(path))
            self.assertGreater(os.path.getsize(path), 0)

    def test_assemble_html_contains_german(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok(),
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "report.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("Zusammenfassung", content)

    def test_assemble_html_contains_glossary(self):
        html = report.build_report_html(
            _config(), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok(),
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "report.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("Glossar", content)
            self.assertIn("Relevanz", content)


if __name__ == "__main__":
    unittest.main()
