#!/usr/bin/env python3
"""Storage-aware BuddySwitch cleanup backend."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    from env_manifest import ManifestError, load_manifest as _load_manifest_full
except ModuleNotFoundError:  # pragma: no cover - exercised in shell integration fixture
    class ManifestError(ValueError):
        """Manifest validation error."""

    _load_manifest_full = None

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_ORDER = (
    "artifact_objects",
    "task_objects",
    "track_objects",
    "message_objects",
    "comment_objects",
)


def _strip_toml_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    output: list[str] = []
    for char in line:
        if escaped:
            output.append(char)
            escaped = False
            continue
        if char == "\\" and in_double:
            output.append(char)
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            output.append(char)
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            output.append(char)
            continue
        if char == "#" and not in_single and not in_double:
            break
        output.append(char)
    return "".join(output)


def _strip_toml_quotes(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1].strip()
    return value


def _load_valid_buddies_minimal(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        raise ManifestError(f"Manifest not found: {manifest_path}")

    buddy_ids: set[str] = set()
    current_section: str | None = None
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = _strip_toml_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("[[") and line.endswith("]]"):
            current_section = line[2:-2].strip()
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = None
            continue
        if current_section != "buddies" or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip() != "id":
            continue
        buddy_id = _strip_toml_quotes(raw_value.strip())
        if buddy_id:
            buddy_ids.add(buddy_id)
    if not buddy_ids:
        raise ManifestError("manifest must define at least one [[buddies]] id")
    return buddy_ids


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


def resolve_guarded_object_json_path(
    root: Path,
    *,
    relative_dir: str,
    object_id: str,
) -> tuple[Path | None, str | None]:
    object_name = Path(f"{object_id}.json")
    if object_name.is_absolute() or ".." in object_name.parts or len(object_name.parts) != 1:
        return None, f"invalid cleanup object id '{object_id}'."

    target_dir, blocked_reason = resolve_guarded_relative_dir(root, relative_dir)
    if target_dir is None:
        return None, blocked_reason

    target_path = target_dir / object_name.name
    if target_path.is_symlink():
        return None, f"cleanup target '{rel(root, target_path)}' is a symlink."

    resolved_root = root.resolve(strict=False)
    resolved_target_path = target_path.resolve(strict=False)
    if not is_path_within(resolved_target_path, resolved_root):
        return None, "cleanup path resolves outside repo root."
    return target_path, None


def iter_files(root: Path, relative_dir: str) -> list[Path]:
    target_dir, _ = resolve_guarded_relative_dir(root, relative_dir)
    if target_dir is None:
        return []
    return iter_directory_files(target_dir)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def append_warning(warnings: list[str] | None, message: str) -> None:
    if warnings is None:
        return
    if message not in warnings:
        warnings.append(message)


def load_valid_buddies(manifest_path: Path) -> set[str]:
    if _load_manifest_full is not None:
        try:
            data = _load_manifest_full(manifest_path)
            ids = {
                buddy["id"]
                for buddy in data.get("buddies", [])
                if isinstance(buddy, dict) and isinstance(buddy.get("id"), str) and buddy["id"].strip()
            }
            if ids:
                return ids
        except (ManifestError, OSError, ValueError, json.JSONDecodeError):
            pass
    return _load_valid_buddies_minimal(manifest_path)


def new_plan(scope: str, *, buddy: str | None = None) -> dict[str, Any]:
    counts = {key: 0 for key in CATEGORY_ORDER}
    return {
        "scope": scope,
        "buddy": buddy,
        "delete_paths": [],
        "artifact_object_ids": [],
        "task_object_ids": [],
        "message_object_ids": [],
        "comment_object_ids": [],
        "warnings": [],
        "counts_by_category": counts,
        "artifact_records": [],
        "task_records": [],
        "message_records": [],
        "comment_records": [],
        "direct_delete_paths": [],
        "external_delete_paths": {},
    }


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


def discover_artifact_objects(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in iter_files(root, "buddyswitch/objects/artifacts"):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid artifact object JSON: {exc}"})
            continue

        artifact_id = payload.get("id")
        producer_buddy = payload.get("created_by")
        if not isinstance(artifact_id, str) or not artifact_id:
            invalid.append({"path": relative, "reason": "artifact object is missing id"})
            continue
        if not isinstance(producer_buddy, str) or not producer_buddy:
            invalid.append({"path": relative, "reason": f"artifact '{artifact_id}' is missing created_by"})
            continue

        record = {
            "id": artifact_id,
            "producer_buddy": producer_buddy,
            "object_path": relative,
        }
        valid.append(record)
    return valid, invalid


def discover_task_objects(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in iter_files(root, "buddyswitch/objects/tasks"):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid task object JSON: {exc}"})
            continue

        task_id = payload.get("id")
        task_buddy = payload.get("buddy")
        if not isinstance(task_id, str) or not task_id:
            invalid.append({"path": relative, "reason": "task object is missing id"})
            continue
        if not isinstance(task_buddy, str) or not task_buddy:
            invalid.append({"path": relative, "reason": f"task '{task_id}' is missing buddy"})
            continue

        valid.append(
            {
                "id": task_id,
                "buddy": task_buddy,
                "track_id": payload.get("track_id"),
                "object_path": relative,
            }
        )
    return valid, invalid


def discover_message_objects(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in iter_files(root, "buddyswitch/objects/messages"):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid message object JSON: {exc}"})
            continue

        msg_id = payload.get("id")
        from_buddy = payload.get("from_buddy")
        to_buddy = payload.get("to_buddy")
        if not isinstance(msg_id, str) or not msg_id:
            invalid.append({"path": relative, "reason": "message object is missing id"})
            continue
        if not isinstance(from_buddy, str) or not from_buddy:
            invalid.append({"path": relative, "reason": f"message '{msg_id}' is missing from_buddy"})
            continue

        valid.append({
            "id": msg_id,
            "from_buddy": from_buddy,
            "to_buddy": to_buddy,
            "object_path": relative,
        })
    return valid, invalid


def discover_comment_objects(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in iter_files(root, "buddyswitch/objects/comments"):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid comment object JSON: {exc}"})
            continue

        cmt_id = payload.get("id")
        author_buddy = payload.get("author_buddy")
        target_type = payload.get("target_type")
        target_id = payload.get("target_id")
        if not isinstance(cmt_id, str) or not cmt_id:
            invalid.append({"path": relative, "reason": "comment object is missing id"})
            continue
        if not isinstance(author_buddy, str) or not author_buddy:
            invalid.append({"path": relative, "reason": f"comment '{cmt_id}' is missing author_buddy"})
            continue

        valid.append({
            "id": cmt_id,
            "author_buddy": author_buddy,
            "target_type": target_type,
            "target_id": target_id,
            "object_path": relative,
        })
    return valid, invalid


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
    buddy_filter: str | None,
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

        instance_buddy: str | None = None
        instance_json = instance_root / "instance.json"
        if instance_json.exists():
            try:
                payload = read_json(instance_json)
            except (OSError, ValueError, json.JSONDecodeError):
                payload = {}
                if buddy_filter is not None:
                    add_warning(
                        plan,
                        f"Skipping buddy-filtered cleanup for '{instance_root.name}': invalid instance.json.",
                    )
            buddy_value = payload.get("buddy")
            if isinstance(buddy_value, str) and buddy_value:
                instance_buddy = buddy_value

        if buddy_filter is not None:
            if instance_buddy is None:
                add_warning(
                    plan,
                    f"Skipping buddy-filtered cleanup for '{instance_root.name}': missing buddy in instance.json.",
                )
                continue
            if instance_buddy != buddy_filter:
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


def add_indexed_artifact(plan: dict[str, Any], record: dict[str, Any]) -> None:
    root = Path(plan["repo_root"])
    if record["id"] not in plan["artifact_object_ids"]:
        plan["artifact_object_ids"].append(record["id"])
        plan["artifact_records"].append(record)

    object_path = root / record["object_path"]
    add_path(plan, object_path, "artifact_objects")


def add_indexed_task(plan: dict[str, Any], record: dict[str, Any]) -> None:
    root = Path(plan["repo_root"])
    if record["id"] not in plan["task_object_ids"]:
        plan["task_object_ids"].append(record["id"])
        plan["task_records"].append(record)

    object_path = root / record["object_path"]
    add_path(plan, object_path, "task_objects")


def delete_relative_path(root: Path, relative_path: str) -> None:
    resolved = repo_path(root, relative_path)
    if resolved is None or (not resolved.exists() and not resolved.is_symlink()):
        return
    if resolved.is_dir() and not resolved.is_symlink():
        shutil.rmtree(resolved)
        return
    resolved.unlink()


def delete_absolute_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def ensure_required_skeleton(root: Path, *, warnings: list[str] | None = None) -> None:
    for relative_dir in (
        "buddyswitch/objects/tracks",
        "buddyswitch/objects/tasks",
        "buddyswitch/objects/artifacts",
        "buddyswitch/objects/messages",
        "buddyswitch/objects/comments",
    ):
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


def default_manifest_path(repo_root: Path) -> Path:
    return repo_root / "buddyswitch" / "manifest.toml"


def build_cleanup_plan(
    *,
    scope: str,
    buddy: str | None,
    repo_root: Path = ROOT,
    manifest_path: Path | None = None,
    shared_root: Path | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path or default_manifest_path(repo_root)
    valid_buddies = load_valid_buddies(manifest_path)
    if scope == "buddy" and (buddy is None or buddy not in valid_buddies):
        raise ValueError(f"Invalid buddy '{buddy}'. Check buddyswitch/manifest.toml")

    plan = new_plan(scope, buddy=buddy)
    plan["repo_root"] = str(repo_root)
    plan["shared_root"] = str(shared_root) if shared_root is not None else None
    plan["_path_categories"] = {}

    artifact_objects, invalid_artifact_objects = discover_artifact_objects(repo_root)
    task_objects, invalid_task_objects = discover_task_objects(repo_root)
    message_objects, invalid_message_objects = discover_message_objects(repo_root)
    comment_objects, invalid_comment_objects = discover_comment_objects(repo_root)
    if scope == "buddy":
        for record in artifact_objects:
            if record["producer_buddy"] == buddy:
                add_indexed_artifact(plan, record)
        for record in task_objects:
            if record["buddy"] == buddy:
                add_indexed_task(plan, record)
        for record in message_objects:
            if record.get("from_buddy") == buddy or record.get("to_buddy") == buddy:
                if record["id"] not in plan["message_object_ids"]:
                    plan["message_object_ids"].append(record["id"])
                    plan["message_records"].append(record)
                object_path = repo_root / record["object_path"]
                add_path(plan, object_path, "message_objects")
        for record in comment_objects:
            if record.get("author_buddy") == buddy:
                if record["id"] not in plan["comment_object_ids"]:
                    plan["comment_object_ids"].append(record["id"])
                    plan["comment_records"].append(record)
                object_path = repo_root / record["object_path"]
                add_path(plan, object_path, "comment_objects")
        for item in invalid_artifact_objects:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to buddy '{buddy}' and will be skipped in scoped cleanup ({item['reason']}).",
            )
        for item in invalid_task_objects:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to buddy '{buddy}' and will be skipped in scoped cleanup ({item['reason']}).",
            )
        for item in invalid_message_objects:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to buddy '{buddy}' and will be skipped in scoped cleanup ({item['reason']}).",
            )
        for item in invalid_comment_objects:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to buddy '{buddy}' and will be skipped in scoped cleanup ({item['reason']}).",
            )

    elif scope == "all-data":
        add_dir_files(plan, "buddyswitch/objects/tracks", "track_objects")
        add_dir_files(plan, "buddyswitch/objects/tasks", "task_objects")
        add_dir_files(plan, "buddyswitch/objects/artifacts", "artifact_objects")
        add_dir_files(plan, "buddyswitch/objects/messages", "message_objects")
        add_dir_files(plan, "buddyswitch/objects/comments", "comment_objects")
        for record in artifact_objects:
            if record["id"] not in plan["artifact_object_ids"]:
                plan["artifact_object_ids"].append(record["id"])
                plan["artifact_records"].append(record)
        for record in task_objects:
            if record["id"] not in plan["task_object_ids"]:
                plan["task_object_ids"].append(record["id"])
                plan["task_records"].append(record)
        for record in message_objects:
            if record["id"] not in plan["message_object_ids"]:
                plan["message_object_ids"].append(record["id"])
                plan["message_records"].append(record)
        for record in comment_objects:
            if record["id"] not in plan["comment_object_ids"]:
                plan["comment_object_ids"].append(record["id"])
                plan["comment_records"].append(record)
        for item in invalid_artifact_objects:
            add_warning(plan, f"All-data cleanup will delete malformed artifact object: {item['path']} ({item['reason']}).")
        for item in invalid_task_objects:
            add_warning(plan, f"All-data cleanup will delete malformed task object: {item['path']} ({item['reason']}).")
        for item in invalid_message_objects:
            add_warning(plan, f"All-data cleanup will delete malformed message object: {item['path']} ({item['reason']}).")
        for item in invalid_comment_objects:
            add_warning(plan, f"All-data cleanup will delete malformed comment object: {item['path']} ({item['reason']}).")
    else:
        raise ValueError(f"Unsupported cleanup scope: {scope}")

    plan["delete_paths"].sort()
    plan["artifact_object_ids"].sort()
    plan["task_object_ids"].sort()
    plan["message_object_ids"].sort()
    plan["comment_object_ids"].sort()
    plan["direct_delete_paths"] = sorted(set(plan["direct_delete_paths"]))
    plan["external_delete_paths"] = {
        key: plan["external_delete_paths"][key] for key in sorted(plan["external_delete_paths"])
    }
    plan["warnings"].sort()
    plan.pop("_path_categories", None)
    return plan


def execute_cleanup_plan(plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(plan["repo_root"])
    deleted_paths: list[str] = []
    warnings = plan.get("warnings")
    if not isinstance(warnings, list):
        warnings = None

    indexed_artifact_paths = set()
    for record in plan["artifact_records"]:
        indexed_artifact_paths.add(record["object_path"])

    indexed_task_paths = set()
    for record in plan["task_records"]:
        indexed_task_paths.add(record["object_path"])

    indexed_message_paths = set()
    for record in plan["message_records"]:
        indexed_message_paths.add(record["object_path"])

    indexed_comment_paths = set()
    for record in plan["comment_records"]:
        indexed_comment_paths.add(record["object_path"])

    indexed_all_paths = indexed_artifact_paths | indexed_task_paths | indexed_message_paths | indexed_comment_paths

    for relative_path in sorted(indexed_all_paths):
        delete_relative_path(root, relative_path)
        deleted_paths.append(relative_path)

    for relative_path in plan["direct_delete_paths"]:
        if relative_path in indexed_all_paths:
            continue
        external_path = plan.get("external_delete_paths", {}).get(relative_path)
        if external_path is not None:
            delete_absolute_path(Path(external_path))
        else:
            delete_relative_path(root, relative_path)
        deleted_paths.append(relative_path)

    ensure_required_skeleton(root, warnings=warnings)
    if isinstance(warnings, list):
        warnings.sort()
    return {
        "ok": True,
        "scope": plan["scope"],
        "buddy": plan["buddy"],
        "deleted_paths": deleted_paths,
        "deleted_count": len(deleted_paths),
        "artifact_object_ids": plan["artifact_object_ids"],
        "task_object_ids": plan["task_object_ids"],
        "message_object_ids": plan["message_object_ids"],
        "comment_object_ids": plan["comment_object_ids"],
        "warnings": plan["warnings"],
    }


def print_text_plan(plan: dict[str, Any]) -> None:
    if plan["scope"] == "buddy":
        target = f"--buddy {plan['buddy']}"
    elif plan["scope"] == "all-data":
        target = "--all-data"
    else:
        target = "--all-data"

    print("BuddySwitch cleanup plan")
    print(f"Repo root: {plan['repo_root']}")
    print(f"Target: {target}")
    print()
    print("Counts by category:")
    has_any = False
    for key in CATEGORY_ORDER:
        count = plan["counts_by_category"].get(key, 0)
        if count:
            print(f"  - {key}: {count}")
            has_any = True
    if not has_any:
        print("  - no files matched")
    print()
    print(f"Delete candidates: {len(plan['delete_paths'])}")
    for path in plan["delete_paths"]:
        print(f"  - {path}")
    if plan["warnings"]:
        print()
        print("Warnings:")
        for warning in plan["warnings"]:
            print(f"  - {warning}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BuddySwitch cleanup utility (manual use only)")
    parser.add_argument("--repo-root", type=Path, help="Cleanup root. Defaults to the current script checkout root.")
    parser.add_argument(
        "--shared-root",
        type=Path,
        help="Shared BuddySwitch root used to discover instance workspaces for instance-local cleanup.",
    )
    parser.add_argument("--manifest", type=Path, help="Manifest path. Defaults to <repo-root>/buddyswitch/manifest.toml.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--buddy")
    target.add_argument("--all-data", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print cleanup plan/result as JSON.")
    return parser


def resolve_scope(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.buddy:
        return "buddy", args.buddy
    if args.all_data:
        return "all-data", None
    raise ValueError("No cleanup target provided")


def resolve_repo_root_arg(*, repo_root_arg: Path | None, shared_root: Path | None) -> Path:
    if repo_root_arg is None:
        return ROOT
    if repo_root_arg.is_symlink():
        raise ValueError(f"Refusing cleanup: repo root argument is a symlink ({repo_root_arg}).")

    resolved_repo_root = repo_root_arg.resolve()
    if shared_root is None:
        return resolved_repo_root

    resolved_shared_root = shared_root.resolve(strict=False)
    resolved_state_root = (shared_root / "state").resolve(strict=False)
    if not is_path_within(resolved_state_root, resolved_shared_root):
        raise ValueError(
            "Refusing cleanup: shared-state root resolves outside shared root "
            f"({resolved_state_root} not within {resolved_shared_root})."
        )
    if not is_path_within(resolved_repo_root, resolved_state_root):
        raise ValueError(
            f"Refusing cleanup: repo root resolves outside shared-state root ({resolved_repo_root})."
        )
    return resolved_repo_root


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        shared_root = args.shared_root if args.shared_root else None
        if shared_root is not None and shared_root.is_symlink():
            raise ValueError(f"Refusing cleanup: shared root argument is a symlink ({shared_root}).")
        repo_root = resolve_repo_root_arg(repo_root_arg=args.repo_root, shared_root=shared_root)
        manifest_path = args.manifest.resolve() if args.manifest else default_manifest_path(repo_root)
        scope, buddy = resolve_scope(args)
        plan = build_cleanup_plan(
            scope=scope,
            buddy=buddy,
            repo_root=repo_root,
            manifest_path=manifest_path,
            shared_root=shared_root,
        )
        if not args.json:
            print_text_plan(plan)

        if not args.yes:
            if args.json:
                print(json.dumps(plan, ensure_ascii=True, indent=2))
            else:
                print()
                print("Preview mode: no files were deleted.")
            return 0

        result = execute_cleanup_plan(plan)
        if args.json:
            print(json.dumps({"plan": plan, "result": result}, ensure_ascii=True, indent=2))
        else:
            print()
            print(f"Cleanup completed. Deleted {result['deleted_count']} file(s).")
        return 0
    except (OSError, ValueError, ManifestError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
