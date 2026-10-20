#!/usr/bin/env python3
"""Structural checks for the motion-video-planner skill bundle.

A dangling reference link or an unlinked reference file fails silently: the
agent simply never loads the file. The description cap and the name rule are
enforced by the skills CLI only at install time.

Run from the repo root:
    python3 tests/motion-video-planner/test_skill_structure.py
"""

import pathlib
import re
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "motion-video-planner"
SKILL_MD = SKILL_DIR / "SKILL.md"
TEMPLATE = SKILL_DIR / "references" / "production-prompt-template.md"

# Lower-case .md names the references mention that are not bundled: files of
# the plan directory or the produced project, and HyperFrames' own references.
PLAN_AND_EXTERNAL_FILES = {
    "context.md", "decisions.md", "concepts.md", "production-prompt.md", "frame.md",
    "design.md", "brief-format.md", "brief-contract.md", "intent-interview.md",
    "review-loop.md", "production-loop.md", "cloud.md", "init-and-scaffold.md",
    "design-spec.md",
}


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([a-z][a-z0-9_-]*):\s*(.*)$", line)
        if km:
            fields[km.group(1)] = km.group(2).strip()
            raw = fields[km.group(1)]
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
                fields[km.group(1)] = raw[1:-1]
    return fields


class SkillStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL_MD.read_text(encoding="utf-8")
        cls.fm = frontmatter(cls.text)

    def test_name_matches_directory(self):
        self.assertEqual(self.fm.get("name"), SKILL_DIR.name)

    def test_frontmatter_plain_scalars_are_valid_yaml(self):
        # The skills CLI skips a skill whose frontmatter fails to parse; an
        # unquoted ": " or " #" inside a plain scalar is the usual cause.
        block = re.match(r"^---\n(.*?)\n---\n", self.text, re.S).group(1)
        for line in block.splitlines():
            km = re.match(r"^\s*[a-z][a-z0-9_-]*:\s*(.*)$", line)
            if not km or not km.group(1) or km.group(1)[0] in "\"'":
                continue
            self.assertNotIn(": ", km.group(1), f"unquoted ': ' in: {line}")
            self.assertNotIn(" #", km.group(1), f"unquoted ' #' in: {line}")

    def test_description_within_cap(self):
        desc = self.fm.get("description", "")
        self.assertTrue(desc, "description missing")
        self.assertLessEqual(len(desc), 250)
        self.assertGreaterEqual(len(desc), 120, "too short to route reliably")

    def test_description_has_german_and_english_triggers(self):
        desc = self.fm.get("description", "")
        for phrase in ("video concept", "Video planen", "Videokonzept"):
            self.assertIn(phrase, desc)

    def test_skill_md_under_500_lines(self):
        self.assertLess(len(self.text.splitlines()), 500)

    def test_every_link_resolves(self):
        for target in re.findall(r"\]\(([^)#]+)\)", self.text):
            if "://" in target:
                continue
            self.assertTrue((SKILL_DIR / target).is_file(), f"dangling link: {target}")

    def test_every_reference_and_script_is_mentioned(self):
        bundled = [p for p in SKILL_DIR.rglob("*") if p.is_file() and p.suffix in (".md", ".py")
                   and p != SKILL_MD and "__pycache__" not in p.parts]
        for path in bundled:
            rel = path.relative_to(SKILL_DIR).as_posix()
            self.assertIn(rel, self.text, f"{rel} is never referenced from SKILL.md")

    def test_no_stray_files_in_bundle(self):
        for path in SKILL_DIR.rglob("*"):
            if path.is_file():
                self.assertIn(path.suffix, (".md", ".py"), f"unexpected file in bundle: {path}")

    def test_cross_references_between_references_exist(self):
        refs = SKILL_DIR / "references"
        names = {p.name for p in refs.glob("*.md")}
        for path in refs.glob("*.md"):
            for name in re.findall(r"`([a-z0-9-]+\.md)`", path.read_text(encoding="utf-8")):
                if name in PLAN_AND_EXTERNAL_FILES:
                    continue
                self.assertIn(name, names, f"{path.name} mentions missing {name}")

    def test_template_sections_match_checker(self):
        sys.path.insert(0, str(SKILL_DIR / "scripts"))
        import check_prompt
        template = TEMPLATE.read_text(encoding="utf-8")
        for section in check_prompt.REQUIRED_SECTIONS:
            self.assertIn(f"\n## {section}\n", template, f"template lacks '## {section}'")
        for field in check_prompt.SCENE_FIELDS:
            self.assertIn(f"- {field}:", template, f"template lacks scene field {field}")

    def test_style_kit_has_21_styles(self):
        kit = (SKILL_DIR / "references" / "style-kit.md").read_text(encoding="utf-8")
        styles = [h for h in re.findall(r"^## (.+)$", kit, re.M) if h != "How to use a style"
                  and not h.lower().startswith("combin")]
        self.assertEqual(len(styles), 21, styles)


if __name__ == "__main__":
    unittest.main(verbosity=1)
