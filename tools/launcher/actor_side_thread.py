#!/usr/bin/env python3
"""Actor-aware side-thread creation boundary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

import actor_model_config  # noqa: E402
import side_thread_lifecycle  # noqa: E402


class ActorSideThreadError(RuntimeError):
    """Raised when actor-aware side-thread setup fails before lifecycle start."""


def start_actor_side_thread(
    *,
    socket_path: Path,
    instance_json: Path,
    actor_id: str,
    parent_thread_id: str,
    text: str,
    purpose: str,
    workspace_dir: Path,
    shared_project_workspace_dir: Path,
    permissions: str,
    task_id: str | None = None,
    model: str | None = None,
    model_reasoning_effort: str | None = None,
) -> dict[str, Any]:
    try:
        options = actor_model_config.resolve_side_options(
            instance_json,
            explicit_model=model,
            explicit_effort=model_reasoning_effort,
        )
    except actor_model_config.ActorModelConfigError as exc:
        raise ActorSideThreadError(f"side model config invalid: {exc}") from exc

    payload = side_thread_lifecycle.start_side_thread(
        socket_path=socket_path,
        instance_json=instance_json,
        actor_id=actor_id,
        parent_thread_id=parent_thread_id,
        text=text,
        purpose=purpose,
        workspace_dir=workspace_dir,
        shared_project_workspace_dir=shared_project_workspace_dir,
        permissions=permissions,
        task_id=task_id,
        model=options.model,
        model_reasoning_effort=options.effort,
    )
    return actor_model_config.apply_side_source_metadata(payload, options)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=True))


def _command_start(args: argparse.Namespace) -> int:
    _print_json(
        start_actor_side_thread(
            socket_path=Path(args.socket),
            instance_json=Path(args.instance_json),
            actor_id=args.actor_id,
            parent_thread_id=args.parent_thread_id,
            text=args.text,
            purpose=args.purpose,
            workspace_dir=Path(args.workspace_dir),
            shared_project_workspace_dir=Path(args.shared_project_workspace_dir),
            permissions=args.permissions,
            task_id=args.task_id,
            model=args.model,
            model_reasoning_effort=args.effort,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--socket", required=True)
    start.add_argument("--instance-json", required=True)
    start.add_argument("--actor-id", required=True)
    start.add_argument("--parent-thread-id", required=True)
    start.add_argument("--text", required=True)
    start.add_argument("--purpose", required=True)
    start.add_argument("--workspace-dir", required=True)
    start.add_argument("--shared-project-workspace-dir", required=True)
    start.add_argument("--permissions", required=True)
    start.add_argument("--task-id")
    start.add_argument("--model")
    start.add_argument("--effort")
    start.set_defaults(func=_command_start)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
