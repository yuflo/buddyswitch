"""Task-owned CLI registration over the external-safe read model."""

from __future__ import annotations

from collections.abc import Sequence

from buddyswitch.foundation.cli_runtime import contracts as cli_contract
from buddyswitch.foundation.host_control import runtime as host_control
import buddyswitch.foundation.identity.profiles as identity_profiles
from buddyswitch.modules.task.private import read_model


def _single_positional(
    args: Sequence[str],
    *,
    label: str,
    context: str,
) -> str:
    rows = list(args)
    if len(rows) != 1 or rows[0].startswith("-"):
        raise cli_contract.CliError(
            "INVALID_ARGUMENT",
            f"{context} requires <{label}>",
        )
    return rows[0]


def _actor_target(actor_id: str) -> dict[str, str] | None:
    try:
        normalized = host_control.validate_actor_id(actor_id)
    except host_control.HostControlError as exc:
        raise cli_contract.CliError("INVALID_ARGUMENT", str(exc)) from exc
    role_id = identity_profiles.get_actor_role_id(normalized)
    if role_id is None:
        return None
    return {"actor_id": normalized, "role_id": role_id}


def dispatch(args: Sequence[str]) -> cli_contract.CliCommandResult:
    rows = list(args)
    if not rows:
        raise cli_contract.CliError("UNKNOWN_COMMAND", "task command is required")
    command, rest = rows[0], rows[1:]
    try:
        if command == "list":
            actor_id = cli_contract.optional_single_option(
                rest,
                "--actor",
                "task list",
            )
            target = _actor_target(actor_id) if actor_id is not None else None
            tasks = (
                []
                if actor_id is not None and target is None
                else read_model.list_external_tasks(actor_target=target)
            )
            return cli_contract.CliCommandResult(
                "task.list",
                {"tasks": tasks},
            )
        if command == "get":
            task_id = _single_positional(
                rest,
                label="task id",
                context="task get",
            )
            task = read_model.get_external_task(task_id)
            if task is None:
                raise cli_contract.CliError(
                    "NOT_FOUND",
                    f"Task not found: {task_id}",
                    {"task_id": task_id},
                )
            return cli_contract.CliCommandResult("task.get", {"task": task})
    except ValueError as exc:
        raise cli_contract.CliError("INVALID_ARGUMENT", str(exc)) from exc
    raise cli_contract.CliError(
        "UNKNOWN_COMMAND",
        f"Unknown task command: {command}",
    )


REGISTRATION = cli_contract.CliCommandRegistration(
    name="task",
    help_rows=(
        "  buddyswitch-codex task list [--actor <actor-id>]",
        "  buddyswitch-codex task get <task-id>",
        "  task      Read external-safe Task projections.",
    ),
    handler=dispatch,
)
