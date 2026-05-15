#!/usr/bin/env python3
"""Runless manifest contract checks."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402


class EnvManifestV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)

    def test_manifest_has_no_run_tool_skill(self) -> None:
        skill_paths = [row["path"] for row in self.manifest.get("skills", []) if isinstance(row, dict)]
        self.assertFalse(any("run-tool" in path for path in skill_paths))

    def test_buddy_permissions_are_runless(self) -> None:
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            permissions = set(buddy.get("permissions", []))
            with self.subTest(buddy=buddy.get("id")):
                self.assertIn("memory.read", permissions)
                self.assertIn("buddybox.read", permissions)
                self.assertNotIn("run.commit", permissions)
                self.assertNotIn("binding.get", permissions)

    def test_shared_skill_rows_use_id_and_path_contract(self) -> None:
        for row in self.manifest.get("skills", []):
            assert isinstance(row, dict)
            self.assertEqual(set(row.keys()), {"id", "path"})


if __name__ == "__main__":
    unittest.main()
