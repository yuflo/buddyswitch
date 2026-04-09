#!/usr/bin/env python3
"""BuddySwitch switch runtime: resolve and execute switch directives."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from env_manifest import DEFAULT_MANIFEST, ManifestError, buddy_skill_docs, load_manifest, require_buddy
from env_store import (
    ROOT,
    artifact_markdown_path,
    create_artifact,
    create_track,
    get_artifact,
    get_track,
    list_artifacts,
    list_tracks,
    normalize_artifact_file_path,
    now_iso,
    slugify,
    update_track,
)
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


def _normalize_summary_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"summary path must be repo-relative: {raw_path}")
    normalized = path.as_posix()
    if not normalized.startswith("runs/summaries/") or not normalized.endswith(".md"):
        raise ValueError("summary path must be under runs/summaries/ and end with .md")
    return normalized


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


def _first_trigger_match(skill: dict[str, Any], task_lower: str) -> tuple[int, int] | None:
    def _trigger_position(text: str, trigger: str) -> int:
        token = trigger.lower()
        if re.search(r"[A-Za-z0-9]", token):
            pattern = rf"(?<![a-z0-9-]){re.escape(token)}(?![a-z0-9-])"
            match = re.search(pattern, text)
            return -1 if match is None else match.start()
        return text.find(token)

    triggers = skill["runtime"].get("triggers", [])
    for trigger_index, trigger in enumerate(triggers):
        position = _trigger_position(task_lower, trigger)
        if position >= 0:
            return position, trigger_index
    return None


def _pick_skill(buddy_id: str, task: str, manifest: dict[str, Any]) -> dict[str, Any]:
    skills = buddy_skill_docs(manifest, buddy_id)
    if not skills:
        raise ValueError(f"buddy '{buddy_id}' has no skills configured")
    if len(skills) == 1:
        return skills[0]

    task_lower = task.lower()
    matches: list[tuple[int, int, int, dict[str, Any]]] = []
    for skill_index, skill in enumerate(skills):
        match = _first_trigger_match(skill, task_lower)
        if match is None:
            continue
        position, trigger_index = match
        matches.append((position, trigger_index, skill_index, skill))

    if matches:
        matches.sort(key=lambda item: (item[0], item[1], item[2]))
        best_position = matches[0][0]
        best = [row for row in matches if row[0] == best_position]
        if len(best) == 1:
            return best[0][3]
        raise ValueError(
            "Multiple skills matched at the same trigger position: "
            + ", ".join(row[3]["id"] for row in best)
            + ". Add clearer intent keywords."
        )

    defaults = [skill for skill in skills if skill["runtime"].get("default") is True]
    if len(defaults) == 1:
        return defaults[0]
    if len(defaults) > 1:
        raise ValueError("Multiple default skills configured: " + ", ".join(skill["id"] for skill in defaults))
    raise ValueError(
        "No skill trigger matched and no default skill configured for buddy "
        f"'{buddy_id}'."
    )


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


def _derive_artifact_title(buddy: str, skill: str, task: str) -> str:
    snippet = " ".join(task.split()[:8]).strip()
    if snippet:
        return f"{buddy.upper()} {skill} - {snippet}"
    return f"{buddy.upper()} {skill}"


def _derive_artifact_defaults(
    buddy: str,
    skill: dict[str, Any],
    task: str,
    track_id: str | None,
) -> dict[str, Any]:
    existing_ids = {artifact["id"] for artifact in list_artifacts()}
    kind = skill["runtime"]["default_artifact_kind"]
    base = f"art-{slugify((track_id or buddy) + '-' + kind)}"
    artifact_id = _next_unique(base, existing_ids)
    title = _derive_artifact_title(buddy, skill["id"], task)
    explicit_path = _extract_output_path(task)
    artifact_path = normalize_artifact_file_path(explicit_path) if explicit_path else artifact_markdown_path(artifact_id, title)
    summary_path = _extract_summary_path(task) or f"runs/summaries/{buddy}/{artifact_id}.md"
    summary_path = _normalize_summary_path(summary_path)
    return {
        "id": artifact_id,
        "title": title,
        "kind": kind,
        "path": artifact_path,
        "summary_path": summary_path,
    }


def resolve_switch(text: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    parsed = parse_switch(text, manifest_path=manifest_path)
    if not parsed.get("ok"):
        return parsed

    buddy_id = parsed["buddy"]
    task = parsed["task"]
    buddy = require_buddy(manifest, buddy_id)
    skill = _pick_skill(buddy_id, task, manifest)
    action = _extract_action(task) if skill["id"] == "track-manager" else None
    track = _resolve_track_context(
        task,
        skill["runtime"]["track_mode"],
        allow_missing_explicit=bool(skill["id"] == "track-manager" and action == "create"),
    )
    valid_buddies = sorted(b.get("id") for b in manifest["buddies"])
    resolved: dict[str, Any] = {
        "ok": True,
        "switch": {"buddy": buddy_id, "task": task},
        "valid_buddies": valid_buddies,
        "profile": {
            "buddy": {"id": buddy["id"], "label": buddy["label"], "scope": buddy["scope"]},
            "permissions": buddy.get("permissions", []),
            "skill": skill,
        },
        "track": track,
    }

    if skill["id"] == "track-manager":
        resolved["track_operation"] = {
            "action": action,
            "artifact_id": _extract_artifact_id(task),
            "status": _extract_status(task),
            "current_buddy": _extract_buddy(task, set(valid_buddies), "current_buddy"),
            "next_buddy": _extract_buddy(task, set(valid_buddies), "next_buddy"),
            "summary": _extract_summary_text(task),
        }
    else:
        resolved["artifact"] = _derive_artifact_defaults(buddy_id, skill, task, track["track_id"])
        resolved["summary"] = {
            "enabled": bool(skill["runtime"]["auto_summary"]),
            "path": resolved["artifact"]["summary_path"],
        }
    return resolved


def _write_summary(path: str, buddy: str, task: str, artifact_path: str | None = None) -> None:
    lines = [
        f"# {buddy.upper()} Run Summary",
        "",
        f"- generated_at: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- task: {task}",
    ]
    if artifact_path:
        lines.append(f"- artifact: {artifact_path}")
    lines.extend(
        [
            "",
            "## execution summary",
            "- completed by switch runtime scaffold",
            "",
            "## working notes",
            "- replace scaffold with task-specific notes",
            "",
            "## deliverables or changed files",
            "- artifact and summary persisted",
        ]
    )
    _write_file(path, "\n".join(lines) + "\n")


def _write_artifact_stub(path: str, title: str, buddy: str, skill_id: str, task: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"- buddy: {buddy}",
        f"- skill: {skill_id}",
        f"- generated_at: {now_iso()}",
        "",
        "## task",
        task,
        "",
        "## notes",
        "- replace scaffold with real content.",
    ]
    _write_file(path, "\n".join(lines) + "\n")


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


def _validate_buddy_value(value: str | None, field: str, valid_buddies: set[str]) -> str | None:
    if value is None:
        return None
    if value not in valid_buddies:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(valid_buddies))}")
    return value


def _execute_track_manager(resolved: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    op = dict(resolved.get("track_operation") or {})
    task = resolved["switch"]["task"]
    action = (args.action or op.get("action") or "").lower()
    if action not in TRACK_ACTIONS:
        raise ValueError("track-manager action unresolved. Include create/read/list/update/advance/attach/detach/archive.")
    valid_buddies = set(resolved.get("valid_buddies", []))

    track_id = args.track_id or resolved["track"]["track_id"] or resolved["track"].get("explicit_track_id")
    artifact_id = args.artifact_id or op.get("artifact_id")

    if action == "list":
        return {"ok": True, "action": "list", "tracks": list_tracks()}

    if action == "create":
        new_id = _next_unique(args.track_id, {track["id"] for track in list_tracks()}) if args.track_id else _derive_create_track_id(task)
        title = args.title or new_id.replace("-", " ").title()
        current_buddy = _validate_buddy_value(args.current_buddy or "pm", "current_buddy", valid_buddies) or "pm"
        if args.next_buddy == "null":
            next_buddy = None
        else:
            next_buddy = _validate_buddy_value(args.next_buddy, "next_buddy", valid_buddies)
        track = create_track(
            new_id,
            title,
            status=args.status or "active",
            current_buddy=current_buddy,
            next_buddy=next_buddy,
            summary=args.summary or "",
        )
        summary_path = _normalize_summary_path(args.summary_path or f"runs/summaries/pm/{new_id}-create.md")
        _write_summary(summary_path, "pm", task)
        return {"ok": True, "action": "create", "track": track, "summary_path": summary_path}

    track_id = _ensure_track_target(track_id)
    track = get_track(track_id)
    assert track is not None

    if action == "read":
        return {"ok": True, "action": "read", "track": track}

    if action in {"update", "advance"}:
        patch: dict[str, Any] = {}
        status = args.status or op.get("status")
        if status:
            patch["status"] = status
        current_buddy = _validate_buddy_value(args.current_buddy or op.get("current_buddy"), "current_buddy", valid_buddies)
        if current_buddy:
            patch["current_buddy"] = current_buddy
        raw_next = args.next_buddy if args.next_buddy is not None else op.get("next_buddy")
        if raw_next == "null":
            patch["next_buddy"] = None
        else:
            next_buddy = _validate_buddy_value(raw_next, "next_buddy", valid_buddies)
            if next_buddy is not None:
                patch["next_buddy"] = next_buddy
        summary = args.summary or op.get("summary")
        if summary:
            patch["summary"] = summary
        if not patch:
            raise ValueError("update/advance requires at least one field (status/current_buddy/next_buddy/summary)")
        updated = update_track(track_id, patch)
        summary_path = _normalize_summary_path(args.summary_path or f"runs/summaries/pm/{track_id}-{action}.md")
        _write_summary(summary_path, "pm", task)
        return {"ok": True, "action": action, "track": updated, "summary_path": summary_path}

    if action == "archive":
        updated = update_track(track_id, {"status": "archived"})
        summary_path = _normalize_summary_path(args.summary_path or f"runs/summaries/pm/{track_id}-archive.md")
        _write_summary(summary_path, "pm", task)
        return {"ok": True, "action": "archive", "track": updated, "summary_path": summary_path}

    if action in {"attach", "detach"}:
        if not artifact_id:
            raise ValueError(f"{action} requires artifact id (e.g., art-xxx).")
        artifact = get_artifact(artifact_id)
        if artifact is None:
            raise ValueError(f"artifact not found: {artifact_id}")
        artifact_ids = list(track["artifact_ids"])
        if action == "attach" and artifact_id not in artifact_ids:
            artifact_ids.append(artifact_id)
        if action == "detach":
            artifact_ids = [item for item in artifact_ids if item != artifact_id]
        patch = {"artifact_ids": artifact_ids}
        if action == "attach":
            patch["current_buddy"] = "pm"
        updated = update_track(track_id, patch)
        if action == "attach" and artifact.get("context_track_id") != track_id:
            from env_store import update_artifact as _update_artifact  # local import to avoid cycle at module import.

            _update_artifact(artifact_id, {"context_track_id": track_id}, auto_register=False)
        if action == "detach" and artifact.get("context_track_id") == track_id:
            from env_store import update_artifact as _update_artifact

            _update_artifact(artifact_id, {"context_track_id": None}, auto_register=False)
        summary_path = _normalize_summary_path(args.summary_path or f"runs/summaries/pm/{track_id}-{action}.md")
        _write_summary(summary_path, "pm", task)
        return {
            "ok": True,
            "action": action,
            "track": updated,
            "artifact_id": artifact_id,
            "summary_path": summary_path,
        }

    raise ValueError(f"Unsupported track-manager action: {action}")


def execute_switch(text: str, args: argparse.Namespace) -> dict[str, Any]:
    resolved = resolve_switch(text, manifest_path=args.manifest)
    if not resolved.get("ok"):
        return resolved

    skill = resolved["profile"]["skill"]
    buddy = resolved["switch"]["buddy"]
    task = resolved["switch"]["task"]

    if skill["id"] == "track-manager":
        return _execute_track_manager(resolved, args)

    track_mode = skill["runtime"]["track_mode"]
    if track_mode == "forbidden" and args.track_id:
        raise ValueError("This skill forbids track linkage; remove --track-id.")

    artifact_defaults = resolved["artifact"]
    artifact_id = args.artifact_id or artifact_defaults["id"]
    title = args.title or artifact_defaults["title"]
    kind = args.kind or artifact_defaults["kind"]
    path = normalize_artifact_file_path(args.output_path) if args.output_path else artifact_defaults["path"]
    context_track_id = args.track_id if args.track_id is not None else resolved["track"]["track_id"]

    artifact = create_artifact(
        artifact_id=artifact_id,
        title=title,
        kind=kind,
        path=path,
        producer_buddy=buddy,
        source_skill=skill["id"],
        context_track_id=context_track_id,
        auto_register=True,
    )

    _write_artifact_stub(path, title, buddy, skill["id"], task)

    summary = resolved.get("summary", {})
    summary_path = None
    if summary.get("enabled"):
        summary_path = _normalize_summary_path(args.summary_path or summary["path"])
        _write_summary(summary_path, buddy, task, artifact_path=path)

    return {
        "ok": True,
        "switch": resolved["switch"],
        "skill": {"id": skill["id"], "track_mode": skill["runtime"]["track_mode"]},
        "track": resolved["track"],
        "artifact": artifact,
        "summary": {"path": summary_path},
    }


def _cmd_resolve(args: argparse.Namespace) -> int:
    try:
        payload = resolve_switch(args.text, manifest_path=args.manifest)
    except (ManifestError, ValueError) as exc:
        payload = runtime_error("E_RUNTIME_RESOLVE", str(exc))
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


def _cmd_execute(args: argparse.Namespace) -> int:
    try:
        payload = execute_switch(args.text, args)
    except (ManifestError, ValueError) as exc:
        payload = runtime_error("E_RUNTIME_EXECUTE", str(exc))
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BuddySwitch switch runtime.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_cmd = subparsers.add_parser("resolve", help="Resolve switch directive into execution context.")
    resolve_cmd.add_argument("text", help="switch directive")
    resolve_cmd.set_defaults(func=_cmd_resolve)

    exec_cmd = subparsers.add_parser("execute", help="Execute switch directive with default runtime actions.")
    exec_cmd.add_argument("text", help="switch directive")
    exec_cmd.add_argument("--track-id")
    exec_cmd.add_argument("--artifact-id")
    exec_cmd.add_argument("--title")
    exec_cmd.add_argument("--kind")
    exec_cmd.add_argument("--output-path")
    exec_cmd.add_argument("--summary-path")
    exec_cmd.add_argument("--action", choices=TRACK_ACTIONS)
    exec_cmd.add_argument("--status", choices=STATUS_VALUES)
    exec_cmd.add_argument("--current-buddy")
    exec_cmd.add_argument("--next-buddy")
    exec_cmd.add_argument("--summary")
    exec_cmd.set_defaults(func=_cmd_execute)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
