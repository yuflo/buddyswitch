"""Verified Runtime Broker entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.runtime_kernel.broker import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
