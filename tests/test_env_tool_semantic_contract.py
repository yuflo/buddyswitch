#!/usr/bin/env python3
"""Runtime semantic contract coverage for env.tool registry projection."""

from __future__ import annotations

import json
import re
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
_TEMPLATE_PATTERNS = (
    re.compile(r"you need\s+[a-z_]+\.[a-z_]+\s+behavior"),
    re.compile(r"execute\s+[a-z_]+\.[a-z_]+"),
    re.compile(r"returned structured state"),
    re.compile(r"completed with explicit ids"),
    re.compile(r"semantic metadata for action"),
    re.compile(r"structured capability feedback"),
)


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
        self.assertNotIn("memory", expected_tools)
        self.assertIn("buddybox", expected_tools)
        self.assertNotIn("run", expected_tools)
        self.assertNotIn("binding", expected_tools)
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

    def test_semantic_text_rejects_template_action_language(self) -> None:
        desc = contracts.env_tools_description()
        for tool, row in sorted(desc.items()):
            for action, semantic in sorted(row["action_semantics"].items()):
                key = f"{tool}.{action}"
                checks = [
                    str(semantic.get("plain_description", "")),
                    str(semantic.get("success_means", "")),
                    *[str(text) for text in semantic.get("use_when", [])],
                ]
                for text in checks:
                    lowered = text.strip().lower()
                    with self.subTest(action=key, text=text):
                        for pattern in _TEMPLATE_PATTERNS:
                            self.assertIsNone(
                                pattern.search(lowered),
                                msg=f"{key} contains template phrase: {text}",
                            )

    def test_action_semantics_explain_content_level_state_effect_and_durability(self) -> None:
        desc = contracts.env_tools_description()
        for tool_spec in contracts.TOOL_REGISTRY:
            tool = str(tool_spec["tool"])
            for action_spec in tool_spec["actions"]:
                action = str(action_spec["name"])
                key = f"{tool}.{action}"
                semantic = desc[tool]["action_semantics"][action]
                text = " ".join(
                    [
                        str(semantic.get("plain_description", "")),
                        str(semantic.get("success_means", "")),
                        *[str(row) for row in semantic.get("use_when", [])],
                        *[str(row) for row in semantic.get("inputs_explained", {}).values()],
                    ]
                ).lower()
                side_effects = semantic["side_effects"]
                mutates = str(action_spec["mutates"])

                with self.subTest(action=key):
                    self.assertEqual(side_effects["mutates"], mutates)
                    self.assertIsInstance(side_effects.get("durability"), str)
                    self.assertNotIn("semantic metadata", text)

                    if action == "list":
                        self.assertTrue("summary" in text or "record" in text, msg=text)
                    if action in {"get", "read"} and key != "context.get":
                        self.assertTrue(
                            "id" in text or "logical_name" in text or "logical name" in text,
                            msg=text,
                        )
                    if "validate" in action:
                        self.assertIn("validat", text, msg=text)
                        self.assertTrue(
                            "no write" in text
                            or "without writing" in text
                            or "no mutat" in text,
                            msg=text,
                        )
                        self.assertEqual(side_effects["mutates"], contracts.MUTATES_NONE)
                    if action in {"create", "update", "archive", "delete", "attach_task", "detach_task", "advance", "join", "open_browser"}:
                        if side_effects["mutates"] != contracts.MUTATES_NONE:
                            self.assertTrue(
                                any(token in text for token in ("create", "update", "archive", "delete", "open", "write", "attach", "detach", "join", "advanc")),
                                msg=text,
                            )

                    if key.startswith("artifact.list"):
                        self.assertIn("summary", text, msg=text)
                        self.assertTrue(
                            "no full" in text
                            or "not full" in text
                            or "excluded" in text
                            or "without full artifact content" in text,
                            msg=text,
                        )
                    if key.startswith("artifact.get"):
                        self.assertTrue("full" in text and "content" in text, msg=text)
                    if key.startswith("buddybox.read"):
                        self.assertTrue("content" in text or "content_base64" in text, msg=text)
                    if key.startswith("evidence."):
                        self.assertIn("token", text, msg=text)
                        self.assertIn("target", text, msg=text)
                        self.assertIn("transient", str(side_effects.get("durability", "")).lower())
                    if key == "search.status":
                        self.assertTrue("metadata" in text or "status" in text, msg=text)
                    if key == "search.request":
                        self.assertTrue("target url" in text or "browser intent" in text, msg=text)
                        self.assertTrue("not open" in text or "without opening" in text, msg=text)
                    if key == "search.open_browser":
                        self.assertIn("browser", text, msg=text)
                        self.assertIn("session", str(side_effects.get("durability", "")).lower(), msg=side_effects)

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
        self.assertNotIn("memory.write", by_action)
        self.assertFalse(by_action["buddybox.write"]["risk_hints"]["read_only"])
        self.assertFalse(by_action["evidence.issue_browser"]["risk_hints"]["read_only"])
        self.assertNotIn("run.commit", by_action)
        self.assertNotIn("binding.get", by_action)
        for key, semantic in sorted(by_action.items()):
            with self.subTest(action=key):
                self.assertNotIn("enforces_permission", semantic["risk_hints"])
                self.assertNotIn("authorization_decision", semantic["risk_hints"])

    def test_operation_semantics_machine_contract_is_preserved(self) -> None:
        op = contracts.operation_semantics()
        _, expected_actions = _expected_tool_action_sets()
        expected_keys = {f"{tool}.{action}" for tool, actions in expected_actions.items() for action in actions}
        self.assertEqual(set(op), expected_keys)
        desc = contracts.env_tools_description()
        for forbidden in ("semantic_v2", "schema_version", "workflow_engine", "parallel_catalog"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, desc)
        required = {"kind", "mutates", "required_permission", "authority", "requires", "returns"}
        for action_key, row in sorted(op.items()):
            with self.subTest(action=action_key):
                self.assertTrue(required.issubset(set(row)))
                self.assertIsInstance(row["requires"], list)
                self.assertIsInstance(row["returns"], list)

    def test_buddybox_semantics_explain_private_local_workspace_boundary(self) -> None:
        desc = contracts.env_tools_description()
        buddybox = desc["buddybox"]
        capability_text = json.dumps(
            {
                "plain_description": buddybox["plain_description"],
                "use_when": buddybox["use_when"],
                "do_not_use_when": buddybox["do_not_use_when"],
            },
            ensure_ascii=True,
        ).lower().replace("-", " ")
        for token in (
            "active buddy",
            "private",
            "private file",
            "logical_name",
            "active instance local",
            "artifact",
        ):
            self.assertIn(token, capability_text)
        self.assertIn("not product object", capability_text)

        actions = buddybox["action_semantics"]
        self.assertIn("desc", actions)
        desc_semantic = actions["desc"]
        self.assertEqual(desc_semantic["inputs_explained"], {})
        self.assertEqual(desc_semantic["side_effects"]["writes"], [])
        self.assertTrue(desc_semantic["risk_hints"]["read_only"])

    def test_buddybox_semantics_cover_file_output_affordances_and_output_meanings(self) -> None:
        desc = contracts.env_tools_description()
        buddybox = desc["buddybox"]
        capability_text = json.dumps(
            {
                "plain_description": buddybox["plain_description"],
                "use_when": buddybox["use_when"],
                "do_not_use_when": buddybox["do_not_use_when"],
                "capability_boundary": buddybox["capability_boundary"],
            },
            ensure_ascii=True,
        ).lower().replace("-", " ")
        for token in (
            "active buddy",
            "private",
            "private file",
            "drafts",
            "lightweight prototypes",
            "exports",
            "reports",
            "logs",
            "generated files",
            "binary outputs",
            "active instance local",
            "not product object",
            "artifact",
            "product readable",
        ):
            with self.subTest(token=token):
                self.assertIn(token, capability_text)

        actions = buddybox["action_semantics"]
        for action, success_text in {
            name: str(row["success_means"]).lower().replace("-", " ")
            for name, row in actions.items()
        }.items():
            with self.subTest(action=action):
                if action == "desc":
                    self.assertIn("capability", success_text)
                    self.assertIn("summary", success_text)
                    self.assertTrue("descriptor" in success_text or "metadata" in success_text, msg=success_text)
                elif action == "list":
                    self.assertIn("summary", success_text)
                    self.assertTrue("no content" in success_text or "excluded" in success_text, msg=success_text)
                elif action == "read":
                    self.assertIn("private file", success_text)
                    self.assertIn("content", success_text)
                    self.assertIn("content_base64", success_text)
                elif action == "write":
                    self.assertIn("private file", success_text)
                    self.assertTrue("created" in success_text or "overwritten" in success_text, msg=success_text)
                    self.assertTrue("without product object mutation" in success_text or "no product object mutation" in success_text, msg=success_text)
                elif action == "delete":
                    self.assertTrue("deleted" in success_text or "already_absent" in success_text, msg=success_text)
                    self.assertTrue("no product object mutation" in success_text or "no product collaboration object changed" in success_text, msg=success_text)

    def test_buddybox_action_semantics_explain_input_formats_and_output_fields(self) -> None:
        actions = contracts.env_tools_description()["buddybox"]["action_semantics"]

        for action in ("list", "read", "write", "delete"):
            fields = actions[action]["inputs_explained"]
            self.assertIn("logical_name", fields, msg=action)
            self.assertNotIn("path", fields, msg=action)
            logical_name_text = str(fields["logical_name"]).lower().replace("-", " ")
            self.assertIn("logical", logical_name_text, msg=action)
            self.assertIn("active buddy", logical_name_text, msg=action)

        write_fields = actions["write"]["inputs_explained"]
        self.assertIn("utf-8 text", str(write_fields["content"]).lower())
        self.assertIn("binary", str(write_fields["content_base64"]).lower())
        self.assertIn("non-utf-8", str(write_fields["content_base64"]).lower())
        self.assertIn("mime hint", str(write_fields["content_type"]).lower())
        self.assertIn("not a product contract", str(write_fields["content_type"]).lower())

        read_fields = actions["read"]["inputs_explained"]
        encoding_text = str(read_fields["encoding"]).lower()
        for token in ("auto", "utf-8", "base64"):
            self.assertIn(token, encoding_text)

    def test_buddybox_semantics_reject_old_ambiguous_wording(self) -> None:
        desc = contracts.env_tools_description()
        packed = json.dumps(desc["buddybox"], ensure_ascii=True).lower()
        self.assertNotIn("durable buddy-" + "owned", packed)
        self.assertNotIn("readable buddybox " + "scope", packed)
        self.assertNotIn("source_ref read authority", packed)

    def test_buddybox_semantics_keep_host_decision_space(self) -> None:
        desc = contracts.env_tools_description()
        actions = desc["buddybox"]["action_semantics"]
        packed = json.dumps(actions, ensure_ascii=True).lower()
        for forbidden in (
            "prototype means",
            "hardcoded trigger",
            "only next action",
            "always create artifact",
            "must create artifact",
            "must create artifact after buddybox.write",
            "artifact-required-for-cross-buddy-readable-content",
        ):
            self.assertNotIn(forbidden, packed)

        local_affordance_actions = 0
        conditional_readable_actions = 0
        for action_name, row in sorted(actions.items()):
            with self.subTest(action=action_name):
                use_when_text = " ".join(str(item) for item in row.get("use_when", [])).lower()
                if "private file" in use_when_text:
                    local_affordance_actions += 1
                if "artifact" in use_when_text and "host decides" in use_when_text:
                    conditional_readable_actions += 1
                self.assertNotIn("must ", use_when_text)

        self.assertGreaterEqual(local_affordance_actions, 1)
        self.assertGreaterEqual(conditional_readable_actions, 1)

    def test_buddybox_current_operations_do_not_conflate_read_list_and_search(self) -> None:
        self.assertEqual(contracts.supported_actions("buddybox"), {"desc", "list", "read", "write", "delete"})
        buddybox = contracts.env_tools_description()["buddybox"]["action_semantics"]
        self.assertNotIn("search", buddybox)

        read_text = json.dumps(
            {
                "plain_description": buddybox["read"]["plain_description"],
                "use_when": buddybox["read"]["use_when"],
                "success_means": buddybox["read"]["success_means"],
            },
            ensure_ascii=True,
        ).lower()
        self.assertIn("one", read_text)
        self.assertTrue("exact" in read_text or "logical_name" in read_text, msg=read_text)

        list_text = json.dumps(
            {
                "plain_description": buddybox["list"]["plain_description"],
                "success_means": buddybox["list"]["success_means"],
            },
            ensure_ascii=True,
        ).lower()
        self.assertIn("summary", list_text)
        self.assertTrue("no content" in list_text or "excluded" in list_text, msg=list_text)

    def test_buddybox_semantics_do_not_expose_filesystem_roots(self) -> None:
        catalog_blob = json.dumps(contracts.env_tools_description()["buddybox"], ensure_ascii=True).lower()
        write_blob = json.dumps(contracts.operation_semantics()["buddybox.write"], ensure_ascii=True).lower()
        for token in (
            "buddyswitch/local/buddybox",
            "<active_buddy>",
            "logical_root",
            "source_of_truth",
            "shared root",
            "workspace root",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, catalog_blob)
                self.assertNotIn(token, write_blob)


if __name__ == "__main__":
    unittest.main()
