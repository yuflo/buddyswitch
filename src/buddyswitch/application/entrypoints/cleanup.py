"""Verified cleanup entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.runtime_support import env_cleanup


def main() -> int:
    application = activate_application()
    return env_cleanup.main(contributions=application.cleanup)


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
