"""Verified Env MCP entrypoint."""

from buddyswitch.application.build import activate_application
from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.foundation.tool_runtime import mcp_server


def main() -> int:
    activate_application()
    return mcp_server.main()


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
