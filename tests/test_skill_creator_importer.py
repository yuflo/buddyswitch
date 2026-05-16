#!/usr/bin/env python3
"""Tests for importing Codex-native skills into BuddySwitch source."""

from __future__ import annotations

import json
import subprocess
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

                [[buddies]]
                id = "pm"
                label = "PM"
                scope = "PM scope"
                skills = []
                artifact_kinds = ["prd", "pm-decision", "track-note"]
                permissions = ["track.read", "task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

                [[buddies]]
                id = "dev"
                label = "DEV"
                scope = "Dev scope"
                skills = ["implement-task"]
                artifact_kinds = ["implementation-report", "skill-import-report"]
                permissions = ["track.read", "task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

                [[buddies]]
                id = "test"
                label = "TEST"
                scope = "Test scope"
                skills = []
                artifact_kinds = ["smoke-test", "test-report"]
                permissions = ["track.read", "task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

                [[buddies]]
                id = "market"
                label = "MARKET"
                scope = "Market scope"
                skills = []
                artifact_kinds = ["market-scan", "pmf-report"]
                permissions = ["track.read", "task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

                [[buddies]]
                id = "design"
                label = "DESIGN"
                scope = "Design scope"
                skills = []
                artifact_kinds = ["design-handoff", "prototype-brief"]
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
        artifact_kind: str | None = None,
    ) -> None:
        manifest_before, target_before = self._snapshot(
            repo_root, buddy_id=buddy_id, skill_id=expected_skill_id_for_snapshot
        )
        with self.assertRaises(skill_creator_importer.SkillImportError):
            skill_creator_importer.import_skill(
                source=source,
                buddy_id=buddy_id,
                skill_id=skill_id,
                artifact_kind=artifact_kind,
                repo_root=repo_root,
            )
        manifest_after, target_after = self._snapshot(
            repo_root, buddy_id=buddy_id, skill_id=expected_skill_id_for_snapshot
        )
        self.assertEqual(manifest_after, manifest_before)
        self.assertEqual(target_after, target_before)

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
        self.assertIsNone(result.artifact_kind)
        self.assertTrue((target / "SKILL.md").exists())
        self.assertTrue((target / "assets" / "example-output.md").exists())
        self.assertTrue((target / "references" / "style-guide.md").exists())
        self.assertTrue((target / "scripts" / "helper.sh").exists())

        skill_text = (target / "SKILL.md").read_text(encoding="utf-8")
        retired_current_buddy_run = "current buddy " + "run"
        retired_persist_one_buddy_run = "persist one buddy " + "run"
        self.assertIn("## BuddySwitch Runtime Closing Rules", skill_text)
        self.assertIn("Target BuddySwitch buddy: `dev`.", skill_text)
        self.assertIn("Runtime execution uses env.tool through python3 scripts/env/client.py", skill_text)
        self.assertIn(
            "Product-readable durable state is written explicitly as task, artifact, or handoff objects.",
            skill_text,
        )
        self.assertIn("active buddy private local working files", skill_text)
        self.assertNotIn(retired_current_buddy_run, skill_text)
        self.assertNotIn("Do not call " + "persist", skill_text)
        self.assertNotIn(retired_persist_one_buddy_run, skill_text)
        self.assertNotIn("persist --skill-id", skill_text)

        manifest = env_manifest.load_manifest(repo_root / "buddyswitch" / "manifest.toml")
        skills = env_manifest.skills_by_id(manifest)
        buddies = env_manifest.buddies_by_id(manifest)
        self.assertIn("dev-summary", skills)
        self.assertEqual(set(skills["dev-summary"].keys()), {"id", "path"})
        self.assertIn("dev-summary", buddies["dev"]["skills"])
        self.assertNotIn("dev-summary", buddies["dev"]["artifact_kinds"])

    def test_import_with_explicit_artifact_kind_updates_buddy_contract(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root, package_name="community-dev-report")

        result = skill_creator_importer.import_skill(
            source=source_root,
            buddy_id="dev",
            skill_id="dev-reporter",
            artifact_kind="community-dev-report",
            repo_root=repo_root,
        )

        self.assertEqual(result.artifact_kind, "community-dev-report")
        manifest = env_manifest.load_manifest(repo_root / "buddyswitch" / "manifest.toml")
        buddies = env_manifest.buddies_by_id(manifest)
        self.assertIn("community-dev-report", buddies["dev"]["artifact_kinds"])

    def test_import_rejects_invalid_artifact_kind_without_writes(self) -> None:
        repo_root = self._create_temp_repo()
        source_root = self._create_source_package(root=repo_root)
        self._assert_failure_without_writes(
            repo_root=repo_root,
            source=source_root,
            buddy_id="dev",
            skill_id="dev-summary",
            expected_skill_id_for_snapshot="dev-summary",
            artifact_kind="Bad/Kind",
        )

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
        self.assertFalse((generated / "skill.toml").exists())

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
                "--artifact-kind",
                "community-dev-report",
                "--repo-root",
                str(repo_root),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["skill_id"], "dev-summary-cli")
        self.assertEqual(payload["buddy_id"], "dev")
        self.assertEqual(payload["package_path"], "buddyswitch/skills/dev/dev-summary-cli")
        self.assertEqual(payload["manifest_path"], "buddyswitch/manifest.toml")
        self.assertEqual(payload["artifact_kind"], "community-dev-report")
        self.assertNotIn("output_slot", payload)
        self.assertNotIn("output_schema", payload)


if __name__ == "__main__":
    unittest.main()
