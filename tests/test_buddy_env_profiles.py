#!/usr/bin/env python3
"""Tests for role env profile contract and profile matrix."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env_profiles  # noqa: E402


class BuddyEnvProfilesTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.role_ids = [role["id"] for role in self.manifest["roles"]]
        self.role_set = set(self.role_ids)
        self.profile_root = ROOT / "buddyswitch" / "env-profiles"

    def test_profile_files_match_manifest_buddies(self) -> None:
        files = {
            path.stem
            for path in self.profile_root.glob("*.json")
            if path.is_file()
        }
        self.assertEqual(files, self.role_set)

    def test_profiles_validate_with_matrix_rules(self) -> None:
        track_effects_seen = []
        for role_id in self.role_ids:
            profile = env_profiles.require_env_profile(
                role_id,
                manifest_path=self.manifest_path,
                repo_root=ROOT,
            )
            self.assertEqual(list(profile.keys()), env_profiles.profile_contract(ROOT)["top_level_key_order"])
            self.assertEqual(profile["role_id"], role_id)
            self.assertEqual(profile["private_workspace"]["root"], env_profiles.PRIVATE_WORKSPACE_ROOT)
            self.assertEqual(profile["context_projection"]["skills"], "role-profile-only")
            self.assertEqual(
                env_profiles.resolve_private_workspace_root(profile["private_workspace"]["root"], role_id=role_id),
                "private",
            )
            self.assertEqual(profile["filesystem_capability"]["raw_state"], "broker-only")
            if role_id == "dev":
                self.assertEqual(profile["project"]["access"], "write")
                self.assertEqual(profile["filesystem_capability"]["source_root"], "write")
                self.assertIn("source-root", profile["filesystem_capability"]["host_writable"])
                self.assertIn("runtime-temp", profile["filesystem_capability"]["host_writable"])
                self.assertNotIn("temp", profile["filesystem_capability"]["host_writable"])
                self.assertNotIn("project-workspace", profile["filesystem_capability"]["host_writable"])
            else:
                self.assertEqual(profile["project"]["access"], "read-only")
                self.assertEqual(profile["filesystem_capability"]["source_root"], "read-only")
                self.assertNotIn("source-root", profile["filesystem_capability"]["host_writable"])
                self.assertIn("runtime-temp", profile["filesystem_capability"]["host_writable"])
                self.assertNotIn("temp", profile["filesystem_capability"]["host_writable"])
                self.assertNotIn("project-workspace", profile["filesystem_capability"]["host_writable"])
            if role_id == "market":
                self.assertEqual(profile["tool_capability"]["browser_cockpit"], "required")
                self.assertEqual(profile["tool_capability"]["market_research_evidence"], "required")
                self.assertEqual(profile["tool_capability"]["ordinary_web_fallback"], "user-approved-only")
            else:
                self.assertEqual(profile["tool_capability"]["browser_cockpit"], "available")
                self.assertEqual(profile["tool_capability"]["market_research_evidence"], "not-required")
            search = profile["tool_capability"]["search"]
            self.assertEqual(search["native_codex_web_search"], "disabled")
            self.assertEqual(search["browser_cockpit"], profile["tool_capability"]["browser_cockpit"])
            self.assertNotIn("default_engine", search)
            self.assertNotIn("preferred_backend", search)
            self.assertNotIn("market_workflow", search)
            self.assertEqual(
                profile["state_capability"]["task_effects"],
                ["create", "update", "priority", "status", "archive", "history"],
            )
            if role_id == "market":
                self.assertEqual(search["browser_cockpit"], "required")
                self.assertEqual(search["search_api"], "user-approved-only")
            else:
                self.assertEqual(search["browser_cockpit"], "available")
                self.assertEqual(search["search_api"], "available")
            effects = profile["state_capability"]["track_effects"]
            if effects:
                track_effects_seen.append((role_id, effects))
            self.assertEqual(
                profile["state_capability"]["request_effects"],
                ["create", "accept", "block", "complete", "cancel"],
            )
            expected_comment_effects = ["resolve"] if role_id == "pm" else []
            self.assertEqual(profile["state_capability"]["comment_effects"], expected_comment_effects)

        self.assertEqual(
            track_effects_seen,
            [
                ("market", ["update_now", "add_material", "add_update", "add_proof"]),
                ("pm", ["create", "update_now", "add_material", "add_update", "add_proof", "archive"]),
                ("design", ["update_now", "add_material", "add_update", "add_proof"]),
                ("dev", ["update_now", "add_material", "add_update", "add_proof"]),
                ("test", ["update_now", "add_material", "add_update", "add_proof"]),
            ],
        )

    def test_profile_contract_uses_source_root_permission_semantics(self) -> None:
        contract = env_profiles.profile_contract(ROOT)
        enums = contract.get("enums")
        self.assertIsInstance(enums, dict)
        assert isinstance(enums, dict)
        self.assertIn("filesystem_capability.source_root", enums)
        self.assertNotIn("filesystem_capability.project_workspace", enums)

    def test_profile_skill_projection_uses_role_profile_enum(self) -> None:
        contract_text = (ROOT / "framework/contracts/role-env-profile.json").read_text(encoding="utf-8")
        self.assertNotIn("active-role-only", contract_text)
        self.assertIn("role-profile-only", contract_text)

        for path in sorted(self.profile_root.glob("*.json")):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("active-role-only", text)
                profile = json.loads(text)
                self.assertEqual(profile["context_projection"]["skills"], "role-profile-only")

    def test_validate_all_cli(self) -> None:
        completed = subprocess.run(
            ["python3", str(ROOT / "scripts" / "env_profiles.py"), "validate-all"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(
            [line.strip() for line in completed.stdout.splitlines() if line.strip()],
            ["market: ok", "pm: ok", "design: ok", "dev: ok", "test: ok"],
        )

    def test_corrupted_temp_profile_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            (temp_root / "buddyswitch" / "env-profiles").mkdir(parents=True)
            src = ROOT / "buddyswitch" / "env-profiles" / "market.json"
            bad = json.loads(src.read_text(encoding="utf-8"))
            bad["role_id"] = "pm"
            dst = temp_root / "buddyswitch" / "env-profiles" / "market.json"
            dst.write_text(json.dumps(bad, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(env_profiles.EnvProfileError):
                env_profiles.require_env_profile(
                    "market",
                    manifest_path=self.manifest_path,
                    repo_root=temp_root,
                )

    def test_validation_rejects_profiles_with_retired_project_workspace_key(self) -> None:
        manifest = env_manifest.load_manifest(self.manifest_path)
        profile = json.loads((self.profile_root / "dev.json").read_text(encoding="utf-8"))
        profile["filesystem_capability"]["source_root"] = "write"
        profile["filesystem_capability"]["project_workspace"] = "write"
        with self.assertRaisesRegex(env_profiles.EnvProfileError, "project_workspace is retired"):
            env_profiles.validate_env_profile(
                profile,
                role_id="dev",
                manifest=manifest,
                repo_root=ROOT,
            )

    def test_search_capability_boundary_is_required_and_validated(self) -> None:
        manifest = env_manifest.load_manifest(self.manifest_path)
        market = json.loads((self.profile_root / "market.json").read_text(encoding="utf-8"))
        market["tool_capability"]["search"] = {
            "native_codex_web_search": "disabled",
            "browser_cockpit": "required",
            "search_api": "user-approved-only",
        }
        missing_search = json.loads(json.dumps(market))
        missing_search["tool_capability"].pop("search", None)
        with self.assertRaisesRegex(env_profiles.EnvProfileError, "tool_capability.search"):
            env_profiles.validate_env_profile(
                missing_search,
                role_id="market",
                manifest=manifest,
                repo_root=ROOT,
            )

        bad_api = json.loads(json.dumps(market))
        bad_api["tool_capability"]["search"]["search_api"] = "silent-fallback"
        with self.assertRaisesRegex(env_profiles.EnvProfileError, "tool_capability.search.search_api"):
            env_profiles.validate_env_profile(
                bad_api,
                role_id="market",
                manifest=manifest,
                repo_root=ROOT,
            )

        dev = json.loads((self.profile_root / "dev.json").read_text(encoding="utf-8"))
        dev["tool_capability"]["search"] = {
            "native_codex_web_search": "disabled",
            "browser_cockpit": "available",
            "search_api": "available",
        }
        dev["tool_capability"]["search"]["browser_cockpit"] = "required"
        with self.assertRaisesRegex(env_profiles.EnvProfileError, "tool_capability.search.browser_cockpit"):
            env_profiles.validate_env_profile(
                dev,
                role_id="dev",
                manifest=manifest,
                repo_root=ROOT,
            )


if __name__ == "__main__":
    unittest.main()
