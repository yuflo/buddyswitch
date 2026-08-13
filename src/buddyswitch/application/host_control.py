"""Assemble the one current application input for Foundation Host Control."""

from __future__ import annotations

from buddyswitch.application.build import ApplicationRuntime
from buddyswitch.foundation.host_control.runtime import (
    HostControl,
    HostControlApplicationInput,
    HostControlError,
    HostControlRole,
)


START_MODULE = "buddyswitch.application.entrypoints.host_control_start"
CENTRAL_DAEMON_MODULE = "buddyswitch.application.entrypoints.central_daemon"
INSTANCE_DAEMON_MODULE = "buddyswitch.application.entrypoints.instance_daemon"
RUNTIME_BROKER_MODULE = "buddyswitch.application.entrypoints.runtime_broker"


def assemble_host_control(application: ApplicationRuntime) -> HostControl:
    """Build the concrete lifecycle capability from current application truth."""

    if not isinstance(application, ApplicationRuntime):
        raise ValueError("Host Control assembly requires ApplicationRuntime")
    try:
        roles = tuple(
            HostControlRole(
                id=role.id,
                label=role.label,
                scope=role.scope,
            )
            for role in application.role_host.roles
        )
        application_input = HostControlApplicationInput(
            roles=roles,
            start_module=START_MODULE,
            central_daemon_module=CENTRAL_DAEMON_MODULE,
            instance_daemon_module=INSTANCE_DAEMON_MODULE,
            runtime_broker_module=RUNTIME_BROKER_MODULE,
        )
    except (TypeError, ValueError) as exc:
        raise HostControlError(
            "COMMAND_FAILED",
            str(exc),
            returncode=1,
        ) from exc
    return HostControl(application_input=application_input)
