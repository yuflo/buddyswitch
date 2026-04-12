#!/usr/bin/env python3
"""BuddySwitch runtime: resolve switch context and persist structured results."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from env_manifest import (
    ADVISORY_RUNTIME_METADATA_POLICY,
    DEFAULT_MANIFEST,
    ManifestError,
    buddy_authority_profile,
    buddy_skill_docs,
    load_manifest,
    require_buddy,
)
from env_store import (
    ROOT,
    advance_track,
    attach_artifact,
    create_artifact,
    create_track,
    detach_artifact,
    get_track,
    list_artifacts,
    list_tracks,
    now_iso,
    run_content_path,
    save_run_content,
    slugify,
    update_track,
)
from output_schema import OutputSchemaError, load_output_schema, validate_output_payload
from parse_switch import EXAMPLE, SYNTAX, parse_switch


TRACK_ACTIONS = ("create", "read", "list", "update", "advance", "attach", "detach", "archive")
STATUS_VALUES = ("active", "blocked", "done", "archived")
LEGACY_OUTPUT_ERROR = (
    "Derived markdown outputs are retired. Persist BuddySwitch state to artifact objects and run audits only."
)


def runtime_error(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "expected_syntax": SYNTAX,
            "example": EXAMPLE,
        },
    }
    if extra:
        payload["error"].update(extra)
    return payload


def _extract_output_path(task: str) -> str | None:
    match = re.search(r"(artifacts/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\.md)", task)
    return match.group(1) if match else None


def _extract_summary_path(task: str) -> str | None:
    match = re.search(r"(runs/summaries/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\.md)", task)
    return match.group(1) if match else None


def _extract_track_id(task: str) -> str | None:
    candidates: list[tuple[int, str]] = []
    patterns = (
        r"(?<![a-z0-9-])track\s+([a-z0-9][a-z0-9-]{1,80})\b",
        r"(?<![a-z0-9-])([a-z0-9][a-z0-9-]{1,80})\s+track\b(?!-)",
        r"继续\s*([a-z0-9][a-z0-9-]{1,80})\s*track",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, task, flags=re.IGNORECASE):
            candidates.append((match.start(1), match.group(1).lower()))

    if not candidates:
        return None

    stop_words = {
        "create",
        "read",
        "list",
        "update",
        "advance",
        "attach",
        "detach",
        "archive",
        "continue",
        "show",
    }
    filtered = [item for item in candidates if item[1] not in stop_words]
    if not filtered:
        return None
    filtered.sort(key=lambda item: item[0])

    prefixed = [item for item in filtered if item[1].startswith("track-")]
    if prefixed:
        return prefixed[0][1]

    structured = [item for item in filtered if "-" in item[1] or any(ch.isdigit() for ch in item[1])]
    if structured:
        return structured[0][1]

    return filtered[0][1]


def _extract_artifact_id(task: str) -> str | None:
    match = re.search(r"\b(art-[a-z0-9][a-z0-9-]{2,120})\b", task, flags=re.IGNORECASE)
    return match.group(1).lower() if match else None


def _extract_action(task: str) -> str | None:
    lowered = task.lower()
    action_keywords = (
        ("archive", ("archive", "archived", "归档")),
        ("detach", ("detach", "解除关联", "unattach")),
        ("attach", ("attach", "关联", "link")),
        ("advance", ("advance", "推进", "handoff", "next buddy")),
        ("update", ("update", "更新")),
        ("list", ("list", "列表", "all tracks")),
        ("read", ("read", "show", "查看")),
        ("create", ("create", "new track", "创建")),
    )

    def _keyword_hit(text: str, keyword: str) -> bool:
        token = keyword.lower()
        if re.search(r"[A-Za-z0-9]", token):
            if " " in token:
                return token in text
            pattern = rf"(?<![a-z0-9-]){re.escape(token)}(?![a-z0-9-])"
            return re.search(pattern, text) is not None
        return token in text

    for action, keys in action_keywords:
        if any(_keyword_hit(lowered, key) for key in keys):
            return action
    return None


def _extract_status(task: str) -> str | None:
    lowered = task.lower()
    for status in STATUS_VALUES:
        if re.search(rf"\b{status}\b", lowered):
            return status
    if "完成" in task:
        return "done"
    if "阻塞" in task:
        return "blocked"
    if "归档" in task:
        return "archived"
    return None


def _extract_buddy(task: str, valid: set[str], key: str) -> str | None:
    pattern = rf"{key}\s*[:=]?\s*([a-z][a-z0-9-]*)"
    match = re.search(pattern, task, flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).lower()
    return value if value in valid else None


def _extract_summary_text(task: str) -> str | None:
    match = re.search(r"summary\s*:\s*(.+)$", task, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_task_hints(task: str, valid_buddies: set[str]) -> dict[str, Any]:
    output_path = _extract_output_path(task)
    summary_path = _extract_summary_path(task)
    if output_path:
        raise ValueError(f"{LEGACY_OUTPUT_ERROR} Rejecting requested output path '{output_path}'.")
    if summary_path:
        raise ValueError(f"{LEGACY_OUTPUT_ERROR} Rejecting requested summary path '{summary_path}'.")
    return {
        "explicit_track_id": _extract_track_id(task),
        "explicit_artifact_id": _extract_artifact_id(task),
        "action_hint": _extract_action(task),
        "status_hint": _extract_status(task),
        "current_buddy_hint": _extract_buddy(task, valid_buddies, "current_buddy"),
        "next_buddy_hint": _extract_buddy(task, valid_buddies, "next_buddy"),
        "summary_hint": _extract_summary_text(task),
    }


def _resolve_track_context(task: str, track_mode: str, *, allow_missing_explicit: bool = False) -> dict[str, Any]:
    explicit_track_id = _extract_track_id(task)
    active_tracks = [track for track in list_tracks() if track.get("status") == "active"]
    active_ids = [track["id"] for track in active_tracks]

    resolved_track_id = None
    reason = "none"

    if explicit_track_id:
        if get_track(explicit_track_id) is None:
            if allow_missing_explicit:
                reason = "explicit_not_found_allowed"
            else:
                raise ValueError(f"Referenced track '{explicit_track_id}' not found.")
        else:
            resolved_track_id = explicit_track_id
            reason = "explicit"
    elif track_mode != "forbidden" and len(active_tracks) == 1:
        resolved_track_id = active_tracks[0]["id"]
        reason = "single_active"
    elif len(active_tracks) > 1:
        reason = "ambiguous_active"

    if track_mode == "forbidden":
        if explicit_track_id:
            raise ValueError("This skill forbids track linkage, but task references a track.")
        resolved_track_id = None
        reason = "forbidden"

    if track_mode == "required":
        if resolved_track_id is None:
            if len(active_tracks) > 1:
                raise ValueError(
                    "Track required but multiple active tracks found. Specify '<track-id> track' in task."
                )
            raise ValueError(
                "Track required but no active track found. Use `switch pm: create <track-id> track ...` first."
            )

    if track_mode == "optional" and explicit_track_id is None and len(active_tracks) > 1:
        resolved_track_id = None
        reason = "optional_untracked_multiple_active"

    return {
        "track_mode": track_mode,
        "track_id": resolved_track_id,
        "reason": reason,
        "explicit_track_id": explicit_track_id,
        "active_track_ids": active_ids,
    }


def _next_unique(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    index = 2
    while True:
        candidate = f"{base}-{index}"
        if candidate not in existing:
            return candidate
        index += 1


def _derive_artifact_title(buddy: str, skill_id: str, task: str) -> str:
    snippet = " ".join(task.split()[:8]).strip()
    if snippet:
        return f"{buddy.upper()} {skill_id} - {snippet}"
    return f"{buddy.upper()} {skill_id}"


def _derive_artifact_defaults(
    buddy: str,
    skill: dict[str, Any],
    task: str,
    track_id: str | None,
    task_hints: dict[str, Any],
) -> dict[str, Any]:
    existing_ids = {artifact["id"] for artifact in list_artifacts()}
    artifact_kind = skill["runtime"]["default_artifact_kind"]
    base = f"art-{slugify((track_id or buddy) + '-' + artifact_kind)}"
    artifact_id = _next_unique(base, existing_ids)
    title = _derive_artifact_title(buddy, skill["id"], task)
    return {
        "id": artifact_id,
        "title": title,
        "summary": result_summary_hint(task_hints),
    }


def result_summary_hint(task_hints: dict[str, Any]) -> str:
    summary_hint = task_hints.get("summary_hint")
    return summary_hint.strip() if isinstance(summary_hint, str) else ""


def _build_skill_card(skill: dict[str, Any]) -> dict[str, Any]:
    runtime = skill["runtime"]
    guidance = runtime.get("guidance", {})
    required_tools = runtime.get("required_tools", [])
    required_env = runtime.get("required_env", [])
    return {
        "id": skill["id"],
        "path": skill["path"],
        "description": skill["description"],
        "objects": skill["objects"],
        "track_mode": runtime["track_mode"],
        "default_artifact_kind": runtime["default_artifact_kind"],
        "auto_summary": runtime["auto_summary"],
        "output_schema": runtime["output_schema"],
        "version": runtime.get("version"),
        "side_effect_level": runtime.get("side_effect_level"),
        "required_tools": required_tools,
        "required_env": required_env,
        "runtime_requirements": {
            "required_tools": required_tools,
            "required_env": required_env,
            "policy": ADVISORY_RUNTIME_METADATA_POLICY,
            "note": "These fields inform the host session and do not reject resolve candidates.",
        },
        "produces": runtime.get("produces", []),
        "consumes": runtime.get("consumes", []),
        "purpose": guidance.get("purpose", []),
        "use_when": guidance.get("use_when", []),
        "do_not_use_when": guidance.get("do_not_use_when", []),
        "inputs": guidance.get("inputs", []),
        "outputs": guidance.get("outputs", []),
        "verification": guidance.get("verification", []),
        "examples": guidance.get("examples", []),
        "counterexamples": guidance.get("counterexamples", []),
        "gotchas": guidance.get("gotchas", []),
    }


def _build_run_instructions(implicit_skill_id: str | None) -> dict[str, Any]:
    if implicit_skill_id:
        first_action = f"Use implicit_skill_id '{implicit_skill_id}' for this run."
    else:
        first_action = "Choose one skill_id from eligible_skills."

    return {
        "host": "codex",
        "selection_rule": "Choose exactly one skill_id from eligible_skills. Multi-skill buddies are never auto-selected by the runtime.",
        "execution_rule": "The host Codex session runs the selected skill workflow and produces a structured result that matches required_output_schema_by_skill[skill_id].",
        "persistence_rule": "Call persist with the resolved payload, selected skill_id, and structured result when the run should become BuddySwitch state.",
        "resolve_notes": [
            "resolve parses the invocation, derives skill candidates and defaults, and does not write BuddySwitch state."
        ],
        "next_actions": [
            first_action,
            "Read the selected buddyswitch/skills/<buddy>/<skill>/SKILL.md in the current Codex CLI session.",
            "Produce a structured result payload matching required_output_schema_by_skill[skill_id].",
            "Call persist when you want BuddySwitch to write state, canonical artifact content, and run audit metadata.",
        ],
        "persist_notes": [
            "Artifact skills write artifact objects under buddyswitch/objects/ and run audits under buddyswitch/content/runs/.",
            "track-manager writes the requested track or attachment state plus the run audit.",
        ],
    }


def _track_object_path(track_id: str) -> str:
    return f"buddyswitch/objects/tracks/{track_id}.json"


def _artifact_object_path(artifact_id: str) -> str:
    return f"buddyswitch/objects/artifacts/{artifact_id}.json"


def _build_track_manager_writes(
    *,
    action: str,
    track_payload: dict[str, Any],
    run_content_path_value: str,
) -> list[str]:
    writes = [run_content_path_value]
    if action in {"create", "update", "advance", "archive", "attach", "detach"}:
        track = track_payload.get("track")
        if isinstance(track, dict) and track.get("id"):
            writes.insert(0, _track_object_path(track["id"]))
    if action in {"attach", "detach"}:
        artifact = track_payload.get("artifact")
        if isinstance(artifact, dict) and artifact.get("id"):
            writes.insert(1, _artifact_object_path(artifact["id"]))
    return writes


def _build_artifact_writes(
    *,
    artifact: dict[str, Any],
    run_content_path_value: str,
) -> list[str]:
    writes = [
        _artifact_object_path(artifact["id"]),
        run_content_path_value,
    ]
    if artifact.get("track_id"):
        writes.insert(1, _track_object_path(artifact["track_id"]))
    return writes


def _receipt_paths(
    *,
    run_content_path_value: str,
    artifact_id: str | None = None,
    track_id: str | None = None,
) -> dict[str, str | None]:
    paths: dict[str, str | None] = {"run": run_content_path_value}
    if artifact_id:
        paths["artifact"] = _artifact_object_path(artifact_id)
    if track_id:
        paths["track"] = _track_object_path(track_id)
    return paths


def resolve_switch(text: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    parsed = parse_switch(text, manifest_path=manifest_path)
    if not parsed.get("ok"):
        return parsed

    buddy_id = parsed["buddy"]
    task = parsed["task"]
    buddy = require_buddy(manifest, buddy_id)
    valid_buddies = {row["id"] for row in manifest["buddies"]}
    task_hints = _extract_task_hints(task, valid_buddies)

    eligible_skill_ids: list[str] = []
    skill_cards: list[dict[str, Any]] = []
    rejected_skills: list[dict[str, str]] = []
    track_context_by_skill: dict[str, Any] = {}
    required_output_schema_by_skill: dict[str, str] = {}

    for skill in buddy_skill_docs(manifest, buddy_id):
        reasons: list[str] = []
        allow_missing_explicit = bool(skill["id"] == "track-manager" and task_hints["action_hint"] == "create")
        try:
            track_context = _resolve_track_context(
                task,
                skill["runtime"]["track_mode"],
                allow_missing_explicit=allow_missing_explicit,
            )
        except ValueError as exc:
            track_context = {
                "track_mode": skill["runtime"]["track_mode"],
                "track_id": None,
                "reason": "ineligible",
                "explicit_track_id": task_hints["explicit_track_id"],
                "active_track_ids": [track["id"] for track in list_tracks() if track.get("status") == "active"],
                "error": str(exc),
            }
            reasons.append(str(exc))

        track_context_by_skill[skill["id"]] = track_context
        required_output_schema_by_skill[skill["id"]] = skill["runtime"]["output_schema"]

        if reasons:
            rejected_skills.append({"id": skill["id"], "reason": "; ".join(reasons)})
            continue

        eligible_skill_ids.append(skill["id"])
        skill_cards.append(_build_skill_card(skill))

    if not eligible_skill_ids:
        reasons = ", ".join(f"{item['id']}: {item['reason']}" for item in rejected_skills) or "none"
        raise ValueError(f"No eligible skills remain for buddy '{buddy_id}'. Rejections: {reasons}")

    implicit_skill_id = eligible_skill_ids[0] if len(eligible_skill_ids) == 1 else None
    return {
        "ok": True,
        "intent": parsed.get("intent", "switch"),
        "raw_text": parsed.get("raw_text", text),
        "normalized_text": parsed.get("normalized_text", f"switch {buddy_id}: {task}"),
        "invocation": parsed.get(
            "invocation",
            {
                "intent": "switch",
                "buddy": buddy_id,
                "task": task,
                "raw_text": text,
                "normalized_text": f"switch {buddy_id}: {task}",
            },
        ),
        "switch": {"buddy": buddy_id, "task": task},
        "profile": {
            "buddy": {"id": buddy["id"], "label": buddy["label"], "scope": buddy["scope"]},
            "permissions": buddy.get("permissions", []),
            "authority": buddy_authority_profile(manifest, buddy_id),
        },
        "task_hints": task_hints,
        "eligible_skills": eligible_skill_ids,
        "skill_cards": skill_cards,
        "rejected_skills": rejected_skills,
        "implicit_skill_id": implicit_skill_id,
        "track_context_by_skill": track_context_by_skill,
        "required_output_schema_by_skill": required_output_schema_by_skill,
        "run_instructions": _build_run_instructions(implicit_skill_id),
    }


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


def _pick_skill_id(resolved: dict[str, Any], requested_skill_id: str | None) -> str:
    if requested_skill_id:
        return requested_skill_id
    implicit_skill_id = resolved.get("implicit_skill_id")
    if isinstance(implicit_skill_id, str) and implicit_skill_id:
        return implicit_skill_id
    raise ValueError("skill_id is required for multi-skill buddies. Choose one from eligible_skills first.")


def _strip_run_fields(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_summary": result.get("execution_summary"),
        "working_notes": result.get("working_notes") or [],
        "deliverables_or_changed_files": result.get("deliverables_or_changed_files") or [],
        "suggested_next_switch": result.get("suggested_next_switch"),
    }


def _build_run_audit(
    *,
    resolved: dict[str, Any],
    skill_id: str,
    run_id: str,
    paths: dict[str, str | None],
    writes: list[str],
    result: dict[str, Any],
    artifact_id: str | None = None,
    track_id: str | None = None,
    track_action: str | None = None,
) -> dict[str, Any]:
    audit = {
        "run_id": run_id,
        "timestamp": now_iso(),
        "switch": resolved["switch"],
        "skill_id": skill_id,
        "artifact_id": artifact_id,
        "track_id": track_id,
        "track_action": track_action,
        "paths": paths,
        "writes": writes,
    }
    audit.update(_strip_run_fields(result))
    return audit


def _validate_buddy_value(value: str | None, field: str, valid_buddies: set[str]) -> str | None:
    if value is None:
        return None
    if value not in valid_buddies:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(valid_buddies))}")
    return value


def _ensure_track_target(track_id: str | None) -> str:
    if not track_id:
        raise ValueError("Track operation requires a track id.")
    if get_track(track_id) is None:
        raise ValueError(f"Track not found: {track_id}")
    return track_id


def _derive_create_track_id(task: str) -> str:
    explicit = _extract_track_id(task)
    if explicit:
        candidate = explicit
    else:
        candidate = slugify(task)
        candidate = candidate.replace("switch", "").replace("track", "").strip("-")
        candidate = candidate or "track"
    candidate = candidate if candidate.startswith("track") else f"track-{candidate}"
    existing = {track["id"] for track in list_tracks()}
    return _next_unique(candidate, existing)


def _persist_track_manager(
    resolved: dict[str, Any],
    result: dict[str, Any],
    *,
    manifest: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    op = dict(result.get("track_operation") or {})
    action = str(op.get("action") or "").lower()
    if action not in TRACK_ACTIONS:
        raise ValueError("track_operation.action must be one of create/read/list/update/advance/attach/detach/archive")

    task = resolved["switch"]["task"]
    task_hints = resolved.get("task_hints", {})
    valid_buddies = {row["id"] for row in manifest["buddies"]}

    track_id = op.get("track_id") or task_hints.get("explicit_track_id")
    artifact_id = op.get("artifact_id") or task_hints.get("explicit_artifact_id")
    track_payload: dict[str, Any]

    if action == "list":
        track_payload = {"action": "list", "tracks": list_tracks()}
    elif action == "create":
        explicit_track = op.get("track_id")
        if explicit_track:
            new_id = _next_unique(explicit_track, {track["id"] for track in list_tracks()})
        else:
            new_id = _derive_create_track_id(task)
        title = op.get("title") or new_id.replace("-", " ").title()
        current_buddy = _validate_buddy_value(op.get("current_buddy") or "pm", "current_buddy", valid_buddies) or "pm"
        next_buddy = _validate_buddy_value(op.get("next_buddy"), "next_buddy", valid_buddies)
        status = op.get("status") or "active"
        if status not in STATUS_VALUES:
            raise ValueError(f"track_operation.status must be one of {', '.join(STATUS_VALUES)}")
        track = create_track(
            new_id,
            title,
            status=status,
            current_buddy=current_buddy,
            next_buddy=next_buddy,
            summary=op.get("summary") or "",
        )
        track_payload = {"action": "create", "track": track}
    else:
        target_track_id = _ensure_track_target(track_id)
        if action == "read":
            track = get_track(target_track_id)
            assert track is not None
            track_payload = {"action": "read", "track": track}
        elif action in {"update", "advance"}:
            patch: dict[str, Any] = {}
            status = op.get("status")
            if status is not None:
                if status not in STATUS_VALUES:
                    raise ValueError(f"track_operation.status must be one of {', '.join(STATUS_VALUES)}")
                patch["status"] = status
            current_buddy = _validate_buddy_value(op.get("current_buddy"), "current_buddy", valid_buddies)
            if current_buddy is not None:
                patch["current_buddy"] = current_buddy
            if "next_buddy" in op:
                patch["next_buddy"] = _validate_buddy_value(op.get("next_buddy"), "next_buddy", valid_buddies)
            if op.get("summary") is not None:
                patch["summary"] = op.get("summary")
            if not patch:
                raise ValueError("track_operation for update/advance must include at least one mutable field")
            track = advance_track(target_track_id, **patch) if action == "advance" else update_track(target_track_id, patch)
            track_payload = {"action": action, "track": track}
        elif action == "archive":
            track = update_track(target_track_id, {"status": "archived"})
            track_payload = {"action": "archive", "track": track}
        elif action == "attach":
            if not artifact_id:
                raise ValueError("track_operation.artifact_id is required for attach")
            artifact = attach_artifact(target_track_id, artifact_id)
            track_payload = {"action": "attach", "track": get_track(target_track_id), "artifact": artifact}
        elif action == "detach":
            if not artifact_id:
                raise ValueError("track_operation.artifact_id is required for detach")
            artifact = detach_artifact(target_track_id, artifact_id)
            track_payload = {"action": "detach", "track": get_track(target_track_id), "artifact": artifact}
        else:
            raise ValueError(f"Unsupported track action: {action}")

    track = track_payload.get("track")
    persisted_track_id = track.get("id") if isinstance(track, dict) else None
    artifact = track_payload.get("artifact")
    persisted_artifact_id = artifact.get("id") if isinstance(artifact, dict) else None
    run_content_path_value = run_content_path(run_id)
    writes = _build_track_manager_writes(
        action=action,
        track_payload=track_payload,
        run_content_path_value=run_content_path_value,
    )
    paths = _receipt_paths(
        run_content_path_value=run_content_path_value,
        artifact_id=persisted_artifact_id,
        track_id=persisted_track_id,
    )
    save_run_content(
        run_id,
        _build_run_audit(
            resolved=resolved,
            skill_id="track-manager",
            run_id=run_id,
            paths=paths,
            writes=writes,
            result=result,
            artifact_id=persisted_artifact_id,
            track_id=persisted_track_id,
            track_action=action,
        ),
    )
    return {
        "ok": True,
        "switch": resolved["switch"],
        "skill_id": "track-manager",
        "track_action": action,
        "track_id": persisted_track_id,
        "artifact_id": persisted_artifact_id,
        "run_id": run_id,
        "paths": paths,
        "writes": writes,
    }


def _persist_artifact_skill(
    resolved: dict[str, Any],
    skill: dict[str, Any],
    result: dict[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    buddy = resolved["switch"]["buddy"]
    task = resolved["switch"]["task"]
    skill_id = skill["id"]
    track_context = resolved.get("track_context_by_skill", {}).get(skill_id, {})
    task_hints = resolved.get("task_hints", {})
    artifact_defaults = _derive_artifact_defaults(
        buddy,
        skill,
        task,
        track_context.get("track_id"),
        task_hints,
    )

    artifact_id = artifact_defaults["id"]
    artifact_summary = str(result.get("execution_summary") or artifact_defaults["summary"] or "")

    artifact = create_artifact(
        artifact_id=artifact_id,
        title=artifact_defaults["title"],
        buddy=buddy,
        skill_id=skill_id,
        track_id=track_context.get("track_id"),
        summary=artifact_summary,
        content=result["artifact_content"],
        auto_register=True,
    )

    run_content_path_value = run_content_path(run_id)
    writes = _build_artifact_writes(
        artifact=artifact,
        run_content_path_value=run_content_path_value,
    )
    paths = _receipt_paths(
        run_content_path_value=run_content_path_value,
        artifact_id=artifact["id"],
        track_id=artifact.get("track_id"),
    )
    save_run_content(
        run_id,
        _build_run_audit(
            resolved=resolved,
            skill_id=skill_id,
            run_id=run_id,
            paths=paths,
            writes=writes,
            result=result,
            artifact_id=artifact["id"],
            track_id=artifact.get("track_id"),
        ),
    )

    return {
        "ok": True,
        "switch": resolved["switch"],
        "skill_id": skill_id,
        "artifact_id": artifact["id"],
        "track_id": artifact.get("track_id"),
        "run_id": run_id,
        "paths": paths,
        "writes": writes,
    }


def persist_switch(
    resolved: dict[str, Any],
    *,
    skill_id: str | None,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    if not resolved.get("ok"):
        raise ValueError("resolved payload must be successful before persist")

    selected_skill_id = _pick_skill_id(resolved, skill_id)
    eligible_skills = resolved.get("eligible_skills", [])
    if selected_skill_id not in eligible_skills:
        raise ValueError(
            f"skill_id '{selected_skill_id}' is not eligible for this switch. Eligible: {', '.join(eligible_skills)}"
        )

    manifest = load_manifest(manifest_path)
    buddy_id = resolved["switch"]["buddy"]
    buddy = require_buddy(manifest, buddy_id)
    if selected_skill_id not in buddy.get("skills", []):
        raise ValueError(f"skill_id '{selected_skill_id}' is not declared for buddy '{buddy_id}'")

    skill = next(skill for skill in buddy_skill_docs(manifest, buddy_id) if skill["id"] == selected_skill_id)
    schema = load_output_schema(skill["runtime"]["output_schema"])
    errors = validate_output_payload(result, schema)
    if errors:
        raise ValueError("result payload failed schema validation: " + "; ".join(errors))

    run_id = f"run-{uuid.uuid4().hex[:10]}"
    if selected_skill_id == "track-manager":
        return _persist_track_manager(
            resolved,
            result,
            manifest=manifest,
            run_id=run_id,
        )

    return _persist_artifact_skill(resolved, skill, result, run_id=run_id)


def _cmd_resolve(args: argparse.Namespace) -> int:
    try:
        payload = resolve_switch(args.text, manifest_path=args.manifest)
    except (ManifestError, ValueError, OutputSchemaError) as exc:
        payload = runtime_error("E_RUNTIME_RESOLVE", str(exc))
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


def _cmd_persist(args: argparse.Namespace) -> int:
    try:
        if args.resolved == "-" and args.result == "-":
            raise ValueError("resolved and result cannot both read from stdin")
        stdin_text = sys.stdin.read() if args.resolved == "-" or args.result == "-" else None
        resolved = _read_json_input(args.resolved, stdin_text=stdin_text if args.resolved == "-" else None)
        result = _read_json_input(args.result, stdin_text=stdin_text if args.result == "-" else None)
        payload = persist_switch(resolved, skill_id=args.skill_id, result=result, manifest_path=args.manifest)
    except (ManifestError, ValueError, OutputSchemaError, json.JSONDecodeError) as exc:
        payload = runtime_error("E_RUNTIME_PERSIST", str(exc))
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BuddySwitch runtime.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_cmd = subparsers.add_parser("resolve", help="Resolve switch directive into BuddySwitch preflight context.")
    resolve_cmd.add_argument("text", help="switch directive")
    resolve_cmd.set_defaults(func=_cmd_resolve)

    persist_cmd = subparsers.add_parser("persist", help="Persist a structured BuddySwitch run result.")
    persist_cmd.add_argument("--resolved", required=True, help="Resolved JSON payload file, or '-' for stdin")
    persist_cmd.add_argument("--result", required=True, help="Structured result JSON file, or '-' for stdin")
    persist_cmd.add_argument("--skill-id", help="Chosen skill id. Optional only when resolve returned implicit_skill_id.")
    persist_cmd.set_defaults(func=_cmd_persist)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
