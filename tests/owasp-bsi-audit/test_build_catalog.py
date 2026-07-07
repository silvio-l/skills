#!/usr/bin/env python3
"""Tests for owasp-bsi-audit/scripts/build_catalog.py.

Covers the pure parsing/classification functions only - no network calls.
Each build_* function fetches from a live upstream URL and then hands off
to a pure parse_*() function; these tests feed synthetic payloads/XML
snippets directly into the parse_*() functions so a regex or parsing bug
produces a loud test failure instead of silently wrong catalog content.

Run from the repo root:
    python3 tests/owasp-bsi-audit/test_build_catalog.py
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "owasp-bsi-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import build_catalog as C  # noqa: E402


class ClassifyCheckTypeTests(unittest.TestCase):
    def test_manual_keyword_wins(self):
        text = "Der Serverraum MUSS klimatisiert werden und Zutritt kontrolliert werden."
        self.assertEqual(C.classify_check_type(text), "manual")

    def test_process_keyword(self):
        text = "Es SOLLTE eine Richtlinie für die Software-Entwicklung erstellt werden."
        self.assertEqual(C.classify_check_type(text), "process")

    def test_config_keyword(self):
        text = "TLS MUSS für die Verschlüsselung der Verbindung konfiguriert werden."
        self.assertEqual(C.classify_check_type(text), "config")

    def test_default_is_code(self):
        text = "Eingaben MÜSSEN vor der Verarbeitung validiert werden."
        self.assertEqual(C.classify_check_type(text), "code")

    def test_manual_takes_priority_over_config(self):
        # contains both a manual keyword (serverraum) and a config keyword
        # (konfigur) - manual must win per the documented priority order.
        text = "Der Serverraum MUSS ordnungsgemäß konfiguriert werden."
        self.assertEqual(C.classify_check_type(text), "manual")


class PickLatestSemverTagTests(unittest.TestCase):
    def test_picks_highest_version(self):
        releases = [
            {"tag_name": "v4.0.3_release"},
            {"tag_name": "v5.0.0_release"},
            {"tag_name": "v4.0.1_release"},
            {"tag_name": "latest"},  # does not match the pattern, ignored
        ]
        result = C.pick_latest_semver_tag(releases, C.ASVS_RELEASE_TAG_RE)
        self.assertEqual(result, ((5, 0, 0), "v5.0.0_release"))

    def test_no_match_returns_none(self):
        releases = [{"tag_name": "latest"}, {"tag_name": "v1.0-rc1"}]
        result = C.pick_latest_semver_tag(releases, C.ASVS_RELEASE_TAG_RE)
        self.assertIsNone(result)

    def test_masvs_pattern_tolerates_missing_v_prefix(self):
        releases = [{"tag_name": "2.1.0"}, {"tag_name": "v2.0.0"}]
        result = C.pick_latest_semver_tag(releases, C.MASVS_RELEASE_TAG_RE)
        self.assertEqual(result[0], (2, 1, 0))


class ParseAsvsRequirementsTests(unittest.TestCase):
    def test_filters_to_l1_l2_and_groups_by_chapter(self):
        payload = {
            "requirements": [
                {"chapter_id": "V1", "chapter_name": "Encoding", "section_id": "V1.1",
                 "section_name": "Arch", "req_id": "V1.1.1", "req_description": "desc a", "L": "2"},
                {"chapter_id": "V1", "chapter_name": "Encoding", "section_id": "V1.2",
                 "section_name": "Inj", "req_id": "V1.2.1", "req_description": "desc b", "L": "1"},
                {"chapter_id": "V7", "chapter_name": "Auth", "section_id": "V7.1",
                 "section_name": "Docs", "req_id": "V7.1.1", "req_description": "desc c", "L": "3"},
            ]
        }
        groups = C.parse_asvs_requirements(payload)
        chapter_ids = [g["chapter_id"] for g in groups]
        self.assertEqual(chapter_ids, ["V1"])  # V7 dropped: only an L3 requirement
        reqs = groups[0]["requirements"]
        self.assertEqual({r["req_id"] for r in reqs}, {"V1.1.1", "V1.2.1"})
        self.assertEqual(reqs[0]["level"], "L2")

    def test_accepts_bare_list_payload(self):
        payload = [{"chapter_id": "V2", "chapter_name": "Validation", "section_id": "V2.1",
                    "section_name": "X", "req_id": "V2.1.1", "req_description": "d", "L": "1"}]
        groups = C.parse_asvs_requirements(payload)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["requirements"][0]["req_id"], "V2.1.1")


class ParseMasvsYamlTests(unittest.TestCase):
    def test_extracts_controls_and_groups_by_prefix(self):
        raw = """
metadata:
  version: vx.x.x
groups:
- id: MASVS-STORAGE
  controls:
  - id: MASVS-STORAGE-1
    statement: The app securely stores sensitive data.
    description: some longer text here.
  - id: MASVS-STORAGE-2
    statement: The app prevents leakage of sensitive data.
    description: more text.
- id: MASVS-AUTH
  controls:
  - id: MASVS-AUTH-1
    statement: The app uses secure auth.
    description: text.
"""
        groups = C.parse_masvs_yaml(raw)
        group_codes = [g["masvs_group"] for g in groups]
        self.assertEqual(group_codes, ["MASVS-AUTH", "MASVS-STORAGE"])  # sorted
        storage = next(g for g in groups if g["masvs_group"] == "MASVS-STORAGE")
        self.assertEqual(len(storage["controls"]), 2)
        self.assertEqual(storage["controls"][0]["id"], "MASVS-STORAGE-1")

    def test_normalizes_multiline_statement_folding(self):
        raw = """
groups:
- id: MASVS-CODE
  controls:
  - id: MASVS-CODE-1
    statement: This statement
      wraps across
      multiple lines.
    description: x
"""
        groups = C.parse_masvs_yaml(raw)
        statement = groups[0]["controls"][0]["statement"]
        self.assertNotIn("\n", statement)
        self.assertEqual(statement, "This statement wraps across multiple lines.")


class ParseBsiXmlTests(unittest.TestCase):
    """Feeds a small synthetic DocBook snippet mirroring the real BSI
    Kompendium's structure (see the CON.8 excerpt reviewed during catalog
    design) rather than the full ~3MB document."""

    def _snippet(self, requirements_xml):
        return f"""
<section xml:id="s1">
<title>CON.10 Entwicklung von Webanwendungen</title>
<section xml:id="s2">
<title>Anforderungen</title>
<section xml:id="s3">
<title>Basis-Anforderungen</title>
{requirements_xml}
</section>
</section>
</section>
"""

    def test_extracts_basis_and_standard_skips_hoch_and_entfallen(self):
        xml = self._snippet("""
<section xml:id="r1">
<title>CON.10.A1 Authentisierung bei Webanwendungen (B)</title>
<para>Text zur Anforderung A1.</para>
</section>
<section xml:id="r2">
<title>CON.10.A2 ENTFALLEN (B)</title>
</section>
<section xml:id="r3">
<title>CON.10.A3 Sicheres Session-Management (S)</title>
<para>Text zur Anforderung A3.</para>
</section>
<section xml:id="r4">
<title>CON.10.A4 Anforderung bei erhöhtem Schutzbedarf (H)</title>
<para>Sollte nicht auftauchen.</para>
</section>
</section>
""")
        bausteine = C.parse_bsi_xml(xml)
        con10 = bausteine["CON.10"]
        req_ids = {r["req_id"] for r in con10["requirements"]}
        self.assertEqual(req_ids, {"CON.10.A1", "CON.10.A3"})  # A2 ENTFALLEN, A4 Hoch dropped
        levels = {r["req_id"]: r["level"] for r in con10["requirements"]}
        self.assertEqual(levels["CON.10.A1"], "Basis")
        self.assertEqual(levels["CON.10.A3"], "Standard")

    def test_strips_role_annotation_from_title(self):
        xml = self._snippet("""
<section xml:id="r1">
<title>CON.10.A5 Upload-Funktionen (B) [Entwickelnde]</title>
<para>Text.</para>
</section>
""")
        bausteine = C.parse_bsi_xml(xml)
        req = bausteine["CON.10"]["requirements"][0]
        self.assertEqual(req["title"], "Upload-Funktionen")

    def test_body_text_is_flattened_and_whitespace_normalized(self):
        xml = self._snippet("""
<section xml:id="r1">
<title>CON.10.A1 Authentisierung bei Webanwendungen (B)</title>
<para>Erste   Zeile.</para>
<para>Zweite Zeile.</para>
</section>
""")
        bausteine = C.parse_bsi_xml(xml)
        desc = bausteine["CON.10"]["requirements"][0]["description"]
        self.assertNotIn("<para>", desc)
        self.assertNotIn("  ", desc)  # no double spaces left over

    def test_unrelated_baustein_prefix_is_not_matched(self):
        # A hypothetical "APP.3.10.A1" must not be picked up as CON.10 or
        # APP.3.1 despite the shared string prefix.
        xml = """
<section xml:id="s1">
<title>Basis-Anforderungen</title>
<section xml:id="r1">
<title>APP.3.10.A1 Irrelevant (B)</title>
<para>Text.</para>
</section>
</section>
"""
        bausteine = C.parse_bsi_xml(xml)
        all_reqs = [r for b in bausteine.values() for r in b["requirements"]]
        self.assertEqual(all_reqs, [])


class ParseSsdfPayloadTests(unittest.TestCase):
    def test_filters_to_selected_ids_and_groups_by_parent_practice(self):
        payload = {
            "definitions": {
                "standards": [{
                    "version": "1.1",
                    "requirements": [
                        {"identifier": "PO.1.1", "text": "not selected, should be dropped"},
                        {"identifier": "PW.6.1", "text": "Use compiler security features."},
                        {"identifier": "PW.6.2", "text": "Configure those features."},
                        {"identifier": "RV.1.3", "text": "Have a disclosure policy."},
                    ],
                }]
            }
        }
        version, groups = C.parse_ssdf_payload(payload)
        self.assertEqual(version, "1.1")
        group_ids = {g["practice_group"] for g in groups}
        self.assertEqual(group_ids, {"PW.6", "RV.1"})
        pw6 = next(g for g in groups if g["practice_group"] == "PW.6")
        self.assertEqual({r["req_id"] for r in pw6["requirements"]}, {"PW.6.1", "PW.6.2"})
        # PO.1.1 must not appear anywhere - it isn't in SSDF_SELECTED_IDS
        all_ids = {r["req_id"] for g in groups for r in g["requirements"]}
        self.assertNotIn("PO.1.1", all_ids)


if __name__ == "__main__":
    unittest.main()
