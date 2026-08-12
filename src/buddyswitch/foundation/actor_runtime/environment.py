"""Publish one complete, Git-free Actor environment from resolved inputs."""

from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from buddyswitch.foundation.process_runtime.invocation import (
    RuntimeIdentity,
    current_runtime_identity,
)

_ACTOR_ID_RE = re.compile(r"^act-[A-Za-z0-9._-]+$")
_SKILL_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]*$")
_FORBIDDEN_WORKSPACE_ENTRIES = (
    "buddyswitch",
    "framework",
    "scripts",
    "src",
    "tools",
    "tests",
    "docs",
    "README.md",
    "buddyswitch-codex",
    "runs",
)


class ActorEnvironmentBuildError(RuntimeError):
    """Raised when an Actor environment cannot be safely built or validated."""


@dataclass(frozen=True)
class ResolvedActorSkill:
    """One application-selected Skill source for Actor publication."""

    skill_id: str
    source: Path


@dataclass(frozen=True)
class ResolvedActorBootstrap:
    """Explicit application-selected bootstrap projection."""

    source_root: Path
    agents_source: Path
    skills: tuple[ResolvedActorSkill, ...]
    codex_config: str


@dataclass(frozen=True)
class ActorEnvironmentSpec:
    project_source: Path
    shared_root: Path
    actor_id: str
    source_codex_home: Path
    runtime_identity: RuntimeIdentity
    bootstrap: ResolvedActorBootstrap


@dataclass(frozen=True)
class ActorEnvironmentResult:
    actor_root: Path
    workspace_dir: Path
    project_workspace_dir: Path
    private_dir: Path
    home_dir: Path
    codex_home_dir: Path
    xdg_config_home: Path
    tmp_dir: Path
    installed_skills: tuple[str, ...]
    runtime_identity: dict[str, object]


@dataclass(frozen=True)
class _BuildPaths:
    shared_root: Path
    source_codex_home: Path
    source_project_app: Path
    project_workspace: Path
    actor_root: Path
    runtime_identity: RuntimeIdentity
    bootstrap: ResolvedActorBootstrap


class ActorEnvironmentBuilder:
    """Sole owner of the fixed Actor environment filesystem build SOP."""

    def build(self, spec: ActorEnvironmentSpec) -> ActorEnvironmentResult:
        paths, planned_skills = self._preflight(spec)
        project_workspace = self._ensure_project_environment(paths)
        actor_stage: Path | None = None
        try:
            actor_stage = self._create_actor_stage(paths)
            installed_skills = self._materialize_actor_stage(
                paths,
                actor_stage,
                project_workspace,
            )
            if installed_skills != planned_skills:
                raise ActorEnvironmentBuildError(
                    "runtime skill install result did not match the validated role plan"
                )
            self._validate_actor_stage(actor_stage, project_workspace, installed_skills)
            os.replace(actor_stage, paths.actor_root)
            actor_stage = None
            return self._result(
                paths.actor_root,
                project_workspace,
                installed_skills,
                paths.runtime_identity,
            )
        except ActorEnvironmentBuildError:
            raise
        except Exception as exc:
            raise ActorEnvironmentBuildError(f"actor environment build failed: {exc}") from exc
        finally:
            if actor_stage is not None:
                _remove_owned_tree(actor_stage)

    def _preflight(
        self,
        spec: ActorEnvironmentSpec,
    ) -> tuple[_BuildPaths, tuple[str, ...]]:
        if not isinstance(spec, ActorEnvironmentSpec):
            raise ActorEnvironmentBuildError("build spec must be ActorEnvironmentSpec")
        if not _ACTOR_ID_RE.fullmatch(spec.actor_id):
            raise ActorEnvironmentBuildError(f"invalid actor id: {spec.actor_id}")
        bootstrap = self._validate_bootstrap(spec.bootstrap)

        project_source = _normalize_existing_directory(
            spec.project_source,
            "source projects/app",
        )
        active_runtime = current_runtime_identity()
        if spec.runtime_identity != active_runtime:
            raise ActorEnvironmentBuildError(
                "Actor build runtime identity does not match the activated runtime"
            )
        shared_root = _normalize_output_root(spec.shared_root, "shared root")
        raw_source_codex_home = spec.source_codex_home.expanduser()
        if raw_source_codex_home.is_symlink():
            raise ActorEnvironmentBuildError(
                f"source Codex home must not be a symlink: {raw_source_codex_home}"
            )
        source_codex_home = raw_source_codex_home.resolve(strict=False)
        if source_codex_home.exists() and not source_codex_home.is_dir():
            raise ActorEnvironmentBuildError(
                f"source Codex home must be a directory: {source_codex_home}"
            )
        source_auth = source_codex_home / "auth.json"
        if source_auth.is_symlink() or (source_auth.exists() and not source_auth.is_file()):
            raise ActorEnvironmentBuildError(
                f"source auth must be a real file when present: {source_auth}"
            )

        project_workspace = shared_root / "project" / "workspace"
        actor_root = shared_root / "instances" / spec.actor_id
        _require_under_root(project_workspace, shared_root, "project workspace")
        _require_under_root(actor_root, shared_root, "actor root")
        _reject_symlink(shared_root / "project", "project root")
        _reject_symlink(project_workspace, "project workspace")
        _reject_symlink(shared_root / "instances", "instances root")
        _reject_symlink(actor_root, "actor root")
        if actor_root.exists():
            raise ActorEnvironmentBuildError(f"actor environment already exists: {actor_root}")

        source_project_app = project_source
        _reject_unexpected_symlinks(
            source_project_app,
            "source projects/app",
            ignored_names={".git"},
        )
        planned_skills = tuple(skill.skill_id for skill in bootstrap.skills)

        paths = _BuildPaths(
            shared_root=shared_root,
            source_codex_home=source_codex_home,
            source_project_app=source_project_app,
            project_workspace=project_workspace,
            actor_root=actor_root,
            runtime_identity=spec.runtime_identity,
            bootstrap=bootstrap,
        )
        if project_workspace.exists():
            self._validate_project_environment(project_workspace, shared_root)
        return paths, planned_skills

    @staticmethod
    def _validate_bootstrap(
        bootstrap: ResolvedActorBootstrap,
    ) -> ResolvedActorBootstrap:
        if not isinstance(bootstrap, ResolvedActorBootstrap):
            raise ActorEnvironmentBuildError(
                "build bootstrap must be ResolvedActorBootstrap"
            )
        source_root = _normalize_existing_directory(
            bootstrap.source_root,
            "bootstrap source root",
        )
        agents_source = _normalized_source_file(
            bootstrap.agents_source,
            source_root,
            "role AGENTS",
        )
        if not isinstance(bootstrap.skills, tuple) or not bootstrap.skills:
            raise ActorEnvironmentBuildError(
                "resolved bootstrap must include at least one Skill"
            )
        resolved_skills: list[ResolvedActorSkill] = []
        seen_skill_ids: set[str] = set()
        for skill in bootstrap.skills:
            if not isinstance(skill, ResolvedActorSkill):
                raise ActorEnvironmentBuildError(
                    "resolved bootstrap Skills must be ResolvedActorSkill"
                )
            if not _SKILL_ID_RE.fullmatch(skill.skill_id):
                raise ActorEnvironmentBuildError(
                    f"invalid resolved Skill id: {skill.skill_id}"
                )
            if skill.skill_id in seen_skill_ids:
                raise ActorEnvironmentBuildError(
                    f"duplicate resolved Skill id: {skill.skill_id}"
                )
            seen_skill_ids.add(skill.skill_id)
            source = _normalized_source_directory(
                skill.source,
                source_root,
                f"runtime Skill '{skill.skill_id}'",
            )
            _reject_unexpected_symlinks(
                source,
                f"runtime Skill '{skill.skill_id}'",
                ignored_names={".git"},
            )
            resolved_skills.append(
                ResolvedActorSkill(skill_id=skill.skill_id, source=source)
            )
        if (
            not isinstance(bootstrap.codex_config, str)
            or not bootstrap.codex_config.strip()
        ):
            raise ActorEnvironmentBuildError(
                "resolved bootstrap Codex config must be non-empty text"
            )
        return ResolvedActorBootstrap(
            source_root=source_root,
            agents_source=agents_source,
            skills=tuple(resolved_skills),
            codex_config=bootstrap.codex_config,
        )

    def _ensure_project_environment(self, paths: _BuildPaths) -> Path:
        if paths.project_workspace.exists():
            self._validate_project_environment(paths.project_workspace, paths.shared_root)
            return paths.project_workspace

        project_parent = paths.project_workspace.parent
        project_parent.mkdir(parents=True, exist_ok=True)
        stage = Path(
            tempfile.mkdtemp(
                prefix=".workspace.staging-",
                dir=project_parent,
            )
        )
        try:
            target = stage / "projects" / "app"
            target.parent.mkdir(parents=True)
            _copy_git_free(paths.source_project_app, target)
            self._validate_project_environment(stage, paths.shared_root)
            if paths.project_workspace.exists() or paths.project_workspace.is_symlink():
                raise ActorEnvironmentBuildError(
                    f"project environment appeared during publish: {paths.project_workspace}"
                )
            os.replace(stage, paths.project_workspace)
            stage = None
            return paths.project_workspace
        except ActorEnvironmentBuildError:
            raise
        except Exception as exc:
            raise ActorEnvironmentBuildError(f"shared project seed failed: {exc}") from exc
        finally:
            if stage is not None:
                _remove_owned_tree(stage)

    def _create_actor_stage(self, paths: _BuildPaths) -> Path:
        instances_root = paths.actor_root.parent
        instances_root.mkdir(parents=True, exist_ok=True)
        return Path(
            tempfile.mkdtemp(
                prefix=f".{paths.actor_root.name}.staging-",
                dir=instances_root,
            )
        )

    def _materialize_actor_stage(
        self,
        paths: _BuildPaths,
        actor_stage: Path,
        project_workspace: Path,
    ) -> tuple[str, ...]:
        workspace = actor_stage / "workspace"
        private_dir = workspace / "private"
        home_dir = actor_stage / "home"
        codex_home_dir = actor_stage / "codex-home"
        xdg_config_home = actor_stage / "xdg-config"
        tmp_dir = actor_stage / "tmp"
        runtime_dir = actor_stage / "runtime"
        browser_dir = actor_stage / "browser"
        for directory in (
            workspace,
            private_dir,
            home_dir,
            codex_home_dir,
            xdg_config_home,
            tmp_dir,
            runtime_dir,
            browser_dir,
        ):
            directory.mkdir(parents=True, exist_ok=False)

        (codex_home_dir / "config.toml").write_text(
            paths.bootstrap.codex_config,
            encoding="utf-8",
        )
        self._install_auth_surface(paths, codex_home_dir)
        shutil.copy2(
            paths.bootstrap.agents_source,
            workspace / "AGENTS.md",
            follow_symlinks=False,
        )
        try:
            skills_dir = workspace / ".agents" / "skills"
            skills_dir.mkdir(parents=True)
            installed_skill_ids: list[str] = []
            for skill in paths.bootstrap.skills:
                _copy_git_free(skill.source, skills_dir / skill.skill_id)
                installed_skill_ids.append(skill.skill_id)
            installed_skills = tuple(installed_skill_ids)
        except OSError as exc:
            raise ActorEnvironmentBuildError(f"runtime skill installation failed: {exc}") from exc

        project_link = workspace / "projects" / "app"
        project_link.parent.mkdir(parents=True)
        project_link.symlink_to(project_workspace / "projects" / "app", target_is_directory=True)
        return installed_skills

    def _install_auth_surface(self, paths: _BuildPaths, codex_home_dir: Path) -> None:
        shared_codex_home = paths.shared_root / "codex-home"
        _reject_symlink(shared_codex_home, "shared Codex home")
        shared_codex_home.mkdir(parents=True, exist_ok=True)
        shared_auth = shared_codex_home / "auth.json"
        _reject_symlink(shared_auth, "shared auth")
        source_auth = paths.source_codex_home / "auth.json"
        if not shared_auth.exists() and source_auth.is_file():
            auth_stage = shared_codex_home / f".auth.json.staging-{os.getpid()}"
            try:
                shutil.copy2(source_auth, auth_stage, follow_symlinks=False)
                if shared_auth.exists() or shared_auth.is_symlink():
                    raise ActorEnvironmentBuildError(
                        f"shared auth appeared during publish: {shared_auth}"
                    )
                os.replace(auth_stage, shared_auth)
            finally:
                auth_stage.unlink(missing_ok=True)
        if shared_auth.is_file():
            (codex_home_dir / "auth.json").symlink_to(shared_auth)

    def _validate_project_environment(self, project_workspace: Path, shared_root: Path) -> None:
        _reject_symlink(project_workspace, "project workspace")
        if not project_workspace.is_dir():
            raise ActorEnvironmentBuildError(
                f"project environment must be a directory: {project_workspace}"
            )
        _require_under_root(project_workspace, shared_root, "project workspace")
        project_app = project_workspace / "projects" / "app"
        if project_app.is_symlink() or not project_app.is_dir():
            raise ActorEnvironmentBuildError(
                f"project environment is missing a real projects/app directory: {project_app}"
            )
        _reject_unexpected_symlinks(project_workspace, "project environment")
        _reject_git_entries(project_workspace, "project environment")

    def _validate_actor_stage(
        self,
        stage_root: Path,
        project_workspace: Path,
        installed_skills: tuple[str, ...],
    ) -> None:
        shared_root = project_workspace.parent.parent
        _require_under_root(stage_root, shared_root, "actor environment")
        workspace = stage_root / "workspace"
        required_directories = (
            workspace,
            workspace / "private",
            stage_root / "home",
            stage_root / "codex-home",
            stage_root / "xdg-config",
            stage_root / "tmp",
            stage_root / "runtime",
            stage_root / "browser",
        )
        for directory in required_directories:
            if directory.is_symlink() or not directory.is_dir():
                raise ActorEnvironmentBuildError(
                    f"actor environment required directory is invalid: {directory}"
                )
        private_mode = (workspace / "private").stat().st_mode
        if not private_mode & stat.S_IWUSR or not private_mode & stat.S_IXUSR:
            raise ActorEnvironmentBuildError(
                "actor environment private directory must be owner-writable"
            )
        config_path = stage_root / "codex-home" / "config.toml"
        if config_path.is_symlink() or not config_path.is_file():
            raise ActorEnvironmentBuildError(
                f"actor environment is missing base Codex config: {config_path}"
            )
        shared_codex_home = shared_root / "codex-home"
        _reject_symlink(shared_codex_home, "shared Codex home")
        shared_auth = shared_codex_home / "auth.json"
        actor_auth = stage_root / "codex-home" / "auth.json"
        if shared_auth.is_symlink() or (shared_auth.exists() and not shared_auth.is_file()):
            raise ActorEnvironmentBuildError(
                f"shared auth must be a real file when present: {shared_auth}"
            )
        if shared_auth.is_file():
            if (
                not actor_auth.is_symlink()
                or actor_auth.resolve(strict=False) != shared_auth.resolve(strict=True)
            ):
                raise ActorEnvironmentBuildError(
                    "actor environment auth must project the shared auth file"
                )
        elif actor_auth.exists() or actor_auth.is_symlink():
            raise ActorEnvironmentBuildError(
                "actor environment auth exists without a shared auth file"
            )
        if shared_codex_home.exists():
            _reject_git_entries(shared_codex_home, "shared Codex home")
        if not (workspace / "AGENTS.md").is_file():
            raise ActorEnvironmentBuildError("actor environment is missing role AGENTS.md")
        for skill_id in installed_skills:
            skill_root = workspace / ".agents" / "skills" / skill_id
            if skill_root.is_symlink() or not skill_root.is_dir():
                raise ActorEnvironmentBuildError(
                    f"actor environment is missing runtime skill: {skill_id}"
                )
        project_link = workspace / "projects" / "app"
        if not project_link.is_symlink():
            raise ActorEnvironmentBuildError(
                "actor environment projects/app must be the shared project projection"
            )
        expected_project = (project_workspace / "projects" / "app").resolve(strict=True)
        if project_link.resolve(strict=True) != expected_project:
            raise ActorEnvironmentBuildError(
                "actor environment projects/app points outside the shared project environment"
            )
        for relative_path in _FORBIDDEN_WORKSPACE_ENTRIES:
            if (workspace / relative_path).exists() or (workspace / relative_path).is_symlink():
                raise ActorEnvironmentBuildError(
                    f"actor environment contains forbidden source surface: {relative_path}"
                )
        allowed_symlinks = {project_link}
        if shared_auth.is_file():
            allowed_symlinks.add(actor_auth)
        _reject_unexpected_symlinks(
            stage_root,
            "actor environment",
            allowed=allowed_symlinks,
        )
        _reject_git_entries(stage_root, "actor environment")

    @staticmethod
    def _result(
        actor_root: Path,
        project_workspace: Path,
        installed_skills: tuple[str, ...],
        runtime_identity: RuntimeIdentity,
    ) -> ActorEnvironmentResult:
        return ActorEnvironmentResult(
            actor_root=actor_root,
            workspace_dir=actor_root / "workspace",
            project_workspace_dir=project_workspace,
            private_dir=actor_root / "workspace" / "private",
            home_dir=actor_root / "home",
            codex_home_dir=actor_root / "codex-home",
            xdg_config_home=actor_root / "xdg-config",
            tmp_dir=actor_root / "tmp",
            installed_skills=installed_skills,
            runtime_identity=runtime_identity.to_record(),
        )


def _normalize_existing_directory(path: Path, label: str) -> Path:
    candidate = path.expanduser()
    if candidate.is_symlink() or not candidate.is_dir():
        raise ActorEnvironmentBuildError(f"{label} must be a real directory: {candidate}")
    return candidate.resolve(strict=True)


def _normalize_output_root(path: Path, label: str) -> Path:
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise ActorEnvironmentBuildError(f"{label} must not be a symlink: {candidate}")
    if candidate.exists() and not candidate.is_dir():
        raise ActorEnvironmentBuildError(f"{label} must be a directory: {candidate}")
    return candidate.resolve(strict=False)


def _require_under_root(path: Path, root: Path, label: str) -> None:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise ActorEnvironmentBuildError(f"{label} must stay under shared root: {path}") from exc


def _reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ActorEnvironmentBuildError(f"{label} must not be a symlink: {path}")


def _require_source_path(path: Path, package_root: Path, label: str) -> None:
    try:
        path.resolve(strict=True).relative_to(package_root)
    except (FileNotFoundError, ValueError) as exc:
        raise ActorEnvironmentBuildError(f"{label} is missing or escapes repo root: {path}") from exc
    if path.is_symlink() or not path.exists():
        raise ActorEnvironmentBuildError(f"{label} must be a real file or directory: {path}")


def _require_source_file(path: Path, package_root: Path, label: str) -> None:
    _require_source_path(path, package_root, label)
    if not path.is_file():
        raise ActorEnvironmentBuildError(f"{label} must be a file: {path}")


def _require_source_directory(path: Path, package_root: Path, label: str) -> None:
    _require_source_path(path, package_root, label)
    if not path.is_dir():
        raise ActorEnvironmentBuildError(f"{label} must be a directory: {path}")


def _normalized_source_file(path: Path, source_root: Path, label: str) -> Path:
    _require_source_file(path, source_root, label)
    return path.resolve(strict=True)


def _normalized_source_directory(path: Path, source_root: Path, label: str) -> Path:
    _require_source_directory(path, source_root, label)
    return path.resolve(strict=True)


def _copy_git_free(source: Path, target: Path) -> None:
    if source.name == ".git":
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(
            source,
            target,
            symlinks=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        return
    shutil.copy2(source, target, follow_symlinks=False)


def _reject_git_entries(root: Path, label: str) -> None:
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        if ".git" in directory_names or ".git" in file_names:
            raise ActorEnvironmentBuildError(
                f"{label} must be Git-free: {Path(current_root) / '.git'}"
            )


def _reject_unexpected_symlinks(
    root: Path,
    label: str,
    *,
    allowed: set[Path] | None = None,
    ignored_names: set[str] | None = None,
) -> None:
    allowed_paths = allowed or set()
    ignored = ignored_names or set()
    if root.is_symlink():
        if root not in allowed_paths:
            raise ActorEnvironmentBuildError(f"{label} contains an unexpected symlink: {root}")
        return
    if not root.is_dir():
        return
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_root)
        for name in tuple(directory_names) + tuple(file_names):
            if name in ignored:
                continue
            candidate = current / name
            if candidate.is_symlink() and candidate not in allowed_paths:
                raise ActorEnvironmentBuildError(
                    f"{label} contains an unexpected symlink: {candidate}"
                )
        directory_names[:] = [name for name in directory_names if name not in ignored]


def _remove_owned_tree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if not path.exists():
        return
    for current_root, directory_names, file_names in os.walk(path, topdown=False):
        current = Path(current_root)
        for file_name in file_names:
            file_path = current / file_name
            try:
                file_path.chmod(stat.S_IWUSR | stat.S_IRUSR)
            except OSError:
                pass
        for directory_name in directory_names:
            directory = current / directory_name
            if directory.is_symlink():
                continue
            try:
                directory.chmod(stat.S_IRWXU)
            except OSError:
                pass
    shutil.rmtree(path)
