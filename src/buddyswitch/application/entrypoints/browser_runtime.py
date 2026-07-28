"""Verified Browser runtime lifecycle entrypoint."""

import sys

from buddyswitch.env import browser_ttl_config, cdp_target
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher import browser_runtime_manager


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["ttl-config"]:
        return browser_ttl_config.main(argv[1:])
    if argv[:1] == ["target"]:
        return cdp_target.main(argv[1:])
    return browser_runtime_manager.main(argv)


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
