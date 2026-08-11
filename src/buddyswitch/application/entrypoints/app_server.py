"""Verified App Server entrypoint."""

from buddyswitch.application.build import activate_application
import buddyswitch.foundation.app_server.runtime as app_server
from buddyswitch.foundation.process_runtime.invocation import run_verified


def main() -> int:
    activate_application()
    return app_server.main()


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
