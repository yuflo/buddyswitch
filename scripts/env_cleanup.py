"""Storage-aware BuddySwitch cleanup backend."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from env.repos import actor_private_files as actor_private_repo
from env.repos import runtime_files

try:
    from env_manifest import ManifestError, load_manifest as _load_manifest_full
except ModuleNotFoundError:  # pragma: no cover - exercised in shell integration fixture
    class ManifestError(ValueError):
        """Manifest validation error."""

    _load_manifest_full = None

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_ORDER = (
    "artifact_objects",
    "track_objects",
    "message_objects",
    "comment_objects",
    "actor_private_files",
)


def _runtime_relative_path(path: Path) -> str:
    return path.relative_to(runtime_files.STATE_ROOT).as_posix()


TRACK_OBJECTS_RELATIVE_DIR = _runtime_relative_path(runtime_files.TRACKS_DIR)
ARTIFACT_OBJECTS_RELATIVE_DIR = _runtime_relative_path(runtime_files.ARTIFACT_OBJECTS_DIR)
MESSAGE_OBJECTS_RELATIVE_DIR = _runtime_relative_path(runtime_files.STATE_ROOT / "im" / "messages")
RETIRED_MESSAGE_OBJECTS_RELATIVE_DIR = _runtime_relative_path(runtime_files.MESSAGES_DIR)
COMMENT_OBJECTS_RELATIVE_DIR = _runtime_relative_path(runtime_files.TRACK_COMMENTS_DIR)
ACTOR_PRIVATE_RELATIVE_DIR = "private"


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


def _load_valid_roles_minimal(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        raise ManifestError(f"Manifest not found: {manifest_path}")

    role_ids: set[str] = set()
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
        if current_section != "roles" or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        if key.strip() != "id":
            continue
        role_id = _strip_toml_quotes(raw_value.strip())
        if role_id:
            role_ids.add(role_id)
    if not role_ids:
        raise ManifestError("manifest must define at least one [[roles]] id")
    return role_ids


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


def _identity_id_from_ref(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        if isinstance(value.get("id"), str) and value["id"].strip():
            return value["id"].strip()
        identity = value.get("identity")
        if isinstance(identity, dict) and isinstance(identity.get("id"), str) and identity["id"].strip():
            return identity["id"].strip()
    return None


def _role_from_actor_identity_id(identity_id: str) -> str | None:
    if not identity_id.startswith("act-"):
        return None
    role_id, separator, _suffix = identity_id.removeprefix("act-").partition("-")
    if not separator or not role_id:
        return None
    return role_id


def append_warning(warnings: list[str] | None, message: str) -> None:
    if warnings is None:
        return
    if message not in warnings:
        warnings.append(message)


def load_valid_roles(manifest_path: Path) -> set[str]:
    if _load_manifest_full is not None:
        try:
            data = _load_manifest_full(manifest_path)
            ids = {
                role["id"]
                for role in data.get("roles", [])
                if isinstance(role, dict) and isinstance(role.get("id"), str) and role["id"].strip()
            }
            if ids:
                return ids
        except (ManifestError, OSError, ValueError, json.JSONDecodeError):
            pass
    return _load_valid_roles_minimal(manifest_path)


def new_plan(scope: str, *, role: str | None = None) -> dict[str, Any]:
    counts = {key: 0 for key in CATEGORY_ORDER}
    return {
        "scope": scope,
        "role": role,
        "delete_paths": [],
        "artifact_object_ids": [],
        "message_object_ids": [],
        "comment_object_ids": [],
        "warnings": [],
        "counts_by_category": counts,
        "artifact_records": [],
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
    for path in iter_files(root, ARTIFACT_OBJECTS_RELATIVE_DIR):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid artifact object JSON: {exc}"})
            continue

        artifact_id = payload.get("id")
        created_by_actor = payload.get("created_by_actor")
        producer_role = created_by_actor.get("role_id") if isinstance(created_by_actor, dict) else None
        if not isinstance(artifact_id, str) or not artifact_id:
            invalid.append({"path": relative, "reason": "artifact object is missing id"})
            continue
        if not isinstance(producer_role, str) or not producer_role:
            invalid.append({"path": relative, "reason": f"artifact '{artifact_id}' is missing created_by_actor.role_id"})
            continue

        record = {
            "id": artifact_id,
            "producer_role": producer_role,
            "object_path": relative,
        }
        valid.append(record)
    return valid, invalid


def discover_message_objects(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in iter_files(root, MESSAGE_OBJECTS_RELATIVE_DIR):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid message object JSON: {exc}"})
            continue

        msg_id = payload.get("id")
        if not isinstance(msg_id, str) or not msg_id:
            invalid.append({"path": relative, "reason": "message object is missing id"})
            continue
        conversation_id = payload.get("conversation_id")
        if not isinstance(conversation_id, str) or not conversation_id:
            invalid.append({"path": relative, "reason": f"message '{msg_id}' is missing conversation_id"})
            continue
        sender_identity_id = _identity_id_from_ref(payload.get("sender_identity"))
        target_identity_id = _identity_id_from_ref(payload.get("target_identity"))
        if sender_identity_id is None:
            invalid.append({"path": relative, "reason": f"message '{msg_id}' is missing sender_identity.id"})
            continue
        if target_identity_id is None:
            invalid.append({"path": relative, "reason": f"message '{msg_id}' is missing target_identity.id"})
            continue

        valid.append({
            "id": msg_id,
            "conversation_id": conversation_id,
            "sender_identity_id": sender_identity_id,
            "target_identity_id": target_identity_id,
            "from_role": _role_from_actor_identity_id(sender_identity_id),
            "to_role": _role_from_actor_identity_id(target_identity_id),
            "object_path": relative,
        })
    for path in iter_files(root, RETIRED_MESSAGE_OBJECTS_RELATIVE_DIR):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid retired message object JSON: {exc}"})
            continue
        msg_id = payload.get("id")
        label = f"message '{msg_id}'" if isinstance(msg_id, str) and msg_id else "message object"
        invalid.append({
            "path": relative,
            "reason": f"{label} uses retired message object schema; current IM messages live under {MESSAGE_OBJECTS_RELATIVE_DIR}",
        })
    return valid, invalid


def discover_comment_objects(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in iter_files(root, COMMENT_OBJECTS_RELATIVE_DIR):
        relative = rel(root, path)
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({"path": relative, "reason": f"invalid comment object JSON: {exc}"})
            continue

        cmt_id = payload.get("id")
        by_actor = payload.get("by_actor")
        author_role = by_actor.get("role_id") if isinstance(by_actor, dict) else None
        track_id = payload.get("track_id")
        if not isinstance(cmt_id, str) or not cmt_id:
            invalid.append({"path": relative, "reason": "comment object is missing id"})
            continue
        if not isinstance(track_id, str) or not track_id:
            invalid.append({"path": relative, "reason": f"comment '{cmt_id}' is missing track_id"})
            continue
        if not isinstance(author_role, str) or not author_role:
            invalid.append({"path": relative, "reason": f"comment '{cmt_id}' is missing by_actor.role_id"})
            continue

        valid.append({
            "id": cmt_id,
            "author_role": author_role,
            "track_id": track_id,
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


def object_category_relative_dir(category: str) -> str:
    if category == "artifact_objects":
        return ARTIFACT_OBJECTS_RELATIVE_DIR
    if category == "message_objects":
        return MESSAGE_OBJECTS_RELATIVE_DIR
    if category == "comment_objects":
        return COMMENT_OBJECTS_RELATIVE_DIR
    if category == "track_objects":
        return TRACK_OBJECTS_RELATIVE_DIR
    raise ValueError(f"Unsupported object category: {category}")


def owner_object_json_path(root: Path, *, category: str, object_id: str) -> tuple[Path | None, str | None]:
    return resolve_guarded_object_json_path(
        root,
        relative_dir=object_category_relative_dir(category),
        object_id=object_id,
    )


def _parse_actor_private_owner_path(path: Path) -> tuple[Path, str] | None:
    parts = path.resolve(strict=False).parts
    marker = tuple(Path(ACTOR_PRIVATE_RELATIVE_DIR).parts)
    if not marker:
        return None
    window = len(marker)
    for index in range(0, len(parts) - window + 1):
        if tuple(parts[index : index + window]) != marker:
            continue
        marker_end = index + window
        if marker_end >= len(parts):
            return None
        logical_parts = parts[marker_end:]
        if not logical_parts:
            return None
        private_root = Path(*parts[:marker_end])
        logical_name = "/".join(logical_parts)
        return private_root, logical_name
    return None


def delete_actor_private_path(path: Path) -> bool:
    owner = _parse_actor_private_owner_path(path)
    if owner is None:
        return False
    private_root, logical_name = owner
    try:
        actor_private_repo.delete_private_file(root=private_root, logical_name=logical_name)
    except (actor_private_repo.ActorPrivateBoundaryError, IsADirectoryError, OSError):
        return False
    return True


def add_indexed_artifact(plan: dict[str, Any], record: dict[str, Any]) -> None:
    root = Path(plan["repo_root"])
    if record["id"] not in plan["artifact_object_ids"]:
        plan["artifact_object_ids"].append(record["id"])
        plan["artifact_records"].append(record)

    object_path, blocked_reason = owner_object_json_path(root, category="artifact_objects", object_id=str(record["id"]))
    if object_path is None:
        if blocked_reason is not None:
            add_warning(plan, f"Skipping artifact cleanup for '{record['id']}': {blocked_reason}")
        return
    add_path(plan, object_path, "artifact_objects")


def add_indexed_message(plan: dict[str, Any], record: dict[str, Any]) -> None:
    root = Path(plan["repo_root"])
    if record["id"] not in plan["message_object_ids"]:
        plan["message_object_ids"].append(record["id"])
        plan["message_records"].append(record)

    object_path, blocked_reason = owner_object_json_path(root, category="message_objects", object_id=str(record["id"]))
    if object_path is None:
        if blocked_reason is not None:
            add_warning(plan, f"Skipping message cleanup for '{record['id']}': {blocked_reason}")
        return
    add_path(plan, object_path, "message_objects")


def add_indexed_comment(plan: dict[str, Any], record: dict[str, Any]) -> None:
    root = Path(plan["repo_root"])
    if record["id"] not in plan["comment_object_ids"]:
        plan["comment_object_ids"].append(record["id"])
        plan["comment_records"].append(record)

    relative_path = record.get("object_path")
    if not isinstance(relative_path, str) or not relative_path:
        add_warning(plan, f"Skipping comment cleanup for '{record['id']}': missing object path")
        return
    object_path = root / relative_path
    add_path(plan, object_path, "comment_objects")


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
        TRACK_OBJECTS_RELATIVE_DIR,
        ARTIFACT_OBJECTS_RELATIVE_DIR,
        MESSAGE_OBJECTS_RELATIVE_DIR,
        COMMENT_OBJECTS_RELATIVE_DIR,
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
    role: str | None,
    repo_root: Path = ROOT,
    manifest_path: Path | None = None,
    shared_root: Path | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path or default_manifest_path(repo_root)
    valid_roles = load_valid_roles(manifest_path)
    if scope == "role" and (role is None or role not in valid_roles):
        raise ValueError(f"Invalid role '{role}'. Check buddyswitch/manifest.toml")

    plan = new_plan(scope, role=role)
    plan["repo_root"] = str(repo_root)
    plan["shared_root"] = str(shared_root) if shared_root is not None else None
    plan["_path_categories"] = {}

    artifact_objects, invalid_artifact_objects = discover_artifact_objects(repo_root)
    message_objects, invalid_message_objects = discover_message_objects(repo_root)
    comment_objects, invalid_comment_objects = discover_comment_objects(repo_root)
    if scope == "role":
        for record in artifact_objects:
            if record["producer_role"] == role:
                add_indexed_artifact(plan, record)
        for record in message_objects:
            if record.get("from_role") == role or record.get("to_role") == role:
                add_indexed_message(plan, record)
        for record in comment_objects:
            if record.get("author_role") == role:
                add_indexed_comment(plan, record)
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
        for item in invalid_artifact_objects:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to role '{role}' and will be skipped in scoped cleanup ({item['reason']}).",
            )
        for item in invalid_message_objects:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to role '{role}' and will be skipped in scoped cleanup ({item['reason']}).",
            )
        for item in invalid_comment_objects:
            add_warning(
                plan,
                f"{item['path']} cannot be safely attributed to role '{role}' and will be skipped in scoped cleanup ({item['reason']}).",
            )

    elif scope == "all-data":
        add_dir_files(plan, TRACK_OBJECTS_RELATIVE_DIR, "track_objects")
        add_dir_files(plan, ARTIFACT_OBJECTS_RELATIVE_DIR, "artifact_objects")
        add_dir_files(plan, MESSAGE_OBJECTS_RELATIVE_DIR, "message_objects")
        add_dir_files(plan, COMMENT_OBJECTS_RELATIVE_DIR, "comment_objects")
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
        for record in artifact_objects:
            if record["id"] not in plan["artifact_object_ids"]:
                plan["artifact_object_ids"].append(record["id"])
                plan["artifact_records"].append(record)
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
        for item in invalid_message_objects:
            add_warning(plan, f"All-data cleanup will delete malformed message object: {item['path']} ({item['reason']}).")
        for item in invalid_comment_objects:
            add_warning(plan, f"All-data cleanup will delete malformed comment object: {item['path']} ({item['reason']}).")
    else:
        raise ValueError(f"Unsupported cleanup scope: {scope}")

    plan["delete_paths"].sort()
    plan["artifact_object_ids"].sort()
    plan["message_object_ids"].sort()
    plan["comment_object_ids"].sort()
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


def execute_cleanup_plan(plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(plan["repo_root"])
    deleted_paths: list[str] = []
    warnings = plan.get("warnings")
    if not isinstance(warnings, list):
        warnings = None

    path_categories = plan.get("path_categories", {})
    if not isinstance(path_categories, dict):
        path_categories = {}
    deleted_set: set[str] = set()

    indexed_sets: tuple[tuple[str, str], ...] = (
        ("artifact_objects", "artifact_records"),
        ("message_objects", "message_records"),
        ("comment_objects", "comment_records"),
    )
    for category, records_key in indexed_sets:
        records = plan.get(records_key, [])
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            object_id = record.get("id")
            if not isinstance(object_id, str) or not object_id:
                continue
            raw_object_path = record.get("object_path")
            if isinstance(raw_object_path, str) and raw_object_path:
                relative_path = raw_object_path
            else:
                owner_path, _ = owner_object_json_path(root, category=category, object_id=object_id)
                if owner_path is None:
                    continue
                relative_path = rel(root, owner_path)
            if relative_path in deleted_set:
                continue
            delete_relative_path(root, relative_path)
            deleted_paths.append(relative_path)
            deleted_set.add(relative_path)

    for relative_path in plan["direct_delete_paths"]:
        if relative_path in deleted_set:
            continue
        category = path_categories.get(relative_path)
        external_path = plan.get("external_delete_paths", {}).get(relative_path)
        if external_path is not None:
            target_path = Path(external_path)
            if category == "actor_private_files" and delete_actor_private_path(target_path):
                pass
            else:
                delete_absolute_path(target_path)
        else:
            target_path = root / relative_path
            if category == "actor_private_files" and delete_actor_private_path(target_path):
                pass
            else:
                delete_relative_path(root, relative_path)
        deleted_paths.append(relative_path)
        deleted_set.add(relative_path)

    ensure_required_skeleton(root, warnings=warnings)
    if isinstance(warnings, list):
        warnings.sort()
    return {
        "ok": True,
        "scope": plan["scope"],
        "role": plan["role"],
        "deleted_paths": deleted_paths,
        "deleted_count": len(deleted_paths),
        "artifact_object_ids": plan["artifact_object_ids"],
        "message_object_ids": plan["message_object_ids"],
        "comment_object_ids": plan["comment_object_ids"],
        "warnings": plan["warnings"],
    }


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
        scope, role = resolve_scope(args)
        plan = build_cleanup_plan(
            scope=scope,
            role=role,
            repo_root=repo_root,
            manifest_path=manifest_path,
            shared_root=shared_root,
        )

        if not args.yes:
            print(json.dumps(plan, ensure_ascii=True, sort_keys=True))
            return 0

        result = execute_cleanup_plan(plan)
        print(json.dumps({"plan": plan, "result": result}, ensure_ascii=True, sort_keys=True))
        return 0
    except (OSError, ValueError, ManifestError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
