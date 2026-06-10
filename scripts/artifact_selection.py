#!/usr/bin/env python3
"""Deterministic artifact selection for Track-related Artifact inputs."""

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


def _as_actor(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    actor_id = value.get("actor_id")
    role_id = value.get("role_id")
    if not isinstance(actor_id, str) or not actor_id:
        return None
    if not isinstance(role_id, str) or not role_id:
        return None
    return {"actor_id": actor_id, "role_id": role_id}


def _extract_artifacts(track_artifact_index: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(track_artifact_index, dict):
        return []
    rows = []
    source_rows = _as_list(track_artifact_index.get("artifacts"))
    if not source_rows:
        source_rows = _as_list(track_artifact_index.get("artifact_relations"))
    for artifact in source_rows:
        if isinstance(artifact, dict):
            rows.append(artifact)
    rows.sort(
        key=lambda row: (_as_str(row.get("updated_at")), _as_str(row.get("artifact_id"))),
        reverse=True,
    )
    return rows


def _select_template_rows(
    artifacts: list[dict[str, Any]],
    required_templates: list[str],
) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for template in required_templates:
        for artifact in artifacts:
            if _as_str(artifact.get("template")) != template:
                continue
            if not bool(artifact.get("is_current", artifact.get("current"))):
                continue
            selected[template] = artifact
            break
    return selected


def select_artifacts_for_run(
    *,
    active_role: str,
    demand: str,
    required_templates: list[str],
    track_artifact_index: dict[str, Any] | None,
    task_id_scope: str | None = None,
    max_default_items: int | None = None,
) -> dict[str, Any]:
    del active_role
    del demand
    del task_id_scope

    config = _selection_config()
    selection_mode = str(config["selection_mode"])
    max_items = max_default_items if isinstance(max_default_items, int) and max_default_items > 0 else int(
        config["max_default_items"]
    )

    artifacts = _extract_artifacts(track_artifact_index)
    if not artifacts:
        return {
            "selected_inputs": [],
            "reasons": ["No track artifacts available."],
            "selection_mode": selection_mode,
        }

    selected_inputs: list[dict[str, Any]] = []
    reasons: list[str] = []
    normalized_templates = [template for template in required_templates if isinstance(template, str) and template]
    selected_by_template = _select_template_rows(artifacts, normalized_templates)

    for template in normalized_templates:
        artifact = selected_by_template.get(template)
        if artifact is None:
            continue
        artifact_id = _as_str(artifact.get("artifact_id"))
        if any(item.get("artifact_id") == artifact_id for item in selected_inputs):
            continue
        selected_inputs.append(
            {
                "template": template,
                "artifact_id": artifact_id,
                "revision": _as_int(artifact.get("revision")),
                "selection_reason": "current track-related artifact for required upstream template",
                "created_by_actor": _as_actor(artifact.get("created_by_actor")),
            }
        )
        reasons.append(f"Selected current track-related artifact for required template '{template}': {artifact_id}")

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
    parser.add_argument("--role", required=True, help="Current executing role id")
    parser.add_argument("--demand", required=True, help="Turn request text")
    parser.add_argument("--index-file", type=Path, required=True, help="Path to track_artifact_index JSON")
    parser.add_argument(
        "--required-template",
        action="append",
        dest="required_templates",
        default=[],
        help="Required input template",
    )
    parser.add_argument("--current-task-id", dest="task_id_scope", help="Task scope id when continuing an existing task")
    parser.add_argument("--max-default-items", type=int)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload = select_artifacts_for_run(
        active_role=args.role,
        demand=args.demand,
        required_templates=args.required_templates,
        track_artifact_index=_load_json(args.index_file),
        task_id_scope=args.task_id_scope,
        max_default_items=args.max_default_items,
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
