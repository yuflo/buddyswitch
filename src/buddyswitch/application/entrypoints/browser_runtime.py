"""Verified Browser runtime lifecycle entrypoint."""

import sys

from buddyswitch.foundation.browser_runtime import config, runtime, target
from buddyswitch.foundation.process_runtime.invocation import run_verified


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["ttl-config"]:
        return config.main(argv[1:])
    if argv[:1] == ["target"]:
        return target.main(argv[1:])
    return runtime.main(argv)


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
