"""Verified central Daemon entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher.central_daemon import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
