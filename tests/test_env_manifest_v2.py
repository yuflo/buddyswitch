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
                self.assertFalse(any(item.startswith("buddybox.") for item in permissions))
                self.assertNotIn("run.commit", permissions)
                self.assertNotIn("binding.get", permissions)
                self.assertFalse(any(item.startswith("handoff.") for item in permissions))

    def test_buddy_permissions_do_not_declare_buddybox_special_cases(self) -> None:
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            buddy_id = str(buddy.get("id"))
            permissions = set(buddy.get("permissions", []))
            with self.subTest(buddy=buddy_id):
                for permission in permissions:
                    lowered = permission.lower()
                    self.assertFalse(lowered.startswith("buddybox.read_foreign"))
                    self.assertFalse(lowered.startswith("buddybox.pm_override"))
                    self.assertFalse(lowered.startswith("buddybox." + buddy_id + "_"))
                    self.assertFalse(lowered.startswith("buddybox."))

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

    def test_buddies_do_not_receive_buddybox_tool(self) -> None:
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            buddy_id = buddy.get("id")
            permissions = {row for row in buddy.get("permissions", []) if isinstance(row, str)}
            self.assertIsInstance(buddy_id, str)
            assert isinstance(buddy_id, str)
            self.assertFalse(any(permission.startswith("buddybox.") for permission in permissions), msg=buddy_id)
            skills = {row for row in buddy.get("skills", []) if isinstance(row, str)}
            self.assertNotIn("buddybox-tool", skills, msg=buddy_id)

    def test_manifest_has_no_buddybox_tool_skill_row(self) -> None:
        rows = [
            row
            for row in self.manifest.get("skills", [])
            if isinstance(row, dict) and row.get("id") == "buddybox-tool"
        ]
        self.assertEqual(rows, [])

    def test_message_comment_and_request_permissions_are_supported(self) -> None:
        """MCT-MAN-001: Manifest validator accepts message/comment/request permission objects."""
        env_manifest._validate_permission("message.send", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("message.list", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("comment.add", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("comment.list", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("comment.resolve", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("request.read", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("request.create", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("request.accept", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("request.block", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("request.complete", "synthetic")  # noqa: SLF001
        env_manifest._validate_permission("request.cancel", "synthetic")  # noqa: SLF001

    def test_all_buddies_have_message_comment_request_tools_and_permissions(self) -> None:
        """MCT-MAN-002: Every buddy has message/comment/request tools and participant permissions."""
        required_tools = {"message-tool", "comment-tool", "request-tool"}
        required_permissions = {
            "message.send",
            "message.list",
            "comment.add",
            "comment.list",
            "request.read",
            "request.create",
            "request.accept",
            "request.block",
            "request.complete",
            "request.cancel",
        }
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            buddy_id = str(buddy.get("id"))
            skills = {row for row in buddy.get("skills", []) if isinstance(row, str)}
            permissions = {row for row in buddy.get("permissions", []) if isinstance(row, str)}
            with self.subTest(buddy=buddy_id):
                self.assertTrue(required_tools.issubset(skills), msg=f"{buddy_id} missing tools: {required_tools - skills}")
                self.assertTrue(required_permissions.issubset(permissions), msg=f"{buddy_id} missing permissions: {required_permissions - permissions}")
                if buddy_id == "pm":
                    self.assertIn("comment.resolve", permissions)
                else:
                    self.assertNotIn("comment.resolve", permissions)

    def test_pm_manifest_and_profile_exclude_track_advance(self) -> None:
        pm = next(
            row for row in self.manifest.get("buddies", []) if isinstance(row, dict) and row.get("id") == "pm"
        )
        permissions = set(pm.get("permissions", []))
        self.assertNotIn("track.advance", permissions)

    def test_buddies_use_artifact_templates_vocabulary(self) -> None:
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            with self.subTest(buddy=buddy.get("id")):
                self.assertIn("artifact_templates", buddy)
                self.assertNotIn("artifact_kinds", buddy)
                templates = buddy.get("artifact_templates")
                self.assertIsInstance(templates, list)
                assert isinstance(templates, list)
                self.assertTrue(templates)


if __name__ == "__main__":
    unittest.main()
