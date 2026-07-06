#!/usr/bin/env python3
"""Schema contract coverage for env.tool action definitions."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tool_runtime import registry as catalog  # noqa: E402
from env.tool_runtime.definition import ActionDefinition, TASK_REQUIREMENT_FREE, ToolDefinition, validate_definition  # noqa: E402


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
        track_update_status = catalog.get_action_definition("track", "update_status").input_schema
        track_update_requirements = catalog.get_action_definition("track", "update_requirements").input_schema
        track_add_update = catalog.get_action_definition("track", "add_update").input_schema
        track_add_comment = catalog.get_action_definition("track", "add_comment").input_schema
        track_list_comments = catalog.get_action_definition("track", "list_comments").input_schema
        track_resolve_comment = catalog.get_action_definition("track", "resolve_comment_thread").input_schema
        artifact_create = catalog.get_action_definition("artifact", "create_revision").input_schema
        self.assertEqual(set(catalog.supported_actions("task_sys")), {"list", "get", "close", "need_parent"})
        task_sys_list = catalog.get_action_definition("task_sys", "list").input_schema
        task_sys_get = catalog.get_action_definition("task_sys", "get").input_schema
        task_sys_close = catalog.get_action_definition("task_sys", "close").input_schema
        task_sys_need_parent = catalog.get_action_definition("task_sys", "need_parent").input_schema
        context_get = catalog.get_action_definition("context", "get").input_schema
        context_summarize = catalog.get_action_definition("context", "summarize").input_schema
        evidence_issue = catalog.get_action_definition("evidence", "issue_browser").input_schema
        evidence_approve = catalog.get_action_definition("evidence", "approve_downgrade").input_schema
        search_request = catalog.get_action_definition("search", "request").input_schema
        search_open = catalog.get_action_definition("search", "open_browser").input_schema
        message_send_action = catalog.get_action_definition("message", "send")
        message_send = message_send_action.input_schema
        message_contacts_action = catalog.get_action_definition("message", "contacts")
        message_get_action = catalog.get_action_definition("message", "get")
        message_get = message_get_action.input_schema
        message_mark_action = catalog.get_action_definition("message", "mark")
        message_mark = message_mark_action.input_schema
        message_list_action = catalog.get_action_definition("message", "list")
        message_list = message_list_action.input_schema
        message_conversation_action = catalog.get_action_definition("message", "conversation")
        message_conversation = message_conversation_action.input_schema
        self.assertNotIn("comment", catalog.supported_tools())

        create_now = track_create["properties"]["now"]
        update_now = track_update_status["properties"]["now"]
        for row in (create_now, update_now):
            self.assertEqual(row.get("type"), "object")
            self.assertIs(row.get("additionalProperties"), False)
            self.assertEqual(row.get("required"), ["next"])
            self.assertEqual(row.get("properties", {}).get("next", {}).get("type"), "string")
            self.assertEqual(row.get("properties", {}).get("blocker", {}).get("type"), ["string", "null"])
            self.assertIsInstance(row.get("examples"), list)
            self.assertTrue(row.get("examples"))

        self.assertNotIn("state", track_create["properties"])
        self.assertNotIn("health", track_create["properties"])
        self.assertNotIn("appetite", track_create["properties"])
        self.assertNotIn("owner_role", track_create["properties"])
        self.assertNotIn("created_by_actor", track_create["properties"])
        self.assertEqual(
            track_update_status["properties"]["state"].get("enum"),
            ["active", "blocked", "done"],
        )
        self.assertIn("acceptance_criteria", track_update_requirements["properties"])
        self.assertIn("non_goals", track_update_requirements["properties"])
        self.assertEqual(
            track_add_update["properties"]["kind"].get("enum"),
            ["progress", "decision", "blocker"],
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
        self.assertGreaterEqual(len(variants), 5)
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
        for required_type in ("artifact", "track", "task", "external", "note"):
            self.assertIn(required_type, variant_by_type, msg=f"source_refs missing {required_type}")
        self.assertNotIn("actor_private", variant_by_type)
        self.assertEqual(set(variant_by_type["artifact"]["required"]), {"type", "id"})
        self.assertEqual(set(variant_by_type["track"]["required"]), {"type", "id"})
        self.assertEqual(set(variant_by_type["task"]["required"]), {"type", "id"})
        self.assertEqual(set(variant_by_type["external"]["required"]), {"type", "label"})
        self.assertEqual(set(variant_by_type["note"]["required"]), {"type", "label"})
        self.assertEqual(artifact_create["properties"]["read_claim"].get("type"), "string")

        mentions = track_add_comment["properties"]["mentioned_identity_ids"]
        self.assertEqual(mentions.get("type"), "array")
        self.assertEqual(mentions.get("items", {}).get("type"), "string")
        self.assertEqual(set(track_add_comment.get("required", [])), {"track_id", "content"})
        self.assertNotIn("target_type", track_add_comment["properties"])
        self.assertNotIn("target_id", track_add_comment["properties"])
        self.assertNotIn("anchor", track_add_comment["properties"])
        self.assertNotIn("artifact_revision_id", track_add_comment["properties"])
        self.assertEqual(track_list_comments["properties"]["status"].get("enum"), ["open", "resolved", "all"])

        self.assertEqual(task_sys_list.get("required"), [])
        self.assertEqual(task_sys_list["properties"]["status"].get("enum"), ["active", "recoverable", "all"])
        self.assertEqual(task_sys_list["properties"]["limit"].get("type"), "integer")
        self.assertEqual(task_sys_list["properties"]["limit"].get("minimum"), 1)
        self.assertEqual(task_sys_get.get("required"), ["task_id"])
        self.assertEqual(task_sys_get["properties"]["task_id"].get("type"), "string")
        self.assertEqual(task_sys_close.get("required"), ["task_id"])
        self.assertEqual(task_sys_need_parent.get("required"), ["task_id", "params"])
        self.assertEqual(task_sys_need_parent["properties"]["params"]["properties"]["interrupt"].get("type"), "boolean")

        self.assertEqual(context_get["properties"]["limit"].get("type"), "integer")
        self.assertEqual(context_get["properties"]["limit"].get("minimum"), 1)
        self.assertEqual(context_summarize["properties"]["limit"].get("type"), "integer")
        self.assertEqual(context_summarize["properties"]["limit"].get("minimum"), 1)

        self.assertEqual(evidence_issue["properties"]["target_type"].get("enum"), ["artifact"])
        self.assertEqual(evidence_approve["properties"]["target_type"].get("enum"), ["artifact"])

        self.assertEqual(search_request["properties"]["backend"].get("enum"), ["browser", "search_api"])
        self.assertEqual(search_request["properties"]["engine"].get("enum"), ["google", "web", "reddit", "x"])
        self.assertEqual(search_open["properties"]["engine"].get("enum"), ["google", "web", "reddit", "x"])

        self.assertEqual(message_send.get("required", []), ["content"])
        self.assertNotIn("to_role", message_send.get("properties", {}))
        self.assertNotIn("target_actor_address", message_send.get("properties", {}))
        target_identity_id = message_send["properties"]["target_identity_id"]
        self.assertEqual(target_identity_id.get("type"), "string")
        message_contacts = catalog.get_action_definition("message", "contacts").input_schema
        self.assertEqual(message_contacts.get("required"), [])
        self.assertEqual(set(message_contacts.get("properties", {})), {"role"})

        self.assertEqual(message_get_action.kind, "read")
        self.assertEqual(message_get_action.mutates, "none")
        self.assertEqual(message_get_action.required_permission, "message.get")
        self.assertEqual(message_get_action.durability, "none")
        self.assertEqual(message_get.get("required"), ["message_id"])
        self.assertEqual(set(message_get.get("properties", {})), {"message_id"})
        self.assertEqual(message_get["properties"]["message_id"].get("type"), "string")

        self.assertEqual(message_list_action.kind, "read")
        self.assertEqual(message_list_action.mutates, "none")
        self.assertEqual(message_list_action.required_permission, "message.list")
        self.assertEqual(message_list_action.durability, "none")
        self.assertEqual(message_list.get("required"), [])
        message_list_properties = message_list.get("properties", {})
        self.assertEqual(set(message_list_properties), {"cursor", "limit"})
        self.assertEqual(message_list_properties["cursor"].get("type"), "string")
        self.assertEqual(message_list_properties["limit"].get("type"), "integer")
        self.assertNotIn("role", message_list_properties)
        self.assertNotIn("q", message_list_properties)

        self.assertEqual(message_mark_action.kind, "write")
        self.assertEqual(message_mark_action.mutates, "runtime_objects")
        self.assertEqual(message_mark_action.required_permission, "message.mark")
        self.assertEqual(message_mark_action.durability, "durable")
        self.assertEqual(set(message_mark.get("required", [])), {"message_id", "disposition"})
        self.assertEqual(set(message_mark.get("properties", {})), {"message_id", "disposition", "reason"})
        self.assertEqual(message_mark["properties"]["message_id"].get("type"), "string")
        self.assertEqual(message_mark["properties"]["disposition"].get("enum"), ["absorbed"])
        self.assertEqual(message_mark["properties"]["reason"].get("type"), "string")
        send_contract_text = " ".join(
            str(row)
            for row in (
                message_send_action.description,
                message_send["properties"]["target_identity_id"].get("description"),
                message_send["properties"]["reply_to"].get("description"),
                message_send_action.result_content_level,
                message_send_action.success_effect,
                message_send_action.failure_state_guarantee,
                message_send_action.writes,
                message_send_action.returns,
                message_send_action.preconditions,
                message_send_action.use_when,
                message_send_action.do_not_use_when,
            )
        ).lower()
        for snippet in (
            "central im message",
            "target identity",
            "im target resolver",
            "reply wrapper",
            "same im target resolver",
            "original sender into target_identity_id",
            "unified send path",
            "actor runtime reachability",
            "identity profiles",
            "reply_to",
            "processable inbound",
            "external",
            "active actor",
            "replied",
            "disposition save failure",
            "previous disposition",
            "message.mark(absorbed)",
            "task_sys.need_parent",
            "actor_handling_status",
            "target actor local inbound event",
            "target_identity",
        ):
            self.assertIn(snippet, send_contract_text)
        self.assertNotIn("actor-directed", send_contract_text)
        self.assertNotIn("reach policy", send_contract_text)
        self.assertNotIn("use message.contacts", send_contract_text)
        self.assertNotIn("central im derives the other " + "direct identity", send_contract_text)
        self.assertNotIn("reply inside the existing " + "direct conversation", send_contract_text)
        self.assertNotIn("target_identity_id is only required for a new " + "target-identity message", send_contract_text)
        self.assertNotIn("tasks", message_send_action.does_not_write)
        mark_contract_text = " ".join(
            str(row)
            for row in (
                message_mark_action.description,
                message_mark["properties"]["disposition"].get("description"),
                message_mark["properties"]["reason"].get("description"),
                message_mark_action.success_effect,
                message_mark_action.failure_state_guarantee,
                message_mark_action.do_not_use_when,
            )
        ).lower()
        for snippet in (
            "absorbed",
            "task_sys.need_parent",
            "message.send(reply_to=...)",
            "generic disposition editor",
        ):
            self.assertIn(snippet, mark_contract_text)
        self.assertNotIn("parent prompt first", mark_contract_text)
        self.assertIn("identity", str(message_contacts_action.description).lower())
        self.assertIn("self", str(message_contacts_action.description).lower())
        message_contacts_contract = json.dumps(asdict(message_contacts_action), ensure_ascii=True, sort_keys=True).lower()
        self.assertIn("actor runtime presence", message_contacts_contract)
        self.assertIn("optional actor discovery", message_contacts_contract)
        self.assertIn("read-only view", message_contacts_contract)
        self.assertIn("does not decide message.send permission", message_contacts_contract)

        self.assertEqual(message_conversation_action.kind, "read")
        self.assertEqual(message_conversation_action.mutates, "none")
        self.assertEqual(message_conversation_action.required_permission, "message.conversation")
        self.assertEqual(message_conversation_action.durability, "none")
        self.assertEqual(message_conversation.get("required"), ["target_identity_id"])
        conversation_properties = message_conversation.get("properties", {})
        self.assertEqual(set(conversation_properties), {"target_identity_id", "q", "limit"})
        self.assertNotIn("box", conversation_properties)
        self.assertNotIn("role", conversation_properties)
        self.assertNotIn("to_role", conversation_properties)
        self.assertNotIn("from_role", conversation_properties)
        conversation_target = conversation_properties["target_identity_id"]
        self.assertEqual(conversation_target.get("type"), "string")

        self.assertEqual(set(track_resolve_comment.get("required", [])), {"track_id", "comment_id", "resolution_summary"})

    def test_artifact_list_schema_is_simple_and_bounded(self) -> None:
        artifact_list = catalog.get_action_definition("artifact", "list").input_schema
        self.assertEqual(artifact_list.get("required"), [])
        self.assertIs(artifact_list.get("additionalProperties"), False)
        properties = artifact_list.get("properties")
        self.assertIsInstance(properties, dict)
        assert isinstance(properties, dict)
        self.assertEqual(
            set(properties),
            {"track_id", "created_by_identity_id", "template", "q", "limit"},
        )
        self.assertNotIn("created_by_role", properties)
        self.assertEqual(properties["created_by_identity_id"].get("type"), "string")
        self.assertEqual(
            properties["template"].get("enum"),
            ["brief", "proposal", "design", "decision", "proof", "note"],
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
            task_requirement=TASK_REQUIREMENT_FREE,
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
