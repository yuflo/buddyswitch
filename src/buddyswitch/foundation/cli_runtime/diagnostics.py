"""Runless BuddySwitch diagnostics and Tool-catalog projection.

This module no longer owns prepare/persist run lifecycle. Runtime Broker entrypoints
route ``env.tool``, health, and Browser methods, and services mutate durable product
objects directly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from buddyswitch.foundation.tool_runtime import registry as tool_registry


def _build_env_tools_desc() -> dict[str, Any]:
    """Expose canonical env tool contract and semantics map for runtime consumers."""

    return tool_registry.env_tools_description()


def _runtime_status_payload(*, manifest_path: Path) -> dict[str, Any]:
    return {
        "ok": True,
        "runtime_mode": "runless",
        "manifest_path": str(manifest_path),
        "env_tools": _build_env_tools_desc(),
    }


def _cmd_status(_args: argparse.Namespace) -> int:
    print(
        json.dumps(
            _runtime_status_payload(manifest_path=_args.manifest_path),
            ensure_ascii=True,
        )
    )
    return 0


def _parse_args(*, manifest_path: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runless BuddySwitch runtime entrypoints.")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show runless runtime status and env tool catalog.")
    status.set_defaults(func=_cmd_status, manifest_path=manifest_path)

    return parser.parse_args()


def main(*, manifest_path: Path) -> int:
    args = _parse_args(manifest_path=manifest_path)
    return args.func(args)
