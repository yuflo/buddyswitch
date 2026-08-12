"""Verified Runtime Broker entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.foundation.runtime_broker import broker
from buddyswitch.runtime_support import env_manifest


def main() -> int:
    activate_application()
    return broker.main(manifest_loader=env_manifest.load_manifest)


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
