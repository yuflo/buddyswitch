"""Demand-owned CLI registration over the current Demand read model."""

from __future__ import annotations

from collections.abc import Sequence

from buddyswitch.foundation.cli_runtime import contracts as cli_contract
from buddyswitch.foundation.host_control import runtime as host_control
import buddyswitch.foundation.identity.profiles as identity_profiles
from buddyswitch.modules.demand.private import read_model


def _required_actor(args: Sequence[str], *, context: str) -> str:
    return cli_contract.single_required_option(
        args,
        "--actor",
        context,
    ).strip()


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
        raise cli_contract.CliError("UNKNOWN_COMMAND", "demand command is required")
    command, rest = rows[0], rows[1:]
    try:
        if command == "list":
            actor_id = _required_actor(rest, context="demand list")
            actor_target = _actor_target(actor_id)
            return cli_contract.CliCommandResult(
                "demand.list",
                {
                    "demands": (
                        []
                        if actor_target is None
                        else read_model.list_external_demands(actor_target=actor_target)
                    )
                },
            )
        if command == "get":
            if not rest or rest[0].startswith("-"):
                raise cli_contract.CliError(
                    "INVALID_ARGUMENT",
                    "demand get requires <demand id> --actor <actor-id>",
                )
            demand_id = rest[0]
            actor_id = _required_actor(rest[1:], context="demand get")
            actor_target = _actor_target(actor_id)
            demand = (
                None
                if actor_target is None
                else read_model.get_external_demand(
                    demand_id,
                    actor_target=actor_target,
                )
            )
            if demand is None:
                raise cli_contract.CliError(
                    "NOT_FOUND",
                    f"Demand not found for actor {actor_id}: {demand_id}",
                    {"demand_id": demand_id, "actor_id": actor_id},
                )
            return cli_contract.CliCommandResult(
                "demand.get",
                {"demand": demand},
            )
    except ValueError as exc:
        raise cli_contract.CliError("INVALID_ARGUMENT", str(exc)) from exc
    raise cli_contract.CliError(
        "UNKNOWN_COMMAND",
        f"Unknown demand command: {command}",
    )


REGISTRATION = cli_contract.CliCommandRegistration(
    name="demand",
    help_rows=(
        "  buddyswitch-codex demand list --actor <actor-id>",
        "  buddyswitch-codex demand get <demand-id> --actor <actor-id>",
        "  demand    Read actor-scoped external-safe Demand projections.",
    ),
    handler=dispatch,
)
