#!/usr/bin/env python3
"""Tests for motion-video-planner/scripts/check_prompt.py.

The checker is the hand-over gate between planning and production. A false
pass sends a fresh agent a prompt with a timeline gap, a missing asset or a
leftover placeholder; a false fail blocks a good prompt. Both are silent in
the sense that nothing downstream re-checks the structure.

Run from the repo root:
    python3 tests/motion-video-planner/test_check_prompt.py
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "motion-video-planner" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import check_prompt as C  # noqa: E402

SCENE_FIELDS = """- Composition: ground #0b122a, note 280x280 px centered
- Assets: assets/logo.svg
- Action: the note slaps onto the monitor; the monitor wobbles
- Camera: static
- Motion/easing: note y -400 to 0, 0.3 s, expo.out
- Transition out: hard cut on the slap
- Audio cues: paper slap at +0.3 s
"""

VALID = f"""# Production brief: Sticky

> Timings are PLANNED.

## 0. Start here

Build it. Write Appendix A verbatim to BRIEF.md.

## 1. Goal and context

- Core message: notes stop getting lost.

## 2. Story

- Hook: a note falls.

## 3. Format

- Duration (planned): 6 s (tolerance ±1 s)
- Resolution / aspect: 1080x1920

## 4. Look

- Palette: ground `#0b122a`, accent `#ffd84d`

## 5. Timeline

All times are PLANNED.

| # | Start | End | Purpose | Voiceover (exact) | On-screen text (exact) |
|---|---|---|---|---|---|
| 1 | 0.0 | 2.5 | hook | — | "Wo war der Zettel?" |
| 2 | 2.5 | 6.0 | close | "Nie wieder suchen." | "Sticky" |

### Scene 1 (0.0–2.5 s): fall
{SCENE_FIELDS}
### Scene 2 (2.5–6.0 s): close
{SCENE_FIELDS}
## 6. Audio

- Voiceover: yes

## 7. Assets

| Path | Status | Use | Notes |
|---|---|---|---|
| `assets/logo.svg` | exists | close | light variant |
| `code: note` | create | hero | 280x280 px #ffd84d |

## 8. Technical execution

- Workflow: `/general-video`, because it is narrated.

## 9. Quality and delivery

- lint and check with zero errors.

## Appendix A: BRIEF.md

```markdown
---
workflow: general-video
flow: automation
storyboard: no
message: "Notes stop getting lost"
narration: yes
---

## Intent

Confirmed.
```

## Appendix B: Sources

| # | Claim or fact used in the video | Evidence |
|---|---|---|
| 1 | syncs notes | `src/sync.ts:12` |

## Appendix C: frame.md

```markdown
---
name: Sticky
colors:
  ground: "#0b122a"
typography:
  display: {{ fontFamily: "Inter", px: 140, weight: 800 }}
---

## Overview
Flat.
```
"""


class CheckPromptTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="chk-test-")
        os.makedirs(os.path.join(self.root, "assets"))
        with open(os.path.join(self.root, "assets", "logo.svg"), "w") as fh:
            fh.write("<svg/>")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_check(self, text, root=True):
        return C.check(text, self.root if root else None)

    def assertHasError(self, rep, fragment):
        self.assertTrue(any(fragment in e for e in rep.errors),
                        f"expected an error containing {fragment!r}, got {rep.errors}")

    def test_valid_prompt_passes(self):
        rep = self.run_check(VALID)
        self.assertEqual(rep.errors, [])

    def test_headings_inside_code_fences_are_not_sections(self):
        sections, order = C.split_sections(VALID)
        self.assertNotIn("Intent", sections)
        self.assertNotIn("Overview", sections)
        self.assertEqual(order[-1], "Appendix C: frame.md")

    def test_leftover_template_slot(self):
        self.assertHasError(self.run_check(VALID.replace("hook | —", "hook | «vo»")), "unfilled template slot")

    def test_tbd_marker(self):
        self.assertHasError(self.run_check(VALID.replace("Flat.", "Flat. TBD")), "placeholder marker")

    def test_reference_to_planning_chat(self):
        rep = self.run_check(VALID.replace("Build it.", "Build it wie besprochen."))
        self.assertHasError(rep, "planning chat")

    def test_missing_section(self):
        rep = self.run_check(VALID.replace("## 6. Audio", "## 6. Sound"))
        self.assertHasError(rep, "missing section '## 6. Audio'")

    def test_timeline_gap(self):
        rep = self.run_check(VALID.replace("| 2 | 2.5 | 6.0 |", "| 2 | 3.0 | 6.0 |"))
        self.assertHasError(rep, "gap of 0.50 s")

    def test_timeline_overlap(self):
        rep = self.run_check(VALID.replace("| 2 | 2.5 | 6.0 |", "| 2 | 2.0 | 6.0 |"))
        self.assertHasError(rep, "overlap")

    def test_timeline_must_match_duration(self):
        rep = self.run_check(VALID.replace("Duration (planned): 6 s", "Duration (planned): 8 s"))
        self.assertHasError(rep, "timeline ends at 6.0 s but planned duration is 8.0 s")

    def test_minute_second_times_are_parsed(self):
        text = VALID.replace("| 1 | 0.0 | 2.5 |", "| 1 | 0:00 | 0:02.5 |").replace(
            "| 2 | 2.5 | 6.0 |", "| 2 | 0:02.5 | 0:06 |")
        self.assertEqual(self.run_check(text).errors, [])

    def test_planned_marker_required(self):
        text = VALID.replace("All times are PLANNED.", "Times below.")
        rep = self.run_check(text)
        self.assertHasError(rep, "PLANNED")

    def test_missing_scene_field(self):
        text = VALID.replace("- Camera: static\n", "", 1)
        self.assertHasError(self.run_check(text), "scene 1: missing field 'Camera:'")

    def test_missing_scene_block(self):
        text = VALID.replace("### Scene 2 (2.5–6.0 s): close", "### Szene zwei")
        self.assertHasError(self.run_check(text), "no '### Scene 2' detail block")

    def test_exists_asset_must_exist(self):
        os.remove(os.path.join(self.root, "assets", "logo.svg"))
        self.assertHasError(self.run_check(VALID), "marked 'exists' but not found")

    def test_exists_asset_unchecked_without_root_is_warning(self):
        rep = self.run_check(VALID, root=False)
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("existence not checked" in w for w in rep.warnings))

    def test_unknown_asset_status(self):
        text = VALID.replace("| exists | close |", "| maybe | close |")
        self.assertHasError(self.run_check(text), "status 'maybe'")

    def test_user_asset_missing_is_warning(self):
        text = VALID.replace("| `code: note` | create |", "| `assets/screen.mp4` | user |")
        rep = self.run_check(text)
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("supplied by the user" in w for w in rep.warnings))
        with open(os.path.join(self.root, "assets", "screen.mp4"), "w") as fh:
            fh.write("x")
        rep = self.run_check(text)
        self.assertFalse(any("supplied by the user" in w for w in rep.warnings))

    def test_as_above_inside_the_prompt_is_allowed(self):
        rep = self.run_check(VALID.replace("Flat.", "Flat. Same palette as above."))
        self.assertEqual(rep.errors, [])

    def test_generate_requires_budget_line(self):
        text = VALID.replace("| create | hero |", "| generate | hero |")
        self.assertHasError(self.run_check(text), "Budget for paid generation")
        text += "\n"  # budget line added to section 7 makes it pass
        text = text.replace("## 8. Technical execution",
                            "- Budget for paid generation: up to 5 EUR for one image\n\n## 8. Technical execution")
        self.assertEqual(self.run_check(text).errors, [])

    def test_motion_graphics_rejects_narration(self):
        text = VALID.replace("workflow: general-video", "workflow: motion-graphics").replace(
            "`/general-video`", "`/motion-graphics`")
        self.assertHasError(self.run_check(text), "motion-graphics does not take narration")

    def test_workflow_must_be_named_in_section_8(self):
        text = VALID.replace("`/general-video`, because", "`/faceless-explainer`, because")
        self.assertHasError(self.run_check(text), "does not name the workflow '/general-video'")

    def test_unknown_workflow(self):
        text = VALID.replace("workflow: general-video", "workflow: promo-maker")
        self.assertHasError(self.run_check(text), "not a known HyperFrames route")

    def test_look_needs_hex(self):
        text = VALID.replace("ground `#0b122a`, accent `#ffd84d`", "dark ground, yellow accent")
        self.assertHasError(self.run_check(text), "section 4 names no exact hex color")

    def test_source_row_needs_evidence(self):
        text = VALID.replace("| 1 | syncs notes | `src/sync.ts:12` |", "| 1 | syncs notes |  |")
        self.assertHasError(self.run_check(text), "row without evidence")

    def test_reading_speed_warning(self):
        text = VALID.replace('"Wo war der Zettel?"', '"' + " ".join(["Wort"] * 12) + '"')
        rep = self.run_check(text)
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("too fast to read" in w for w in rep.warnings))

    def test_cli_exit_codes(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        good = os.path.join(self.root, "good.md")
        bad = os.path.join(self.root, "bad.md")
        with open(good, "w") as fh:
            fh.write(VALID)
        with open(bad, "w") as fh:
            fh.write(VALID.replace("## 2. Story", "## 2. Plot"))
        script = str(SCRIPTS_DIR / "check_prompt.py")
        r = subprocess.run([sys.executable, script, good, "--assets-root", self.root],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout)
        r = subprocess.run([sys.executable, script, bad, "--assets-root", self.root],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing section '## 2. Story'", r.stdout)
        r = subprocess.run([sys.executable, script, os.path.join(self.root, "nope.md")],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
