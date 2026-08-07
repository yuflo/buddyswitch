"""Runless BuddySwitch runtime primitives.

This module no longer owns prepare/persist run lifecycle. Runtime Broker entrypoints
route ``env.tool``, health, and Browser methods, and services mutate durable product
objects directly.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from buddyswitch.runtime_support.env_manifest import DEFAULT_MANIFEST
from buddyswitch.foundation.tool_runtime import registry as tool_registry

def _build_env_tools_desc() -> dict[str, Any]:
    """Expose canonical env tool contract and semantics map for runtime consumers."""

    return tool_registry.env_tools_description()


def _runtime_status_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "runtime_mode": "runless",
        "manifest_path": str(DEFAULT_MANIFEST),
        "env_tools": _build_env_tools_desc(),
    }


def _cmd_status(_args: argparse.Namespace) -> int:
    print(json.dumps(_runtime_status_payload(), ensure_ascii=True))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runless BuddySwitch runtime entrypoints.")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show runless runtime status and env tool catalog.")
    status.set_defaults(func=_cmd_status)

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return args.func(args)
