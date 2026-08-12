"""Verified public CLI entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.application.host_control import assemble_host_control
from buddyswitch.foundation.host_control.runtime import HostControlError
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher import cli


def main() -> int:
    application = activate_application()
    try:
        host_control = assemble_host_control(application)
    except HostControlError as exc:
        return cli.emit_failure(exc)
    return cli.main(
        host_control=host_control,
        command_registrations=application.cli_commands,
    )


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
