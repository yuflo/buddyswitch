#!/usr/bin/env python3
"""Task TUI renderer."""

from __future__ import annotations

from typing import Any, Mapping


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _short_event(event: Any) -> str:
    row = _as_mapping(event)
    if row is None:
        return "none"
    event_name = row.get("event")
    task_id = row.get("task_id")
    if isinstance(event_name, str) and isinstance(task_id, str):
        return f"{event_name} {task_id}"
    line = row.get("line")
    if isinstance(line, str) and line.strip():
        parts = line.strip().split()
        if len(parts) >= 4:
            return " ".join(parts[2:4])
        return line.strip()
    return "none"


def _pending_line(pending: Mapping[str, Any] | None) -> str:
    if pending is None:
        return "Pending Confirmation: none"
    confirmation_id = pending.get("confirmation_id")
    target = _as_mapping(pending.get("target"))
    target_label = "unknown target"
    if target is not None:
        task_id = target.get("task_id")
        task = _as_mapping(target.get("task"))
        if task is not None and isinstance(task.get("title"), str):
            target_label = str(task["title"])
        elif isinstance(task_id, str) and task_id:
            target_label = task_id
    if not isinstance(confirmation_id, str) or not confirmation_id:
        confirmation_id = "unknown"
    return f"Pending Confirmation: {confirmation_id} -> {target_label}"


def _turn_id(previous_turn: Mapping[str, Any]) -> str:
    for key in ("turn_id", "id"):
        value = previous_turn.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def render_task_tui(snapshot: Mapping[str, object]) -> str:
    current_task = _as_mapping(snapshot.get("current_task"))
    pending_confirmation = _as_mapping(snapshot.get("pending_confirmation"))
    progress = snapshot.get("progress_summary")
    if not isinstance(progress, str):
        progress = ""

    lines: list[str] = ["[TASK CONTEXT]"]
    if current_task is None:
        lines.extend(
            [
                "Current Task: none",
                "Title: none",
                f"State: {snapshot.get('task_state') or 'none'}",
                "Progress: none",
            ]
        )
    else:
        lines.extend(
            [
                f"Current Task: {current_task.get('id') or 'unknown'}",
                f"Title: {current_task.get('title') or 'untitled'}",
                f"State: {current_task.get('status') or snapshot.get('task_state') or 'none'}",
                f"Progress: {progress or current_task.get('summary') or current_task.get('body_excerpt') or 'none'}",
            ]
        )

    lines.append(f"Last Event: {_short_event(snapshot.get('last_event'))}")
    lines.append(_pending_line(pending_confirmation))
    lines.append("Recent Events:")
    recent_events = snapshot.get("recent_events")
    if isinstance(recent_events, list) and recent_events:
        for event in recent_events:
            lines.append(f"- {_short_event(event)}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "Task Handling Cue:",
            "- Continue current task: no task state change.",
            "- Clear new task with no active current task: use $task-management and task.propose(start).",
            "- Clear switch away from current task: use $task-management and task.propose(switch).",
            "- Pending switch answer: use task.confirm.",
            "- Unclear: no task mutation.",
        ]
    )
    return "\n".join(lines)


def render_stop_task_tui(snapshot: Mapping[str, Any], previous_turn: Mapping[str, Any]) -> str:
    current_task = _as_mapping(snapshot.get("current_task"))
    progress = snapshot.get("progress_summary")
    if not isinstance(progress, str):
        progress = ""

    lines: list[str] = [
        "[TASK CHECKOUT]",
        f"Previous turn completed: {_turn_id(previous_turn)}",
        "",
        "Active task",
    ]

    if current_task is None:
        lines.extend(
            [
                "  none",
                "  no active task is present; no task update is needed by default.",
            ]
        )
    else:
        lines.extend(
            [
                f"  {current_task.get('id') or 'unknown'}",
                f"  Status: {current_task.get('status') or snapshot.get('task_state') or 'none'}",
                f"  Progress: {progress or current_task.get('summary') or current_task.get('body_excerpt') or 'none'}",
                f"  Last event: {_short_event(snapshot.get('last_event'))}",
            ]
        )

    lines.extend(
        [
            "",
            "Decision",
            "  Done -> $task-management + task.propose(finish)",
            "  Blocked -> $task-management + task.propose(block)",
            "  Continue -> no task update",
            "",
            "Limits",
            "  No start / switch / confirm in checkout.",
            "  Stay silent if no task update is needed.",
        ]
    )
    return "\n".join(lines)
