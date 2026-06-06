#!/usr/bin/env python3
"""TaskViewModel TUI renderer."""

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


def _pending_line(pending: Mapping[str, Any] | None) -> str:
    if pending is None:
        return "Pending Switch: none"
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
    return f"Pending Switch: {confirmation_id} -> {target_label}"


def _turn_id(previous_turn: Mapping[str, Any]) -> str:
    for key in ("turn_id", "id"):
        value = previous_turn.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def render_task_tui(view: Mapping[str, object]) -> str:
    current_anchor = _as_mapping(view.get("current_anchor"))
    shelf = view.get("shelf")
    pending_switch = _as_mapping(view.get("pending_switch"))
    recent_evidence = view.get("recent_evidence")
    recent_events = view.get("recent_events")
    available_actions = view.get("available_actions")
    checkout_cue = _as_mapping(view.get("checkout_cue"))
    warnings = view.get("warnings")

    lines: list[str] = ["[TASK CONTEXT]"]
    lines.append(f"Current Anchor: {_task_label(current_anchor)}")
    if current_anchor is None:
        lines.append(f"State: {view.get('task_state') or 'none'}")
        lines.append("Progress: none")
    else:
        lines.append(f"State: {current_anchor.get('status') or view.get('task_state') or 'none'}")
        lines.append(f"Progress: {current_anchor.get('progress_summary') or current_anchor.get('summary') or 'none'}")

    lines.append("")
    lines.append("Shelf:")
    if isinstance(shelf, list) and shelf:
        for task in shelf:
            label = _task_label(_as_mapping(task))
            lines.append(f"- {label}")
    else:
        lines.append("- none")

    lines.append(_pending_line(pending_switch))
    if isinstance(available_actions, list) and available_actions:
        lines.append("Available Actions: " + ", ".join(str(row) for row in available_actions))
    else:
        lines.append("Available Actions: none")

    choices = checkout_cue.get("choices") if checkout_cue is not None else None
    if isinstance(choices, list) and choices:
        lines.append("Checkout: task.checkout next=" + "|".join(str(row) for row in choices))
    else:
        lines.append("Checkout: none")

    lines.append("Recent Evidence:")
    if isinstance(recent_evidence, list) and recent_evidence:
        for row in recent_evidence:
            mapping = _as_mapping(row)
            if mapping is None:
                continue
            evidence = mapping.get("evidence") or mapping.get("reason") or "none"
            lines.append(f"- {mapping.get('task_id') or 'unknown'}: {evidence}")
    else:
        lines.append("- none")

    lines.append("Warnings:")
    if isinstance(warnings, list) and warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    lines.append("Recent Events:")
    if isinstance(recent_events, list) and recent_events:
        for event in recent_events:
            lines.append(f"- {_short_event(event)}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def render_stop_task_tui(view: Mapping[str, Any], previous_turn: Mapping[str, Any]) -> str:
    current_anchor = _as_mapping(view.get("current_anchor"))
    recent_events = view.get("recent_events")

    lines: list[str] = [
        "[TASK CHECKOUT]",
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
                f"  {current_anchor.get('id') or 'unknown'}",
                f"  Status: {current_anchor.get('status') or view.get('task_state') or 'none'}",
                f"  Progress: {current_anchor.get('progress_summary') or current_anchor.get('summary') or 'none'}",
                f"  Last event: {_short_event(recent_events[-1] if isinstance(recent_events, list) and recent_events else None)}",
            ]
        )

    lines.extend(
        [
            "",
            "Checkout",
            "  task.checkout next=continue",
            "  task.checkout next=finish",
            "  task.checkout next=block",
            "",
            "Limits",
            "  No capture, select, switch_request, or switch_confirm in checkout.",
            "  Stay silent if no checkout update is needed.",
        ]
    )
    return "\n".join(lines)
