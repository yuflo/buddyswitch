#!/usr/bin/env python3
"""message env.tool CLI registration."""

from __future__ import annotations

import argparse
from typing import Any

from env.tools import cli_helpers

TOOL_ID = "message"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("message", help="Message env tool operations")
    message_sub = parser.add_subparsers(dest="operation", required=True)

    send = message_sub.add_parser("send", help="Send direct message to a buddy")
    cli_helpers.add_payload_argument(send)
    send.set_defaults(_env_tool=TOOL_ID, _env_action="send", _env_payload_builder=_json_payload)

    list_parser = message_sub.add_parser("list", help="List active-buddy inbox messages")
    list_parser.add_argument("--buddy")
    list_parser.set_defaults(_env_tool=TOOL_ID, _env_action="list", _env_payload_builder=_list_payload)


def _json_payload(args: argparse.Namespace) -> dict[str, Any]:
    return cli_helpers.load_json_object(args.payload)


def _list_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if isinstance(args.buddy, str) and args.buddy.strip():
        payload["buddy"] = args.buddy.strip()
    return payload
