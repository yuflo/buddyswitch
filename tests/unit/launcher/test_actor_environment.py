"""Exact behavior tests for the Actor Environment Build owner."""

from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


EXPECTED_RUNTIME_COPY_PATHS = (
    "scripts/env",
    "scripts/runtime_kernel",
    "scripts/turn_runtime.py",
    "scripts/env_store.py",
    "scripts/env_legacy_store.py",
    "scripts/env_manifest.py",
    "scripts/env_profiles.py",
    "scripts/browser_evidence.py",
    "buddyswitch/manifest.toml",
    "buddyswitch/env-profiles",
    "framework/contracts",
)


class ActorEnvironmentBuilderTests(unittest.TestCase):
    def _module(self):
        module_name = "tools.launcher.actor_environment"
        self.assertIsNotNone(
            importlib.util.find_spec(module_name),
            "ActorEnvironmentBuilder must exist as the sole actor environment build owner",
        )
        return importlib.import_module(module_name)

    def _fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        repo_root = root / "repo"
        shared_root = root / "shared" / ".codex-buddyswitch"
        source_codex_home = root / "source-codex-home"

        for relative_path in EXPECTED_RUNTIME_COPY_PATHS:
            path = repo_root / relative_path
            if path.suffix or relative_path == "buddyswitch/manifest.toml":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"runtime:{relative_path}\n", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
                (path / "surface.txt").write_text(f"runtime:{relative_path}\n", encoding="utf-8")

        manifest_path = repo_root / "buddyswitch" / "manifest.toml"
        manifest_path.write_text(
            """
schema_version = 1

[env]
id = "buddyswitch"
label = "BuddySwitch"

[[skills]]
id = "role-skill"
path = "buddyswitch/skills/role-skill"

[[roles]]
id = "pm"
label = "PM"
scope = "Own product direction."
skills = ["role-skill"]
artifact_templates = ["brief"]
""".strip()
            + "\n",
            encoding="utf-8",
        )
        skill_root = repo_root / "buddyswitch" / "skills" / "role-skill"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text("# Role skill\n", encoding="utf-8")
        (skill_root / ".git").mkdir()
        (skill_root / ".git" / "config").write_text("must not copy\n", encoding="utf-8")

        role_assets = repo_root / "tools" / "launcher" / "assets" / "roles" / "pm"
        role_assets.mkdir(parents=True)
        (role_assets / "AGENTS.md").write_text("# PM runtime instructions\n", encoding="utf-8")

        project_source = repo_root / "projects" / "app"
        project_source.mkdir(parents=True)
        (project_source / "product.txt").write_text("source-v1\n", encoding="utf-8")
        (project_source / ".git").mkdir()
        (project_source / ".git" / "config").write_text("must not copy\n", encoding="utf-8")

        (repo_root / ".git").mkdir()
        (repo_root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        source_codex_home.mkdir(parents=True)
        (source_codex_home / "auth.json").write_text('{"auth_mode":"apikey"}\n', encoding="utf-8")
        return temporary, repo_root, shared_root, source_codex_home

    def _spec(self, module, repo_root: Path, shared_root: Path, source_codex_home: Path, actor_id: str = "act-pm-one"):
        return module.ActorEnvironmentSpec(
            repo_root=repo_root,
            shared_root=shared_root,
            actor_id=actor_id,
            role_id="pm",
            source_codex_home=source_codex_home,
        )

    @staticmethod
    def _git_entries(root: Path) -> list[Path]:
        if not root.exists():
            return []
        return sorted(path for path in root.rglob(".git"))

    @staticmethod
    def _seed_valid_project(repo_root: Path, shared_root: Path) -> Path:
        project_workspace = shared_root / "project" / "workspace"
        project_app = project_workspace / "projects" / "app"
        project_app.mkdir(parents=True)
        shutil.copy2(repo_root / "projects" / "app" / "product.txt", project_app / "product.txt")
        return project_workspace

    def test_build_materializes_typed_git_free_actor_environment(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()
        spec = self._spec(module, repo_root, shared_root, source_codex_home)

        result = module.ActorEnvironmentBuilder().build(spec)

        actor_root = shared_root / "instances" / "act-pm-one"
        project_workspace = shared_root / "project" / "workspace"
        self.assertIsInstance(result, module.ActorEnvironmentResult)
        self.assertEqual(result.actor_root, actor_root)
        self.assertEqual(result.workspace_dir, actor_root / "workspace")
        self.assertEqual(result.project_workspace_dir, project_workspace)
        self.assertEqual(result.private_dir, actor_root / "workspace" / "private")
        self.assertEqual(result.home_dir, actor_root / "home")
        self.assertEqual(result.codex_home_dir, actor_root / "codex-home")
        self.assertEqual(result.xdg_config_home, actor_root / "xdg-config")
        self.assertEqual(result.tmp_dir, actor_root / "tmp")
        self.assertEqual(result.installed_skills, ("role-skill",))

        for relative_path in EXPECTED_RUNTIME_COPY_PATHS:
            self.assertTrue((result.workspace_dir / relative_path).exists(), relative_path)
        self.assertEqual(
            (result.workspace_dir / "AGENTS.md").read_text(encoding="utf-8"),
            "# PM runtime instructions\n",
        )
        self.assertTrue((result.workspace_dir / ".agents" / "skills" / "role-skill" / "SKILL.md").is_file())
        self.assertTrue(result.private_dir.is_dir())
        self.assertFalse(result.private_dir.is_symlink())
        probe = result.private_dir / "writable.txt"
        probe.write_text("ok\n", encoding="utf-8")
        self.assertEqual(probe.read_text(encoding="utf-8"), "ok\n")

        project_link = result.workspace_dir / "projects" / "app"
        self.assertTrue(project_link.is_symlink())
        self.assertEqual(project_link.resolve(), (project_workspace / "projects" / "app").resolve())
        self.assertEqual((project_workspace / "projects" / "app" / "product.txt").read_text(encoding="utf-8"), "source-v1\n")
        self.assertTrue((result.codex_home_dir / "config.toml").is_file())
        self.assertTrue((result.codex_home_dir / "auth.json").is_symlink())
        self.assertEqual(
            (result.codex_home_dir / "auth.json").resolve(),
            (shared_root / "codex-home" / "auth.json").resolve(),
        )
        self.assertEqual(self._git_entries(actor_root), [])
        self.assertEqual(self._git_entries(project_workspace), [])
        for forbidden in ("tools", "tests", "docs", "README.md", "buddyswitch-codex"):
            self.assertFalse((result.workspace_dir / forbidden).exists(), forbidden)

    def test_build_seeds_shared_project_once_without_refresh(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()
        builder = module.ActorEnvironmentBuilder()
        first = builder.build(self._spec(module, repo_root, shared_root, source_codex_home, "act-pm-first"))
        project_app = first.project_workspace_dir / "projects" / "app"
        (project_app / "product.txt").write_text("user-owned\n", encoding="utf-8")
        (project_app / "sentinel.txt").write_text("preserve\n", encoding="utf-8")
        (repo_root / "projects" / "app" / "product.txt").write_text("source-v2\n", encoding="utf-8")
        (repo_root / "projects" / "app" / "new-source.txt").write_text("do not sync\n", encoding="utf-8")

        second = builder.build(self._spec(module, repo_root, shared_root, source_codex_home, "act-pm-second"))

        self.assertEqual(first.project_workspace_dir, second.project_workspace_dir)
        self.assertEqual((project_app / "product.txt").read_text(encoding="utf-8"), "user-owned\n")
        self.assertEqual((project_app / "sentinel.txt").read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse((project_app / "new-source.txt").exists())

    def test_preflight_failure_writes_nothing(self) -> None:
        module = self._module()
        cases = (
            "missing-runtime",
            "missing-role-agents",
            "invalid-actor",
            "symlink-shared-root",
            "symlink-source-auth",
            "nested-runtime-symlink",
            "nested-project-symlink",
            "nested-skill-symlink",
        )
        for case in cases:
            with self.subTest(case=case):
                _temporary, repo_root, shared_root, source_codex_home = self._fixture()
                actor_id = "act-pm-preflight"
                if case == "missing-runtime":
                    shutil.rmtree(repo_root / "scripts" / "env")
                elif case == "missing-role-agents":
                    (repo_root / "tools" / "launcher" / "assets" / "roles" / "pm" / "AGENTS.md").unlink()
                elif case == "invalid-actor":
                    actor_id = "../escape"
                elif case == "symlink-shared-root":
                    external = shared_root.parent / "external"
                    external.mkdir(parents=True)
                    shared_root.parent.mkdir(parents=True, exist_ok=True)
                    shared_root.symlink_to(external, target_is_directory=True)
                elif case == "symlink-source-auth":
                    source_auth = source_codex_home / "auth.json"
                    source_auth.unlink()
                    external_auth = source_codex_home.parent / "external-auth.json"
                    external_auth.write_text('{"auth_mode":"apikey"}\n', encoding="utf-8")
                    source_auth.symlink_to(external_auth)
                elif case == "nested-runtime-symlink":
                    (repo_root / "scripts" / "env" / "escape").symlink_to(source_codex_home)
                elif case == "nested-project-symlink":
                    (repo_root / "projects" / "app" / "escape").symlink_to(source_codex_home)
                elif case == "nested-skill-symlink":
                    (repo_root / "buddyswitch" / "skills" / "role-skill" / "escape").symlink_to(
                        source_codex_home
                    )

                spec = self._spec(module, repo_root, shared_root, source_codex_home, actor_id)
                with self.assertRaises(module.ActorEnvironmentBuildError):
                    module.ActorEnvironmentBuilder().build(spec)

                if case == "symlink-shared-root":
                    self.assertEqual(list((shared_root.parent / "external").iterdir()), [])
                else:
                    self.assertFalse(shared_root.exists())

    def test_existing_actor_target_is_rejected_without_mutation(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()
        actor_root = shared_root / "instances" / "act-pm-existing"
        actor_root.mkdir(parents=True)
        sentinel = actor_root / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")

        with self.assertRaises(module.ActorEnvironmentBuildError):
            module.ActorEnvironmentBuilder().build(
                self._spec(module, repo_root, shared_root, source_codex_home, "act-pm-existing")
            )

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse((shared_root / "project").exists())
        self.assertEqual(list((shared_root / "instances").glob(".act-pm-existing.staging-*")), [])

    def test_invalid_existing_shared_project_is_rejected_without_overwrite(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()
        project_workspace = shared_root / "project" / "workspace"
        project_workspace.mkdir(parents=True)
        sentinel = project_workspace / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")

        with self.assertRaises(module.ActorEnvironmentBuildError):
            module.ActorEnvironmentBuilder().build(self._spec(module, repo_root, shared_root, source_codex_home))

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse((shared_root / "instances" / "act-pm-one").exists())
        self.assertEqual(list((shared_root / "project").glob(".workspace.staging-*")), [])

    def test_actor_copy_failure_cleans_staging_and_does_not_publish(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()
        self._seed_valid_project(repo_root, shared_root)
        builder = module.ActorEnvironmentBuilder()

        with mock.patch.object(builder, "_copy_runtime_surface", side_effect=OSError("injected copy failure")):
            with self.assertRaises(module.ActorEnvironmentBuildError):
                builder.build(self._spec(module, repo_root, shared_root, source_codex_home))

        self.assertFalse((shared_root / "instances" / "act-pm-one").exists())
        self.assertEqual(list((shared_root / "instances").glob(".act-pm-one.staging-*")), [])

    def test_actor_validation_failure_cleans_staging_and_does_not_publish(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()
        self._seed_valid_project(repo_root, shared_root)
        builder = module.ActorEnvironmentBuilder()
        original_validate = builder._validate_actor_stage

        def inject_git(stage_root: Path, project_workspace: Path, installed_skills: tuple[str, ...]) -> None:
            (stage_root / "workspace" / ".git").mkdir()
            original_validate(stage_root, project_workspace, installed_skills)

        with mock.patch.object(builder, "_validate_actor_stage", side_effect=inject_git):
            with self.assertRaises(module.ActorEnvironmentBuildError):
                builder.build(self._spec(module, repo_root, shared_root, source_codex_home))

        self.assertFalse((shared_root / "instances" / "act-pm-one").exists())
        self.assertEqual(list((shared_root / "instances").glob(".act-pm-one.staging-*")), [])

    def test_actor_validation_rejects_nonwritable_private_directory(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()
        self._seed_valid_project(repo_root, shared_root)
        builder = module.ActorEnvironmentBuilder()
        original_materialize = builder._materialize_actor_stage

        def make_private_read_only(
            paths,
            actor_stage: Path,
            project_workspace: Path,
        ) -> tuple[str, ...]:
            installed = original_materialize(paths, actor_stage, project_workspace)
            (actor_stage / "workspace" / "private").chmod(0o500)
            return installed

        with mock.patch.object(builder, "_materialize_actor_stage", side_effect=make_private_read_only):
            with self.assertRaises(module.ActorEnvironmentBuildError):
                builder.build(self._spec(module, repo_root, shared_root, source_codex_home))

        self.assertFalse((shared_root / "instances" / "act-pm-one").exists())
        self.assertEqual(list((shared_root / "instances").glob(".act-pm-one.staging-*")), [])

    def test_actor_validation_rejects_unexpected_output_symlink(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()
        self._seed_valid_project(repo_root, shared_root)
        builder = module.ActorEnvironmentBuilder()
        original_materialize = builder._materialize_actor_stage

        def inject_symlink(
            paths,
            actor_stage: Path,
            project_workspace: Path,
        ) -> tuple[str, ...]:
            installed = original_materialize(paths, actor_stage, project_workspace)
            (actor_stage / "workspace" / "unexpected-link").symlink_to(source_codex_home)
            return installed

        with mock.patch.object(builder, "_materialize_actor_stage", side_effect=inject_symlink):
            with self.assertRaises(module.ActorEnvironmentBuildError):
                builder.build(self._spec(module, repo_root, shared_root, source_codex_home))

        self.assertFalse((shared_root / "instances" / "act-pm-one").exists())
        self.assertEqual(list((shared_root / "instances").glob(".act-pm-one.staging-*")), [])

    def test_actor_publish_failure_cleans_staging_and_does_not_publish(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()
        self._seed_valid_project(repo_root, shared_root)

        with mock.patch.object(module.os, "replace", side_effect=OSError("injected publish failure")):
            with self.assertRaises(module.ActorEnvironmentBuildError):
                module.ActorEnvironmentBuilder().build(
                    self._spec(module, repo_root, shared_root, source_codex_home)
                )

        self.assertFalse((shared_root / "instances" / "act-pm-one").exists())
        self.assertEqual(list((shared_root / "instances").glob(".act-pm-one.staging-*")), [])

    def test_project_seed_failure_cleans_staging_and_does_not_publish(self) -> None:
        module = self._module()
        _temporary, repo_root, shared_root, source_codex_home = self._fixture()

        with mock.patch.object(module.os, "replace", side_effect=OSError("injected seed publish failure")):
            with self.assertRaises(module.ActorEnvironmentBuildError):
                module.ActorEnvironmentBuilder().build(
                    self._spec(module, repo_root, shared_root, source_codex_home)
                )

        self.assertFalse((shared_root / "project" / "workspace").exists())
        self.assertEqual(list((shared_root / "project").glob(".workspace.staging-*")), [])
        self.assertFalse((shared_root / "instances" / "act-pm-one").exists())

    def test_runtime_copy_allowlist_is_exact_and_excludes_source_surfaces(self) -> None:
        module = self._module()

        self.assertEqual(module.RUNTIME_COPY_PATHS, EXPECTED_RUNTIME_COPY_PATHS)
        flattened = "\n".join(module.RUNTIME_COPY_PATHS)
        for forbidden in ("tools", "tests", "docs", "README.md", "buddyswitch-codex", ".git"):
            self.assertNotIn(forbidden, flattened)

if __name__ == "__main__":
    unittest.main()
