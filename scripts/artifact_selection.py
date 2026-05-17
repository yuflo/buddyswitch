#!/usr/bin/env python3
"""Deterministic artifact selection for track-page BuddySwitch runs."""

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


def _extract_shared_materials(track_artifact_index: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(track_artifact_index, dict):
        return []
    rows: list[dict[str, Any]] = []
    for row in _as_list(track_artifact_index.get("shared_materials")):
        if not isinstance(row, dict):
            continue
        if row.get("type") != "artifact":
            continue
        if not bool(row.get("current")):
            continue
        artifact_id = _as_str(row.get("artifact_id"))
        kind = _as_str(row.get("kind"))
        if not artifact_id or not kind:
            continue
        rows.append(row)
    rows.sort(
        key=lambda item: (
            _as_str(item.get("published_at")),
            _as_str(item.get("artifact_id")),
        ),
        reverse=True,
    )
    return rows


def _pick_current_material_by_kind(shared_materials: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    picked: dict[str, dict[str, Any]] = {}
    for row in shared_materials:
        kind = _as_str(row.get("kind"))
        if kind and kind not in picked:
            picked[kind] = row
    return picked


def select_artifacts_for_run(
    *,
    active_buddy: str,
    demand: str,
    required_kinds: list[str],
    track_artifact_index: dict[str, Any] | None,
    max_default_items: int | None = None,
) -> dict[str, Any]:
    del active_buddy
    del demand

    config = _selection_config()
    selection_mode = str(config["selection_mode"])
    max_items = max_default_items if isinstance(max_default_items, int) and max_default_items > 0 else int(
        config["max_default_items"]
    )

    shared_materials = _extract_shared_materials(track_artifact_index)
    if not shared_materials:
        return {
            "selected_inputs": [],
            "reasons": ["No current shared materials are available on this track."],
            "selection_mode": selection_mode,
        }

    material_by_kind = _pick_current_material_by_kind(shared_materials)
    selected_inputs: list[dict[str, Any]] = []
    reasons: list[str] = []
    seen_kinds: set[str] = set()

    for required_kind in required_kinds:
        kind = _as_str(required_kind)
        if not kind or kind in seen_kinds:
            continue
        seen_kinds.add(kind)
        row = material_by_kind.get(kind)
        if row is None:
            continue
        artifact_id = _as_str(row.get("artifact_id"))
        selected_inputs.append(
            {
                "artifact_id": artifact_id,
                "kind": kind,
                "from_buddy": _as_str(row.get("from_buddy")),
                "label": _as_str(row.get("label")),
                "selection_reason": "current shared material for required kind",
            }
        )
        reasons.append(f"Selected current shared material for required kind '{kind}': {artifact_id}")

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
    parser.add_argument("--max-default-items", type=int)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload = select_artifacts_for_run(
        active_buddy=args.buddy,
        demand=args.demand,
        required_kinds=args.required_kinds,
        track_artifact_index=_load_json(args.index_file),
        max_default_items=args.max_default_items,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
