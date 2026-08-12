"""Verified cleanup entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.application.role_source import load_valid_role_ids
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.foundation.state import cleanup
from buddyswitch.runtime_support import env_manifest


def main() -> int:
    application = activate_application()
    return cleanup.main(
        contributions=application.cleanup,
        default_manifest_path=env_manifest.DEFAULT_MANIFEST,
        valid_role_ids_loader=load_valid_role_ids,
    )


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
