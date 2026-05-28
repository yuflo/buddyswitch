#!/usr/bin/env python3
"""BuddySwitch daemon entrypoint."""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import daemon_core  # noqa: E402
import task_checkout_handler  # noqa: E402


def default_handlers() -> list[object]:
    return [task_checkout_handler.TaskCheckoutHandler()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_name in ("run", "start", "stop", "status"):
        command = subparsers.add_parser(command_name)
        command.add_argument("--instance-json", required=True)
        if command_name == "status":
            command.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    instance_json = Path(args.instance_json)
    try:
        if args.command == "run":
            return daemon_core.run_daemon(instance_json, handlers=default_handlers())
        if args.command == "start":
            print(json.dumps(daemon_core.start_daemon(instance_json), ensure_ascii=True))
            return 0
        if args.command == "stop":
            print(json.dumps(daemon_core.stop_daemon(instance_json), ensure_ascii=True))
            return 0
        if args.command == "status":
            print(json.dumps(daemon_core.daemon_status(instance_json), ensure_ascii=True))
            return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
