"""Verified Browser evidence entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.modules.evidence.entrypoints.browser_evidence import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
