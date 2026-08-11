"""Verified instance Daemon entrypoint."""

from buddyswitch.application.daemon import build_instance_daemon_application
from buddyswitch.foundation.daemon import instance_process
from buddyswitch.foundation.process_runtime.invocation import run_verified


def main() -> int:
    application = build_instance_daemon_application()
    return instance_process.main(
        host=application.host,
        handlers=application.handlers,
        notify_subscriptions=application.notify_subscriptions,
        application_command_factories=application.application_command_factories,
    )


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
