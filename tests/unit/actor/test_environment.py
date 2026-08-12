"""Exact behavior tests for the code-free Actor environment owner."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from buddyswitch.foundation.actor_runtime import environment as actor_environment
from buddyswitch.foundation.process_runtime.invocation import current_runtime_identity


class ActorEnvironmentBuilderTests(unittest.TestCase):
    def _roots(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        project_source = root / "projects" / "app"
        shared_root = root / "shared" / ".codex-buddyswitch"
        source_codex_home = root / "source-codex-home"
        project_source.mkdir(parents=True)
        (project_source / "product.txt").write_text("source-v1\n", encoding="utf-8")
        (project_source / ".git").mkdir()
        (project_source / ".git" / "config").write_text("must not copy\n", encoding="utf-8")
        source_codex_home.mkdir()
        (source_codex_home / "auth.json").write_text(
            '{"auth_mode":"apikey"}\n',
            encoding="utf-8",
        )
        return temporary, project_source, shared_root, source_codex_home

    @staticmethod
    def _spec(
        project_source: Path,
        shared_root: Path,
        source_codex_home: Path,
        actor_id: str = "act-pm-one",
    ) -> actor_environment.ActorEnvironmentSpec:
        return actor_environment.ActorEnvironmentSpec(
            project_source=project_source,
            shared_root=shared_root,
            actor_id=actor_id,
            source_codex_home=source_codex_home,
            runtime_identity=current_runtime_identity(),
            bootstrap=ActorEnvironmentBuilderTests._bootstrap(project_source),
        )

    @staticmethod
    def _bootstrap(project_source: Path) -> actor_environment.ResolvedActorBootstrap:
        source_root = project_source.parents[1] / "bootstrap"
        role_agents = source_root / "roles" / "pm" / "AGENTS.md"
        role_agents.parent.mkdir(parents=True, exist_ok=True)
        role_agents.write_text("# Selected PM Role\n", encoding="utf-8")
        skills: list[actor_environment.ResolvedActorSkill] = []
        for skill_id in ActorEnvironmentBuilderTests._expected_skills():
            source = source_root / "skills" / skill_id
            source.mkdir(parents=True, exist_ok=True)
            (source / "SKILL.md").write_text(
                f"# {skill_id}\n",
                encoding="utf-8",
            )
            skills.append(
                actor_environment.ResolvedActorSkill(
                    skill_id=skill_id,
                    source=source,
                )
            )
        return actor_environment.ResolvedActorBootstrap(
            source_root=source_root,
            agents_source=role_agents,
            skills=tuple(skills),
            codex_config=(
                "[skills.bundled]\n"
                "enabled = false\n\n"
                "[features]\n"
                "plugins = false\n"
                "goals = true\n"
            ),
        )

    @staticmethod
    def _expected_skills() -> tuple[str, ...]:
        return ("selected-one", "selected-two")

    def test_build_materializes_typed_git_free_actor_environment(self) -> None:
        _temporary, project_source, shared_root, source_codex_home = self._roots()
        spec = self._spec(project_source, shared_root, source_codex_home)
        result = actor_environment.ActorEnvironmentBuilder().build(spec)

        actor_root = shared_root / "instances" / "act-pm-one"
        project_workspace = shared_root / "project" / "workspace"
        self.assertEqual(result.actor_root, actor_root)
        self.assertEqual(result.private_dir, actor_root / "workspace" / "private")
        self.assertEqual(result.installed_skills, self._expected_skills())
        self.assertEqual(result.runtime_identity, current_runtime_identity().to_record())
        self.assertEqual(list(actor_root.rglob(".git")), [])
        self.assertEqual(list(project_workspace.rglob(".git")), [])
        self.assertTrue((result.codex_home_dir / "auth.json").is_symlink())
        self.assertEqual(
            (result.codex_home_dir / "auth.json").resolve(),
            (shared_root / "codex-home" / "auth.json").resolve(),
        )
        self.assertEqual(
            (result.codex_home_dir / "auth.json").read_text(encoding="utf-8"),
            '{"auth_mode":"apikey"}\n',
        )
        self.assertEqual(
            (result.codex_home_dir / "config.toml").read_text(encoding="utf-8"),
            spec.bootstrap.codex_config,
        )
        for skill_id in self._expected_skills():
            self.assertEqual(
                (
                    result.workspace_dir
                    / ".agents"
                    / "skills"
                    / skill_id
                    / "SKILL.md"
                ).read_text(encoding="utf-8"),
                f"# {skill_id}\n",
            )
        self.assertEqual(
            (result.workspace_dir / "projects" / "app").resolve(),
            (project_workspace / "projects" / "app").resolve(),
        )
        self.assertEqual(
            (project_workspace / "projects" / "app" / "product.txt").read_text(encoding="utf-8"),
            "source-v1\n",
        )
        probe = result.private_dir / "writable.txt"
        probe.write_text("ok\n", encoding="utf-8")
        self.assertEqual(probe.read_text(encoding="utf-8"), "ok\n")

    def test_actor_workspace_contains_only_selected_projection(self) -> None:
        _temporary, project_source, shared_root, source_codex_home = self._roots()
        result = actor_environment.ActorEnvironmentBuilder().build(
            self._spec(project_source, shared_root, source_codex_home)
        )

        workspace_entries = {path.name for path in result.workspace_dir.iterdir()}
        selected_skills = {
            path.name
            for path in (result.workspace_dir / ".agents" / "skills").iterdir()
        }
        forbidden = [
            relative
            for relative in (
                "scripts",
                "tools",
                "framework",
                "src",
                "tests",
                "docs",
                "buddyswitch/manifest.toml",
            )
            if (result.workspace_dir / relative).exists()
        ]

        self.assertFalse(hasattr(actor_environment, "RUNTIME_COPY_PATHS"))
        self.assertEqual(workspace_entries, {".agents", "AGENTS.md", "private", "projects"})
        self.assertEqual(selected_skills, set(self._expected_skills()))
        self.assertEqual(
            (result.workspace_dir / "AGENTS.md").read_text(encoding="utf-8"),
            "# Selected PM Role\n",
        )
        self.assertEqual(forbidden, [])

    def test_build_seeds_shared_project_once_without_refresh(self) -> None:
        _temporary, project_source, shared_root, source_codex_home = self._roots()
        builder = actor_environment.ActorEnvironmentBuilder()
        first = builder.build(
            self._spec(project_source, shared_root, source_codex_home, "act-pm-first")
        )
        project_app = first.project_workspace_dir / "projects" / "app"
        (project_app / "product.txt").write_text("user-owned\n", encoding="utf-8")
        (project_app / "sentinel.txt").write_text("preserve\n", encoding="utf-8")
        (project_source / "product.txt").write_text("source-v2\n", encoding="utf-8")

        second = builder.build(
            self._spec(project_source, shared_root, source_codex_home, "act-pm-second")
        )

        self.assertEqual(first.project_workspace_dir, second.project_workspace_dir)
        self.assertEqual((project_app / "product.txt").read_text(encoding="utf-8"), "user-owned\n")
        self.assertEqual((project_app / "sentinel.txt").read_text(encoding="utf-8"), "preserve\n")

    def test_preflight_failures_publish_nothing(self) -> None:
        for case in (
            "invalid-actor",
            "symlink-shared-root",
            "symlink-source-auth",
            "nested-project-symlink",
            "nested-skill-symlink",
        ):
            with self.subTest(case=case):
                _temporary, project_source, shared_root, source_codex_home = self._roots()
                actor_id = "act-pm-preflight"
                if case == "invalid-actor":
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
                    external_auth.write_text("{}\n", encoding="utf-8")
                    source_auth.symlink_to(external_auth)
                elif case == "nested-project-symlink":
                    (project_source / "escape").symlink_to(source_codex_home)
                spec = self._spec(
                    project_source,
                    shared_root,
                    source_codex_home,
                    actor_id,
                )
                if case == "nested-skill-symlink":
                    (spec.bootstrap.skills[0].source / "escape").symlink_to(
                        source_codex_home,
                        target_is_directory=True,
                    )

                with self.assertRaises(actor_environment.ActorEnvironmentBuildError):
                    actor_environment.ActorEnvironmentBuilder().build(spec)

                if case == "symlink-shared-root":
                    self.assertEqual(list((shared_root.parent / "external").iterdir()), [])
                else:
                    self.assertFalse(shared_root.exists())

    def test_existing_actor_target_is_rejected_without_mutation(self) -> None:
        _temporary, project_source, shared_root, source_codex_home = self._roots()
        actor_root = shared_root / "instances" / "act-pm-existing"
        actor_root.mkdir(parents=True)
        sentinel = actor_root / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")

        with self.assertRaises(actor_environment.ActorEnvironmentBuildError):
            actor_environment.ActorEnvironmentBuilder().build(
                self._spec(project_source, shared_root, source_codex_home, "act-pm-existing")
            )

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
        self.assertFalse((shared_root / "project").exists())

    def test_concurrent_project_appearance_is_preserved_and_stage_is_cleaned(self) -> None:
        _temporary, project_source, shared_root, source_codex_home = self._roots()
        project_workspace = shared_root / "project" / "workspace"
        original_replace = os.replace

        def publish_with_concurrent_project(source: Path, target: Path) -> None:
            if Path(target) == project_workspace:
                project_workspace.mkdir(parents=True)
                (project_workspace / "sentinel.txt").write_text(
                    "preserve\n",
                    encoding="utf-8",
                )
            original_replace(source, target)

        with mock.patch.object(
            actor_environment.os,
            "replace",
            side_effect=publish_with_concurrent_project,
        ):
            with self.assertRaises(actor_environment.ActorEnvironmentBuildError):
                actor_environment.ActorEnvironmentBuilder().build(
                    self._spec(project_source, shared_root, source_codex_home)
                )

        self.assertEqual(
            (project_workspace / "sentinel.txt").read_text(encoding="utf-8"),
            "preserve\n",
        )
        self.assertEqual(
            list((shared_root / "project").glob(".workspace.staging-*")),
            [],
        )
        self.assertFalse((shared_root / "instances" / "act-pm-one").exists())

    def test_concurrent_actor_appearance_is_preserved_and_stage_is_cleaned(self) -> None:
        _temporary, project_source, shared_root, source_codex_home = self._roots()
        actor_root = shared_root / "instances" / "act-pm-one"
        original_replace = os.replace

        def publish_with_concurrent_actor(source: Path, target: Path) -> None:
            if Path(target) == actor_root:
                actor_root.mkdir(parents=True)
                (actor_root / "sentinel.txt").write_text(
                    "preserve\n",
                    encoding="utf-8",
                )
            original_replace(source, target)

        with mock.patch.object(
            actor_environment.os,
            "replace",
            side_effect=publish_with_concurrent_actor,
        ):
            with self.assertRaises(actor_environment.ActorEnvironmentBuildError):
                actor_environment.ActorEnvironmentBuilder().build(
                    self._spec(project_source, shared_root, source_codex_home)
                )

        self.assertEqual(
            (actor_root / "sentinel.txt").read_text(encoding="utf-8"),
            "preserve\n",
        )
        self.assertEqual(
            list((shared_root / "instances").glob(".act-pm-one.staging-*")),
            [],
        )

    def test_validation_failure_cleans_staging_and_does_not_publish(self) -> None:
        _temporary, project_source, shared_root, source_codex_home = self._roots()
        builder = actor_environment.ActorEnvironmentBuilder()
        original_validate = builder._validate_actor_stage

        def inject_git(
            stage_root: Path,
            project_workspace: Path,
            installed_skills: tuple[str, ...],
        ) -> None:
            (stage_root / "workspace" / ".git").mkdir()
            original_validate(stage_root, project_workspace, installed_skills)

        with mock.patch.object(builder, "_validate_actor_stage", side_effect=inject_git):
            with self.assertRaises(actor_environment.ActorEnvironmentBuildError):
                builder.build(self._spec(project_source, shared_root, source_codex_home))

        self.assertFalse((shared_root / "instances" / "act-pm-one").exists())
        self.assertEqual(list((shared_root / "instances").glob(".act-pm-one.staging-*")), [])
