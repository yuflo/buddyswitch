#!/usr/bin/env python3
"""task env.tool CLI registration."""

from __future__ import annotations

import argparse
from typing import Any

from env.tools import cli_helpers

TOOL_ID = "task"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("task", help="Task env tool operations")
    task_sub = parser.add_subparsers(dest="operation", required=True)

    create = task_sub.add_parser("create", help="Create active-buddy task")
    cli_helpers.add_payload_argument(create)
    create.set_defaults(_env_tool=TOOL_ID, _env_action="create", _env_payload_builder=_json_payload)

    list_parser = task_sub.add_parser("list", help="List active-buddy tasks")
    list_parser.add_argument("--status")
    list_parser.add_argument("--track-id")
    list_parser.add_argument("--limit", type=int)
    list_parser.set_defaults(_env_tool=TOOL_ID, _env_action="list", _env_payload_builder=_list_payload)

    get = task_sub.add_parser("get", help="Get active-buddy task by id")
    get.add_argument("--task-id", required=True)
    get.set_defaults(_env_tool=TOOL_ID, _env_action="get", _env_payload_builder=_task_id_payload)

    update = task_sub.add_parser("update", help="Update active-buddy task fields")
    cli_helpers.add_payload_argument(update)
    update.set_defaults(_env_tool=TOOL_ID, _env_action="update", _env_payload_builder=_json_payload)

    archive = task_sub.add_parser("archive", help="Archive active-buddy task")
    archive.add_argument("--task-id", required=True)
    archive.set_defaults(_env_tool=TOOL_ID, _env_action="archive", _env_payload_builder=_task_id_payload)


def _json_payload(args: argparse.Namespace) -> dict[str, Any]:
    return cli_helpers.load_json_object(args.payload)


def _task_id_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {"task_id": args.task_id}


def _list_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in ("status", "track_id", "limit"):
        value = getattr(args, field, None)
        if value is not None:
            payload[field] = value
    return payload
