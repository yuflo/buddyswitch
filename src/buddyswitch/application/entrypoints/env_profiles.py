"""Verified environment-profile entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.runtime_support import env_profiles


def main() -> int:
    activate_application()
    return env_profiles.main()


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
