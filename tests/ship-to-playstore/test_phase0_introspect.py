#!/usr/bin/env python3
"""Tests for ship-to-playstore/scripts/phase0-introspect.

Run from the repo root with `python3 tests/ship-to-playstore/test_phase0_introspect.py`.

Lives outside `skills/` on purpose: the `skills` CLI bundles a skill directory
as-is, and shipping tests to every install would just bloat the bundle.
See CLAUDE.md → "Tooling and testing".

Fixtures are built inside tempfile.TemporaryDirectory() so nothing leaks into
skills/. PYTHONDONTWRITEBYTECODE=1 is passed to subprocesses and
sys.dont_write_bytecode is set on import.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import importlib.util
from importlib.machinery import SourceFileLoader

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "ship-to-playstore" / "scripts"

sys.dont_write_bytecode = True

# The script is named `phase0-introspect` (hyphen, no extension) to match the
# PRD §6 layout and the iOS analogue — that name is not a valid Python module
# identifier and has no .py suffix, so load it explicitly via SourceFileLoader.
_SCRIPT_PATH = str(SCRIPTS_DIR / "phase0-introspect")
_loader = SourceFileLoader("phase0_introspect", _SCRIPT_PATH)
_spec = importlib.util.spec_from_loader("phase0_introspect", _loader)
P = importlib.util.module_from_spec(_spec)
_loader.exec_module(P)

SCRIPT = _SCRIPT_PATH


def write_fixture(root: str, files: dict) -> None:
    """Write {relpath: content} under root, creating parent dirs."""
    for rel, content in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)


def make_flutter_android_fixture(root: str, **overrides) -> None:
    """Write a minimal-but-realistic Flutter/Android fixture tree."""
    files = {
        "pubspec.yaml": (
            "name: my_app\n"
            "description: A test app.\n"
            "version: 1.2.3+42\n"
            "environment:\n"
            "  sdk: '>=3.0.0 <4.0.0'\n"
            "dependencies:\n"
            "  flutter:\n"
            "    sdk: flutter\n"
            "  supabase_flutter: ^2.0.0\n"
        ),
        "android/app/build.gradle": (
            "plugins {\n"
            '    id "com.android.application"\n'
            '    id "org.jetbrains.kotlin.android"\n'
            "}\n"
            "android {\n"
            '    namespace "com.example.myapp"\n'
            '    applicationId "com.example.myapp"\n'
            "    compileSdk 34\n"
            "    defaultConfig {\n"
            "        minSdk 21\n"
            "        targetSdk 34\n"
            "    }\n"
            "    compileOptions {\n"
            "        sourceCompatibility JavaVersion.VERSION_17\n"
            "        targetCompatibility JavaVersion.VERSION_17\n"
            "    }\n"
            "}\n"
        ),
        "android/settings.gradle": (
            "plugins {\n"
            '    id "dev.flutter.flutter-plugin-loader" version "1.0.0"\n'
            '    id "com.android.application" version "8.3.0" apply false\n'
            '    id "org.jetbrains.kotlin.android" version "1.9.22" apply false\n'
            "}\n"
        ),
        "android/gradle/wrapper/gradle-wrapper.properties": (
            "distributionBase=GRADLE_USER_HOME\n"
            "distributionPath=wrapper/dists\n"
            "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.5-bin.zip\n"
        ),
        "android/app/src/main/AndroidManifest.xml": (
            "<manifest xmlns:android=\"http://schemas.android.com/apk/res/android\">\n"
            '    <uses-permission android:name="android.permission.INTERNET" />\n'
            "</manifest>\n"
        ),
    }
    files.update(overrides.pop("files", {}))
    write_fixture(root, files)


class DetectFlutterAndroid(unittest.TestCase):
    def test_flutter_android_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_flutter_android_fixture(tmp)
            ok, reason = P.detect_flutter_android(tmp)
            self.assertTrue(ok)
            self.assertIsNone(reason)

    def test_ios_only_repo_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\nversion: 1.0.0+1\ndependencies:\n  flutter:\n    sdk: flutter\n",
                "ios/Runner.xcodeproj/project.pbxproj": "",
            })
            ok, reason = P.detect_flutter_android(tmp)
            self.assertFalse(ok)
            self.assertIn("android/", reason)

    def test_plain_dart_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {"pubspec.yaml": "name: cli\nversion: 1.0.0\n"})
            ok, reason = P.detect_flutter_android(tmp)
            self.assertFalse(ok)
            self.assertIn("flutter:", reason)

    def test_android_dir_without_app_gradle_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n",
                "android/placeholder.txt": "",
            })
            ok, reason = P.detect_flutter_android(tmp)
            self.assertFalse(ok)
            self.assertIn("build.gradle", reason)


class ParsePubspec(unittest.TestCase):
    def test_name_version_name_version_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {"pubspec.yaml": "name: my_app\nversion: 1.2.3+42\n"})
            out = P.parse_pubspec(tmp)
            self.assertEqual(out["app_display_name"], "my_app")
            self.assertEqual(out["version_name"], "1.2.3")
            self.assertEqual(out["version_code"], 42)

    def test_no_build_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {"pubspec.yaml": "name: x\nversion: 1.0.0\n"})
            self.assertIsNone(P.parse_pubspec(tmp)["version_code"])

    def test_non_numeric_code_is_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {"pubspec.yaml": "name: x\nversion: 1.0.0+abc\n"})
            self.assertIsNone(P.parse_pubspec(tmp)["version_code"])


class GradleWrapperVersion(unittest.TestCase):
    def test_extracted_from_distribution_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/gradle/wrapper/gradle-wrapper.properties":
                    "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.5-bin.zip\n"
            })
            self.assertEqual(P.parse_gradle_wrapper(tmp), "8.5")

    def test_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(P.parse_gradle_wrapper(tmp))


class GradlePluginVersions(unittest.TestCase):
    def test_modern_plugins_block_in_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/settings.gradle": (
                    "plugins {\n"
                    '    id "com.android.application" version "8.3.0" apply false\n'
                    '    id "org.jetbrains.kotlin.android" version "1.9.22" apply false\n'
                    "}\n"
                ),
            })
            out = P.parse_gradle_plugins(tmp)
            self.assertEqual(out["agp_version"], "8.3.0")
            self.assertEqual(out["kotlin_version"], "1.9.22")

    def test_legacy_buildscript_classpath(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/build.gradle": (
                    "buildscript {\n"
                    "    dependencies {\n"
                    '        classpath "com.android.tools.build:gradle:7.4.2"\n'
                    '        classpath "org.jetbrains.kotlin:kotlin-gradle-plugin:1.8.20"\n'
                    "    }\n"
                    "}\n"
                ),
            })
            out = P.parse_gradle_plugins(tmp)
            self.assertEqual(out["agp_version"], "7.4.2")
            self.assertEqual(out["kotlin_version"], "1.8.20")

    def test_ext_kotlin_version_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/build.gradle": 'ext {\n    kotlin_version = "1.7.10"\n}\n',
            })
            self.assertEqual(P.parse_gradle_plugins(tmp)["kotlin_version"], "1.7.10")

    def test_kts_plugins_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/settings.gradle.kts": (
                    "plugins {\n"
                    '    id("dev.flutter.flutter-plugin-loader") version "1.0.0"\n'
                    '    id("com.android.application") version "8.1.0" apply false\n'
                    '    id("org.jetbrains.kotlin.android") version "1.9.0" apply false\n'
                    "}\n"
                ),
            })
            out = P.parse_gradle_plugins(tmp)
            self.assertEqual(out["agp_version"], "8.1.0")
            self.assertEqual(out["kotlin_version"], "1.9.0")

    def test_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = P.parse_gradle_plugins(tmp)
            self.assertIsNone(out["agp_version"])
            self.assertIsNone(out["kotlin_version"])


class AppBuildGradle(unittest.TestCase):
    def test_full_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/app/build.gradle": (
                    "android {\n"
                    '    namespace "com.example.myapp"\n'
                    '    applicationId "com.example.myapp"\n'
                    "    defaultConfig {\n"
                    "        minSdkVersion 21\n"
                    "        targetSdkVersion 34\n"
                    "    }\n"
                    '    ndkVersion "25.1.8937393"\n'
                    "    compileOptions {\n"
                    "        sourceCompatibility JavaVersion.VERSION_17\n"
                    "    }\n"
                    "}\n"
                ),
            })
            out = P.parse_app_build_gradle(tmp)
            self.assertEqual(out["application_id"], "com.example.myapp")
            self.assertEqual(out["min_sdk_version"], 21)
            self.assertEqual(out["target_sdk_version"], 34)
            self.assertEqual(out["ndk_version"], "25.1.8937393")
            self.assertEqual(out["java_toolchain"], "17")

    def test_newer_dsl_without_version_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/app/build.gradle": (
                    "android {\n"
                    '    applicationId "com.x.y"\n'
                    "    defaultConfig { minSdk 23\ntargetSdk 33 }\n"
                    "    kotlinOptions { jvmTarget = '17' }\n"
                    "}\n"
                ),
            })
            out = P.parse_app_build_gradle(tmp)
            self.assertEqual(out["min_sdk_version"], 23)
            self.assertEqual(out["target_sdk_version"], 33)
            self.assertEqual(out["java_toolchain"], "17")

    def test_namespace_fallback_when_no_application_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/app/build.gradle": 'android {\n    namespace "com.fallback.pkg"\n}\n',
            })
            self.assertEqual(P.parse_app_build_gradle(tmp)["application_id"], "com.fallback.pkg")

    def test_signing_config_wired(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/app/build.gradle": (
                    "android {\n"
                    "    signingConfigs { release { } }\n"
                    "    buildTypes { release { signingConfig signingConfigs.release } }\n"
                    "}\n"
                ),
            })
            self.assertTrue(P.parse_app_build_gradle(tmp)["signing_config_set"])

    def test_no_signing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/app/build.gradle": 'android {\n    namespace "com.x"\n}\n',
            })
            self.assertFalse(P.parse_app_build_gradle(tmp)["signing_config_set"])


class IconDensities(unittest.TestCase):
    def _with_icons(self, densities: list[str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            for d in densities:
                bucket = os.path.join(tmp, "android", "app", "src", "main", "res", f"mipmap-{d}")
                os.makedirs(bucket)
                with open(os.path.join(bucket, "ic_launcher.png"), "wb") as f:
                    f.write(b"\x89PNG\r\n")
            return P.check_icon_densities(tmp)

    def test_complete(self):
        out = self._with_icons(["mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"])
        self.assertTrue(out["complete"])
        self.assertEqual(out["missing_densities"], [])

    def test_missing_density_reported(self):
        out = self._with_icons(["mdpi", "hdpi", "xhdpi", "xxhdpi"])
        self.assertFalse(out["complete"])
        self.assertEqual(out["missing_densities"], ["xxxhdpi"])

    def test_no_res_dir_all_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = P.check_icon_densities(tmp)
            self.assertFalse(out["complete"])
            self.assertEqual(len(out["missing_densities"]), 5)

    def test_adaptive_xml_counts_as_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            for d in ["mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"]:
                bucket = os.path.join(tmp, "android", "app", "src", "main", "res", f"mipmap-{d}")
                os.makedirs(bucket)
                with open(os.path.join(bucket, "ic_launcher.xml"), "w") as fobj:
                    fobj.write("<adaptive-icon/>")
            out = P.check_icon_densities(tmp)
            self.assertTrue(out["complete"])

    def test_unrelated_file_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            bucket = os.path.join(tmp, "android", "app", "src", "main", "res", "mipmap-mdpi")
            os.makedirs(bucket)
            with open(os.path.join(bucket, "background.png"), "wb") as f:
                f.write(b"\x89PNG")
            out = P.check_icon_densities(tmp)
            self.assertIn("mdpi", out["missing_densities"])


class Permissions(unittest.TestCase):
    def test_excessive_and_missing_computed(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": (
                    "name: x\n"
                    "dependencies:\n"
                    "  flutter:\n"
                    "    sdk: flutter\n"
                    "  camera:\n"  # expects CAMERA → missing
                    "  geolocator:\n"  # expects LOCATION → missing
                ),
                "android/app/src/main/AndroidManifest.xml": (
                    "<manifest>\n"
                    '    <uses-permission android:name="android.permission.INTERNET" />\n'
                    '    <uses-permission android:name="android.permission.READ_SMS" />\n'  # excessive
                    "</manifest>\n"
                ),
            })
            out = P.detect_permissions(tmp)
            self.assertIn("android.permission.CAMERA", out["missing"])
            self.assertIn("android.permission.ACCESS_FINE_LOCATION", out["missing"])
            self.assertIn("android.permission.READ_SMS", out["excessive"])
            self.assertIn("android.permission.INTERNET", out["declared"])

    def test_baseline_internet_never_excessive(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n",
                "android/app/src/main/AndroidManifest.xml": (
                    "<manifest>\n"
                    '    <uses-permission android:name="android.permission.INTERNET" />\n'
                    "</manifest>\n"
                ),
            })
            out = P.detect_permissions(tmp)
            self.assertEqual(out["excessive"], [])

    def test_complete_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": (
                    "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n  camera:\n"
                ),
                "android/app/src/main/AndroidManifest.xml": (
                    "<manifest>\n"
                    '    <uses-permission android:name="android.permission.INTERNET" />\n'
                    '    <uses-permission android:name="android.permission.CAMERA" />\n'
                    "</manifest>\n"
                ),
            })
            out = P.detect_permissions(tmp)
            self.assertEqual(out["missing"], [])
            self.assertEqual(out["excessive"], [])


class SigningSecretHygiene(unittest.TestCase):
    """The critical silent-miss-risk test: a password in key.properties must
    NEVER appear in the parsed output. The script must not read the file."""

    PASSWORD = "SUPER_SECRET_KEYSTORE_PASSWORD_123"

    def test_key_properties_password_never_emitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/key.properties": (
                    f"storePassword={self.PASSWORD}\n"
                    f"keyPassword={self.PASSWORD}\n"
                    "keyAlias=release-key\n"
                    f"keyAliasPassword={self.PASSWORD}\n"
                    "storeFile=keystore.jks\n"
                ),
            })
            out = P.detect_signing(tmp)
            # Path surfaced.
            self.assertTrue(out["has_key_properties"])
            self.assertIn("android/key.properties", out["keystore_hints"])
            # Password string must NOT appear anywhere in the output.
            self.assertNotIn(self.PASSWORD, json.dumps(out))

    def test_service_account_json_contents_never_read(self):
        secret_body = "-----BEGIN PRIVATE KEY-----\nNEVER_EMIT_THIS_SECRET\n-----END PRIVATE KEY-----"
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/api/play-service-account.json": json.dumps({
                    "private_key": secret_body,
                    "client_email": "secret@secret.iam.gserviceaccount.com",
                }),
            })
            out = P.discover_credentials(tmp)
            # Path surfaced, body never emitted.
            self.assertTrue(out["service_account_json"])
            joined = json.dumps(out)
            self.assertNotIn(secret_body, joined)
            self.assertNotIn("NEVER_EMIT_THIS_SECRET", joined)

    def test_enrollable_hint_when_no_keystore(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = P.detect_signing(tmp)
            self.assertTrue(out["play_app_signing_enrollable_from_repo"])

    def test_enrollable_false_when_keystore_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/app/keystore.jks": "fake-binary",
                "android/app/build.gradle": (
                    "android {\n    buildTypes { release { signingConfig signingConfigs.release } }\n}\n"
                ),
            })
            out = P.detect_signing(tmp)
            self.assertFalse(out["play_app_signing_enrollable_from_repo"])
            self.assertIn("android/app/keystore.jks", out["keystore_hints"])


class Credentials(unittest.TestCase):
    def test_env_hint_name_only_never_value(self):
        secret_value = "file:///tmp/secret-credentials.json"
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, GOOGLE_APPLICATION_CREDENTIALS=secret_value)
            old_env = os.environ
            os.environ = env
            try:
                out = P.discover_credentials(tmp)
            finally:
                os.environ = old_env
            self.assertIn("GOOGLE_APPLICATION_CREDENTIALS", out["env_hints"])
            self.assertNotIn(secret_value, json.dumps(out))

    def test_fastlane_appfile_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {"fastlane/Appfile": "app_identifier \"com.x\"\n"})
            out = P.discover_credentials(tmp)
            self.assertEqual(out["fastlane_supplyfile"]["path"], "fastlane/Appfile")

    def test_service_account_json_path_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "android/api/play-service-account.json": "{}",
                "android/api/random.json": "{}",  # not service-account-shaped
            })
            out = P.discover_credentials(tmp)
            paths = [e["path"] for e in out["service_account_json"]]
            self.assertIn("android/api/play-service-account.json", paths)
            self.assertNotIn("android/api/random.json", paths)


class FastlaneLanes(unittest.TestCase):
    def test_lanes_listed(self):
        # private_lane / desc blocks are excluded — only top-level lanes count
        # (matches the iOS analogue regex).
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "fastlane/Fastfile": (
                    "lane :play_release do\nend\n"
                    "lane :supply do\nend\n"
                    "private_lane :internal do\nend\n"
                    "desc 'x'\n"
                ),
            })
            self.assertEqual(P.detect_fastlane_lanes(tmp), ["play_release", "supply"])

    def test_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(P.detect_fastlane_lanes(tmp), [])


class PlayBilling(unittest.TestCase):
    def test_detected_via_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n  in_app_purchase:\n",
            })
            out = P.detect_play_billing(tmp)
            self.assertTrue(out["likely_present"])
            self.assertIn("in_app_purchase", out["packages"])

    def test_detected_via_code_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n",
                "lib/store.dart": (
                    "final InAppPurchase iap = InAppPurchase.instance;\n"
                    "queryProductDetails(ids);\n"
                    "BillingClient client;\n"
                ),
            })
            out = P.detect_play_billing(tmp)
            self.assertTrue(out["likely_present"])
            self.assertIn("BillingClient", out["code_markers"])

    def test_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n",
            })
            self.assertFalse(P.detect_play_billing(tmp)["likely_present"])


class DataSafetyHints(unittest.TestCase):
    def test_analytics_and_deletion_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": (
                    "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n  sentry_flutter:\n"
                ),
                "lib/account.dart": "await auth.admin.deleteUser(userId);\n",
            })
            out = P.detect_data_safety_hints(tmp)
            self.assertEqual(out["analytics_tracking"][0]["package"], "sentry_flutter")
            self.assertTrue(out["account_deletion"]["likely_present"])

    def test_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n",
            })
            out = P.detect_data_safety_hints(tmp)
            self.assertEqual(out["analytics_tracking"], [])
            self.assertFalse(out["account_deletion"]["likely_present"])


class PushNotificationsAndSupabase(unittest.TestCase):
    def test_supabase_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n  supabase_flutter:\n",
            })
            self.assertTrue(P.detect_supabase(tmp))

    def test_supabase_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n",
            })
            self.assertFalse(P.detect_supabase(tmp))

    def test_fcm_transport_only_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n  flutter_local_notifications:\n",
                "android/app/google-services.json": "{}",
                "android/build.gradle": (
                    'buildscript { dependencies { classpath "com.google.gms:google-services:4.3.15" } }\n'
                ),
                "android/app/build.gradle": (
                    "apply plugin: 'com.google.gms.google-services'\nandroid {\n    namespace \"com.x\"\n}\n"
                ),
            })
            out = P.detect_push_notifications(tmp)
            self.assertTrue(out["fcm_used"])
            self.assertTrue(out["firebase_in_manifest_only"])

    def test_broad_firebase_not_flagged_transport_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": (
                    "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n  firebase_core:\n  firebase_messaging:\n"
                ),
                "android/app/google-services.json": "{}",
                "android/app/build.gradle": "apply plugin: 'com.google.gms.google-services'\nandroid {\n    namespace \"com.x\"\n}\n",
            })
            out = P.detect_push_notifications(tmp)
            self.assertTrue(out["fcm_used"])
            self.assertFalse(out["firebase_in_manifest_only"])


class SchemaCompleteness(unittest.TestCase):
    EXPECTED_TOP_KEYS = {
        "flutter_android", "app_display_name", "application_id", "version_name",
        "version_code", "min_sdk_version", "target_sdk_version", "gradle",
        "signing", "icon_set", "permissions", "credentials", "fastlane_lanes",
        "play_billing", "data_safety_hints", "user_generated_content",
        "push_notifications", "supabase_used",
    }

    def test_all_top_level_keys_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_flutter_android_fixture(tmp)
            report = P.build_report(tmp)
            self.assertEqual(set(report.keys()), self.EXPECTED_TOP_KEYS)

    def test_gradle_subkeys(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_flutter_android_fixture(tmp)
            gradle = P.build_report(tmp)["gradle"]
            self.assertEqual(
                set(gradle.keys()),
                {"wrapper_version", "agp_version", "kotlin_version", "java_toolchain", "ndk_version"},
            )

    def test_signing_subkeys(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_flutter_android_fixture(tmp)
            signing = P.build_report(tmp)["signing"]
            self.assertEqual(
                set(signing.keys()),
                {"signing_config_set", "keystore_hints", "has_key_properties",
                 "play_app_signing_enrollable_from_repo"},
            )


class Cli(unittest.TestCase):
    def _run(self, args, cwd=None, env_extra=None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, SCRIPT, *args],
            capture_output=True, text=True, env=env, cwd=cwd,
        )

    def test_exit0_on_flutter_android(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_flutter_android_fixture(tmp)
            r = self._run([tmp])
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            data = json.loads(r.stdout)
            self.assertTrue(data["flutter_android"])

    def test_exit1_on_ios_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(tmp, {
                "pubspec.yaml": "name: x\ndependencies:\n  flutter:\n    sdk: flutter\n",
                "ios/Runner.xcodeproj/project.pbxproj": "",
            })
            r = self._run([tmp])
            self.assertEqual(r.returncode, 1)
            self.assertIn("WARNING", r.stderr)
            self.assertEqual(r.stdout.strip(), "")

    def test_exit2_on_too_many_args(self):
        r = self._run(["a", "b", "c"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("Usage", r.stderr)

    def test_default_path_uses_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_flutter_android_fixture(tmp)
            r = self._run([], cwd=tmp)
            self.assertEqual(r.returncode, 0, msg=r.stderr)

    def test_secret_never_in_stdout(self):
        password = "CLI_LEAKED_PASSWORD_XYZ"
        with tempfile.TemporaryDirectory() as tmp:
            make_flutter_android_fixture(tmp, files={
                "android/key.properties": f"storePassword={password}\nstoreFile=k.jks\n",
            })
            r = self._run([tmp])
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            self.assertNotIn(password, r.stdout)
            self.assertNotIn(password, r.stderr)


class NoBytecodeInSkills(unittest.TestCase):
    """Guard: running the test suite must not leave __pycache__ in skills/."""

    def test_no_pycache_under_skill(self):
        pycache = SCRIPTS_DIR / "__pycache__"
        self.assertFalse(
            pycache.exists(),
            f"__pycache__ leaked into skills/ at {pycache}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
