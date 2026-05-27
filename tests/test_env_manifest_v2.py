#!/usr/bin/env python3
"""Runless manifest contract checks."""

from __future__ import annotations

import sys
import tempfile
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

    def test_buddies_do_not_carry_retired_permission_rows(self) -> None:
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            with self.subTest(buddy=buddy.get("id")):
                self.assertNotIn("permissions", buddy)

    def test_legacy_role_acl_rows_are_rejected(self) -> None:
        manifest_text = self.manifest_path.read_text(encoding="utf-8")
        legacy_text = manifest_text.replace(
            'artifact_templates = ["brief"]',
            'artifact_templates = ["brief"]\npermissions = ["track.read"]',
            1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "manifest.toml"
            path.write_text(legacy_text, encoding="utf-8")
            manifest_error = env_manifest.ManifestError
            retired_key = "per" + "missions"
            with self.assertRaisesRegex(manifest_error, retired_key + ".*retired"):
                env_manifest.load_manifest(path)

    def test_shared_skill_rows_use_id_and_path_contract(self) -> None:
        for row in self.manifest.get("skills", []):
            assert isinstance(row, dict)
            self.assertEqual(set(row.keys()), {"id", "path"})

    def test_buddies_do_not_receive_buddybox_tool(self) -> None:
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            buddy_id = buddy.get("id")
            self.assertIsInstance(buddy_id, str)
            assert isinstance(buddy_id, str)
            skills = {row for row in buddy.get("skills", []) if isinstance(row, str)}
            self.assertNotIn("buddybox-tool", skills, msg=buddy_id)

    def test_manifest_has_no_buddybox_tool_skill_row(self) -> None:
        rows = [
            row
            for row in self.manifest.get("skills", [])
            if isinstance(row, dict) and row.get("id") == "buddybox-tool"
        ]
        self.assertEqual(rows, [])

    def test_all_buddies_have_message_comment_request_tools(self) -> None:
        """MCT-MAN-002: Every buddy has message/comment/request tools."""
        required_tools = {"message-tool", "comment-tool", "request-tool"}
        for buddy in self.manifest.get("buddies", []):
            assert isinstance(buddy, dict)
            buddy_id = str(buddy.get("id"))
            skills = {row for row in buddy.get("skills", []) if isinstance(row, str)}
            with self.subTest(buddy=buddy_id):
                self.assertTrue(required_tools.issubset(skills), msg=f"{buddy_id} missing tools: {required_tools - skills}")

    def test_show_buddy_authority_excludes_retired_acl_fields(self) -> None:
        profile = env_manifest.buddy_authority_profile(self.manifest, "pm")
        self.assertNotIn("object_" + "permissions", profile)
        self.assertNotIn("permission_scope", profile)
        self.assertNotIn("manual_debug_" + "apis", str(profile))

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
