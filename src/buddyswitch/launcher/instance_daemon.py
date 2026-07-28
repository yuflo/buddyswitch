"""BuddySwitch daemon entrypoint."""

from __future__ import annotations

import json
import argparse
import signal
import sys
from pathlib import Path


from buddyswitch.launcher import daemon_core  # noqa: E402
from buddyswitch.launcher import browser_inbound  # noqa: E402
from buddyswitch.launcher import demand_orchestration_handler  # noqa: E402
from buddyswitch.launcher import demand_triage_handler  # noqa: E402
from buddyswitch.launcher import message_inbound  # noqa: E402
from buddyswitch.launcher import notification_center  # noqa: E402
from buddyswitch.launcher import task_goal_handler  # noqa: E402
from buddyswitch.launcher import track_comment_inbound  # noqa: E402


def default_notification_registrations() -> list[notification_center.InboundSourceRegistration]:
    return [
        *message_inbound.inbound_registrations(),
        *track_comment_inbound.inbound_registrations(),
    ]


def default_notify_subscriptions() -> list[str]:
    return notification_center.subscriptions_from_registrations(default_notification_registrations())


def default_application_command_factories() -> list[object]:
    return [task_goal_handler.command_handlers]


def default_daemon_handlers() -> list[object]:
    registrations = default_notification_registrations()
    browser_registrations = browser_inbound.inbound_registrations()
    return [
        *notification_center.handlers_from_registrations(registrations),
        *notification_center.handlers_from_registrations(browser_registrations),
        demand_triage_handler.DemandTriageHandler(),
        task_goal_handler.TaskGoalHandler(),
        demand_orchestration_handler.DemandOrchestrationHandler(),
    ]


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
            previous_sigint = signal.signal(
                signal.SIGINT,
                lambda signum, _frame: (_ for _ in ()).throw(SystemExit(128 + signum)),
            )
            previous_sigterm = signal.signal(
                signal.SIGTERM,
                lambda signum, _frame: (_ for _ in ()).throw(SystemExit(128 + signum)),
            )
            try:
                return daemon_core.run_daemon(
                    instance_json,
                    handlers=default_daemon_handlers(),
                    notify_subscriptions=default_notify_subscriptions(),
                    application_command_factories=default_application_command_factories(),
                )
            finally:
                signal.signal(signal.SIGINT, previous_sigint)
                signal.signal(signal.SIGTERM, previous_sigterm)
        if args.command == "start":
            print(
                json.dumps(
                    daemon_core.start_daemon(
                        instance_json,
                        handlers=default_daemon_handlers(),
                        notify_subscriptions=default_notify_subscriptions(),
                    ),
                    ensure_ascii=True,
                )
            )
            return 0
        if args.command == "stop":
            print(json.dumps(daemon_core.stop_daemon(instance_json), ensure_ascii=True))
            return 0
        if args.command == "status":
            print(
                json.dumps(
                    daemon_core.daemon_status(
                        instance_json,
                        handlers=default_daemon_handlers(),
                        notify_subscriptions=default_notify_subscriptions(),
                    ),
                    ensure_ascii=True,
                )
            )
            return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
