#!/usr/bin/env python3
"""Deterministic artifact selection for track-centric BuddySwitch runs."""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "framework" / "config" / "artifact-selection-v2.json"


@lru_cache(maxsize=1)
def _selection_config() -> dict[str, Any]:
    payload = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact selection config must be a JSON object")

    selection_mode = payload.get("selection_mode")
    history_hints = payload.get("history_hints")
    max_default_items = payload.get("max_default_items")
    if not isinstance(selection_mode, str) or not selection_mode:
        raise ValueError("artifact selection config requires non-empty selection_mode")
    if not isinstance(history_hints, list) or any(not isinstance(item, str) or not item for item in history_hints):
        raise ValueError("artifact selection config history_hints must be a non-empty string list")
    if not isinstance(max_default_items, int) or max_default_items <= 0:
        raise ValueError("artifact selection config max_default_items must be a positive integer")
    return payload


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


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


def _latest_current_artifact_for_slot(
    tasks: list[dict[str, Any]],
    slot: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    rows: list[tuple[str, str, dict[str, Any], dict[str, Any]]] = []
    for task in tasks:
        for artifact in _all_artifacts(task):
            if _as_str(artifact.get("slot")) != slot or not bool(artifact.get("is_current")):
                continue
            rows.append(
                (
                    _as_str(artifact.get("updated_at")),
                    _as_str(artifact.get("artifact_id")),
                    task,
                    artifact,
                )
            )
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not rows:
        return None
    _, _, task, artifact = rows[0]
    return task, artifact


def select_artifacts_for_run(
    *,
    current_buddy: str,
    demand: str,
    required_slots: list[str],
    track_artifact_index: dict[str, Any] | None,
    current_task_id: str | None = None,
    max_default_items: int | None = None,
) -> dict[str, Any]:
    del current_buddy
    del demand
    del current_task_id

    config = _selection_config()
    selection_mode = str(config["selection_mode"])
    max_items = max_default_items if isinstance(max_default_items, int) and max_default_items > 0 else int(
        config["max_default_items"]
    )

    tasks = _extract_tasks(track_artifact_index)
    if not tasks:
        return {
            "selected_inputs": [],
            "reasons": ["No track artifacts available."],
            "selection_mode": selection_mode,
        }

    selected_inputs: list[dict[str, Any]] = []
    reasons: list[str] = []
    seen_artifact_ids: set[str] = set()

    for slot in required_slots:
        if not isinstance(slot, str) or not slot:
            continue
        picked = _latest_current_artifact_for_slot(tasks, slot)
        if picked is None:
            continue
        task, artifact = picked
        artifact_id = _as_str(artifact.get("artifact_id"))
        if not artifact_id or artifact_id in seen_artifact_ids:
            continue
        seen_artifact_ids.add(artifact_id)
        selected_inputs.append(
            {
                "slot": slot,
                "artifact_id": artifact_id,
                "revision": _as_int(artifact.get("revision")),
                "selection_reason": "current artifact for required upstream slot",
                "task_id": _as_str(task.get("task_id")),
                "buddy": _as_str(task.get("buddy")),
            }
        )
        reasons.append(f"Selected current artifact for required slot '{slot}': {artifact_id}")

    if len(selected_inputs) > max_items:
        selected_inputs = selected_inputs[:max_items]
        reasons.append(f"Trimmed selection to max_default_items={max_items}.")

    return {
        "selected_inputs": selected_inputs,
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
    parser.add_argument("--required-slot", action="append", dest="required_slots", default=[], help="Required input slot")
    parser.add_argument("--current-task-id", help="Current task id when continuing an existing task")
    parser.add_argument("--max-default-items", type=int)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload = select_artifacts_for_run(
        current_buddy=args.buddy,
        demand=args.demand,
        required_slots=args.required_slots,
        track_artifact_index=_load_json(args.index_file),
        current_task_id=args.current_task_id,
        max_default_items=args.max_default_items,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
