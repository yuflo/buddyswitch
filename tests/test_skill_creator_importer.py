#!/usr/bin/env python3
"""Tests for importing Codex-native skills into BuddySwitch source."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import skill_creator_importer  # noqa: E402


DEFAULT_PERMISSIONS = [
    "track.read",
    "task.read",
    "task.create",
    "task.update",
    "artifact.read",
    "artifact.create",
    "artifact.update",
]


class SkillCreatorImporterTests(unittest.TestCase):
    def _create_temp_repo(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(temp_dir.cleanup)
        repo_root = Path(temp_dir.name)

        (repo_root / "buddyswitch" / "skills").mkdir(parents=True, exist_ok=True)
        (repo_root / "buddyswitch" / "skills" / "dev" / "implement-task").mkdir(parents=True, exist_ok=True)
        (repo_root / "buddyswitch" / "skills" / "dev" / "implement-task" / "SKILL.md").write_text(
            "---\nname: implement-task\ndescription: Built-in dev skill.\n---\n",
            encoding="utf-8",
        )

        schema_paths = (
            repo_root / "framework" / "schemas" / "dev" / "dev-result.json",
            repo_root / "framework" / "schemas" / "pm" / "pm-result.json",
            repo_root / "framework" / "schemas" / "test" / "test-result.json",
            repo_root / "framework" / "schemas" / "market" / "market-result.json",
            repo_root / "framework" / "schemas" / "design" / "design-result.json",
        )
        for schema_path in schema_paths:
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.write_text('{"type":"object"}\n', encoding="utf-8")

        manifest_path = repo_root / "buddyswitch" / "manifest.toml"
        manifest_path.write_text(
            textwrap.dedent(
                """\
                schema_version = 1

                [env]
                id = "demo"
                label = "Demo"

                [[skills]]
                id = "implement-task"
                path = "buddyswitch/skills/dev/implement-task"
                produces_artifact = true
                output_slot = "implementation-report"
                output_schema = "framework/schemas/dev/dev-result.json"

                [[buddies]]
                id = "pm"
                label = "PM"
                scope = "PM scope"
                skills = []
                permissions = ["track.read", "task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

                [[buddies]]
                id = "dev"
                label = "DEV"
                scope = "Dev scope"
                skills = ["implement-task"]
                permissions = ["track.read", "task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

                [[buddies]]
                id = "test"
                label = "TEST"
                scope = "Test scope"
                skills = []
                permissions = ["track.read", "task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

                [[buddies]]
                id = "market"
                label = "MARKET"
                scope = "Market scope"
                skills = []
                permissions = ["track.read", "task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

                [[buddies]]
                id = "design"
                label = "DESIGN"
                scope = "Design scope"
                skills = []
                permissions = ["track.read", "task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                """
            ),
            encoding="utf-8",
        )
        return repo_root

    def _create_source_package(
        self,
        *,
        root: Path,
        package_name: str = "community-dev-summary",
        name: str = "dev-summary",
        include_description: bool = True,
        with_skill_toml: bool = False,
        with_symlink: bool = False,
    ) -> Path:
        package_root = root / package_name
        package_root.mkdir(parents=True, exist_ok=True)

        skill_lines = ["---", f"name: {name}"]
        if include_description:
            skill_lines.append("description: Use when summarizing code changes for handoff.")
        skill_lines.extend(
            [
                "---",
                "",
                f"# {name}",
                "",
                "Summarize code changes, verification evidence, and handoff risks.",
                "",
            ]
        )
        (package_root / "SKILL.md").write_text("\n".join(skill_lines), encoding="utf-8")
        (package_root / "README.md").write_text("community skill package\n", encoding="utf-8")
        (package_root / "assets").mkdir(parents=True, exist_ok=True)
        (package_root / "assets" / "example-output.md").write_text("example output\n", encoding="utf-8")
        (package_root / "references").mkdir(parents=True, exist_ok=True)
        (package_root / "references" / "style-guide.md").write_text("style guide\n", encoding="utf-8")
        (package_root / "scripts").mkdir(parents=True, exist_ok=True)
        (package_root / "scripts" / "helper.sh").write_text("#!/usr/bin/env bash\necho helper\n", encoding="utf-8")

        if with_skill_toml:
            (package_root / "skill.toml").write_text('name = "legacy"\n', encoding="utf-8")
        if with_symlink:
            (package_root / "linked-readme.md").symlink_to("README.md")

        return package_root

    @staticmethod
    def _snapshot(repo_root: Path, *, buddy_id: str, skill_id: str) -> tuple[bytes, bool]:
        manifest_bytes = (repo_root / "buddyswitch" / "manifest.toml").read_bytes()
        target_exists = (repo_root / "buddyswitch" / "skills" / buddy_id / skill_id).exists()
        return manifest_bytes, target_exists

    def _assert_failure_without_writes(
        self,
        *,
        repo_root: Path,
        source: Path,
        buddy_id: str,
        skill_id: str | None,
        expected_skill_id_for_snapshot: str,
    ) -> None:
        manifest_before, target_before = self._snapshot(
            repo_root, buddy_id=buddy_id, skill_id=expected_skill_id_for_snapshot
        )
        with self.assertRaises(skill_creator_importer.SkillImportError):
            skill_creator_importer.import_skill(
                source=source,
                buddy_id=buddy_id,
                skill_id=skill_id,
                repo_root=repo_root,
            )
        manifest_after, target_after = self._snapshot(
            repo_root, buddy_id=buddy_id, skill_id=expected_skill_id_for_snapshot
        )
        self.assertEqual(manifest_after, manifest_before)
        self.assertEqual(target_after, target_before)

    @staticmethod
    def _read_bytes(path: Path) -> bytes:
        return path.read_bytes()

    @staticmethod
    def _script_path() -> Path:
        return ROOT / "scripts" / "skill_creator_importer.py"

    def test_imports_codex_skill_package_and_registers_target_buddy(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root, with_symlink=True)

        result = skill_creator_importer.import_skill(
            source=source_root,
            buddy_id="dev",
            skill_id="dev-summary",
            repo_root=repo_root,
        )

        target = repo_root / "buddyswitch" / "skills" / "dev" / "dev-summary"
        self.assertEqual(result.skill_id, "dev-summary")
        self.assertEqual(result.buddy_id, "dev")
        self.assertEqual(result.package_path, "buddyswitch/skills/dev/dev-summary")
        self.assertEqual(result.manifest_path, "buddyswitch/manifest.toml")
        self.assertEqual(result.output_slot, "dev-summary")
        self.assertEqual(result.output_schema, "framework/schemas/dev/dev-result.json")
        self.assertTrue((target / "SKILL.md").exists())
        self.assertTrue((target / "assets" / "example-output.md").exists())
        self.assertTrue((target / "references" / "style-guide.md").exists())
        self.assertTrue((target / "scripts" / "helper.sh").exists())
        self.assertEqual(
            self._read_bytes(source_root / "README.md"),
            self._read_bytes(target / "README.md"),
        )
        self.assertEqual(
            self._read_bytes(source_root / "assets" / "example-output.md"),
            self._read_bytes(target / "assets" / "example-output.md"),
        )
        self.assertEqual(
            self._read_bytes(source_root / "references" / "style-guide.md"),
            self._read_bytes(target / "references" / "style-guide.md"),
        )
        self.assertEqual(
            self._read_bytes(source_root / "scripts" / "helper.sh"),
            self._read_bytes(target / "scripts" / "helper.sh"),
        )

        skill_text = (target / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("# dev-summary", skill_text)
        self.assertIn("Summarize code changes, verification evidence, and handoff risks.", skill_text)
        self.assertIn("## BuddySwitch Runtime Closing Rules", skill_text)
        self.assertIn("Target BuddySwitch buddy: `dev`.", skill_text)
        self.assertIn("persist --skill-id dev-summary", skill_text)
        self.assertIn("framework/schemas/dev/dev-result.json", skill_text)
        self.assertIn("execution_summary", skill_text)
        self.assertIn("working_notes", skill_text)
        self.assertIn("deliverables_or_changed_files", skill_text)
        self.assertIn("artifact_content", skill_text)
        self.assertNotIn("result_bridge", skill_text)
        self.assertNotIn("selected_skill_packet", skill_text)
        self.assertNotIn("prepare_context.skills", skill_text)
        self.assertNotIn("runtime interception", skill_text)
        self.assertNotIn("compatibility wrapper", skill_text)
        self.assertNotIn("fallback converter", skill_text)

        manifest = env_manifest.load_manifest(repo_root / "buddyswitch" / "manifest.toml")
        skills = env_manifest.skills_by_id(manifest)
        buddies = env_manifest.buddies_by_id(manifest)
        self.assertIn("dev-summary", skills)
        self.assertEqual(skills["dev-summary"]["path"], "buddyswitch/skills/dev/dev-summary")
        self.assertTrue(skills["dev-summary"]["persistence"]["produces_artifact"])
        self.assertEqual(skills["dev-summary"]["persistence"]["output_slot"], "dev-summary")
        self.assertEqual(skills["dev-summary"]["persistence"]["output_schema"], "framework/schemas/dev/dev-result.json")
        self.assertIn("dev-summary", buddies["dev"]["skills"])
        self.assertNotIn("dev-summary", buddies["pm"]["skills"])

    def test_import_derives_skill_id_from_frontmatter_name(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root, name="Dev Summary Skill")

        result = skill_creator_importer.import_skill(
            source=source_root,
            buddy_id="dev",
            repo_root=repo_root,
        )

        self.assertEqual(result.skill_id, "dev-summary-skill")
        target = repo_root / "buddyswitch" / "skills" / "dev" / "dev-summary-skill"
        self.assertTrue((target / "SKILL.md").exists())

    def test_import_rejects_invalid_skill_id_without_writes(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        self._assert_failure_without_writes(
            repo_root=repo_root,
            source=source_root,
            buddy_id="dev",
            skill_id="Bad/Skill",
            expected_skill_id_for_snapshot="Bad/Skill",
        )

    def test_import_rejects_duplicate_skill_id_without_writes(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        self._assert_failure_without_writes(
            repo_root=repo_root,
            source=source_root,
            buddy_id="dev",
            skill_id="implement-task",
            expected_skill_id_for_snapshot="implement-task",
        )

    def test_import_rejects_duplicate_manifest_id_when_target_path_absent_without_writes(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        manifest_path = repo_root / "buddyswitch" / "manifest.toml"
        duplicate_id = "ghost-duplicate"
        target = repo_root / "buddyswitch" / "skills" / "dev" / duplicate_id
        self.assertFalse(target.exists())

        manifest_path.write_text(
            manifest_path.read_text(encoding="utf-8")
            + textwrap.dedent(
                f"""\

                [[skills]]
                id = "{duplicate_id}"
                path = "buddyswitch/skills/dev/nonexistent-path"
                produces_artifact = true
                output_slot = "{duplicate_id}"
                output_schema = "framework/schemas/dev/dev-result.json"
                """
            ),
            encoding="utf-8",
        )
        manifest_before = manifest_path.read_bytes()

        with self.assertRaisesRegex(skill_creator_importer.SkillImportError, "already exists in manifest"):
            skill_creator_importer.import_skill(
                source=source_root,
                buddy_id="dev",
                skill_id=duplicate_id,
                repo_root=repo_root,
            )

        self.assertFalse(target.exists())
        self.assertEqual(manifest_path.read_bytes(), manifest_before)

    def test_import_accepts_direct_skill_md_file(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        source_file = source_root / "SKILL.md"

        result = skill_creator_importer.import_skill(
            source=source_file,
            buddy_id="dev",
            skill_id="dev-summary-file",
            repo_root=repo_root,
        )

        self.assertEqual(result.skill_id, "dev-summary-file")
        target = repo_root / "buddyswitch" / "skills" / "dev" / "dev-summary-file"
        self.assertTrue((target / "SKILL.md").exists())
        self.assertFalse((target / "README.md").exists())
        skill_text = (target / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("BuddySwitch Runtime Closing Rules", skill_text)

    def test_import_rejects_missing_skill_md_without_writes(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = repo_root / "missing-skill-md"
        source_root.mkdir(parents=True, exist_ok=True)
        (source_root / "README.md").write_text("missing skill file\n", encoding="utf-8")

        self._assert_failure_without_writes(
            repo_root=repo_root,
            source=source_root,
            buddy_id="dev",
            skill_id="missing-skill",
            expected_skill_id_for_snapshot="missing-skill",
        )

    def test_import_rejects_missing_description_frontmatter_without_writes(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root, include_description=False)
        self._assert_failure_without_writes(
            repo_root=repo_root,
            source=source_root,
            buddy_id="dev",
            skill_id="no-description",
            expected_skill_id_for_snapshot="no-description",
        )

    def test_import_preserves_symlink_objects(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root, with_symlink=True)

        skill_creator_importer.import_skill(
            source=source_root,
            buddy_id="dev",
            skill_id="dev-symlink",
            repo_root=repo_root,
        )

        linked = repo_root / "buddyswitch" / "skills" / "dev" / "dev-symlink" / "linked-readme.md"
        self.assertTrue(linked.is_symlink())
        self.assertEqual(linked.readlink(), Path("README.md"))

    def test_import_drops_skill_toml_from_generated_package(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root, with_skill_toml=True, name="From Skill Md")

        result = skill_creator_importer.import_skill(
            source=source_root,
            buddy_id="dev",
            repo_root=repo_root,
        )

        generated = repo_root / "buddyswitch" / "skills" / "dev" / "from-skill-md"
        self.assertEqual(result.skill_id, "from-skill-md")
        self.assertTrue((generated / "SKILL.md").exists())
        self.assertFalse((generated / "skill.toml").exists())

    def test_imported_manifest_loads_with_env_manifest(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)

        skill_creator_importer.import_skill(
            source=source_root,
            buddy_id="pm",
            skill_id="pm-notes",
            repo_root=repo_root,
        )

        manifest = env_manifest.load_manifest(repo_root / "buddyswitch" / "manifest.toml")
        skills = env_manifest.skills_by_id(manifest)
        buddies = env_manifest.buddies_by_id(manifest)
        self.assertIn("pm-notes", skills)
        self.assertEqual(skills["pm-notes"]["persistence"]["output_slot"], "pm-notes")
        self.assertEqual(skills["pm-notes"]["persistence"]["output_schema"], "framework/schemas/pm/pm-result.json")
        self.assertIn("pm-notes", buddies["pm"]["skills"])
        self.assertNotIn("pm-notes", buddies["dev"]["skills"])

    def test_import_registers_expected_output_schema_for_each_buddy(self) -> None:
        cases = (
            ("dev", "dev-summary", "framework/schemas/dev/dev-result.json"),
            ("pm", "pm-notes", "framework/schemas/pm/pm-result.json"),
            ("test", "regression-notes", "framework/schemas/test/test-result.json"),
            ("market", "market-brief", "framework/schemas/market/market-result.json"),
            ("design", "ux-notes", "framework/schemas/design/design-result.json"),
        )
        for buddy_id, skill_id, expected_schema in cases:
            with self.subTest(buddy=buddy_id):
                repo_root = self._create_temp_repo()
                source_root = self._create_source_package(root=repo_root, name=skill_id)
                result = skill_creator_importer.import_skill(
                    source=source_root,
                    buddy_id=buddy_id,
                    skill_id=skill_id,
                    repo_root=repo_root,
                )
                self.assertEqual(result.output_schema, expected_schema)
                self.assertEqual(result.output_slot, skill_id)
                target = repo_root / "buddyswitch" / "skills" / buddy_id / skill_id
                self.assertTrue((target / "SKILL.md").exists())
                manifest = env_manifest.load_manifest(repo_root / "buddyswitch" / "manifest.toml")
                skills = env_manifest.skills_by_id(manifest)
                buddies = env_manifest.buddies_by_id(manifest)
                self.assertEqual(skills[skill_id]["persistence"]["output_schema"], expected_schema)
                self.assertEqual(skills[skill_id]["persistence"]["output_slot"], skill_id)
                self.assertIn(skill_id, buddies[buddy_id]["skills"])
                for other_buddy_id, buddy_row in buddies.items():
                    if other_buddy_id == buddy_id:
                        continue
                    self.assertNotIn(skill_id, buddy_row["skills"])

    def test_import_rejects_existing_target_package_without_writes(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        target = repo_root / "buddyswitch" / "skills" / "dev" / "dev-summary"
        target.mkdir(parents=True, exist_ok=True)
        existing_skill_md = target / "SKILL.md"
        existing_bytes = b"# keep-existing\n"
        existing_skill_md.write_bytes(existing_bytes)

        manifest_before = (repo_root / "buddyswitch" / "manifest.toml").read_bytes()
        with self.assertRaises(skill_creator_importer.SkillImportError):
            skill_creator_importer.import_skill(
                source=source_root,
                buddy_id="dev",
                skill_id="dev-summary",
                repo_root=repo_root,
            )
        self.assertEqual(existing_skill_md.read_bytes(), existing_bytes)
        self.assertEqual((repo_root / "buddyswitch" / "manifest.toml").read_bytes(), manifest_before)

    def test_import_rejects_missing_source_path_without_writes(self) -> None:
        repo_root = self._create_temp_repo()
        missing_source = repo_root / "does-not-exist"
        self._assert_failure_without_writes(
            repo_root=repo_root,
            source=missing_source,
            buddy_id="dev",
            skill_id="missing-source",
            expected_skill_id_for_snapshot="missing-source",
        )

    def test_import_rolls_back_staged_package_when_generated_manifest_is_invalid(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        manifest_path = repo_root / "buddyswitch" / "manifest.toml"
        manifest_before = manifest_path.read_bytes()
        target = repo_root / "buddyswitch" / "skills" / "dev" / "dev-summary"

        with mock.patch.object(
            skill_creator_importer,
            "_serialize_manifest",
            return_value='schema_version = 1\n\n[env]\nid = "demo"\nlabel = "Demo"\n',
        ):
            with self.assertRaises(skill_creator_importer.SkillImportError):
                skill_creator_importer.import_skill(
                    source=source_root,
                    buddy_id="dev",
                    skill_id="dev-summary",
                    repo_root=repo_root,
                )

        self.assertFalse(target.exists())
        self.assertEqual(manifest_path.read_bytes(), manifest_before)

    def test_import_rejects_unknown_buddy_without_writes(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        self._assert_failure_without_writes(
            repo_root=repo_root,
            source=source_root,
            buddy_id="ops",
            skill_id="ops-summary",
            expected_skill_id_for_snapshot="ops-summary",
        )

    def test_cli_import_success_prints_expected_json(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        completed = subprocess.run(
            [
                "python3",
                str(self._script_path()),
                "--source",
                str(source_root),
                "--buddy",
                "dev",
                "--skill-id",
                "dev-summary-cli",
                "--repo-root",
                str(repo_root),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stderr, "")
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["skill_id"], "dev-summary-cli")
        self.assertEqual(payload["buddy_id"], "dev")
        self.assertEqual(payload["package_path"], "buddyswitch/skills/dev/dev-summary-cli")
        self.assertEqual(payload["manifest_path"], "buddyswitch/manifest.toml")
        self.assertEqual(payload["output_slot"], "dev-summary-cli")
        self.assertEqual(payload["output_schema"], "framework/schemas/dev/dev-result.json")

    def test_cli_import_failure_returns_error_and_exit_code_one(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        manifest_path = repo_root / "buddyswitch" / "manifest.toml"
        manifest_before = manifest_path.read_bytes()
        target = repo_root / "buddyswitch" / "skills" / "ops" / "ops-summary-cli"
        self.assertFalse(target.exists())

        completed = subprocess.run(
            [
                "python3",
                str(self._script_path()),
                "--source",
                str(source_root),
                "--buddy",
                "ops",
                "--skill-id",
                "ops-summary-cli",
                "--repo-root",
                str(repo_root),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("ERROR:", completed.stderr)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
