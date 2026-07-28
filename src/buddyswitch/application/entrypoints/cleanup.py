"""Verified cleanup entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.runtime_support.env_cleanup import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
