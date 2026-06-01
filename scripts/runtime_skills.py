#!/usr/bin/env python3
"""Materialize active role skills into runtime `.agents/skills` directories."""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from env_manifest import DEFAULT_MANIFEST, ManifestError, load_manifest, require_role, skills_by_id


ROOT = Path(__file__).resolve().parents[1]
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
    if workspace == ROOT.resolve(strict=False):
        raise RuntimeSkillsError("workspace must not be BuddySwitch source checkout root")
    if not workspace.exists() or not workspace.is_dir():
        raise RuntimeSkillsError(f"workspace must exist as a directory: {workspace}")
    return workspace


def _require_workspace(workspace_arg: str) -> Path:
    return _normalize_workspace(workspace_arg)


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


def _validate_repo_relative_skill_path(raw_path: str) -> Path:
    path_obj = Path(raw_path)
    if path_obj.is_absolute():
        raise RuntimeSkillsError(f"manifest skill path must be repo-relative: {raw_path}")
    if ".." in path_obj.parts:
        raise RuntimeSkillsError(f"manifest skill path must not contain '..': {raw_path}")

    candidate = ROOT
    for part in path_obj.parts:
        if part in ("", "."):
            continue
        candidate = candidate / part
        if candidate.is_symlink():
            try:
                component = candidate.relative_to(ROOT).as_posix()
            except ValueError:
                component = candidate.as_posix()
            raise RuntimeSkillsError(
                "skill package path contains symlink boundary: "
                f"{raw_path} (component: {component}); skill package directory must not be a symlink"
            )

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeSkillsError(f"manifest skill path escapes repo root: {raw_path}") from exc

    if not resolved.exists() or not resolved.is_dir():
        raise RuntimeSkillsError(f"skill package directory not found: {raw_path}")
    return resolved


def _build_install_plan(*, manifest_path: Path, role_id: str) -> list[InstallEntry]:
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
        source = _validate_repo_relative_skill_path(raw_path.strip())
        install_entries.append(InstallEntry(skill_id=skill_id, source=source))

    if not install_entries:
        raise RuntimeSkillsError(f"role '{role_id}' has no skills to materialize")
    return install_entries


def install_runtime_skills(*, manifest_path: Path, role_id: str, workspace: Path) -> list[str]:
    agents_dir, skills_dir = _validate_runtime_target(workspace)
    plan = _build_install_plan(manifest_path=manifest_path, role_id=role_id)

    if skills_dir.exists():
        shutil.rmtree(skills_dir)
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_dir.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    for entry in plan:
        target_dir = skills_dir / entry.skill_id
        shutil.copytree(entry.source, target_dir, symlinks=True)
        installed.append(entry.skill_id)
    return installed


def _cmd_install(args: argparse.Namespace) -> int:
    workspace = _require_workspace(args.workspace)
    installed = install_runtime_skills(
        manifest_path=args.manifest,
        role_id=args.role,
        workspace=workspace,
    )
    for skill_id in installed:
        print(skill_id)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install runtime .agents/skills for the active role.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install runtime skills into workspace/.agents/skills")
    install.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    install.add_argument("--role", required=True)
    install.add_argument("--workspace", required=True)
    install.set_defaults(func=_cmd_install)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ManifestError, RuntimeSkillsError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
