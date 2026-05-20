#!/usr/bin/env python3
"""buddybox env.tool CLI registration."""

from __future__ import annotations

import argparse
from typing import Any

from env.tools import cli_helpers

TOOL_ID = "buddybox"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("buddybox", help="Buddybox env operations")
    buddybox_sub = parser.add_subparsers(dest="operation", required=True)

    desc = buddybox_sub.add_parser("desc", help="Describe active buddy private local workspace")
    desc.set_defaults(_env_tool=TOOL_ID, _env_action="desc", _env_payload_builder=_empty_payload)

    list_parser = buddybox_sub.add_parser("list", help="List buddybox files")
    list_parser.add_argument("--logical-name")
    list_parser.add_argument("--recursive", action="store_true")
    list_parser.add_argument("--limit", type=int)
    list_parser.set_defaults(_env_tool=TOOL_ID, _env_action="list", _env_payload_builder=_list_payload)

    read = buddybox_sub.add_parser("read", help="Read buddybox file")
    read.add_argument("--logical-name", required=True)
    read.add_argument("--encoding")
    read.set_defaults(_env_tool=TOOL_ID, _env_action="read", _env_payload_builder=_read_payload)

    write = buddybox_sub.add_parser("write", help="Write buddybox file")
    cli_helpers.add_payload_argument(write)
    write.set_defaults(_env_tool=TOOL_ID, _env_action="write", _env_payload_builder=_json_payload)

    delete = buddybox_sub.add_parser("delete", help="Delete buddybox file")
    delete.add_argument("--logical-name", required=True)
    delete.set_defaults(_env_tool=TOOL_ID, _env_action="delete", _env_payload_builder=_delete_payload)


def _empty_payload(_args: argparse.Namespace) -> dict[str, Any]:
    return {}


def _json_payload(args: argparse.Namespace) -> dict[str, Any]:
    return cli_helpers.load_json_object(args.payload)


def _read_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {"logical_name": args.logical_name}
    if isinstance(args.encoding, str) and args.encoding.strip():
        payload["encoding"] = args.encoding.strip()
    return payload


def _delete_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {"logical_name": args.logical_name}


def _list_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if isinstance(args.logical_name, str) and args.logical_name.strip():
        payload["logical_name"] = args.logical_name.strip()
    if args.recursive:
        payload["recursive"] = True
    if isinstance(args.limit, int):
        payload["limit"] = args.limit
    return payload
