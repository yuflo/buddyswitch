"""Verified Runtime Broker entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.foundation.runtime_broker import broker


def main() -> int:
    activate_application()
    return broker.main()


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
