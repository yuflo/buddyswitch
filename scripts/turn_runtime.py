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
import env_profiles
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
from runtime_kernel.client import RuntimeBrokerError, request_runtime_broker
ROOT = env_store.ROOT
REPO_ROOT = Path(__file__).resolve().parents[1]


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
_RUNTIME_RAW_STATE_PATHS = (
    "buddyswitch/objects/tracks/*.json",
    "buddyswitch/objects/tasks/*.json",
    "buddyswitch/objects/artifacts/*.json",
    "buddyswitch/content/runs/*.json",
)
_CANONICAL_PREPARE_COMMAND = 'python3 scripts/turn_runtime.py prepare "<request>"'
_CANONICAL_PERSIST_COMMAND = "python3 scripts/turn_runtime.py persist --context <context> --result <result>"
_ARTIFACT_KIND_DESC: dict[str, dict[str, str]] = {
    "market-scan": {
        "label": "Market scan",
        "use_when": "Market summarizes demand, competition, audience, and positioning evidence for downstream product decisions.",
    },
    "pmf-report": {
        "label": "PMF report",
        "use_when": "Market evaluates product-market-fit signals, ICP hypotheses, confidence, and interview angles.",
    },
    "customer-discovery": {
        "label": "Customer discovery",
        "use_when": "Market prepares or summarizes customer interview hypotheses, guides, and learning points.",
    },
    "positioning-brief": {
        "label": "Positioning brief",
        "use_when": "Market defines message house, homepage angles, competitive contrast, and copy direction.",
    },
    "channel-plan": {
        "label": "Channel plan",
        "use_when": "Market proposes acquisition channels, experiment plans, and channel scoring.",
    },
    "launch-prep": {
        "label": "Launch prep",
        "use_when": "Market prepares launch assets, instrumentation, feedback collection, and release readiness notes.",
    },
    "prd": {
        "label": "PRD",
        "use_when": "PM defines product requirements, scope, decisions, acceptance criteria, and implementation-ready constraints.",
    },
    "pm-decision": {
        "label": "PM decision",
        "use_when": "PM records a product decision, tradeoff, or scope clarification that downstream buddies should follow.",
    },
    "track-note": {
        "label": "Track note",
        "use_when": "PM records cross-buddy track status, next buddy direction, blockers, or lifecycle rationale.",
    },
    "design-handoff": {
        "label": "Design handoff",
        "use_when": "Design provides interaction decisions, visual direction, handoff notes, and implementation constraints.",
    },
    "prototype-brief": {
        "label": "Prototype brief",
        "use_when": "Design captures prototype goals, flows, interaction states, preview references, and open UX questions.",
    },
    "implementation-report": {
        "label": "Implementation report",
        "use_when": "Dev reports changed files, implementation notes, verification evidence, risks, and follow-up work.",
    },
    "skill-import-report": {
        "label": "Skill import report",
        "use_when": "Dev reports skill import or conversion work, changed skill files, validation, and remaining risks.",
    },
    "smoke-test": {
        "label": "Smoke test",
        "use_when": "Test records focused smoke checks, pass/fail/blocked results, reproduction notes, and readiness.",
    },
    "test-report": {
        "label": "Test report",
        "use_when": "Test records broader regression scope, commands, evidence, failures, and release readiness judgment.",
    },
}


class RuntimeFeedbackError(ValueError):
    """Structured runtime feedback for buddy-facing validation failures."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _raise_runtime_feedback(code: str, message: str, **details: Any) -> None:
    raise RuntimeFeedbackError(code, message, details=details)


def _runtime_command_hints() -> dict[str, str]:
    return {
        "prepare": _CANONICAL_PREPARE_COMMAND,
        "persist": _CANONICAL_PERSIST_COMMAND,
    }


def _context_save_path(active_buddy: str, run_id: str) -> str:
    normalized_buddy = active_buddy.strip()
    normalized_run_id = run_id.strip()
    if not normalized_buddy:
        raise ValueError("active_buddy is required to derive context_save_path")
    if not normalized_run_id:
        raise ValueError("run_id is required to derive context_save_path")
    return f"runs/raw/{normalized_buddy}/prepare-context-{normalized_run_id}.json"


def _persist_command_hint_for_context(context_save_path: str, active_buddy: str) -> str:
    normalized_context_path = context_save_path.strip()
    normalized_buddy = active_buddy.strip()
    if not normalized_context_path:
        raise ValueError("context_save_path is required to derive persist command hint")
    if not normalized_buddy:
        raise ValueError("active_buddy is required to derive persist command hint")
    return (
        "python3 scripts/turn_runtime.py persist "
        f"--context {normalized_context_path} "
        f"--result runs/raw/{normalized_buddy}/persist-result.json"
    )


def _rerun_prepare_actions() -> list[str]:
    commands = _runtime_command_hints()
    return [
        commands["prepare"],
        commands["persist"],
        "Use the refreshed context from prepare for the next persist attempt.",
        "Do not write raw BuddySwitch state directly.",
    ]


def _market_evidence_command_hint() -> str:
    return (
        "python3 scripts/browser_evidence.py issue --context <prepare-context.json> "
        "--mode browser-cockpit-preflight"
    )


def _market_evidence_feedback() -> dict[str, Any]:
    return {
        "permission_boundary": "market.browser_evidence",
        "allowed_next_actions": [
            "Issue broker-backed browser evidence for the current prepared run.",
            "Include the returned token in tool_evidence on the next artifact-producing persist.",
            "Use an approved downgrade token only when the user explicitly approves the fallback.",
        ],
        "command_hint": _market_evidence_command_hint(),
        "persist_payload_hint": {
            "tool_evidence": {
                "accepted_fields": ["browser_cockpit_token", "approved_downgrade_token"],
            }
        },
    }


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
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            f"task not found: {task_id}",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=_rerun_prepare_actions(),
        )

    expected_sequence = _derive_context_sequence(stored_task)
    expected_revision = _derive_context_revision(stored_task, expected_sequence)
    if context_revision != expected_revision:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            f"context_revision mismatch: expected '{expected_revision}', received '{context_revision}'",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=_rerun_prepare_actions(),
        )

    run_envelope = context.get("run_envelope")
    if not isinstance(run_envelope, dict):
        raise ValueError("run_envelope is required")
    sequence = run_envelope.get("sequence")
    if isinstance(sequence, int) and sequence != expected_sequence:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            f"context_revision mismatch: expected sequence {expected_sequence}, received {sequence}",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=_rerun_prepare_actions(),
        )

    return stored_task


def _assert_run_id_unused(run_id: str) -> None:
    normalized_run_id = run_id.strip()
    if any(normalized_run_id in task.get("run_ids", []) for task in list_tasks()):
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            f"run_id already committed: {normalized_run_id}",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=_rerun_prepare_actions(),
        )
    if (env_store.STATE_ROOT / run_content_path(normalized_run_id)).exists():
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            f"run_id already committed: {normalized_run_id}",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=_rerun_prepare_actions(),
        )


def _track_object_path(track_id: str) -> str:
    return f"buddyswitch/objects/tracks/{track_id}.json"


def _task_object_path(task_id: str) -> str:
    return f"buddyswitch/objects/tasks/{task_id}.json"


def _artifact_object_path(artifact_id: str) -> str:
    return f"buddyswitch/objects/artifacts/{artifact_id}.json"


def _reserved_run_path(run_id: str) -> Path:
    return env_store.CONTENT_ROOT / "runs" / "reserved" / f"{run_id}.json"


def _write_runtime_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=True, indent=2) + os.linesep
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(serialized)
        temp_name = handle.name
    os.replace(temp_name, path)


def _runtime_evidence_token_root() -> Path | None:
    raw_instance_json = os.environ.get("BUDDYSWITCH_INSTANCE_JSON")
    if not isinstance(raw_instance_json, str) or not raw_instance_json.strip():
        return None
    instance_json = Path(raw_instance_json.strip())
    if not instance_json.exists():
        return None
    return instance_json.parent / "runtime" / "evidence-tokens"


def _load_evidence_token_record(*, token: str, run_id: str) -> dict[str, Any] | None:
    root = _runtime_evidence_token_root()
    if root is None:
        return None
    token_path = root / run_id / f"{token}.json"
    if not token_path.exists():
        return None
    payload = json.loads(token_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid evidence token record: {token_path}")
    return payload


def _validate_market_tool_evidence(
    *,
    context: dict[str, Any],
    result: dict[str, Any],
    env_profile: dict[str, Any],
    active_buddy: str,
) -> dict[str, Any] | None:
    tool_capability = env_profile.get("tool_capability")
    if not isinstance(tool_capability, dict):
        raise ValueError("env profile tool_capability must be an object")
    evidence_required = tool_capability.get("market_research_evidence") == "required"
    if not evidence_required:
        return None

    # Evidence gate is enforced in runtime broker-backed product mode.
    if _runtime_evidence_token_root() is None:
        return None

    artifacts = result.get("artifacts")
    has_artifacts = isinstance(artifacts, list) and len(artifacts) > 0
    if not has_artifacts:
        return None

    tool_evidence = result.get("tool_evidence")
    if not isinstance(tool_evidence, dict):
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "Market persist requires tool_evidence with broker-issued token",
            **_market_evidence_feedback(),
        )

    browser_token = tool_evidence.get("browser_cockpit_token")
    downgrade_token = tool_evidence.get("approved_downgrade_token")
    browser_value = browser_token.strip() if isinstance(browser_token, str) and browser_token.strip() else None
    downgrade_value = downgrade_token.strip() if isinstance(downgrade_token, str) and downgrade_token.strip() else None
    if bool(browser_value) == bool(downgrade_value):
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "Market tool_evidence must include exactly one broker-issued token",
            **_market_evidence_feedback(),
        )

    run_envelope = context.get("run_envelope")
    if not isinstance(run_envelope, dict):
        raise ValueError("run_envelope is required for market evidence validation")
    run_id = run_envelope.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_envelope.run_id is required for market evidence validation")
    run_id = run_id.strip()
    context_revision = context.get("context_revision")
    if not isinstance(context_revision, str) or not context_revision.strip():
        raise ValueError("context_revision is required for market evidence validation")
    context_revision = context_revision.strip()
    instance_id = context.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError("instance_id is required for market evidence validation")
    instance_id = instance_id.strip()

    token_value = browser_value or downgrade_value or ""
    record = _load_evidence_token_record(token=token_value, run_id=run_id)
    if record is None:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "Market tool_evidence token was not issued by runtime broker for this run",
            **_market_evidence_feedback(),
        )

    expected_mode = "browser-cockpit-preflight" if browser_value else "approved-downgrade"
    if record.get("mode") != expected_mode:
        _raise_runtime_feedback("E_RUNTIME_PERSIST", "Market tool_evidence token mode mismatch", **_market_evidence_feedback())
    if record.get("run_id") != run_id:
        _raise_runtime_feedback("E_RUNTIME_PERSIST", "Market tool_evidence token run_id mismatch", **_market_evidence_feedback())
    if record.get("context_revision") != context_revision:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "Market tool_evidence token context revision mismatch",
            **_market_evidence_feedback(),
        )
    if record.get("instance_id") != instance_id:
        _raise_runtime_feedback("E_RUNTIME_PERSIST", "Market tool_evidence token instance id mismatch", **_market_evidence_feedback())
    if record.get("buddy_id") != active_buddy:
        _raise_runtime_feedback("E_RUNTIME_PERSIST", "Market tool_evidence token buddy mismatch", **_market_evidence_feedback())

    normalized: dict[str, Any] = {
        "kind": expected_mode,
        "token": token_value,
        "issued_at": record.get("issued_at"),
    }
    if expected_mode == "browser-cockpit-preflight" and isinstance(record.get("browser_url"), str):
        normalized["browser_url"] = record.get("browser_url")
    if expected_mode == "approved-downgrade":
        reason = record.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("approved downgrade token record must include non-empty reason")
        normalized["reason"] = reason.strip()
    return normalized


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
    run_root = env_store.RUN_CONTENT_DIR
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
        persisted_task_id = payload.get("task_id")
        if not isinstance(persisted_task_id, str) or not persisted_task_id:
            continue
        if persisted_task_id != task_id:
            continue
        rows.append(
            {
                "run_id": payload.get("run_id", path.stem),
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
            for kind, row in artifact_slots.items():
                if not isinstance(row, dict):
                    continue
                artifact_id = row.get("current_artifact_id")
                if not isinstance(artifact_id, str) or not artifact_id:
                    continue
                artifact = get_artifact(artifact_id)
                if artifact is not None:
                    current_artifacts[kind] = artifact
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
        "recent_handoffs": _scan_track_recent_handoffs(track["id"], limit=5),
    }


def _scan_track_recent_handoffs(track_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    run_root = env_store.RUN_CONTENT_DIR
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
        payload_track_id = payload.get("track_id")
        if not isinstance(payload_track_id, str) or payload_track_id != track_id:
            continue
        handoff = payload.get("handoff")
        if not isinstance(handoff, dict):
            continue
        next_buddy = handoff.get("next_buddy")
        reason = handoff.get("reason")
        context = handoff.get("context")
        if not isinstance(next_buddy, str) or not next_buddy.strip():
            continue
        if not isinstance(reason, str) or not reason.strip():
            continue
        if not isinstance(context, str) or not context.strip():
            continue
        rows.append(
            {
                "run_id": payload.get("run_id", path.stem),
                "task_id": payload.get("task_id"),
                "buddy_id": payload.get("buddy_id"),
                "next_buddy": next_buddy.strip(),
                "reason": reason.strip(),
                "context": context.strip(),
                "timestamp": payload.get("timestamp"),
            }
        )
    rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("run_id") or ""), reverse=True)
    return rows[:limit]


def _manifest_buddy_order(manifest: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    for row in manifest.get("buddies", []):
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            ordered.append(row["id"])
    return ordered


def _project_write_rule(access: str) -> str:
    if access == "write":
        return "Active buddy can write project source under projects/app."
    return "Project source is read-only for this buddy; hand source edits to Dev."


def _summarize_runtime_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": artifact.get("id"),
        "kind": artifact.get("kind"),
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "buddy": artifact.get("buddy"),
        "task_id": artifact.get("task_id"),
        "source_run_id": artifact.get("source_run_id"),
        "updated_at": artifact.get("updated_at"),
    }


def _build_persist_field_desc(active_buddy: str, tool_capability: dict[str, Any]) -> dict[str, Any]:
    tool_evidence_required: bool | str = False
    if active_buddy == "market" and tool_capability.get("market_research_evidence") == "required":
        tool_evidence_required = "Market artifact-producing commits require broker-issued evidence."
    return {
        "execution_summary": {
            "required": True,
            "purpose": "Short durable summary of what this buddy completed in this turn.",
        },
        "artifacts": {
            "required": False,
            "purpose": "Durable work products owned by the active buddy.",
            "item_fields": ["kind", "title", "summary", "content"],
            "kind_source": "runtime_context.artifact_kind_desc",
        },
        "state_effects.task": {
            "required": False,
            "purpose": "Update status or summary for the current prepared task only.",
            "allowed_fields": ["status", "summary"],
        },
        "state_effects.track": {
            "required": False,
            "purpose": "PM-owned track lifecycle mutations.",
            "rule_source": "runtime_context.track_lifecycle_desc",
        },
        "handoff": {
            "required": False,
            "purpose": "Ask another manifest buddy to continue with explicit reason and context.",
            "does_not_mutate_track": True,
        },
        "contributors": {
            "required": False,
            "purpose": "Record skill ids or agent labels that contributed to the run.",
        },
        "tool_evidence": {
            "required": tool_evidence_required,
            "purpose": "Attach broker-issued evidence tokens; do not hand-write tokens.",
        },
    }


def _build_track_lifecycle_desc(active_buddy: str, allowed_track_effects: list[str]) -> dict[str, Any]:
    if active_buddy == "pm":
        return {
            "owner": "pm",
            "allowed_actions": list(allowed_track_effects),
            "create": "Creates a track and binds the current prepared task.",
            "non_create_requires_existing_track": True,
            "handoff_does_not_mutate_track": True,
            "current_track_source": "current_track_id",
        }
    return {
        "owner": "pm",
        "allowed_actions": [],
        "handoff_does_not_mutate_track": True,
        "allowed_next_action": "Persist an artifact/task update or hand off track lifecycle changes to PM.",
    }


def _build_artifact_kind_desc(buddy: dict[str, Any]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for kind in buddy.get("artifact_kinds", []):
        if not isinstance(kind, str) or not kind:
            continue
        row = _ARTIFACT_KIND_DESC.get(kind)
        if row is None:
            raise ValueError(f"missing runtime artifact kind description for '{kind}'")
        label = row.get("label", "")
        use_when = row.get("use_when", "")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"artifact kind description '{kind}' must include non-empty label")
        if not isinstance(use_when, str) or not use_when.strip():
            raise ValueError(f"artifact kind description '{kind}' must include non-empty use_when")
        rows[kind] = {
            "label": label.strip(),
            "use_when": use_when.strip(),
        }
    return rows


def _build_context_sources_desc() -> dict[str, str]:
    return {
        "request_text": "Original user request for this turn.",
        "task_context.task": "Current task metadata and summary.",
        "task_context.artifacts": "Full prior artifact content for the current task when available.",
        "track_context.track": "Current track title, status, buddies, and summary when bound.",
        "track_context.recent_handoffs": "Recent handoff reason and context.",
        "current_context_summary": "Compact scan-friendly summary; use full task_context artifacts when content detail is needed.",
    }


def _build_runtime_context(
    *,
    manifest: dict[str, Any],
    buddy: dict[str, Any],
    env_profile: dict[str, Any],
    task_context: dict[str, Any],
    track_context: dict[str, Any] | None,
) -> dict[str, Any]:
    state_capability = env_profile.get("state_capability")
    if not isinstance(state_capability, dict):
        raise ValueError("env profile state_capability must be an object")
    tool_capability = env_profile.get("tool_capability")
    if not isinstance(tool_capability, dict):
        raise ValueError("env profile tool_capability must be an object")
    project = env_profile.get("project")
    if not isinstance(project, dict):
        raise ValueError("env profile project must be an object")
    scratch = env_profile.get("scratch")
    if not isinstance(scratch, dict):
        raise ValueError("env profile scratch must be an object")

    project_path = project.get("path")
    if not isinstance(project_path, str) or not project_path:
        raise ValueError("env profile project.path must be a non-empty string")
    project_access = project.get("access")
    if not isinstance(project_access, str) or not project_access:
        raise ValueError("env profile project.access must be a non-empty string")

    allowed_task_effects = state_capability.get("task_effects")
    if not isinstance(allowed_task_effects, list):
        raise ValueError("env profile state_capability.task_effects must be a list")
    allowed_track_effects = state_capability.get("track_effects")
    if not isinstance(allowed_track_effects, list):
        raise ValueError("env profile state_capability.track_effects must be a list")
    normalized_allowed_task_effects = [item for item in allowed_task_effects if isinstance(item, str)]
    normalized_allowed_track_effects = [item for item in allowed_track_effects if isinstance(item, str)]

    tool_requirements = {
        "browser_cockpit": tool_capability.get("browser_cockpit"),
        "market_research_evidence": tool_capability.get("market_research_evidence"),
        "ordinary_web_fallback": tool_capability.get("ordinary_web_fallback"),
    }
    if buddy.get("id") == "market":
        tool_requirements["evidence_next_action"] = (
            "Use scripts/browser_evidence.py issue --context <prepare-context.json> "
            "--mode browser-cockpit-preflight before artifact-producing persist."
        )

    persist_payload_hint: dict[str, Any] = {
        "required": ["execution_summary"],
        "optional": [
            "working_notes",
            "artifacts",
            "state_effects",
            "handoff",
            "contributors",
            "tool_evidence",
        ],
        "durable_signal_rule": "include at least one of artifacts/state_effects/handoff",
        "artifact_kind_source": "runtime_context.capability_boundary.allowed_artifact_kinds",
        "state_effect_source": "runtime_context.capability_boundary.allowed_state_effects",
        "handoff_target_source": "runtime_context.capability_boundary.handoff_targets",
    }
    if buddy.get("id") == "market":
        persist_payload_hint["tool_evidence"] = {
            "required_when": "Market artifact-producing commit",
            "accepted_fields": ["browser_cockpit_token", "approved_downgrade_token"],
            "source": "broker-issued evidence response for current run",
        }

    task_payload = task_context.get("task")
    summarized_task: dict[str, Any] | None
    if isinstance(task_payload, dict):
        summarized_task = {
            "id": task_payload.get("id"),
            "buddy": task_payload.get("buddy"),
            "status": task_payload.get("status"),
            "summary": task_payload.get("summary", ""),
            "track_id": task_payload.get("track_id"),
            "latest_run_id": task_payload.get("latest_run_id"),
        }
    else:
        summarized_task = None

    track_payload = track_context.get("track") if isinstance(track_context, dict) else None
    summarized_track: dict[str, Any] | None
    if isinstance(track_payload, dict):
        summarized_track = {
            "id": track_payload.get("id"),
            "title": track_payload.get("title"),
            "status": track_payload.get("status"),
            "current_buddy": track_payload.get("current_buddy"),
            "next_buddy": track_payload.get("next_buddy"),
            "summary": track_payload.get("summary", ""),
        }
    else:
        summarized_track = None

    task_artifacts = task_context.get("artifacts")
    summarized_artifacts: list[dict[str, Any]] = []
    if isinstance(task_artifacts, list):
        for artifact in task_artifacts:
            if isinstance(artifact, dict):
                summarized_artifacts.append(_summarize_runtime_artifact(artifact))

    handoff_rows = track_context.get("recent_handoffs") if isinstance(track_context, dict) else None
    summarized_handoffs: list[dict[str, Any]] = []
    if isinstance(handoff_rows, list):
        for row in handoff_rows:
            if not isinstance(row, dict):
                continue
            summarized_handoffs.append(
                {
                    "run_id": row.get("run_id"),
                    "task_id": row.get("task_id"),
                    "buddy_id": row.get("buddy_id"),
                    "next_buddy": row.get("next_buddy"),
                    "reason": row.get("reason"),
                    "context": row.get("context"),
                    "timestamp": row.get("timestamp"),
                }
            )

    return {
        "active_buddy": {
            "id": buddy.get("id"),
            "label": buddy.get("label"),
            "scope": buddy.get("scope"),
        },
        "active_skill_ids": list(buddy.get("skills", [])),
        "runtime_commands": _runtime_command_hints(),
        "capability_boundary": {
            "allowed_artifact_kinds": list(buddy.get("artifact_kinds", [])),
            "allowed_state_effects": {
                "task": list(normalized_allowed_task_effects),
                "track": list(normalized_allowed_track_effects),
            },
            "handoff_targets": _manifest_buddy_order(manifest),
            "project": {
                "path": project_path,
                "access": project_access,
                "write_rule": _project_write_rule(project_access),
            },
            "scratch": {
                "root": scratch.get("root"),
                "access": "write",
            },
            "raw_state": {
                "access": "broker-only",
                "paths": list(_RUNTIME_RAW_STATE_PATHS),
            },
        },
        "tool_requirements": tool_requirements,
        "persist_payload_hint": persist_payload_hint,
        "desc": _build_persist_field_desc(str(buddy.get("id") or ""), tool_capability),
        "track_lifecycle_desc": _build_track_lifecycle_desc(
            str(buddy.get("id") or ""),
            normalized_allowed_track_effects,
        ),
        "artifact_kind_desc": _build_artifact_kind_desc(buddy),
        "context_sources_desc": _build_context_sources_desc(),
        "current_context_summary": {
            "task": summarized_task,
            "track": summarized_track,
            "artifacts": summarized_artifacts,
            "recent_handoffs": summarized_handoffs,
        },
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
    env_profile = env_profiles.require_env_profile(
        active_buddy,
        manifest_path=manifest_path,
        repo_root=REPO_ROOT,
    )

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
        if explicit_track_id and existing_task.get("track_id") not in {None, explicit_track_id}:
            raise ValueError(
                f"Task '{existing_task['id']}' is bound to track '{existing_task['track_id']}', cannot switch to '{explicit_track_id}'."
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
    runtime_context = _build_runtime_context(
        manifest=manifest,
        buddy=buddy,
        env_profile=env_profile,
        task_context=task_context,
        track_context=track_context,
    )
    context_save_path = _context_save_path(buddy["id"], run_id)
    persist_command_hint = _persist_command_hint_for_context(context_save_path, buddy["id"])

    prepared_payload = {
        "ok": True,
        "context_revision": context_revision,
        "instance_id": instance_id,
        "active_buddy": buddy["id"],
        "runtime_context": runtime_context,
        "context_save_path": context_save_path,
        "persist_command_hint": persist_command_hint,
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
    context_path = ROOT / context_save_path
    try:
        _write_runtime_json(context_path, prepared_payload)
    except (ValueError, OSError) as exc:
        warning = _clear_run_reservation(run_id)
        if warning is not None:
            _raise_reservation_clear_failure(warning)
        raise ValueError(f"failed to write prepare context to {context_save_path}: {exc}") from exc

    return prepared_payload


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


def _validate_run_envelope(
    *,
    context: dict[str, Any],
    active_buddy: str,
    request_text: str,
    task_id: str,
    track_id: str | None,
) -> tuple[str, dict[str, Any]]:
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
    if context_turn_identity.get("task_id") != task_id:
        raise ValueError("run_envelope.turn_identity task_id mismatch")
    if context_turn_identity.get("track_id") != track_id:
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
    if reserved_task_id != task_id:
        raise ValueError("run reservation mismatch: task_id differs from reserved envelope")
    reserved_sequence = reservation.get("sequence")
    if reserved_sequence != run_envelope.get("sequence"):
        raise ValueError("run reservation mismatch: sequence differs from reserved envelope")
    reservation_turn_identity = reservation.get("turn_identity")
    if not isinstance(reservation_turn_identity, dict):
        raise ValueError("run reservation mismatch: turn_identity payload is missing")
    if _normalize_turn_identity(reservation_turn_identity) != _normalize_turn_identity(context_turn_identity):
        raise ValueError("run reservation mismatch: turn_identity differs from reserved envelope")

    return run_id, run_envelope


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} must contain non-empty strings")
        cleaned.append(item.strip())
    return cleaned


def _known_buddy_ids(manifest: dict[str, Any]) -> set[str]:
    return {
        buddy.get("id")
        for buddy in manifest.get("buddies", [])
        if isinstance(buddy, dict) and isinstance(buddy.get("id"), str)
    }


def _allowed_state_effects_hint(env_profile: dict[str, Any]) -> dict[str, Any]:
    state_capability = env_profile.get("state_capability")
    if not isinstance(state_capability, dict):
        raise ValueError("env profile state_capability must be an object")
    task_effects = state_capability.get("task_effects")
    track_effects = state_capability.get("track_effects")
    if not isinstance(task_effects, list):
        raise ValueError("env profile state_capability.task_effects must be a list")
    if not isinstance(track_effects, list):
        raise ValueError("env profile state_capability.track_effects must be a list")
    return {
        "task": [item for item in task_effects if isinstance(item, str)],
        "track": [item for item in track_effects if isinstance(item, str)],
    }


def _validate_handoff(handoff: Any, known_buddies: set[str]) -> dict[str, Any]:
    if not isinstance(handoff, dict):
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "handoff must be an object",
            permission_boundary="persist.handoff",
            allowed_next_actions=[
                "Provide handoff as an object with next_buddy, reason, and context.",
                "Remove handoff when no transfer is needed.",
            ],
            persist_payload_hint={"handoff_fields": ["next_buddy", "reason", "context"]},
        )
    next_buddy = handoff.get("next_buddy")
    reason = handoff.get("reason")
    context = handoff.get("context")
    if not isinstance(next_buddy, str) or not next_buddy.strip():
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "handoff.next_buddy must be a non-empty string",
            permission_boundary="persist.handoff",
            allowed_next_actions=[
                "Set handoff.next_buddy to a manifest buddy id.",
                "Remove handoff when no transfer is needed.",
            ],
            persist_payload_hint={"handoff_fields": ["next_buddy", "reason", "context"]},
        )
    if next_buddy.strip() not in known_buddies:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            f"handoff.next_buddy must reference a manifest buddy id; got '{next_buddy}'",
            permission_boundary="manifest.buddies",
            allowed_next_actions=[
                "Use one of the manifest buddy ids as handoff.next_buddy.",
                "Remove handoff if no valid target exists.",
            ],
            persist_payload_hint={"handoff_targets": sorted(known_buddies)},
        )
    if not isinstance(reason, str) or not reason.strip():
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "handoff.reason must be a non-empty string",
            permission_boundary="persist.handoff",
            allowed_next_actions=[
                "Add a concise handoff.reason that explains why the next buddy is needed.",
                "Remove handoff when no transfer is needed.",
            ],
            persist_payload_hint={"handoff_fields": ["next_buddy", "reason", "context"]},
        )
    if not isinstance(context, str) or not context.strip():
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "handoff.context must be a non-empty string",
            permission_boundary="persist.handoff",
            allowed_next_actions=[
                "Add handoff.context with the minimum task context the next buddy needs.",
                "Remove handoff when no transfer is needed.",
            ],
            persist_payload_hint={"handoff_fields": ["next_buddy", "reason", "context"]},
        )
    return {
        "next_buddy": next_buddy.strip(),
        "reason": reason.strip(),
        "context": context.strip(),
    }


def _validate_state_effects(
    *,
    state_effects: Any,
    buddy: dict[str, Any],
    env_profile: dict[str, Any],
    task: dict[str, Any],
    explicit_track_id: str | None,
    known_buddies: set[str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if state_effects is None:
        return None, None
    if not isinstance(state_effects, dict):
        raise ValueError("state_effects must be an object")

    track_effect = state_effects.get("track")
    task_effect = state_effects.get("task")

    normalized_track: dict[str, Any] | None = None
    if track_effect is not None:
        if not isinstance(track_effect, dict):
            raise ValueError("state_effects.track must be an object")
        allowed_track_keys = {"action", "track_id", "title", "status", "current_buddy", "next_buddy", "summary"}
        unsupported_track_keys = sorted(key for key in track_effect if key not in allowed_track_keys)
        if unsupported_track_keys:
            raise ValueError(
                "state_effects.track has unsupported keys: "
                + ", ".join(unsupported_track_keys)
            )
        action = track_effect.get("action")
        allowed_state_effects = _allowed_state_effects_hint(env_profile)
        if action not in TRACK_ACTIONS:
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                "state_effects.track.action must be one of create/update/advance/archive",
                permission_boundary="env-profile.state_capability.track_effects",
                allowed_next_actions=[
                    "Use one of create, update, advance, or archive for state_effects.track.action.",
                    "Remove state_effects.track when no track lifecycle mutation is needed.",
                ],
                persist_payload_hint={"allowed_state_effects": allowed_state_effects},
            )
        allowed_track_effects = env_profile.get("state_capability", {}).get("track_effects")
        if not isinstance(allowed_track_effects, list):
            raise ValueError("env profile state_capability.track_effects must be a list")
        if action not in allowed_track_effects:
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"buddy '{buddy.get('id')}' is not allowed to perform track action '{action}'",
                permission_boundary="env-profile.state_capability.track_effects",
                allowed_next_actions=[
                    f"Remove state_effects.track from the {buddy.get('id')} commit.",
                    "Persist an artifact or handoff instead when appropriate.",
                    "Hand off track lifecycle changes to PM.",
                ],
                persist_payload_hint={"allowed_state_effects": allowed_state_effects},
            )

        normalized_track = {"action": action}
        for key in ("track_id", "title", "status", "current_buddy", "next_buddy", "summary"):
            if key in track_effect:
                normalized_track[key] = track_effect.get(key)

        for key in ("current_buddy", "next_buddy"):
            if key not in normalized_track or normalized_track.get(key) is None:
                continue
            value = normalized_track.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"state_effects.track.{key} must be a non-empty string when provided")
            value = value.strip()
            if value not in known_buddies:
                raise ValueError(f"state_effects.track.{key} must reference a manifest buddy id; got '{value}'")
            normalized_track[key] = value

        if "status" in normalized_track and normalized_track.get("status") is not None:
            status = normalized_track.get("status")
            if status not in STATUS_VALUES:
                raise ValueError(f"state_effects.track.status must be one of {', '.join(STATUS_VALUES)}")

        requested_track_id = normalized_track.get("track_id")
        normalized_requested_track_id: str | None
        if isinstance(requested_track_id, str) and requested_track_id.strip():
            normalized_requested_track_id = requested_track_id.strip()
            normalized_track["track_id"] = normalized_requested_track_id
        else:
            normalized_requested_track_id = None
            normalized_track.pop("track_id", None)

        if explicit_track_id and normalized_requested_track_id and normalized_requested_track_id != explicit_track_id:
            raise ValueError("state_effects.track.track_id must match current_track_id when current_track_id is set")

        if action == "create":
            existing_bound_track = explicit_track_id or task.get("track_id")
            if isinstance(existing_bound_track, str) and existing_bound_track:
                _raise_runtime_feedback(
                    "E_RUNTIME_PERSIST",
                    "state_effects.track.create cannot be used when the prepared task is already bound "
                    f"to track '{existing_bound_track}'.",
                    permission_boundary="state_effects.track.create",
                    allowed_next_actions=[
                        "Use update, advance, or archive for the existing track.",
                        "Remove state_effects.track when no lifecycle change is needed.",
                    ],
                    persist_payload_hint={"allowed_state_effects": allowed_state_effects},
                )

        target_track_id = normalized_requested_track_id or explicit_track_id or task.get("track_id")
        if action != "create":
            if not isinstance(target_track_id, str) or not target_track_id:
                _raise_runtime_feedback(
                    "E_RUNTIME_PERSIST",
                    "state_effects.track requires track_id for non-create actions",
                    permission_boundary="state_effects.track.track_id",
                    allowed_next_actions=[
                        "Provide state_effects.track.track_id for update, advance, or archive.",
                        "Create a track first in PM when no current track exists.",
                    ],
                    persist_payload_hint={"allowed_state_effects": allowed_state_effects},
                )
            if get_track(target_track_id) is None:
                _raise_runtime_feedback(
                    "E_RUNTIME_PERSIST",
                    f"Track not found: {target_track_id}",
                    permission_boundary="state_effects.track.track_id",
                    allowed_next_actions=[
                        "Use a valid existing track_id from current context.",
                        "Rerun prepare and confirm current_track_id before persisting.",
                    ],
                    persist_payload_hint={"allowed_state_effects": allowed_state_effects},
                )
            if action in {"update", "advance"}:
                mutable = {
                    key: normalized_track.get(key)
                    for key in ("title", "status", "current_buddy", "next_buddy", "summary")
                    if key in normalized_track and normalized_track.get(key) is not None
                }
                if not mutable:
                    _raise_runtime_feedback(
                        "E_RUNTIME_PERSIST",
                        "state_effects.track for update/advance must include at least one mutable field",
                        permission_boundary="state_effects.track",
                        allowed_next_actions=[
                            "Add at least one of title, status, current_buddy, next_buddy, or summary.",
                            "Remove state_effects.track when no track change is needed.",
                        ],
                        persist_payload_hint={
                            "mutable_fields": ["title", "status", "current_buddy", "next_buddy", "summary"]
                        },
                    )

    normalized_task: dict[str, Any] | None = None
    if task_effect is not None:
        if not isinstance(task_effect, dict):
            raise ValueError("state_effects.task must be an object")
        allowed_task_effects = env_profile.get("state_capability", {}).get("task_effects")
        if not isinstance(allowed_task_effects, list):
            raise ValueError("env profile state_capability.task_effects must be a list")
        allowed_task_keys = set(allowed_task_effects)
        unsupported_task_keys = sorted(key for key in task_effect if key not in allowed_task_keys)
        if unsupported_task_keys:
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                "state_effects.task has unsupported keys: " + ", ".join(unsupported_task_keys),
                permission_boundary="env-profile.state_capability.task_effects",
                allowed_next_actions=[
                    "Remove unsupported state_effects.task fields.",
                    "Use only status and summary for task updates.",
                ],
                persist_payload_hint={"allowed_state_effects": {"task": sorted(allowed_task_keys)}},
            )
        normalized_task = {}
        if "status" in task_effect:
            status = task_effect.get("status")
            if status not in STATUS_VALUES:
                raise ValueError(f"state_effects.task.status must be one of {', '.join(STATUS_VALUES)}")
            normalized_task["status"] = status
        if "summary" in task_effect:
            summary = task_effect.get("summary")
            if summary is not None and not isinstance(summary, str):
                raise ValueError("state_effects.task.summary must be a string")
            normalized_task["summary"] = summary or ""
        if not normalized_task:
            raise ValueError("state_effects.task must include at least one of status or summary")

    return normalized_track, normalized_task


def _validate_artifacts(
    *,
    artifacts: Any,
    allowed_kinds: set[str],
    active_buddy: str,
) -> list[dict[str, Any]]:
    if artifacts is None:
        return []
    if not isinstance(artifacts, list):
        raise ValueError("artifacts must be a list")
    normalized: list[dict[str, Any]] = []
    seen_kinds: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise ValueError("artifacts items must be objects")
        kind = artifact.get("kind")
        title = artifact.get("title")
        content = artifact.get("content")
        summary = artifact.get("summary", "")
        if not isinstance(kind, str) or not kind.strip():
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"artifacts[{index}].kind must be a non-empty string",
                permission_boundary="persist.artifacts",
                allowed_next_actions=[
                    "Provide artifacts as objects with kind, title, summary, and content.",
                    "Remove malformed artifacts entries before persisting.",
                ],
                persist_payload_hint={"artifact_fields": ["kind", "title", "summary", "content"]},
            )
        normalized_kind = kind.strip()
        if normalized_kind in seen_kinds:
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                "duplicate artifact kind in one commit",
                permission_boundary="persist.artifacts.kind",
                allowed_next_actions=[
                    "Keep only one artifact per kind in a single persist commit.",
                    "Split additional artifacts into later turns when needed.",
                ],
                persist_payload_hint={"one_artifact_per_kind": True},
            )
        if normalized_kind not in allowed_kinds:
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"artifact kind '{normalized_kind}' is not allowed for this buddy",
                permission_boundary="manifest.artifact_kinds",
                allowed_next_actions=[
                    f"Use one of the artifact kinds allowed for buddy '{active_buddy}'.",
                    "Hand off work to a buddy that owns the requested artifact kind.",
                ],
                persist_payload_hint={"allowed_artifact_kinds": sorted(allowed_kinds)},
            )
        if not isinstance(title, str) or not title.strip():
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"artifacts[{index}].title must be a non-empty string",
                permission_boundary="persist.artifacts",
                allowed_next_actions=[
                    "Provide artifacts as objects with kind, title, summary, and content.",
                    "Remove malformed artifacts entries before persisting.",
                ],
                persist_payload_hint={"artifact_fields": ["kind", "title", "summary", "content"]},
            )
        if not isinstance(content, dict):
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"artifacts[{index}].content must be an object",
                permission_boundary="persist.artifacts",
                allowed_next_actions=[
                    "Provide artifacts as objects with kind, title, summary, and content.",
                    "Remove malformed artifacts entries before persisting.",
                ],
                persist_payload_hint={"artifact_fields": ["kind", "title", "summary", "content"]},
            )
        if summary is not None and not isinstance(summary, str):
            raise ValueError(f"artifacts[{index}].summary must be a string when provided")
        seen_kinds.add(normalized_kind)
        normalized.append(
            {
                "kind": normalized_kind,
                "title": title.strip(),
                "summary": summary or "",
                "content": content,
            }
        )
    return normalized


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


def _apply_track_effect(
    *,
    track_effect: dict[str, Any] | None,
    active_buddy: str,
    request_text: str,
    task: dict[str, Any],
    effective_track_id: str | None,
) -> tuple[dict[str, Any], str | None, str | None, str | None, str | None, list[str]]:
    if track_effect is None:
        return task, effective_track_id, None, None, None, []

    action = str(track_effect.get("action") or "")
    if action == "create":
        new_id = track_effect.get("track_id") or _derive_track_id(request_text)
        title = track_effect.get("title") or str(new_id).replace("-", " ").title()
        status = track_effect.get("status") or "active"
        track = create_track(
            str(new_id),
            str(title),
            status=str(status),
            current_buddy=track_effect.get("current_buddy") or active_buddy,
            next_buddy=track_effect.get("next_buddy"),
            summary=track_effect.get("summary") or "",
        )
        updated_task = register_task_to_track(track["id"], task["id"])
        writes = [_task_object_path(updated_task["id"]), _track_object_path(track["id"])]
        return updated_task, track["id"], track["title"], track.get("next_buddy"), action, writes

    target_track_id = track_effect.get("track_id") or effective_track_id
    if not isinstance(target_track_id, str) or not target_track_id:
        raise ValueError("state_effects.track requires track_id for non-create actions")

    if action in {"update", "advance"}:
        patch: dict[str, Any] = {}
        for key in ("title", "status", "current_buddy", "next_buddy", "summary"):
            if key in track_effect and track_effect.get(key) is not None:
                patch[key] = track_effect.get(key)
        track = update_track(target_track_id, patch)
    elif action == "archive":
        track = update_track(target_track_id, {"status": "archived"})
    else:
        raise ValueError("state_effects.track.action must be one of create/update/advance/archive")

    updated_task = register_task_to_track(track["id"], task["id"])
    writes = [_task_object_path(updated_task["id"]), _track_object_path(track["id"])]
    return updated_task, track["id"], track["title"], track.get("next_buddy"), action, writes


def _validate_buddy_run_commit(
    *,
    context: dict[str, Any],
    result: dict[str, Any],
    manifest: dict[str, Any],
    buddy: dict[str, Any],
    env_profile: dict[str, Any],
    task: dict[str, Any],
    current_track_id: str | None,
) -> dict[str, Any]:
    if "skill_id" in result:
        raise ValueError("top-level skill_id is not allowed in buddy run commits")

    execution_summary = result.get("execution_summary")
    if not isinstance(execution_summary, str) or not execution_summary.strip():
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "execution_summary must be a non-empty string",
            permission_boundary="persist.execution_summary",
            allowed_next_actions=[
                "Add execution_summary with a short durable summary of completed work.",
                "Keep execution_summary concise and specific to this turn.",
            ],
            persist_payload_hint={"required": ["execution_summary"]},
        )

    working_notes = result.get("working_notes")
    normalized_working_notes: list[str]
    if working_notes is None:
        normalized_working_notes = []
    else:
        normalized_working_notes = _require_string_list(working_notes, "working_notes")

    known_buddies = _known_buddy_ids(manifest)
    profile_state_capability = env_profile.get("state_capability")
    if not isinstance(profile_state_capability, dict):
        raise ValueError("env profile state_capability must be an object")
    if profile_state_capability.get("artifact_kinds") != "from-manifest":
        raise ValueError("env profile must declare state_capability.artifact_kinds=from-manifest")
    allowed_kinds = {
        kind
        for kind in buddy.get("artifact_kinds", [])
        if isinstance(kind, str) and kind
    }
    normalized_artifacts = _validate_artifacts(
        artifacts=result.get("artifacts"),
        allowed_kinds=allowed_kinds,
        active_buddy=str(buddy.get("id") or ""),
    )

    normalized_track_effect, normalized_task_effect = _validate_state_effects(
        state_effects=result.get("state_effects"),
        buddy=buddy,
        env_profile=env_profile,
        task=task,
        explicit_track_id=current_track_id,
        known_buddies=known_buddies,
    )

    normalized_handoff: dict[str, Any] | None = None
    if result.get("handoff") is not None:
        if profile_state_capability.get("handoff_targets") != "manifest-buddies":
            raise ValueError("env profile must declare state_capability.handoff_targets=manifest-buddies")
        normalized_handoff = _validate_handoff(result.get("handoff"), known_buddies)

    if normalized_handoff is not None and normalized_track_effect is not None:
        track_next_buddy = normalized_track_effect.get("next_buddy")
        if isinstance(track_next_buddy, str) and track_next_buddy and track_next_buddy != normalized_handoff["next_buddy"]:
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                "handoff.next_buddy and state_effects.track.next_buddy must match",
                permission_boundary="persist.handoff",
                allowed_next_actions=[
                    "Make handoff.next_buddy and state_effects.track.next_buddy the same value.",
                    "Remove one of the fields when only one transition target is needed.",
                ],
                persist_payload_hint={"handoff_fields": ["next_buddy", "reason", "context"]},
            )

    contributors = result.get("contributors")
    normalized_contributors = {"skills": [], "agents": []}
    if contributors is not None:
        if not isinstance(contributors, dict):
            raise ValueError("contributors must be an object")
        if "skills" in contributors:
            normalized_contributors["skills"] = _require_string_list(contributors.get("skills"), "contributors.skills")
        if "agents" in contributors:
            normalized_contributors["agents"] = _require_string_list(contributors.get("agents"), "contributors.agents")

    normalized_tool_evidence = _validate_market_tool_evidence(
        context=context,
        result=result,
        env_profile=env_profile,
        active_buddy=str(buddy.get("id") or ""),
    )

    has_state_effects = normalized_track_effect is not None or normalized_task_effect is not None
    if not normalized_artifacts and not has_state_effects and normalized_handoff is None:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "at least one durable collaboration signal is required (artifacts/state_effects/handoff)",
            permission_boundary="persist.durable_signal",
            allowed_next_actions=[
                "Provide at least one artifact, state_effects entry, or handoff.",
                "Do not submit summary-only commits with no durable state change.",
            ],
            persist_payload_hint={
                "durable_signal_options": ["artifacts", "state_effects", "handoff"],
            },
        )

    return {
        "execution_summary": execution_summary.strip(),
        "working_notes": normalized_working_notes,
        "artifacts": normalized_artifacts,
        "track_effect": normalized_track_effect,
        "task_effect": normalized_task_effect,
        "handoff": normalized_handoff,
        "contributors": normalized_contributors,
        "tool_evidence": normalized_tool_evidence,
    }


def _build_run_audit(
    *,
    run_id: str,
    active_buddy: str,
    task: dict[str, Any],
    track_id: str | None,
    track_title: str | None,
    artifact_ids: list[str],
    track_action: str | None,
    writes: list[str],
    receipt_paths: dict[str, Any],
    related_run_ids: list[str],
    next_state: dict[str, Any],
    commit: dict[str, Any],
) -> dict[str, Any]:
    state_effects: dict[str, Any] = {}
    if commit.get("track_effect") is not None:
        state_effects["track"] = commit["track_effect"]
    if commit.get("task_effect") is not None:
        state_effects["task"] = commit["task_effect"]

    audit: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": now_iso(),
        "buddy_id": active_buddy,
        "task_id": task["id"],
        "track_id": track_id,
        "task_title": task["title"],
        "track_title": track_title,
        "artifact_ids": artifact_ids,
        "execution_summary": commit["execution_summary"],
        "working_notes": commit["working_notes"],
        "state_effects": state_effects,
        "handoff": commit.get("handoff"),
        "contributors": commit.get("contributors", {"skills": [], "agents": []}),
        "tool_evidence": commit.get("tool_evidence"),
        "next_state": next_state,
        "track_action": track_action,
        "receipt_paths": receipt_paths,
        "related_run_ids": related_run_ids,
        "writes": writes,
    }
    return audit


def _persist_buddy_run(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    if not context.get("ok"):
        raise ValueError("context payload must be successful before persist_buddy_run")
    if not isinstance(result, dict):
        raise ValueError("result payload must be a JSON object")

    early_run_envelope = context.get("run_envelope")
    if not isinstance(early_run_envelope, dict):
        raise ValueError("run_envelope is required")
    early_run_id = early_run_envelope.get("run_id")
    if not isinstance(early_run_id, str) or not early_run_id.strip():
        raise ValueError("run_envelope.run_id is required")
    _assert_run_id_unused(early_run_id.strip())

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

    run_id, _ = _validate_run_envelope(
        context=context,
        active_buddy=active_buddy,
        request_text=request_text,
        task_id=current_task_id,
        track_id=current_track_id,
    )

    manifest = load_manifest(manifest_path)
    buddy = require_buddy(manifest, active_buddy)
    env_profile = env_profiles.require_env_profile(
        active_buddy,
        manifest_path=manifest_path,
        repo_root=REPO_ROOT,
    )
    commit = _validate_buddy_run_commit(
        context=context,
        result=result,
        manifest=manifest,
        buddy=buddy,
        env_profile=env_profile,
        task=stored_task,
        current_track_id=current_track_id,
    )

    _validate_task_binding(task=stored_task, explicit_track_id=current_track_id)
    effective_track_id = current_track_id or stored_task.get("track_id")

    task_after_track, effective_track_id, track_title, track_next_buddy, track_action, track_writes = _apply_track_effect(
        track_effect=commit.get("track_effect"),
        active_buddy=active_buddy,
        request_text=request_text,
        task=stored_task,
        effective_track_id=effective_track_id,
    )

    task = task_after_track
    if effective_track_id:
        task = register_task_to_track(effective_track_id, task["id"])

    if commit.get("task_effect") is not None:
        task_patch: dict[str, Any] = {}
        task_effect = commit["task_effect"]
        if "status" in task_effect:
            task_patch["status"] = task_effect["status"]
        if "summary" in task_effect:
            task_patch["summary"] = task_effect["summary"]
        if task_patch:
            task = env_store.update_task(task["id"], task_patch)

    artifact_ids: list[str] = []
    for artifact_payload in commit["artifacts"]:
        artifact = create_artifact(
            artifact_id=_derive_artifact_id(task["id"], artifact_payload["kind"]),
            title=artifact_payload["title"],
            buddy=active_buddy,
            kind=artifact_payload["kind"],
            task_id=task["id"],
            source_run_id=run_id,
            summary=artifact_payload.get("summary", ""),
            content=artifact_payload["content"],
        )
        artifact_ids.append(artifact["id"])

    summary_for_task_run = commit["execution_summary"]
    task_effect = commit.get("task_effect")
    if isinstance(task_effect, dict) and isinstance(task_effect.get("summary"), str):
        summary_for_task_run = task_effect.get("summary") or summary_for_task_run
    add_run_to_task(task["id"], run_id, summary=summary_for_task_run)

    if effective_track_id:
        track = get_track(effective_track_id)
        if track is not None:
            if track_title is None:
                track_title = track.get("title")
            if track_next_buddy is None:
                track_next_buddy = track.get("next_buddy")

    handoff = commit.get("handoff")
    next_buddy = handoff.get("next_buddy") if isinstance(handoff, dict) else track_next_buddy
    next_state = _build_next_state(
        task_id=task["id"],
        track_id=effective_track_id,
        current_buddy=active_buddy,
        next_buddy=next_buddy,
        track_action=track_action,
    )

    run_content_path_value = run_content_path(run_id)
    related_run_ids = _related_run_ids_for_task(task["id"], run_id, limit=2)
    receipt_paths = _receipt_paths(
        run_content_path_value=run_content_path_value,
        task_id=task["id"],
        artifact_ids=artifact_ids,
        track_id=effective_track_id,
    )

    writes = list(track_writes)
    writes.append(_task_object_path(task["id"]))
    writes.extend(_artifact_object_path(artifact_id) for artifact_id in artifact_ids)
    writes.append(run_content_path_value)
    if effective_track_id:
        writes.append(_track_object_path(effective_track_id))
    writes = list(dict.fromkeys(writes))

    run_audit = _build_run_audit(
        run_id=run_id,
        active_buddy=active_buddy,
        task=task,
        track_id=effective_track_id,
        track_title=track_title,
        artifact_ids=artifact_ids,
        track_action=track_action,
        writes=writes,
        receipt_paths=receipt_paths,
        related_run_ids=related_run_ids,
        next_state=next_state,
        commit=commit,
    )
    save_run_content(run_id, run_audit)

    receipt: dict[str, Any] = {
        "ok": True,
        "buddy_id": active_buddy,
        "task_id": task["id"],
        "task_title": task["title"],
        "artifact_ids": artifact_ids,
        "run_id": run_id,
        "next_state": next_state,
        "receipt_paths": receipt_paths,
        "related_run_ids": related_run_ids,
    }
    if effective_track_id:
        receipt["track_id"] = effective_track_id
        if track_title is not None:
            receipt["track_title"] = track_title
    if track_action is not None:
        receipt["track_action"] = track_action
    if handoff is not None:
        receipt["handoff"] = handoff

    reservation_clear_warning = _clear_run_reservation(run_id)
    if reservation_clear_warning is not None:
        warnings = receipt.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(reservation_clear_warning)

    refreshed_context = _post_persist_refreshed_context_unavailable(receipt)
    return {
        "ok": True,
        "receipt": receipt,
        "refreshed_context": refreshed_context,
    }


def persist_buddy_run(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    return _persist_buddy_run(
        context,
        result=result,
        manifest_path=manifest_path,
    )


def _cmd_prepare(args: argparse.Namespace) -> int:
    try:
        product_session = _load_product_mode_session(args.manifest)
        if product_session is not None and os.environ.get("BUDDYSWITCH_RUNTIME_BROKER_MODE") != "server":
            broker_response = request_runtime_broker("prepare", {"text": args.text})
            if not isinstance(broker_response, dict) or not isinstance(broker_response.get("ok"), bool):
                raise RuntimeBrokerError(
                    "E_RUNTIME_BROKER_UNAVAILABLE",
                    "runtime broker returned invalid response shape for prepare.",
                )
            if broker_response["ok"]:
                payload = broker_response.get("payload")
                if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
                    raise RuntimeBrokerError(
                        "E_RUNTIME_BROKER_UNAVAILABLE",
                        "runtime broker returned invalid payload shape for prepare.",
                    )
            else:
                payload = broker_response
            print(json.dumps(payload, ensure_ascii=True, indent=2))
            return 0 if payload.get("ok") else 1
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
    except RuntimeBrokerError as exc:
        payload = runtime_error(exc.code, exc.message, exc.details)
    except RuntimeFeedbackError as exc:
        payload = runtime_error(exc.code, exc.message, exc.details)
    except (ManifestError, ValueError, OSError) as exc:
        payload = runtime_error("E_RUNTIME_PREPARE", str(exc))
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


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
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "product-mode context instance mismatch: "
            f"expected '{session_instance_id}', received '{context_instance_id}'",
            permission_boundary="active-instance",
            allowed_next_actions=_rerun_prepare_actions(),
        )

    context_buddy = context.get("active_buddy")
    if context_buddy != session_buddy:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "product-mode context buddy mismatch: "
            f"expected '{session_buddy}', received '{context_buddy}'",
            permission_boundary="active-buddy",
            allowed_next_actions=_rerun_prepare_actions(),
        )

    run_envelope = context.get("run_envelope")
    turn_identity = run_envelope.get("turn_identity") if isinstance(run_envelope, dict) else None
    if not isinstance(turn_identity, dict):
        raise ValueError("product-mode context turn_identity is required")
    if turn_identity.get("instance_id") != session_instance_id:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "product-mode turn_identity instance mismatch: "
            f"expected '{session_instance_id}', received '{turn_identity.get('instance_id')}'",
            permission_boundary="active-instance",
            allowed_next_actions=_rerun_prepare_actions(),
        )
    if turn_identity.get("active_buddy") != session_buddy:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "product-mode turn_identity buddy mismatch: "
            f"expected '{session_buddy}', received '{turn_identity.get('active_buddy')}'",
            permission_boundary="active-buddy",
            allowed_next_actions=_rerun_prepare_actions(),
        )


def _cmd_persist(args: argparse.Namespace) -> int:
    try:
        if args.context == "-" and args.result == "-":
            raise ValueError("context and result cannot both read from stdin")
        stdin_text = sys.stdin.read() if args.context == "-" or args.result == "-" else None
        context = _read_json_input(args.context, stdin_text=stdin_text if args.context == "-" else None)
        result = _read_json_input(args.result, stdin_text=stdin_text if args.result == "-" else None)
        product_session = _load_product_mode_session(args.manifest)
        if product_session is not None and os.environ.get("BUDDYSWITCH_RUNTIME_BROKER_MODE") != "server":
            broker_response = request_runtime_broker(
                "persist",
                {"context": context, "result": result},
            )
            if not isinstance(broker_response, dict) or not isinstance(broker_response.get("ok"), bool):
                raise RuntimeBrokerError(
                    "E_RUNTIME_BROKER_UNAVAILABLE",
                    "runtime broker returned invalid response shape for persist.",
                )
            if broker_response["ok"]:
                payload = broker_response.get("payload")
                if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
                    raise RuntimeBrokerError(
                        "E_RUNTIME_BROKER_UNAVAILABLE",
                        "runtime broker returned invalid payload shape for persist.",
                    )
            else:
                payload = broker_response
            print(json.dumps(payload, ensure_ascii=True, indent=2))
            return 0 if payload.get("ok") else 1
        if product_session is None:
            payload = persist_buddy_run(
                context,
                result=result,
                manifest_path=args.manifest,
            )
        else:
            with _hold_product_runtime_lock(product_session):
                product_session = _load_product_mode_session(args.manifest)
                if product_session is None:
                    raise ValueError("product-mode env disappeared while acquiring runtime lock")
                _validate_product_persist_context_binding(context, product_session)
                payload = persist_buddy_run(
                    context,
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
    except RuntimeBrokerError as exc:
        payload = runtime_error(exc.code, exc.message, exc.details)
    except RuntimeFeedbackError as exc:
        payload = runtime_error(exc.code, exc.message, exc.details)
    except (ManifestError, ValueError, OSError, json.JSONDecodeError) as exc:
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
    persist_cmd.set_defaults(func=_cmd_persist)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
