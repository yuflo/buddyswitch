"""Verified public CLI entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher import cli


def main() -> int:
    application = activate_application()
    return cli.main(command_registrations=application.cli_commands)


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
