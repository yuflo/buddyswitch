#!/usr/bin/env python3
"""Skill-facing CLI for broker-routed runless env tool operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from env.tools import discovery
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


def _register_tool_clis(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    for tool in discovery.discover_tool_ids():
        module = discovery.import_tool_module(tool, "cli")
        register = getattr(module, "register_cli", None)
        if not callable(register):
            raise TypeError(f"env.tools.{tool}.cli.register_cli must be callable")
        register(subparsers)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call broker-routed BuddySwitch env operations.")
    subparsers = parser.add_subparsers(dest="resource", required=True)
    _register_tool_clis(subparsers)
    return parser.parse_args()


def main() -> int:
    try:
        args = _parse_args()
        tool = getattr(args, "_env_tool", None)
        action = getattr(args, "_env_action", None)
        payload_builder = getattr(args, "_env_payload_builder", None)
        if not isinstance(tool, str) or not isinstance(action, str) or not callable(payload_builder):
            raise ValueError("selected CLI operation is not registered as an env.tool action")
        payload_fn: Callable[[argparse.Namespace], dict[str, Any]] = payload_builder
        payload = _dispatch_env_tool(tool, action, payload_fn(args))
    except Exception as exc:
        print(json.dumps(_error_payload("E_ENV_CLI", str(exc)), ensure_ascii=True, indent=2))
        return 1

    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
