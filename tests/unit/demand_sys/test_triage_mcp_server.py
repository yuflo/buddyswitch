"""Protocol tests for the thread-scoped Demand triage resolver."""

from __future__ import annotations

import importlib
import json
import os
import unittest
from unittest.mock import patch


class DemandTriageMcpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = importlib.import_module("demand_triage_mcp_server")

    def test_lists_exactly_one_flat_resolve_tool(self) -> None:
        response = self.server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            dispatcher=lambda **_: {},
        )

        tools = response["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["resolve"])
        schema = tools[0]["inputSchema"]
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["required"],
            [
                "decision",
                "reason",
                "demand_ref",
                "description",
                "detail",
                "reply_content",
            ],
        )
        self.assertEqual(
            schema["properties"]["decision"]["enum"],
            [
                "no_action_needed",
                "handled",
                "create",
                "merge_intake",
                "revise",
                "cancel",
            ],
        )
        for field in ("demand_ref", "description", "detail", "reply_content"):
            self.assertEqual(schema["properties"][field]["type"], ["string", "null"])
        encoded = json.dumps(schema, sort_keys=True)
        for forbidden in ("oneOf", "anyOf", "allOf", "if", "then", "else"):
            self.assertNotIn(f'"{forbidden}"', encoded)

    def test_resolve_forwards_host_capability_and_model_proposal(self) -> None:
        calls: list[dict[str, object]] = []
        proposal = {
            "decision": "create",
            "reason": "New unmet obligation.",
            "demand_ref": None,
            "description": "Research AI adoption.",
            "detail": "Compare buyer segments.",
            "reply_content": None,
        }
        with patch.dict(
            os.environ,
            {"BUDDYSWITCH_DEMAND_TRIAGE_CAPABILITY": "host-secret"},
            clear=False,
        ):
            response = self.server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "resolve", "arguments": proposal},
                },
                dispatcher=lambda **kwargs: calls.append(kwargs)
                or {"ok": True, "decision": "create"},
            )

        self.assertEqual(
            calls,
            [{"capability": "host-secret", "proposal": proposal}],
        )
        result = response["result"]
        self.assertIs(result["isError"], False)
        self.assertEqual(
            json.loads(result["content"][0]["text"])["decision"],
            "create",
        )

    def test_resolve_rejects_missing_host_capability_without_dispatch(self) -> None:
        calls: list[dict[str, object]] = []
        with patch.dict(os.environ, {}, clear=True):
            response = self.server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "resolve",
                        "arguments": {
                            "decision": "no_action_needed",
                            "reason": "Acknowledgement only.",
                            "demand_ref": None,
                            "description": None,
                            "detail": None,
                            "reply_content": None,
                        },
                    },
                },
                dispatcher=lambda **kwargs: calls.append(kwargs) or {},
            )

        self.assertEqual(calls, [])
        result = response["result"]
        self.assertIs(result["isError"], True)
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(
            payload["error"]["code"],
            "E_DEMAND_TRIAGE_CAPABILITY",
        )
