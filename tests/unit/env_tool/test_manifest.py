"""Runless manifest contract checks."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

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

    def test_roles_do_not_carry_retired_permission_rows(self) -> None:
        for role in self.manifest.get("roles", []):
            assert isinstance(role, dict)
            with self.subTest(role=role.get("id")):
                self.assertNotIn("permissions", role)

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

    def test_roles_do_not_receive_private_workspace_tool(self) -> None:
        for role in self.manifest.get("roles", []):
            assert isinstance(role, dict)
            role_id = role.get("id")
            self.assertIsInstance(role_id, str)
            assert isinstance(role_id, str)
            skills = {row for row in role.get("skills", []) if isinstance(row, str)}
            self.assertNotIn("actor_private-tool", skills, msg=role_id)

    def test_manifest_has_no_actor_private_tool_skill_row(self) -> None:
        rows = [
            row
            for row in self.manifest.get("skills", [])
            if isinstance(row, dict) and row.get("id") == "actor_private-tool"
        ]
        self.assertEqual(rows, [])

    def test_manifest_has_no_message_tool_skill_row(self) -> None:
        retired_id = "message" + "-tool"
        rows = [
            row
            for row in self.manifest.get("skills", [])
            if isinstance(row, dict) and row.get("id") == retired_id
        ]
        self.assertEqual(rows, [])

    def test_all_roles_have_track_tool_skill(self) -> None:
        """Every role keeps Track collaboration as a shared skill."""
        required_tools = {"track-tool"}
        retired_message_tool = "message" + "-tool"
        for role in self.manifest.get("roles", []):
            assert isinstance(role, dict)
            role_id = str(role.get("id"))
            skills = {row for row in role.get("skills", []) if isinstance(row, str)}
            with self.subTest(role=role_id):
                self.assertTrue(required_tools.issubset(skills), msg=f"{role_id} missing tools: {required_tools - skills}")
                self.assertNotIn(retired_message_tool, skills)

    def test_show_role_authority_excludes_retired_acl_fields(self) -> None:
        profile = env_manifest.role_authority_profile(self.manifest, "pm")
        self.assertNotIn("object_" + "permissions", profile)
        self.assertNotIn("permission_scope", profile)
        self.assertNotIn("manual_debug_" + "apis", str(profile))

    def test_roles_use_artifact_templates_vocabulary(self) -> None:
        for role in self.manifest.get("roles", []):
            assert isinstance(role, dict)
            with self.subTest(role=role.get("id")):
                self.assertIn("artifact_templates", role)
                self.assertNotIn("artifact_kinds", role)
                templates = role.get("artifact_templates")
                self.assertIsInstance(templates, list)
                assert isinstance(templates, list)
                self.assertTrue(templates)

    def test_manifest_loader_has_one_standard_toml_path(self) -> None:
        source = (ROOT / "scripts" / "env_manifest.py").read_text(encoding="utf-8")
        compatibility_package = "tom" + "li"
        self.assertIn("import tomllib", source)
        self.assertNotRegex(source, rf"\b{compatibility_package}\b")
        self.assertNotIn("_parse_toml_scalar", source)
        self.assertNotIn("_parse_toml_array", source)
