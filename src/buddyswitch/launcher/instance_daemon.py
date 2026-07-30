"""BuddySwitch daemon entrypoint."""

from __future__ import annotations

import json
import argparse
import signal
import sys
from pathlib import Path
from collections.abc import Sequence


from buddyswitch.launcher import daemon_core  # noqa: E402
from buddyswitch.launcher import browser_inbound  # noqa: E402
from buddyswitch.launcher.daemon_contracts import DaemonHandlerRegistration  # noqa: E402
from buddyswitch.launcher import message_inbound  # noqa: E402
from buddyswitch.launcher import notification_center  # noqa: E402
from buddyswitch.launcher import track_comment_inbound  # noqa: E402


def default_notification_registrations() -> list[notification_center.InboundSourceRegistration]:
    return [
        *message_inbound.inbound_registrations(),
        *track_comment_inbound.inbound_registrations(),
    ]


def default_notify_subscriptions() -> list[str]:
    return notification_center.subscriptions_from_registrations(default_notification_registrations())


def default_application_command_factories(
    component_registrations: Sequence[DaemonHandlerRegistration] = (),
) -> list[object]:
    return [
        registration.application_command_factory
        for registration in component_registrations
        if registration.application_command_factory is not None
    ]


def default_daemon_handlers(
    component_registrations: Sequence[DaemonHandlerRegistration] = (),
) -> list[object]:
    registrations = default_notification_registrations()
    browser_registrations = browser_inbound.inbound_registrations()
    built_in_before = [
        *notification_center.handlers_from_registrations(registrations),
        *notification_center.handlers_from_registrations(browser_registrations),
    ]
    names: set[str] = set()
    for handler in built_in_before:
        name = getattr(handler, "name", None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("built-in daemon handler name must be non-empty")
        name = name.strip()
        if name in names:
            raise ValueError(f"duplicate built-in daemon handler: {name}")
        names.add(name)

    component_handlers: list[object] = []
    for registration in component_registrations:
        if not isinstance(registration, DaemonHandlerRegistration):
            raise ValueError(
                "daemon contribution must be DaemonHandlerRegistration"
            )
        declared_name = registration.name
        if not isinstance(declared_name, str) or not declared_name.strip():
            raise ValueError("daemon handler registration name must be non-empty")
        declared_name = declared_name.strip()
        if declared_name in names:
            raise ValueError(
                f"duplicate daemon handler registration: {declared_name}"
            )
        if not callable(registration.factory):
            raise ValueError(
                f"daemon handler factory for '{declared_name}' must be callable"
            )
        handler = registration.factory()
        actual_name = getattr(handler, "name", None)
        if not isinstance(actual_name, str) or not actual_name.strip():
            raise ValueError(
                f"daemon handler registration '{declared_name}' constructed "
                "a handler without a name"
            )
        actual_name = actual_name.strip()
        if actual_name != declared_name:
            raise ValueError(
                f"daemon handler registration '{declared_name}' constructed "
                f"'{actual_name}'"
            )
        names.add(declared_name)
        component_handlers.append(handler)
    return [*built_in_before, *component_handlers]


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
    component_registrations: tuple[DaemonHandlerRegistration, ...] = (),
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
                return daemon_core.run_daemon(
                    instance_json,
                    handlers=default_daemon_handlers(component_registrations),
                    notify_subscriptions=default_notify_subscriptions(),
                    application_command_factories=default_application_command_factories(
                        component_registrations
                    ),
                )
            finally:
                signal.signal(signal.SIGINT, previous_sigint)
                signal.signal(signal.SIGTERM, previous_sigterm)
        if args.command == "start":
            print(
                json.dumps(
                    daemon_core.start_daemon(
                        instance_json,
                        handlers=default_daemon_handlers(component_registrations),
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
                        handlers=default_daemon_handlers(component_registrations),
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
