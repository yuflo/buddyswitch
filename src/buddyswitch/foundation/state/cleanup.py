"""Product-neutral cleanup planning and guarded state execution."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Callable

from buddyswitch.foundation.composition import (
    CleanupContribution,
    CleanupIndexProjection,
    OwnedStatePath,
)
import buddyswitch.foundation.state.actor_private as actor_private_state
import buddyswitch.foundation.state.runtime as state_runtime

ROOT = state_runtime.ROOT
_PROJECTION_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_RESERVED_PROJECTION_FIELDS = frozenset(
    {
        "scope",
        "role",
        "delete_paths",
        "deleted_paths",
        "deleted_count",
        "warnings",
        "counts_by_category",
        "direct_delete_paths",
        "external_delete_paths",
        "path_categories",
        "repo_root",
        "shared_root",
        "ok",
    }
)


ACTOR_PRIVATE_RELATIVE_DIR = "private"


def validate_cleanup_contributions(
    contributions: tuple[CleanupContribution, ...],
) -> tuple[CleanupContribution, ...]:
    if not isinstance(contributions, tuple):
        raise ValueError("cleanup contributions must be a tuple")

    categories: set[str] = set()
    projection_fields = set(_RESERVED_PROJECTION_FIELDS)
    for contribution in contributions:
        if not isinstance(contribution, CleanupContribution):
            raise ValueError("cleanup contribution must be CleanupContribution")
        category = contribution.category
        if (
            not isinstance(category, str)
            or not category.strip()
            or category != category.strip()
            or category == "actor_private_files"
            or category in categories
        ):
            raise ValueError(f"invalid or duplicate cleanup category: {category}")
        if not callable(contribution.discover):
            raise ValueError(
                f"cleanup discoverer for '{category}' must be callable"
            )
        categories.add(category)

        projection = contribution.index_projection
        if projection is None:
            continue
        if not isinstance(projection, CleanupIndexProjection):
            raise ValueError(
                f"cleanup index projection for '{category}' must be "
                "CleanupIndexProjection"
            )
        fields = (
            projection.object_ids_field,
            projection.records_field,
        )
        for field_name in fields:
            if (
                not isinstance(field_name, str)
                or _PROJECTION_FIELD_RE.fullmatch(field_name) is None
                or field_name in projection_fields
            ):
                raise ValueError(
                    f"cleanup projection field for '{category}' is invalid or duplicate: "
                    f"{field_name!r}"
                )
            projection_fields.add(field_name)

    _required_directories(contributions)
    return contributions


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def is_path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def repo_path(root: Path, raw_path: str) -> Path | None:
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    return root / path


def iter_directory_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    paths: list[Path] = []
    for current_root, dir_names, file_names in os.walk(directory, followlinks=False):
        current = Path(current_root)
        kept_dirs: list[str] = []
        for dir_name in dir_names:
            candidate = current / dir_name
            if candidate.is_symlink():
                if candidate.name != ".gitkeep":
                    paths.append(candidate)
                continue
            kept_dirs.append(dir_name)
        dir_names[:] = kept_dirs

        for file_name in file_names:
            candidate = current / file_name
            if candidate.name == ".gitkeep":
                continue
            if candidate.is_file() or candidate.is_symlink():
                paths.append(candidate)
    return sorted(paths)


def resolve_guarded_relative_dir(
    root: Path,
    relative_dir: str,
    *,
    allow_missing: bool = False,
) -> tuple[Path | None, str | None]:
    relative_target = Path(relative_dir)
    if relative_target.is_absolute() or ".." in relative_target.parts:
        return None, f"invalid cleanup path '{relative_dir}'."

    current = root
    for part in relative_target.parts:
        current = current / part
        if current.is_symlink():
            return None, f"cleanup path traverses symlink '{rel(root, current)}'."

    target_dir = root / relative_target
    if target_dir.exists():
        if not target_dir.is_dir():
            if allow_missing:
                return None, f"cleanup path '{relative_dir}' is not a directory."
            return None, None
    elif not allow_missing:
        return None, None

    resolved_root = root.resolve(strict=False)
    resolved_target_dir = target_dir.resolve(strict=False)
    if not is_path_within(resolved_target_dir, resolved_root):
        return None, "cleanup path resolves outside repo root."
    return target_dir, None


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def append_warning(warnings: list[str] | None, message: str) -> None:
    if warnings is None:
        return
    if message not in warnings:
        warnings.append(message)


def _valid_role_ids(role_ids: frozenset[str]) -> frozenset[str]:
    if not isinstance(role_ids, frozenset) or not role_ids or not all(
        isinstance(role_id, str) and bool(role_id) and role_id.strip() == role_id
        for role_id in role_ids
    ):
        raise ValueError("valid Role source must return a frozenset of normalized strings")
    return role_ids


def _new_plan(
    scope: str,
    *,
    role: str | None,
    contributions: tuple[CleanupContribution, ...],
) -> dict[str, Any]:
    counts = {"actor_private_files": 0}
    plan: dict[str, Any] = {
        "scope": scope,
        "role": role,
        "delete_paths": [],
        "warnings": [],
        "counts_by_category": counts,
        "direct_delete_paths": [],
        "external_delete_paths": {},
    }
    for contribution in contributions:
        counts[contribution.category] = 0
        projection = contribution.index_projection
        if projection is not None:
            plan[projection.object_ids_field] = []
            plan[projection.records_field] = []
    return plan


def add_warning(plan: dict[str, Any], message: str) -> None:
    if message not in plan["warnings"]:
        plan["warnings"].append(message)


def add_path(plan: dict[str, Any], path: Path, category: str) -> None:
    relative = rel(Path(plan["repo_root"]), path)
    if relative not in plan["_path_categories"]:
        plan["_path_categories"][relative] = category
        plan["delete_paths"].append(relative)
        plan["counts_by_category"][category] += 1


def add_external_path(plan: dict[str, Any], *, display_path: str, absolute_path: Path, category: str) -> None:
    if display_path not in plan["_path_categories"]:
        plan["_path_categories"][display_path] = category
        plan["delete_paths"].append(display_path)
        plan["counts_by_category"][category] += 1
    if display_path not in plan["external_delete_paths"]:
        plan["external_delete_paths"][display_path] = str(absolute_path)
        plan["direct_delete_paths"].append(display_path)


def add_dir_files(plan: dict[str, Any], relative_dir: str, category: str) -> None:
    root = Path(plan["repo_root"])
    target_dir, blocked_reason = resolve_guarded_relative_dir(root, relative_dir)
    if target_dir is None:
        if blocked_reason is None:
            return
        if blocked_reason.startswith("invalid cleanup path"):
            add_warning(plan, f"Skipping shared-state cleanup: {blocked_reason}")
        else:
            add_warning(plan, f"Skipping shared-state cleanup for '{relative_dir}': {blocked_reason}")
        return

    for path in iter_directory_files(target_dir):
        add_path(plan, path, category)
        plan["direct_delete_paths"].append(rel(root, path))


def discover_instance_workspaces(
    plan: dict[str, Any],
    *,
    shared_root: Path,
    role_filter: str | None,
) -> list[Path]:
    instances_root = shared_root / "instances"
    if shared_root.is_symlink():
        add_warning(plan, f"Skipping instance-local cleanup: shared root is a symlink ({shared_root}).")
        return []
    if not instances_root.exists() or not instances_root.is_dir():
        return []
    if instances_root.is_symlink():
        add_warning(plan, f"Skipping instance-local cleanup: instances root is a symlink ({instances_root}).")
        return []

    resolved_instances_root = instances_root.resolve(strict=False)
    workspaces: list[Path] = []
    for instance_root in sorted(instances_root.iterdir()):
        if not instance_root.is_dir():
            continue
        if instance_root.is_symlink():
            add_warning(
                plan,
                f"Skipping instance-local cleanup for '{instance_root.name}': instance root is a symlink.",
            )
            continue

        resolved_instance_root = instance_root.resolve(strict=False)
        if not is_path_within(resolved_instance_root, resolved_instances_root):
            add_warning(
                plan,
                f"Skipping instance-local cleanup for '{instance_root.name}': instance root resolves outside shared instances root.",
            )
            continue

        workspace_dir = instance_root / "workspace"
        if not workspace_dir.exists():
            continue
        if workspace_dir.is_symlink():
            add_warning(
                plan,
                f"Skipping instance-local cleanup for '{instance_root.name}': workspace path is a symlink.",
            )
            continue
        if not workspace_dir.is_dir():
            add_warning(
                plan,
                f"Skipping instance-local cleanup for '{instance_root.name}': workspace path is not a directory.",
            )
            continue

        resolved_workspace = workspace_dir.resolve(strict=False)
        if not is_path_within(resolved_workspace, resolved_instance_root):
            add_warning(
                plan,
                f"Skipping instance-local cleanup for '{instance_root.name}': workspace resolves outside its instance root.",
            )
            continue

        instance_role: str | None = None
        instance_json = instance_root / "instance.json"
        if instance_json.exists():
            try:
                payload = read_json(instance_json)
            except (OSError, ValueError, json.JSONDecodeError):
                payload = {}
                if role_filter is not None:
                    add_warning(
                        plan,
                        f"Skipping role-filtered cleanup for '{instance_root.name}': invalid instance.json.",
                    )
            role_value = payload.get("role")
            if isinstance(role_value, str) and role_value:
                instance_role = role_value

        if role_filter is not None:
            if instance_role is None:
                add_warning(
                    plan,
                    f"Skipping role-filtered cleanup for '{instance_root.name}': missing role in instance.json.",
                )
                continue
            if instance_role != role_filter:
                continue

        workspaces.append(workspace_dir)
    return workspaces


def add_instance_workspace_dir_files(
    plan: dict[str, Any],
    *,
    shared_root: Path,
    workspace_dir: Path,
    relative_dir: str,
    category: str,
) -> None:
    instance_name = workspace_dir.parent.name
    relative_target = Path(relative_dir)
    if relative_target.is_absolute() or ".." in relative_target.parts:
        add_warning(
            plan,
            f"Skipping instance-local cleanup for '{instance_name}': invalid cleanup path '{relative_dir}'.",
        )
        return

    current = workspace_dir
    for part in relative_target.parts:
        current = current / part
        if current.is_symlink():
            add_warning(
                plan,
                (
                    f"Skipping instance-local cleanup for '{instance_name}': cleanup path "
                    f"'{relative_dir}' traverses symlink '{rel(workspace_dir, current)}'."
                ),
            )
            return

    target_dir = workspace_dir / relative_target
    if not target_dir.is_dir():
        return

    resolved_workspace = workspace_dir.resolve(strict=False)
    resolved_target_dir = target_dir.resolve(strict=False)
    if not is_path_within(resolved_target_dir, resolved_workspace):
        add_warning(
            plan,
            f"Skipping instance-local cleanup for '{instance_name}': cleanup path '{relative_dir}' resolves outside workspace.",
        )
        return

    for path in iter_directory_files(target_dir):
        display_path = rel(shared_root, path)
        add_external_path(plan, display_path=display_path, absolute_path=path, category=category)


def _validated_execution_root(root: Path, *, label: str) -> Path:
    if root.is_symlink():
        raise ValueError(f"Refusing cleanup execution: {label} is a symlink ({root}).")
    if not root.exists():
        raise ValueError(f"Refusing cleanup execution: {label} is missing ({root}).")
    if not root.is_dir():
        raise ValueError(f"Refusing cleanup execution: {label} is not a directory ({root}).")
    return root.resolve(strict=True)


def _guard_execution_target(
    root: Path,
    *,
    resolved_root: Path,
    relative_path: str,
) -> tuple[Path | None, str | None]:
    relative = Path(relative_path)
    if (
        not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        return None, "planned path is not a safe relative path"

    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            return None, f"parent '{current.relative_to(root).as_posix()}' is a symlink"
        if not current.exists():
            return None, "target is missing"
        if not current.is_dir():
            return None, f"parent '{current.relative_to(root).as_posix()}' is not a directory"

    target = root / relative
    if target.is_symlink():
        return target, None
    if not target.exists():
        return None, "target is missing"
    if not is_path_within(target.resolve(strict=True), resolved_root):
        return None, "target resolves outside its cleanup root"
    return target, None


def _actor_private_owner(
    root: Path,
    *,
    relative_path: str,
    external: bool,
) -> tuple[Path, str] | None:
    parts = Path(relative_path).parts
    if external:
        if (
            len(parts) < 5
            or parts[0] != "instances"
            or parts[2] != "workspace"
            or parts[3] != ACTOR_PRIVATE_RELATIVE_DIR
        ):
            return None
        private_root_parts = parts[:4]
        logical_parts = parts[4:]
    else:
        private_marker = Path(ACTOR_PRIVATE_RELATIVE_DIR).parts
        if not private_marker or tuple(parts[: len(private_marker)]) != private_marker:
            return None
        private_root_parts = parts[: len(private_marker)]
        logical_parts = parts[len(private_marker) :]

    if not logical_parts:
        return None
    return root.joinpath(*private_root_parts), "/".join(logical_parts)


def _delete_actor_private_target(
    target: Path,
    *,
    private_root: Path,
    logical_name: str,
) -> tuple[bool, str | None]:
    if target.is_symlink():
        return delete_absolute_path(target), None
    if not target.is_file():
        if not target.exists():
            return False, "target is missing"
        return False, "actor-private target is not a regular file"
    try:
        deleted = actor_private_state.delete_private_file(
            root=private_root,
            logical_name=logical_name,
        )
    except (actor_private_state.ActorPrivateBoundaryError, IsADirectoryError) as exc:
        return False, f"actor-private owner rejected the path: {exc}"
    if not deleted:
        return False, "actor-private owner reported no deletion"
    return True, None


def delete_relative_path(root: Path, relative_path: str) -> bool:
    resolved = repo_path(root, relative_path)
    if resolved is None or (not resolved.exists() and not resolved.is_symlink()):
        return False
    if resolved.is_dir() and not resolved.is_symlink():
        shutil.rmtree(resolved)
        return True
    resolved.unlink()
    return True


def delete_absolute_path(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return True
    path.unlink()
    return True


def _required_directories(
    contributions: tuple[CleanupContribution, ...],
) -> tuple[str, ...]:
    directories: list[str] = []
    for contribution in contributions:
        if not isinstance(contribution.required_directories, tuple):
            raise ValueError(
                f"cleanup required directories for "
                f"'{contribution.category}' must be a tuple"
            )
        for relative_dir in contribution.required_directories:
            path = Path(relative_dir)
            if (
                not isinstance(relative_dir, str)
                or not relative_dir.strip()
                or path.is_absolute()
                or ".." in path.parts
            ):
                raise ValueError(
                    f"invalid cleanup required directory: {relative_dir!r}"
                )
            normalized = path.as_posix()
            if normalized not in directories:
                directories.append(normalized)
    return tuple(directories)


def ensure_required_skeleton(
    root: Path,
    *,
    contributions: tuple[CleanupContribution, ...] = (),
    warnings: list[str] | None = None,
) -> None:
    for relative_dir in _required_directories(contributions):
        directory, blocked_reason = resolve_guarded_relative_dir(root, relative_dir, allow_missing=True)
        if directory is None:
            if blocked_reason is not None:
                append_warning(
                    warnings,
                    f"Skipping skeleton recreation for '{relative_dir}': {blocked_reason}",
                )
            continue
        if directory.exists():
            if directory.is_dir():
                continue
            append_warning(
                warnings,
                f"Skipping skeleton recreation for '{relative_dir}': target exists and is not a directory.",
            )
            continue
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            append_warning(
                warnings,
                f"Skipping skeleton recreation for '{relative_dir}': {exc}",
            )


def build_cleanup_plan(
    *,
    scope: str,
    role: str | None,
    repo_root: Path = ROOT,
    valid_role_ids: frozenset[str],
    shared_root: Path | None = None,
    contributions: tuple[CleanupContribution, ...] = (),
) -> dict[str, Any]:
    contributions = validate_cleanup_contributions(contributions)
    valid_roles = _valid_role_ids(valid_role_ids)
    if scope == "role" and (role is None or role not in valid_roles):
        raise ValueError(f"Invalid role '{role}'. Check the installed BuddySwitch role catalog.")

    plan = _new_plan(
        scope,
        role=role,
        contributions=contributions,
    )
    plan["repo_root"] = str(repo_root)
    plan["shared_root"] = str(shared_root) if shared_root is not None else None
    plan["_path_categories"] = {}
    if scope == "role":
        actor_private_relative_dir = ACTOR_PRIVATE_RELATIVE_DIR
        if shared_root is not None:
            resolved_shared_root = shared_root.resolve(strict=False)
            for workspace_dir in discover_instance_workspaces(
                plan,
                shared_root=resolved_shared_root,
                role_filter=role,
            ):
                add_instance_workspace_dir_files(
                    plan,
                    shared_root=resolved_shared_root,
                    workspace_dir=workspace_dir,
                    relative_dir=actor_private_relative_dir,
                    category="actor_private_files",
                )
        else:
            add_dir_files(plan, actor_private_relative_dir, "actor_private_files")

    elif scope == "all-data":
        if shared_root is not None:
            resolved_shared_root = shared_root.resolve(strict=False)
            for workspace_dir in discover_instance_workspaces(
                plan,
                shared_root=resolved_shared_root,
                role_filter=None,
            ):
                add_instance_workspace_dir_files(
                    plan,
                    shared_root=resolved_shared_root,
                    workspace_dir=workspace_dir,
                    relative_dir=ACTOR_PRIVATE_RELATIVE_DIR,
                    category="actor_private_files",
                )
        else:
            add_dir_files(plan, ACTOR_PRIVATE_RELATIVE_DIR, "actor_private_files")
    else:
        raise ValueError(f"Unsupported cleanup scope: {scope}")

    resolved_repo_root = repo_root.resolve(strict=False)
    for contribution in contributions:
        for owned_path in contribution.discover(repo_root):
            if not isinstance(owned_path, OwnedStatePath):
                raise ValueError(
                    f"cleanup contribution '{contribution.category}' returned "
                    "a non-OwnedStatePath value"
                )
            relative_path = owned_path.relative_path
            if isinstance(owned_path.warning, str) and owned_path.warning:
                add_warning(plan, owned_path.warning)
            if not isinstance(owned_path.owner_roles, tuple) or not all(
                isinstance(owner_role, str) and owner_role.strip()
                for owner_role in owned_path.owner_roles
            ):
                raise ValueError(
                    f"cleanup contribution '{contribution.category}' returned "
                    "invalid owner_roles"
                )
            candidate = repo_path(repo_root, relative_path)
            if candidate is None:
                add_warning(
                    plan,
                    f"Skipping unsafe cleanup path '{relative_path}' from "
                    f"'{contribution.category}'.",
                )
                continue
            current = repo_root
            unsafe = False
            for part in Path(relative_path).parts[:-1]:
                current = current / part
                if current.is_symlink():
                    unsafe = True
                    break
            candidate_is_symlink = candidate.is_symlink()
            if unsafe or (
                not candidate_is_symlink
                and not is_path_within(
                    candidate.resolve(strict=False),
                    resolved_repo_root,
                )
            ):
                add_warning(
                    plan,
                    f"Skipping unsafe cleanup path '{relative_path}' from "
                    f"'{contribution.category}'.",
                )
                continue
            if scope == "role":
                if not owned_path.owner_roles:
                    if owned_path.warning is None:
                        add_warning(
                            plan,
                            f"{relative_path} cannot be safely attributed to role "
                            f"'{role}' and will be skipped in scoped cleanup.",
                        )
                    continue
                if role not in owned_path.owner_roles:
                    continue
            if not candidate.exists() and not candidate_is_symlink:
                continue
            add_path(plan, candidate, contribution.category)
            plan["direct_delete_paths"].append(relative_path)
            projection = contribution.index_projection
            record = owned_path.index_record
            if projection is None or record is None:
                continue
            if not isinstance(record, Mapping):
                raise ValueError(
                    f"cleanup contribution '{contribution.category}' returned "
                    "a non-mapping index record"
                )
            object_id = record.get("id")
            if not isinstance(object_id, str) or not object_id:
                raise ValueError(
                    f"cleanup contribution '{contribution.category}' returned "
                    "an index record without id"
                )
            object_ids = plan[projection.object_ids_field]
            records = plan[projection.records_field]
            if object_id not in object_ids:
                object_ids.append(object_id)
                records.append(dict(record))

    plan["delete_paths"].sort()
    for contribution in contributions:
        projection = contribution.index_projection
        if projection is not None:
            plan[projection.object_ids_field].sort()
    plan["direct_delete_paths"] = sorted(set(plan["direct_delete_paths"]))
    plan["external_delete_paths"] = {
        key: plan["external_delete_paths"][key] for key in sorted(plan["external_delete_paths"])
    }
    plan["path_categories"] = {
        key: plan["_path_categories"][key] for key in sorted(plan["_path_categories"])
    }
    plan["warnings"].sort()
    plan.pop("_path_categories", None)
    return plan


def _append_execution_warning(
    warnings: list[str],
    *,
    relative_path: str,
    reason: str,
) -> None:
    append_warning(
        warnings,
        f"Skipping cleanup path '{relative_path}' during execution: {reason}.",
    )


def _actual_index_object_ids(
    plan: dict[str, Any],
    *,
    contributions: tuple[CleanupContribution, ...],
    deleted_paths: set[str],
    path_categories: dict[str, Any],
) -> dict[str, list[str]]:
    fields = tuple(
        contribution.index_projection.object_ids_field
        for contribution in contributions
        if contribution.index_projection is not None
    )
    deleted_ids_by_field: dict[str, set[str]] = {field: set() for field in fields}
    for contribution in contributions:
        projection = contribution.index_projection
        if projection is None or projection.object_ids_field not in deleted_ids_by_field:
            continue
        records = plan.get(projection.records_field, [])
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            object_id = record.get("id")
            object_path = record.get("object_path")
            if (
                isinstance(object_id, str)
                and object_id
                and isinstance(object_path, str)
                and object_path in deleted_paths
                and path_categories.get(object_path) == contribution.category
            ):
                deleted_ids_by_field[projection.object_ids_field].add(object_id)

    actual: dict[str, list[str]] = {}
    for field in fields:
        planned_ids = plan.get(field, [])
        if not isinstance(planned_ids, list):
            planned_ids = []
        actual[field] = [
            object_id
            for object_id in planned_ids
            if isinstance(object_id, str) and object_id in deleted_ids_by_field[field]
        ]
    return actual


def execute_cleanup_plan(
    plan: dict[str, Any],
    *,
    contributions: tuple[CleanupContribution, ...] = (),
) -> dict[str, Any]:
    contributions = validate_cleanup_contributions(contributions)
    root = Path(plan["repo_root"])
    planned_warnings = plan.get("warnings")
    warnings = list(planned_warnings) if isinstance(planned_warnings, list) else []
    path_categories = plan.get("path_categories", {})
    if not isinstance(path_categories, dict):
        path_categories = {}
    external_delete_paths = plan.get("external_delete_paths", {})
    if not isinstance(external_delete_paths, dict):
        external_delete_paths = {}
    direct_delete_paths = plan.get("direct_delete_paths", [])
    if not isinstance(direct_delete_paths, list) or not all(
        isinstance(path, str) and path for path in direct_delete_paths
    ):
        raise ValueError("Refusing cleanup execution: planned delete paths are invalid.")

    shared_root_value = plan.get("shared_root")
    shared_root: Path | None = None
    resolved_shared_root: Path | None = None
    if shared_root_value is not None:
        if not isinstance(shared_root_value, str) or not shared_root_value:
            raise ValueError("Refusing cleanup execution: shared root is invalid.")
        shared_root = Path(shared_root_value)
        resolved_shared_root = _validated_execution_root(
            shared_root,
            label="shared root",
        )

    if not root.exists() and not root.is_symlink():
        state_relative_paths = [
            path for path in direct_delete_paths if path not in external_delete_paths
        ]
        expected_state_root = shared_root / "state" if shared_root is not None else None
        may_initialize_empty_state = (
            expected_state_root is not None
            and Path(os.path.abspath(root))
            == Path(os.path.abspath(expected_state_root))
            and not state_relative_paths
            and bool(_required_directories(contributions))
        )
        if may_initialize_empty_state:
            root.mkdir()
    resolved_root = _validated_execution_root(root, label="state root")

    execution_paths = sorted(
        set(direct_delete_paths),
        key=lambda path: (-len(Path(path).parts), path),
    )
    deleted_paths: list[str] = []
    deleted_set: set[str] = set()

    for relative_path in execution_paths:
        category = path_categories.get(relative_path)
        has_external_path = relative_path in external_delete_paths

        if has_external_path:
            stored_external_path = external_delete_paths[relative_path]
            if (
                shared_root is None
                or resolved_shared_root is None
                or category != "actor_private_files"
            ):
                _append_execution_warning(
                    warnings,
                    relative_path=relative_path,
                    reason="external path has no current actor-private shared-root authority",
                )
                continue
            if not isinstance(stored_external_path, str):
                _append_execution_warning(
                    warnings,
                    relative_path=relative_path,
                    reason="stored external path is invalid",
                )
                continue
            expected_external_path = shared_root / relative_path
            actual_external_path = Path(stored_external_path)
            if (
                not actual_external_path.is_absolute()
                or Path(os.path.abspath(actual_external_path))
                != Path(os.path.abspath(expected_external_path))
            ):
                _append_execution_warning(
                    warnings,
                    relative_path=relative_path,
                    reason="stored external path no longer agrees with the shared-root derivation",
                )
                continue
            target_path, blocked_reason = _guard_execution_target(
                shared_root,
                resolved_root=resolved_shared_root,
                relative_path=relative_path,
            )
            owner = _actor_private_owner(
                shared_root,
                relative_path=relative_path,
                external=True,
            )
        else:
            if category == "actor_private_files" and shared_root is not None:
                _append_execution_warning(
                    warnings,
                    relative_path=relative_path,
                    reason="actor-private path is missing its shared-root derivation",
                )
                continue
            target_path, blocked_reason = _guard_execution_target(
                root,
                resolved_root=resolved_root,
                relative_path=relative_path,
            )
            owner = (
                _actor_private_owner(
                    root,
                    relative_path=relative_path,
                    external=False,
                )
                if category == "actor_private_files"
                else None
            )

        if target_path is None:
            _append_execution_warning(
                warnings,
                relative_path=relative_path,
                reason=blocked_reason or "path is not executable",
            )
            continue

        deleted = False
        owner_reason: str | None = None
        if category == "actor_private_files":
            if owner is None:
                owner_reason = "path does not identify a current actor-private owner"
            else:
                private_root, logical_name = owner
                deleted, owner_reason = _delete_actor_private_target(
                    target_path,
                    private_root=private_root,
                    logical_name=logical_name,
                )
        elif has_external_path:
            owner_reason = "external path category is not actor-private"
        else:
            deleted = delete_relative_path(root, relative_path)
            if not deleted:
                owner_reason = "target changed before deletion"

        if not deleted:
            _append_execution_warning(
                warnings,
                relative_path=relative_path,
                reason=owner_reason or "deletion produced no effect",
            )
            continue
        deleted_paths.append(relative_path)
        deleted_set.add(relative_path)

    actual_object_ids = _actual_index_object_ids(
        plan,
        contributions=contributions,
        deleted_paths=deleted_set,
        path_categories=path_categories,
    )
    ensure_required_skeleton(
        root,
        contributions=contributions,
        warnings=warnings,
    )
    warnings.sort()
    result = {
        "ok": True,
        "scope": plan["scope"],
        "role": plan["role"],
        "deleted_paths": deleted_paths,
        "deleted_count": len(deleted_paths),
        "warnings": warnings,
    }
    result.update(actual_object_ids)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BuddySwitch cleanup utility (manual use only)")
    parser.add_argument("--state-root", type=Path, help="Cleanup state root. Defaults to the active shared-state root.")
    parser.add_argument(
        "--shared-root",
        type=Path,
        help="Shared BuddySwitch root used to discover instance workspaces for instance-local cleanup.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--role")
    target.add_argument("--all-data", action="store_true")
    parser.add_argument("--yes", action="store_true")
    return parser


def resolve_scope(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.role:
        return "role", args.role
    if args.all_data:
        return "all-data", None
    raise ValueError("No cleanup target provided")


def resolve_state_root_arg(*, state_root_arg: Path | None, shared_root: Path | None) -> Path:
    if state_root_arg is None:
        return ROOT
    if state_root_arg.is_symlink():
        raise ValueError(f"Refusing cleanup: state root argument is a symlink ({state_root_arg}).")

    resolved_state_argument = state_root_arg.resolve()
    if shared_root is None:
        return resolved_state_argument

    resolved_shared_root = shared_root.resolve(strict=False)
    resolved_state_root = (shared_root / "state").resolve(strict=False)
    if not is_path_within(resolved_state_root, resolved_shared_root):
        raise ValueError(
            "Refusing cleanup: shared-state root resolves outside shared root "
            f"({resolved_state_root} not within {resolved_shared_root})."
        )
    if not is_path_within(resolved_state_argument, resolved_state_root):
        raise ValueError(
            f"Refusing cleanup: state root resolves outside shared-state root ({resolved_state_argument})."
        )
    return resolved_state_argument


def main(
    *,
    contributions: tuple[CleanupContribution, ...],
    valid_role_ids: frozenset[str],
) -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        shared_root = args.shared_root if args.shared_root else None
        if shared_root is not None and shared_root.is_symlink():
            raise ValueError(f"Refusing cleanup: shared root argument is a symlink ({shared_root}).")
        repo_root = resolve_state_root_arg(state_root_arg=args.state_root, shared_root=shared_root)
        scope, role = resolve_scope(args)
        plan = build_cleanup_plan(
            scope=scope,
            role=role,
            repo_root=repo_root,
            valid_role_ids=valid_role_ids,
            shared_root=shared_root,
            contributions=contributions,
        )

        if not args.yes:
            print(json.dumps(plan, ensure_ascii=True, sort_keys=True))
            return 0

        result = execute_cleanup_plan(
            plan,
            contributions=contributions,
        )
        print(json.dumps({"plan": plan, "result": result}, ensure_ascii=True, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
