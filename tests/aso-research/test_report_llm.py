#!/usr/bin/env python3
"""Tests for the full 8-section report assembly (slice 03) — report.py.

Run from the repo root:
    python3 tests/aso-research/test_report_llm.py

Covers: all 8 canonical sections present (AC6); §8 Methodology explicit
about proxies + unavailable sources (AC6); §7 Listing Recommendation
renders 1+2 per Apple slot with char counts (AC4); §3/§5/§6 render from
the S1/S2/H2 subagent-output schema (AC3); Modus A self-audit present vs
Modus B absent — no separate code path (AC7); backward-compatible default
(all sections render with deterministic fallbacks when no subagent output).
"""

import datetime
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import report  # noqa: E402


def _config(*, own_app_id=None):
    return {
        "app_name": "Habit Hero",
        "description": "A gamified habit tracker app",
        "category": "health_fitness",
        "country": "de",
        "language": "de",
        "own_app_id": own_app_id,
        "seed_keywords": ["habit", "tracker"],
    }


def _competitors():
    return [
        {"id": "1", "title": "Habit Tracker", "developer": "DevA", "category": "health_fitness",
         "rating_avg": 4.5, "rating_count": 1000, "price_model": "free",
         "subtitle": "Daily Routine", "discovery": "chart/search"},
        {"id": "2", "title": "Streak Buddy", "developer": "DevB", "category": "health_fitness",
         "rating_avg": 4.7, "rating_count": 500, "price_model": "paid",
         "subtitle": "", "discovery": "niche_similar"},
    ]


def _keywords():
    return [
        {"term": "habit", "competition": 20, "relevance": 80, "opportunity": 64,
         "split": "primary-candidate", "is_gap": False, "suggest": True},
        {"term": "tracker", "competition": 40, "relevance": 70, "opportunity": 42,
         "split": "primary-candidate", "is_gap": False, "suggest": False},
        {"term": "routine", "competition": 10, "relevance": 60, "opportunity": 54,
         "split": "primary-candidate", "is_gap": True, "suggest": False},
    ]


def _s1():
    return {
        "niches": ["gamified habits", "streak motivation"],
        "dominant_themes": ["routine building", "daily reminders"],
        "leader_positioning": ["Spotify-style gamification"],
        "audiences": ["students", "professionals"],
        "missing_themes": ["accountability partners"],
        "threats": ["Apple's native Reminders integration"],
    }


def _s2():
    title = "Habit Hero Tracker"
    subtitle = "Build Daily Routines"
    kw = "habit,tracker,routine,streak"
    return {
        "store": "apple",
        "slots": [
            {"slot": "title", "recommended": {"text": title, "char_count": len(title)},
             "alternatives": [{"text": "Habit Hero", "char_count": 10}, {"text": "Daily Habit", "char_count": 10}]},
            {"slot": "subtitle", "recommended": {"text": subtitle, "char_count": len(subtitle)},
             "alternatives": [{"text": "Routine Builder", "char_count": 14}, {"text": "Streak & Habit", "char_count": 14}]},
            {"slot": "keyword_field", "recommended": {"text": kw, "char_count": len(kw)},
             "alternatives": [{"text": "habit,routine,daily", "char_count": 19}, {"text": "tracker,streak", "char_count": 14}]},
        ],
    }


def _h2_ok():
    return {"status": "ok", "findings": [], "note": "every keyword evidence-conform."}


NOW = datetime.datetime(2026, 6, 26, 12, 0, 0)


class EightSectionAssemblyTests(unittest.TestCase):
    def test_all_eight_canonical_sections_present(self):
        body = report.build_report(
            _config(), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok(),
        )
        for i, name in enumerate(
            ["Executive Summary", "Competitive Landscape", "Positioning Map",
             "Keyword Report", "Opportunities", "Risks / Threats",
             "Listing Recommendation", "Methodology"],
            start=1,
        ):
            self.assertIn(f"## {i}. {name}", body, msg=f"missing section {i}: {name}")

    def test_sections_present_even_without_subagent_output(self):
        """Backward-compat: a default report still has all 8 sections."""
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW)
        for i in range(1, 9):
            self.assertIn(f"## {i}. ", body)

    def test_body_stable_for_identical_input(self):
        a = report.build_report(_config(), _competitors(), _keywords(), now=NOW,
                                s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok())
        b = report.build_report(_config(), _competitors(), _keywords(), now=NOW,
                                s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok())
        self.assertEqual(a, b)


class MethodologyTests(unittest.TestCase):
    def test_explicit_about_proxies(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("proxy", body.lower())
        self.assertIn("not real search volume", body.lower())

    def test_lists_sources_ran_and_unavailable(self):
        status = {
            "apple_subtitle": "ok", "apple_similar": "ok", "apple_rss_charts": "ok",
            "apple_search_suggest": "ok", "ms": "unavailable",
        }
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW,
                                   source_status=status)
        self.assertIn("**Sources that ran:**", body)
        self.assertIn("apple_subtitle", body)
        self.assertIn("ms", body)
        self.assertIn("unavailable", body.lower())


class ListingRecommendationTests(unittest.TestCase):
    def test_renders_one_recommended_plus_two_alternatives_with_char_counts(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW,
                                   s2_output=_s2(), h2_output=_h2_ok())
        self.assertIn("(recommended)", body)
        self.assertIn("alt 1", body)
        self.assertIn("alt 2", body)
        self.assertIn("chars", body)
        self.assertIn("H2 cross-check", body)

    def test_listing_char_counts_accurate(self):
        listing = _s2()
        for slot in listing["slots"]:
            rec = slot["recommended"]
            self.assertEqual(rec["char_count"], len(rec["text"]))
            self.assertLessEqual(len(rec["text"]), 30 if slot["slot"] != "keyword_field" else 100)
            self.assertEqual(len(slot["alternatives"]), 2)


class PlayListingReportTests(unittest.TestCase):
    """Slice 04: the report carries a Play-specific listing (1+2 per Play slot)."""

    def _play_s2(self):
        title = "Habit Hero Tracker"
        short = "Build daily habits & routines that stick"
        long_text = "Habit Hero is the best habit tracker. Build streaks and routines."
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

    def _play_competitors(self):
        return [
            {"id": "com.a", "platform": "play", "title": "Habit Hero", "developer": "DevA",
             "category": "health_fitness", "rating_avg": 4.5, "rating_count": 1000,
             "price_model": "free", "discovery": "chart/search"},
        ]

    def test_play_listing_section_renders_when_play_present(self):
        body = report.build_report(
            _config(), self._play_competitors(), _keywords(), now=NOW,
            s2_output=_s2(), h2_output=_h2_ok(),
            s2_play_output=self._play_s2(),
            h2_play_output=_h2_ok(),
        )
        self.assertIn("### Google Play", body)
        # Play slot names + limits documented in the section
        self.assertIn("Title 30 / Short 80 / Long 4000", body)
        # 1 recommended + 2 alts per Play slot rendered with char counts
        self.assertIn("(recommended)", body)
        self.assertIn("alt 1", body)
        self.assertIn("H2 cross-check (Google Play)", body)

    def test_no_play_section_when_play_absent(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW)
        self.assertNotIn("### Google Play", body)
        self.assertIn("### Apple", body)


class ModusTests(unittest.TestCase):
    def test_modus_b_has_no_self_audit_section(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW)
        self.assertNotIn("Self-audit", body)
        self.assertIn("Mode:** B", body)

    def test_modus_a_renders_self_audit_block(self):
        body = report.build_report(
            _config(own_app_id="1"), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(), s2_output=_s2(), h2_output=_h2_ok(),
        )
        self.assertIn("Self-audit (Modus A)", body)
        self.assertIn("Mode:** A", body)

    def test_modus_a_self_audit_renders_s1_audit_content(self):
        s1 = _s1()
        s1["own_app_audit"] = ["own subtitle is generic", "missing 'streak' keyword"]
        body = report.build_report(
            _config(own_app_id="1"), _competitors(), _keywords(), now=NOW,
            s1_output=s1, s2_output=_s2(), h2_output=_h2_ok(),
        )
        self.assertIn("own subtitle is generic", body)


class LlmDrivenSectionTests(unittest.TestCase):
    def test_positioning_map_renders_s1_themes(self):
        body = report.build_report(
            _config(), _competitors(), _keywords(), now=NOW,
            s1_output=_s1(),
        )
        self.assertIn("Dominant themes", body)
        self.assertIn("routine building", body)

    def test_opportunities_renders_buckets_and_missing_themes(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW, s1_output=_s1())
        self.assertIn("Quick wins", body)
        self.assertIn("Niche levers", body)
        self.assertIn("Coverage gaps", body)
        self.assertIn("Missing themes (S1)", body)
        self.assertIn("routine", body)  # routine is a niche lever + quick win

    def test_risks_renders_s1_threats(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW, s1_output=_s1())
        self.assertIn("Apple's native Reminders integration", body)

    def test_opportunities_renders_validation_candidates_and_asa_note(self):
        kws = _keywords() + [
            {"term": "checklist", "competition": 35, "relevance": 55, "opportunity": 30,
             "split": "primary-candidate", "is_gap": False, "suggest": False},
        ]
        body = report.build_report(_config(), _competitors(), kws, now=NOW)
        self.assertIn("Validation candidates", body)
        self.assertIn("checklist", body)
        self.assertIn("Apple Search Ads Basic", body)

    def test_no_asa_note_without_validation_candidates(self):
        """Habit/tracker/routine all clear the Quick-Win bar (opp >= 40) — no validation bucket."""
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Validation candidates", body)  # label always renders
        self.assertNotIn("Apple Search Ads Basic", body)  # note only when non-empty


class FeaturingNominationTests(unittest.TestCase):
    def test_apple_listing_section_includes_featuring_reminder(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Featuring Nomination", body)
        self.assertIn("New Content / App Enhancements / App Launch", body)
        self.assertIn("3 weeks", body)


class ScreenshotCopyTests(unittest.TestCase):
    def _s2_with_screenshots(self):
        s2 = _s2()
        s2["screenshot_copy"] = [
            {"headline": "Build habits that stick", "subtext": "Track any routine in seconds"},
            {"headline": "Streaks that motivate", "subtext": "See your progress every day"},
            {"headline": "Gamified, not gimmicky", "subtext": "Rewards for real consistency"},
        ]
        return s2

    def test_renders_screenshot_copy_when_present(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW,
                                   s2_output=self._s2_with_screenshots(), h2_output=_h2_ok())
        self.assertIn("Screenshot copy", body)
        self.assertIn("Build habits that stick", body)
        self.assertIn("Streaks that motivate", body)

    def test_pending_note_when_s2_present_without_screenshot_copy(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW,
                                   s2_output=_s2(), h2_output=_h2_ok())
        self.assertIn("Screenshot copy pending", body)

    def test_no_screenshot_section_when_s2_entirely_absent(self):
        """No s2_output at all -> the listing-pending message already covers it; no duplicate note."""
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW)
        self.assertNotIn("Screenshot copy pending", body)


class HeuristicScaleClarificationTests(unittest.TestCase):
    def test_methodology_clarifies_proxy_scale_vs_paid_tool_heuristics(self):
        body = report.build_report(_config(), _competitors(), _keywords(), now=NOW)
        self.assertIn("Not the same scale as paid-tool heuristics", body)
        self.assertIn("Popularity > 40", body)


if __name__ == "__main__":
    unittest.main()
