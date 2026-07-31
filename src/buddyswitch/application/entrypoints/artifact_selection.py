"""Verified Artifact selection entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.modules.artifact.entrypoints.artifact_selection import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
