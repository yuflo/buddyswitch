#!/usr/bin/env python3
"""search env.tool CLI registration."""

from __future__ import annotations

import argparse
from typing import Any

TOOL_ID = "search"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "search",
        help="Search env operations",
        description="Search actions use --query (request/open-browser), --backend (request), and optional --engine.",
    )
    search_sub = parser.add_subparsers(dest="operation", required=True)

    status = search_sub.add_parser("status", help="Show runtime search configuration")
    status.set_defaults(_env_tool=TOOL_ID, _env_action="status", _env_payload_builder=_status_payload)

    request = search_sub.add_parser("request", help="Issue search request")
    request.add_argument("--query", required=True)
    request.add_argument("--backend", required=True, choices=["browser", "search_api"])
    request.add_argument("--engine", choices=["google", "web", "reddit", "x"])
    request.set_defaults(_env_tool=TOOL_ID, _env_action="request", _env_payload_builder=_request_payload)

    open_browser = search_sub.add_parser("open-browser", help="Open browser search URL")
    open_browser.add_argument("--query", required=True)
    open_browser.add_argument("--engine", choices=["google", "web", "reddit", "x"])
    open_browser.set_defaults(_env_tool=TOOL_ID, _env_action="open_browser", _env_payload_builder=_open_browser_payload)


def _status_payload(_args: argparse.Namespace) -> dict[str, Any]:
    return {}


def _request_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": args.query, "backend": args.backend}
    if isinstance(args.engine, str) and args.engine.strip():
        payload["engine"] = args.engine.strip()
    return payload


def _open_browser_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": args.query}
    if isinstance(args.engine, str) and args.engine.strip():
        payload["engine"] = args.engine.strip()
    return payload
