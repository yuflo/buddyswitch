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

from env.tool_runtime import registry as catalog  # noqa: E402

_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment"}
_EXPECTED_ACTIONS_BY_TOOL = {
    "task": {"create", "list", "get", "update", "archive"},
    "track": {"create", "list", "open", "update_now", "add_material", "add_update", "add_proof", "archive"},
    "artifact": {"get", "create_revision", "update_metadata"},
    "buddybox": {"desc", "list", "read", "write", "delete"},
    "context": {"get", "summarize", "list_sources"},
    "evidence": {"issue_browser", "approve_downgrade"},
    "search": {"status", "request", "open_browser"},
    "message": {"send", "list"},
    "comment": {"add", "list"},
}


class EnvToolSemanticContractTests(unittest.TestCase):
    def test_registry_semantics_cover_every_registered_tool_and_action(self) -> None:
        desc = catalog.env_tools_description()
        registry_tools = set(catalog.supported_tools())

        self.assertEqual(registry_tools, _EXPECTED_TOOLS)
        self.assertEqual(set(desc), _EXPECTED_TOOLS)
        self.assertEqual(catalog.semantic_contract_errors(), [])

        for tool in sorted(registry_tools):
            expected_actions = set(catalog.supported_actions(tool))
            self.assertEqual(expected_actions, _EXPECTED_ACTIONS_BY_TOOL[tool])
            self.assertEqual(set(desc[tool]["operations"]), expected_actions)
            self.assertEqual(set(desc[tool]["payload_fields"]), expected_actions)
            self.assertEqual(set(desc[tool]["action_semantics"]), expected_actions)

    def test_handoff_and_track_advance_are_absent(self) -> None:
        by_tool = {tool: set(catalog.supported_actions(tool)) for tool in catalog.supported_tools()}
        self.assertNotIn("handoff", by_tool)
        self.assertNotIn("advance", by_tool["track"])
        self.assertNotIn("resolve", by_tool["comment"])
        self.assertNotIn("reopen", by_tool["comment"])

        op = catalog.operation_semantics()
        self.assertNotIn("track.advance", op)
        self.assertFalse(any(key.startswith("handoff.") for key in op))
        self.assertNotIn("comment.resolve", op)
        self.assertNotIn("comment.reopen", op)

    def test_operation_semantics_machine_contract_is_preserved(self) -> None:
        op = catalog.operation_semantics()
        expected_keys = {
            f"{tool}.{action}"
            for tool in catalog.supported_tools()
            for action in catalog.supported_actions(tool)
        }
        self.assertEqual(set(op), expected_keys)
        self.assertEqual(
            expected_keys,
            {f"{tool}.{action}" for tool, actions in _EXPECTED_ACTIONS_BY_TOOL.items() for action in actions},
        )

        for key, row in op.items():
            with self.subTest(action=key):
                self.assertIn("kind", row)
                self.assertIn("mutates", row)
                self.assertIn("required_permission", row)
                self.assertIn("authority", row)
                self.assertIsInstance(row.get("requires"), list)
                self.assertIsInstance(row.get("returns"), list)
                self.assertIsInstance(row.get("risk_hints"), dict)

    def test_critical_track_artifact_action_semantics_are_not_placeholders(self) -> None:
        op = catalog.operation_semantics()
        critical = (
            "track.create",
            "track.open",
            "track.add_material",
            "track.add_proof",
            "artifact.create_revision",
            "artifact.get",
        )
        for key in critical:
            semantic = op.get(key)
            self.assertIsInstance(semantic, dict, msg=key)
            assert isinstance(semantic, dict)
            with self.subTest(action=key):
                self.assertIsInstance(semantic.get("risk_hints"), dict)
                full_semantic = catalog.env_tools_description()[key.split(".", 1)[0]]["action_semantics"][key.split(".", 1)[1]]
                self.assertIsInstance(full_semantic.get("use_when"), list)
                self.assertGreater(len(full_semantic.get("use_when", [])), 0)
                self.assertIsInstance(full_semantic.get("do_not_use_when"), list)
                self.assertGreater(len(full_semantic.get("do_not_use_when", [])), 0)
                self.assertIsInstance(full_semantic.get("inputs_explained"), dict)
                self.assertGreater(len(full_semantic.get("inputs_explained", {})), 0)
                self.assertIsInstance(full_semantic.get("common_failures"), list)
                self.assertGreater(len(full_semantic.get("common_failures", [])), 0)
                self.assertIsInstance(full_semantic.get("success_means"), str)
                self.assertNotIn("Operation completed with structured tool feedback.", full_semantic.get("success_means", ""))

    def test_publication_payload_fields_match_single_publication_path(self) -> None:
        desc = catalog.env_tools_description()
        track_fields = desc["track"]["payload_fields"]
        artifact_fields = desc["artifact"]["payload_fields"]
        self.assertEqual(track_fields["add_material"], ["track_id", "artifact_id", "label", "summary"])
        self.assertEqual(track_fields["add_proof"], ["track_id", "artifact_id", "label", "summary"])
        self.assertEqual(
            artifact_fields["create_revision"],
            ["artifact_id", "title", "summary", "template", "body", "supersedes_artifact_id", "source_refs", "read_claim"],
        )
        self.assertEqual(
            artifact_fields["update_metadata"],
            ["artifact_id", "title", "summary", "template", "body", "source_refs", "read_claim"],
        )

    def test_compact_affordances_are_registry_aligned(self) -> None:
        compact = catalog.compact_tool_affordances()
        self.assertEqual(set(compact), _EXPECTED_TOOLS)
        for tool, row in compact.items():
            with self.subTest(tool=tool):
                self.assertIsInstance(row, dict)
                self.assertIn("capability", row)
                self.assertIn("returns", row)
                self.assertIn("state_effect", row)

    def test_comment_payload_fields_match_active_comment_capability(self) -> None:
        desc = catalog.env_tools_description()
        comment_fields = desc["comment"]["payload_fields"]
        self.assertEqual(
            comment_fields["add"],
            ["target_type", "target_id", "content", "reply_to", "artifact_revision_id", "anchor", "mentions"],
        )
        self.assertEqual(comment_fields["list"], ["target_type", "target_id", "status"])

    def test_full_catalog_exposes_input_schemas_from_definitions(self) -> None:
        desc = catalog.env_tools_description()
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                action_def = catalog.get_action_definition(tool, action)
                self.assertEqual(desc[tool]["input_schemas"][action], action_def.input_schema)

    def test_inputs_explained_are_derived_from_schema_descriptions(self) -> None:
        desc = catalog.env_tools_description()
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                schema = catalog.get_action_definition(tool, action).input_schema
                properties = schema.get("properties") or {}
                self.assertIsInstance(properties, dict, msg=f"{tool}.{action}")
                assert isinstance(properties, dict)
                explanations = desc[tool]["action_semantics"][action]["inputs_explained"]
                self.assertEqual(set(explanations), set(properties))
                for field, field_schema in properties.items():
                    self.assertIsInstance(field_schema, dict, msg=f"{tool}.{action}.{field}")
                    assert isinstance(field_schema, dict)
                    description = field_schema.get("description")
                    self.assertIsInstance(description, str, msg=f"{tool}.{action}.{field}.description")
                    assert isinstance(description, str)
                    self.assertIn(description, explanations[field])
                    self.assertNotIn("payload field", explanations[field])


if __name__ == "__main__":
    unittest.main()
