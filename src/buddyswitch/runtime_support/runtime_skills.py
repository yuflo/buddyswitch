"""Resolve the active Role's selected Skill packages for application use."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from buddyswitch.runtime_support.env_manifest import (
    load_manifest,
    require_role,
    skills_by_id,
)


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_SKILL_ID_RE = r"^[a-zA-Z0-9][a-zA-Z0-9-]*$"


class RuntimeSkillsError(ValueError):
    """Raised when current Role Skill resolution is invalid."""


@dataclass(frozen=True)
class ResolvedSkill:
    skill_id: str
    source: Path


def _validate_skill_id(skill_id: str) -> None:
    import re

    if not isinstance(skill_id, str) or not skill_id.strip():
        raise RuntimeSkillsError("skill id must be a non-empty string")
    normalized = skill_id.strip()
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        raise RuntimeSkillsError(f"invalid skill id '{skill_id}': path separators are not allowed")
    if not re.match(_SKILL_ID_RE, normalized):
        raise RuntimeSkillsError(f"invalid skill id '{skill_id}'")


def _validate_repo_relative_skill_path(
    raw_path: str,
    *,
    package_root: Path | None = None,
) -> Path:
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


def _resolve_skill_sources(
    *,
    manifest_path: Path,
    role_id: str,
    package_root: Path | None = None,
) -> tuple[ResolvedSkill, ...]:
    manifest = load_manifest(manifest_path)
    role = require_role(manifest, role_id)
    lookup = skills_by_id(manifest)

    resolved_skills: list[ResolvedSkill] = []
    for skill_id in role.get("skills", []):
        _validate_skill_id(skill_id)
        skill = lookup.get(skill_id)
        if not isinstance(skill, dict):
            raise RuntimeSkillsError(f"skill '{skill_id}' not found in manifest")
        raw_path = skill.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise RuntimeSkillsError(f"manifest skill '{skill_id}' must define repo-relative path")
        source = _validate_repo_relative_skill_path(
            raw_path.strip(),
            package_root=package_root,
        )
        resolved_skills.append(ResolvedSkill(skill_id=skill_id, source=source))

    if not resolved_skills:
        raise RuntimeSkillsError(f"role '{role_id}' has no skills to materialize")
    return tuple(resolved_skills)


def resolve_runtime_skills(
    *,
    manifest_path: Path,
    role_id: str,
    package_root: Path | None = None,
) -> tuple[ResolvedSkill, ...]:
    """Resolve one Role's selected Skill sources without materializing them."""

    return _resolve_skill_sources(
        manifest_path=manifest_path,
        role_id=role_id,
        package_root=package_root,
    )
