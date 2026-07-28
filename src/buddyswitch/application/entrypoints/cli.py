"""Verified public CLI entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher.cli import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
