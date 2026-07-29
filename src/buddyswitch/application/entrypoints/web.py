"""Verified Web management entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher import web_management


def main() -> int:
    activate_application()
    return web_management.main()


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
