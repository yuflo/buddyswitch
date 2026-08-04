"""Verified broker-routed environment client entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.tool_runtime import client
from buddyswitch.foundation.process_runtime.invocation import run_verified


def main() -> int:
    activate_application()
    return client.main()


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
