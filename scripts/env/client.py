#!/usr/bin/env python3
"""Skill-facing CLI for broker-routed runless env tool operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from env.tool_runtime import registry as tool_registry
from runtime_kernel.client import RuntimeBrokerError, broker_unavailable_feedback, request_runtime_broker


def _error_payload(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {"code": code, "message": message},
    }
    if not extra:
        return payload
    top_level = {
        "tool",
        "action",
        "permission_boundary",
        "allowed_next_actions",
        "allowed_next_action_options",
        "command_hint",
        "stop_condition",
        "request_id",
        "retriable",
        "retry_after_ms",
        "feedback",
        "broker_status",
    }
    for key, value in extra.items():
        if key in {"code", "message"}:
            continue
        if key in top_level:
            payload[key] = value
        else:
            payload["error"][key] = value
    return payload


def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--payload must be a JSON object string: {exc.msg} at char {exc.pos}") from exc
    if not isinstance(payload, dict):
        raise ValueError("--payload must be a JSON object string")
    return payload


def _dispatch_env_tool(tool: str, action: str, args: dict[str, Any]) -> dict[str, Any]:
    params = {
        "tool": tool,
        "action": action,
        "args": args,
    }
    try:
        return request_runtime_broker("env.tool", params)
    except RuntimeBrokerError as exc:
        extra: dict[str, Any] = dict(exc.details)
        if exc.response and isinstance(exc.response, dict):
            for key, value in exc.response.items():
                if key in {"protocol", "request_id", "ok", "error"}:
                    continue
                extra[key] = value
        if exc.code == "E_RUNTIME_BROKER_UNAVAILABLE":
            unavailable = broker_unavailable_feedback()
            unavailable.update(extra)
            extra = unavailable
        return _error_payload(exc.code, exc.message, extra)


def _register_tool_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    for tool in sorted(tool_registry.supported_tools()):
        parser = subparsers.add_parser(tool, help=f"{tool} operations")
        parser.set_defaults(_env_tool=tool)
        tool_sub = parser.add_subparsers(dest="action", required=True)
        for action in sorted(tool_registry.supported_actions(tool)):
            cli_action = action.replace("_", "-")
            action_parser = tool_sub.add_parser(cli_action, help=f"{tool}.{action}")
            action_parser.add_argument(
                "--payload",
                required=False,
                metavar="JSON_OBJECT",
                help="JSON object string to send as env.tool args; do not pass a file path.",
            )
            action_parser.set_defaults(_env_action=action)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call broker-routed BuddySwitch env operations.")
    subparsers = parser.add_subparsers(dest="tool", required=True)
    _register_tool_subcommands(subparsers)
    return parser.parse_args()


def main() -> int:
    try:
        args = _parse_args()
        tool = getattr(args, "_env_tool", None)
        action = getattr(args, "_env_action", None)
        raw_payload = getattr(args, "payload", None)
        if not isinstance(tool, str) or not isinstance(action, str):
            raise ValueError("selected CLI operation is not registered as an env.tool action")

        payload = {} if raw_payload is None else _load_json_object(raw_payload)
        response = _dispatch_env_tool(tool, action, payload)
    except Exception as exc:
        print(json.dumps(_error_payload("E_ENV_CLI", str(exc)), ensure_ascii=True, indent=2))
        return 1

    print(json.dumps(response, ensure_ascii=True, indent=2))
    return 0 if response.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
