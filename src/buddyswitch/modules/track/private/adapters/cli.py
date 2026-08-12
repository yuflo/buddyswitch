"""Track-owned CLI registration over the external-safe read model."""

from __future__ import annotations

from collections.abc import Sequence

from buddyswitch.foundation.cli_runtime import contracts as cli_contract
from buddyswitch.modules.track import public as track_public


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


def dispatch(args: Sequence[str]) -> cli_contract.CliCommandResult:
    rows = list(args)
    if not rows:
        raise cli_contract.CliError(
            "UNKNOWN_COMMAND",
            "track command is required",
        )
    command, rest = rows[0], rows[1:]
    try:
        if command == "list":
            owner = cli_contract.optional_single_option(
                rest,
                "--owner",
                "track list",
            )
            return cli_contract.CliCommandResult(
                "track.list",
                {
                    "tracks": track_public.list_external_tracks(
                        owner_identity=owner,
                    )
                },
            )
        if command == "get":
            track_id = _single_positional(
                rest,
                label="track id",
                context="track get",
            )
            track = track_public.get_external_track(track_id)
            if track is None:
                raise cli_contract.CliError(
                    "NOT_FOUND",
                    f"Track not found: {track_id}",
                    {"track_id": track_id},
                )
            return cli_contract.CliCommandResult(
                "track.get",
                {"track": track},
            )
    except ValueError as exc:
        raise cli_contract.CliError("INVALID_ARGUMENT", str(exc)) from exc
    raise cli_contract.CliError(
        "UNKNOWN_COMMAND",
        f"Unknown track command: {command}",
    )


REGISTRATION = cli_contract.CliCommandRegistration(
    name="track",
    help_rows=(
        "  buddyswitch-codex track list [--owner <identity-id>]",
        "  buddyswitch-codex track get <track-id>",
        "  track     Read external-safe Track projections.",
    ),
    handler=dispatch,
)
