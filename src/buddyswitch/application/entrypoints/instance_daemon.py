"""Verified instance Daemon entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher import instance_daemon


def main() -> int:
    application = activate_application()
    return instance_daemon.main(
        component_registrations=application.daemon_handlers,
        inbound_source_registrations=application.inbound_sources,
    )


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
