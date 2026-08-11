"""Actor instance daemon process command handling."""

from __future__ import annotations

import json
import argparse
import signal
import sys
from pathlib import Path


from buddyswitch.foundation.daemon import instance  # noqa: E402
from buddyswitch.foundation.daemon import contracts  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_name in ("run", "start", "stop", "status"):
        command = subparsers.add_parser(command_name)
        command.add_argument("--instance-json", required=True)
        if command_name == "status":
            command.add_argument("--json", action="store_true")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    host: contracts.DaemonHost,
    handlers: tuple[object, ...] = (),
    notify_subscriptions: tuple[str, ...] = (),
    application_command_factories: tuple[
        contracts.ApplicationCommandFactory, ...
    ] = (),
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    instance_json = Path(args.instance_json)
    try:
        if args.command == "run":
            previous_sigint = signal.signal(
                signal.SIGINT,
                lambda signum, _frame: (_ for _ in ()).throw(SystemExit(128 + signum)),
            )
            previous_sigterm = signal.signal(
                signal.SIGTERM,
                lambda signum, _frame: (_ for _ in ()).throw(SystemExit(128 + signum)),
            )
            try:
                return instance.run_daemon(
                    instance_json,
                    host=host,
                    handlers=list(handlers),
                    notify_subscriptions=list(notify_subscriptions),
                    application_command_factories=list(
                        application_command_factories
                    ),
                )
            finally:
                signal.signal(signal.SIGINT, previous_sigint)
                signal.signal(signal.SIGTERM, previous_sigterm)
        if args.command == "start":
            print(
                json.dumps(
                    instance.start_daemon(
                        instance_json,
                        host=host,
                        handlers=list(handlers),
                        notify_subscriptions=list(notify_subscriptions),
                    ),
                    ensure_ascii=True,
                )
            )
            return 0
        if args.command == "stop":
            print(
                json.dumps(
                    instance.stop_daemon(instance_json, host=host),
                    ensure_ascii=True,
                )
            )
            return 0
        if args.command == "status":
            print(
                json.dumps(
                    instance.daemon_status(
                        instance_json,
                        host=host,
                        handlers=list(handlers),
                        notify_subscriptions=list(notify_subscriptions),
                    ),
                    ensure_ascii=True,
                )
            )
            return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 2
