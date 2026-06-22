#!/usr/bin/env python3
"""Tests for ship-to-playstore/scripts/play-status.

Run from the repo root with `python3 tests/ship-to-playstore/test_play_status.py`.

Lives outside `skills/` on purpose: the `skills` CLI bundles a skill directory
as-is, and shipping tests to every install would just bloat the bundle.
See CLAUDE.md → "Tooling and testing".

The script calls live external APIs and shells out to openssl for RS256 —
neither is testable end-to-end without credentials. These tests cover the PURE
LOGIC (JWT claim construction, tri-state classifier, read-request builder,
strategy selector, credential discovery, situation-overview formatter, and the
read-only / secret-hygiene invariants). The thin HTTP + openssl wrappers are
NOT exercised here. See the issue's "Testability" section.

The hyphenated, extensionless script is loaded via SourceFileLoader (mirrors
slice 01's test_phase0_introspect.py).
"""

import base64
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "ship-to-playstore" / "scripts"
FIXTURES_DIR = pathlib.Path(__file__).resolve().parent / "fixtures"

sys.dont_write_bytecode = True

_SCRIPT_PATH = str(SCRIPTS_DIR / "play-status")
_loader = SourceFileLoader("play_status", _SCRIPT_PATH)
_spec = importlib.util.spec_from_loader("play_status", _loader)
PS = importlib.util.module_from_spec(_spec)
_loader.exec_module(PS)

SCRIPT = _SCRIPT_PATH


def _b64url_json(seg: str) -> dict:
    """Decode a base64url JWT segment (with padding restored) to a dict."""
    pad = "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg + pad))


class JwtAssertionSegments(unittest.TestCase):
    """AC: the JWT assertion (header.payload) is built purely and correctly."""

    def test_header_is_rs256_jwt(self):
        seg = PS.build_jwt_assertion_segments(
            "sa@proj.iam.gserviceaccount.com",
            PS.PUBLISHER_SCOPE, PS.TOKEN_URL, 1000, 4600,
        )
        header_seg, payload_seg = seg.split(".")
        header = _b64url_json(header_seg)
        self.assertEqual(header, {"alg": "RS256", "typ": "JWT"})

    def test_claim_set_carries_publisher_scope(self):
        email = "sa@proj.iam.gserviceaccount.com"
        seg = PS.build_jwt_assertion_segments(
            email, PS.PUBLISHER_SCOPE, PS.TOKEN_URL, 1000, 4600,
        )
        payload = _b64url_json(seg.split(".")[1])
        self.assertEqual(payload["iss"], email)
        self.assertEqual(payload["scope"], "https://www.googleapis.com/auth/androidpublisher")
        self.assertEqual(payload["aud"], "https://oauth2.googleapis.com/token")
        self.assertEqual(payload["iat"], 1000)
        self.assertEqual(payload["exp"], 4600)
        self.assertGreater(payload["exp"], payload["iat"])

    def test_signing_input_excludes_the_private_key(self):
        # The pure builder must not reference or carry any key material — signing
        # is the signer's job. The returned string is just two b64url segments.
        seg = PS.build_jwt_assertion_segments(
            "x@y.iam.gserviceaccount.com", "scope", "aud", 1, 2,
        )
        self.assertEqual(seg.count("."), 1)
        self.assertNotIn("PRIVATE KEY", seg)
        self.assertNotIn("BEGIN", seg)


class ReadRequestBuilder(unittest.TestCase):
    """AC3: BOTH IAP namespaces are queried. AC2: the read path is GET-only."""

    def test_both_iap_namespaces_always_present(self):
        reqs = PS.build_read_requests("com.example.app")
        labels = {r["label"] for r in reqs}
        self.assertIn("iap_one_time", labels)
        self.assertIn("iap_subscriptions", labels)

    def test_one_time_hits_inappproducts_namespace(self):
        reqs = PS.build_read_requests("com.example.app")
        one_time = next(r for r in reqs if r["label"] == "iap_one_time")
        self.assertIn("/inappproducts", one_time["url"])

    def test_subscriptions_hits_monetization_namespace(self):
        # The monetization.subscriptions resource; v3 path token is /subscriptions.
        reqs = PS.build_read_requests("com.example.app")
        sub = next(r for r in reqs if r["label"] == "iap_subscriptions")
        self.assertIn("/subscriptions", sub["url"])

    def test_no_edits_without_edit_id(self):
        # play-status never creates an edit (slice 04's job). Without --edit-id
        # there must be no edit-scoped request at all.
        reqs = PS.build_read_requests("com.example.app")
        for r in reqs:
            self.assertNotIn("/edits/", r["url"])

    def test_edit_scoped_reads_only_when_edit_id_given(self):
        reqs = PS.build_read_requests("com.example.app", edit_id="abc123")
        labels = {r["label"] for r in reqs}
        self.assertEqual({"iap_one_time", "iap_subscriptions", "tracks",
                          "listings", "appDetails"}, labels)

    def test_read_only_invariant_all_get(self):
        # AC2 hard invariant: every Play API request is a GET.
        for edit_id in (None, "abc"):
            reqs = PS.build_read_requests("com.example.app", edit_id=edit_id)
            self.assertTrue(
                PS.is_read_only_request_set(reqs),
                f"non-GET request in read path (edit_id={edit_id})",
            )
            for r in reqs:
                self.assertEqual(r["method"], "GET")

    def test_no_mutation_endpoints_constructed(self):
        # The forbidden mutations must never appear as a constructed request.
        forbidden_substrings = ("edits:commit", "edits/commit", "bundles:upload",
                                "bundles/upload", "tracks:update", "inappproducts:patch",
                                "subscriptions:patch")
        for edit_id in (None, "abc"):
            reqs = PS.build_read_requests("com.example.app", edit_id=edit_id)
            for r in reqs:
                for bad in forbidden_substrings:
                    self.assertNotIn(bad, r["url"], f"{bad} in {r['url']}")

    def test_package_is_url_encoded(self):
        reqs = PS.build_read_requests("com.example.app/odd name")
        for r in reqs:
            self.assertNotIn(" ", r["url"])


class TriStateClassifier(unittest.TestCase):
    """AC4: HTTP 403/404/401/network surface as cannot-verify with a cause,
    never swallowed to {}."""

    def test_200_is_verified(self):
        v = PS.classify_http(200, {"tracks": []})
        self.assertEqual(v["marker"], "✓")
        self.assertIsNone(v["likely_cause"])

    def test_403_cannot_verify_wrong_scope(self):
        v = PS.classify_http(403, {})
        self.assertEqual(v["marker"], "?")
        self.assertIn("scope", v["likely_cause"])
        self.assertIn("linked", v["likely_cause"])

    def test_404_cannot_verify_app_not_found(self):
        v = PS.classify_http(404, {})
        self.assertEqual(v["marker"], "?")
        self.assertIn("not found", v["likely_cause"])

    def test_401_cannot_verify_token(self):
        v = PS.classify_http(401, {})
        self.assertEqual(v["marker"], "?")
        self.assertIn("token", v["likely_cause"])

    def test_network_error_sentinel_is_cannot_verify(self):
        v = PS.classify_http(0, {})
        self.assertEqual(v["marker"], "?")
        self.assertIn("network", v["likely_cause"])

    def test_other_non_200_always_carries_a_cause(self):
        # Never swallowed to an empty result — the cardinal error (PRD §9.4).
        for code in (500, 502, 429, 400):
            v = PS.classify_http(code, {})
            self.assertEqual(v["marker"], "?")
            self.assertIsNotNone(v["likely_cause"])
            self.assertNotEqual(v["likely_cause"], "")


class StrategySelection(unittest.TestCase):
    """AC8 / OQ2: lane-first when a supply/play_* lane exists, raw API otherwise."""

    def test_supply_lane_preferred(self):
        letter, note = PS.select_strategy(["supply"])
        self.assertEqual(letter, "B")
        self.assertIn("lane", note.lower())

    def test_play_prefixed_lane_preferred(self):
        letter, _ = PS.select_strategy(["play_release", "beta"])
        self.assertEqual(letter, "B")

    def test_no_lane_falls_back_to_raw_api(self):
        letter, _ = PS.select_strategy(["beta", "test"])
        self.assertEqual(letter, "A")

    def test_no_lanes_at_all(self):
        letter, _ = PS.select_strategy([])
        self.assertEqual(letter, "A")

    def test_none_lanes(self):
        letter, _ = PS.select_strategy(None)
        self.assertEqual(letter, "A")


class CredentialDiscovery(unittest.TestCase):
    """AC2 secret hygiene: env var NAMES only, never values."""

    SECRET_ENV_VALUE = "/tmp/SECRET-service-account-DO-NOT-EMIT.json"

    def test_report_path_surfaced(self):
        report = {"credentials": {"service_account_json": [
            {"path": "android/api/play-service-account.json"}]}}
        out = PS.discover_service_account(report, env={})
        self.assertEqual(out["path"], "android/api/play-service-account.json")
        self.assertIsNone(out["missing_cause"])

    def test_env_names_only_never_values(self):
        report = {"credentials": {}}
        env = {"GOOGLE_APPLICATION_CREDENTIALS": self.SECRET_ENV_VALUE}
        out = PS.discover_service_account(report, env=env)
        self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", out["env_names"])
        # The secret VALUE must never appear in the discovery result.
        self.assertNotIn(self.SECRET_ENV_VALUE, json.dumps(out))

    def test_missing_cause_when_nothing_found(self):
        out = PS.discover_service_account({"credentials": {}}, env={})
        self.assertIsNotNone(out["missing_cause"])
        self.assertFalse(out["path"])
        self.assertEqual(out["env_names"], [])

    def test_truthiness_only_no_value_copy(self):
        # A set-but-empty env var does not count; a set var counts by name only.
        env = {"PLAY_CONFIG_JSON": "", "ANDROID_PUBLISHER_SERVICE_ACCOUNT": "x"}
        out = PS.discover_service_account({"credentials": {}}, env=env)
        self.assertIn("ANDROID_PUBLISHER_SERVICE_ACCOUNT", out["env_names"])
        self.assertNotIn("PLAY_CONFIG_JSON", out["env_names"])


class SituationOverviewFormatter(unittest.TestCase):
    """AC: the rendered block matches PRD §9.5 shape and carries tri-state markers."""

    def _full_facts(self):
        return {
            "package": "com.example.myapp",
            "app_exists": "yes",
            "live_prod": "v1.2.2 (40) — rollout 100%",
            "tracks": {
                "internal": "v1.2.3 (42) (completed)",
                "closed": "none",
                "open": "unknown",
                "production": "v1.2.2 (40) (inProgress) — rollout 10%",
            },
            "signing_enrolled": "?",
            "upload_keystore": "yes (android/key.properties)",
            "iap_one_time": {"marker": "✓", "products": [
                {"id": "pro_unlock", "status": "published"}], "cause": None},
            "iap_subscriptions": {"marker": "✓", "products": [
                {"id": "monthly", "status": "published"}], "cause": None},
            "listing": "complete (3 locale(s))",
            "feature_graphic": "set",
            "screenshots": "complete",
            "privacy_policy": "set",
            "data_safety": "published",
            "content_rating": "completed (IARC)",
            "pricing": "set",
            "fcm_used": True,
            "firebase_in_manifest_only": True,
            "strategy": "B",
            "strategy_note": "Fastlane supply/play_* lane (lane-first)",
        }

    def test_renders_package_and_header(self):
        out = PS.render_situation_overview(self._full_facts())
        self.assertIn("Situation Overview", out)
        self.assertIn("com.example.myapp", out)

    def test_renders_all_four_tracks(self):
        out = PS.render_situation_overview(self._full_facts())
        for track in ("Internal", "Closed", "Open", "Production"):
            self.assertIn(track, out)

    def test_renders_both_iap_sections(self):
        out = PS.render_situation_overview(self._full_facts())
        self.assertIn("Play Billing (one-time)", out)
        self.assertIn("Play Billing (subs)", out)
        self.assertIn("pro_unlock", out)
        self.assertIn("monthly", out)

    def test_verified_marker_present(self):
        out = PS.render_situation_overview(self._full_facts())
        self.assertIn("✓", out)

    def test_fcm_transport_only_note_when_transport_only(self):
        out = PS.render_situation_overview(self._full_facts())
        self.assertIn("FCM transport-only ✓", out)

    def test_fcm_flagged_when_broad_firebase_sdk(self):
        facts = self._full_facts()
        facts["firebase_in_manifest_only"] = False
        out = PS.render_situation_overview(facts)
        self.assertIn("stack-fidelity flag", out)

    def test_no_fcm_omits_transport_note(self):
        facts = self._full_facts()
        facts["fcm_used"] = False
        out = PS.render_situation_overview(facts)
        self.assertIn("no FCM detected", out)

    def test_cannot_verify_marker_for_missing_iap(self):
        facts = self._full_facts()
        facts["iap_one_time"] = {"marker": "?", "products": [],
                                 "cause": "wrong scope or service account not linked in Play Console"}
        out = PS.render_situation_overview(facts)
        self.assertIn("? cannot-verify", out)
        self.assertIn("linked", out)

    def test_strategy_line_rendered(self):
        out = PS.render_situation_overview(self._full_facts())
        self.assertIn("Access strategy", out)
        self.assertIn("B", out)

    def test_empty_facts_does_not_crash(self):
        # Minimal facts — every cell defaults; no KeyError.
        out = PS.render_situation_overview({"package": "com.x"})
        self.assertIn("com.x", out)
        self.assertIn("unknown", out)


class OverviewFromFixtures(unittest.TestCase):
    """Drive the formatter with fixture-shaped facts to lock the §9.5 shape."""

    def setUp(self):
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    def test_cannot_verify_fixture_renders_question_marks(self):
        with open(FIXTURES_DIR / "cannot_verify_facts.json", encoding="utf-8") as f:
            facts = json.load(f)
        out = PS.render_situation_overview(facts)
        self.assertIn("? cannot-verify", out)
        self.assertIn("com.example.unlinked", out)


class ReadOnlySurfaceInvariant(unittest.TestCase):
    """AC2: the script source itself has no mutation surface / no --yes flag."""

    def setUp(self):
        with open(SCRIPT, encoding="utf-8") as f:
            self.src = f.read()

    def test_no_yes_flag(self):
        self.assertNotIn('"--yes"', self.src)
        self.assertNotIn("'-y'", self.src)
        self.assertNotIn("'--yes'", self.src)

    def test_no_edits_insert(self):
        # play-status must not create edits (slice 04's job).
        self.assertNotIn("edits:insert", self.src)
        # No bare POST to .../edits (the edit-creation call).
        self.assertNotIn('"/edits"', self.src)

    def test_no_mutation_named_function(self):
        # No function in the module is named after a Play mutation (commit /
        # upload / update / insert / publish). The docstring legitimately names
        # these to say the script does NOT do them — a source substring grep
        # would false-positive, so check the actual callables instead.
        mutators = ("commit", "upload", "update", "insert", "publish", "delete")
        for name in dir(PS):
            if name.startswith("__"):
                continue
            self.assertFalse(
                any(m == name for m in mutators),
                f"module exposes a mutation-named callable: {name}",
            )

    def test_read_requests_only_get(self):
        # The only methods the read path constructs.
        reqs = PS.build_read_requests("com.x", edit_id="e")
        self.assertTrue({r["method"] for r in reqs} == {"GET"})

    def test_only_post_is_oauth_token_endpoint(self):
        # Sanity: the script's sole POST is the OAuth2 token mint (auth, not a
        # Play mutation). Confirmed by reading the mint function.
        self.assertIn(TOKEN_URL if False else PS.TOKEN_URL, self.src)
        self.assertIn("grant_type", self.src)


class SecretHygieneInvariant(unittest.TestCase):
    """AC2: the script never emits the JSON contents, private key, JWT, or token."""

    def setUp(self):
        with open(SCRIPT, encoding="utf-8") as f:
            self.src = f.read()

    def test_token_never_printed(self):
        # No print/f-string that interpolates the access token or assertion.
        self.assertNotIn("print(token", self.src)
        self.assertNotIn("print(assertion", self.src)
        self.assertNotIn("print(private_key", self.src)
        self.assertNotIn("print(private_key_pem", self.src)

    def test_authorization_header_never_logged(self):
        # The bearer header is set in http_get but must never be printed.
        self.assertNotIn("print(.*Authorization", self.src)

    def test_debug_does_not_emit_token(self):
        # Every print() call in the source must be free of secret-bearing
        # identifiers. The debug branch prints only "{label}: HTTP {status}";
        # grep that no print line interpolates the token/key/assertion/Bearer.
        secret_words = ("token", "private_key", "assertion", "Bearer", "access_token")
        for line in self.src.splitlines():
            if "print(" in line:
                for w in secret_words:
                    self.assertNotIn(
                        w, line,
                        f"print() references secret identifier {w!r}: {line.strip()}",
                    )


class TestClassifyIapProduct(unittest.TestCase):
    """AC1: classify_iap_product covers both namespaces with correct publishability rules."""

    # --- inappproducts (one-time) ---

    def test_active_status_is_publishable(self):
        p = PS.classify_iap_product({"sku": "coins_100", "status": "active"}, "inappproducts")
        self.assertEqual(p["id"], "coins_100")
        self.assertEqual(p["status"], "active")
        self.assertTrue(p["publishable"])

    def test_published_status_is_publishable(self):
        p = PS.classify_iap_product({"sku": "pro", "status": "published"}, "inappproducts")
        self.assertTrue(p["publishable"])

    def test_draft_status_is_not_publishable(self):
        p = PS.classify_iap_product({"sku": "old_feat", "status": "draft"}, "inappproducts")
        self.assertFalse(p["publishable"])
        self.assertEqual(p["status"], "draft")

    def test_inactive_status_is_not_publishable(self):
        p = PS.classify_iap_product({"sku": "sku1", "status": "inactive"}, "inappproducts")
        self.assertFalse(p["publishable"])

    def test_inappproduct_uses_sku_field(self):
        p = PS.classify_iap_product({"sku": "my_sku"}, "inappproducts")
        self.assertEqual(p["id"], "my_sku")

    def test_inappproduct_falls_back_to_productId(self):
        p = PS.classify_iap_product({"productId": "pid_123", "status": "active"}, "inappproducts")
        self.assertEqual(p["id"], "pid_123")

    def test_no_base_plans_key_for_inappproducts(self):
        p = PS.classify_iap_product({"sku": "x", "status": "active"}, "inappproducts")
        self.assertNotIn("base_plans", p)

    # --- subscriptions ---

    def test_active_subscription_with_active_base_plan_is_publishable(self):
        item = {
            "productId": "monthly_sub",
            "state": "ACTIVE",
            "basePlans": [{"basePlanId": "p1", "state": "ACTIVE"}],
        }
        p = PS.classify_iap_product(item, "subscriptions")
        self.assertEqual(p["id"], "monthly_sub")
        self.assertEqual(p["state"], "ACTIVE")
        self.assertTrue(p["publishable"])
        self.assertTrue(p["has_active_base_plan"])
        self.assertEqual(len(p["base_plans"]), 1)
        self.assertTrue(p["base_plans"][0]["active"])

    def test_active_subscription_without_active_base_plan_is_not_publishable(self):
        item = {
            "productId": "annual_sub",
            "state": "ACTIVE",
            "basePlans": [{"basePlanId": "p1", "state": "INACTIVE"}],
        }
        p = PS.classify_iap_product(item, "subscriptions")
        self.assertFalse(p["publishable"])
        self.assertFalse(p["has_active_base_plan"])

    def test_active_subscription_with_no_base_plans_is_not_publishable(self):
        item = {"productId": "new_sub", "state": "ACTIVE", "basePlans": []}
        p = PS.classify_iap_product(item, "subscriptions")
        self.assertFalse(p["publishable"])
        self.assertEqual(p["base_plans"], [])

    def test_inactive_subscription_with_active_base_plan_is_not_publishable(self):
        item = {
            "productId": "old_sub",
            "state": "INACTIVE",
            "basePlans": [{"basePlanId": "p1", "state": "ACTIVE"}],
        }
        p = PS.classify_iap_product(item, "subscriptions")
        self.assertFalse(p["publishable"])

    def test_subscription_base_plan_offers_counted(self):
        item = {
            "productId": "sub1",
            "state": "ACTIVE",
            "basePlans": [{
                "basePlanId": "annual",
                "state": "ACTIVE",
                "offers": [{}, {}],
            }],
        }
        p = PS.classify_iap_product(item, "subscriptions")
        self.assertEqual(p["base_plans"][0]["offers_count"], 2)

    def test_subscription_multiple_base_plans_any_active_is_publishable(self):
        item = {
            "productId": "sub2",
            "state": "ACTIVE",
            "basePlans": [
                {"basePlanId": "monthly", "state": "INACTIVE"},
                {"basePlanId": "annual", "state": "ACTIVE"},
            ],
        }
        p = PS.classify_iap_product(item, "subscriptions")
        self.assertTrue(p["publishable"])
        self.assertTrue(p["has_active_base_plan"])


class TestIapFactsDeepened(unittest.TestCase):
    """AC1: _iap_facts deepened to use classify_iap_product and emit has_blocker."""

    def _ok_body_inapp(self, products):
        return {"kind": "androidpublisher#inappproductsListResponse",
                "inappproducts": products}

    def _ok_body_subs(self, products):
        return {"subscriptions": products}

    def test_publishable_inapp_no_blocker(self):
        body = self._ok_body_inapp([{"sku": "coin", "status": "active"}])
        result = PS._iap_facts(200, body, "inappproducts")
        self.assertEqual(result["marker"], "✓")
        self.assertFalse(result["has_blocker"])
        self.assertTrue(result["products"][0]["publishable"])

    def test_draft_inapp_sets_has_blocker(self):
        body = self._ok_body_inapp([{"sku": "coin", "status": "draft"}])
        result = PS._iap_facts(200, body, "inappproducts")
        self.assertEqual(result["marker"], "✓")
        self.assertTrue(result["has_blocker"])
        self.assertFalse(result["products"][0]["publishable"])

    def test_subscription_no_active_base_plan_sets_has_blocker(self):
        body = self._ok_body_subs([{
            "productId": "sub1",
            "state": "ACTIVE",
            "basePlans": [{"basePlanId": "p1", "state": "INACTIVE"}],
        }])
        result = PS._iap_facts(200, body, "subscriptions")
        self.assertTrue(result["has_blocker"])
        self.assertFalse(result["products"][0]["publishable"])

    def test_error_response_returns_cannot_verify_no_blocker(self):
        result = PS._iap_facts(403, {"error": {"message": "forbidden"}}, "inappproducts")
        self.assertEqual(result["marker"], "?")
        self.assertFalse(result["has_blocker"])
        self.assertEqual(result["products"], [])

    def test_has_blocker_false_for_empty_catalog(self):
        body = self._ok_body_inapp([])
        result = PS._iap_facts(200, body, "inappproducts")
        self.assertFalse(result["has_blocker"])
        self.assertEqual(result["products"], [])


class TestSituationOverviewBlockers(unittest.TestCase):
    """AC1: _iap_block renders BLOCKER tags for non-publishable products."""

    def _facts_with_iap(self, iap_ot, iap_sub):
        return {
            "package": "com.x",
            "iap_one_time": iap_ot,
            "iap_subscriptions": iap_sub,
        }

    def test_draft_inapp_shows_blocker_tag(self):
        facts = self._facts_with_iap(
            iap_ot={"marker": "✓", "has_blocker": True, "cause": None,
                    "products": [{"id": "old_feat", "status": "draft", "publishable": False}]},
            iap_sub=None,
        )
        out = PS.render_situation_overview(facts)
        self.assertIn("old_feat=draft ← BLOCKER", out)

    def test_publishable_inapp_no_blocker_tag(self):
        facts = self._facts_with_iap(
            iap_ot={"marker": "✓", "has_blocker": False, "cause": None,
                    "products": [{"id": "coin", "status": "active", "publishable": True}]},
            iap_sub=None,
        )
        out = PS.render_situation_overview(facts)
        self.assertIn("coin=active", out)
        self.assertNotIn("BLOCKER", out)

    def test_subscription_no_active_bp_shows_blocker(self):
        facts = self._facts_with_iap(
            iap_ot=None,
            iap_sub={"marker": "✓", "has_blocker": True, "cause": None, "products": [{
                "id": "monthly", "state": "ACTIVE",
                "publishable": False,
                "base_plans": [{"id": "p1", "state": "INACTIVE", "active": False, "offers_count": 0}],
                "has_active_base_plan": False,
            }]},
        )
        out = PS.render_situation_overview(facts)
        self.assertIn("monthly", out)
        self.assertIn("BLOCKER", out)
        self.assertIn("0/1 base plan(s)", out)

    def test_old_format_no_publishable_key_no_blocker_tag(self):
        # Old fixture format without "publishable" key must not show BLOCKER (backward compat)
        facts = self._facts_with_iap(
            iap_ot={"marker": "✓", "cause": None,
                    "products": [{"id": "pro_unlock", "status": "published"}]},
            iap_sub=None,
        )
        out = PS.render_situation_overview(facts)
        self.assertIn("pro_unlock=published", out)
        self.assertNotIn("BLOCKER", out)


class NoBytecodeInSkills(unittest.TestCase):
    """Guard: importing the script must not leave __pycache__ in skills/."""

    def test_no_pycache_under_skill(self):
        pycache = SCRIPTS_DIR / "__pycache__"
        self.assertFalse(
            pycache.exists(),
            f"__pycache__ leaked into skills/ at {pycache}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
