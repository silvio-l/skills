"""Unit tests for the pure-logic parts of mail-deliverability-audit's
dispatcher: SPF parsing/lookup-counting and Netcup known-good comparison.
These are the parts that can fail silently (a wrong verdict, not a crash).

Run: python3 tests/mail-deliverability-audit/test_audit.py
"""

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "skills" / "mail-deliverability-audit" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import audit  # noqa: E402


class TestParseTxtValues(unittest.TestCase):
    def test_single_quoted_segment(self):
        self.assertEqual(audit.parse_txt_values(['"v=spf1 mx a ~all"']), ["v=spf1 mx a ~all"])

    def test_multi_segment_join(self):
        self.assertEqual(
            audit.parse_txt_values(['"v=spf1 " "mx a ~all"']),
            ["v=spf1 mx a ~all"],
        )

    def test_multiple_records(self):
        values = audit.parse_txt_values(['"v=spf1 mx ~all"', '"some-other-verification-token"'])
        self.assertEqual(len(values), 2)


class TestFindSpfRecords(unittest.TestCase):
    def test_filters_non_spf_txt(self):
        values = ["v=spf1 mx ~all", "google-site-verification=abc123", "v=DMARC1; p=none"]
        self.assertEqual(audit.find_spf_records(values), ["v=spf1 mx ~all"])

    def test_case_insensitive(self):
        self.assertEqual(audit.find_spf_records(["V=SPF1 mx ~all"]), ["V=SPF1 mx ~all"])


class TestSpfSyntaxIssues(unittest.TestCase):
    def test_clean_record_no_issues(self):
        self.assertEqual(audit.spf_syntax_issues("v=spf1 mx a ~all"), [])

    def test_missing_v_spf1_prefix(self):
        issues = audit.spf_syntax_issues("mx a ~all")
        self.assertTrue(any(level == "fail" for level, _ in issues))

    def test_plus_all_is_fail(self):
        issues = audit.spf_syntax_issues("v=spf1 mx a +all")
        self.assertTrue(any(level == "fail" and "spoof" in msg for level, msg in issues))

    def test_bare_all_defaults_to_plus_and_fails(self):
        issues = audit.spf_syntax_issues("v=spf1 mx a all")
        self.assertTrue(any(level == "fail" for level, _ in issues))

    def test_missing_all_mechanism_warns(self):
        issues = audit.spf_syntax_issues("v=spf1 mx a")
        self.assertTrue(any(level == "warn" and "no 'all'" in msg for level, msg in issues))

    def test_all_not_last_warns(self):
        issues = audit.spf_syntax_issues("v=spf1 ~all mx a")
        self.assertTrue(any("not the last term" in msg for _, msg in issues))

    def test_ptr_mechanism_warns(self):
        issues = audit.spf_syntax_issues("v=spf1 ptr ~all")
        self.assertTrue(any("ptr" in msg.lower() for _, msg in issues))

    def test_hard_fail_all_is_clean(self):
        self.assertEqual(audit.spf_syntax_issues("v=spf1 mx a -all"), [])


class TestCountSpfLookups(unittest.TestCase):
    def test_no_lookup_mechanisms(self):
        self.assertEqual(audit.count_spf_lookups("v=spf1 ip4:1.2.3.4 ~all", lambda d: []), 0)

    def test_simple_mechanisms_count_one_each(self):
        self.assertEqual(audit.count_spf_lookups("v=spf1 a mx ~all", lambda d: []), 2)

    def test_qualified_mechanism_still_counts(self):
        self.assertEqual(audit.count_spf_lookups("v=spf1 -include:example.com ~all", lambda d: []), 1)

    def test_include_recurses_into_target(self):
        def resolver(d):
            if d == "_spf.example.com":
                return ["v=spf1 a mx ~all"]
            return []
        # 1 for the include itself + 2 for the resolved a/mx inside it
        self.assertEqual(
            audit.count_spf_lookups("v=spf1 include:_spf.example.com ~all", resolver), 3,
        )

    def test_exceeds_rfc_limit(self):
        record = "v=spf1 " + " ".join(f"include:s{i}.example.com" for i in range(11)) + " ~all"
        self.assertGreater(audit.count_spf_lookups(record, lambda d: []), 10)

    def test_shared_include_target_not_double_counted(self):
        def resolver(d):
            return ["v=spf1 a ~all"]
        record = "v=spf1 include:shared.example.com include:shared.example.com ~all"
        # two include mechanisms (2) but the shared target is only recursed into once (+1 for its 'a')
        self.assertEqual(audit.count_spf_lookups(record, resolver), 3)


class TestNetcupComparison(unittest.TestCase):
    def test_is_netcup_mx_matches_canonical_pattern(self):
        self.assertTrue(audit.is_netcup_mx("mxf91d.netcup.net"))
        self.assertTrue(audit.is_netcup_mx("mxf91d.netcup.net."))

    def test_is_netcup_mx_rejects_other_hosts(self):
        self.assertFalse(audit.is_netcup_mx("mail.example.com"))
        self.assertFalse(audit.is_netcup_mx("aspmx.l.google.com"))

    def test_compare_netcup_spf_exact_match(self):
        self.assertTrue(audit.compare_netcup_spf(audit.NETCUP_SPF_TARGET))

    def test_compare_netcup_spf_mismatch(self):
        self.assertFalse(audit.compare_netcup_spf("v=spf1 mx ~all"))

    def test_compare_netcup_dkim_match(self):
        self.assertTrue(audit.compare_netcup_dkim("key1", "key1._domainkey.webhosting.systems."))

    def test_compare_netcup_dkim_mismatch(self):
        self.assertFalse(audit.compare_netcup_dkim("key1", "somewhere-else.example.com"))

    def test_compare_netcup_dkim_unknown_selector_returns_none(self):
        self.assertIsNone(audit.compare_netcup_dkim("selector1", "anything"))


if __name__ == "__main__":
    unittest.main()
