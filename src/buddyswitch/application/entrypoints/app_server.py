"""Verified App Server entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher import app_server


def main() -> int:
    activate_application()
    return app_server.main()


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
