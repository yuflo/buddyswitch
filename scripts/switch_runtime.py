#!/usr/bin/env python3
"""BuddySwitch runtime: resolve switch context and persist structured results."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
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
    register_task_to_track,
    run_content_path,
    save_run_content,
    slugify,
    update_track,
)
from output_schema import OutputSchemaError, load_output_schema, validate_output_payload
from parse_switch import EXAMPLE, SYNTAX, parse_switch
from artifact_selection import select_artifacts_for_run


TRACK_ACTIONS = ("create", "read", "list", "update", "advance", "archive")
STATUS_VALUES = ("active", "blocked", "done", "archived")
LEGACY_OUTPUT_ERROR = (
    "Derived markdown outputs are retired. Persist BuddySwitch state to task/artifact objects and run audits only."
)
_LEGACY_OUTPUT_PATTERNS = (
    re.compile(r"(artifacts/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\.md)"),
    re.compile(r"(runs/summaries/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\.md)"),
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


def _derive_task_id(buddy: str, demand: str) -> str:
    existing = {row["id"] for row in list_tasks()}
    tokens = [token for token in slugify(demand).split("-") if token]
    if not tokens:
        tokens = ["task"]
    short_slug = "-".join(token[:10] for token in tokens[:4]).strip("-") or "task"
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


def _derive_artifact_title(buddy: str, skill_id: str, demand: str) -> str:
    snippet = " ".join(demand.split()[:8]).strip()
    if snippet:
        return f"{buddy.upper()} {skill_id} - {snippet}"
    return f"{buddy.upper()} {skill_id}"


def _derive_artifact_id(task_id: str, kind: str) -> str:
    existing = {artifact["id"] for artifact in list_artifacts()}
    base = f"art-{slugify(f'{task_id}-{kind}')}"
    return _next_unique(base, existing)


def _build_reference_switches(
    *,
    buddy_id: str,
    task_id: str,
    track_id: str | None,
    next_buddy: str | None,
) -> dict[str, str]:
    references: dict[str, str] = {
        "continue_current_task": f"switch {buddy_id}({task_id}): <demand>",
    }
    if track_id:
        references["continue_current_task_in_track"] = f"switch {buddy_id}({task_id}) -> {track_id}: <demand>"
        if next_buddy:
            references["handoff_to_next_buddy"] = f"switch {next_buddy} -> {track_id}: <demand>"
    return references


def _pick_recommended_switch(reference_switches: dict[str, str]) -> str:
    for key in ("handoff_to_next_buddy", "continue_current_task_in_track", "continue_current_task"):
        command = reference_switches.get(key)
        if command:
            return command
    return ""


def _build_skill_card(skill: dict[str, Any]) -> dict[str, Any]:
    runtime = skill["runtime"]
    guidance = runtime.get("guidance", {})
    required_tools = runtime.get("required_tools", [])
    required_env = runtime.get("required_env", [])
    output_slot = runtime.get("output_slot")
    input_slots = runtime.get("input_slots")
    if not isinstance(input_slots, list):
        input_slots = runtime.get("consumes", [])
    card = {
        "id": skill["id"],
        "path": skill["path"],
        "instruction_path": runtime.get("instruction_path", skill["path"]),
        "description": skill["description"],
        "objects": skill["objects"],
        "produces_artifact": bool(runtime.get("produces_artifact", True)),
        "input_slots": input_slots,
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
    if isinstance(output_slot, str) and output_slot.strip():
        card["output_slot"] = output_slot.strip()
    return card


def _build_run_instructions(
    implicit_skill_id: str | None,
    artifact_selection: dict[str, Any] | None,
    *,
    selected_skill_id: str | None = None,
) -> dict[str, Any]:
    selected_inputs: list[dict[str, Any]] = []
    if isinstance(artifact_selection, dict):
        raw_inputs = artifact_selection.get("selected_inputs")
        if isinstance(raw_inputs, list):
            selected_inputs = [item for item in raw_inputs if isinstance(item, dict)]

    next_actions: list[str]
    if implicit_skill_id:
        next_actions = [f"Use implicit_skill_id '{implicit_skill_id}' for this run."]
    elif selected_skill_id:
        next_actions = [
            "Choose one skill_id from eligible_skills.",
            f"If you choose skill_id '{selected_skill_id}', use the selected inputs below for that run.",
        ]
    else:
        next_actions = ["Choose one skill_id from eligible_skills."]

    next_actions.append("When track_artifact_index is present, select relevant inputs by slot before running the skill.")
    if selected_inputs:
        joined_slots = ", ".join(
            f"{item.get('slot')}={item.get('artifact_id')}"
            for item in selected_inputs
            if isinstance(item.get("slot"), str) and isinstance(item.get("artifact_id"), str)
        )
        next_actions.append(f"Read selected inputs by slot: {joined_slots}.")
    next_actions.extend(
        [
            "Read the selected buddyswitch/skills/<buddy>/<skill>/SKILL.md in the current Codex CLI session.",
            "Produce a structured result payload matching required_output_schema_by_skill[skill_id].",
            "Call persist when you want BuddySwitch to write task/artifact/track state and run audit metadata.",
        ]
    )

    artifact_read_commands = []
    seen_artifact_ids: set[str] = set()
    for item in selected_inputs:
        artifact_id = item.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in seen_artifact_ids:
            continue
        seen_artifact_ids.add(artifact_id)
        artifact_read_commands.append(f"python3 scripts/env_artifacts.py get {artifact_id}")
    return {
        "host": "codex",
        "selection_rule": "Choose exactly one skill_id from eligible_skills. Multi-skill buddies are never auto-selected by the runtime.",
        "execution_rule": "The host Codex session runs the selected skill workflow and produces a structured result that matches required_output_schema_by_skill[skill_id].",
        "persistence_rule": "Call persist with the resolved payload, selected skill_id, and structured result when the run should become BuddySwitch state.",
        "resolve_notes": [
            "resolve parses the invocation, derives candidates and context, and does not write BuddySwitch state."
        ],
        "selected_inputs": selected_inputs,
        "artifact_read_commands": artifact_read_commands,
        "next_actions": next_actions,
    }


def _track_object_path(track_id: str) -> str:
    return f"buddyswitch/objects/tracks/{track_id}.json"


def _task_object_path(task_id: str) -> str:
    return f"buddyswitch/objects/tasks/{task_id}.json"


def _artifact_object_path(artifact_id: str) -> str:
    return f"buddyswitch/objects/artifacts/{artifact_id}.json"


def _scan_task_recent_runs(task_id: str, *, limit: int = 3) -> list[dict[str, Any]]:
    run_root = ROOT / "buddyswitch" / "content" / "runs"
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
        switch = payload.get("switch")
        if not isinstance(switch, dict):
            continue
        if switch.get("task_id") != task_id:
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


def _build_artifact_selection_context(
    *,
    demand: str,
    required_slots: list[str],
    task_id: str,
    track_artifact_index: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if track_artifact_index is None:
        return None
    return select_artifacts_for_run(
        current_buddy="",
        demand=demand,
        required_slots=required_slots,
        track_artifact_index=track_artifact_index,
        current_task_id=task_id,
    )


def _skill_required_slots(skill: dict[str, Any]) -> list[str]:
    runtime = skill["runtime"]
    raw_slots = runtime.get("input_slots")
    if not isinstance(raw_slots, list):
        raw_slots = runtime.get("consumes", [])
    return [slot for slot in raw_slots if isinstance(slot, str) and slot]


def _build_selection_contexts_by_skill(
    *,
    demand: str,
    skills: list[dict[str, Any]],
    task_id: str,
    track_artifact_index: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    artifact_selection_by_skill: dict[str, dict[str, Any]] = {}
    run_instructions_by_skill: dict[str, dict[str, Any]] = {}

    for skill in skills:
        required_slots = _skill_required_slots(skill)
        skill_id = skill["id"]
        selection = select_artifacts_for_run(
            current_buddy="",
            demand=demand,
            required_slots=required_slots,
            track_artifact_index=track_artifact_index,
            current_task_id=task_id,
        )
        artifact_selection_by_skill[skill_id] = selection
        run_instructions_by_skill[skill_id] = _build_run_instructions(
            None,
            selection,
            selected_skill_id=skill_id,
        )

    return artifact_selection_by_skill, run_instructions_by_skill


def resolve_switch(text: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    parsed = parse_switch(text, manifest_path=manifest_path)
    if not parsed.get("ok"):
        return parsed

    buddy_id = parsed["buddy"]
    demand = parsed["demand"]
    explicit_task_id = parsed.get("task_id")
    explicit_track_id = parsed.get("track_id")
    _ensure_no_legacy_outputs(demand)

    buddy = require_buddy(manifest, buddy_id)

    existing_task: dict[str, Any] | None = None
    if explicit_task_id:
        existing_task = get_task(explicit_task_id)
        if existing_task is None:
            raise ValueError(f"Referenced task '{explicit_task_id}' not found.")
        if existing_task["buddy"] != buddy_id:
            raise ValueError(
                f"Task '{explicit_task_id}' belongs to buddy '{existing_task['buddy']}', not '{buddy_id}'."
            )

    if explicit_track_id and get_track(explicit_track_id) is None:
        raise ValueError(f"Referenced track '{explicit_track_id}' not found.")

    if existing_task and explicit_track_id and existing_task.get("track_id") not in {None, explicit_track_id}:
        raise ValueError(
            f"Task '{existing_task['id']}' is bound to track '{existing_task['track_id']}', cannot switch to '{explicit_track_id}'."
        )

    if existing_task:
        resolved_task_id = existing_task["id"]
        task_resolution = {
            "mode": "reuse",
            "task_id": resolved_task_id,
            "task_exists": True,
            "task_buddy": existing_task["buddy"],
            "task_track_id": existing_task.get("track_id"),
        }
    else:
        resolved_task_id = _derive_task_id(buddy_id, demand)
        task_resolution = {
            "mode": "create",
            "task_id": resolved_task_id,
            "task_exists": False,
            "task_buddy": buddy_id,
            "task_track_id": None,
        }

    effective_track_id = explicit_track_id or (existing_task.get("track_id") if existing_task else None)

    eligible_skills = buddy_skill_docs(manifest, buddy_id)
    eligible_skill_ids: list[str] = []
    skill_cards: list[dict[str, Any]] = []
    required_output_schema_by_skill: dict[str, str] = {}
    for skill in eligible_skills:
        eligible_skill_ids.append(skill["id"])
        skill_cards.append(_build_skill_card(skill))
        required_output_schema_by_skill[skill["id"]] = skill["runtime"]["output_schema"]

    if not eligible_skill_ids:
        raise ValueError(f"No eligible skills remain for buddy '{buddy_id}'.")

    implicit_skill_id = eligible_skill_ids[0] if len(eligible_skill_ids) == 1 else None
    implicit_skill = next((skill for skill in eligible_skills if skill["id"] == implicit_skill_id), None)
    normalized_text = parsed.get("normalized_text")
    switch_payload = {
        "buddy": buddy_id,
        "task_id": resolved_task_id,
        "track_id": explicit_track_id,
        "demand": demand,
        "raw_text": parsed.get("raw_text", text),
        "normalized_text": normalized_text,
    }

    track_context = _build_track_context(effective_track_id)
    track_artifact_index = build_track_artifact_index(effective_track_id)
    artifact_selection_by_skill, run_instructions_by_skill = _build_selection_contexts_by_skill(
        demand=demand,
        skills=eligible_skills,
        task_id=resolved_task_id,
        track_artifact_index=track_artifact_index,
    )
    artifact_selection = _build_artifact_selection_context(
        demand=demand,
        required_slots=(
            _skill_required_slots(implicit_skill)
            if implicit_skill
            else []
        ),
        task_id=resolved_task_id,
        track_artifact_index=track_artifact_index,
    )
    if implicit_skill is None:
        artifact_selection = None

    return {
        "ok": True,
        "intent": parsed.get("intent", "switch"),
        "raw_text": parsed.get("raw_text", text),
        "normalized_text": normalized_text,
        "invocation": parsed.get("invocation", switch_payload),
        "switch": switch_payload,
        "profile": {
            "buddy": {"id": buddy["id"], "label": buddy["label"], "scope": buddy["scope"]},
            "permissions": buddy.get("permissions", []),
            "authority": buddy_authority_profile(manifest, buddy_id),
        },
        "task_resolution": task_resolution,
        "effective_track_id": effective_track_id,
        "task_context": _build_task_context(existing_task),
        "track_context": track_context,
        "track_artifact_index": track_artifact_index,
        "artifact_selection": artifact_selection,
        "artifact_selection_by_skill": artifact_selection_by_skill,
        "eligible_skills": eligible_skill_ids,
        "skill_cards": skill_cards,
        "implicit_skill_id": implicit_skill_id,
        "required_output_schema_by_skill": required_output_schema_by_skill,
        "run_instructions": _build_run_instructions(
            implicit_skill_id,
            artifact_selection,
        ),
        "run_instructions_by_skill": run_instructions_by_skill,
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
    reference_switches: dict[str, str],
    related_run_ids: list[str],
    recommended_switch: str,
) -> dict[str, Any]:
    audit = {
        "run_id": run_id,
        "timestamp": now_iso(),
        "switch": resolved["switch"],
        "resolved_task_id": task_id,
        "effective_track_id": effective_track_id,
        "skill_id": skill_id,
        "artifact_ids": artifact_ids,
        "track_action": track_action,
        "paths": paths,
        "writes": writes,
        "task_title": task_title,
        "track_title": track_title,
        "reference_switches": reference_switches,
        "related_run_ids": related_run_ids,
        "recommended_switch": recommended_switch,
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

    if task.get("track_id") not in {None, explicit_track_id}:
        raise ValueError(
            f"Task '{task['id']}' is bound to track '{task['track_id']}', cannot switch to '{explicit_track_id}'."
        )
    updated_task = register_task_to_track(explicit_track_id, task["id"])
    writes = [_task_object_path(updated_task["id"]), _track_object_path(explicit_track_id)]
    return updated_task, explicit_track_id, writes


def _persist_track_manager(
    *,
    resolved: dict[str, Any],
    result: dict[str, Any],
    run_id: str,
    task: dict[str, Any],
    effective_track_id: str | None,
) -> dict[str, Any]:
    op = dict(result.get("track_operation") or {})
    action = str(op.get("action") or "").lower()
    if action not in TRACK_ACTIONS:
        raise ValueError("track_operation.action must be one of create/read/list/update/advance/archive")

    writes = [_task_object_path(task["id"])]
    persisted_track_id = effective_track_id
    persisted_track_title: str | None = None
    next_buddy: str | None = None

    if action == "list":
        if persisted_track_id:
            track = get_track(persisted_track_id)
            if track:
                persisted_track_title = track["title"]
                next_buddy = track.get("next_buddy")
    elif action == "create":
        new_id = op.get("track_id") or _derive_track_id(resolved["switch"]["demand"])
        title = op.get("title") or new_id.replace("-", " ").title()
        status = op.get("status") or "active"
        if status not in STATUS_VALUES:
            raise ValueError(f"track_operation.status must be one of {', '.join(STATUS_VALUES)}")
        track = create_track(
            new_id,
            title,
            status=status,
            current_buddy=op.get("current_buddy") or "pm",
            next_buddy=op.get("next_buddy"),
            summary=op.get("summary") or "",
        )
        register_task_to_track(track["id"], task["id"])
        persisted_track_id = track["id"]
        persisted_track_title = track["title"]
        next_buddy = track.get("next_buddy")
        writes.extend([_track_object_path(track["id"]), _task_object_path(task["id"])])
    else:
        target_track_id = op.get("track_id") or effective_track_id
        if not target_track_id:
            raise ValueError("track_operation requires track_id for non-create/non-list actions")
        track = get_track(target_track_id)
        if track is None:
            raise ValueError(f"Track not found: {target_track_id}")
        persisted_track_id = target_track_id
        persisted_track_title = track["title"]
        next_buddy = track.get("next_buddy")

        if action in {"update", "advance"}:
            patch: dict[str, Any] = {}
            for key in ("title", "status", "current_buddy", "next_buddy", "summary"):
                if key in op and op.get(key) is not None:
                    patch[key] = op.get(key)
            if not patch:
                raise ValueError("track_operation for update/advance must include at least one mutable field")
            if "status" in patch and patch["status"] not in STATUS_VALUES:
                raise ValueError(f"track_operation.status must be one of {', '.join(STATUS_VALUES)}")
            track = update_track(target_track_id, patch)
            persisted_track_title = track["title"]
            next_buddy = track.get("next_buddy")
            writes.append(_track_object_path(track["id"]))
        elif action == "archive":
            track = update_track(target_track_id, {"status": "archived"})
            persisted_track_title = track["title"]
            next_buddy = track.get("next_buddy")
            writes.append(_track_object_path(track["id"]))

    add_run_to_task(task["id"], run_id, summary=str(result.get("execution_summary") or ""))

    run_content_path_value = run_content_path(run_id)
    artifact_ids: list[str] = []
    related_run_ids = _related_run_ids_for_task(task["id"], run_id, limit=2)
    reference_switches = _build_reference_switches(
        buddy_id=resolved["switch"]["buddy"],
        task_id=task["id"],
        track_id=persisted_track_id,
        next_buddy=next_buddy,
    )
    recommended_switch = _pick_recommended_switch(reference_switches)
    paths = _receipt_paths(
        run_content_path_value=run_content_path_value,
        task_id=task["id"],
        artifact_ids=artifact_ids,
        track_id=persisted_track_id,
    )
    writes = list(dict.fromkeys(writes + [run_content_path_value]))
    save_run_content(
        run_id,
        _build_run_audit(
            resolved=resolved,
            task_id=task["id"],
            effective_track_id=persisted_track_id,
            skill_id="track-manager",
            run_id=run_id,
            artifact_ids=artifact_ids,
            track_action=action,
            paths=paths,
            writes=writes,
            result=result,
            task_title=task["title"],
            track_title=persisted_track_title,
            reference_switches=reference_switches,
            related_run_ids=related_run_ids,
            recommended_switch=recommended_switch,
        ),
    )
    return {
        "ok": True,
        "switch": resolved["switch"],
        "skill_id": "track-manager",
        "track_action": action,
        "task_id": task["id"],
        "track_id": persisted_track_id,
        "task_title": task["title"],
        "track_title": persisted_track_title,
        "reference_switches": reference_switches,
        "related_run_ids": related_run_ids,
        "recommended_switch": recommended_switch,
        "artifact_ids": artifact_ids,
        "run_id": run_id,
        "paths": paths,
        "writes": writes,
    }


def _persist_artifact_skill(
    *,
    resolved: dict[str, Any],
    skill: dict[str, Any],
    result: dict[str, Any],
    run_id: str,
    task: dict[str, Any],
    effective_track_id: str | None,
) -> dict[str, Any]:
    buddy = resolved["switch"]["buddy"]
    demand = resolved["switch"]["demand"]
    skill_id = skill["id"]
    output_slot = skill["runtime"].get("output_slot")
    if not isinstance(output_slot, str) or not output_slot:
        raise ValueError(f"skill '{skill_id}' must define a non-empty output_slot")
    output_slot = output_slot.strip()
    if not output_slot:
        raise ValueError(f"skill '{skill_id}' must define a non-empty output_slot")
    artifact_id = _derive_artifact_id(task["id"], output_slot)
    artifact_summary = str(result.get("execution_summary") or "")
    artifact = create_artifact(
        artifact_id=artifact_id,
        title=_derive_artifact_title(buddy, skill_id, demand),
        buddy=buddy,
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
    track_title: str | None = None
    next_buddy: str | None = None
    if effective_track_id:
        track = get_track(effective_track_id)
        if track:
            track_title = track["title"]
            next_buddy = track.get("next_buddy")
    reference_switches = _build_reference_switches(
        buddy_id=buddy,
        task_id=task["id"],
        track_id=effective_track_id,
        next_buddy=next_buddy,
    )
    recommended_switch = _pick_recommended_switch(reference_switches)
    paths = _receipt_paths(
        run_content_path_value=run_content_path_value,
        task_id=task["id"],
        artifact_ids=artifact_ids,
        track_id=effective_track_id,
    )
    writes = [_task_object_path(task["id"]), _artifact_object_path(artifact["id"]), run_content_path_value]
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
            track_action=None,
            paths=paths,
            writes=writes,
            result=result,
            task_title=task["title"],
            track_title=track_title,
            reference_switches=reference_switches,
            related_run_ids=related_run_ids,
            recommended_switch=recommended_switch,
        ),
    )
    return {
        "ok": True,
        "switch": resolved["switch"],
        "skill_id": skill_id,
        "task_id": task["id"],
        "artifact_id": artifact["id"],
        "artifact_ids": artifact_ids,
        "track_id": effective_track_id,
        "task_title": task["title"],
        "track_title": track_title,
        "reference_switches": reference_switches,
        "related_run_ids": related_run_ids,
        "recommended_switch": recommended_switch,
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
    switch_payload = resolved.get("switch") or {}
    buddy_id = switch_payload.get("buddy")
    if not isinstance(buddy_id, str) or not buddy_id:
        raise ValueError("resolved.switch.buddy is required")
    buddy = require_buddy(manifest, buddy_id)
    if selected_skill_id not in buddy.get("skills", []):
        raise ValueError(f"skill_id '{selected_skill_id}' is not declared for buddy '{buddy_id}'")

    skill = next(skill for skill in buddy_skill_docs(manifest, buddy_id) if skill["id"] == selected_skill_id)
    schema = load_output_schema(skill["runtime"]["output_schema"])
    errors = validate_output_payload(result, schema)
    if errors:
        raise ValueError("result payload failed schema validation: " + "; ".join(errors))

    resolution = dict(resolved.get("task_resolution") or {})
    task_mode = resolution.get("mode")
    task_id = resolution.get("task_id")
    if task_mode not in {"create", "reuse"}:
        raise ValueError("resolved.task_resolution.mode must be 'create' or 'reuse'")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("resolved.task_resolution.task_id must be a non-empty string")

    run_id = f"run-{uuid.uuid4().hex[:10]}"
    explicit_track_id = switch_payload.get("track_id")

    if task_mode == "create":
        task = create_task(
            task_id,
            _derive_task_title(switch_payload.get("demand") or ""),
            buddy=buddy_id,
            track_id=None,
            status="active",
            summary="",
            initial_run_id=run_id,
        )
    else:
        task = get_task(task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id}")
        if task["buddy"] != buddy_id:
            raise ValueError(f"task '{task_id}' belongs to '{task['buddy']}', not '{buddy_id}'")
        add_run_to_task(task_id, run_id)
        task = get_task(task_id) or task

    task, effective_track_id, _ = _ensure_task_binding(task=task, explicit_track_id=explicit_track_id)

    if selected_skill_id == "track-manager":
        return _persist_track_manager(
            resolved=resolved,
            result=result,
            run_id=run_id,
            task=task,
            effective_track_id=effective_track_id,
        )

    return _persist_artifact_skill(
        resolved=resolved,
        skill=skill,
        result=result,
        run_id=run_id,
        task=task,
        effective_track_id=effective_track_id,
    )


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
