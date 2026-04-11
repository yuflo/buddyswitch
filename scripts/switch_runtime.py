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
    artifact_content_path,
    artifact_markdown_path,
    attach_artifact,
    create_artifact,
    create_track,
    detach_artifact,
    get_track,
    list_artifacts,
    list_tracks,
    normalize_artifact_file_path,
    normalize_summary_file_path,
    now_iso,
    save_artifact_content,
    save_run_content,
    slugify,
    update_track,
)
from output_schema import OutputSchemaError, load_output_schema, validate_output_payload
from parse_switch import EXAMPLE, SYNTAX, parse_switch


TRACK_ACTIONS = ("create", "read", "list", "update", "advance", "attach", "detach", "archive")
STATUS_VALUES = ("active", "blocked", "done", "archived")


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


def _write_file(repo_path: str, content: str) -> None:
    path = ROOT / repo_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
    return {
        "explicit_track_id": _extract_track_id(task),
        "explicit_artifact_id": _extract_artifact_id(task),
        "output_path": normalize_artifact_file_path(output_path) if output_path else None,
        "summary_path": normalize_summary_file_path(summary_path) if summary_path else None,
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
    kind = skill["runtime"]["default_artifact_kind"]
    base = f"art-{slugify((track_id or buddy) + '-' + kind)}"
    artifact_id = _next_unique(base, existing_ids)
    title = _derive_artifact_title(buddy, skill["id"], task)
    artifact_path = task_hints["output_path"] or artifact_markdown_path(artifact_id, title)
    summary_path = task_hints["summary_path"] or f"runs/summaries/{buddy}/{artifact_id}.md"
    return {
        "id": artifact_id,
        "title": title,
        "kind": kind,
        "path": normalize_artifact_file_path(artifact_path),
        "summary_path": normalize_summary_file_path(summary_path),
    }


def _derive_track_summary_defaults(buddy: str, task: str, task_hints: dict[str, Any]) -> dict[str, Any]:
    if task_hints["summary_path"]:
        summary_path = task_hints["summary_path"]
    else:
        seed = task_hints["explicit_track_id"] or slugify(task) or "track-operation"
        summary_path = normalize_summary_file_path(f"runs/summaries/{buddy}/{seed}--track-manager.md")
    return {"enabled": True, "path": summary_path}


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
        "resolve_effects": [
            "resolve parses the invocation, derives skill candidates and defaults, and does not write BuddySwitch state."
        ],
        "next_actions": [
            first_action,
            "Read the selected buddyswitch/skills/<buddy>/<skill>/SKILL.md in the current Codex CLI session.",
            "Produce a structured result payload matching required_output_schema_by_skill[skill_id].",
            "Call persist when you want BuddySwitch to write state, artifact content, summaries, and run metadata.",
        ],
        "persist_effects": [
            "Artifact skills write artifact state under buddyswitch/objects/ and buddyswitch/content/, plus compatibility markdown under artifacts/ and runs/summaries/.",
            "track-manager writes only the requested track or attachment state, plus the run summary and run metadata.",
        ],
    }


def _build_track_manager_effects(
    *,
    action: str,
    track_payload: dict[str, Any],
    summary_path: str,
    run_content_path_value: str,
) -> dict[str, Any]:
    writes = [summary_path, run_content_path_value]
    if action in {"create", "update", "advance", "archive", "attach", "detach"}:
        track = track_payload.get("track")
        if isinstance(track, dict) and track.get("id"):
            writes.insert(0, f"buddyswitch/objects/tracks/{track['id']}.json")
    if action in {"attach", "detach"}:
        artifact = track_payload.get("artifact")
        if isinstance(artifact, dict) and artifact.get("id"):
            writes.insert(1, f"buddyswitch/objects/artifacts/{artifact['id']}.json")

    if action in {"list", "read"}:
        summary = "persist validated the payload and wrote only summary/run metadata."
    else:
        summary = "persist validated the payload and wrote the requested BuddySwitch state changes."

    return {"summary": summary, "writes": writes}


def _build_artifact_effects(
    *,
    artifact: dict[str, Any],
    content_path: str,
    summary_path: str | None,
    run_content_path_value: str,
) -> dict[str, Any]:
    writes = [
        f"buddyswitch/objects/artifacts/{artifact['id']}.json",
        content_path,
        artifact["path"],
        run_content_path_value,
    ]
    if summary_path:
        writes.insert(3, summary_path)
    if artifact.get("context_track_id"):
        writes.insert(1, f"buddyswitch/objects/tracks/{artifact['context_track_id']}.json")

    return {
        "summary": "persist validated the payload and wrote BuddySwitch artifact state plus compatibility files.",
        "writes": writes,
    }


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
    artifact_defaults_by_skill: dict[str, Any] = {}
    summary_defaults_by_skill: dict[str, Any] = {}
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
        if skill["id"] == "track-manager":
            summary_defaults_by_skill[skill["id"]] = _derive_track_summary_defaults(buddy_id, task, task_hints)
        else:
            artifact_defaults = _derive_artifact_defaults(
                buddy_id,
                skill,
                task,
                track_context["track_id"],
                task_hints,
            )
            artifact_defaults_by_skill[skill["id"]] = artifact_defaults
            summary_defaults_by_skill[skill["id"]] = {
                "enabled": bool(skill["runtime"]["auto_summary"]),
                "path": artifact_defaults["summary_path"],
            }

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
        "artifact_defaults_by_skill": artifact_defaults_by_skill,
        "summary_defaults_by_skill": summary_defaults_by_skill,
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


def _render_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _render_value(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}- {key}:")
                lines.extend(_render_value(child, indent + 2))
            else:
                lines.append(f"{prefix}- {key}: {_render_scalar(child)}")
        return lines or [f"{prefix}-"]
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_render_value(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_render_scalar(item)}")
        return lines or [f"{prefix}-"]
    return [f"{prefix}{_render_scalar(value)}"]


def _render_artifact_markdown(
    artifact: dict[str, Any],
    *,
    buddy: str,
    skill_id: str,
    task: str,
    artifact_content: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    section_order = list(schema.get("properties", {}).get("artifact_content", {}).get("properties", {}).keys())
    if not section_order:
        section_order = list(artifact_content.keys())

    lines = [
        f"# {artifact['title']}",
        "",
        f"- buddy: {buddy}",
        f"- skill: {skill_id}",
        f"- generated_at: {now_iso()}",
        f"- task: {task}",
    ]
    if artifact.get("context_track_id"):
        lines.append(f"- context_track_id: {artifact['context_track_id']}")

    for section in section_order:
        if section not in artifact_content:
            continue
        lines.extend(["", f"## {section}", ""])
        lines.extend(_render_value(artifact_content[section]))

    return "\n".join(lines) + "\n"


def _render_summary_markdown(
    *,
    buddy: str,
    skill_id: str,
    task: str,
    result: dict[str, Any],
    artifact_path: str | None = None,
) -> str:
    lines = [
        f"# {buddy.upper()} Run Summary",
        "",
        f"- generated_at: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- task: {task}",
        f"- skill: {skill_id}",
    ]
    if artifact_path:
        lines.append(f"- artifact: {artifact_path}")

    sections = (
        ("execution_summary", result.get("execution_summary")),
        ("working_notes", result.get("working_notes")),
        ("deliverables_or_changed_files", result.get("deliverables_or_changed_files")),
    )
    for label, value in sections:
        if value in (None, "", []):
            continue
        lines.extend(["", f"## {label}", ""])
        lines.extend(_render_value(value))

    if result.get("track_operation"):
        lines.extend(["", "## track_operation", ""])
        lines.extend(_render_value(result["track_operation"]))

    suggested = result.get("suggested_next_switch")
    if suggested not in (None, ""):
        lines.extend(["", "## suggested_next_switch", "", suggested])

    return "\n".join(lines) + "\n"


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
    summary_path: str,
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
        _write_file(summary_path, _render_summary_markdown(buddy="pm", skill_id="track-manager", task=task, result=result))
        run_content_path_value = save_run_content(run_id, {"switch": resolved["switch"], "skill_id": "track-manager", "result": result, "track_result": track_payload})
        return {
            "ok": True,
            "switch": resolved["switch"],
            "skill": {"id": "track-manager"},
            "track": track_payload,
            "summary": {"path": summary_path},
            "effects": _build_track_manager_effects(
                action=action,
                track_payload=track_payload,
                summary_path=summary_path,
                run_content_path_value=run_content_path_value,
            ),
            "run": {"id": run_id, "content_path": run_content_path_value},
        }

    if action == "create":
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

    _write_file(summary_path, _render_summary_markdown(buddy="pm", skill_id="track-manager", task=task, result=result))
    run_content_path_value = save_run_content(
        run_id,
        {
            "switch": resolved["switch"],
            "skill_id": "track-manager",
            "result": result,
            "track_result": track_payload,
            "summary_path": summary_path,
        },
    )
    return {
        "ok": True,
        "switch": resolved["switch"],
        "skill": {"id": "track-manager"},
        "track": track_payload,
        "summary": {"path": summary_path},
        "effects": _build_track_manager_effects(
            action=action,
            track_payload=track_payload,
            summary_path=summary_path,
            run_content_path_value=run_content_path_value,
        ),
        "run": {"id": run_id, "content_path": run_content_path_value},
    }


def _persist_artifact_skill(
    resolved: dict[str, Any],
    skill: dict[str, Any],
    result: dict[str, Any],
    schema: dict[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    buddy = resolved["switch"]["buddy"]
    task = resolved["switch"]["task"]
    skill_id = skill["id"]
    artifact_defaults = resolved.get("artifact_defaults_by_skill", {}).get(skill_id)
    if not isinstance(artifact_defaults, dict):
        raise ValueError(f"resolve payload is missing artifact defaults for skill '{skill_id}'")

    artifact_id = artifact_defaults["id"]
    content_path_value = artifact_content_path(artifact_id)
    summary_defaults = resolved.get("summary_defaults_by_skill", {}).get(skill_id, {})
    summary_path = summary_defaults.get("path") if summary_defaults.get("enabled") else None
    track_context = resolved.get("track_context_by_skill", {}).get(skill_id, {})

    artifact = create_artifact(
        artifact_id=artifact_id,
        title=artifact_defaults["title"],
        kind=artifact_defaults["kind"],
        path=artifact_defaults["path"],
        producer_buddy=buddy,
        source_skill=skill_id,
        context_track_id=track_context.get("track_id"),
        content_path=content_path_value,
        summary_path=summary_path,
        auto_register=True,
    )

    artifact_content = {
        "artifact_id": artifact["id"],
        "buddy": buddy,
        "skill_id": skill_id,
        "task": task,
        "schema_path": skill["runtime"]["output_schema"],
        "generated_at": now_iso(),
        "content": result["artifact_content"],
    }
    saved_content_path = save_artifact_content(artifact["id"], artifact_content)

    artifact_markdown = _render_artifact_markdown(
        artifact,
        buddy=buddy,
        skill_id=skill_id,
        task=task,
        artifact_content=result["artifact_content"],
        schema=schema,
    )
    _write_file(artifact["path"], artifact_markdown)

    if summary_path:
        _write_file(
            summary_path,
            _render_summary_markdown(
                buddy=buddy,
                skill_id=skill_id,
                task=task,
                result=result,
                artifact_path=artifact["path"],
            ),
        )

    run_content_path_value = save_run_content(
        run_id,
        {
            "switch": resolved["switch"],
            "skill_id": skill_id,
            "artifact_id": artifact["id"],
            "artifact_path": artifact["path"],
            "content_path": saved_content_path,
            "summary_path": summary_path,
            "result": result,
        },
    )

    return {
        "ok": True,
        "switch": resolved["switch"],
        "skill": {"id": skill_id, "track_mode": skill["runtime"]["track_mode"]},
        "artifact": artifact,
        "summary": {"path": summary_path},
        "effects": _build_artifact_effects(
            artifact=artifact,
            content_path=saved_content_path,
            summary_path=summary_path,
            run_content_path_value=run_content_path_value,
        ),
        "run": {"id": run_id, "content_path": run_content_path_value},
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
        summary_defaults = resolved.get("summary_defaults_by_skill", {}).get("track-manager")
        if not isinstance(summary_defaults, dict) or not summary_defaults.get("path"):
            raise ValueError("resolve payload is missing track-manager summary defaults")
        return _persist_track_manager(
            resolved,
            result,
            manifest=manifest,
            summary_path=summary_defaults["path"],
            run_id=run_id,
        )

    return _persist_artifact_skill(resolved, skill, result, schema, run_id=run_id)


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

    execute_cmd = subparsers.add_parser("execute", help="Deprecated alias for persist.")
    execute_cmd.add_argument("--resolved", required=True, help="Resolved JSON payload file, or '-' for stdin")
    execute_cmd.add_argument("--result", required=True, help="Structured result JSON file, or '-' for stdin")
    execute_cmd.add_argument("--skill-id", help="Chosen skill id. Optional only when resolve returned implicit_skill_id.")
    execute_cmd.set_defaults(func=_cmd_persist)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
