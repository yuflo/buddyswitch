#!/usr/bin/env python3
"""V2 manifest loading and persistence contract tests."""

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


DEFAULT_PERMISSIONS = [
    "task.read",
    "task.create",
    "task.update",
    "artifact.read",
    "artifact.create",
    "artifact.update",
]


class EnvManifestV2Tests(unittest.TestCase):
    def _write_manifest(
        self,
        root: Path,
        *,
        skills: list[dict[str, object]],
        buddies: dict[str, list[str]],
        permissions_by_buddy: dict[str, list[str]] | None = None,
    ) -> Path:
        skill_blocks: list[str] = []
        for row in skills:
            produces = row.get("produces_artifact", True)
            if isinstance(produces, bool):
                produces_value = "true" if produces else "false"
            else:
                produces_value = str(produces)
            output_slot = row.get("output_slot")
            output_slot_line = f'output_slot = "{output_slot}"\n' if output_slot is not None else ""
            skill_blocks.append(
                textwrap.dedent(
                    f"""\
                    [[skills]]
                    id = "{row['id']}"
                    path = "{row['path']}"
                    produces_artifact = {produces_value}
                    {output_slot_line}output_schema = "{row.get('output_schema', 'framework/schemas/pm/pm-result.json')}"
                    """
                )
            )

        buddy_blocks: list[str] = []
        for buddy_id, skill_ids in buddies.items():
            permissions = permissions_by_buddy.get(buddy_id, DEFAULT_PERMISSIONS) if permissions_by_buddy else DEFAULT_PERMISSIONS
            skills_line = ", ".join(f'"{skill_id}"' for skill_id in skill_ids)
            permissions_line = ", ".join(f'"{permission}"' for permission in permissions)
            buddy_blocks.append(
                textwrap.dedent(
                    f"""\
                    [[buddies]]
                    id = "{buddy_id}"
                    label = "{buddy_id.upper()}"
                    scope = "{buddy_id} scope"
                    skills = [{skills_line}]
                    permissions = [{permissions_line}]
                    """
                )
            )

        manifest_path = root / "manifest.toml"
        manifest_path.write_text(
            "schema_version = 1\n\n[env]\nid = \"demo\"\nlabel = \"Demo\"\n\n"
            + "\n".join(skill_blocks)
            + "\n"
            + "\n".join(buddy_blocks)
            + "\n",
            encoding="utf-8",
        )
        return manifest_path

    def test_load_manifest_does_not_validate_skill_package_contents(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            package_root = temp_root / "skills" / "community-skill"
            package_root.mkdir(parents=True)
            (package_root / "README.md").write_text("community package\n", encoding="utf-8")
            (package_root / "skill.toml").write_text('name = "legacy"\n', encoding="utf-8")
            (package_root / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "community-skill",
                        "path": package_root.relative_to(ROOT).as_posix(),
                        "produces_artifact": True,
                        "output_slot": "community-output",
                        "output_schema": "framework/schemas/dev/dev-result.json",
                    }
                ],
                buddies={"dev": ["community-skill"]},
            )

            loaded = env_manifest.load_manifest(manifest_path)

        self.assertEqual(loaded["skills"][0]["id"], "community-skill")
        self.assertEqual(loaded["skills"][0]["path"], package_root.relative_to(ROOT).as_posix())

    def test_load_manifest_does_not_require_skill_source_directory_for_non_materialization_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "missing-source-skill",
                        "path": "does/not/exist",
                        "produces_artifact": True,
                        "output_slot": "missing-source",
                        "output_schema": "framework/schemas/dev/dev-result.json",
                    }
                ],
                buddies={"dev": ["missing-source-skill"]},
            )

            loaded = env_manifest.load_manifest(manifest_path)

        self.assertEqual(loaded["skills"][0]["path"], "does/not/exist")

    def test_load_manifest_does_not_require_output_schema_file_for_prepare_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "schema-later",
                        "path": "buddyswitch/skills/dev/implement-task",
                        "produces_artifact": True,
                        "output_slot": "implementation-report",
                        "output_schema": "framework/schemas/dev/not-runtime-gated.json",
                    }
                ],
                buddies={"dev": ["schema-later"]},
            )

            loaded = env_manifest.load_manifest(manifest_path)

        self.assertEqual(
            loaded["skills"][0]["persistence"]["output_schema"],
            "framework/schemas/dev/not-runtime-gated.json",
        )

    def test_load_manifest_rejects_duplicate_skill_ids(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "duplicate",
                        "path": "buddyswitch/skills/pm/write-prd",
                        "produces_artifact": True,
                        "output_slot": "one",
                    },
                    {
                        "id": "duplicate",
                        "path": "buddyswitch/skills/pm/track-manager",
                        "produces_artifact": True,
                        "output_slot": "two",
                    },
                ],
                buddies={"pm": ["duplicate"]},
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "duplicate skill id"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_rejects_unknown_buddy_skill_reference(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "declared",
                        "path": "buddyswitch/skills/pm/write-prd",
                        "produces_artifact": True,
                        "output_slot": "prd",
                    }
                ],
                buddies={"pm": ["not-declared"]},
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "unknown skill"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_rejects_invalid_permission_object(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "write-prd",
                        "path": "buddyswitch/skills/pm/write-prd",
                        "produces_artifact": True,
                        "output_slot": "prd",
                    }
                ],
                buddies={"pm": ["write-prd"]},
                permissions_by_buddy={"pm": ["project.read"]},
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "unsupported object"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_requires_persistence_fields(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            missing_slot_manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "demo-skill",
                        "path": "buddyswitch/skills/pm/write-prd",
                        "produces_artifact": True,
                        "output_slot": None,
                    }
                ],
                buddies={"pm": ["demo-skill"]},
            )
            with self.assertRaisesRegex(env_manifest.ManifestError, "output_slot"):
                env_manifest.load_manifest(missing_slot_manifest)

            missing_bool_manifest = temp_root / "manifest-bad-bool.toml"
            missing_bool_manifest.write_text(
                textwrap.dedent(
                    """\
                    schema_version = 1

                    [env]
                    id = "demo"
                    label = "Demo"

                    [[skills]]
                    id = "demo-skill"
                    path = "buddyswitch/skills/pm/write-prd"
                    output_slot = "prd"
                    output_schema = "framework/schemas/pm/pm-result.json"

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

    def test_load_manifest_rejects_non_artifact_persistence(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "demo-skill",
                        "path": "buddyswitch/skills/pm/write-prd",
                        "produces_artifact": False,
                        "output_slot": None,
                    }
                ],
                buddies={"pm": ["demo-skill"]},
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "produces_artifact=false is not supported"):
                env_manifest.load_manifest(manifest_path)

    def test_live_manifest_exposes_persistence_contracts(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        skills = {skill["id"]: skill for skill in manifest["skills"]}

        self.assertEqual(skills["write-prd"]["persistence"]["output_slot"], "prd")
        self.assertTrue(skills["write-prd"]["persistence"]["produces_artifact"])
        self.assertEqual(skills["track-manager"]["persistence"]["output_slot"], "track-operation")
        self.assertTrue(skills["track-manager"]["persistence"]["produces_artifact"])

    def test_live_manifest_maps_artifact_skills_to_buddy_level_schema_metadata(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        skills = {skill["id"]: skill for skill in manifest["skills"]}

        expected_artifact_schema_by_skill = {
            "write-prd": "framework/schemas/pm/pm-result.json",
            "track-manager": "framework/schemas/pm/pm-result.json",
            "implement-task": "framework/schemas/dev/dev-result.json",
            "smoke-test": "framework/schemas/test/test-result.json",
            "shape-prototype": "framework/schemas/design/design-result.json",
            "research-scan": "framework/schemas/market/market-result.json",
            "pmf-recon": "framework/schemas/market/market-result.json",
            "customer-discovery": "framework/schemas/market/market-result.json",
            "positioning-copy": "framework/schemas/market/market-result.json",
            "channel-discovery": "framework/schemas/market/market-result.json",
            "launch-prep": "framework/schemas/market/market-result.json",
        }
        for skill_id, expected_schema in expected_artifact_schema_by_skill.items():
            with self.subTest(skill=skill_id):
                persistence = skills[skill_id]["persistence"]
                self.assertTrue(persistence["produces_artifact"])
                self.assertIsInstance(persistence["output_slot"], str)
                self.assertEqual(persistence["output_schema"], expected_schema)

    def test_buddy_authority_profile_uses_membership_and_persist_wording(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        authority = env_manifest.buddy_authority_profile(manifest, "pm")

        self.assertEqual(authority["routing_skills"], ["write-prd", "track-manager"])
        self.assertIn("materialized", authority["runtime_note"])
        self.assertIn("persist", authority["runtime_note"])


if __name__ == "__main__":
    unittest.main()
