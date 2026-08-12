"""Verified public CLI entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.application.cli_runtime import assemble_cli_runtime
from buddyswitch.application.host_control import assemble_host_control
from buddyswitch.foundation.cli_runtime import runtime as cli_runtime
from buddyswitch.foundation.host_control.runtime import HostControlError
from buddyswitch.foundation.process_runtime.invocation import run_verified


def main() -> int:
    application = activate_application()
    try:
        host_control = assemble_host_control(application)
        application_input = assemble_cli_runtime(application)
    except (HostControlError, ValueError) as exc:
        return cli_runtime.emit_failure(exc)
    return cli_runtime.main(
        application_input=application_input,
        host_control=host_control,
        command_registrations=application.cli_commands,
    )


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
