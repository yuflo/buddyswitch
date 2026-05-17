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

    def test_manifest_has_no_handoff_tool_skill(self) -> None:
        skill_ids = [row["id"] for row in self.manifest.get("skills", []) if isinstance(row, dict)]
        self.assertNotIn("handoff-tool", skill_ids)

    def test_buddy_permissions_are_runless(self) -> None:
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            permissions = set(buddy.get("permissions", []))
            with self.subTest(buddy=buddy.get("id")):
                self.assertFalse(any(item.startswith("memory.") for item in permissions))
                self.assertIn("buddybox.read", permissions)
                self.assertNotIn("run.commit", permissions)
                self.assertNotIn("binding.get", permissions)
                self.assertFalse(any(item.startswith("handoff.") for item in permissions))

    def test_buddy_permissions_have_no_buddybox_special_cases(self) -> None:
        expected = {"buddybox.read", "buddybox.write", "buddybox.delete"}
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            buddy_id = str(buddy.get("id"))
            permissions = set(buddy.get("permissions", []))
            with self.subTest(buddy=buddy_id):
                self.assertTrue(expected.issubset(permissions))
                for permission in permissions:
                    lowered = permission.lower()
                    self.assertFalse(lowered.startswith("buddybox.read_foreign"))
                    self.assertFalse(lowered.startswith("buddybox.pm_override"))
                    self.assertFalse(lowered.startswith("buddybox." + buddy_id + "_"))

    def test_memory_permissions_are_rejected_by_validator(self) -> None:
        with self.assertRaisesRegex(env_manifest.ManifestError, "unsupported object 'memory'"):
            env_manifest._validate_permission("memory.read", "synthetic")  # noqa: SLF001

    def test_handoff_permissions_are_rejected_by_validator(self) -> None:
        with self.assertRaisesRegex(env_manifest.ManifestError, "unsupported object 'handoff'"):
            env_manifest._validate_permission("handoff.read", "synthetic")  # noqa: SLF001

    def test_shared_skill_rows_use_id_and_path_contract(self) -> None:
        for row in self.manifest.get("skills", []):
            assert isinstance(row, dict)
            self.assertEqual(set(row.keys()), {"id", "path"})

    def test_buddybox_capable_buddies_include_buddybox_tool(self) -> None:
        buddybox_capable: set[str] = set()
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            buddy_id = buddy.get("id")
            permissions = {row for row in buddy.get("permissions", []) if isinstance(row, str)}
            if {"buddybox.read", "buddybox.write", "buddybox.delete"} & permissions:
                self.assertIsInstance(buddy_id, str)
                assert isinstance(buddy_id, str)
                buddybox_capable.add(buddy_id)
                skills = {row for row in buddy.get("skills", []) if isinstance(row, str)}
                self.assertIn("buddybox-tool", skills, msg=buddy_id)
        self.assertEqual(buddybox_capable, {"market", "pm", "design", "dev", "test"})

    def test_buddybox_tool_skill_row_points_to_shared_package(self) -> None:
        rows = [
            row
            for row in self.manifest.get("skills", [])
            if isinstance(row, dict) and row.get("id") == "buddybox-tool"
        ]
        self.assertEqual(len(rows), 1, msg=rows)
        row = rows[0]
        self.assertEqual(set(row.keys()), {"id", "path"})
        self.assertEqual(row.get("path"), "buddyswitch/skills/shared/buddybox-tool")
        self.assertTrue((ROOT / str(row["path"]) / "SKILL.md").exists())

    def test_message_and_comment_permissions_are_supported(self) -> None:
        """MCT-MAN-001: Manifest validator accepts message and comment permission objects."""
        env_manifest._validate_permission("message.send", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("message.list", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("comment.add", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("comment.list", "synthetic")  # noqa: SLF001

    def test_all_buddies_have_message_comment_tools_and_permissions(self) -> None:
        """MCT-MAN-002: Every buddy has message-tool, comment-tool, and full permissions."""
        required_tools = {"message-tool", "comment-tool"}
        required_permissions = {"message.send", "message.list", "comment.add", "comment.list"}
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            buddy_id = str(buddy.get("id"))
            skills = {row for row in buddy.get("skills", []) if isinstance(row, str)}
            permissions = {row for row in buddy.get("permissions", []) if isinstance(row, str)}
            with self.subTest(buddy=buddy_id):
                self.assertTrue(required_tools.issubset(skills), msg=f"{buddy_id} missing tools: {required_tools - skills}")
                self.assertTrue(required_permissions.issubset(permissions), msg=f"{buddy_id} missing permissions: {required_permissions - permissions}")

    def test_pm_manifest_and_profile_exclude_track_advance(self) -> None:
        pm = next(
            row for row in self.manifest.get("buddies", []) if isinstance(row, dict) and row.get("id") == "pm"
        )
        permissions = set(pm.get("permissions", []))
        self.assertNotIn("track.advance", permissions)


if __name__ == "__main__":
    unittest.main()
