"""Reviewed Role package discovery, validation, and selected projections."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path
import re
from types import ModuleType
from typing import Final

from buddyswitch.foundation.composition import SkillExport


__all__ = (
    "RoleDescriptor",
    "RoleHost",
    "RoleHostError",
    "RoleRuntime",
    "RoleSummary",
)


_ID_RE: Final = re.compile(r"^[a-z][a-z0-9-]*$")
_VALID_SOURCE_ACCESS: Final = frozenset({"read-only", "write"})
_VALID_BROWSER: Final = frozenset({"available", "required"})
_VALID_SEARCH_API: Final = frozenset({"available", "user-approved-only"})


class RoleHostError(ValueError):
    """Raised before publication when reviewed Role packages are invalid."""


@dataclass(frozen=True)
class RoleDescriptor:
    """Small exact public contract declared by one reviewed Role package."""

    id: str
    label: str
    scope: str
    skills: tuple[str, ...]
    artifact_templates: tuple[str, ...]
    project_path: str
    source_access: str
    browser_cockpit: str
    search_api: str


@dataclass(frozen=True)
class RoleSummary:
    id: str
    label: str
    scope: str


@dataclass(frozen=True)
class RoleRuntime:
    """Immutable consumer-earned facts for one selected Role."""

    id: str
    artifact_templates: tuple[str, ...]
    project_path: str
    source_access: str
    browser_cockpit: str
    search_api: str


@dataclass(frozen=True)
class _SkillSource:
    id: str
    source: Path


@dataclass(frozen=True)
class _ResolvedRole:
    descriptor: RoleDescriptor
    agents_source: Path
    skills: tuple[_SkillSource, ...]


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoleHostError(f"{label} must be a non-empty string")
    return value.strip()


def _id(value: object, *, label: str) -> str:
    normalized = _text(value, label=label)
    if _ID_RE.fullmatch(normalized) is None:
        raise RoleHostError(f"{label} must match /^[a-z][a-z0-9-]*$/")
    return normalized


def _tuple_of_ids(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise RoleHostError(f"{label} must be a tuple")
    normalized = tuple(_id(item, label=f"{label} entry") for item in value)
    if len(normalized) != len(set(normalized)):
        raise RoleHostError(f"{label} contains a duplicate selected Skill")
    return normalized


def _artifact_template_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise RoleHostError("valid Artifact templates must be a tuple")
    normalized = tuple(
        _id(item, label="valid Artifact template id") for item in value
    )
    if len(normalized) != len(set(normalized)):
        raise RoleHostError("valid Artifact templates contains a duplicate")
    return normalized


def _enum(value: object, *, label: str, allowed: frozenset[str]) -> str:
    normalized = _text(value, label=label)
    if normalized not in allowed:
        raise RoleHostError(
            f"{label} must be one of {', '.join(sorted(allowed))}; got {normalized!r}"
        )
    return normalized


def _relative_project_path(value: object, *, label: str) -> str:
    normalized = _text(value, label=label)
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts or path.as_posix() in {"", "."}:
        raise RoleHostError(f"{label} must be a contained relative path")
    return path.as_posix()


def _real_directory(path: Path, *, label: str) -> Path:
    if path.is_symlink():
        raise RoleHostError(f"{label} must not be a symlink: {path}")
    absolute = Path(os.path.abspath(path))
    if not absolute.exists():
        raise RoleHostError(f"{label} directory not found: {path}")
    if not absolute.is_dir():
        raise RoleHostError(f"{label} must be a directory: {path}")
    return absolute


def _real_file(path: Path, *, root: Path, label: str) -> Path:
    if path.is_symlink():
        raise RoleHostError(f"{label} must not be a symlink: {path}")
    absolute = Path(os.path.abspath(path))
    if not absolute.exists():
        raise RoleHostError(f"{label} file not found: {path}")
    if not absolute.is_file():
        raise RoleHostError(f"{label} must be a file: {path}")
    _under(absolute, root=root, label=label)
    return absolute


def _under(path: Path, *, root: Path, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RoleHostError(f"{label} escapes trusted package root: {path}") from exc


def _reject_tree_symlinks(root: Path, *, label: str) -> None:
    for current_text, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_text)
        for name in (*directory_names, *file_names):
            candidate = current / name
            if candidate.is_symlink():
                raise RoleHostError(f"{label} contains symlink boundary: {candidate}")


def _relative_skill_source(
    *,
    package_root: Path,
    raw_path: str,
    label: str,
) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise RoleHostError(f"{label} path must be package-relative: {raw_path}")
    if ".." in path.parts:
        raise RoleHostError(f"{label} path must not contain '..': {raw_path}")
    candidate = package_root
    for part in path.parts:
        if part in {"", "."}:
            continue
        candidate = candidate / part
        if candidate.is_symlink():
            raise RoleHostError(f"{label} path contains symlink boundary: {candidate}")
    source = _real_directory(candidate, label=label)
    _under(source, root=package_root, label=label)
    _reject_tree_symlinks(source, label=label)
    _real_file(source / "SKILL.md", root=package_root, label=f"{label} SKILL.md")
    return source


def _load_descriptor(
    role_file: Path,
    *,
    valid_artifact_templates: frozenset[str],
) -> RoleDescriptor:
    module_name = f"_buddyswitch_reviewed_role_{role_file.parent.name}_{abs(hash(role_file))}"
    spec = importlib.util.spec_from_file_location(module_name, role_file)
    if spec is None or spec.loader is None:
        raise RoleHostError(f"failed to load exact Role entrypoint: {role_file}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise RoleHostError(f"failed loading reviewed Role entrypoint {role_file}: {exc}") from exc
    return _descriptor_from_module(
        module,
        role_file=role_file,
        valid_artifact_templates=valid_artifact_templates,
    )


def _descriptor_from_module(
    module: ModuleType,
    *,
    role_file: Path,
    valid_artifact_templates: frozenset[str],
) -> RoleDescriptor:
    descriptor = getattr(module, "ROLE", None)
    if not isinstance(descriptor, RoleDescriptor):
        raise RoleHostError(f"{role_file} must define exact ROLE = RoleDescriptor(...)")
    role_id = _id(descriptor.id, label="Role id")
    label = _text(descriptor.label, label=f"Role '{role_id}' label")
    scope = _text(descriptor.scope, label=f"Role '{role_id}' scope")
    skills = _tuple_of_ids(descriptor.skills, label=f"Role '{role_id}' skills")
    if not skills:
        raise RoleHostError(f"Role '{role_id}' skills must not be empty")
    if not isinstance(descriptor.artifact_templates, tuple) or not descriptor.artifact_templates:
        raise RoleHostError(f"Role '{role_id}' artifact_templates must be a non-empty tuple")
    templates = tuple(
        _enum(
            value,
            label=f"Role '{role_id}' artifact_templates entry",
            allowed=valid_artifact_templates,
        )
        for value in descriptor.artifact_templates
    )
    if len(templates) != len(set(templates)):
        raise RoleHostError(f"Role '{role_id}' artifact_templates contains a duplicate")
    project_path = _relative_project_path(
        descriptor.project_path,
        label=f"Role '{role_id}' project_path",
    )
    source_access = _enum(
        descriptor.source_access,
        label=f"Role '{role_id}' source_access",
        allowed=_VALID_SOURCE_ACCESS,
    )
    browser_cockpit = _enum(
        descriptor.browser_cockpit,
        label=f"Role '{role_id}' browser_cockpit",
        allowed=_VALID_BROWSER,
    )
    search_api = _enum(
        descriptor.search_api,
        label=f"Role '{role_id}' search_api",
        allowed=_VALID_SEARCH_API,
    )
    return RoleDescriptor(
        id=role_id,
        label=label,
        scope=scope,
        skills=skills,
        artifact_templates=templates,
        project_path=project_path,
        source_access=source_access,
        browser_cockpit=browser_cockpit,
        search_api=search_api,
    )


class RoleHost:
    """One narrow immutable host for reviewed local Role packages."""

    def __init__(
        self,
        *,
        package_root: Path,
        roles: tuple[_ResolvedRole, ...],
    ) -> None:
        self._package_root = package_root
        self._resolved = {role.descriptor.id: role for role in roles}
        self.roles = tuple(
            RoleSummary(
                id=role.descriptor.id,
                label=role.descriptor.label,
                scope=role.descriptor.scope,
            )
            for role in roles
        )
        self.valid_role_ids = frozenset(self._resolved)

    @classmethod
    def discover(
        cls,
        *,
        package_root: Path,
        component_skills: tuple[SkillExport, ...],
        valid_artifact_templates: tuple[str, ...],
    ) -> "RoleHost":
        trusted_package_root = _real_directory(
            Path(package_root),
            label="BuddySwitch package root",
        )
        trusted_roles_root = _real_directory(
            trusted_package_root / "roles",
            label="reviewed Roles root",
        )
        _under(
            trusted_roles_root,
            root=trusted_package_root,
            label="reviewed Roles root",
        )
        _reject_tree_symlinks(trusted_roles_root, label="reviewed Roles root")

        normalized_artifact_templates = _artifact_template_ids(
            valid_artifact_templates
        )
        if not normalized_artifact_templates:
            raise RoleHostError("valid Artifact templates must not be empty")
        artifact_template_set = frozenset(normalized_artifact_templates)

        component_skill_sources: dict[str, _SkillSource] = {}
        if not isinstance(component_skills, tuple):
            raise RoleHostError("component Skills must be a tuple")
        for export in component_skills:
            if not isinstance(export, SkillExport):
                raise RoleHostError("component Skill entry must be SkillExport")
            skill_id = _id(export.id, label="component Skill id")
            if skill_id in component_skill_sources:
                raise RoleHostError(f"duplicate component Skill id: {skill_id}")
            raw_path = _text(
                export.package_path,
                label=f"component Skill '{skill_id}' path",
            )
            component_skill_sources[skill_id] = _SkillSource(
                id=skill_id,
                source=_relative_skill_source(
                    package_root=trusted_package_root,
                    raw_path=raw_path,
                    label=f"component Skill '{skill_id}'",
                ),
            )

        discovered: list[
            tuple[RoleDescriptor, Path, Path, dict[str, _SkillSource]]
        ] = []
        role_ids: set[str] = set()
        for role_directory in sorted(trusted_roles_root.iterdir()):
            if role_directory.name.startswith("_"):
                continue
            if role_directory.is_symlink():
                raise RoleHostError(
                    f"reviewed Role package must not be a symlink: {role_directory}"
                )
            if not role_directory.is_dir():
                raise RoleHostError(
                    f"reviewed Roles root entries must be directories: {role_directory}"
                )
            role_root = _real_directory(
                role_directory,
                label=f"reviewed Role package '{role_directory.name}'",
            )
            _under(role_root, root=trusted_roles_root, label="reviewed Role package")
            role_file = _real_file(
                role_root / "role.py",
                root=role_root,
                label="Role role.py",
            )
            agents = _real_file(
                role_root / "AGENTS.md",
                root=role_root,
                label="Role AGENTS.md",
            )
            assets_root = _real_directory(
                role_root / "assets",
                label="Role assets root",
            )
            _under(assets_root, root=role_root, label="Role assets root")
            _reject_tree_symlinks(assets_root, label="Role assets root")
            result_schema = _real_file(
                assets_root / "result-schema.json",
                root=role_root,
                label="Role result schema",
            )
            try:
                result_contract = json.loads(result_schema.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise RoleHostError(
                    f"Role result schema must be valid UTF-8 JSON: {result_schema}"
                ) from exc
            if not isinstance(result_contract, dict):
                raise RoleHostError(
                    f"Role result schema must contain a JSON object: {result_schema}"
                )
            descriptor = _load_descriptor(
                role_file,
                valid_artifact_templates=artifact_template_set,
            )
            if descriptor.id in role_ids:
                raise RoleHostError(f"duplicate Role id: {descriptor.id}")
            role_ids.add(descriptor.id)
            private_skill_sources: dict[str, _SkillSource] = {}
            private_skills_root = role_root / "skills"
            if private_skills_root.exists() or private_skills_root.is_symlink():
                private_skills_root = _real_directory(
                    private_skills_root,
                    label=f"Role '{descriptor.id}' Skills root",
                )
                for skill_directory in sorted(private_skills_root.iterdir()):
                    if skill_directory.name.startswith("_"):
                        continue
                    skill_id = _id(
                        skill_directory.name,
                        label=f"Role '{descriptor.id}' private Skill id",
                    )
                    if skill_id in component_skill_sources:
                        raise RoleHostError(
                            f"Role '{descriptor.id}' private Skill '{skill_id}' "
                            f"conflicts with component Skill '{skill_id}'"
                        )
                    source = _real_directory(
                        skill_directory,
                        label=f"Role-private Skill '{skill_id}'",
                    )
                    _under(source, root=role_root, label=f"Role-private Skill '{skill_id}'")
                    _reject_tree_symlinks(source, label=f"Role-private Skill '{skill_id}'")
                    _real_file(
                        source / "SKILL.md",
                        root=role_root,
                        label=f"Role-private Skill '{skill_id}' SKILL.md",
                    )
                    private_skill_sources[skill_id] = _SkillSource(
                        id=skill_id,
                        source=source,
                    )
            discovered.append(
                (descriptor, role_root, agents, private_skill_sources)
            )

        if not discovered:
            raise RoleHostError("reviewed Roles root contains no Role packages")
        resolved_roles: list[_ResolvedRole] = []
        for descriptor, role_root, agents, private_skill_sources in discovered:
            selected: list[_SkillSource] = []
            for skill_id in descriptor.skills:
                skill = private_skill_sources.get(skill_id)
                if skill is None:
                    skill = component_skill_sources.get(skill_id)
                if skill is None:
                    raise RoleHostError(
                        f"Role '{descriptor.id}' selects unknown Skill '{skill_id}'"
                    )
                selected.append(skill)
            resolved_roles.append(
                _ResolvedRole(
                    descriptor=descriptor,
                    agents_source=agents,
                    skills=tuple(selected),
                )
            )
        resolved_roles.sort(key=lambda role: role.descriptor.id)
        return cls(
            package_root=trusted_package_root,
            roles=tuple(resolved_roles),
        )

    def _require(self, role_id: str) -> _ResolvedRole:
        normalized = _id(role_id, label="Role id")
        resolved = self._resolved.get(normalized)
        if resolved is None:
            raise RoleHostError(
                f"Unknown Role '{normalized}'. Valid: {', '.join(sorted(self._resolved))}"
            )
        return resolved

    def runtime(self, role_id: str) -> RoleRuntime:
        descriptor = self._require(role_id).descriptor
        return RoleRuntime(
            id=descriptor.id,
            artifact_templates=descriptor.artifact_templates,
            project_path=descriptor.project_path,
            source_access=descriptor.source_access,
            browser_cockpit=descriptor.browser_cockpit,
            search_api=descriptor.search_api,
        )

    def actor_bootstrap(self, role_id: str, *, codex_config: str):
        from buddyswitch.foundation.actor_runtime.environment import (
            ResolvedActorBootstrap,
            ResolvedActorSkill,
        )

        resolved = self._require(role_id)
        return ResolvedActorBootstrap(
            source_root=self._package_root,
            agents_source=resolved.agents_source,
            skills=tuple(
                ResolvedActorSkill(skill_id=skill.id, source=skill.source)
                for skill in resolved.skills
            ),
            codex_config=codex_config,
        )
