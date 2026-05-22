#!/usr/bin/env python3
"""Schema contract coverage for env.tool action definitions."""

from __future__ import annotations

from dataclasses import replace
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tool_runtime import registry as catalog  # noqa: E402
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition  # noqa: E402


_ENUM_FIELDS = {"status", "state", "health", "kind", "template", "target_type", "backend", "engine", "box", "type"}


def _type_has(schema: Mapping[str, Any], expected: str) -> bool:
    value = schema.get("type")
    if value == expected:
        return True
    if isinstance(value, list):
        return expected in value
    return False


class EnvToolSchemaContractTests(unittest.TestCase):
    def _assert_object_shape(self, schema: Mapping[str, Any], *, path: str) -> None:
        self.assertEqual(schema.get("type"), "object", msg=f"{path}.type")
        self.assertIs(schema.get("additionalProperties"), False, msg=f"{path}.additionalProperties")
        properties = schema.get("properties")
        self.assertIsInstance(properties, dict, msg=f"{path}.properties")
        required = schema.get("required")
        self.assertIsInstance(required, list, msg=f"{path}.required")
        assert isinstance(required, list)
        assert isinstance(properties, dict)
        self.assertTrue(
            all(isinstance(entry, str) and entry in properties for entry in required),
            msg=f"{path}.required entries must be declared properties",
        )

    def _assert_property_schema(
        self,
        *,
        property_schema: Mapping[str, Any],
        property_name: str,
        path: str,
    ) -> None:
        description = property_schema.get("description")
        self.assertIsInstance(description, str, msg=f"{path}.description")
        assert isinstance(description, str)
        self.assertTrue(description.strip(), msg=f"{path}.description must be non-empty")

        if property_name in _ENUM_FIELDS:
            enum_values = property_schema.get("enum")
            self.assertIsInstance(enum_values, list, msg=f"{path}.enum")
            assert isinstance(enum_values, list)
            self.assertTrue(enum_values, msg=f"{path}.enum must be non-empty")

        if _type_has(property_schema, "object"):
            self._assert_object_shape(property_schema, path=path)
            nested = property_schema.get("properties")
            assert isinstance(nested, dict)
            for nested_name, nested_schema in nested.items():
                if not isinstance(nested_name, str):
                    continue
                self.assertIsInstance(nested_schema, dict, msg=f"{path}.{nested_name}")
                assert isinstance(nested_schema, dict)
                self._assert_property_schema(
                    property_schema=nested_schema,
                    property_name=nested_name,
                    path=f"{path}.{nested_name}",
                )
            return

        if _type_has(property_schema, "array"):
            items = property_schema.get("items")
            self.assertIsInstance(items, dict, msg=f"{path}.items")
            assert isinstance(items, dict)
            if _type_has(items, "object"):
                self._assert_object_shape(items, path=f"{path}.items")

    def test_every_shipped_action_schema_is_complete(self) -> None:
        self.assertTrue(catalog.supported_tools())
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                action_definition = catalog.get_action_definition(tool, action)
                schema = action_definition.input_schema
                self.assertIsInstance(schema, dict, msg=f"{tool}.{action}.input_schema")
                assert isinstance(schema, dict)
                self._assert_object_shape(schema, path=f"{tool}.{action}.input_schema")
                self.assertTrue(action_definition.use_when, msg=f"{tool}.{action}.use_when")
                self.assertTrue(action_definition.do_not_use_when, msg=f"{tool}.{action}.do_not_use_when")
                self.assertTrue(all(isinstance(row, str) and row.strip() for row in action_definition.use_when))
                self.assertTrue(all(isinstance(row, str) and row.strip() for row in action_definition.do_not_use_when))
                properties = schema.get("properties")
                assert isinstance(properties, dict)
                for field_name, field_schema in properties.items():
                    if not isinstance(field_name, str):
                        continue
                    self.assertIsInstance(field_schema, dict, msg=f"{tool}.{action}.{field_name}")
                    assert isinstance(field_schema, dict)
                    self._assert_property_schema(
                        property_schema=field_schema,
                        property_name=field_name,
                        path=f"{tool}.{action}.{field_name}",
                    )

    def test_high_risk_schema_shapes_match_domain_contracts(self) -> None:
        self.assertIn("track", catalog.supported_tools())

        track_create = catalog.get_action_definition("track", "create").input_schema
        track_update_now = catalog.get_action_definition("track", "update_now").input_schema
        track_add_update = catalog.get_action_definition("track", "add_update").input_schema
        artifact_create = catalog.get_action_definition("artifact", "create_revision").input_schema
        buddybox_list = catalog.get_action_definition("buddybox", "list").input_schema
        buddybox_read = catalog.get_action_definition("buddybox", "read").input_schema
        comment_add = catalog.get_action_definition("comment", "add").input_schema
        task_create = catalog.get_action_definition("task", "create").input_schema
        task_list = catalog.get_action_definition("task", "list").input_schema
        context_get = catalog.get_action_definition("context", "get").input_schema
        context_summarize = catalog.get_action_definition("context", "summarize").input_schema
        evidence_issue = catalog.get_action_definition("evidence", "issue_browser").input_schema
        evidence_approve = catalog.get_action_definition("evidence", "approve_downgrade").input_schema
        search_request = catalog.get_action_definition("search", "request").input_schema
        search_open = catalog.get_action_definition("search", "open_browser").input_schema
        message_send = catalog.get_action_definition("message", "send").input_schema
        request_create = catalog.get_action_definition("request", "create").input_schema
        request_list = catalog.get_action_definition("request", "list").input_schema
        request_complete = catalog.get_action_definition("request", "complete").input_schema
        comment_resolve = catalog.get_action_definition("comment", "resolve").input_schema

        create_now = track_create["properties"]["now"]
        update_now = track_update_now["properties"]["now"]
        for row in (create_now, update_now):
            self.assertEqual(row.get("type"), "object")
            self.assertIs(row.get("additionalProperties"), False)
            self.assertEqual(row.get("required"), ["next"])
            self.assertEqual(row.get("properties", {}).get("next", {}).get("type"), "string")
            self.assertEqual(row.get("properties", {}).get("blocker", {}).get("type"), ["string", "null"])
            self.assertIsInstance(row.get("examples"), list)
            self.assertTrue(row.get("examples"))

        self.assertEqual(
            track_create["properties"]["state"].get("enum"),
            ["active", "blocked", "review", "done"],
        )
        self.assertEqual(
            track_create["properties"]["health"].get("enum"),
            ["ok", "risk", "blocked", "stale"],
        )
        self.assertEqual(
            track_add_update["properties"]["kind"].get("enum"),
            ["progress", "decision", "blocker", "proof"],
        )

        refs_items = track_add_update["properties"]["refs"].get("items", {})
        self.assertEqual(refs_items.get("type"), "object")
        self.assertIs(refs_items.get("additionalProperties"), False)
        self.assertEqual(refs_items.get("required"), ["type", "id"])
        self.assertEqual(refs_items.get("properties", {}).get("type", {}).get("enum"), ["artifact"])

        self.assertEqual(
            artifact_create["properties"]["template"].get("enum"),
            ["brief", "proposal", "design", "decision", "proof", "note"],
        )
        source_ref_items = artifact_create["properties"]["source_refs"].get("items", {})
        self.assertEqual(source_ref_items.get("type"), "object")
        variants = source_ref_items.get("anyOf")
        self.assertIsInstance(variants, list)
        assert isinstance(variants, list)
        self.assertGreaterEqual(len(variants), 6)
        variant_by_type: dict[str, dict[str, Any]] = {}
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            props = variant.get("properties")
            if not isinstance(props, dict):
                continue
            type_enum = props.get("type", {}).get("enum")
            if isinstance(type_enum, list) and len(type_enum) == 1 and isinstance(type_enum[0], str):
                variant_by_type[type_enum[0]] = variant
        for required_type in ("artifact", "track", "task", "buddybox", "external", "note"):
            self.assertIn(required_type, variant_by_type, msg=f"source_refs missing {required_type}")
        self.assertEqual(set(variant_by_type["artifact"]["required"]), {"type", "id"})
        self.assertEqual(set(variant_by_type["track"]["required"]), {"type", "id"})
        self.assertEqual(set(variant_by_type["task"]["required"]), {"type", "id"})
        self.assertEqual(set(variant_by_type["buddybox"]["required"]), {"type", "logical_name"})
        self.assertEqual(set(variant_by_type["external"]["required"]), {"type", "label"})
        self.assertEqual(set(variant_by_type["note"]["required"]), {"type", "label"})
        self.assertEqual(artifact_create["properties"]["read_claim"].get("type"), "string")

        self.assertEqual(buddybox_list["properties"]["recursive"].get("type"), "boolean")
        self.assertEqual(buddybox_list["properties"]["recursive"].get("default"), False)
        self.assertEqual(buddybox_list["properties"]["limit"].get("type"), "integer")
        self.assertEqual(buddybox_list["properties"]["limit"].get("minimum"), 1)
        self.assertEqual(buddybox_list["properties"]["limit"].get("default"), 200)
        self.assertEqual(buddybox_read["properties"]["encoding"].get("enum"), ["auto", "utf-8", "base64"])

        mentions = comment_add["properties"]["mentions"]
        self.assertEqual(mentions.get("type"), "array")
        self.assertEqual(mentions.get("items", {}).get("type"), "string")
        self.assertEqual(comment_add["properties"]["target_type"].get("enum"), ["track", "artifact", "artifact_section"])
        comment_list = catalog.get_action_definition("comment", "list").input_schema
        self.assertEqual(comment_list["properties"]["status"].get("enum"), ["open", "resolved", "all"])

        self.assertEqual(task_create["properties"]["status"].get("enum"), ["active", "blocked", "done", "archived"])
        self.assertEqual(task_list["properties"]["limit"].get("type"), "integer")
        self.assertEqual(task_list["properties"]["limit"].get("minimum"), 1)

        self.assertEqual(context_get["properties"]["limit"].get("type"), "integer")
        self.assertEqual(context_get["properties"]["limit"].get("minimum"), 1)
        self.assertEqual(context_summarize["properties"]["limit"].get("type"), "integer")
        self.assertEqual(context_summarize["properties"]["limit"].get("minimum"), 1)

        self.assertEqual(evidence_issue["properties"]["target_type"].get("enum"), ["artifact"])
        self.assertEqual(evidence_approve["properties"]["target_type"].get("enum"), ["artifact"])

        self.assertEqual(search_request["properties"]["backend"].get("enum"), ["browser", "search_api"])
        self.assertEqual(search_request["properties"]["engine"].get("enum"), ["google", "web", "reddit", "x"])
        self.assertEqual(search_open["properties"]["engine"].get("enum"), ["google", "web", "reddit", "x"])

        self.assertIn("manifest buddy id", message_send["properties"]["to_buddy"].get("description", ""))

        self.assertIn("track_id", request_create.get("required", []))
        self.assertIn("to_buddy", request_create.get("required", []))
        self.assertIn("title", request_create.get("required", []))
        self.assertIn("summary", request_create.get("required", []))
        target_ref = request_create["properties"]["target_refs"]["items"]
        self.assertEqual(target_ref.get("type"), "object")
        self.assertIs(target_ref.get("additionalProperties"), False)
        self.assertEqual(set(target_ref.get("required", [])), {"type", "id"})
        self.assertEqual(target_ref.get("properties", {}).get("type", {}).get("enum"), ["track", "artifact", "comment"])
        self.assertEqual(request_list["properties"]["box"].get("enum"), ["all", "inbox", "outbox"])
        self.assertEqual(request_list["properties"]["status"].get("enum"), ["open", "accepted", "blocked", "done", "canceled"])
        self.assertEqual(request_complete["properties"]["result_refs"].get("type"), "array")
        result_ref = request_complete["properties"]["result_refs"]["items"]
        self.assertEqual(result_ref.get("type"), "object")
        self.assertEqual(result_ref.get("properties", {}).get("type", {}).get("enum"), ["track", "artifact", "comment"])

        self.assertEqual(set(comment_resolve.get("required", [])), {"comment_id", "resolution_summary"})

    def test_artifact_list_schema_is_simple_and_bounded(self) -> None:
        artifact_list = catalog.get_action_definition("artifact", "list").input_schema
        self.assertEqual(artifact_list.get("required"), [])
        self.assertIs(artifact_list.get("additionalProperties"), False)
        properties = artifact_list.get("properties")
        self.assertIsInstance(properties, dict)
        assert isinstance(properties, dict)
        self.assertEqual(
            set(properties),
            {"track_id", "created_by", "template", "status", "q", "limit"},
        )
        self.assertEqual(
            properties["template"].get("enum"),
            ["brief", "proposal", "design", "decision", "proof", "note"],
        )
        self.assertEqual(
            properties["status"].get("enum"),
            ["draft", "published", "archived"],
        )
        self.assertEqual(properties["limit"].get("type"), "integer")
        self.assertEqual(properties["limit"].get("minimum"), 1)

    def test_action_definition_validation_requires_action_semantic_tuples(self) -> None:
        action = ActionDefinition(
            name="example_action",
            title="example.action",
            description="Example action.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "required": [],
                "properties": {},
            },
            output_schema={"$ref": "ToolResult"},
            kind="read",
            mutates="none",
            required_permission="none",
            authority="example.readonly",
            visibility="example reader",
            durability="none",
            result_content_level="example row",
            success_effect="Returns one example row without mutation.",
            failure_state_guarantee="Rejected reads do not mutate runtime state.",
            reads=("example rows",),
            writes=(),
            does_not_write=("example state",),
            use_when=("Use when example action is needed.",),
            do_not_use_when=("Do not use for write operations.",),
        )
        valid = ToolDefinition(
            id="example",
            title="Example",
            description="Example tool",
            cli_resource="example",
            command="python3 scripts/env/client.py example do --payload '{}'",
            scope="example scope",
            capability_boundary="example capability boundary",
            object_model="Example objects are test-only validation rows.",
            use_when=("Use for example checks.",),
            do_not_use_when=("Do not use for non-example work.",),
            actions=(action,),
        )
        validate_definition(valid)

        with self.assertRaisesRegex(ValueError, "example.example_action.use_when"):
            validate_definition(replace(valid, actions=(replace(action, use_when=()),)))
        with self.assertRaisesRegex(ValueError, "example.example_action.do_not_use_when"):
            validate_definition(replace(valid, actions=(replace(action, do_not_use_when=()),)))
        with self.assertRaisesRegex(ValueError, "example.example_action.does_not_write"):
            validate_definition(replace(valid, actions=(replace(action, does_not_write=()),)))


if __name__ == "__main__":
    unittest.main()
