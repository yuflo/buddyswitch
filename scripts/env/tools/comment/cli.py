#!/usr/bin/env python3
"""comment env.tool CLI registration."""

from __future__ import annotations

import argparse
from typing import Any

from env.tools import cli_helpers

TOOL_ID = "comment"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("comment", help="Comment env tool operations")
    comment_sub = parser.add_subparsers(dest="operation", required=True)

    add = comment_sub.add_parser("add", help="Add comment to a track/artifact target")
    cli_helpers.add_payload_argument(add)
    add.set_defaults(_env_tool=TOOL_ID, _env_action="add", _env_payload_builder=_json_payload)

    list_parser = comment_sub.add_parser("list", help="List comments on one target")
    list_parser.add_argument("--target-type", required=True)
    list_parser.add_argument("--target-id", required=True)
    list_parser.add_argument("--status")
    list_parser.set_defaults(_env_tool=TOOL_ID, _env_action="list", _env_payload_builder=_list_payload)


def _json_payload(args: argparse.Namespace) -> dict[str, Any]:
    return cli_helpers.load_json_object(args.payload)


def _list_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {"target_type": args.target_type, "target_id": args.target_id}
    if isinstance(args.status, str) and args.status.strip():
        payload["status"] = args.status.strip()
    return payload
