"""Thread-scoped MCP server for committing one Demand ingress decision."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from runtime_kernel.client import RuntimeBrokerError, request_runtime_broker  # noqa: E402


MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "buddyswitch-demand-triage"
CAPABILITY_ENV = "BUDDYSWITCH_DEMAND_TRIAGE_CAPABILITY"
Dispatcher = Callable[..., dict[str, Any]]

RESOLVE_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "decision",
        "reason",
        "demand_ref",
        "description",
        "detail",
        "reply_content",
    ],
    "properties": {
        "decision": {
            "type": "string",
            "enum": [
                "no_action_needed",
                "handled",
                "create",
                "merge_intake",
                "revise",
                "cancel",
            ],
        },
        "reason": {"type": "string"},
        "demand_ref": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "detail": {"type": ["string", "null"]},
        "reply_content": {"type": ["string", "null"]},
    },
}

RESOLVE_TOOL = {
    "name": "resolve",
    "description": (
        "Commit exactly one decision for the current isolated Demand ingress. "
        "Call this once before ending the triage turn."
    ),
    "inputSchema": RESOLVE_INPUT_SCHEMA,
}


class DemandTriageMcpError(RuntimeError):
    """Normalized error returned as MCP tool content."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker-socket", help="Runtime broker Unix socket path.")
    return parser.parse_args(argv)


def apply_runtime_env(args: argparse.Namespace) -> None:
    if isinstance(args.broker_socket, str) and args.broker_socket.strip():
        os.environ["BUDDYSWITCH_RUNTIME_BROKER_SOCKET"] = args.broker_socket.strip()


def _capability() -> str:
    value = os.environ.get(CAPABILITY_ENV)
    if not isinstance(value, str) or not value.strip():
        raise DemandTriageMcpError(
            "E_DEMAND_TRIAGE_CAPABILITY",
            f"{CAPABILITY_ENV} is required",
        )
    return value.strip()


def default_dispatcher(
    *,
    capability: str,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    try:
        return request_runtime_broker(
            "demand.ingress.resolve",
            {
                "capability": capability,
                "proposal": proposal,
            },
            idempotency_key=(
                "demand-ingress-resolve:"
                + hashlib.sha256(capability.encode("utf-8")).hexdigest()
            ),
        )
    except RuntimeBrokerError as exc:
        details = dict(exc.details)
        if exc.response:
            for key, value in exc.response.items():
                if key not in {"protocol", "request_id", "ok", "error"}:
                    details[key] = value
        raise DemandTriageMcpError(
            exc.code,
            exc.message,
            details=details,
        ) from exc


def _rpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _tool_result(payload: dict[str, Any], *, is_error: bool) -> dict[str, Any]:
    return {
        "content": [{
            "type": "text",
            "text": json.dumps(
                payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ),
        }],
        "isError": is_error,
    }


def _tool_error(error: DemandTriageMcpError) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {"code": error.code, "message": error.message},
    }
    payload.update(error.details)
    return payload


def _handle_call(
    request_id: Any,
    params: Any,
    dispatcher: Dispatcher,
) -> dict[str, Any]:
    if not isinstance(params, dict):
        return _rpc_result(
            request_id,
            _tool_result(
                _tool_error(DemandTriageMcpError(
                    "E_DEMAND_TRIAGE_PARAMS",
                    "tools/call params must be an object",
                )),
                is_error=True,
            ),
        )
    if params.get("name") != "resolve":
        return _rpc_result(
            request_id,
            _tool_result(
                _tool_error(DemandTriageMcpError(
                    "E_DEMAND_TRIAGE_UNKNOWN_TOOL",
                    f"unknown tool: {params.get('name')!r}",
                )),
                is_error=True,
            ),
        )
    proposal = params.get("arguments")
    if not isinstance(proposal, dict):
        return _rpc_result(
            request_id,
            _tool_result(
                _tool_error(DemandTriageMcpError(
                    "E_DEMAND_TRIAGE_PARAMS",
                    "resolve arguments must be an object",
                )),
                is_error=True,
            ),
        )
    try:
        result = dispatcher(
            capability=_capability(),
            proposal=dict(proposal),
        )
    except DemandTriageMcpError as exc:
        return _rpc_result(
            request_id,
            _tool_result(_tool_error(exc), is_error=True),
        )
    except Exception as exc:
        return _rpc_result(
            request_id,
            _tool_result(
                _tool_error(DemandTriageMcpError(
                    "E_DEMAND_TRIAGE_DISPATCH",
                    str(exc),
                )),
                is_error=True,
            ),
        )
    return _rpc_result(request_id, _tool_result(result, is_error=False))


def handle_request(
    message: dict[str, Any],
    *,
    dispatcher: Dispatcher = default_dispatcher,
) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return _rpc_error(None, -32600, "JSON-RPC message must be an object")
    request_id = message.get("id")
    method = message.get("method")
    if not isinstance(method, str):
        return _rpc_error(request_id, -32600, "JSON-RPC method must be a string")
    if request_id is None:
        return None
    if method == "initialize":
        return _rpc_result(
            request_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": "1.0.0"},
            },
        )
    if method == "tools/list":
        return _rpc_result(request_id, {"tools": [RESOLVE_TOOL]})
    if method == "tools/call":
        return _handle_call(request_id, message.get("params"), dispatcher)
    return _rpc_error(request_id, -32601, f"unsupported method: {method}")


def run_stdio(*, dispatcher: Dispatcher = default_dispatcher) -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _rpc_error(None, -32700, f"invalid JSON: {exc.msg}")
        else:
            response = handle_request(message, dispatcher=dispatcher)
        if response is None:
            continue
        sys.stdout.write(
            json.dumps(response, ensure_ascii=True, separators=(",", ":"))
            + "\n"
        )
        sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv if argv is not None else sys.argv[1:]))
    apply_runtime_env(args)
    return run_stdio()


if __name__ == "__main__":
    raise SystemExit(main())
