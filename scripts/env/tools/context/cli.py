#!/usr/bin/env python3
"""context env.tool CLI registration."""

from __future__ import annotations

import argparse
from typing import Any

TOOL_ID = "context"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("context", help="Context env operations")
    context_sub = parser.add_subparsers(dest="operation", required=True)

    get = context_sub.add_parser("get", help="Get runless context sections")
    get.add_argument("--track-id")
    get.add_argument("--task-id")
    get.add_argument("--limit", type=int)
    get.set_defaults(_env_tool=TOOL_ID, _env_action="get", _env_payload_builder=_context_payload)

    summarize = context_sub.add_parser("summarize", help="Summarize runless context")
    summarize.add_argument("--track-id")
    summarize.add_argument("--task-id")
    summarize.add_argument("--limit", type=int)
    summarize.set_defaults(_env_tool=TOOL_ID, _env_action="summarize", _env_payload_builder=_context_payload)

    list_sources = context_sub.add_parser("list-sources", help="List context source descriptions")
    list_sources.set_defaults(_env_tool=TOOL_ID, _env_action="list_sources", _env_payload_builder=_empty_payload)


def _empty_payload(_args: argparse.Namespace) -> dict[str, Any]:
    return {}


def _context_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in ("track_id", "task_id", "limit"):
        value = getattr(args, field, None)
        if value is not None:
            payload[field] = value
    return payload
