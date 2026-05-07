#!/usr/bin/env python3
"""Tests for buddy env profile contract and profile matrix."""

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
        self.buddy_ids = [buddy["id"] for buddy in self.manifest["buddies"]]
        self.buddy_set = set(self.buddy_ids)
        self.profile_root = ROOT / "buddyswitch" / "env-profiles"

    def test_profile_files_match_manifest_buddies(self) -> None:
        files = {
            path.stem
            for path in self.profile_root.glob("*.json")
            if path.is_file()
        }
        self.assertEqual(files, self.buddy_set)

    def test_profiles_validate_with_matrix_rules(self) -> None:
        pm_track_effects_seen = []
        for buddy_id in self.buddy_ids:
            profile = env_profiles.require_env_profile(
                buddy_id,
                manifest_path=self.manifest_path,
                repo_root=ROOT,
            )
            self.assertEqual(list(profile.keys()), env_profiles.profile_contract(ROOT)["top_level_key_order"])
            self.assertEqual(profile["buddy_id"], buddy_id)
            self.assertEqual(profile["scratch"]["root"], f"runs/raw/{buddy_id}")
            self.assertEqual(profile["filesystem_capability"]["raw_state"], "broker-only")
            if buddy_id == "dev":
                self.assertEqual(profile["project"]["access"], "write")
                self.assertEqual(profile["filesystem_capability"]["project_workspace"], "write")
            else:
                self.assertEqual(profile["project"]["access"], "read-only")
                self.assertEqual(profile["filesystem_capability"]["project_workspace"], "read-only")
            if buddy_id == "market":
                self.assertEqual(profile["tool_capability"]["browser_cockpit"], "required")
                self.assertEqual(profile["tool_capability"]["market_research_evidence"], "required")
                self.assertEqual(profile["tool_capability"]["ordinary_web_fallback"], "user-approved-only")
            else:
                self.assertEqual(profile["tool_capability"]["browser_cockpit"], "available")
                self.assertEqual(profile["tool_capability"]["market_research_evidence"], "not-required")
            effects = profile["state_capability"]["track_effects"]
            if effects:
                pm_track_effects_seen.append((buddy_id, effects))

        self.assertEqual(
            pm_track_effects_seen,
            [("pm", ["create", "update", "advance", "archive"])],
        )

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
            bad["buddy_id"] = "pm"
            dst = temp_root / "buddyswitch" / "env-profiles" / "market.json"
            dst.write_text(json.dumps(bad, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(env_profiles.EnvProfileError):
                env_profiles.require_env_profile(
                    "market",
                    manifest_path=self.manifest_path,
                    repo_root=temp_root,
                )


if __name__ == "__main__":
    unittest.main()
