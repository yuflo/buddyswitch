"""Verified Web management entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.application.host_control import assemble_host_control
from buddyswitch.foundation.host_control.runtime import HostControlError
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher import web_management


def main() -> int:
    application = activate_application()
    try:
        host_control = assemble_host_control(application)
    except HostControlError as exc:
        return web_management.emit_startup_failure(exc)
    return web_management.main(
        host_control=host_control,
    )


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
