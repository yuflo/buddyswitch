#!/usr/bin/env python3
"""track env.tool CLI registration."""

from __future__ import annotations

import argparse
from typing import Any

from env.tools import cli_helpers

TOOL_ID = "track"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("track", help="Track env tool operations")
    track_sub = parser.add_subparsers(dest="operation", required=True)

    create = track_sub.add_parser("create", help="Create PM-owned track page")
    cli_helpers.add_payload_argument(create)
    create.set_defaults(_env_tool=TOOL_ID, _env_action="create", _env_payload_builder=_json_payload)

    list_parser = track_sub.add_parser("list", help="List non-archived track page summaries")
    list_parser.add_argument("--state")
    list_parser.add_argument("--limit", type=int)
    list_parser.set_defaults(_env_tool=TOOL_ID, _env_action="list", _env_payload_builder=_list_payload)

    open_parser = track_sub.add_parser("open", help="Open one track page by id")
    open_parser.add_argument("--track-id", required=True)
    open_parser.set_defaults(_env_tool=TOOL_ID, _env_action="open", _env_payload_builder=_track_id_payload)

    update_now = track_sub.add_parser("update-now", help="Update now/state/health on track page")
    cli_helpers.add_payload_argument(update_now)
    update_now.set_defaults(_env_tool=TOOL_ID, _env_action="update_now", _env_payload_builder=_json_payload)

    add_material = track_sub.add_parser("add-material", help="Publish draft artifact as current track material")
    cli_helpers.add_payload_argument(add_material)
    add_material.set_defaults(_env_tool=TOOL_ID, _env_action="add_material", _env_payload_builder=_json_payload)

    add_update = track_sub.add_parser("add-update", help="Append one track timeline update")
    cli_helpers.add_payload_argument(add_update)
    add_update.set_defaults(_env_tool=TOOL_ID, _env_action="add_update", _env_payload_builder=_json_payload)

    add_proof = track_sub.add_parser("add-proof", help="Publish draft artifact as close proof")
    cli_helpers.add_payload_argument(add_proof)
    add_proof.set_defaults(_env_tool=TOOL_ID, _env_action="add_proof", _env_payload_builder=_json_payload)

    archive = track_sub.add_parser("archive", help="Archive PM-owned track")
    archive.add_argument("--track-id", required=True)
    archive.set_defaults(_env_tool=TOOL_ID, _env_action="archive", _env_payload_builder=_track_id_payload)


def _json_payload(args: argparse.Namespace) -> dict[str, Any]:
    return cli_helpers.load_json_object(args.payload)


def _track_id_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {"track_id": args.track_id}


def _list_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in ("state", "limit"):
        value = getattr(args, field, None)
        if value is not None:
            payload[field] = value
    return payload
