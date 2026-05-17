#!/usr/bin/env python3
"""Semantic contract coverage for env.tool registry projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tools import contracts  # noqa: E402

_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment"}


class EnvToolSemanticContractTests(unittest.TestCase):
    def test_registry_semantics_cover_every_registered_tool_and_action(self) -> None:
        desc = contracts.env_tools_description()
        registry_tools = {row["tool"] for row in contracts.TOOL_REGISTRY}

        self.assertEqual(registry_tools, _EXPECTED_TOOLS)
        self.assertEqual(set(desc), _EXPECTED_TOOLS)
        self.assertEqual(contracts.semantic_contract_errors(), [])

        for spec in contracts.TOOL_REGISTRY:
            tool = spec["tool"]
            expected_actions = {row["name"] for row in spec["actions"]}
            self.assertEqual(set(desc[tool]["operations"]), expected_actions)
            self.assertEqual(set(desc[tool]["payload_fields"]), expected_actions)
            self.assertEqual(set(desc[tool]["action_semantics"]), expected_actions)

    def test_handoff_and_track_advance_are_absent(self) -> None:
        by_tool = {row["tool"]: row for row in contracts.TOOL_REGISTRY}
        self.assertNotIn("handoff", by_tool)
        self.assertNotIn("advance", {row["name"] for row in by_tool["track"]["actions"]})

        op = contracts.operation_semantics()
        self.assertNotIn("track.advance", op)
        self.assertFalse(any(key.startswith("handoff.") for key in op))

    def test_operation_semantics_machine_contract_is_preserved(self) -> None:
        op = contracts.operation_semantics()
        expected_keys = {
            f"{tool_spec['tool']}.{action_spec['name']}"
            for tool_spec in contracts.TOOL_REGISTRY
            for action_spec in tool_spec["actions"]
        }
        self.assertEqual(set(op), expected_keys)

        for key, row in op.items():
            with self.subTest(action=key):
                self.assertIn("kind", row)
                self.assertIn("mutates", row)
                self.assertIn("required_permission", row)
                self.assertIn("authority", row)
                self.assertIsInstance(row.get("requires"), list)
                self.assertIsInstance(row.get("returns"), list)
                self.assertIsInstance(row.get("risk_hints"), dict)

    def test_compact_affordances_are_registry_aligned(self) -> None:
        compact = contracts.compact_tool_affordances()
        self.assertEqual(set(compact), _EXPECTED_TOOLS)
        for tool, row in compact.items():
            with self.subTest(tool=tool):
                self.assertIsInstance(row, dict)
                self.assertIn("capability", row)
                self.assertIn("returns", row)
                self.assertIn("state_effect", row)


if __name__ == "__main__":
    unittest.main()
