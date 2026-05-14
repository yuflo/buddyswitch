#!/usr/bin/env python3
"""Current runtime context service for broker-routed env.tool operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

import env_profiles
import env_store
from env.services import bindings
from env.tools import responses as tool_responses

_IDENTITY_FIELDS = {"active_buddy", "buddy", "instance_id"}
_GET_FIELDS = {"context"} | _IDENTITY_FIELDS


class ContextServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _error_payload(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    allowed_next_actions: list[str],
    human_summary: str | None = None,
    why_blocked: str | None = None,
    impact: str = "No runtime context or object state was changed.",
    retryable: bool = True,
    retry_guidance: str | None = None,
    allowed_next_action_options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        human_summary=human_summary or message,
        why_blocked=why_blocked or message,
        impact=impact,
        state_changed=False,
        retryable=retryable,
        retry_guidance=retry_guidance or "Refresh context payload or active instance state, then retry.",
        allowed_next_actions=allowed_next_actions,
        allowed_next_action_options=allowed_next_action_options,
    )


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_CONTEXT_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Context request payload is invalid.",
        why_blocked=message,
        retryable=True,
        retry_guidance="Fix context payload fields and retry.",
        allowed_next_actions=[
            'Fix the env.tool envelope fields (`tool`, `action`, `args`) and retry.',
            "Use context.list_sources to inspect available context sections.",
        ],
        allowed_next_action_options=[
            tool_responses.next_action_option(
                tool="context",
                action="list_sources",
                option_id="inspect_context_sources",
                reason="Inspect available context sections and payload expectations.",
            ),
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_current_context",
                reason="Review compact current context before retrying payload input.",
            ),
        ],
    )


def _context_boundary_error(
    *,
    action: str,
    active_buddy: str,
    code: str = "E_CONTEXT_SCOPE",
    message: str,
    permission_boundary: str,
) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        human_summary="Prepared context does not match active runtime state.",
        why_blocked=message,
        retryable=True,
        retry_guidance="Rerun prepare in the active instance and retry with the refreshed context.",
        allowed_next_actions=[
            "Rerun prepare in the active launcher-managed instance.",
            "Use the refreshed context returned by prepare for the next action.",
        ],
        allowed_next_action_options=[
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_active_context_before_prepare",
                reason="Summarize active context before rerunning prepare.",
            ),
            tool_responses.next_action_option(
                tool="context",
                action="get",
                option_id="inspect_active_context_before_prepare",
                reason="Inspect full active context and binding before rerunning prepare.",
            ),
        ],
    )


def _ensure_allowed_fields(
    *,
    action: str,
    active_buddy: str,
    args: dict[str, Any],
    allowed_fields: set[str],
) -> dict[str, Any] | None:
    unknown = sorted(key for key in args.keys() if key not in allowed_fields)
    if not unknown:
        return None
    return _payload_error(
        action=action,
        active_buddy=active_buddy,
        message=f"unsupported payload fields: {', '.join(unknown)}",
    )


def _summarize_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    source_buddy = artifact.get("buddy")
    source_run_id = artifact.get("source_run_id")
    is_current = bool(artifact.get("is_current"))
    return {
        "id": artifact.get("id"),
        "kind": artifact.get("kind"),
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "buddy": source_buddy,
        "source_buddy": source_buddy,
        "task_id": artifact.get("task_id"),
        "source_run_id": source_run_id,
        "source_run": source_run_id,
        "revision": artifact.get("revision"),
        "is_current": is_current,
        "currentness": "current" if is_current else "superseded",
        "updated_at": artifact.get("updated_at"),
    }


def context_sources_desc() -> dict[str, dict[str, Any]]:
    return {
        "request_text": {
            "description": "Original user request for this turn.",
            "content": "full",
            "scope": "current_turn_input",
            "nullable": False,
            "decision_use": ["request_intent", "handoff_continuation"],
            "source_of_truth": "prepare.request_text",
            "summary_projection": "runtime_context.current_context_summary.task",
        },
        "task_context.task": {
            "description": "Current task metadata and summary.",
            "content": "summary",
            "scope": "active_instance_task",
            "nullable": True,
            "decision_use": ["task_ownership", "task_status"],
            "source_of_truth": "buddyswitch/objects/tasks/<task_id>.json",
        },
        "task_context.artifacts": {
            "description": "Projection of recent current-task artifacts for context continuity; direct full-body reads use artifact.get.",
            "content": "full",
            "scope": "active_instance_task_artifacts",
            "nullable": True,
            "decision_use": ["artifact_continuation", "source_orientation"],
            "source_of_truth": "buddyswitch/objects/artifacts/<artifact_id>.json",
            "summary_projection": "runtime_context.current_context_summary.artifacts",
            "max_items": 5,
            "sorted_by": "updated_at desc, id desc",
        },
        "track_context.track": {
            "description": "Current track title, status, buddies, and summary when bound.",
            "content": "summary",
            "scope": "current_track",
            "nullable": True,
            "decision_use": ["track_alignment", "ownership_alignment"],
            "source_of_truth": "buddyswitch/objects/tracks/<track_id>.json",
        },
        "track_context.recent_handoffs": {
            "description": "Recent handoff reason and context discovered from committed run audits.",
            "content": "summary",
            "scope": "current_track_run_audits",
            "nullable": True,
            "decision_use": ["handoff_continuation", "latest_transition_check"],
            "source_of_truth": "buddyswitch/content/runs/<run_id>.json",
            "max_items": 5,
            "sorted_by": "timestamp desc, run_id desc",
        },
        "current_context_summary": {
            "description": "Compact scan-friendly summary; use track.get and artifact.get for direct source intake.",
            "content": "summary",
            "scope": "active_instance_projection",
            "nullable": False,
            "decision_use": ["first_pass_orientation", "safe_context_scan"],
            "source_of_truth": "runtime projection from task_context + track_context",
            "summary_projection": "runtime_context.current_context_summary",
        },
    }


def _build_candidate_track_rows(*, active_buddy: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in env_store.list_tracks():
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id:
            continue

        reasons: list[str] = []
        role = "observer"
        score = 0
        current_buddy = track.get("current_buddy")
        next_buddy = track.get("next_buddy")
        if isinstance(current_buddy, str) and current_buddy == active_buddy:
            role = "current_buddy"
            score += 60
            reasons.append("track.current_buddy == active_buddy")
        if isinstance(next_buddy, str) and next_buddy == active_buddy:
            role = "next_buddy"
            score += 80
            reasons.append("track.next_buddy == active_buddy")

        has_active_task = False
        for task_id in track.get("task_ids", []):
            if not isinstance(task_id, str) or not task_id:
                continue
            task = env_store.get_task(task_id)
            if isinstance(task, dict) and task.get("buddy") == active_buddy:
                has_active_task = True
                break
        if has_active_task:
            if role == "observer":
                role = "participant"
            score += 40
            reasons.append("track contains active_buddy task")

        recent_handoffs = scan_track_recent_handoffs(track_id, limit=1)
        latest_handoff_to_active = False
        if recent_handoffs:
            handoff = recent_handoffs[0]
            if handoff.get("next_buddy") == active_buddy:
                latest_handoff_to_active = True
                score += 100
                reasons.append("recent_handoff.next_buddy == active_buddy")

        if score <= 0:
            continue
        rows.append(
            {
                "track_id": track_id,
                "title": track.get("title"),
                "status": track.get("status"),
                "current_buddy": current_buddy,
                "next_buddy": next_buddy,
                "summary": track.get("summary", ""),
                "active_buddy_role": role,
                "latest_handoff_to_active_buddy": latest_handoff_to_active,
                "relevance_score": score,
                "relevance_reasons": reasons,
                "updated_at": track.get("updated_at"),
            }
        )
    rows.sort(
        key=lambda row: (
            int(row.get("relevance_score") or 0),
            str(row.get("updated_at") or ""),
            str(row.get("track_id") or ""),
        ),
        reverse=True,
    )
    return rows


def build_decision_surface(
    *,
    active_buddy: str,
    current_binding: dict[str, Any],
    task_context: dict[str, Any] | None,
    track_context: dict[str, Any] | None,
    tool_requirements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    binding_task_id = current_binding.get("current_task_id")
    binding_track_id = current_binding.get("current_track_id")

    has_task_binding = isinstance(binding_task_id, str) and bool(binding_task_id.strip())
    has_track_binding = isinstance(binding_track_id, str) and bool(binding_track_id.strip())

    task_row = task_context.get("task") if isinstance(task_context, dict) else None
    task_missing = has_task_binding and not isinstance(task_row, dict)
    track_row = track_context.get("track") if isinstance(track_context, dict) else None
    track_missing = has_track_binding and not isinstance(track_row, dict)

    if task_missing or track_missing:
        binding_state = "stale"
    elif has_task_binding and has_track_binding:
        binding_state = "bound_task_and_track"
    elif has_task_binding:
        binding_state = "bound_task_only"
    elif has_track_binding:
        binding_state = "bound_track_only"
    else:
        binding_state = "unbound"

    if isinstance(task_row, dict):
        task_buddy = task_row.get("buddy")
        if isinstance(task_buddy, str):
            task_role = "owner" if task_buddy == active_buddy else "foreign"
        else:
            task_role = "missing"
    else:
        task_role = "missing" if has_task_binding else "none"

    if isinstance(track_row, dict):
        current_buddy = track_row.get("current_buddy")
        next_buddy = track_row.get("next_buddy")
        if isinstance(current_buddy, str) and current_buddy == active_buddy:
            track_role = "current_buddy"
        elif isinstance(next_buddy, str) and next_buddy == active_buddy:
            track_role = "next_buddy"
        else:
            track_tasks = track_context.get("tasks") if isinstance(track_context, dict) else None
            active_participant = False
            if isinstance(track_tasks, list):
                for row in track_tasks:
                    if isinstance(row, dict) and row.get("buddy") == active_buddy:
                        active_participant = True
                        break
            track_role = "participant" if active_participant else "observer"
    else:
        track_role = "missing" if has_track_binding else "none"

    handoffs = track_context.get("recent_handoffs") if isinstance(track_context, dict) else None
    latest_handoff_to_active_buddy = False
    if isinstance(handoffs, list) and handoffs:
        first = handoffs[0]
        if isinstance(first, dict) and first.get("next_buddy") == active_buddy:
            latest_handoff_to_active_buddy = True

    task_artifacts = task_context.get("artifacts") if isinstance(task_context, dict) else None
    has_task_artifacts = isinstance(task_artifacts, list) and len(task_artifacts) > 0
    has_track_tasks = isinstance(track_context, dict) and isinstance(track_context.get("tasks"), list) and bool(track_context["tasks"])
    has_track_handoffs = isinstance(handoffs, list) and bool(handoffs)

    requirements = tool_requirements if isinstance(tool_requirements, dict) else {}
    evidence_readiness = {
        "browser_cockpit": requirements.get("browser_cockpit"),
        "market_research_evidence": requirements.get("market_research_evidence"),
        "ordinary_web_fallback": requirements.get("ordinary_web_fallback"),
    }

    safe_read_affordances = [
        {
            "id": "summarize_current_context",
            "tool": "context",
            "action": "summarize",
            "mutates": "none",
            "reason": "Get compact decision context without mutation.",
            "source_refs": ["runtime_context.operation_semantics['context.summarize']"],
        },
        {
            "id": "inspect_current_context",
            "tool": "context",
            "action": "get",
            "mutates": "none",
            "reason": "Inspect full current context sections.",
            "source_refs": ["runtime_context.operation_semantics['context.get']"],
        },
        {
            "id": "inspect_context_sources",
            "tool": "context",
            "action": "list_sources",
            "mutates": "none",
            "reason": "Inspect context source descriptors.",
            "source_refs": ["runtime_context.operation_semantics['context.list_sources']"],
        },
        {
            "id": "inspect_candidate_tracks",
            "tool": "track",
            "action": "list",
            "mutates": "none",
            "reason": "Discover readable candidate tracks for continuation context.",
            "source_refs": ["runtime_context.operation_semantics['track.list']"],
        },
        {
            "id": "inspect_track_details",
            "tool": "track",
            "action": "get",
            "mutates": "none",
            "reason": "Read one candidate track context summary.",
            "source_refs": ["runtime_context.operation_semantics['track.get']"],
        },
    ]

    return {
        "binding_state": {
            "state": binding_state,
            "current_task_id": binding_task_id,
            "current_track_id": binding_track_id,
            "enum_values": [
                "unbound",
                "bound_task_only",
                "bound_track_only",
                "bound_task_and_track",
                "stale",
            ],
        },
        "active_buddy_relation": {
            "task_role": task_role,
            "track_role": track_role,
            "latest_handoff_to_active_buddy": latest_handoff_to_active_buddy,
            "task_role_enum_values": ["owner", "foreign", "none", "missing"],
            "track_role_enum_values": [
                "current_buddy",
                "next_buddy",
                "participant",
                "observer",
                "none",
                "missing",
            ],
        },
        "context_readiness": {
            "has_task": isinstance(task_row, dict),
            "has_task_artifacts": has_task_artifacts,
            "has_track": isinstance(track_row, dict),
            "has_track_tasks": has_track_tasks,
            "has_track_handoffs": has_track_handoffs,
        },
        "evidence_readiness": evidence_readiness,
        "safe_read_affordances": safe_read_affordances,
    }


def build_task_context(task: dict[str, Any] | None) -> dict[str, Any]:
    if not task:
        return {
            "task": None,
            "artifacts": [],
            "recent_runs": [],
        }

    artifact_map = {artifact["id"]: artifact for artifact in env_store.list_artifacts()}
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
        "recent_runs": scan_task_recent_runs(task["id"], limit=3),
    }


def build_track_context(track_id: str | None) -> dict[str, Any] | None:
    if not track_id:
        return None
    track = env_store.get_track(track_id)
    if track is None:
        return None

    rows: list[dict[str, Any]] = []
    for task_id in track.get("task_ids", []):
        task = env_store.get_task(task_id)
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
                artifact = env_store.get_artifact(artifact_id)
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
        "recent_handoffs": scan_track_recent_handoffs(track["id"], limit=5),
    }


def enrich_task_context_with_track_artifacts(
    *,
    task_context: dict[str, Any],
    track_context: dict[str, Any] | None,
) -> dict[str, Any]:
    artifacts = task_context.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        return task_context
    if not isinstance(track_context, dict):
        return task_context
    tasks = track_context.get("tasks")
    if not isinstance(tasks, list):
        return task_context

    discovered: dict[str, dict[str, Any]] = {}
    for task_row in tasks:
        if not isinstance(task_row, dict):
            continue
        current_artifacts = task_row.get("current_artifacts")
        if not isinstance(current_artifacts, dict):
            continue
        for artifact in current_artifacts.values():
            if not isinstance(artifact, dict):
                continue
            artifact_id = artifact.get("id")
            if not isinstance(artifact_id, str) or not artifact_id:
                continue
            discovered[artifact_id] = artifact

    if not discovered:
        return task_context
    rows = list(discovered.values())
    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("id") or "")), reverse=True)
    enriched = dict(task_context)
    enriched["artifacts"] = rows[:5]
    return enriched


def scan_track_recent_handoffs(track_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
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


def scan_track_handoff_records(track_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    list_handoffs = getattr(env_store, "list_handoffs", None)
    if not callable(list_handoffs):
        return rows
    for row in list_handoffs():
        if not isinstance(row, dict):
            continue
        if row.get("track_id") != track_id:
            continue
        rows.append(
            {
                "handoff_id": row.get("id"),
                "track_id": row.get("track_id"),
                "source_buddy": row.get("source_buddy"),
                "target_buddy": row.get("target_buddy"),
                "source_task_id": row.get("source_task_id"),
                "source_run_id": row.get("source_run_id"),
                "artifact_ids": row.get("artifact_ids", []),
                "status": row.get("status"),
                "timestamp": row.get("updated_at") or row.get("created_at"),
            }
        )
    rows.sort(key=lambda row: (str(row.get("timestamp") or ""), str(row.get("handoff_id") or "")), reverse=True)
    return rows[:limit]


def scan_task_recent_runs(task_id: str, *, limit: int = 3) -> list[dict[str, Any]]:
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
        if payload.get("task_id") != task_id:
            continue
        run_id = payload.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            run_id = path.stem
        rows.append(
            {
                "run_id": run_id,
                "buddy_id": payload.get("buddy_id"),
                "execution_summary": payload.get("execution_summary"),
                "timestamp": payload.get("timestamp"),
            }
        )
    rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("run_id") or ""), reverse=True)
    return rows[:limit]


def summarize_current_context(
    *,
    task_context: dict[str, Any] | None,
    track_context: dict[str, Any] | None,
) -> dict[str, Any]:
    task_payload = task_context.get("task") if isinstance(task_context, dict) else None
    if isinstance(task_payload, dict):
        summarized_task: dict[str, Any] | None = {
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
    if isinstance(track_payload, dict):
        summarized_track: dict[str, Any] | None = {
            "id": track_payload.get("id"),
            "title": track_payload.get("title"),
            "status": track_payload.get("status"),
            "current_buddy": track_payload.get("current_buddy"),
            "next_buddy": track_payload.get("next_buddy"),
            "summary": track_payload.get("summary", ""),
        }
    else:
        summarized_track = None

    summarized_artifacts: list[dict[str, Any]] = []
    task_artifacts = task_context.get("artifacts") if isinstance(task_context, dict) else None
    if isinstance(task_artifacts, list):
        for artifact in task_artifacts:
            if isinstance(artifact, dict):
                summarized_artifacts.append(_summarize_artifact(artifact))
    if not summarized_artifacts and isinstance(track_context, dict):
        track_tasks = track_context.get("tasks")
        if isinstance(track_tasks, list):
            discovered: dict[str, dict[str, Any]] = {}
            for row in track_tasks:
                if not isinstance(row, dict):
                    continue
                current_artifacts = row.get("current_artifacts")
                if not isinstance(current_artifacts, dict):
                    continue
                for artifact in current_artifacts.values():
                    if not isinstance(artifact, dict):
                        continue
                    artifact_id = artifact.get("id")
                    if isinstance(artifact_id, str) and artifact_id:
                        discovered[artifact_id] = artifact
            fallback_rows = list(discovered.values())
            fallback_rows.sort(
                key=lambda row: (str(row.get("updated_at") or ""), str(row.get("id") or "")),
                reverse=True,
            )
            for artifact in fallback_rows[:5]:
                summarized_artifacts.append(_summarize_artifact(artifact))

    summarized_handoffs: list[dict[str, Any]] = []
    handoff_rows = track_context.get("recent_handoffs") if isinstance(track_context, dict) else None
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
        "task": summarized_task,
        "track": summarized_track,
        "artifacts": summarized_artifacts,
        "recent_handoffs": summarized_handoffs,
    }


def _tool_requirements(active_buddy: str) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    profile = env_profiles.require_env_profile(active_buddy, repo_root=repo_root)
    tool_capability = profile.get("tool_capability")
    if not isinstance(tool_capability, dict):
        return {}
    return {
        "browser_cockpit": tool_capability.get("browser_cockpit"),
        "market_research_evidence": tool_capability.get("market_research_evidence"),
        "ordinary_web_fallback": tool_capability.get("ordinary_web_fallback"),
    }


def current_context_sections(context: ContextServiceContext) -> dict[str, Any]:
    binding = bindings.current_binding(
        {
            "active_buddy": context["active_buddy"],
            "instance_id": context["instance_id"],
            "instance_json": context["instance_json"],
            "instance_payload": context["instance_payload"],
            "manifest": context["manifest"],
        }
    )
    task_id = binding.get("current_task_id")
    task = env_store.get_task(task_id.strip()) if isinstance(task_id, str) and task_id.strip() else None
    task_context = build_task_context(task)
    track_id = binding.get("current_track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        track_id = task.get("track_id") if isinstance(task, dict) else None
    track_context = build_track_context(track_id if isinstance(track_id, str) else None)
    task_context = enrich_task_context_with_track_artifacts(task_context=task_context, track_context=track_context)
    tool_requirements = _tool_requirements(context["active_buddy"])
    decision_surface = build_decision_surface(
        active_buddy=context["active_buddy"],
        current_binding=binding,
        task_context=task_context,
        track_context=track_context,
        tool_requirements=tool_requirements,
    )
    return {
        "current_binding": binding,
        "task_context": task_context,
        "track_context": track_context,
        "decision_surface": decision_surface,
        "context_sources_desc": context_sources_desc(),
        "current_context_summary": summarize_current_context(
            task_context=task_context,
            track_context=track_context,
        ),
    }


def _validate_context_payload(
    *,
    action: str,
    args_context: dict[str, Any],
    context: ContextServiceContext,
) -> dict[str, Any] | None:
    if args_context.get("ok") is not True:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_CONTEXT_SCOPE",
            message="context must be a successful prepare payload",
            permission_boundary="prepare.context_revision",
        )
    if args_context.get("instance_id") != context["instance_id"]:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="context instance_id does not match active instance",
            permission_boundary="active-instance",
        )
    if args_context.get("active_buddy") != context["active_buddy"]:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="context active_buddy does not match active buddy",
            permission_boundary="active-buddy",
        )

    import turn_runtime as rt
    try:
        validated = rt._validate_prepared_run_context(args_context)
    except rt.RuntimeFeedbackError as exc:
        return _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code=exc.code,
            message=exc.message,
            permission_boundary=str(exc.details.get("permission_boundary", "prepare.context_revision")),
            human_summary="Prepared context validation failed for the active runtime state.",
            why_blocked=exc.message,
            retryable=True,
            retry_guidance="Rerun prepare and retry with the refreshed context payload.",
            allowed_next_actions=list(exc.details.get("allowed_next_actions", [])),
        )
    except (ValueError, TypeError) as exc:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_CONTEXT_SCOPE",
            message=str(exc),
            permission_boundary="prepare.context_revision",
        )
    task_id = validated.get("task_id")
    track_id = validated.get("track_id")

    bound_task_id = context["instance_payload"].get("current_task_id")
    if isinstance(bound_task_id, str) and bound_task_id.strip() and bound_task_id.strip() != task_id:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="context current_task_id does not match active instance binding",
            permission_boundary="active-instance",
        )

    bound_track_id = context["instance_payload"].get("current_track_id")
    if isinstance(bound_track_id, str) and bound_track_id.strip():
        if track_id != bound_track_id.strip():
            return _context_boundary_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="context current_track_id does not match active instance binding",
                permission_boundary="active-instance",
            )

    if isinstance(task_id, str):
        task = env_store.get_task(task_id)
    else:
        task = None
    if isinstance(task_id, str) and task is None:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_CONTEXT_TASK_NOT_FOUND",
            message=f"context task not found: {task_id}",
            permission_boundary="prepare.context_revision",
        )
    if isinstance(track_id, str) and env_store.get_track(track_id) is None:
        return _context_boundary_error(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_CONTEXT_TRACK_NOT_FOUND",
            message=f"context track not found: {track_id}",
            permission_boundary="prepare.context_revision",
        )
    return None


def get_context(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.get"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_GET_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    supplied_context = args.get("context")
    if supplied_context is not None:
        if not isinstance(supplied_context, dict):
            return _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="context must be an object when provided",
            )
        validation_error = _validate_context_payload(
            action=action,
            args_context=supplied_context,
            context=context,
        )
        if validation_error is not None:
            return validation_error

    sections = current_context_sections(context)
    response_sections = dict(sections)
    response_sections.pop("context_sources_desc", None)
    return tool_responses.success(
        tool="context",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary="Returned active instance context sections and decision surface without mutating state.",
        state_changed=False,
        durability="none",
        read_scope="Active runtime context snapshot sections; this is not a direct foreign artifact full-body API.",
        allowed_next_actions=[
            "Use context.summarize for compact scan-friendly context.",
            "Use track.get to inspect artifact ids and relation context.",
            "Use artifact.get --artifact-id <artifact-id> for full-body reads.",
            "Use track.join --track-id <track-id> when relation is missing.",
        ],
        allowed_next_action_options=[
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_current_context",
                reason="Get compact decision context before state mutation.",
            ),
            tool_responses.next_action_option(
                tool="context",
                action="list_sources",
                option_id="inspect_context_sources",
                reason="Inspect structured source descriptors for context sections.",
            ),
        ],
        extra=response_sections,
    )


def summarize_context(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.summarize"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_IDENTITY_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    sections = current_context_sections(context)
    decision_surface = sections["decision_surface"]
    candidate_tracks: list[dict[str, Any]] = []
    binding_state = decision_surface.get("binding_state") if isinstance(decision_surface, dict) else None
    state = binding_state.get("state") if isinstance(binding_state, dict) else None
    relation = decision_surface.get("active_buddy_relation") if isinstance(decision_surface, dict) else None
    latest_handoff = relation.get("latest_handoff_to_active_buddy") if isinstance(relation, dict) else False
    if state in {"unbound", "bound_task_only"} or (
        state in {"bound_track_only", "bound_task_and_track"} and latest_handoff is not True
    ):
        candidate_tracks = _build_candidate_track_rows(active_buddy=context["active_buddy"])

    return tool_responses.success(
        tool="context",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary="Returned compact context summary and candidate tracks without mutating state.",
        state_changed=False,
        durability="none",
        read_scope="Current binding, context summary, and decision-surface projection only.",
        allowed_next_actions=[
            "Use track.get --track-id <track-id> to inspect source artifact ids.",
            "Use artifact.get --artifact-id <artifact-id> for direct full-body reads.",
            "Use track.join --track-id <track-id> when artifact.get reports missing relation.",
        ],
        allowed_next_action_options=[
            tool_responses.next_action_option(
                tool="track",
                action="get",
                option_id="inspect_track_for_source_ids",
                reason="Inspect one track summary and current artifact ids for direct intake.",
            ),
            tool_responses.next_action_option(
                tool="track",
                action="list",
                option_id="inspect_candidate_tracks",
                reason="Inspect candidate tracks for cross-buddy continuation context.",
            ),
        ],
        extra={
            "current_binding": sections["current_binding"],
            "current_context_summary": sections["current_context_summary"],
            "decision_surface": decision_surface,
            "candidate_tracks": candidate_tracks,
        },
    )


def list_sources(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.list_sources"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_IDENTITY_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    return tool_responses.success(
        tool="context",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary="Listed context source descriptors for active runtime sections without changing state.",
        state_changed=False,
        durability="none",
        read_scope="Context section descriptor metadata only.",
        allowed_next_actions=[
            "Use context.get to read full current context.",
            "Use context.summarize for compact context.",
        ],
        allowed_next_action_options=[
            tool_responses.next_action_option(
                tool="context",
                action="get",
                option_id="read_full_current_context",
                reason="Read full current task and track context.",
            ),
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_current_context",
                reason="Read compact current context summary for quick orientation.",
            ),
        ],
        extra={"sources": context_sources_desc()},
    )
