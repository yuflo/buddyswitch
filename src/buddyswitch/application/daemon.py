"""Explicit product composition for the actor instance Daemon."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from buddyswitch.application.build import ApplicationAssembly, activate_application
from buddyswitch.application.daemon_host import AppActorDaemonHost
from buddyswitch.foundation.browser_runtime import inbound as browser_inbound
from buddyswitch.foundation.daemon import contracts, inbound


@dataclass(frozen=True)
class InstanceDaemonApplication:
    host: contracts.DaemonHost
    handlers: tuple[object, ...]
    notify_subscriptions: tuple[str, ...]
    application_command_factories: tuple[contracts.ApplicationCommandFactory, ...]


def _component_handlers(
    registrations: Sequence[contracts.DaemonHandlerRegistration],
    *,
    occupied_names: set[str],
) -> list[object]:
    handlers: list[object] = []
    for registration in registrations:
        if not isinstance(registration, contracts.DaemonHandlerRegistration):
            raise ValueError("daemon contribution must be DaemonHandlerRegistration")
        declared_name = registration.name
        if not isinstance(declared_name, str) or not declared_name.strip():
            raise ValueError("daemon handler registration name must be non-empty")
        declared_name = declared_name.strip()
        if declared_name in occupied_names:
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
        occupied_names.add(declared_name)
        handlers.append(handler)
    return handlers


def _registered_handlers(
    registrations: Sequence[inbound.InboundSourceRegistration],
    *,
    occupied_names: set[str],
) -> list[object]:
    handlers = inbound.handlers_from_registrations(tuple(registrations))
    for handler in handlers:
        name = getattr(handler, "name", None)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("built-in daemon handler name must be non-empty")
        name = name.strip()
        if name in occupied_names:
            raise ValueError(f"duplicate built-in daemon handler: {name}")
        occupied_names.add(name)
    return handlers


def compose_instance_daemon_handlers(
    component_registrations: Sequence[contracts.DaemonHandlerRegistration],
    inbound_source_registrations: Sequence[inbound.InboundSourceRegistration],
) -> list[object]:
    occupied_names: set[str] = set()
    return [
        *_registered_handlers(
            inbound_source_registrations,
            occupied_names=occupied_names,
        ),
        *_registered_handlers(
            browser_inbound.inbound_registrations(),
            occupied_names=occupied_names,
        ),
        *_component_handlers(
            component_registrations,
            occupied_names=occupied_names,
        ),
    ]


def daemon_notify_subscriptions(
    registrations: Sequence[inbound.InboundSourceRegistration],
) -> list[str]:
    return inbound.subscriptions_from_registrations(tuple(registrations))


def daemon_application_command_factories(
    registrations: Sequence[contracts.DaemonHandlerRegistration],
) -> list[contracts.ApplicationCommandFactory]:
    return [
        registration.application_command_factory
        for registration in registrations
        if registration.application_command_factory is not None
    ]


def build_instance_daemon_application(
    application: ApplicationAssembly | None = None,
) -> InstanceDaemonApplication:
    selected = application if application is not None else activate_application()
    component_inbound = tuple(selected.inbound_sources)
    handlers = compose_instance_daemon_handlers(
        selected.daemon_handlers,
        component_inbound,
    )
    return InstanceDaemonApplication(
        host=AppActorDaemonHost(),
        handlers=tuple(handlers),
        notify_subscriptions=tuple(daemon_notify_subscriptions(component_inbound)),
        application_command_factories=tuple(
            daemon_application_command_factories(selected.daemon_handlers)
        ),
    )
