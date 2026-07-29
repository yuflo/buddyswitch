"""Verified environment manifest entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.runtime_support import env_manifest


def main() -> int:
    activate_application()
    return env_manifest.main()


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
