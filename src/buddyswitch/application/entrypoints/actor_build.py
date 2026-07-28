"""Verified Actor environment build entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher.actor_environment import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
