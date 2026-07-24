"""Tests for the BuddySwitch env tool stdio MCP server."""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SERVER = ROOT / "tools" / "launcher" / "env_tool_mcp_server.py"
SCRIPTS = ROOT / "scripts"


def load_server_module():
    return importlib.reload(importlib.import_module("env_tool_mcp_server"))


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
        self.assertNotIn("message__mark", by_name)
        self.assertIn("message__send", by_name)
        self.assertIn("task_sys__list", by_name)
        self.assertIn("task_sys__get", by_name)
        self.assertIn("task_sys__create", by_name)
        self.assertIn("task_sys__cancel", by_name)
        self.assertNotIn("task_sys__close", by_name)
        self.assertNotIn("task_sys__need_parent", by_name)
        self.assertNotIn("task_sys__checkpoint_update", by_name)
        self.assertNotIn("task__get", by_name)
        self.assertNotIn("demand_sys__resolve_ingress", by_name)
        self.assertNotIn("demand_triage__resolve", by_name)
        self.assertEqual(by_name["message__get"]["inputSchema"]["type"], "object")
        self.assertEqual(by_name["message__list"]["inputSchema"]["type"], "object")

        actor_contracts = {
            "demand_sys__list": {"state"},
            "demand_sys__get": {"demand_id"},
            "demand_sys__create": {"description", "detail"},
            "demand_sys__revise": {"demand_ref", "description", "detail", "reason"},
            "demand_sys__complete": {"demand_ref", "summary", "evidence_refs"},
            "demand_sys__cancel": {"demand_ref", "summary"},
            "task_sys__list": {"status", "limit"},
            "task_sys__get": {"task_id"},
            "task_sys__create": {"demand_ref", "objective", "selection_reason"},
            "task_sys__cancel": {"task_id", "reason"},
        }

        def assert_described(schema: dict[str, Any], path: str) -> None:
            properties = schema.get("properties", {})
            self.assertIsInstance(properties, dict, msg=path)
            for field, field_schema in properties.items():
                with self.subTest(field=f"{path}.{field}"):
                    self.assertIsInstance(field_schema, dict)
                    description = field_schema.get("description")
                    self.assertIsInstance(description, str)
                    self.assertTrue(description.strip())
                    if field_schema.get("type") == "object":
                        assert_described(field_schema, f"{path}.{field}")
                    items = field_schema.get("items")
                    if isinstance(items, dict) and items.get("type") == "object":
                        item_description = items.get("description")
                        self.assertIsInstance(item_description, str)
                        self.assertTrue(item_description.strip())
                        assert_described(items, f"{path}.{field}[]")

        for tool_name, expected_fields in actor_contracts.items():
            with self.subTest(tool=tool_name):
                tool = by_name[tool_name]
                self.assertTrue(tool["description"].strip())
                schema = tool["inputSchema"]
                self.assertEqual(set(schema["properties"]), expected_fields)
                assert_described(schema, tool_name)

        self.assertIn(
            "does not create Task work or a native Goal",
            by_name["demand_sys__create"]["description"],
        )
        self.assertIn(
            "does not mutate, satisfy, or reprioritize a Demand",
            by_name["task_sys__create"]["description"],
        )

    def test_tools_call_dispatches_decoded_env_tool_request(self) -> None:
        calls: list[dict[str, Any]] = []

        def dispatcher(
            *,
            tool: str,
            action: str,
            args: dict[str, Any],
            invocation: dict[str, str],
        ) -> dict[str, Any]:
            calls.append(
                {
                    "tool": tool,
                    "action": action,
                    "args": args,
                    "invocation": invocation,
                }
            )
            return {"ok": True, "rows": []}

        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "message__list",
                    "arguments": {},
                    "_meta": {
                        "threadId": "thr-main",
                        "x-codex-turn-metadata": {"turn_id": "turn-9"},
                    },
                },
            },
            dispatcher=dispatcher,
        )

        self.assertEqual(
            calls,
            [{
                "tool": "message",
                "action": "list",
                "args": {},
                "invocation": {
                    "thread_id": "thr-main",
                    "turn_id": "turn-9",
                    "request_id": "3",
                },
            }],
        )
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
        def dispatcher(
            *,
            tool: str,
            action: str,
            args: dict[str, Any],
            invocation: dict[str, str],
        ) -> dict[str, Any]:
            del tool, action, args, invocation
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
