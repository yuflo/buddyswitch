"""Verified Env MCP entrypoint."""

from buddyswitch.foundation.process_runtime.invocation import run_verified
from buddyswitch.launcher.env_tool_mcp_server import main


if __name__ == "__main__":
    raise SystemExit(run_verified(main))
