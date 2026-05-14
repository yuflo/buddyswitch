#!/usr/bin/env python3
"""Runtime semantic contract coverage for env.tool registry projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tools import contracts  # noqa: E402

_CAPABILITY_KEYS = {
    "title",
    "plain_description",
    "use_when",
    "do_not_use_when",
    "capability_boundary",
}
_ACTION_KEYS = {
    "title",
    "plain_description",
    "use_when",
    "do_not_use_when",
    "inputs_explained",
    "side_effects",
    "risk_hints",
    "success_means",
    "common_failures",
}
_SIDE_EFFECT_KEYS = {"mutates", "writes", "does_not_write", "durability", "idempotency"}
_RISK_HINT_KEYS = {
    "read_only",
    "destructive",
    "idempotent",
    "open_world",
    "requires_human_approval",
    "external_effect",
}
_LOW_SIGNAL_EXACT = {
    "n/a",
    "na",
    "none",
    "use this tool",
    "use this action",
    "todo",
    "tbd",
}


def _expected_tool_action_sets() -> tuple[set[str], dict[str, set[str]]]:
    tools: set[str] = set()
    actions_by_tool: dict[str, set[str]] = {}
    for spec in contracts.TOOL_REGISTRY:
        tool = spec["tool"]
        tools.add(tool)
        actions_by_tool[tool] = {row["name"] for row in spec["actions"]}
    return tools, actions_by_tool


class EnvToolSemanticContractTests(unittest.TestCase):
    def _assert_quality_text(self, value: Any, *, label: str, forbid_equals: set[str] | None = None) -> None:
        self.assertIsInstance(value, str, msg=label)
        assert isinstance(value, str)
        stripped = value.strip()
        self.assertTrue(stripped, msg=label)
        lowered = stripped.lower()
        self.assertNotIn(lowered, _LOW_SIGNAL_EXACT, msg=label)
        self.assertNotEqual(lowered, label.lower(), msg=label)
        if forbid_equals is not None:
            self.assertNotIn(lowered, {token.lower() for token in forbid_equals}, msg=label)
        if label.endswith("plain_description") or label.endswith("success_means"):
            self.assertGreaterEqual(len(stripped), 12, msg=label)

    def test_registry_semantics_cover_every_registered_tool_and_action(self) -> None:
        desc = contracts.env_tools_description()
        expected_tools, expected_actions = _expected_tool_action_sets()
        self.assertEqual(set(desc), expected_tools)

        for tool in sorted(expected_tools):
            with self.subTest(tool=tool):
                row = desc[tool]
                self.assertTrue(_CAPABILITY_KEYS.issubset(set(row)))
                self.assertEqual(set(row["operations"]), expected_actions[tool])
                payload_fields = row["payload_fields"]
                self.assertEqual(set(payload_fields), expected_actions[tool])
                action_semantics = row["action_semantics"]
                self.assertEqual(set(action_semantics), expected_actions[tool])

        self.assertEqual(contracts.semantic_contract_errors(), [])

    def test_action_semantics_explain_inputs_side_effects_and_success(self) -> None:
        desc = contracts.env_tools_description()
        for tool_spec in contracts.TOOL_REGISTRY:
            tool = tool_spec["tool"]
            for action_spec in tool_spec["actions"]:
                action = action_spec["name"]
                key = f"{tool}.{action}"
                with self.subTest(action=key):
                    semantic = desc[tool]["action_semantics"][action]
                    self.assertTrue(_ACTION_KEYS.issubset(set(semantic)))
                    side_effects = semantic["side_effects"]
                    self.assertTrue(_SIDE_EFFECT_KEYS.issubset(set(side_effects)))
                    self.assertEqual(side_effects["mutates"], action_spec["mutates"])
                    self.assertIsInstance(side_effects["writes"], list)
                    self.assertIsInstance(side_effects["does_not_write"], list)
                    self.assertIsInstance(side_effects["durability"], str)
                    self.assertIsInstance(side_effects["idempotency"], str)

                    payload_fields = list(action_spec["payload_fields"])
                    inputs_explained = semantic["inputs_explained"]
                    self.assertIsInstance(inputs_explained, dict)
                    self.assertEqual(set(inputs_explained), set(payload_fields))
                    if not payload_fields:
                        self.assertEqual(inputs_explained, {})

                    risk_hints = semantic["risk_hints"]
                    self.assertTrue(_RISK_HINT_KEYS.issubset(set(risk_hints)))
                    for bool_key in ("read_only", "destructive", "open_world", "requires_human_approval", "external_effect"):
                        self.assertIsInstance(risk_hints[bool_key], bool)

                    if action_spec["mutates"] == contracts.MUTATES_NONE:
                        self.assertEqual(side_effects["writes"], [])
                        self.assertTrue(risk_hints["read_only"])
                    else:
                        self.assertGreaterEqual(len(side_effects["writes"]), 1)
                        self.assertGreaterEqual(len(side_effects["does_not_write"]), 1)
                        self.assertFalse(risk_hints["read_only"])

                    self._assert_quality_text(semantic["success_means"], label=f"{key}.success_means")
                    common_failures = semantic["common_failures"]
                    self.assertIsInstance(common_failures, list)
                    self.assertGreaterEqual(len(common_failures), 1)
                    for index, row in enumerate(common_failures):
                        self._assert_quality_text(row, label=f"{key}.common_failures[{index}]")

    def test_semantic_text_rejects_low_signal_placeholders(self) -> None:
        desc = contracts.env_tools_description()
        for tool, row in sorted(desc.items()):
            with self.subTest(tool=tool):
                self._assert_quality_text(row["title"], label=f"{tool}.title", forbid_equals={tool})
                self._assert_quality_text(
                    row["plain_description"],
                    label=f"{tool}.plain_description",
                    forbid_equals={tool},
                )
                self.assertIsInstance(row["use_when"], list)
                self.assertIsInstance(row["do_not_use_when"], list)
                for idx, text in enumerate(row["use_when"]):
                    self._assert_quality_text(text, label=f"{tool}.use_when[{idx}]")
                for idx, text in enumerate(row["do_not_use_when"]):
                    self._assert_quality_text(text, label=f"{tool}.do_not_use_when[{idx}]")

            for action, semantic in sorted(row["action_semantics"].items()):
                key = f"{tool}.{action}"
                with self.subTest(action=key):
                    self._assert_quality_text(semantic["title"], label=f"{key}.title", forbid_equals={tool, action, key})
                    self._assert_quality_text(
                        semantic["plain_description"],
                        label=f"{key}.plain_description",
                        forbid_equals={tool, action, key},
                    )
                    for idx, text in enumerate(semantic["use_when"]):
                        self._assert_quality_text(text, label=f"{key}.use_when[{idx}]")
                    for idx, text in enumerate(semantic["do_not_use_when"]):
                        self._assert_quality_text(text, label=f"{key}.do_not_use_when[{idx}]")
                    for field_name, text in semantic["inputs_explained"].items():
                        self._assert_quality_text(
                            text,
                            label=f"{key}.inputs_explained.{field_name}",
                            forbid_equals={field_name, key, action},
                        )

    def test_risk_hints_match_mutation_and_open_world_behavior(self) -> None:
        desc = contracts.env_tools_description()
        by_action = {
            f"{tool}.{action}": desc[tool]["action_semantics"][action]
            for tool_spec in contracts.TOOL_REGISTRY
            for tool in [tool_spec["tool"]]
            for action_spec in tool_spec["actions"]
            for action in [action_spec["name"]]
        }
        self.assertTrue(by_action["search.open_browser"]["risk_hints"]["open_world"])
        self.assertTrue(by_action["search.open_browser"]["risk_hints"]["external_effect"])
        self.assertFalse(by_action["run.commit"]["risk_hints"]["read_only"])
        self.assertFalse(by_action["evidence.issue_browser"]["risk_hints"]["read_only"])
        for key, semantic in sorted(by_action.items()):
            with self.subTest(action=key):
                self.assertNotIn("enforces_permission", semantic["risk_hints"])
                self.assertNotIn("authorization_decision", semantic["risk_hints"])

    def test_operation_semantics_machine_contract_is_preserved(self) -> None:
        op = contracts.operation_semantics()
        _, expected_actions = _expected_tool_action_sets()
        expected_keys = {f"{tool}.{action}" for tool, actions in expected_actions.items() for action in actions}
        self.assertEqual(set(op), expected_keys)
        required = {"kind", "mutates", "required_permission", "authority", "requires", "returns"}
        for action_key, row in sorted(op.items()):
            with self.subTest(action=action_key):
                self.assertTrue(required.issubset(set(row)))
                self.assertIsInstance(row["requires"], list)
                self.assertIsInstance(row["returns"], list)


if __name__ == "__main__":
    unittest.main()
