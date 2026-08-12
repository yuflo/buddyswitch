"""Verified runtime diagnostics entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.cli_runtime import diagnostics
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.runtime_support import env_manifest


def main() -> int:
    activate_application()
    return diagnostics.main(manifest_path=env_manifest.DEFAULT_MANIFEST)


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
