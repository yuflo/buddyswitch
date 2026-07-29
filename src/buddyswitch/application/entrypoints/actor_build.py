"""Verified Actor environment build entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher import actor_environment


def main() -> int:
    activate_application()
    return actor_environment.main()


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
