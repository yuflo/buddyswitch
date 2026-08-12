"""Verified Web management entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.application.host_control import assemble_host_control
from buddyswitch.foundation.host_control.runtime import HostControlError
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.foundation.web_runtime import runtime as web_runtime


PUBLIC_ATTACH_CLI_MODULE = "buddyswitch.application.entrypoints.cli"


def main() -> int:
    application = activate_application()
    try:
        host_control = assemble_host_control(application)
    except HostControlError as exc:
        return web_runtime.emit_startup_failure(exc)
    return web_runtime.main(
        host_control=host_control,
        attach_cli_module=PUBLIC_ATTACH_CLI_MODULE,
    )


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
