"""BuddySwitch env.tool stdio MCP server."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tool_runtime import native_mcp  # noqa: E402
from runtime_kernel.client import RuntimeBrokerError, request_runtime_broker  # noqa: E402


MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "buddyswitch-env"
Dispatcher = Callable[..., dict[str, Any]]


class McpToolDispatchError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expose BuddySwitch env actions as native MCP tools.")
    parser.add_argument("--repo-root", help="BuddySwitch repo root for diagnostics.")
    parser.add_argument("--actor-id", help="Active BuddySwitch actor id.")
    parser.add_argument("--role", help="Active BuddySwitch role id.")
    parser.add_argument("--broker-socket", help="Runtime broker Unix socket path.")
    return parser.parse_args(argv)


def apply_runtime_env(args: argparse.Namespace) -> None:
    if isinstance(args.actor_id, str) and args.actor_id.strip():
        os.environ["BUDDYSWITCH_ACTOR_ID"] = args.actor_id.strip()
    if isinstance(args.role, str) and args.role.strip():
        os.environ["BUDDYSWITCH_ROLE_ID"] = args.role.strip()
    if isinstance(args.broker_socket, str) and args.broker_socket.strip():
        os.environ["BUDDYSWITCH_RUNTIME_BROKER_SOCKET"] = args.broker_socket.strip()
    if isinstance(args.repo_root, str) and args.repo_root.strip():
        os.environ["BUDDYSWITCH_REPO_ROOT"] = args.repo_root.strip()


def mcp_text_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
            }
        ],
        "isError": bool(is_error),
    }


def rpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def tool_error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    for key, value in (details or {}).items():
        if key in {"code", "message"}:
            continue
        payload[key] = value
    return payload


def default_dispatcher(
    *,
    tool: str,
    action: str,
    args: dict[str, Any],
    invocation: dict[str, str],
) -> dict[str, Any]:
    try:
        return request_runtime_broker(
            "env.tool",
            {
                "tool": tool,
                "action": action,
                "args": args,
                "invocation": invocation,
            },
        )
    except RuntimeBrokerError as exc:
        details = dict(exc.details)
        if exc.response:
            for key, value in exc.response.items():
                if key not in {"protocol", "request_id", "ok", "error"}:
                    details[key] = value
        raise McpToolDispatchError(exc.code, exc.message, details=details) from exc


def _handle_initialize(request_id: Any) -> dict[str, Any]:
    return rpc_result(
        request_id,
        {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": "1.0.0"},
        },
    )


def _handle_tools_list(request_id: Any) -> dict[str, Any]:
    return rpc_result(request_id, {"tools": native_mcp.list_native_tool_specs()})


def _handle_tools_call(request_id: Any, params: Any, dispatcher: Dispatcher) -> dict[str, Any]:
    if not isinstance(params, dict):
        return rpc_result(
            request_id,
            mcp_text_result(
                tool_error_payload("E_ENV_NATIVE_MCP_PARAMS", "tools/call params must be an object"),
                is_error=True,
            ),
        )
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(name, str) or not name.strip():
        return rpc_result(
            request_id,
            mcp_text_result(
                tool_error_payload("E_ENV_NATIVE_MCP_PARAMS", "tools/call params.name must be a non-empty string"),
                is_error=True,
            ),
        )
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return rpc_result(
            request_id,
            mcp_text_result(
                tool_error_payload("E_ENV_NATIVE_MCP_PARAMS", "tools/call params.arguments must be an object"),
                is_error=True,
            ),
        )
    try:
        meta = params.get("_meta", {})
        if not isinstance(meta, dict):
            raise ValueError("tools/call params._meta must be an object")
        turn_meta = meta.get("x-codex-turn-metadata", {})
        if not isinstance(turn_meta, dict):
            raise ValueError(
                "tools/call params._meta.x-codex-turn-metadata must be an object"
            )
        invocation: dict[str, str] = {"request_id": str(request_id)}
        for source, target in (
            (meta.get("threadId"), "thread_id"),
            (turn_meta.get("turn_id"), "turn_id"),
        ):
            if source is not None and (
                not isinstance(source, str) or not source.strip()
            ):
                raise ValueError(f"{target} must be a non-empty string")
            if isinstance(source, str):
                invocation[target] = source.strip()
        tool, action = native_mcp.resolve_native_tool_name(name)
    except (KeyError, ValueError) as exc:
        return rpc_result(
            request_id,
            mcp_text_result(
                tool_error_payload("E_ENV_NATIVE_MCP_UNKNOWN_TOOL", str(exc)),
                is_error=True,
            ),
        )

    try:
        result = dispatcher(
            tool=tool,
            action=action,
            args=arguments,
            invocation=invocation,
        )
    except McpToolDispatchError as exc:
        return rpc_result(
            request_id,
            mcp_text_result(tool_error_payload(exc.code, exc.message, exc.details), is_error=True),
        )
    except Exception as exc:
        return rpc_result(
            request_id,
            mcp_text_result(
                tool_error_payload("E_ENV_NATIVE_MCP_DISPATCH", str(exc)),
                is_error=True,
            ),
        )
    return rpc_result(request_id, mcp_text_result(result, is_error=False))


def handle_request(message: dict[str, Any], *, dispatcher: Dispatcher = default_dispatcher) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return rpc_error(None, -32600, "JSON-RPC message must be an object")
    request_id = message.get("id")
    method = message.get("method")
    if not isinstance(method, str):
        return rpc_error(request_id, -32600, "JSON-RPC method must be a string")
    if request_id is None:
        return None
    if method == "initialize":
        return _handle_initialize(request_id)
    if method == "tools/list":
        return _handle_tools_list(request_id)
    if method == "tools/call":
        return _handle_tools_call(request_id, message.get("params"), dispatcher)
    return rpc_error(request_id, -32601, f"unsupported method: {method}")


def run_stdio(*, dispatcher: Dispatcher = default_dispatcher) -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = rpc_error(None, -32700, f"invalid JSON: {exc.msg}")
        else:
            response = handle_request(message, dispatcher=dispatcher)
        if response is None:
            continue
        sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    apply_runtime_env(args)
    return run_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
