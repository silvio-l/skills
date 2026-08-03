#!/usr/bin/env python3
"""Tests for brainstorming/scripts/draw.

Run from the repo root with `python3 tests/brainstorming/test_draw.py`.

Covers what a silent bug in the draw script would look like: duplicate
cards inside one draw, duplicate triples across a collision draw, a seed
that fails to reproduce, or a category mismatch that gets accepted
instead of rejected. A malformed draw looks exactly like a valid one to
the agent using it, so it must be caught here instead. See CLAUDE.md ->
"Tooling and testing".
"""

import json
import os
import pathlib
import subprocess
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "brainstorming" / "scripts" / "draw"
DECK_PATH = REPO_ROOT / "skills" / "brainstorming" / "deck.json"

sys.dont_write_bytecode = True


def run(args):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env,
    )


def cards(result):
    return [line for line in result.stdout.splitlines() if line.strip()]


class Deck(unittest.TestCase):
    def test_deck_is_valid_json_with_expected_categories(self):
        with open(DECK_PATH, encoding="utf-8") as f:
            deck = json.load(f)
        self.assertEqual(set(deck.keys()), {"lenses", "collision_units", "provocations"})
        for category, pool in deck.items():
            self.assertGreater(len(pool), 10, f"{category} pool too small")
            self.assertEqual(len(pool), len(set(pool)), f"{category} has duplicate entries")


class SingleDraw(unittest.TestCase):
    def test_no_duplicate_cards_within_one_draw(self):
        r = run(["--category", "lenses", "--count", "12", "--seed", "1"])
        self.assertEqual(r.returncode, 0)
        drawn = cards(r)
        self.assertEqual(len(drawn), 12)
        self.assertEqual(len(drawn), len(set(drawn)))

    def test_same_seed_reproduces_the_same_draw(self):
        r1 = run(["--category", "provocations", "--count", "3", "--seed", "20260803"])
        r2 = run(["--category", "provocations", "--count", "3", "--seed", "20260803"])
        self.assertEqual(cards(r1), cards(r2))

    def test_different_seeds_diverge(self):
        r1 = run(["--category", "lenses", "--count", "5", "--seed", "1"])
        r2 = run(["--category", "lenses", "--count", "5", "--seed", "2"])
        self.assertNotEqual(cards(r1), cards(r2))

    def test_omitted_seed_still_prints_a_seed_for_reproduction(self):
        r = run(["--category", "lenses", "--count", "1"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("seed:", r.stderr)

    def test_count_larger_than_pool_errors(self):
        r = run(["--category", "provocations", "--count", "9999", "--seed", "1"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("error", r.stderr)


class CollisionDraw(unittest.TestCase):
    def test_triples_have_three_distinct_units_each(self):
        r = run(["--category", "collision_units", "--collide", "--count", "10", "--seed", "7"])
        self.assertEqual(r.returncode, 0)
        for line in cards(r):
            units = line.split(" + ")
            self.assertEqual(len(units), 3)
            self.assertEqual(len(units), len(set(units)))

    def test_no_duplicate_triples_across_one_draw(self):
        r = run(["--category", "collision_units", "--collide", "--count", "20", "--seed", "7"])
        self.assertEqual(r.returncode, 0)
        triples = [tuple(sorted(line.split(" + "))) for line in cards(r)]
        self.assertEqual(len(triples), 20)
        self.assertEqual(len(triples), len(set(triples)))

    def test_collide_rejected_for_non_collision_category(self):
        r = run(["--category", "lenses", "--collide", "--count", "1"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--collide only works", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
