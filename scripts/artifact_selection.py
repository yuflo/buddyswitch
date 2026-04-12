#!/usr/bin/env python3
"""Deterministic artifact selection for track-centric BuddySwitch runs."""

from __future__ import annotations

import argparse
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "framework" / "config" / "artifact-selection-v1.json"


@lru_cache(maxsize=1)
def _selection_config() -> dict[str, Any]:
    payload = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact selection config must be a JSON object")

    selection_mode = payload.get("selection_mode")
    upstream = payload.get("default_buddy_upstream")
    continuation = payload.get("continuation_buddies")
    hints = payload.get("history_hints")
    max_default_items = payload.get("max_default_items")
    if not isinstance(selection_mode, str) or not selection_mode:
        raise ValueError("artifact selection config requires non-empty selection_mode")
    if not isinstance(upstream, dict):
        raise ValueError("artifact selection config requires object default_buddy_upstream")
    for buddy, rows in upstream.items():
        if not isinstance(buddy, str) or not buddy:
            raise ValueError("artifact selection config has invalid buddy key")
        if not isinstance(rows, list) or any(not isinstance(item, str) or not item for item in rows):
            raise ValueError("artifact selection config default_buddy_upstream values must be non-empty string lists")
    if not isinstance(continuation, list) or any(not isinstance(item, str) or not item for item in continuation):
        raise ValueError("artifact selection config continuation_buddies must be a non-empty string list")
    if not isinstance(hints, list) or any(not isinstance(item, str) or not item for item in hints):
        raise ValueError("artifact selection config history_hints must be a non-empty string list")
    if not isinstance(max_default_items, int) or max_default_items <= 0:
        raise ValueError("artifact selection config max_default_items must be a positive integer")
    return payload


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _extract_tasks(track_artifact_index: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(track_artifact_index, dict):
        return []
    rows = []
    for task in _as_list(track_artifact_index.get("tasks")):
        if isinstance(task, dict):
            rows.append(task)
    return rows


def _all_artifacts(task: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for artifact in _as_list(task.get("artifacts")):
        if isinstance(artifact, dict):
            rows.append(artifact)
    rows.sort(key=lambda row: (_as_str(row.get("updated_at")), _as_str(row.get("artifact_id"))), reverse=True)
    return rows


def _latest_artifact(task: dict[str, Any]) -> dict[str, Any] | None:
    artifacts = _all_artifacts(task)
    for artifact in artifacts:
        if bool(artifact.get("is_latest")):
            return artifact
    return artifacts[0] if artifacts else None


def _first_previous_artifact(task: dict[str, Any]) -> dict[str, Any] | None:
    for artifact in _all_artifacts(task):
        if not bool(artifact.get("is_latest")):
            return artifact
    return None


def _task_buddy(task: dict[str, Any]) -> str:
    return _as_str(task.get("buddy")).strip().lower()


def _task_id(task: dict[str, Any]) -> str:
    return _as_str(task.get("task_id")).strip()


def _artifact_id(artifact: dict[str, Any]) -> str:
    return _as_str(artifact.get("artifact_id")).strip()


def _latest_task_artifact_for_buddy(tasks: list[dict[str, Any]], buddy: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    rows: list[tuple[str, str, dict[str, Any], dict[str, Any]]] = []
    for task in tasks:
        if _task_buddy(task) != buddy:
            continue
        latest = _latest_artifact(task)
        if latest is None:
            continue
        rows.append((_as_str(latest.get("updated_at")), _artifact_id(latest), task, latest))
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not rows:
        return None
    _, _, task, artifact = rows[0]
    return task, artifact


def _first_previous_for_buddy(tasks: list[dict[str, Any]], buddy: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    rows: list[tuple[str, str, dict[str, Any], dict[str, Any]]] = []
    for task in tasks:
        if _task_buddy(task) != buddy:
            continue
        previous = _first_previous_artifact(task)
        if previous is None:
            continue
        rows.append((_as_str(previous.get("updated_at")), _artifact_id(previous), task, previous))
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not rows:
        return None
    _, _, task, artifact = rows[0]
    return task, artifact


def _explicit_buddy_mentions(demand: str, buddies: set[str]) -> list[str]:
    lowered = demand.lower()
    mentions: list[tuple[int, str]] = []
    for buddy in sorted(buddies):
        # Treat explicit mentions as "<buddy> buddy" references only.
        match = re.search(rf"\b{re.escape(buddy)}\s*buddy\b", lowered)
        if match:
            mentions.append((match.start(), buddy))
    mentions.sort(key=lambda item: item[0])
    return [buddy for _, buddy in mentions]


def _contains_ascii_token(text: str, token: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _has_history_hint(demand: str, history_hints: list[str]) -> bool:
    lowered = demand.lower()
    for hint in history_hints:
        if re.search(r"[a-z0-9]", hint):
            if _contains_ascii_token(lowered, hint):
                return True
            continue
        if hint in lowered:
            return True
    return False


def select_artifacts_for_run(
    *,
    current_buddy: str,
    demand: str,
    track_artifact_index: dict[str, Any] | None,
    current_task_id: str | None = None,
    max_default_items: int | None = None,
) -> dict[str, Any]:
    config = _selection_config()
    selection_mode = str(config["selection_mode"])
    default_buddy_upstream = {
        str(key): [str(item) for item in value]
        for key, value in dict(config["default_buddy_upstream"]).items()
    }
    continuation_buddies = set(str(item) for item in list(config["continuation_buddies"]))
    history_hints = [str(item).lower() for item in list(config["history_hints"])]
    max_items = max_default_items if isinstance(max_default_items, int) and max_default_items > 0 else int(
        config["max_default_items"]
    )

    tasks = _extract_tasks(track_artifact_index)
    if not tasks:
        return {
            "selected_artifact_ids": [],
            "reasons": ["No track artifacts available."],
            "selection_mode": selection_mode,
        }

    available_buddies = {_task_buddy(task) for task in tasks if _task_buddy(task)}
    explicit_buddies = _explicit_buddy_mentions(demand, available_buddies)
    upstream = default_buddy_upstream.get(current_buddy, [])
    target_buddies = explicit_buddies or [buddy for buddy in upstream if buddy in available_buddies]

    selected_ids: list[str] = []
    reasons: list[str] = []
    selected_buddies: list[str] = []

    def add_selected(buddy: str, task: dict[str, Any], artifact: dict[str, Any], reason: str) -> None:
        artifact_id = _artifact_id(artifact)
        if not artifact_id or artifact_id in selected_ids:
            return
        selected_ids.append(artifact_id)
        selected_buddies.append(buddy)
        reasons.append(
            f"{reason}: {buddy} task {_task_id(task)} -> {artifact_id}"
        )

    for buddy in target_buddies:
        picked = _latest_task_artifact_for_buddy(tasks, buddy)
        if picked is None:
            continue
        task, artifact = picked
        reason = "Selected explicit buddy latest artifact" if explicit_buddies else "Selected upstream latest artifact"
        add_selected(buddy, task, artifact, reason)

    if current_task_id and current_buddy in continuation_buddies:
        task = next((item for item in tasks if _task_id(item) == current_task_id), None)
        if task is not None and _task_buddy(task) == current_buddy:
            latest = _latest_artifact(task)
            if latest is not None:
                add_selected(current_buddy, task, latest, "Selected continuation latest artifact")

    history_hint = _has_history_hint(demand, history_hints)
    if history_hint:
        for buddy in selected_buddies:
            picked = _first_previous_for_buddy(tasks, buddy)
            if picked is None:
                continue
            task, artifact = picked
            add_selected(buddy, task, artifact, "Selected historical artifact due to history hint")

    if len(selected_ids) > max_items:
        selected_ids = selected_ids[:max_items]
        reasons.append(f"Trimmed selection to max_default_items={max_items}.")

    return {
        "selected_artifact_ids": selected_ids,
        "reasons": reasons,
        "selection_mode": selection_mode,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("index file must be a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic track artifact selection helper.")
    parser.add_argument("--buddy", required=True, help="Current executing buddy id")
    parser.add_argument("--demand", required=True, help="Switch demand text")
    parser.add_argument("--index-file", type=Path, required=True, help="Path to track_artifact_index JSON")
    parser.add_argument("--current-task-id", help="Current task id when continuing an existing task")
    parser.add_argument("--max-default-items", type=int)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload = select_artifacts_for_run(
        current_buddy=args.buddy,
        demand=args.demand,
        track_artifact_index=_load_json(args.index_file),
        current_task_id=args.current_task_id,
        max_default_items=args.max_default_items,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
