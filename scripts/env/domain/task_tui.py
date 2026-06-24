#!/usr/bin/env python3
"""Task checkpoint prompt renderer."""

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


def _task_label(task: Mapping[str, Any] | None) -> str:
    if task is None:
        return "none"
    task_id = task.get("id")
    title = task.get("title")
    if isinstance(task_id, str) and isinstance(title, str) and title:
        return f"{task_id} - {title}"
    if isinstance(task_id, str):
        return task_id
    return "unknown"


def _turn_id(previous_turn: Mapping[str, Any]) -> str:
    for key in ("turn_id", "id"):
        value = previous_turn.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def render_stop_task_tui(view: Mapping[str, Any], previous_turn: Mapping[str, Any]) -> str:
    current_anchor = _as_mapping(view.get("current_anchor"))
    recent_events = view.get("recent_events")
    recent_evidence = view.get("recent_evidence")

    lines: list[str] = [
        "[TASK CHECKPOINT]",
        f"Previous turn completed: {_turn_id(previous_turn)}",
        "",
        "Active task",
    ]

    if current_anchor is None:
        lines.extend(
            [
                "  none",
                "  no active task is present; no checkout update is needed by default.",
            ]
        )
    else:
        lines.extend(
            [
                f"  {_task_label(current_anchor)}",
                f"  Status: {current_anchor.get('status') or view.get('task_state') or 'none'}",
                f"  Progress: {current_anchor.get('progress_summary') or current_anchor.get('summary') or 'none'}",
                f"  Last event: {_short_event(recent_events[-1] if isinstance(recent_events, list) and recent_events else None)}",
            ]
        )

    lines.append("")
    lines.append("Recent evidence")
    if isinstance(recent_evidence, list) and recent_evidence:
        for row in recent_evidence:
            mapping = _as_mapping(row)
            if mapping is None:
                continue
            evidence = mapping.get("evidence") or mapping.get("reason") or "none"
            lines.append(f"  - {mapping.get('task_id') or 'unknown'}: {evidence}")
    else:
        lines.append("  - none")

    lines.extend(
        [
            "",
            "Intent",
            "  Use this checkpoint to decide the next useful action from the current task state.",
            "  If the task is active, keep working in this turn when there is a clear path forward.",
            "",
            "When stopping",
            "  task.progress: record meaningful new progress or evidence.",
            "  task.checkout finish: the deliverable is complete; include evidence.",
            "  task.checkout block: progress is blocked; include reason.",
            "  task.checkout continue: pause an unfinished task; name the next concrete action or waiting condition.",
        ]
    )
    return "\n".join(lines)
