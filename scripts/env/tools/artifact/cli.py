#!/usr/bin/env python3
"""artifact env.tool CLI registration."""

from __future__ import annotations

import argparse
from typing import Any

from env.tools import cli_helpers

TOOL_ID = "artifact"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("artifact", help="Artifact env tool operations")
    artifact_sub = parser.add_subparsers(dest="operation", required=True)

    get_parser = artifact_sub.add_parser("get", help="Get readable artifact by id")
    get_parser.add_argument("--artifact-id", required=True)
    get_parser.set_defaults(_env_tool=TOOL_ID, _env_action="get", _env_payload_builder=_artifact_id_payload)

    create = artifact_sub.add_parser("create-revision", help="Create private draft/revision artifact")
    cli_helpers.add_payload_argument(create)
    create.set_defaults(_env_tool=TOOL_ID, _env_action="create_revision", _env_payload_builder=_json_payload)

    update = artifact_sub.add_parser("update-metadata", help="Update artifact title/summary/source refs")
    cli_helpers.add_payload_argument(update)
    update.set_defaults(_env_tool=TOOL_ID, _env_action="update_metadata", _env_payload_builder=_json_payload)


def _json_payload(args: argparse.Namespace) -> dict[str, Any]:
    return cli_helpers.load_json_object(args.payload)


def _artifact_id_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {"artifact_id": args.artifact_id}
