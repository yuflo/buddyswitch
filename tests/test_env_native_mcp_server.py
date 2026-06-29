#!/usr/bin/env python3
"""Tests for the BuddySwitch env tool stdio MCP server."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "tools" / "launcher" / "env_tool_mcp_server.py"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_server_module():
    spec = importlib.util.spec_from_file_location("env_tool_mcp_server", SERVER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load server module: {SERVER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EnvNativeMcpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = load_server_module()

    def test_initialize_returns_tools_capability(self) -> None:
        response = self.server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            dispatcher=lambda **_: {},
        )

        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"]["protocolVersion"], self.server.MCP_PROTOCOL_VERSION)
        self.assertIn("tools", response["result"]["capabilities"])
        self.assertEqual(response["result"]["serverInfo"]["name"], "buddyswitch-env")

    def test_tools_list_returns_registry_projected_native_tools(self) -> None:
        response = self.server.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            dispatcher=lambda **_: {},
        )

        tools = response["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        self.assertIn("message__get", by_name)
        self.assertIn("message__list", by_name)
        self.assertIn("message__mark", by_name)
        self.assertIn("message__send", by_name)
        self.assertIn("task_sys__checkpoint_update", by_name)
        self.assertNotIn("task__get", by_name)
        self.assertEqual(by_name["message__get"]["inputSchema"]["type"], "object")
        self.assertEqual(by_name["message__list"]["inputSchema"]["type"], "object")

    def test_tools_call_dispatches_decoded_env_tool_request(self) -> None:
        calls: list[dict[str, Any]] = []

        def dispatcher(*, tool: str, action: str, args: dict[str, Any]) -> dict[str, Any]:
            calls.append({"tool": tool, "action": action, "args": args})
            return {"ok": True, "rows": []}

        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "message__list", "arguments": {}},
            },
            dispatcher=dispatcher,
        )

        self.assertEqual(calls, [{"tool": "message", "action": "list", "args": {}}])
        result = response["result"]
        self.assertIs(result.get("isError"), False)
        self.assertEqual(result["content"][0]["type"], "text")
        self.assertEqual(json.loads(result["content"][0]["text"])["rows"], [])

    def test_tools_call_rejects_unknown_native_name_without_dispatch(self) -> None:
        calls: list[dict[str, Any]] = []

        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "task__get", "arguments": {"task_id": "task-demo"}},
            },
            dispatcher=lambda **kwargs: calls.append(kwargs) or {},
        )

        self.assertEqual(calls, [])
        result = response["result"]
        self.assertIs(result["isError"], True)
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["error"]["code"], "E_ENV_NATIVE_MCP_UNKNOWN_TOOL")
        self.assertIn("task__get", payload["error"]["message"])

    def test_tools_call_returns_broker_error_as_mcp_tool_error_content(self) -> None:
        def dispatcher(*, tool: str, action: str, args: dict[str, Any]) -> dict[str, Any]:
            raise self.server.McpToolDispatchError(
                "E_RUNTIME_BROKER_UNAVAILABLE",
                "runtime broker socket not found",
                details={"permission_boundary": "product-mode-runtime-broker"},
            )

        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "message__list", "arguments": {}},
            },
            dispatcher=dispatcher,
        )

        result = response["result"]
        self.assertIs(result["isError"], True)
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["error"]["code"], "E_RUNTIME_BROKER_UNAVAILABLE")
        self.assertEqual(payload["permission_boundary"], "product-mode-runtime-broker")


if __name__ == "__main__":
    unittest.main()
