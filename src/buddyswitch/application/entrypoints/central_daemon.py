"""Verified central Daemon entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.foundation.daemon.central_process import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
