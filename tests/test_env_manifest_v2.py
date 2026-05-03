#!/usr/bin/env python3
"""V2 manifest and Codex-native skill package tests."""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402


class EnvManifestV2Tests(unittest.TestCase):
    def _write_skill_package(
        self,
        root: Path,
        *,
        skill_id: str,
        body: str,
        with_skill_toml: bool = False,
    ) -> Path:
        package_root = root / skill_id
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "SKILL.md").write_text(textwrap.dedent(body), encoding="utf-8")
        if with_skill_toml:
            (package_root / "skill.toml").write_text('id = "legacy"\n', encoding="utf-8")
        return package_root

    def _write_manifest(
        self,
        root: Path,
        *,
        skill_id: str,
        skill_path: Path,
        produces_artifact: str = "true",
        output_schema: str = "framework/schemas/pm/write-prd.json",
        output_slot_line: str = 'output_slot = "prd"\n',
        buddy_id: str = "pm",
    ) -> Path:
        manifest_path = root / "manifest.toml"
        manifest_path.write_text(
            textwrap.dedent(
                f"""\
                schema_version = 1

                [env]
                id = "demo"
                label = "Demo"

                [[skills]]
                id = "{skill_id}"
                path = "{skill_path.relative_to(ROOT).as_posix()}"
                produces_artifact = {produces_artifact}
                {output_slot_line}output_schema = "{output_schema}"

                [[buddies]]
                id = "{buddy_id}"
                label = "PM"
                scope = "Owns scope."
                skills = ["{skill_id}"]
                permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                """
            ),
            encoding="utf-8",
        )
        return manifest_path

    def test_load_manifest_accepts_codex_native_skill_package(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = self._write_skill_package(
                temp_root,
                skill_id="demo-skill",
                body="""\
                ---
                name: demo-skill
                description: Use when demo work needs a native Codex skill.
                ---

                # demo-skill
                """,
            )
            manifest_path = self._write_manifest(
                temp_root,
                skill_id="demo-skill",
                skill_path=package_root,
            )

            loaded = env_manifest.load_manifest(manifest_path)

        skill = loaded["skills"][0]
        self.assertEqual(skill["id"], "demo-skill")
        self.assertNotIn("description", skill)
        self.assertNotIn("runtime", skill)
        persistence = skill.get("persistence")
        self.assertIsInstance(persistence, dict)
        assert isinstance(persistence, dict)
        self.assertTrue(persistence["produces_artifact"])
        self.assertEqual(persistence["output_slot"], "prd")
        self.assertEqual(persistence["output_schema"], "framework/schemas/pm/write-prd.json")

    def test_load_manifest_rejects_skill_package_without_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = self._write_skill_package(
                temp_root,
                skill_id="demo-skill",
                body="# demo-skill\n",
            )
            manifest_path = self._write_manifest(temp_root, skill_id="demo-skill", skill_path=package_root)

            with self.assertRaisesRegex(env_manifest.ManifestError, "frontmatter"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_rejects_dual_metadata_skill_toml(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = self._write_skill_package(
                temp_root,
                skill_id="demo-skill",
                with_skill_toml=True,
                body="""\
                ---
                name: demo-skill
                description: Native metadata.
                ---

                # demo-skill
                """,
            )
            manifest_path = self._write_manifest(temp_root, skill_id="demo-skill", skill_path=package_root)

            with self.assertRaisesRegex(env_manifest.ManifestError, "skill.toml"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_rejects_frontmatter_name_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = self._write_skill_package(
                temp_root,
                skill_id="demo-skill",
                body="""\
                ---
                name: wrong-name
                description: Native metadata.
                ---

                # demo-skill
                """,
            )
            manifest_path = self._write_manifest(temp_root, skill_id="demo-skill", skill_path=package_root)

            with self.assertRaisesRegex(env_manifest.ManifestError, "must match manifest skill id"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_requires_frontmatter_description(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = self._write_skill_package(
                temp_root,
                skill_id="demo-skill",
                body="""\
                ---
                name: demo-skill
                ---

                # demo-skill
                """,
            )
            manifest_path = self._write_manifest(temp_root, skill_id="demo-skill", skill_path=package_root)

            with self.assertRaisesRegex(env_manifest.ManifestError, "description"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_supports_quoted_frontmatter_description_with_colon(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = self._write_skill_package(
                temp_root,
                skill_id="demo-skill",
                body="""\
                ---
                name: "demo-skill"
                description: "Use when demo: scoped native flow."
                ---

                # demo-skill
                """,
            )
            manifest_path = self._write_manifest(temp_root, skill_id="demo-skill", skill_path=package_root)

            loaded = env_manifest.load_manifest(manifest_path)

        self.assertEqual(loaded["skills"][0]["id"], "demo-skill")

    def test_load_manifest_requires_persistence_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = self._write_skill_package(
                temp_root,
                skill_id="demo-skill",
                body="""\
                ---
                name: demo-skill
                description: Use when demo work needs native skill support.
                ---

                # demo-skill
                """,
            )
            manifest_path = self._write_manifest(
                temp_root,
                skill_id="demo-skill",
                skill_path=package_root,
                output_slot_line="",
            )
            with self.assertRaisesRegex(env_manifest.ManifestError, "output_slot"):
                env_manifest.load_manifest(manifest_path)

            missing_schema_manifest = self._write_manifest(
                temp_root,
                skill_id="demo-skill",
                skill_path=package_root,
                output_schema="framework/schemas/pm/does-not-exist.json",
            )
            with self.assertRaisesRegex(env_manifest.ManifestError, "output_schema"):
                env_manifest.load_manifest(missing_schema_manifest)

            missing_bool_manifest = temp_root / "manifest-bad-bool.toml"
            missing_bool_manifest.write_text(
                textwrap.dedent(
                    f"""\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo"

                    [[skills]]
                    id = "demo-skill"
                    path = "{package_root.relative_to(ROOT).as_posix()}"
                    output_slot = "prd"
                    output_schema = "framework/schemas/pm/write-prd.json"

                    [[buddies]]
                    id = "pm"
                    label = "PM"
                    scope = "Owns scope."
                    skills = ["demo-skill"]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(env_manifest.ManifestError, "produces_artifact"):
                env_manifest.load_manifest(missing_bool_manifest)

    def test_load_manifest_rejects_non_track_manager_non_artifact_persistence(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = self._write_skill_package(
                temp_root,
                skill_id="demo-skill",
                body="""\
                ---
                name: demo-skill
                description: Use when demo work needs native skill support.
                ---

                # demo-skill
                """,
            )
            manifest_path = self._write_manifest(
                temp_root,
                skill_id="demo-skill",
                skill_path=package_root,
                produces_artifact="false",
                output_schema="framework/schemas/pm/track-manager.json",
                output_slot_line="",
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "only track-manager currently supports non-artifact persistence"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_allows_track_manager_non_artifact_without_output_slot(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = self._write_skill_package(
                temp_root,
                skill_id="track-manager",
                body="""\
                ---
                name: track-manager
                description: Use when managing track metadata.
                ---

                # track-manager
                """,
            )
            manifest_path = self._write_manifest(
                temp_root,
                skill_id="track-manager",
                skill_path=package_root,
                produces_artifact="false",
                output_schema="framework/schemas/pm/track-manager.json",
                output_slot_line="",
            )

            loaded = env_manifest.load_manifest(manifest_path)

        persistence = loaded["skills"][0]["persistence"]
        self.assertFalse(persistence["produces_artifact"])
        self.assertIsNone(persistence["output_slot"])
        self.assertEqual(persistence["output_schema"], "framework/schemas/pm/track-manager.json")

    def test_live_manifest_exposes_persistence_contracts(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        skills = {skill["id"]: skill for skill in manifest["skills"]}

        self.assertEqual(skills["write-prd"]["persistence"]["output_slot"], "prd")
        self.assertTrue(skills["write-prd"]["persistence"]["produces_artifact"])
        self.assertEqual(skills["track-manager"]["persistence"]["output_slot"], None)
        self.assertFalse(skills["track-manager"]["persistence"]["produces_artifact"])

    def test_buddy_authority_profile_uses_membership_and_persist_wording(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        authority = env_manifest.buddy_authority_profile(manifest, "pm")

        self.assertEqual(authority["routing_skills"], ["write-prd", "track-manager"])
        self.assertIn("materialized", authority["runtime_note"])
        self.assertIn("persist", authority["runtime_note"])


if __name__ == "__main__":
    unittest.main()
