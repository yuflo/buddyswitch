"""Assemble the one current application input for Foundation Host Control."""

from __future__ import annotations

from buddyswitch.application.build import ApplicationAssembly
from buddyswitch.foundation.host_control.runtime import (
    HostControl,
    HostControlApplicationInput,
    HostControlError,
    HostControlRole,
)
from buddyswitch.runtime_support import env_manifest


START_MODULE = "buddyswitch.application.entrypoints.host_control_start"
CENTRAL_DAEMON_MODULE = "buddyswitch.application.entrypoints.central_daemon"
INSTANCE_DAEMON_MODULE = "buddyswitch.application.entrypoints.instance_daemon"
RUNTIME_BROKER_MODULE = "buddyswitch.application.entrypoints.runtime_broker"


def assemble_host_control(application: ApplicationAssembly) -> HostControl:
    """Build the concrete lifecycle capability from current application truth."""

    if not isinstance(application, ApplicationAssembly):
        raise ValueError("Host Control assembly requires ApplicationAssembly")
    try:
        manifest = env_manifest.load_manifest()
        roles = tuple(
            HostControlRole(
                id=role["id"],
                label=role["label"],
                scope=role["scope"],
            )
            for role in manifest["roles"]
        )
        application_input = HostControlApplicationInput(
            roles=roles,
            start_module=START_MODULE,
            central_daemon_module=CENTRAL_DAEMON_MODULE,
            instance_daemon_module=INSTANCE_DAEMON_MODULE,
            runtime_broker_module=RUNTIME_BROKER_MODULE,
        )
    except (env_manifest.ManifestError, KeyError, TypeError, ValueError) as exc:
        raise HostControlError(
            "COMMAND_FAILED",
            str(exc),
            returncode=1,
        ) from exc
    return HostControl(application_input=application_input)
