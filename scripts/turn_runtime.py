#!/usr/bin/env python3
"""BuddySwitch runtime: prepare turn context and persist structured results."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
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
from env.services import context as context_service
from env.tools import contracts as tool_contracts
from env.tools import responses as tool_responses
from env_store import (
    build_track_artifact_index,
    get_task,
    get_track,
    list_tasks,
    now_iso,
    require_runtime_workspace_write_root,
    run_content_path,
)
from runtime_kernel.client import (
    RuntimeBrokerError,
    canonical_result_hash,
    make_persist_idempotency_key,
    request_runtime_broker,
)
ROOT = env_store.ROOT
REPO_ROOT = Path(__file__).resolve().parents[1]


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
        "python3 scripts/env/client.py evidence issue-browser "
        "--context <prepare-context.json>"
    )


def _market_evidence_feedback() -> dict[str, Any]:
    options = [
        tool_responses.next_action_option(
            tool="evidence",
            action="issue_browser",
            option_id="issue_browser_token_for_current_run",
            reason="Issue a browser cockpit token for this prepared run before artifact-producing persist.",
        ),
        tool_responses.next_action_option(
            tool="evidence",
            action="approve_downgrade",
            option_id="issue_approved_downgrade_for_current_run",
            reason="Issue an approved downgrade token only when the user explicitly approves the fallback.",
        ),
    ]
    return {
        "permission_boundary": "market.browser_evidence",
        "allowed_next_actions": [
            "Issue broker-backed browser evidence for the current prepared run.",
            "Include the returned token in tool_evidence on the next artifact-producing persist.",
            "Use an approved downgrade token only when the user explicitly approves the fallback.",
        ],
        "allowed_next_action_options": options,
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
        payload.update(extra)
    if "allowed_next_actions" in payload and "allowed_next_action_options" not in payload:
        payload["allowed_next_action_options"] = [
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_current_context_before_retry",
                reason="Summarize current context before deciding the next mutation.",
            ),
            tool_responses.next_action_option(
                tool="context",
                action="get",
                option_id="inspect_full_context_before_retry",
                reason="Inspect full current context sections before retrying persist.",
            ),
        ]
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
def _hold_product_runtime_lock(
    product_session: dict[str, Any],
    *,
    mode: str = "write",
    timeout_seconds: float | None = None,
):
    shared_root = str(_product_runtime_shared_root(product_session)).rstrip("/")
    if not shared_root:
        raise ValueError("BUDDYSWITCH_SHARED_ROOT must not be empty")
    resolved_timeout_seconds = _runtime_lock_timeout_seconds() if timeout_seconds is None else timeout_seconds
    lock_path = Path(shared_root) / "run" / "locks" / "runtime.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    lock_flag = fcntl.LOCK_EX
    if mode == "read":
        lock_flag = fcntl.LOCK_SH
    elif mode != "write":
        raise ValueError(f"unsupported runtime lock mode: {mode}")
    deadline = time.monotonic() + resolved_timeout_seconds
    try:
        while True:
            try:
                fcntl.flock(lock_fd, lock_flag | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"runtime state busy: could not acquire lock at {lock_path} within {resolved_timeout_seconds:.2f}s"
                    )
                time.sleep(_RUNTIME_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


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


def _ensure_no_legacy_outputs(demand: str) -> None:
    for pattern in _LEGACY_OUTPUT_PATTERNS:
        match = pattern.search(demand)
        if match:
            raise ValueError(f"{LEGACY_OUTPUT_ERROR} Rejecting requested path '{match.group(1)}'.")


def _build_next_state(
    *,
    task_id: str | None,
    track_id: str | None,
    current_buddy: str,
    next_buddy: str | None,
    track_action: str | None = None,
) -> dict[str, Any]:
    resolved_next_buddy = next_buddy if isinstance(next_buddy, str) and next_buddy.strip() else None
    if resolved_next_buddy and resolved_next_buddy != current_buddy:
        mode = "handoff"
    elif task_id:
        mode = "task_associated"
    elif track_id:
        mode = "track_associated"
    else:
        mode = "taskless_audit"
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
    validated = _validate_prepared_run_context(context)
    task_id = validated.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return {}
    stored_task = get_task(task_id.strip())
    if stored_task is None:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            f"task not found: {task_id}",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=_rerun_prepare_actions(),
        )
    return stored_task


def _validate_prepared_run_context(context: dict[str, Any]) -> dict[str, Any]:
    context_revision = context.get("context_revision")
    if not isinstance(context_revision, str) or not context_revision.strip():
        raise ValueError("context_revision is required")
    context_revision = context_revision.strip()

    run_envelope = context.get("run_envelope")
    if not isinstance(run_envelope, dict):
        raise ValueError("run_envelope is required")
    run_id = run_envelope.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_envelope.run_id is required")
    run_id = run_id.strip()
    expected_revision = _derive_run_context_revision(run_id)
    if context_revision != expected_revision:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            f"context_revision mismatch: expected '{expected_revision}', received '{context_revision}'",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=_rerun_prepare_actions(),
        )

    sequence = run_envelope.get("sequence")
    if isinstance(sequence, int) and sequence != 1:
        _raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            f"context_revision mismatch: expected sequence 1, received {sequence}",
            permission_boundary="prepare.context_revision",
            allowed_next_actions=_rerun_prepare_actions(),
        )
    turn_identity = run_envelope.get("turn_identity")
    if not isinstance(turn_identity, dict):
        raise ValueError("run_envelope.turn_identity is required")

    task_id = context.get("current_task_id")
    if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
        raise ValueError("current_task_id must be a non-empty string or null")
    track_id = context.get("current_track_id")
    if track_id is not None and (not isinstance(track_id, str) or not track_id.strip()):
        raise ValueError("current_track_id must be a non-empty string or null")

    if turn_identity.get("run_id") != run_id:
        raise ValueError("run_envelope.turn_identity run_id mismatch")
    if turn_identity.get("context_revision") != context_revision:
        raise ValueError("run_envelope.turn_identity context_revision mismatch")
    if turn_identity.get("task_id") != task_id:
        raise ValueError("run_envelope.turn_identity task_id mismatch")
    if turn_identity.get("track_id") != track_id:
        raise ValueError("run_envelope.turn_identity track_id mismatch")
    if turn_identity.get("instance_id") != context.get("instance_id"):
        raise ValueError("run_envelope.turn_identity instance_id mismatch")
    if turn_identity.get("active_buddy") != context.get("active_buddy"):
        raise ValueError("run_envelope.turn_identity active_buddy mismatch")
    if turn_identity.get("request_text") != context.get("request_text"):
        raise ValueError("run_envelope.turn_identity request_text mismatch")

    return {
        "run_id": run_id,
        "context_revision": context_revision,
        "sequence": sequence,
        "task_id": task_id.strip() if isinstance(task_id, str) else None,
        "track_id": track_id.strip() if isinstance(track_id, str) else None,
        "instance_id": context.get("instance_id"),
        "active_buddy": context.get("active_buddy"),
        "request_text": context.get("request_text"),
        "run_envelope": run_envelope,
        "turn_identity": turn_identity,
    }


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
    from env.services import runs as run_service

    return run_service.reserved_run_path(run_id)


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

    artifact_ids = result.get("artifact_ids")
    has_artifact_refs = isinstance(artifact_ids, list) and len(artifact_ids) > 0
    if not has_artifact_refs:
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
    token_task_id = record.get("task_id")
    result_task_id = result.get("task_id")
    if isinstance(token_task_id, str) and token_task_id:
        if result_task_id is None:
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                "Market tool_evidence token is scoped to a task but result.task_id is missing",
                **_market_evidence_feedback(),
            )
        if token_task_id != result_task_id:
            _raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                "Market tool_evidence token task scope mismatch",
                **_market_evidence_feedback(),
            )

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


def _build_persist_field_desc(active_buddy: str, tool_capability: dict[str, Any]) -> dict[str, Any]:
    tool_evidence_required: bool | str = False
    if active_buddy == "market" and tool_capability.get("market_research_evidence") == "required":
        tool_evidence_required = "Market commits with evidence-backed artifact refs require broker-issued evidence."
    return {
        "execution_summary": {
            "required": True,
            "purpose": "Short durable summary of what this buddy completed in this turn.",
        },
        "task_id": {
            "required": False,
            "purpose": "Optional association to an existing active-buddy task already created through task-tool.",
        },
        "track_id": {
            "required": False,
            "purpose": "Optional association to an existing track already managed through track-tool.",
        },
        "artifact_ids": {
            "required": False,
            "purpose": "Optional refs to artifacts already written through artifact-tool.",
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


def _build_env_tools_desc() -> dict[str, Any]:
    return tool_contracts.env_tools_description()


def _build_runtime_context(
    *,
    manifest: dict[str, Any],
    buddy: dict[str, Any],
    env_profile: dict[str, Any],
    current_binding: dict[str, Any],
    task_context: dict[str, Any] | None,
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
        allowed_task_effects = []
    allowed_track_effects = state_capability.get("track_effects")
    if not isinstance(allowed_track_effects, list):
        allowed_track_effects = []
    normalized_allowed_task_effects = [item for item in allowed_task_effects if isinstance(item, str)]
    normalized_allowed_track_effects = [item for item in allowed_track_effects if isinstance(item, str)]

    tool_requirements = {
        "browser_cockpit": tool_capability.get("browser_cockpit"),
        "market_research_evidence": tool_capability.get("market_research_evidence"),
        "ordinary_web_fallback": tool_capability.get("ordinary_web_fallback"),
    }
    if buddy.get("id") == "market":
        tool_requirements["evidence_next_action"] = (
            "Use scripts/env/client.py evidence issue-browser --context <prepare-context.json> "
            "before artifact-producing persist."
        )

    persist_payload_hint: dict[str, Any] = {
        "required": ["execution_summary"],
        "optional": [
            "working_notes",
            "task_id",
            "track_id",
            "artifact_ids",
            "handoff",
            "contributors",
            "tool_evidence",
        ],
        "durable_signal_rule": "audit-only commits are valid; lifecycle writes must use env tools first",
        "task_write_source": "runtime_context.env_tools.task",
        "track_write_source": "runtime_context.env_tools.track",
        "artifact_write_source": "runtime_context.env_tools.artifact",
        "handoff_target_source": "runtime_context.capability_boundary.handoff_targets",
    }
    if buddy.get("id") == "market":
        persist_payload_hint["tool_evidence"] = {
            "required_when": "Market artifact-producing commit",
            "accepted_fields": ["browser_cockpit_token", "approved_downgrade_token"],
            "source": "broker-issued evidence response for current run",
        }

    decision_surface = context_service.build_decision_surface(
        active_buddy=str(buddy.get("id") or ""),
        current_binding=current_binding,
        task_context=task_context,
        track_context=track_context,
        tool_requirements=tool_requirements,
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
            "state_write_boundary": {
                "task": "Use task-tool/env.tool task actions.",
                "track": "Use track-tool/env.tool track actions.",
                "artifact": "Use artifact-tool/env.tool artifact actions.",
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
        "env_tools": _build_env_tools_desc(),
        "operation_semantics": tool_contracts.operation_semantics(),
        "tool_requirements": tool_requirements,
        "persist_payload_hint": persist_payload_hint,
        "desc": _build_persist_field_desc(str(buddy.get("id") or ""), tool_capability),
        "track_lifecycle_desc": _build_track_lifecycle_desc(
            str(buddy.get("id") or ""),
            normalized_allowed_track_effects,
        ),
        "artifact_kind_desc": _build_artifact_kind_desc(buddy),
        "decision_surface": decision_surface,
        "context_sources_desc": context_service.context_sources_desc(),
        "current_context_summary": context_service.summarize_current_context(
            task_context=task_context,
            track_context=track_context,
        ),
    }


def _derive_run_context_revision(run_id: str) -> str:
    normalized_run_id = env_store.require_id(run_id.strip(), "run id")
    return f"ctx-{normalized_run_id}"


def _build_turn_identity(
    *,
    instance_id: str | None,
    active_buddy: str,
    request_text: str,
    task_id: str | None,
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
    from env.services import runs as run_service

    return run_service.find_active_task_reservation(task_id)


def _save_run_reservation(
    *,
    run_id: str,
    context_revision: str,
    sequence: int,
    task_id: str | None,
    turn_identity: dict[str, Any],
    instance_id: str | None,
) -> None:
    from env.services import runs as run_service

    run_service.save_run_reservation(
        run_id=run_id,
        context_revision=context_revision,
        sequence=sequence,
        task_id=task_id,
        turn_identity=turn_identity,
        instance_id=instance_id,
    )


def _load_run_reservation(run_id: str) -> dict[str, Any]:
    from env.services import runs as run_service

    return run_service.load_run_reservation(run_id)


def _clear_run_reservation(run_id: str) -> dict[str, Any] | None:
    from env.services import runs as run_service

    return run_service.clear_run_reservation(run_id)


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


def _binding_state_name(*, task_id: str | None, track_id: str | None, stale: bool) -> str:
    if stale:
        return "stale"
    if task_id and track_id:
        return "bound_task_and_track"
    if task_id:
        return "bound_task_only"
    if track_id:
        return "bound_track_only"
    return "unbound"


def _binding_snapshot_from_product_session(
    product_session: dict[str, Any],
    active_buddy: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    payload = product_session.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    raw_task_id = payload_dict.get("current_task_id")
    raw_track_id = payload_dict.get("current_track_id")
    current_task_id = raw_task_id.strip() if isinstance(raw_task_id, str) and raw_task_id.strip() else None
    current_track_id = raw_track_id.strip() if isinstance(raw_track_id, str) and raw_track_id.strip() else None
    warnings: list[dict[str, Any]] = []

    task: dict[str, Any] | None = None
    track: dict[str, Any] | None = None
    stale = False
    if current_task_id:
        task = get_task(current_task_id)
        if task is None:
            stale = True
            warnings.append(
                {
                    "code": "W_STALE_TASK_BINDING",
                    "message": f"active instance binding points to missing task '{current_task_id}'",
                    "task_id": current_task_id,
                    "allowed_next_actions": [
                        "Use task.list to inspect active-buddy tasks.",
                        "Use task.set_current, binding.set_task, or binding.clear to repair the binding explicitly.",
                    ],
                }
            )
        elif task.get("buddy") != active_buddy:
            stale = True
            warnings.append(
                {
                    "code": "W_STALE_TASK_BINDING",
                    "message": f"active instance binding points to task owned by '{task.get('buddy')}'",
                    "task_id": current_task_id,
                    "allowed_next_actions": [
                        "Use task.list to inspect active-buddy tasks.",
                        "Use binding.clear or task.set_current with an active-buddy task.",
                    ],
                }
            )
            task = None

    if current_track_id:
        track = get_track(current_track_id)
        if track is None:
            stale = True
            warnings.append(
                {
                    "code": "W_STALE_TRACK_BINDING",
                    "message": f"active instance binding points to missing track '{current_track_id}'",
                    "track_id": current_track_id,
                    "allowed_next_actions": [
                        "Use track.list to inspect tracks.",
                        "Use binding.set_track or binding.clear to repair the binding explicitly.",
                    ],
                }
            )

    if current_track_id is None and isinstance(task, dict):
        task_track_id = task.get("track_id")
        if isinstance(task_track_id, str) and task_track_id.strip():
            derived_track = get_track(task_track_id.strip())
            if derived_track is None:
                warnings.append(
                    {
                        "code": "W_STALE_TRACK_BINDING",
                        "message": f"bound task points to missing track '{task_track_id}'",
                        "track_id": task_track_id,
                        "allowed_next_actions": [
                            "Use track.list to inspect tracks.",
                            "Use track.attach_task or task.update through env tools to repair task-track linkage.",
                        ],
                    }
                )
            else:
                track = derived_track

    state = _binding_state_name(task_id=current_task_id, track_id=current_track_id, stale=stale)
    snapshot = {
        "instance_id": product_session.get("instance_id"),
        "active_buddy": active_buddy,
        "current_task_id": current_task_id,
        "current_track_id": current_track_id,
        "binding_state": state,
        "state": state,
    }
    return snapshot, task, track, warnings


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

    _ensure_no_legacy_outputs(demand)

    buddy = require_buddy(manifest, active_buddy)
    env_profile = env_profiles.require_env_profile(
        active_buddy,
        manifest_path=manifest_path,
        repo_root=REPO_ROOT,
    )

    run_id = f"run-{uuid.uuid4().hex[:10]}"
    sequence = 1
    context_revision = _derive_run_context_revision(run_id)
    binding_snapshot, resolved_task, resolved_track, warnings = _binding_snapshot_from_product_session(
        product_session,
        active_buddy,
    )
    current_task_id = resolved_task["id"] if isinstance(resolved_task, dict) else None
    if isinstance(resolved_track, dict):
        effective_track_id = resolved_track["id"]
    elif isinstance(resolved_task, dict) and isinstance(resolved_task.get("track_id"), str):
        effective_track_id = resolved_task.get("track_id")
    else:
        effective_track_id = None

    task_context = context_service.build_task_context(resolved_task) if resolved_task is not None else None
    track_context = context_service.build_track_context(effective_track_id)
    if task_context is not None:
        task_context = context_service.enrich_task_context_with_track_artifacts(
            task_context=task_context,
            track_context=track_context,
        )
    track_artifact_index = build_track_artifact_index(effective_track_id)

    turn_identity = _build_turn_identity(
        instance_id=instance_id,
        active_buddy=active_buddy,
        request_text=request_text,
        task_id=current_task_id,
        track_id=effective_track_id,
        context_revision=context_revision,
        sequence=sequence,
        run_id=run_id,
    )
    _save_run_reservation(
        run_id=run_id,
        context_revision=context_revision,
        sequence=sequence,
        task_id=current_task_id,
        turn_identity=turn_identity,
        instance_id=instance_id,
    )

    current_track_id = effective_track_id

    runtime_context = _build_runtime_context(
        manifest=manifest,
        buddy=buddy,
        env_profile=env_profile,
        current_binding=binding_snapshot,
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
        "binding_snapshot": binding_snapshot,
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
        "warnings": warnings,
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


def persist_buddy_run(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    from env.services import runs as run_service

    return run_service.commit_buddy_run(
        context,
        result=result,
        manifest_path=manifest_path,
    )


def _prepare_direct(text: str, *, manifest_path: Path, product_session: dict[str, Any] | None) -> dict[str, Any]:
    if product_session is None:
        return prepare_turn_context(text, manifest_path=manifest_path)
    with _hold_product_runtime_lock(product_session):
        refreshed_product_session = _load_product_mode_session(manifest_path)
        if refreshed_product_session is None:
            raise ValueError("product-mode env disappeared while acquiring runtime lock")
        return prepare_turn_context(text, manifest_path=manifest_path)


def _persist_direct(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path,
    product_session: dict[str, Any] | None,
) -> dict[str, Any]:
    if product_session is None:
        return persist_buddy_run(
            context,
            result=result,
            manifest_path=manifest_path,
        )
    with _hold_product_runtime_lock(product_session):
        refreshed_product_session = _load_product_mode_session(manifest_path)
        if refreshed_product_session is None:
            raise ValueError("product-mode env disappeared while acquiring runtime lock")
        _validate_product_persist_context_binding(context, refreshed_product_session)
        return persist_buddy_run(
            context,
            result=result,
            manifest_path=manifest_path,
        )


def _cmd_prepare(args: argparse.Namespace) -> int:
    try:
        product_session = _load_product_mode_session(args.manifest)
        if product_session is not None and os.environ.get("BUDDYSWITCH_RUNTIME_BROKER_MODE") != "server":
            payload = request_runtime_broker("prepare", {"text": args.text})
            if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
                raise RuntimeBrokerError(
                    "E_RUNTIME_BROKER_PROTOCOL",
                    "runtime broker returned invalid result shape for prepare.",
                )
            print(json.dumps(payload, ensure_ascii=True, indent=2))
            return 0 if payload.get("ok") else 1
        payload = _prepare_direct(args.text, manifest_path=args.manifest, product_session=product_session)
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
            idempotency_key = make_persist_idempotency_key(context, result)
            payload = request_runtime_broker("persist", {"context": context, "result": result}, idempotency_key=idempotency_key, result_hash=canonical_result_hash(result))
            if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
                raise RuntimeBrokerError(
                    "E_RUNTIME_BROKER_PROTOCOL",
                    "runtime broker returned invalid result shape for persist.",
                )
            print(json.dumps(payload, ensure_ascii=True, indent=2))
            return 0 if payload.get("ok") else 1
        payload = _persist_direct(
            context,
            result=result,
            manifest_path=args.manifest,
            product_session=product_session,
        )
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
