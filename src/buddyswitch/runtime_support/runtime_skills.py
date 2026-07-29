"""Materialize active role skills into runtime `.agents/skills` directories."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from buddyswitch.runtime_support.env_manifest import DEFAULT_MANIFEST, load_manifest, require_role, skills_by_id
from buddyswitch.runtime_support.env_manifest import configured_skill_exports


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_SKILL_ID_RE = r"^[a-zA-Z0-9][a-zA-Z0-9-]*$"


class RuntimeSkillsError(ValueError):
    """Raised when runtime skill installation is invalid."""


@dataclass(frozen=True)
class InstallEntry:
    skill_id: str
    source: Path


def _is_root_path(path: Path) -> bool:
    return path == path.parent


def _normalize_workspace(workspace_arg: object) -> Path:
    if isinstance(workspace_arg, str):
        if not workspace_arg.strip():
            raise RuntimeSkillsError("--workspace must be a non-empty path")
        workspace = Path(workspace_arg.strip()).expanduser().resolve(strict=False)
    elif isinstance(workspace_arg, Path):
        workspace = workspace_arg.expanduser().resolve(strict=False)
    else:
        raise RuntimeSkillsError("--workspace must be a path string or Path")
    if _is_root_path(workspace):
        raise RuntimeSkillsError("workspace must not be filesystem root")
    if workspace == PACKAGE_ROOT.resolve(strict=False):
        raise RuntimeSkillsError("workspace must not be the BuddySwitch package root")
    if not workspace.exists() or not workspace.is_dir():
        raise RuntimeSkillsError(f"workspace must exist as a directory: {workspace}")
    return workspace


def _validate_runtime_target(workspace: object) -> tuple[Path, Path]:
    workspace_dir = _normalize_workspace(workspace)
    agents_dir = workspace_dir / ".agents"
    skills_dir = agents_dir / "skills"

    if agents_dir.is_symlink():
        raise RuntimeSkillsError(f"refusing symlink runtime target: {agents_dir}")
    if skills_dir.is_symlink():
        raise RuntimeSkillsError(f"refusing symlink runtime target: {skills_dir}")

    try:
        skills_dir.resolve(strict=False).relative_to(workspace_dir)
    except ValueError as exc:
        raise RuntimeSkillsError("runtime skill target must stay under workspace/.agents/skills") from exc
    return agents_dir, skills_dir


def _validate_skill_id(skill_id: str) -> None:
    import re

    if not isinstance(skill_id, str) or not skill_id.strip():
        raise RuntimeSkillsError("skill id must be a non-empty string")
    normalized = skill_id.strip()
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        raise RuntimeSkillsError(f"invalid skill id '{skill_id}': path separators are not allowed")
    if not re.match(_SKILL_ID_RE, normalized):
        raise RuntimeSkillsError(f"invalid skill id '{skill_id}'")


def _validate_repo_relative_skill_path(raw_path: str, *, package_root: Path | None = None) -> Path:
    normalized_package_root = (package_root or PACKAGE_ROOT).expanduser().resolve(strict=False)
    path_obj = Path(raw_path)
    if path_obj.is_absolute():
        raise RuntimeSkillsError(f"manifest skill path must be repo-relative: {raw_path}")
    if ".." in path_obj.parts:
        raise RuntimeSkillsError(f"manifest skill path must not contain '..': {raw_path}")

    candidate = normalized_package_root
    for part in path_obj.parts:
        if part in ("", "."):
            continue
        candidate = candidate / part
        if candidate.is_symlink():
            try:
                component = candidate.relative_to(normalized_package_root).as_posix()
            except ValueError:
                component = candidate.as_posix()
            raise RuntimeSkillsError(
                "skill package path contains symlink boundary: "
                f"{raw_path} (component: {component}); skill package directory must not be a symlink"
            )

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(normalized_package_root)
    except ValueError as exc:
        raise RuntimeSkillsError(f"manifest skill path escapes repo root: {raw_path}") from exc

    if not resolved.exists() or not resolved.is_dir():
        raise RuntimeSkillsError(f"skill package directory not found: {raw_path}")
    for current_root, directory_names, file_names in os.walk(resolved, followlinks=False):
        current = Path(current_root)
        for name in tuple(directory_names) + tuple(file_names):
            if name == ".git":
                continue
            candidate = current / name
            if candidate.is_symlink():
                raise RuntimeSkillsError(
                    f"skill package contains symlink boundary: {raw_path} ({candidate})"
                )
        directory_names[:] = [name for name in directory_names if name != ".git"]
    return resolved


def _build_install_plan(
    *,
    manifest_path: Path,
    role_id: str,
    package_root: Path | None = None,
) -> list[InstallEntry]:
    manifest = load_manifest(manifest_path)
    role = require_role(manifest, role_id)
    lookup = skills_by_id(manifest)

    install_entries: list[InstallEntry] = []
    for skill_id in role.get("skills", []):
        _validate_skill_id(skill_id)
        skill = lookup.get(skill_id)
        if not isinstance(skill, dict):
            raise RuntimeSkillsError(f"skill '{skill_id}' not found in manifest")
        raw_path = skill.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise RuntimeSkillsError(f"manifest skill '{skill_id}' must define repo-relative path")
        source = _validate_repo_relative_skill_path(raw_path.strip(), package_root=package_root)
        install_entries.append(InstallEntry(skill_id=skill_id, source=source))

    if not install_entries:
        raise RuntimeSkillsError(f"role '{role_id}' has no skills to materialize")
    return install_entries


def validate_runtime_skills(
    *,
    manifest_path: Path,
    role_id: str,
    package_root: Path | None = None,
) -> tuple[str, ...]:
    """Validate one role's install plan without mutating a runtime workspace."""

    return tuple(
        entry.skill_id
        for entry in _build_install_plan(
            manifest_path=manifest_path,
            role_id=role_id,
            package_root=package_root,
        )
    )


def install_runtime_skills(
    *,
    manifest_path: Path,
    role_id: str,
    workspace: Path,
    package_root: Path | None = None,
) -> list[str]:
    agents_dir, skills_dir = _validate_runtime_target(workspace)
    plan = _build_install_plan(
        manifest_path=manifest_path,
        role_id=role_id,
        package_root=package_root,
    )

    if skills_dir.exists():
        shutil.rmtree(skills_dir)
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    for entry in plan:
        target_dir = skills_dir / entry.skill_id
        shutil.copytree(
            entry.source,
            target_dir,
            symlinks=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        installed.append(entry.skill_id)
    return installed
