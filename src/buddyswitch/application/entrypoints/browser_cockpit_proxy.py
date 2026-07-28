"""Verified Chrome DevTools cockpit proxy entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher.chrome_devtools_cockpit_proxy import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
