#!/usr/bin/env python3
"""BuddySwitch runtime: prepare turn context and persist structured results."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from env_manifest import (
    DEFAULT_MANIFEST,
    ManifestError,
    load_manifest,
    require_buddy,
)
import env_store
from env_store import (
    add_run_to_task,
    build_track_artifact_index,
    create_artifact,
    create_task,
    create_track,
    get_artifact,
    get_task,
    get_track,
    list_artifacts,
    list_tasks,
    list_tracks,
    now_iso,
    require_runtime_workspace_write_root,
    register_task_to_track,
    run_content_path,
    save_run_content,
    slugify,
    update_track,
)
from output_schema import OutputSchemaError, load_output_schema, validate_output_payload
ROOT = env_store.ROOT


TRACK_ACTIONS = ("create", "update", "advance", "archive")
STATUS_VALUES = ("active", "blocked", "done", "archived")
LEGACY_OUTPUT_ERROR = (
    "Derived markdown outputs are retired. Persist BuddySwitch state to task/artifact objects and run audits only."
)
_LEGACY_OUTPUT_PATTERNS = (
    re.compile(r"(artifacts/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\.md)"),
    re.compile(r"(runs/summaries/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\.md)"),
)
_PRODUCT_MODE_ENV_KEYS = (
    "BUDDYSWITCH_ACTIVE_BUDDY",
    "BUDDYSWITCH_INSTANCE_ID",
    "BUDDYSWITCH_INSTANCE_JSON",
)
_RUNTIME_LOCK_TIMEOUT_ENV = "BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"
_RUNTIME_LOCK_DEFAULT_TIMEOUT_SECONDS = 30.0
_RUNTIME_LOCK_POLL_SECONDS = 0.05


def runtime_error(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if extra:
        payload["error"].update(extra)
    return payload


def _load_product_mode_session(manifest_path: Path) -> dict[str, Any] | None:
    raw_env = {key: os.environ.get(key) for key in _PRODUCT_MODE_ENV_KEYS}
    if all(value is None for value in raw_env.values()):
        return None

    invalid_keys = [
        key
        for key, value in raw_env.items()
        if value is None or not isinstance(value, str) or not value.strip()
    ]
    if invalid_keys:
        raise ValueError(
            "Partial product-mode env is invalid: "
            + ", ".join(_PRODUCT_MODE_ENV_KEYS)
            + " must all be set to non-empty values."
        )

    assert all(isinstance(raw_env[key], str) for key in _PRODUCT_MODE_ENV_KEYS)
    active_buddy = raw_env["BUDDYSWITCH_ACTIVE_BUDDY"].strip()
    instance_id = raw_env["BUDDYSWITCH_INSTANCE_ID"].strip()
    instance_json = Path(raw_env["BUDDYSWITCH_INSTANCE_JSON"].strip())

    manifest = load_manifest(manifest_path)
    require_buddy(manifest, active_buddy)

    if not instance_json.exists():
        raise ValueError(f"BUDDYSWITCH_INSTANCE_JSON does not exist: {instance_json}")

    try:
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"BUDDYSWITCH_INSTANCE_JSON is not valid JSON: {instance_json}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"BUDDYSWITCH_INSTANCE_JSON must be a JSON object: {instance_json}")

    json_instance_id = payload.get("instance_id")
    if not isinstance(json_instance_id, str) or json_instance_id.strip() != instance_id:
        raise ValueError(
            "BUDDYSWITCH_INSTANCE_JSON instance_id mismatch: "
            f"expected '{instance_id}', found '{json_instance_id}'"
        )

    json_buddy = payload.get("buddy")
    if isinstance(json_buddy, str) and json_buddy.strip() and json_buddy.strip() != active_buddy:
        raise ValueError(
            "BUDDYSWITCH_INSTANCE_JSON buddy mismatch: "
            f"expected '{active_buddy}', found '{json_buddy.strip()}'"
        )

    return {
        "active_buddy": active_buddy,
        "instance_id": instance_id,
        "instance_json": instance_json,
        "payload": payload,
    }


def _product_runtime_shared_root(product_session: dict[str, Any]) -> Path:
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(raw_shared_root, str) and raw_shared_root.strip():
        return Path(raw_shared_root.strip())

    instance_json = product_session.get("instance_json")
    if not isinstance(instance_json, Path):
        raise ValueError("BUDDYSWITCH_SHARED_ROOT is required for product-mode runtime locking")

    instance_dir = instance_json.parent
    if instance_dir.parent.name == "instances":
        return instance_dir.parent.parent
    return instance_dir


def _runtime_lock_timeout_seconds() -> float:
    raw_timeout = os.environ.get(_RUNTIME_LOCK_TIMEOUT_ENV)
    if raw_timeout is None or raw_timeout.strip() == "":
        return _RUNTIME_LOCK_DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise ValueError(f"invalid {_RUNTIME_LOCK_TIMEOUT_ENV} value: {raw_timeout!r}") from exc
    if not math.isfinite(timeout):
        raise ValueError(f"runtime lock timeout must be finite, got {timeout}")
    if timeout < 0:
        raise ValueError(f"runtime lock timeout must be >= 0, got {timeout}")
    return timeout


@contextmanager
def _hold_product_runtime_lock(product_session: dict[str, Any]):
    shared_root = str(_product_runtime_shared_root(product_session)).rstrip("/")
    if not shared_root:
        raise ValueError("BUDDYSWITCH_SHARED_ROOT must not be empty")
    timeout_seconds = _runtime_lock_timeout_seconds()
    lock_path = Path(shared_root) / "run" / "locks" / "runtime.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"runtime state busy: could not acquire lock at {lock_path} within {timeout_seconds:.2f}s"
                    )
                time.sleep(_RUNTIME_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def _write_product_session_binding(
    product_session: dict[str, Any],
    *,
    task_id: str,
    track_id: str | None,
) -> None:
    instance_json = product_session.get("instance_json")
    payload = product_session.get("payload")
    if not isinstance(instance_json, Path):
        raise ValueError("product session instance_json is required")
    if not isinstance(payload, dict):
        raise ValueError("product session payload is required")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("resolved task_id is required for product session binding")
    if track_id is not None and (not isinstance(track_id, str) or not track_id.strip()):
        track_id = None

    updated = dict(payload)
    updated["current_task_id"] = task_id.strip()
    updated["current_track_id"] = track_id.strip() if isinstance(track_id, str) and track_id.strip() else None
    updated["updated_at"] = now_iso()
    _write_runtime_json(instance_json, updated)
    product_session["payload"] = updated


def _resolve_binding_from_payload(payload: dict[str, Any]) -> tuple[str, str | None]:
    task_id = payload.get("current_task_id")
    track_id = payload.get("current_track_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("prepare payload current_task_id is required for product session binding")
    if not isinstance(track_id, str) or not track_id.strip():
        track_id = None
    return task_id.strip(), track_id.strip() if isinstance(track_id, str) else None


def _raise_reservation_clear_failure(warning: dict[str, Any]) -> None:
    message = warning.get("message")
    run_id = warning.get("run_id")
    reservation_path = warning.get("reservation_path")
    raise ValueError(
        "run reservation rollback failed: "
        f"{message} (run_id={run_id}, reservation_path={reservation_path})"
    )


def _clear_reservation_from_payload(payload: dict[str, Any], *, fail_on_warning: bool = False) -> None:
    run_envelope = payload.get("run_envelope")
    if isinstance(run_envelope, dict):
        run_id = run_envelope.get("run_id")
        if isinstance(run_id, str) and run_id.strip():
            warning = _clear_run_reservation(run_id.strip())
            if warning is not None and fail_on_warning:
                _raise_reservation_clear_failure(warning)
    refreshed_context = payload.get("refreshed_context")
    if isinstance(refreshed_context, dict):
        _clear_reservation_from_payload(refreshed_context, fail_on_warning=fail_on_warning)


def _receipt_has_binding_update_warning(receipt: dict[str, Any]) -> bool:
    warnings = receipt.get("warnings")
    if not isinstance(warnings, list):
        return False
    return any(
        isinstance(item, dict) and item.get("code") == "W_INSTANCE_BINDING_UPDATE_FAILED"
        for item in warnings
    )


def _persist_binding_from_payload(payload: dict[str, Any]) -> tuple[str, str | None] | None:
    refreshed_context = payload.get("refreshed_context")
    if isinstance(refreshed_context, dict) and refreshed_context.get("ok") is True:
        return _resolve_binding_from_payload(refreshed_context)

    receipt = payload.get("receipt")
    if not isinstance(receipt, dict):
        return None
    refreshed_error = refreshed_context.get("error") if isinstance(refreshed_context, dict) else None
    if (
        isinstance(refreshed_error, dict)
        and refreshed_error.get("code") == "E_RUNTIME_REFRESH_CONTEXT"
        and not _receipt_has_binding_update_warning(receipt)
    ):
        next_state = receipt.get("next_state")
        if isinstance(next_state, dict):
            task_id = next_state.get("task_id")
            track_id = next_state.get("track_id")
        else:
            task_id = receipt.get("task_id")
            track_id = receipt.get("track_id")
        if not isinstance(task_id, str) or not task_id.strip():
            return None
        if not isinstance(track_id, str) or not track_id.strip():
            track_id = None
        return task_id.strip(), track_id.strip() if isinstance(track_id, str) else None
    return None


def _mark_committed_binding_update_failed(payload: dict[str, Any], product_session: dict[str, Any], exc: Exception) -> None:
    _clear_reservation_from_payload(payload)
    receipt = payload.setdefault("receipt", {})
    if not isinstance(receipt, dict):
        return
    warning = {
        "code": "W_INSTANCE_BINDING_UPDATE_FAILED",
        "message": f"instance binding update failed after persist commit: {exc}",
        "instance_id": product_session.get("instance_id"),
        "instance_json": str(product_session.get("instance_json")),
    }
    warnings = receipt.setdefault("warnings", [])
    if isinstance(warnings, list):
        warnings.append(warning)
    payload["refreshed_context"] = {
        "ok": False,
        "error": {
            "code": "E_RUNTIME_REFRESH_CONTEXT",
            "message": "instance binding update failed after persist commit; rerun prepare for next turn",
            "instance_id": product_session.get("instance_id"),
            "instance_json": str(product_session.get("instance_json")),
        },
    }


def _ensure_no_legacy_outputs(demand: str) -> None:
    for pattern in _LEGACY_OUTPUT_PATTERNS:
        match = pattern.search(demand)
        if match:
            raise ValueError(f"{LEGACY_OUTPUT_ERROR} Rejecting requested path '{match.group(1)}'.")


def _is_legacy_command_shaped_request(request_text: str) -> bool:
    stripped = request_text.lstrip()
    if not stripped.lower().startswith("switch "):
        return False
    remainder = stripped[len("switch ") :]
    colon_index = remainder.find(":")
    if colon_index < 0:
        return False
    command_prefix = remainder[:colon_index].strip()
    command_body = remainder[colon_index + 1 :].strip()
    return bool(command_prefix and command_body)


def _next_unique(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    index = 2
    while True:
        candidate = f"{base}-{index}"
        if candidate not in existing:
            return candidate
        index += 1


def _readable_demand_slug(demand: str) -> str:
    tokens = [token for token in slugify(demand).split("-") if token]
    if not tokens:
        tokens = ["task"]
    return "-".join(token[:10] for token in tokens[:4]).strip("-") or "task"


def _derive_create_token(demand: str) -> str:
    return f"{_readable_demand_slug(demand)}-{uuid.uuid4().hex[:8]}"


def _derive_task_id(buddy: str, demand: str, *, create_token: str | None = None) -> str:
    if isinstance(create_token, str) and create_token:
        token_slug = _readable_demand_slug(create_token)
        digest = hashlib.sha256(f"{buddy}\n{create_token}".encode("utf-8")).hexdigest()[:10]
        return f"task-{buddy}-{token_slug}-{digest}"

    short_slug = _readable_demand_slug(demand)
    existing = {row["id"] for row in list_tasks()}
    while True:
        candidate = f"task-{buddy}-{short_slug}-{uuid.uuid4().hex[:6]}"
        if candidate not in existing:
            return candidate


def _derive_track_id(demand: str) -> str:
    candidates: list[tuple[int, str]] = []
    patterns = (
        r"(?<![a-z0-9-])track\s+([a-z0-9][a-z0-9-]{1,80})\b",
        r"(?<![a-z0-9-])([a-z0-9][a-z0-9-]{1,80})\s+track\b(?!-)",
        r"继续\s*([a-z0-9][a-z0-9-]{1,80})\s*track",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, demand, flags=re.IGNORECASE):
            candidates.append((match.start(1), match.group(1).lower()))

    existing = {track["id"] for track in list_tracks()}
    if candidates:
        candidates.sort(key=lambda item: item[0])
        preferred = candidates[0][1]
        if preferred.startswith("track-"):
            return _next_unique(preferred, existing)
        return _next_unique(f"track-{preferred}", existing)

    cleaned = slugify(demand).replace("switch", "").replace("track", "").strip("-") or "track"
    if not cleaned.startswith("track"):
        cleaned = f"track-{cleaned}"
    return _next_unique(cleaned, existing)


def _derive_task_title(demand: str) -> str:
    words = demand.split()
    snippet = " ".join(words[:8]).strip()
    return snippet if snippet else "Task"


def _derive_artifact_title(active_buddy: str, skill_id: str, request_text: str) -> str:
    snippet = " ".join(request_text.split()[:8]).strip()
    if snippet:
        return f"{active_buddy.upper()} {skill_id} - {snippet}"
    return f"{active_buddy.upper()} {skill_id}"


def _derive_artifact_id(task_id: str, kind: str) -> str:
    existing = {artifact["id"] for artifact in list_artifacts()}
    base = f"art-{slugify(f'{task_id}-{kind}')}"
    return _next_unique(base, existing)


def _build_next_state(
    *,
    task_id: str,
    track_id: str | None,
    current_buddy: str,
    next_buddy: str | None,
    track_action: str | None = None,
) -> dict[str, Any]:
    resolved_next_buddy = next_buddy if isinstance(next_buddy, str) and next_buddy.strip() else None
    mode = "handoff" if resolved_next_buddy and resolved_next_buddy != current_buddy else "continue_current_task"
    if track_action == "archive":
        mode = "track_archived"
    return {
        "task_id": task_id,
        "track_id": track_id,
        "current_buddy": current_buddy,
        "next_buddy": resolved_next_buddy,
        "mode": mode,
    }


def _resolve_execution_skill(
    *,
    buddy_id: str,
    skill_id: str,
    manifest_path: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    buddy = require_buddy(manifest, buddy_id)
    allowed_skill_ids = {row for row in buddy.get("skills", []) if isinstance(row, str)}
    if skill_id not in allowed_skill_ids:
        raise ValueError(f"skill_id '{skill_id}' is not available for buddy '{buddy_id}' in the manifest")
    selected_skill = next((skill for skill in manifest.get("skills", []) if skill.get("id") == skill_id), None)
    if selected_skill is None:
        raise ValueError(f"skill '{skill_id}' is missing from manifest skills list")
    return selected_skill


def _validate_context_revision(context: dict[str, Any]) -> dict[str, Any]:
    context_revision = context.get("context_revision")
    if not isinstance(context_revision, str) or not context_revision.strip():
        raise ValueError("context_revision is required")
    context_revision = context_revision.strip()

    task_context = context.get("task_context")
    if not isinstance(task_context, dict):
        raise ValueError("task_context is required")
    task_payload = task_context.get("task")
    if not isinstance(task_payload, dict):
        raise ValueError("task_context.task is required")
    task_id = task_payload.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_context.task.id is required")

    stored_task = get_task(task_id)
    if stored_task is None:
        raise ValueError(f"task not found: {task_id}")

    expected_sequence = _derive_context_sequence(stored_task)
    expected_revision = _derive_context_revision(stored_task, expected_sequence)
    if context_revision != expected_revision:
        raise ValueError(
            f"context_revision mismatch: expected '{expected_revision}', received '{context_revision}'"
        )

    run_envelope = context.get("run_envelope")
    if not isinstance(run_envelope, dict):
        raise ValueError("run_envelope is required")
    sequence = run_envelope.get("sequence")
    if isinstance(sequence, int) and sequence != expected_sequence:
        raise ValueError(
            f"context_revision mismatch: expected sequence {expected_sequence}, received {sequence}"
        )

    return stored_task


def _validate_result_against_skill(skill: dict[str, Any], result: dict[str, Any]) -> None:
    persistence = skill.get("persistence")
    if not isinstance(persistence, dict):
        raise ValueError("skill.persistence is required")
    output_schema = persistence.get("output_schema")
    if not isinstance(output_schema, str) or not output_schema.strip():
        raise ValueError(f"skill '{skill.get('id', '<unknown>')}' must define persistence.output_schema")

    schema = load_output_schema(output_schema)
    errors = validate_output_payload(result, schema)
    if errors:
        raise ValueError("result payload failed schema validation: " + "; ".join(errors))


def _assert_run_id_unused(run_id: str) -> None:
    normalized_run_id = run_id.strip()
    if any(normalized_run_id in task.get("run_ids", []) for task in list_tasks()):
        raise ValueError(f"run_id already exists: {normalized_run_id}")
    if (env_store.ROOT / run_content_path(normalized_run_id)).exists():
        raise ValueError(f"run_id already exists: {normalized_run_id}")


def _track_object_path(track_id: str) -> str:
    return f"buddyswitch/objects/tracks/{track_id}.json"


def _task_object_path(task_id: str) -> str:
    return f"buddyswitch/objects/tasks/{task_id}.json"


def _artifact_object_path(artifact_id: str) -> str:
    return f"buddyswitch/objects/artifacts/{artifact_id}.json"


def _reserved_run_path(run_id: str) -> Path:
    return env_store.ROOT / "buddyswitch" / "content" / "runs" / "reserved" / f"{run_id}.json"


def _write_runtime_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=True, indent=2) + os.linesep
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(serialized)
        temp_name = handle.name
    os.replace(temp_name, path)


def _normalize_turn_identity(turn_identity: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(turn_identity, dict):
        raise ValueError("turn_identity payload is required")
    return {
        "instance_id": turn_identity.get("instance_id"),
        "active_buddy": turn_identity.get("active_buddy"),
        "request_text": turn_identity.get("request_text"),
        "task_id": turn_identity.get("task_id"),
        "track_id": turn_identity.get("track_id"),
        "context_revision": turn_identity.get("context_revision"),
        "sequence": turn_identity.get("sequence"),
        "run_id": turn_identity.get("run_id"),
    }


def _scan_task_recent_runs(task_id: str, *, limit: int = 3) -> list[dict[str, Any]]:
    run_root = env_store.ROOT / "buddyswitch" / "content" / "runs"
    if not run_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in run_root.glob("*.json"):
        if path.name == ".gitkeep":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        resolved_task_id = payload.get("resolved_task_id")
        if isinstance(resolved_task_id, str) and resolved_task_id:
            persisted_task_id = resolved_task_id
        else:
            persisted_task_id = payload.get("current_task_id")
            if not isinstance(persisted_task_id, str) or not persisted_task_id:
                continue
        if persisted_task_id != task_id:
            continue
        rows.append(
            {
                "run_id": payload.get("run_id", path.stem),
                "skill_id": payload.get("skill_id"),
                "execution_summary": payload.get("execution_summary"),
                "timestamp": payload.get("timestamp"),
            }
        )
    rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("run_id") or ""), reverse=True)
    return rows[:limit]


def _related_run_ids_for_task(task_id: str, current_run_id: str, *, limit: int = 2) -> list[str]:
    rows = _scan_task_recent_runs(task_id, limit=max(limit + 1, 3))
    related_run_ids: list[str] = []
    for row in rows:
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or not run_id or run_id == current_run_id:
            continue
        related_run_ids.append(run_id)
        if len(related_run_ids) >= limit:
            break
    return related_run_ids


def _build_task_context(task: dict[str, Any] | None) -> dict[str, Any]:
    if not task:
        return {
            "task": None,
            "artifacts": [],
            "recent_runs": [],
        }

    artifact_map = {artifact["id"]: artifact for artifact in list_artifacts()}
    artifacts = [artifact_map[item] for item in task.get("artifact_ids", []) if item in artifact_map]
    artifacts.sort(key=lambda row: (row.get("updated_at", ""), row["id"]), reverse=True)
    return {
        "task": {
            "id": task["id"],
            "buddy": task["buddy"],
            "status": task["status"],
            "summary": task.get("summary", ""),
            "track_id": task.get("track_id"),
            "latest_run_id": task.get("latest_run_id"),
            "artifact_slots": task.get("artifact_slots", {}),
        },
        "artifacts": artifacts[:5],
        "recent_runs": _scan_task_recent_runs(task["id"], limit=3),
    }


def _build_track_context(track_id: str | None) -> dict[str, Any] | None:
    if not track_id:
        return None
    track = get_track(track_id)
    if track is None:
        return None

    rows: list[dict[str, Any]] = []
    for task_id in track.get("task_ids", []):
        task = get_task(task_id)
        if task is None:
            continue
        current_artifacts: dict[str, dict[str, Any]] = {}
        artifact_slots = task.get("artifact_slots", {})
        if isinstance(artifact_slots, dict):
            for slot, row in artifact_slots.items():
                if not isinstance(row, dict):
                    continue
                artifact_id = row.get("current_artifact_id")
                if not isinstance(artifact_id, str) or not artifact_id:
                    continue
                artifact = get_artifact(artifact_id)
                if artifact is not None:
                    current_artifacts[slot] = artifact
        rows.append(
            {
                "task_id": task["id"],
                "buddy": task["buddy"],
                "status": task["status"],
                "summary": task.get("summary", ""),
                "current_artifacts": current_artifacts,
            }
        )

    return {
        "track": {
            "id": track["id"],
            "title": track["title"],
            "status": track["status"],
            "current_buddy": track["current_buddy"],
            "next_buddy": track.get("next_buddy"),
            "summary": track.get("summary", ""),
        },
        "tasks": rows,
    }


def _derive_context_revision(task: dict[str, Any], sequence: int) -> str:
    task_id = task.get("id") if isinstance(task, dict) else None
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("task.id is required to derive context_revision")
    if not isinstance(sequence, int) or sequence < 1:
        raise ValueError("sequence must be a positive integer")
    return f"ctx-{task_id}-turn-{sequence}"


def _build_turn_identity(
    *,
    instance_id: str | None,
    active_buddy: str,
    request_text: str,
    task_id: str,
    track_id: str | None,
    context_revision: str,
    sequence: int,
    run_id: str,
) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "active_buddy": active_buddy,
        "request_text": request_text,
        "task_id": task_id,
        "track_id": track_id,
        "context_revision": context_revision,
        "sequence": sequence,
        "run_id": run_id,
    }


def _current_product_instance_id() -> str | None:
    raw_instance_id = os.environ.get("BUDDYSWITCH_INSTANCE_ID")
    if isinstance(raw_instance_id, str) and raw_instance_id.strip():
        return raw_instance_id.strip()
    return None


def _find_active_task_reservation(task_id: str) -> dict[str, Any] | None:
    reserved_dir = _reserved_run_path("placeholder").parent
    if not reserved_dir.exists():
        return None
    for path in sorted(reserved_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"run reservation is invalid: {path.name}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"run reservation is invalid: {path.name}")
        if payload.get("status") != "reserved":
            continue
        if payload.get("task_id") == task_id:
            return payload
    return None


def _save_run_reservation(
    *,
    run_id: str,
    context_revision: str,
    sequence: int,
    task_id: str,
    turn_identity: dict[str, Any],
    instance_id: str | None,
) -> None:
    require_runtime_workspace_write_root()
    if instance_id is not None:
        existing = _find_active_task_reservation(task_id)
        if existing is not None:
            existing_run_id = existing.get("run_id")
            existing_instance_id = existing.get("instance_id")
            raise ValueError(
                f"Task '{task_id}' already has an active run reservation"
                f" '{existing_run_id}' for instance '{existing_instance_id or 'unknown'}'."
            )
    reservation = {
        "run_id": run_id,
        "status": "reserved",
        "context_revision": context_revision,
        "sequence": sequence,
        "task_id": task_id,
        "turn_identity": _normalize_turn_identity(turn_identity),
        "reserved_at": now_iso(),
    }
    if instance_id is not None:
        reservation["instance_id"] = instance_id
    _write_runtime_json(
        _reserved_run_path(run_id),
        reservation,
    )


def _load_run_reservation(run_id: str) -> dict[str, Any]:
    path = _reserved_run_path(run_id)
    if not path.exists():
        raise ValueError(f"run reservation not found: {run_id}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"run reservation is invalid: {run_id}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"run reservation is invalid: {run_id}")
    if payload.get("status") != "reserved":
        raise ValueError(f"run reservation is invalid: {run_id}")
    return payload


def _clear_run_reservation(run_id: str) -> dict[str, Any] | None:
    path = _reserved_run_path(run_id)
    try:
        if path.exists():
            path.unlink()
    except OSError as exc:
        return {
            "code": "W_RUN_RESERVATION_CLEAR_FAILED",
            "message": f"run reservation could not be cleared: {exc}",
            "run_id": run_id,
            "reservation_path": str(path),
        }
    return None


def _post_persist_refreshed_context_unavailable(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "E_RUNTIME_REFRESH_CONTEXT",
            "message": (
                "persist completed without reserving a follow-up run; "
                "rerun prepare with a new request_text to continue"
            ),
        },
    }


def _derive_context_sequence(task: dict[str, Any]) -> int:
    run_ids = task.get("run_ids")
    if isinstance(run_ids, list):
        return len(run_ids) + 1
    return 1


def _build_prepare_turn_context(text: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    request_text = text
    if not isinstance(request_text, str) or not request_text.strip():
        return runtime_error("E_EMPTY_INPUT", "Input is empty.")

    product_session = _load_product_mode_session(manifest_path)
    if product_session is None:
        return runtime_error(
            "E_PRODUCT_MODE_REQUIRED",
            "prepare-turn-context requires a launcher-managed buddy instance. Start a buddy instance and use an ordinary request.",
        )
    if _is_legacy_command_shaped_request(request_text):
        return runtime_error(
            "E_LEGACY_COMMAND_INPUT",
            "This buddy instance accepts ordinary requests in the current locked buddy. Remove command syntax and submit an ordinary request.",
        )

    active_buddy = product_session["active_buddy"]
    instance_id = product_session["instance_id"]
    demand = request_text.strip()
    payload = product_session.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    payload_task = payload_dict.get("current_task_id")
    payload_track = payload_dict.get("current_track_id")
    explicit_task_id = payload_task.strip() if isinstance(payload_task, str) and payload_task.strip() else None
    explicit_track_id = payload_track.strip() if isinstance(payload_track, str) and payload_track.strip() else None

    _ensure_no_legacy_outputs(demand)

    buddy = require_buddy(manifest, active_buddy)

    existing_task: dict[str, Any] | None = None
    if explicit_task_id:
        existing_task = get_task(explicit_task_id)
        if existing_task is None:
            if explicit_track_id and get_track(explicit_track_id) is None:
                create_track(
                    explicit_track_id,
                    explicit_track_id.replace("-", " ").title(),
                    status="active",
                    current_buddy=active_buddy,
                    next_buddy=None,
                    summary="",
                )
            existing_task = create_task(
                explicit_task_id,
                _derive_task_title(demand),
                buddy=active_buddy,
                track_id=explicit_track_id,
                status="active",
                summary="",
                initial_run_id=None,
            )
        if existing_task["buddy"] != active_buddy:
            raise ValueError(
                f"Task '{explicit_task_id}' belongs to buddy '{existing_task['buddy']}', not '{active_buddy}'."
            )

    if explicit_track_id and get_track(explicit_track_id) is None:
        create_track(
            explicit_track_id,
            explicit_track_id.replace("-", " ").title(),
            status="active",
            current_buddy=active_buddy,
            next_buddy=None,
            summary="",
        )

    if existing_task and explicit_track_id and existing_task.get("track_id") not in {None, explicit_track_id}:
        raise ValueError(
            f"Task '{existing_task['id']}' is bound to track '{existing_task['track_id']}', cannot switch to '{explicit_track_id}'."
        )

    buddy_skill_ids = [row for row in buddy.get("skills", []) if isinstance(row, str)]
    if not buddy_skill_ids:
        raise ValueError(f"Buddy '{active_buddy}' currently has no registered skills.")

    effective_track_id = explicit_track_id or (existing_task.get("track_id") if existing_task else None)
    if existing_task:
        resolved_task = existing_task
        task_context = _build_task_context(existing_task)
    else:
        create_token = _derive_create_token(demand)
        task_id = _derive_task_id(
            active_buddy,
            demand,
            create_token=create_token,
        )
        preexisting_task = get_task(task_id)
        if preexisting_task is None:
            resolved_task = create_task(
                task_id,
                _derive_task_title(demand),
                buddy=active_buddy,
                track_id=effective_track_id,
                status="active",
                summary="",
                initial_run_id=None,
            )
        else:
            if preexisting_task["buddy"] != active_buddy:
                raise ValueError(
                    f"Task '{task_id}' belongs to buddy '{preexisting_task['buddy']}', not '{active_buddy}'."
                )
            if effective_track_id and preexisting_task.get("track_id") not in {None, effective_track_id}:
                raise ValueError(
                    f"Task '{task_id}' is bound to track '{preexisting_task.get('track_id')}', cannot switch to '{effective_track_id}'."
                )
            resolved_task = preexisting_task
            if effective_track_id and resolved_task.get("track_id") is None:
                resolved_task = register_task_to_track(effective_track_id, task_id)
        if effective_track_id is None:
            effective_track_id = resolved_task.get("track_id")
        task_context = _build_task_context(resolved_task)

    track_context = _build_track_context(effective_track_id)
    track_artifact_index = build_track_artifact_index(effective_track_id)

    sequence = _derive_context_sequence(resolved_task)
    context_revision = _derive_context_revision(resolved_task, sequence)
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    turn_identity = _build_turn_identity(
        instance_id=instance_id,
        active_buddy=active_buddy,
        request_text=request_text,
        task_id=resolved_task["id"],
        track_id=effective_track_id,
        context_revision=context_revision,
        sequence=sequence,
        run_id=run_id,
    )
    _save_run_reservation(
        run_id=run_id,
        context_revision=context_revision,
        sequence=sequence,
        task_id=resolved_task["id"],
        turn_identity=turn_identity,
        instance_id=instance_id,
    )

    current_task_id = resolved_task["id"]
    current_track_id = effective_track_id

    return {
        "ok": True,
        "context_revision": context_revision,
        "instance_id": instance_id,
        "active_buddy": buddy["id"],
        "request_text": request_text,
        "current_task_id": current_task_id,
        "current_track_id": current_track_id,
        "task_context": task_context,
        "track_context": track_context,
        "track_artifact_index": track_artifact_index,
        "run_envelope": {
            "run_id": run_id,
            "status": "reserved",
            "sequence": sequence,
            "turn_identity": turn_identity,
        },
        "warnings": [],
    }


def prepare_turn_context(text: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return _build_prepare_turn_context(text, manifest_path=manifest_path)


def _read_json_input(source: str, *, stdin_text: str | None = None) -> dict[str, Any]:
    if source == "-":
        if stdin_text is None:
            raise ValueError("stdin payload was requested but no stdin text was supplied")
        raw = stdin_text
    else:
        raw = Path(source).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("JSON payload must be an object")
    return payload


def _strip_run_fields(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_summary": result.get("execution_summary"),
        "working_notes": result.get("working_notes") or [],
        "deliverables_or_changed_files": result.get("deliverables_or_changed_files") or [],
    }


def _receipt_paths(
    *,
    run_content_path_value: str,
    task_id: str,
    artifact_ids: list[str],
    track_id: str | None,
) -> dict[str, Any]:
    paths: dict[str, Any] = {"run": run_content_path_value, "task": _task_object_path(task_id)}
    if artifact_ids:
        paths["artifacts"] = [_artifact_object_path(item) for item in artifact_ids]
    if track_id:
        paths["track"] = _track_object_path(track_id)
    return paths


def _build_run_audit(
    *,
    resolved: dict[str, Any],
    task_id: str,
    effective_track_id: str | None,
    skill_id: str,
    run_id: str,
    artifact_ids: list[str],
    track_action: str | None,
    paths: dict[str, Any],
    writes: list[str],
    result: dict[str, Any],
    task_title: str,
    track_title: str | None,
    related_run_ids: list[str],
    next_state: dict[str, Any],
) -> dict[str, Any]:
    audit = {
        "run_id": run_id,
        "timestamp": now_iso(),
        "request_text": resolved.get("request_text"),
        "active_buddy": resolved.get("active_buddy"),
        "current_task_id": resolved.get("current_task_id"),
        "current_track_id": resolved.get("current_track_id"),
        "resolved_task_id": task_id,
        "effective_track_id": effective_track_id,
        "skill_id": skill_id,
        "artifact_ids": artifact_ids,
        "track_action": track_action,
        "task_title": task_title,
        "track_title": track_title,
        "next_state": next_state,
        "receipt_paths": paths,
        "related_run_ids": related_run_ids,
        "paths": paths,
        "writes": writes,
    }
    audit.update(_strip_run_fields(result))
    return audit


def _ensure_task_binding(
    *,
    task: dict[str, Any],
    explicit_track_id: str | None,
) -> tuple[dict[str, Any], str | None, list[str]]:
    writes: list[str] = [_task_object_path(task["id"])]
    if not explicit_track_id:
        return task, task.get("track_id"), writes

    _validate_task_binding(task=task, explicit_track_id=explicit_track_id)
    if task.get("track_id") == explicit_track_id:
        return task, explicit_track_id, writes

    updated_task = register_task_to_track(explicit_track_id, task["id"])
    writes = [_task_object_path(updated_task["id"]), _track_object_path(explicit_track_id)]
    return updated_task, explicit_track_id, writes


def _validate_task_binding(
    *,
    task: dict[str, Any],
    explicit_track_id: str | None,
) -> None:
    if not explicit_track_id:
        return
    if task.get("track_id") not in {None, explicit_track_id}:
        raise ValueError(
            f"Task '{task['id']}' is bound to track '{task['track_id']}', cannot switch to '{explicit_track_id}'."
        )


def _track_operation_from_result(result: dict[str, Any]) -> dict[str, Any] | None:
    if "track_operation" in result:
        raise ValueError("top-level track_operation is retired; use state_effects.track_operation")
    state_effects = result.get("state_effects")
    if state_effects is None:
        return None
    if not isinstance(state_effects, dict):
        raise ValueError("state_effects must be an object")
    track_operation = state_effects.get("track_operation")
    if track_operation is None:
        return None
    if not isinstance(track_operation, dict):
        raise ValueError("state_effects.track_operation must be an object")
    return dict(track_operation)


def _validate_track_operation_effect(
    *,
    operation: dict[str, Any] | None,
    active_buddy: str,
    task: dict[str, Any],
    explicit_track_id: str | None,
) -> dict[str, Any] | None:
    if operation is None:
        return None
    if active_buddy != "pm":
        raise ValueError("state_effects.track_operation is only allowed for buddy 'pm'")

    action = str(operation.get("action") or "").lower()
    if action not in TRACK_ACTIONS:
        raise ValueError("state_effects.track_operation.action must be one of create/update/advance/archive")

    normalized: dict[str, Any] = {"action": action}
    for key in ("track_id", "title", "status", "current_buddy", "next_buddy", "summary"):
        if key in operation:
            normalized[key] = operation.get(key)

    op_track_id = normalized.get("track_id")
    if isinstance(op_track_id, str) and op_track_id.strip():
        op_track_id = op_track_id.strip()
        normalized["track_id"] = op_track_id
    elif op_track_id is None:
        normalized.pop("track_id", None)

    if explicit_track_id and isinstance(op_track_id, str) and op_track_id != explicit_track_id:
        raise ValueError(
            "state_effects.track_operation.track_id must match current_track_id when current_track_id is set"
        )

    target_track_id = op_track_id or explicit_track_id or task.get("track_id")
    status = normalized.get("status")
    if status is not None and status not in STATUS_VALUES:
        raise ValueError(f"state_effects.track_operation.status must be one of {', '.join(STATUS_VALUES)}")

    if action != "create":
        if not isinstance(target_track_id, str) or not target_track_id:
            raise ValueError("state_effects.track_operation requires track_id for non-create actions")
        if get_track(target_track_id) is None:
            raise ValueError(f"Track not found: {target_track_id}")
        if action in {"update", "advance"}:
            patch: dict[str, Any] = {}
            for key in ("title", "status", "current_buddy", "next_buddy", "summary"):
                if key in normalized and normalized.get(key) is not None:
                    patch[key] = normalized.get(key)
            if not patch:
                raise ValueError("state_effects.track_operation for update/advance must include at least one mutable field")
    return normalized


def _apply_track_operation_effect(
    *,
    operation: dict[str, Any] | None,
    active_buddy: str,
    request_text: str,
    task: dict[str, Any],
    effective_track_id: str | None,
) -> tuple[dict[str, Any], str | None, str | None, str | None, str | None, list[str]]:
    if operation is None:
        return task, effective_track_id, None, None, None, []

    action = str(operation.get("action") or "").lower()
    if action == "create":
        new_id = operation.get("track_id") or _derive_track_id(request_text)
        title = operation.get("title") or str(new_id).replace("-", " ").title()
        status = operation.get("status") or "active"
        track = create_track(
            str(new_id),
            str(title),
            status=str(status),
            current_buddy=operation.get("current_buddy") or active_buddy,
            next_buddy=operation.get("next_buddy"),
            summary=operation.get("summary") or "",
        )
        updated_task = register_task_to_track(track["id"], task["id"])
        writes = [_task_object_path(updated_task["id"]), _track_object_path(track["id"])]
        return updated_task, track["id"], track["title"], track.get("next_buddy"), action, writes

    target_track_id = operation.get("track_id") or effective_track_id
    if not isinstance(target_track_id, str) or not target_track_id:
        raise ValueError("state_effects.track_operation requires track_id for non-create actions")

    if action in {"update", "advance"}:
        patch: dict[str, Any] = {}
        for key in ("title", "status", "current_buddy", "next_buddy", "summary"):
            if key in operation and operation.get(key) is not None:
                patch[key] = operation.get(key)
        track = update_track(target_track_id, patch)
    elif action == "archive":
        track = update_track(target_track_id, {"status": "archived"})
    else:
        raise ValueError("state_effects.track_operation.action must be one of create/update/advance/archive")

    updated_task = register_task_to_track(track["id"], task["id"])
    writes = [_task_object_path(updated_task["id"]), _track_object_path(track["id"])]
    return updated_task, track["id"], track["title"], track.get("next_buddy"), action, writes


def _persist_artifact_skill(
    *,
    resolved: dict[str, Any],
    skill: dict[str, Any],
    result: dict[str, Any],
    run_id: str,
    task: dict[str, Any],
    explicit_track_id: str | None,
    track_operation: dict[str, Any] | None,
) -> dict[str, Any]:
    active_buddy = resolved.get("active_buddy")
    if not isinstance(active_buddy, str) or not active_buddy.strip():
        raise ValueError("active_buddy is required")
    active_buddy = active_buddy.strip()
    request_text = resolved.get("request_text")
    if not isinstance(request_text, str) or not request_text.strip():
        raise ValueError("request_text is required")
    skill_id = skill["id"]
    persistence = skill.get("persistence")
    if not isinstance(persistence, dict):
        raise ValueError(f"skill '{skill_id}' must define persistence")
    output_slot = persistence.get("output_slot")
    if not isinstance(output_slot, str) or not output_slot:
        raise ValueError(f"skill '{skill_id}' must define a non-empty output_slot")
    output_slot = output_slot.strip()
    if not output_slot:
        raise ValueError(f"skill '{skill_id}' must define a non-empty output_slot")

    _validate_task_binding(task=task, explicit_track_id=explicit_track_id)
    effective_track_id = explicit_track_id or task.get("track_id")
    task_after_effect, effective_track_id, track_title, next_buddy, track_action, effect_writes = _apply_track_operation_effect(
        operation=track_operation,
        active_buddy=active_buddy,
        request_text=request_text,
        task=task,
        effective_track_id=effective_track_id,
    )
    task, effective_track_id, binding_writes = _ensure_task_binding(
        task=task_after_effect,
        explicit_track_id=effective_track_id,
    )

    artifact_id = _derive_artifact_id(task["id"], output_slot)
    artifact_summary = str(result.get("execution_summary") or "")
    artifact = create_artifact(
        artifact_id=artifact_id,
        title=_derive_artifact_title(active_buddy, skill_id, request_text),
        buddy=active_buddy,
        skill_id=skill_id,
        slot=output_slot,
        task_id=task["id"],
        source_run_id=run_id,
        summary=artifact_summary,
        content=result["artifact_content"],
        auto_register=True,
    )
    add_run_to_task(task["id"], run_id, summary=artifact_summary)

    run_content_path_value = run_content_path(run_id)
    artifact_ids = [artifact["id"]]
    related_run_ids = _related_run_ids_for_task(task["id"], run_id, limit=2)
    if effective_track_id:
        track = get_track(effective_track_id)
        if track:
            if track_title is None:
                track_title = track["title"]
            if next_buddy is None:
                next_buddy = track.get("next_buddy")
    receipt_paths = _receipt_paths(
        run_content_path_value=run_content_path_value,
        task_id=task["id"],
        artifact_ids=artifact_ids,
        track_id=effective_track_id,
    )
    next_state = _build_next_state(
        task_id=task["id"],
        track_id=effective_track_id,
        current_buddy=active_buddy,
        next_buddy=next_buddy,
        track_action=track_action,
    )
    writes = list(effect_writes) + list(binding_writes)
    writes.extend([_task_object_path(task["id"]), _artifact_object_path(artifact["id"]), run_content_path_value])
    if effective_track_id:
        writes.append(_track_object_path(effective_track_id))
    writes = list(dict.fromkeys(writes))
    save_run_content(
        run_id,
        _build_run_audit(
            resolved=resolved,
            task_id=task["id"],
            effective_track_id=effective_track_id,
            skill_id=skill_id,
            run_id=run_id,
            artifact_ids=artifact_ids,
            track_action=track_action,
            paths=receipt_paths,
            writes=writes,
            result=result,
            task_title=task["title"],
            track_title=track_title,
            related_run_ids=related_run_ids,
            next_state=next_state,
        ),
    )
    receipt = {
        "ok": True,
        "skill_id": skill_id,
        "task_id": task["id"],
        "artifact_id": artifact["id"],
        "artifact_ids": artifact_ids,
        "track_id": effective_track_id,
        "task_title": task["title"],
        "track_title": track_title,
        "next_state": next_state,
        "receipt_paths": receipt_paths,
        "related_run_ids": related_run_ids,
        "run_id": run_id,
        "paths": receipt_paths,
        "writes": writes,
    }
    if track_action is not None:
        receipt["track_action"] = track_action
    return receipt


def _persist_skill_result(
    context: dict[str, Any],
    *,
    skill_id: str,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    if not context.get("ok"):
        raise ValueError("context payload must be successful before persist_skill_result")
    if not isinstance(skill_id, str) or not skill_id.strip():
        raise ValueError("persist requires a single skill_id string")
    selected_skill_id = skill_id.strip()
    if not isinstance(result, dict):
        raise ValueError("result payload must be a JSON object")

    stored_task = _validate_context_revision(context)
    active_buddy = context.get("active_buddy")
    if not isinstance(active_buddy, str) or not active_buddy.strip():
        raise ValueError("active_buddy is required")
    active_buddy = active_buddy.strip()
    request_text = context.get("request_text")
    if not isinstance(request_text, str) or not request_text.strip():
        raise ValueError("request_text is required")
    current_task_id = context.get("current_task_id")
    if not isinstance(current_task_id, str) or not current_task_id.strip():
        raise ValueError("current_task_id is required")
    current_task_id = current_task_id.strip()
    if current_task_id != stored_task["id"]:
        raise ValueError(f"current_task_id mismatch: expected '{stored_task['id']}', received '{current_task_id}'")
    raw_current_track_id = context.get("current_track_id")
    current_track_id = raw_current_track_id.strip() if isinstance(raw_current_track_id, str) and raw_current_track_id.strip() else None

    manifest = load_manifest(manifest_path)
    buddy = require_buddy(manifest, active_buddy)
    allowed_skill_ids = {row for row in buddy.get("skills", []) if isinstance(row, str)}
    if selected_skill_id not in allowed_skill_ids:
        raise ValueError(f"selected skill_id '{selected_skill_id}' is not allowed for buddy '{active_buddy}'")

    run_envelope = context.get("run_envelope")
    if not isinstance(run_envelope, dict):
        raise ValueError("run_envelope is required")
    context_turn_identity = run_envelope.get("turn_identity")
    if not isinstance(context_turn_identity, dict):
        raise ValueError("run_envelope.turn_identity is required")
    if context_turn_identity.get("active_buddy") != active_buddy:
        raise ValueError("run_envelope.turn_identity active_buddy mismatch")
    if context_turn_identity.get("request_text") != request_text:
        raise ValueError("run_envelope.turn_identity request_text mismatch")
    if context_turn_identity.get("task_id") != current_task_id:
        raise ValueError("run_envelope.turn_identity task_id mismatch")
    if context_turn_identity.get("track_id") != current_track_id:
        raise ValueError("run_envelope.turn_identity track_id mismatch")
    reserved_run_id = run_envelope.get("run_id")
    if not isinstance(reserved_run_id, str) or not reserved_run_id.strip():
        raise ValueError("run_envelope.run_id is required")
    run_id = reserved_run_id.strip()
    _assert_run_id_unused(run_id)
    reservation = _load_run_reservation(run_id)
    reserved_context_revision = reservation.get("context_revision")
    if reserved_context_revision != context.get("context_revision"):
        raise ValueError("run reservation mismatch: context_revision differs from reserved envelope")
    reserved_task_id = reservation.get("task_id")
    if reserved_task_id != stored_task["id"]:
        raise ValueError("run reservation mismatch: task_id differs from reserved envelope")
    reserved_sequence = reservation.get("sequence")
    if reserved_sequence != run_envelope.get("sequence"):
        raise ValueError("run reservation mismatch: sequence differs from reserved envelope")
    reservation_turn_identity = reservation.get("turn_identity")
    if not isinstance(reservation_turn_identity, dict) or not isinstance(context_turn_identity, dict):
        raise ValueError("run reservation mismatch: turn_identity payload is missing")
    if _normalize_turn_identity(reservation_turn_identity) != _normalize_turn_identity(context_turn_identity):
        raise ValueError("run reservation mismatch: turn_identity differs from reserved envelope")

    selected_skill = _resolve_execution_skill(
        buddy_id=active_buddy,
        skill_id=selected_skill_id,
        manifest_path=manifest_path,
    )
    _validate_result_against_skill(selected_skill, result)
    track_operation = _validate_track_operation_effect(
        operation=_track_operation_from_result(result),
        active_buddy=active_buddy,
        task=stored_task,
        explicit_track_id=current_track_id,
    )
    persist_context = {
        "active_buddy": active_buddy,
        "request_text": request_text,
        "current_task_id": current_task_id,
        "current_track_id": current_track_id,
    }

    try:
        receipt = _persist_artifact_skill(
            resolved=persist_context,
            skill=selected_skill,
            result=result,
            run_id=run_id,
            task=stored_task,
            explicit_track_id=current_track_id,
            track_operation=track_operation,
        )
    except (ValueError, OSError):
        raise

    reservation_clear_warning = _clear_run_reservation(run_id)
    if reservation_clear_warning is not None:
        receipt_warnings = receipt.setdefault("warnings", []) if isinstance(receipt, dict) else []
        if isinstance(receipt_warnings, list):
            receipt_warnings.append(reservation_clear_warning)
    refreshed_context = _post_persist_refreshed_context_unavailable(receipt)

    return {
        "ok": True,
        "receipt": receipt,
        "refreshed_context": refreshed_context,
    }


def persist_skill_result(
    context: dict[str, Any],
    *,
    skill_id: str,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    return _persist_skill_result(
        context,
        skill_id=skill_id,
        result=result,
        manifest_path=manifest_path,
    )


def _cmd_prepare(args: argparse.Namespace) -> int:
    try:
        product_session = _load_product_mode_session(args.manifest)
        if product_session is None:
            payload = prepare_turn_context(args.text, manifest_path=args.manifest)
        else:
            with _hold_product_runtime_lock(product_session):
                product_session = _load_product_mode_session(args.manifest)
                if product_session is None:
                    raise ValueError("product-mode env disappeared while acquiring runtime lock")
                payload = prepare_turn_context(args.text, manifest_path=args.manifest)
                if payload.get("ok"):
                    task_id, track_id = _resolve_binding_from_payload(payload)
                    try:
                        _write_product_session_binding(product_session, task_id=task_id, track_id=track_id)
                    except (OSError, ValueError) as exc:
                        _clear_reservation_from_payload(payload, fail_on_warning=True)
                        raise ValueError(f"instance binding update failed after prepare: {exc}") from exc
    except (ManifestError, ValueError, OutputSchemaError, OSError) as exc:
        payload = runtime_error("E_RUNTIME_PREPARE", str(exc))
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


def _derive_cli_persist_skill_id(
    context: dict[str, Any],
    requested_skill_id: str | None,
) -> str:
    _ = context
    if isinstance(requested_skill_id, str) and requested_skill_id.strip():
        return requested_skill_id.strip()
    raise ValueError("skill_id is required")


def _validate_product_persist_context_binding(context: dict[str, Any], product_session: dict[str, Any]) -> None:
    if not context.get("ok"):
        return

    session_instance_id = product_session.get("instance_id")
    if not isinstance(session_instance_id, str) or not session_instance_id.strip():
        raise ValueError("product-mode session instance_id is required")
    session_instance_id = session_instance_id.strip()

    session_buddy = product_session.get("active_buddy")
    if not isinstance(session_buddy, str) or not session_buddy.strip():
        raise ValueError("product-mode session active_buddy is required")
    session_buddy = session_buddy.strip()

    context_instance_id = context.get("instance_id")
    if context_instance_id != session_instance_id:
        raise ValueError(
            "product-mode context instance mismatch: "
            f"expected '{session_instance_id}', received '{context_instance_id}'"
        )

    context_buddy = context.get("active_buddy")
    if context_buddy != session_buddy:
        raise ValueError(
            "product-mode context buddy mismatch: "
            f"expected '{session_buddy}', received '{context_buddy}'"
        )

    run_envelope = context.get("run_envelope")
    turn_identity = run_envelope.get("turn_identity") if isinstance(run_envelope, dict) else None
    if not isinstance(turn_identity, dict):
        raise ValueError("product-mode context turn_identity is required")
    if turn_identity.get("instance_id") != session_instance_id:
        raise ValueError(
            "product-mode turn_identity instance mismatch: "
            f"expected '{session_instance_id}', received '{turn_identity.get('instance_id')}'"
        )
    if turn_identity.get("active_buddy") != session_buddy:
        raise ValueError(
            "product-mode turn_identity buddy mismatch: "
            f"expected '{session_buddy}', received '{turn_identity.get('active_buddy')}'"
        )


def _cmd_persist(args: argparse.Namespace) -> int:
    try:
        if args.context == "-" and args.result == "-":
            raise ValueError("context and result cannot both read from stdin")
        stdin_text = sys.stdin.read() if args.context == "-" or args.result == "-" else None
        context = _read_json_input(args.context, stdin_text=stdin_text if args.context == "-" else None)
        result = _read_json_input(args.result, stdin_text=stdin_text if args.result == "-" else None)
        product_session = _load_product_mode_session(args.manifest)
        if product_session is None:
            payload = persist_skill_result(
                context,
                skill_id=_derive_cli_persist_skill_id(context, args.skill_id),
                result=result,
                manifest_path=args.manifest,
            )
        else:
            with _hold_product_runtime_lock(product_session):
                product_session = _load_product_mode_session(args.manifest)
                if product_session is None:
                    raise ValueError("product-mode env disappeared while acquiring runtime lock")
                _validate_product_persist_context_binding(context, product_session)
                payload = persist_skill_result(
                    context,
                    skill_id=_derive_cli_persist_skill_id(context, args.skill_id),
                    result=result,
                    manifest_path=args.manifest,
                )
                if payload.get("ok"):
                    binding = _persist_binding_from_payload(payload)
                    if binding is not None:
                        task_id, track_id = binding
                        try:
                            _write_product_session_binding(product_session, task_id=task_id, track_id=track_id)
                        except (OSError, ValueError) as exc:
                            _mark_committed_binding_update_failed(payload, product_session, exc)
    except (ManifestError, ValueError, OSError, OutputSchemaError, json.JSONDecodeError) as exc:
        payload = runtime_error("E_RUNTIME_PERSIST", str(exc))
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BuddySwitch runtime.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_cmd = subparsers.add_parser("prepare", help="Prepare a BuddySwitch turn context from request text.")
    prepare_cmd.add_argument("text", help="ordinary request text")
    prepare_cmd.set_defaults(func=_cmd_prepare)

    persist_cmd = subparsers.add_parser("persist", help="Persist a structured BuddySwitch run result.")
    persist_cmd.add_argument("--context", required=True, help="Prepared turn context JSON file, or '-' for stdin")
    persist_cmd.add_argument("--result", required=True, help="Structured result JSON file, or '-' for stdin")
    persist_cmd.add_argument(
        "--skill-id",
        help="Chosen skill id. Required.",
    )
    persist_cmd.set_defaults(func=_cmd_persist)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
