#!/usr/bin/env python3
"""V2 manifest loading tests for buddy-level persistence metadata."""

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
        artifact_kinds_by_buddy: dict[str, list[str]] | None = None,
        permissions_by_buddy: dict[str, list[str]] | None = None,
    ) -> Path:
        skill_blocks: list[str] = []
        for row in skills:
            skill_blocks.append(
                textwrap.dedent(
                    f"""\
                    [[skills]]
                    id = "{row['id']}"
                    path = "{row['path']}"
                    """
                )
            )

        buddy_blocks: list[str] = []
        for buddy_id, skill_ids in buddies.items():
            permissions = permissions_by_buddy.get(buddy_id, DEFAULT_PERMISSIONS) if permissions_by_buddy else DEFAULT_PERMISSIONS
            artifact_kinds = artifact_kinds_by_buddy.get(buddy_id, ["artifact-note"]) if artifact_kinds_by_buddy else ["artifact-note"]
            skills_line = ", ".join(f'"{skill_id}"' for skill_id in skill_ids)
            permissions_line = ", ".join(f'"{permission}"' for permission in permissions)
            artifact_kinds_line = ", ".join(f'"{kind}"' for kind in artifact_kinds)
            buddy_blocks.append(
                textwrap.dedent(
                    f"""\
                    [[buddies]]
                    id = "{buddy_id}"
                    label = "{buddy_id.upper()}"
                    scope = "{buddy_id} scope"
                    skills = [{skills_line}]
                    artifact_kinds = [{artifact_kinds_line}]
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
                    }
                ],
                buddies={"dev": ["community-skill"]},
                artifact_kinds_by_buddy={"dev": ["implementation-report"]},
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
                    }
                ],
                buddies={"dev": ["missing-source-skill"]},
                artifact_kinds_by_buddy={"dev": ["implementation-report"]},
            )

            loaded = env_manifest.load_manifest(manifest_path)

        self.assertEqual(loaded["skills"][0]["path"], "does/not/exist")

    def test_load_manifest_rejects_duplicate_skill_ids(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "duplicate",
                        "path": "buddyswitch/skills/pm/write-prd",
                    },
                    {
                        "id": "duplicate",
                        "path": "buddyswitch/skills/shared/track-tool",
                    },
                ],
                buddies={"pm": ["duplicate"]},
                artifact_kinds_by_buddy={"pm": ["prd"]},
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
                    }
                ],
                buddies={"pm": ["not-declared"]},
                artifact_kinds_by_buddy={"pm": ["prd"]},
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
                    }
                ],
                buddies={"pm": ["write-prd"]},
                artifact_kinds_by_buddy={"pm": ["prd"]},
                permissions_by_buddy={"pm": ["project.read"]},
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "unsupported object"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_requires_artifact_kinds(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "demo-skill",
                        "path": "buddyswitch/skills/pm/write-prd",
                    }
                ],
                buddies={"pm": ["demo-skill"]},
                artifact_kinds_by_buddy={"pm": []},
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "artifact_kinds"):
                env_manifest.load_manifest(manifest_path)

    def test_load_manifest_rejects_invalid_artifact_kind_id(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "demo-skill",
                        "path": "buddyswitch/skills/pm/write-prd",
                    }
                ],
                buddies={"pm": ["demo-skill"]},
                artifact_kinds_by_buddy={"pm": ["PRD"]},
            )

            with self.assertRaisesRegex(env_manifest.ManifestError, "artifact_kinds"):
                env_manifest.load_manifest(manifest_path)

    def test_live_manifest_exposes_buddy_artifact_kinds_and_no_skill_persistence_payload(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        skills = {skill["id"]: skill for skill in manifest["skills"]}
        buddies = env_manifest.buddies_by_id(manifest)

        self.assertIn("write-prd", skills)
        self.assertNotIn("persistence", skills["write-prd"])
        self.assertIn("artifact_kinds", buddies["pm"])
        self.assertIn("prd", buddies["pm"]["artifact_kinds"])

    def test_buddy_authority_profile_uses_membership_and_buddy_run_persist_wording(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        authority = env_manifest.buddy_authority_profile(manifest, "pm")
        manifest_skill_ids = {row["id"] for row in manifest.get("skills", []) if isinstance(row, dict) and isinstance(row.get("id"), str)}

        self.assertEqual(
            authority["routing_skills"],
            ["write-prd", "track-tool", "artifact-tool", "task-tool"],
        )
        for removed in ("task" + "-manager", "track" + "-manager", "artifact" + "-manager"):
            self.assertNotIn(removed, manifest_skill_ids)
        self.assertIn("materialized", authority["runtime_note"])
        self.assertIn("buddy run", authority["runtime_note"].lower())


if __name__ == "__main__":
    unittest.main()
