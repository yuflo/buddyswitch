"""Verified cleanup entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.foundation.state import cleanup


def main() -> int:
    application = activate_application()
    return cleanup.main(
        contributions=application.cleanup,
        valid_role_ids=application.role_host.valid_role_ids,
    )


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
