"""Task Sys-owned client and CLI for actor daemon runtime commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


SCRIPTS = Path(__file__).resolve().parents[2]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tool_runtime import daemon_client  # noqa: E402
from env.tool_runtime import task_sys_runtime_protocol as task_protocol  # noqa: E402


TASK_SYS_RESPONSE_TIMEOUT_SECONDS = 65.0


class TaskSysRuntimeClientError(RuntimeError):
    def __init__(self, code: str, message: str, *, response: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.response = dict(response) if response is not None else None


def _result(envelope: Mapping[str, object], *, fallback_code: str) -> dict[str, Any]:
    if envelope.get("ok") is not True:
        error = envelope.get("error")
        error_payload = error if isinstance(error, Mapping) else {}
        code = error_payload.get("code")
        message = error_payload.get("message")
        raise TaskSysRuntimeClientError(
            code if isinstance(code, str) and code else fallback_code,
            message if isinstance(message, str) and message else "Task Sys runtime command failed",
            response=envelope,
        )
    result = envelope.get("result")
    if not isinstance(result, Mapping):
        raise TaskSysRuntimeClientError(
            "task_sys_runtime_protocol_error",
            "Task Sys runtime success missing result object",
            response=envelope,
        )
    return dict(result)


def execute_instruction(
    *,
    instance_root: Path,
    instruction: Mapping[str, object],
    socket_path: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(instruction, Mapping):
        raise ValueError("instruction must be an object")
    root = Path(instance_root)
    envelope = daemon_client.request_mailbox(
        task_protocol.EXECUTE_INSTRUCTION,
        {"instruction": dict(instruction)},
        socket_path=Path(socket_path) if socket_path is not None else daemon_client.mailbox_socket_path_for_instance_root(root),
        response_timeout_seconds=TASK_SYS_RESPONSE_TIMEOUT_SECONDS,
    )
    return _result(envelope, fallback_code="task_sys_execute_error")


def cleanup_side_lease(
    *,
    instance_root: Path,
    task_id: str,
    socket_path: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id must be a non-empty string")
    root = Path(instance_root)
    envelope = daemon_client.request_mailbox(
        task_protocol.CLEANUP_SIDE_LEASE,
        {"task_id": task_id.strip()},
        socket_path=Path(socket_path) if socket_path is not None else daemon_client.mailbox_socket_path_for_instance_root(root),
        response_timeout_seconds=TASK_SYS_RESPONSE_TIMEOUT_SECONDS,
    )
    return _result(envelope, fallback_code="task_sys_cleanup_error")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--instance-root", required=True)
    execute.add_argument("--instruction-json", required=True)
    execute.add_argument("--socket")
    cleanup = subparsers.add_parser("cleanup-side-lease")
    cleanup.add_argument("--instance-root", required=True)
    cleanup.add_argument("--task-id", required=True)
    cleanup.add_argument("--socket")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "execute":
            instruction = json.loads(args.instruction_json)
            if not isinstance(instruction, dict):
                raise ValueError("--instruction-json must decode to an object")
            result = execute_instruction(
                instance_root=Path(args.instance_root),
                instruction=instruction,
                socket_path=Path(args.socket) if args.socket else None,
            )
        else:
            result = cleanup_side_lease(
                instance_root=Path(args.instance_root),
                task_id=args.task_id,
                socket_path=Path(args.socket) if args.socket else None,
            )
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (TaskSysRuntimeClientError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
