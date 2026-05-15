#!/usr/bin/env python3
"""Deterministic artifact selection for track-centric BuddySwitch runs."""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from itertools import combinations
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


def _current_artifacts_by_kind(task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    current_artifacts: dict[str, dict[str, Any]] = {}
    for artifact in _all_artifacts(task):
        kind = _as_str(artifact.get("kind"))
        if not kind or not bool(artifact.get("is_current")) or kind in current_artifacts:
            continue
        current_artifacts[kind] = artifact
    return current_artifacts


def _task_bundle_signature(
    task: dict[str, Any],
    current_artifacts: dict[str, dict[str, Any]],
    required_kinds: list[str],
) -> tuple[int, str, str, str]:
    covered_kinds = [kind for kind in required_kinds if kind in current_artifacts]
    newest_updated_at, newest_artifact_id = max(
        (
            _as_str(current_artifacts[kind].get("updated_at")),
            _as_str(current_artifacts[kind].get("artifact_id")),
        )
        for kind in covered_kinds
    )
    return (
        len(covered_kinds),
        newest_updated_at,
        newest_artifact_id,
        _as_str(task.get("task_id")),
    )


def _pick_best_task_cover(
    tasks: list[dict[str, Any]],
    required_kinds: list[str],
) -> list[tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]]:
    bundle_rows: list[tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]] = []
    for task in tasks:
        current_artifacts = _current_artifacts_by_kind(task)
        covered_kinds = [kind for kind in required_kinds if kind in current_artifacts]
        if covered_kinds:
            bundle_rows.append((task, current_artifacts, covered_kinds))

    if not bundle_rows:
        return []

    best_combo: tuple[int, int, tuple[tuple[int, str, str, str], ...], tuple[str, ...]] | None = None
    best_rows: list[tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]] = []

    for combo_size in range(1, len(bundle_rows) + 1):
        for combo in combinations(bundle_rows, combo_size):
            covered = {kind for _, _, kinds in combo for kind in kinds}
            ranked_rows = sorted(
                combo,
                key=lambda row: _task_bundle_signature(row[0], row[1], required_kinds),
                reverse=True,
            )
            row_signatures = tuple(
                _task_bundle_signature(task, current_artifacts, required_kinds)
                for task, current_artifacts, _ in ranked_rows
            )
            task_ids = tuple(_as_str(task.get("task_id")) for task, _, _ in ranked_rows)
            combo_score = (
                len(covered),
                -len(ranked_rows),
                row_signatures,
                task_ids,
            )
            if best_combo is None or combo_score > best_combo:
                best_combo = combo_score
                best_rows = ranked_rows

    return best_rows


def select_artifacts_for_run(
    *,
    current_buddy: str,
    demand: str,
    required_kinds: list[str],
    track_artifact_index: dict[str, Any] | None,
    task_id_scope: str | None = None,
    max_default_items: int | None = None,
) -> dict[str, Any]:
    del current_buddy
    del demand
    del task_id_scope

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
    required_kinds_in_order = [kind for kind in required_kinds if isinstance(kind, str) and kind]
    selected_by_kind: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    bundle_rows = _pick_best_task_cover(tasks, required_kinds_in_order)

    for task, current_artifacts, covered_kinds in bundle_rows:
        for kind in covered_kinds:
            artifact = current_artifacts[kind]
            artifact_id = _as_str(artifact.get("artifact_id"))
            if not artifact_id or artifact_id in seen_artifact_ids or kind in selected_by_kind:
                continue
            seen_artifact_ids.add(artifact_id)
            selected_by_kind[kind] = (task, artifact)

    for kind in required_kinds_in_order:
        picked = selected_by_kind.get(kind)
        if picked is None:
            continue
        if any(item["kind"] == kind for item in selected_inputs):
            continue
        task, artifact = picked
        artifact_id = _as_str(artifact.get("artifact_id"))
        selected_inputs.append(
            {
                "kind": kind,
                "artifact_id": artifact_id,
                "revision": _as_int(artifact.get("revision")),
                "selection_reason": "current artifact for required upstream kind",
                "task_id": _as_str(task.get("task_id")),
                "buddy": _as_str(task.get("buddy")),
            }
        )
        reasons.append(f"Selected current artifact for required kind '{kind}': {artifact_id}")

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
    parser.add_argument("--demand", required=True, help="Turn request text")
    parser.add_argument("--index-file", type=Path, required=True, help="Path to track_artifact_index JSON")
    parser.add_argument("--required-kind", action="append", dest="required_kinds", default=[], help="Required input kind")
    parser.add_argument("--current-task-id", dest="task_id_scope", help="Task scope id when continuing an existing task")
    parser.add_argument("--max-default-items", type=int)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload = select_artifacts_for_run(
        current_buddy=args.buddy,
        demand=args.demand,
        required_kinds=args.required_kinds,
        track_artifact_index=_load_json(args.index_file),
        task_id_scope=args.task_id_scope,
        max_default_items=args.max_default_items,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
