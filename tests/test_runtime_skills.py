#!/usr/bin/env python3
"""Runtime .agents/skills installer tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SKILLS_SCRIPT = ROOT / "scripts" / "runtime_skills.py"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env_manifest import load_manifest  # noqa: E402
import runtime_skills  # noqa: E402


class RuntimeSkillsInstallerTests(unittest.TestCase):
    def _write_skill_package(
        self,
        root: Path,
        *,
        skill_id: str,
        description: str,
        with_frontmatter: bool = True,
        with_skill_toml: bool = False,
        with_asset: bool = False,
        symlink_child: bool = False,
    ) -> Path:
        package_root = root / "skills" / skill_id
        package_root.mkdir(parents=True, exist_ok=True)
        if with_frontmatter:
            text = textwrap.dedent(
                f"""\
                ---
                name: {skill_id}
                description: {description}
                ---

                # {skill_id}
                """
            )
        else:
            text = f"# {skill_id}\n"
        (package_root / "SKILL.md").write_text(text, encoding="utf-8")

        if with_skill_toml:
            (package_root / "skill.toml").write_text('id = "legacy"\n', encoding="utf-8")

        if with_asset:
            assets_dir = package_root / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            (assets_dir / f"{skill_id}.md").write_text(f"template-{skill_id}\n", encoding="utf-8")

        if symlink_child:
            target = package_root / "SKILL.md"
            os.remove(target)
            (package_root / "linked.md").write_text(text, encoding="utf-8")
            target.symlink_to("linked.md")

        return package_root

    def _write_manifest(
        self,
        root: Path,
        *,
        skills: list[dict[str, str]],
        buddies: dict[str, list[str]],
    ) -> Path:
        skill_blocks = []
        for row in skills:
            output_slot_line = f'output_slot = "{row["output_slot"]}"\n' if row.get("output_slot") else ""
            skill_blocks.append(
                textwrap.dedent(
                    f"""\
                    [[skills]]
                    id = "{row['id']}"
                    path = "{row['path']}"
                    produces_artifact = {row['produces_artifact']}
                    {output_slot_line}output_schema = "{row['output_schema']}"
                    """
                )
            )

        buddy_blocks = []
        for buddy_id, member_skills in buddies.items():
            skills_list = ", ".join(json.dumps(item) for item in member_skills)
            buddy_blocks.append(
                textwrap.dedent(
                    f"""\
                    [[buddies]]
                    id = "{buddy_id}"
                    label = "{buddy_id.upper()}"
                    scope = "{buddy_id} scope"
                    skills = [{skills_list}]
                    permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]
                    """
                )
            )

        manifest = root / "manifest.toml"
        manifest.write_text(
            "schema_version = 1\n\n[env]\nid = \"demo\"\nlabel = \"Demo\"\n\n"
            + "\n".join(skill_blocks)
            + "\n"
            + "\n".join(buddy_blocks)
            + "\n",
            encoding="utf-8",
        )
        return manifest

    def _run_install(self, *, manifest: Path, buddy: str, workspace: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(RUNTIME_SKILLS_SCRIPT),
                "install",
                "--manifest",
                str(manifest),
                "--buddy",
                buddy,
                "--workspace",
                str(workspace),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def _snapshot_regular_files(self, root: Path) -> dict[str, bytes]:
        snapshot: dict[str, bytes] = {}
        if not root.exists():
            return snapshot
        for path in sorted(root.rglob("*")):
            if path.is_file():
                snapshot[path.relative_to(root).as_posix()] = path.read_bytes()
        return snapshot

    def _seed_runtime_sentinel(self, workspace: Path, *, name: str = "sentinel.bin") -> tuple[Path, bytes]:
        runtime_skills = workspace / ".agents" / "skills"
        runtime_skills.mkdir(parents=True, exist_ok=True)
        payload = b"runtime-sentinel-v1\n"
        sentinel = runtime_skills / name
        sentinel.write_bytes(payload)
        return sentinel, payload

    def _assert_install_fails_without_mutation(
        self,
        *,
        manifest: Path,
        buddy: str,
        workspace: Path,
        expected_diagnostic: str,
    ) -> subprocess.CompletedProcess[str]:
        runtime_skills = workspace / ".agents" / "skills"
        before_snapshot = self._snapshot_regular_files(runtime_skills)
        result = self._run_install(manifest=manifest, buddy=buddy, workspace=workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(expected_diagnostic.lower(), result.stderr.lower())
        after_snapshot = self._snapshot_regular_files(runtime_skills)
        self.assertEqual(after_snapshot, before_snapshot)
        return result

    def _assert_directory_bytes_equal(self, *, source: Path, target: Path) -> None:
        source_files = sorted(path for path in source.rglob("*") if path.is_file())
        target_files = sorted(path for path in target.rglob("*") if path.is_file())
        self.assertEqual(
            [path.relative_to(source).as_posix() for path in source_files],
            [path.relative_to(target).as_posix() for path in target_files],
        )
        for src_path in source_files:
            relative = src_path.relative_to(source)
            dst_path = target / relative
            self.assertEqual(src_path.read_bytes(), dst_path.read_bytes(), msg=f"mismatch: {relative.as_posix()}")

    def test_install_materializes_only_active_buddy_skills_and_assets(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            skills_root = temp_root / "packages"
            write_prd = self._write_skill_package(
                skills_root,
                skill_id="write-prd",
                description="Write PRD",
                with_asset=True,
            )
            track_manager = self._write_skill_package(
                skills_root,
                skill_id="track-manager",
                description="Manage tracks",
            )
            shape_prototype = self._write_skill_package(
                skills_root,
                skill_id="shape-prototype",
                description="Shape prototype",
            )
            manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "write-prd",
                        "path": write_prd.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    },
                    {
                        "id": "track-manager",
                        "path": track_manager.relative_to(ROOT).as_posix(),
                        "produces_artifact": "false",
                        "output_slot": "",
                        "output_schema": "framework/schemas/pm/track-manager.json",
                    },
                    {
                        "id": "shape-prototype",
                        "path": shape_prototype.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "design-handoff",
                        "output_schema": "framework/schemas/design/design-result.json",
                    },
                ],
                buddies={"pm": ["write-prd", "track-manager"], "design": ["shape-prototype"]},
            )
            workspace = temp_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            completed = self._run_install(manifest=manifest, buddy="pm", workspace=workspace)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            runtime_skills = workspace / ".agents" / "skills"
            self.assertTrue((runtime_skills / "write-prd" / "SKILL.md").exists())
            self.assertTrue((runtime_skills / "track-manager" / "SKILL.md").exists())
            self.assertTrue((runtime_skills / "write-prd" / "assets" / "write-prd.md").exists())
            self.assertFalse((runtime_skills / "shape-prototype").exists())

    def test_install_replaces_stale_directories_when_switching_buddies(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            skills_root = temp_root / "packages"
            write_prd = self._write_skill_package(skills_root, skill_id="write-prd", description="Write PRD")
            track_manager = self._write_skill_package(skills_root, skill_id="track-manager", description="Manage tracks")
            shape_prototype = self._write_skill_package(skills_root, skill_id="shape-prototype", description="Shape prototype")
            manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "write-prd",
                        "path": write_prd.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    },
                    {
                        "id": "track-manager",
                        "path": track_manager.relative_to(ROOT).as_posix(),
                        "produces_artifact": "false",
                        "output_slot": "",
                        "output_schema": "framework/schemas/pm/track-manager.json",
                    },
                    {
                        "id": "shape-prototype",
                        "path": shape_prototype.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "design-handoff",
                        "output_schema": "framework/schemas/design/design-result.json",
                    },
                ],
                buddies={"pm": ["write-prd", "track-manager"], "design": ["shape-prototype"]},
            )
            workspace = temp_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            first = self._run_install(manifest=manifest, buddy="pm", workspace=workspace)
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            stale = workspace / ".agents" / "skills" / "stale-skill"
            stale.mkdir(parents=True, exist_ok=True)
            (stale / "SKILL.md").write_text("# stale\n", encoding="utf-8")

            second = self._run_install(manifest=manifest, buddy="design", workspace=workspace)
            self.assertEqual(second.returncode, 0, msg=second.stderr)

            runtime_skills = workspace / ".agents" / "skills"
            self.assertFalse((runtime_skills / "write-prd").exists())
            self.assertFalse((runtime_skills / "track-manager").exists())
            self.assertFalse((runtime_skills / "stale-skill").exists())
            self.assertTrue((runtime_skills / "shape-prototype" / "SKILL.md").exists())

    def test_install_fails_before_mutation_when_source_package_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            skills_root = temp_root / "packages"
            write_prd = self._write_skill_package(skills_root, skill_id="write-prd", description="Write PRD")
            manifest_ok = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "write-prd",
                        "path": write_prd.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["write-prd"]},
            )
            workspace = temp_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            first = self._run_install(manifest=manifest_ok, buddy="pm", workspace=workspace)
            self.assertEqual(first.returncode, 0, msg=first.stderr)

            before_payload = (workspace / ".agents" / "skills" / "write-prd" / "SKILL.md").read_text(encoding="utf-8")

            bad = self._write_skill_package(
                skills_root,
                skill_id="bad-skill",
                description="Bad",
                with_frontmatter=False,
            )
            manifest_bad = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "bad-skill",
                        "path": bad.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["bad-skill"]},
            )
            failed = self._run_install(manifest=manifest_bad, buddy="pm", workspace=workspace)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("frontmatter", failed.stderr.lower())

            after_payload = (workspace / ".agents" / "skills" / "write-prd" / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(before_payload, after_payload)

    def test_install_rejects_unsafe_workspace_and_manifest_paths(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            skills_root = temp_root / "packages"
            write_prd = self._write_skill_package(skills_root, skill_id="write-prd", description="Write PRD")
            manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "write-prd",
                        "path": write_prd.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["write-prd"]},
            )

            not_dir = temp_root / "workspace-file"
            not_dir.write_text("x\n", encoding="utf-8")
            bad_workspace = self._run_install(manifest=manifest, buddy="pm", workspace=not_dir)
            self.assertNotEqual(bad_workspace.returncode, 0)

            root_workspace = self._run_install(manifest=manifest, buddy="pm", workspace=Path("/"))
            self.assertNotEqual(root_workspace.returncode, 0)

            root_agents = ROOT / ".agents"
            self.assertFalse(root_agents.exists(), "precondition: source checkout root must not already contain .agents")
            try:
                source_checkout_workspace = self._run_install(manifest=manifest, buddy="pm", workspace=ROOT)
                self.assertNotEqual(source_checkout_workspace.returncode, 0)
                self.assertIn("source checkout root", source_checkout_workspace.stderr.lower())
                self.assertFalse(root_agents.exists(), "installer must not create repo-root .agents")
            finally:
                if root_agents.exists():
                    shutil.rmtree(root_agents)
                    self.fail("installer polluted source checkout root with .agents")

            workspace = temp_root / "workspace-ok"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / ".agents").symlink_to(temp_root / "other")
            symlink_agents = self._run_install(manifest=manifest, buddy="pm", workspace=workspace)
            self.assertNotEqual(symlink_agents.returncode, 0)

            workspace2 = temp_root / "workspace-ok2"
            (workspace2 / ".agents").mkdir(parents=True, exist_ok=True)
            (workspace2 / ".agents" / "skills").symlink_to(temp_root / "other2")
            symlink_skills = self._run_install(manifest=manifest, buddy="pm", workspace=workspace2)
            self.assertNotEqual(symlink_skills.returncode, 0)

            absolute_manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "write-prd",
                        "path": str(write_prd.resolve()),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["write-prd"]},
            )
            absolute_workspace = temp_root / "ws-a"
            absolute_workspace.mkdir(parents=True, exist_ok=True)
            sentinel_absolute, sentinel_absolute_bytes = self._seed_runtime_sentinel(absolute_workspace)
            absolute_path_result = self._assert_install_fails_without_mutation(
                manifest=absolute_manifest,
                buddy="pm",
                workspace=absolute_workspace,
                expected_diagnostic="repo-relative",
            )
            self.assertTrue(sentinel_absolute.exists())
            self.assertEqual(sentinel_absolute.read_bytes(), sentinel_absolute_bytes)

            escape_manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "write-prd",
                        "path": "../outside/skill",
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["write-prd"]},
            )
            escape_workspace = temp_root / "ws-b"
            escape_workspace.mkdir(parents=True, exist_ok=True)
            sentinel_escape, sentinel_escape_bytes = self._seed_runtime_sentinel(escape_workspace)
            escape_path_result = self._assert_install_fails_without_mutation(
                manifest=escape_manifest,
                buddy="pm",
                workspace=escape_workspace,
                expected_diagnostic="repository root",
            )
            self.assertTrue(sentinel_escape.exists())
            self.assertEqual(sentinel_escape.read_bytes(), sentinel_escape_bytes)

    def test_install_runtime_skills_api_rejects_source_checkout_root_workspace(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            skills_root = temp_root / "packages"
            write_prd = self._write_skill_package(skills_root, skill_id="write-prd", description="Write PRD")
            manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "write-prd",
                        "path": write_prd.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["write-prd"]},
            )

            root_agents = ROOT / ".agents"
            self.assertFalse(root_agents.exists(), "precondition: source checkout root must not already contain .agents")
            try:
                with self.assertRaisesRegex(runtime_skills.RuntimeSkillsError, "source checkout root"):
                    runtime_skills.install_runtime_skills(
                        manifest_path=manifest,
                        buddy_id="pm",
                        workspace=ROOT,
                    )
                self.assertFalse(root_agents.exists(), "direct API call must not create repo-root .agents")
            finally:
                if root_agents.exists():
                    shutil.rmtree(root_agents)
                    self.fail("direct API polluted source checkout root with .agents")

    def test_install_runtime_skills_api_rejects_filesystem_root_workspace(self) -> None:
        manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        with self.assertRaisesRegex(runtime_skills.RuntimeSkillsError, "filesystem root"):
            runtime_skills.install_runtime_skills(
                manifest_path=manifest_path,
                buddy_id="pm",
                workspace=Path("/"),
            )

    def test_install_runtime_skills_api_rejects_nonexistent_workspace_without_creating_it(self) -> None:
        manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            missing_workspace = temp_root / "missing-workspace"
            self.assertFalse(missing_workspace.exists())
            with self.assertRaisesRegex(runtime_skills.RuntimeSkillsError, "must exist as a directory"):
                runtime_skills.install_runtime_skills(
                    manifest_path=manifest_path,
                    buddy_id="pm",
                    workspace=missing_workspace,
                )
            self.assertFalse(missing_workspace.exists(), "direct API must not create missing workspace")

    def test_install_runtime_skills_api_rejects_file_workspace_without_mutating_file(self) -> None:
        manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            workspace_file = temp_root / "workspace-file"
            workspace_file.write_bytes(b"workspace-file-sentinel\n")
            before = workspace_file.read_bytes()
            with self.assertRaisesRegex(runtime_skills.RuntimeSkillsError, "must exist as a directory"):
                runtime_skills.install_runtime_skills(
                    manifest_path=manifest_path,
                    buddy_id="pm",
                    workspace=workspace_file,
                )
            self.assertEqual(workspace_file.read_bytes(), before)

    def test_install_rejects_invalid_skill_id_and_symlinked_sources(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            skills_root = temp_root / "packages"
            invalid_id_pkg = self._write_skill_package(skills_root, skill_id="bad/skill", description="Write PRD")

            bad_id_manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "bad/skill",
                        "path": invalid_id_pkg.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["bad/skill"]},
            )
            bad_id_workspace = temp_root / "ws-bad-id"
            bad_id_workspace.mkdir(parents=True, exist_ok=True)
            sentinel_bad_id, sentinel_bad_id_bytes = self._seed_runtime_sentinel(bad_id_workspace)
            bad_id_result = self._assert_install_fails_without_mutation(
                manifest=bad_id_manifest,
                buddy="pm",
                workspace=bad_id_workspace,
                expected_diagnostic="invalid skill id",
            )
            self.assertIn("bad/skill", bad_id_result.stderr)
            self.assertTrue(sentinel_bad_id.exists())
            self.assertEqual(sentinel_bad_id.read_bytes(), sentinel_bad_id_bytes)

            symlink_pkg_target = self._write_skill_package(skills_root, skill_id="source-real", description="Real")
            symlink_pkg = skills_root / "source-link"
            symlink_pkg.symlink_to(symlink_pkg_target, target_is_directory=True)
            symlink_pkg_manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "source-real",
                        "path": symlink_pkg.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["source-real"]},
            )
            symlink_workspace = temp_root / "ws-symlink-pkg"
            symlink_workspace.mkdir(parents=True, exist_ok=True)
            sentinel_symlink, sentinel_symlink_bytes = self._seed_runtime_sentinel(symlink_workspace)
            symlink_pkg_result = self._assert_install_fails_without_mutation(
                manifest=symlink_pkg_manifest,
                buddy="pm",
                workspace=symlink_workspace,
                expected_diagnostic="must not be a symlink",
            )
            self.assertIn("skill package directory", symlink_pkg_result.stderr.lower())
            self.assertTrue(sentinel_symlink.exists())
            self.assertEqual(sentinel_symlink.read_bytes(), sentinel_symlink_bytes)

            symlink_child_pkg = self._write_skill_package(
                skills_root,
                skill_id="linked-child",
                description="Linked child",
                symlink_child=True,
            )
            symlink_child_manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "linked-child",
                        "path": symlink_child_pkg.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["linked-child"]},
            )
            symlink_child_workspace = temp_root / "ws-symlink-child"
            symlink_child_workspace.mkdir(parents=True, exist_ok=True)
            sentinel_child, sentinel_child_bytes = self._seed_runtime_sentinel(symlink_child_workspace)
            symlink_child_result = self._assert_install_fails_without_mutation(
                manifest=symlink_child_manifest,
                buddy="pm",
                workspace=symlink_child_workspace,
                expected_diagnostic="must not contain symlinks",
            )
            self.assertIn("skill package content", symlink_child_result.stderr.lower())
            self.assertTrue(sentinel_child.exists())
            self.assertEqual(sentinel_child.read_bytes(), sentinel_child_bytes)

            real_parent = skills_root / "real-parent"
            parent_link_skill = self._write_skill_package(
                real_parent,
                skill_id="parent-link-skill",
                description="Parent link boundary",
            )
            linked_parent = skills_root / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            linked_parent_manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "parent-link-skill",
                        "path": (linked_parent / "skills" / "parent-link-skill").relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "prd",
                        "output_schema": "framework/schemas/pm/pm-result.json",
                    }
                ],
                buddies={"pm": ["parent-link-skill"]},
            )
            linked_parent_workspace = temp_root / "ws-linked-parent"
            linked_parent_workspace.mkdir(parents=True, exist_ok=True)
            sentinel_parent_link, sentinel_parent_link_bytes = self._seed_runtime_sentinel(linked_parent_workspace)
            linked_parent_result = self._assert_install_fails_without_mutation(
                manifest=linked_parent_manifest,
                buddy="pm",
                workspace=linked_parent_workspace,
                expected_diagnostic="symlink boundary",
            )
            self.assertIn("skill package path", linked_parent_result.stderr.lower())
            self.assertTrue(sentinel_parent_link.exists())
            self.assertEqual(sentinel_parent_link.read_bytes(), sentinel_parent_link_bytes)

    def test_install_from_repo_manifest_preserves_all_skill_files_bytes(self) -> None:
        manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        manifest_payload = load_manifest(manifest_path)
        skill_sources = {
            row["id"]: row["path"]
            for row in manifest_payload.get("skills", [])
            if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("path"), str)
        }
        buddies = [row for row in manifest_payload.get("buddies", []) if isinstance(row, dict)]
        self.assertTrue(buddies)

        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            for buddy in buddies:
                buddy_id = buddy.get("id")
                buddy_skills = buddy.get("skills", [])
                if not isinstance(buddy_id, str) or not isinstance(buddy_skills, list):
                    continue
                workspace = temp_root / f"workspace-{buddy_id}"
                workspace.mkdir(parents=True, exist_ok=True)
                completed = self._run_install(manifest=manifest_path, buddy=buddy_id, workspace=workspace)
                self.assertEqual(completed.returncode, 0, msg=f"{buddy_id}: {completed.stderr}")
                runtime_skills = workspace / ".agents" / "skills"
                installed_dirs = sorted(path.name for path in runtime_skills.iterdir() if path.is_dir())
                expected_dirs = sorted(skill_id for skill_id in buddy_skills if isinstance(skill_id, str))
                self.assertEqual(installed_dirs, expected_dirs)
                for skill_id in expected_dirs:
                    source = ROOT / skill_sources[skill_id]
                    target = runtime_skills / skill_id
                    self._assert_directory_bytes_equal(source=source, target=target)

    def test_install_materializes_registered_community_fixture_skill(self) -> None:
        fixture_package = ROOT / "tests" / "fixtures" / "community-skills" / "dev-summary"
        self.assertTrue((fixture_package / "SKILL.md").exists())
        fixture_text = (fixture_package / "SKILL.md").read_text(encoding="utf-8").lower()
        self.assertIn("buddy-level result json", fixture_text)
        self.assertIn("skill_id", fixture_text)
        self.assertIn("dev-result", fixture_text)
        self.assertNotIn("result_bridge", fixture_text)
        self.assertNotIn("implement-task.json", fixture_text)

        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            temp_root = Path(temp_dir)
            manifest = self._write_manifest(
                temp_root,
                skills=[
                    {
                        "id": "dev-summary",
                        "path": fixture_package.relative_to(ROOT).as_posix(),
                        "produces_artifact": "true",
                        "output_slot": "implementation-report",
                        "output_schema": "framework/schemas/dev/dev-result.json",
                    }
                ],
                buddies={"dev": ["dev-summary"]},
            )
            workspace = temp_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            completed = self._run_install(manifest=manifest, buddy="dev", workspace=workspace)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            installed_skill = workspace / ".agents" / "skills" / "dev-summary"
            self.assertTrue((installed_skill / "SKILL.md").exists())
            self._assert_directory_bytes_equal(source=fixture_package, target=installed_skill)


if __name__ == "__main__":
    unittest.main()
