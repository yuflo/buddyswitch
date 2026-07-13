"""Task Sys-owned adapter between generic daemon commands and Task runtime."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import daemon_contracts  # noqa: E402
import task_sys_runtime  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.tool_runtime import task_sys_runtime_protocol as task_protocol  # noqa: E402


def execute_instruction(
    context: daemon_contracts.DaemonContext,
    instruction: Mapping[str, object],
) -> dict[str, Any]:
    if not isinstance(instruction, Mapping):
        raise ValueError("instruction must be an object")
    result = task_sys_runtime.execute_instruction(context, dict(instruction))
    if not isinstance(result, dict):
        raise RuntimeError("Task Sys runtime returned a non-object result")
    return result


def cleanup_side_lease(
    context: daemon_contracts.DaemonContext,
    task_id: str,
) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task_id")
    result = task_sys_runtime.cleanup_side_lease(context, normalized_task_id)
    if not isinstance(result, dict):
        raise RuntimeError("Task Sys cleanup returned a non-object result")
    return result


def command_handlers(
    context: daemon_contracts.DaemonContext,
) -> Mapping[str, daemon_contracts.ApplicationCommand]:
    def execute(params: Mapping[str, object]) -> Mapping[str, object]:
        instruction = params.get("instruction")
        if not isinstance(instruction, Mapping):
            raise ValueError("instruction must be an object")
        return execute_instruction(context, instruction)

    def cleanup(params: Mapping[str, object]) -> Mapping[str, object]:
        task_id = params.get("task_id")
        return cleanup_side_lease(context, task_id if isinstance(task_id, str) else "")

    return {
        task_protocol.EXECUTE_INSTRUCTION: execute,
        task_protocol.CLEANUP_SIDE_LEASE: cleanup,
    }
