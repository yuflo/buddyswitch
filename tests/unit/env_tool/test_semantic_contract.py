"""Semantic contract coverage for env.tool registry projection."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

import env_manifest  # noqa: E402
from env.tool_runtime.definition import ActionDefinition  # noqa: E402
from env.tool_runtime.definition import ToolDefinition  # noqa: E402
from env.tool_runtime.definition import validate_definition  # noqa: E402
from env.tool_runtime import registry as catalog  # noqa: E402
from env.tool_runtime import role_auth  # noqa: E402

_EXPECTED_TOOLS = {"track", "artifact", "context", "evidence", "search", "message", "task_sys"}
_EXPECTED_ACTIONS_BY_TOOL = {
    "track": {
        "create",
        "list",
        "open",
        "add_comment",
        "list_comments",
        "resolve_comment_thread",
        "update_requirements",
        "update_status",
        "add_material",
        "add_update",
        "add_proof",
        "archive",
    },
    "artifact": {"list", "get", "create_revision", "update_metadata", "attach_file", "list_attachments", "get_attachment"},
    "context": {"get", "summarize", "list_sources"},
    "evidence": {"issue_browser", "approve_downgrade"},
    "search": {"status", "request"},
    "message": {"contacts", "send", "get", "mark", "list", "conversation"},
    "task_sys": {"list", "get", "update_task_analysis", "close", "need_parent"},
}
_TASK_REQUIREMENT_FREE = "free"
_TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED = "active_task_required"
_ALLOWED_TASK_REQUIREMENTS = {_TASK_REQUIREMENT_FREE, _TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED}
_EXPECTED_FREE_ACTIONS = {
    "artifact.list",
    "artifact.get",
    "artifact.list_attachments",
    "artifact.get_attachment",
    "context.summarize",
    "context.get",
    "context.list_sources",
    "message.contacts",
    "message.send",
    "message.get",
    "message.mark",
    "message.list",
    "message.conversation",
    "search.status",
    "task_sys.list",
    "task_sys.get",
    "task_sys.update_task_analysis",
    "task_sys.close",
    "task_sys.need_parent",
    "track.list",
    "track.list_comments",
    "track.open",
}
_EXPECTED_ACTIVE_TASK_REQUIRED_ACTIONS = {
    "artifact.create_revision",
    "artifact.update_metadata",
    "artifact.attach_file",
    "evidence.issue_browser",
    "evidence.approve_downgrade",
    "search.request",
    "track.create",
    "track.add_comment",
    "track.resolve_comment_thread",
    "track.update_requirements",
    "track.update_status",
    "track.add_material",
    "track.add_update",
    "track.add_proof",
    "track.archive",
}
_PLACEHOLDER_SNIPPETS = ("is the intended action", "closer semantic match")


class EnvToolSemanticContractTests(unittest.TestCase):
    def _desc(self) -> dict[str, dict[str, object]]:
        return catalog.env_tools_description()

    def _semantic_text(self, *, tool: str, action: str) -> str:
        tool_desc = self._desc()[tool]
        self.assertIn(action, tool_desc["action_semantics"], msg=f"{tool}.{action}")
        semantic = tool_desc["action_semantics"][action]
        self.assertIsInstance(semantic, dict, msg=f"{tool}.{action}")
        assert isinstance(semantic, dict)
        use_when = semantic.get("use_when")
        do_not_use_when = semantic.get("do_not_use_when")
        self.assertIsInstance(use_when, list, msg=f"{tool}.{action}.use_when")
        self.assertIsInstance(do_not_use_when, list, msg=f"{tool}.{action}.do_not_use_when")
        assert isinstance(use_when, list)
        assert isinstance(do_not_use_when, list)
        return "\n".join(str(row) for row in (use_when + do_not_use_when)).lower()

    def test_registry_semantics_cover_every_registered_tool_and_action(self) -> None:
        desc = self._desc()
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

    def test_every_action_has_action_owned_selection_semantics(self) -> None:
        desc = self._desc()
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                with self.subTest(action=f"{tool}.{action}"):
                    semantic = desc[tool]["action_semantics"][action]
                    self.assertIsInstance(semantic, dict)
                    assert isinstance(semantic, dict)
                    use_when = semantic.get("use_when")
                    do_not_use_when = semantic.get("do_not_use_when")
                    self.assertIsInstance(use_when, list)
                    self.assertIsInstance(do_not_use_when, list)
                    assert isinstance(use_when, list)
                    assert isinstance(do_not_use_when, list)
                    self.assertTrue(use_when)
                    self.assertTrue(do_not_use_when)
                    text = "\n".join(use_when + do_not_use_when).lower()
                    for snippet in _PLACEHOLDER_SNIPPETS:
                        self.assertNotIn(snippet, text)

    def test_every_tool_and_action_exposes_source_of_truth_semantic_fields(self) -> None:
        desc = self._desc()
        for tool in sorted(catalog.supported_tools()):
            with self.subTest(tool=tool):
                tool_desc = desc[tool]
                self.assertIsInstance(tool_desc.get("object_model"), str, msg=tool_desc)
                self.assertTrue(str(tool_desc.get("object_model", "")).strip(), msg=tool_desc)
            for action in sorted(catalog.supported_actions(tool)):
                with self.subTest(action=f"{tool}.{action}"):
                    semantic = desc[tool]["action_semantics"][action]
                    self.assertIsInstance(semantic.get("visibility"), str, msg=semantic)
                    self.assertTrue(str(semantic.get("visibility", "")).strip(), msg=semantic)
                    self.assertIn(semantic.get("durability"), {"none", "transient", "durable"}, msg=semantic)
                    self.assertIsInstance(semantic.get("result_content_level"), str, msg=semantic)
                    self.assertTrue(str(semantic.get("result_content_level", "")).strip(), msg=semantic)
                    self.assertIsInstance(semantic.get("success_means"), str, msg=semantic)
                    self.assertNotIn("completed under declared capability boundary", semantic["success_means"])
                    self.assertIsInstance(semantic.get("failure_state_guarantee"), str, msg=semantic)
                    self.assertTrue(str(semantic.get("failure_state_guarantee", "")).strip(), msg=semantic)
                    side_effects = semantic.get("side_effects")
                    self.assertIsInstance(side_effects, dict, msg=semantic)
                    assert isinstance(side_effects, dict)
                    for key in ("reads", "writes", "does_not_write"):
                        self.assertIsInstance(side_effects.get(key), list, msg=semantic)
                    self.assertTrue(
                        side_effects.get("reads") or side_effects.get("writes") or side_effects.get("does_not_write"),
                        msg=semantic,
                    )

    def test_all_expected_actions_have_semantic_boundary_text(self) -> None:
        desc = self._desc()
        for tool, actions in _EXPECTED_ACTIONS_BY_TOOL.items():
            self.assertEqual(set(desc[tool]["action_semantics"]), actions)
            for action in actions:
                with self.subTest(action=f"{tool}.{action}"):
                    text = self._semantic_text(tool=tool, action=action)
                    self.assertTrue(text.strip())

    def test_adjacent_action_boundaries_are_explained(self) -> None:
        checks = [
            ("artifact", "list", ("summary", "filter", "get")),
            ("track", "add_material", ("material", "proof", "timeline")),
            ("track", "add_update", ("timeline", "material", "proof")),
            ("track", "add_proof", ("proof", "material", "timeline")),
            ("artifact", "get", ("full", "body", "draft")),
            ("artifact", "create_revision", ("draft", "relate", "update")),
            ("artifact", "update_metadata", ("patch", "relate", "revision")),
            ("artifact", "attach_file", ("draft", "actor_private", "attachment")),
            ("artifact", "list_attachments", ("attachment", "summary", "get_attachment")),
            ("artifact", "get_attachment", ("attachment_id", "content_base64", "artifact_id")),
            ("track", "add_comment", ("discussion", "track", "message")),
            ("search", "request", ("target_url", "without opening", "search_page")),
            ("evidence", "issue_browser", ("artifact", "token", "downgrade")),
            ("evidence", "approve_downgrade", ("downgrade", "reason", "browser")),
            ("context", "get", ("full", "catalog", "summarize")),
            ("context", "summarize", ("compact", "summary", "get")),
            ("context", "list_sources", ("source", "descriptor", "catalog")),
            ("message", "contacts", ("contact", "actor", "send")),
            ("message", "send", ("central im", "actor identity", "track")),
            ("message", "get", ("exact", "message_id", "disposition")),
            ("message", "mark", ("absorbed", "task_sys.need_parent", "disposition")),
            ("message", "list", ("event", "cursor", "track")),
            ("task_sys", "list", ("summaries", "relations", "execution")),
            ("task_sys", "get", ("task_id", "detail", "events")),
            ("task_sys", "update_task_analysis", ("task_desc", "task_relation", "relation")),
            ("task_sys", "close", ("side", "completed", "parent")),
            ("task_sys", "need_parent", ("parent", "handoff", "interrupt")),
            ("track", "resolve_comment_thread", ("owner", "thread", "resolved")),
        ]
        for tool, action, snippets in checks:
            text = self._semantic_text(tool=tool, action=action)
            with self.subTest(action=f"{tool}.{action}"):
                for snippet in snippets:
                    self.assertIn(snippet, text, msg=f"{tool}.{action} missing snippet '{snippet}'")

    def test_forbidden_tool_and_action_surfaces_are_absent(self) -> None:
        forbidden_tool_ids = {
            "artifact_index",
            "artifact_search",
            "relation",
            "insight",
            "experiment",
            "roadmap",
            "review",
            "approval",
        }
        supported_tools = set(catalog.supported_tools())
        self.assertTrue(forbidden_tool_ids.isdisjoint(supported_tools))

        forbidden_action_ids = {"artifact_index", "artifact_search", "relation", "insight", "experiment", "roadmap", "approval"}
        for tool in sorted(supported_tools):
            actions = set(catalog.supported_actions(tool))
            with self.subTest(tool=tool):
                self.assertTrue(forbidden_action_ids.isdisjoint(actions))

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

    def test_operation_semantics_include_generated_effect_fields(self) -> None:
        op = catalog.operation_semantics()
        for key, row in op.items():
            with self.subTest(action=key):
                self.assertIn("reads", row)
                self.assertIn("writes", row)
                self.assertIn("does_not_write", row)
                self.assertIn("visibility", row)
                self.assertIn("durability", row)
                self.assertIn("result_content_level", row)
                self.assertIn("success_effect", row)
                self.assertIn("failure_state_guarantee", row)
                self.assertIsInstance(row["reads"], list)
                self.assertIsInstance(row["writes"], list)
                self.assertIsInstance(row["does_not_write"], list)
                self.assertIn(row["durability"], {"none", "transient", "durable"})

    def test_task_requirement_contract_is_declared_for_every_action(self) -> None:
        expected_keys = {
            f"{tool}.{action}"
            for tool, actions in _EXPECTED_ACTIONS_BY_TOOL.items()
            for action in actions
        }
        expected_classified = _EXPECTED_FREE_ACTIONS | _EXPECTED_ACTIVE_TASK_REQUIRED_ACTIONS
        self.assertEqual(expected_keys, expected_classified)
        self.assertTrue(_EXPECTED_FREE_ACTIONS.isdisjoint(_EXPECTED_ACTIVE_TASK_REQUIRED_ACTIONS))

        actual_free: set[str] = set()
        actual_active_required: set[str] = set()
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                action_key = f"{tool}.{action}"
                action_definition = catalog.get_action_definition(tool, action)
                task_requirement = getattr(action_definition, "task_requirement", None)
                with self.subTest(action=action_key):
                    self.assertIn(task_requirement, _ALLOWED_TASK_REQUIREMENTS)
                if task_requirement == _TASK_REQUIREMENT_FREE:
                    actual_free.add(action_key)
                elif task_requirement == _TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED:
                    actual_active_required.add(action_key)

        self.assertEqual(actual_free, _EXPECTED_FREE_ACTIONS)
        self.assertEqual(actual_active_required, _EXPECTED_ACTIVE_TASK_REQUIRED_ACTIONS)

    def test_task_requirement_is_exposed_in_operation_and_catalog_semantics(self) -> None:
        operation_rows = catalog.operation_semantics()
        description = catalog.env_tools_description()
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                action_key = f"{tool}.{action}"
                expected = getattr(catalog.get_action_definition(tool, action), "task_requirement", None)
                with self.subTest(action=action_key):
                    self.assertIn(expected, _ALLOWED_TASK_REQUIREMENTS)
                    self.assertEqual(operation_rows[action_key].get("task_requirement"), expected)
                    action_semantics = description[tool]["action_semantics"][action]
                    self.assertIsInstance(action_semantics, dict)
                    assert isinstance(action_semantics, dict)
                    self.assertEqual(action_semantics.get("task_requirement"), expected)

    def test_invalid_task_requirement_fails_definition_validation(self) -> None:
        valid_action = catalog.get_action_definition("search", "status")
        if not hasattr(valid_action, "task_requirement"):
            self.fail("ActionDefinition.task_requirement is required")
        invalid_action = ActionDefinition(
            name="invalid_task_requirement",
            title="invalid task requirement",
            description="Action with invalid task requirement.",
            input_schema={"type": "object", "additionalProperties": False, "required": [], "properties": {}},
            output_schema={"$ref": "ToolResult"},
            kind=valid_action.kind,
            mutates=valid_action.mutates,
            required_permission=valid_action.required_permission,
            authority=valid_action.authority,
            visibility=valid_action.visibility,
            durability=valid_action.durability,
            result_content_level=valid_action.result_content_level,
            success_effect=valid_action.success_effect,
            failure_state_guarantee=valid_action.failure_state_guarantee,
            reads=valid_action.reads,
            writes=valid_action.writes,
            does_not_write=valid_action.does_not_write,
            task_requirement="invalid",
            preconditions=valid_action.preconditions,
            returns=valid_action.returns,
            use_when=valid_action.use_when,
            do_not_use_when=valid_action.do_not_use_when,
            risk_hints=valid_action.risk_hints,
        )
        invalid_definition = ToolDefinition(
            id="invalidtaskrequirement",
            title="Invalid Task Requirement",
            description="Definition used only for task requirement validation.",
            scope="test scope",
            capability_boundary="test boundary",
            object_model="test object model",
            use_when=("testing validation",),
            do_not_use_when=("runtime use",),
            actions=(invalid_action,),
        )
        with self.assertRaisesRegex(ValueError, "task_requirement"):
            validate_definition(invalid_definition)

    def test_operation_semantics_permissions_are_covered_by_role_policy(self) -> None:
        manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
        manifest_roles = role_auth.manifest_role_ids(manifest)
        for key, row in catalog.operation_semantics().items():
            required_permission = row["required_permission"]
            allowed_roles = role_auth.allowed_roles_for_permission(required_permission, manifest)
            with self.subTest(action=key, required_permission=required_permission):
                self.assertTrue(allowed_roles)
                self.assertLessEqual(allowed_roles, manifest_roles)

    def test_operation_semantics_remain_role_neutral(self) -> None:
        forbidden_role_fields = {
            "active_role",
            "active_role",
            "allowed_roles",
            "allowed_" + "actions",
            "denied_" + "actions",
            "denied_" + "action_" + "details",
            "role_" + "authority_" + "source",
            "runtime_policy_preview",
            "available_actions",
            "restricted_actions",
            "restricted_action_details",
            "not_authorization_boundary",
            "not_execution_result",
        }
        for key, row in catalog.operation_semantics().items():
            with self.subTest(action=key):
                self.assertTrue(forbidden_role_fields.isdisjoint(row))

    def test_tool_catalog_and_operation_semantics_do_not_claim_permission_ownership(self) -> None:
        catalog_text = json.dumps(catalog.env_tools_description(), ensure_ascii=True).lower()
        operation_text = json.dumps(catalog.operation_semantics(), ensure_ascii=True).lower()
        combined = f"{catalog_text}\n{operation_text}"
        forbidden = (
            "active role owns",
            "owns message.list permission",
            "owns task_sys.close permission",
            "owns artifact.create permission",
            "owns track.read permission",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, combined)
        self.assertIn("env.tool role-action policy allows this action for the active role", combined)

    def test_message_catalog_uses_identity_language(self) -> None:
        desc = self._desc()
        message_desc = desc["message"]
        operation_rows = catalog.operation_semantics()
        message_rows = {
            key: value
            for key, value in operation_rows.items()
            if key.startswith("message.")
        }

        self.assertEqual(message_desc["title"], "Central IM Messages")
        self.assertEqual(message_rows["message.send"]["authority"], "message.central_im_channel")
        self.assertEqual(message_rows["message.get"]["authority"], "message.current_identity_exact_message")
        self.assertEqual(message_rows["message.mark"]["authority"], "message.current_identity_message_disposition")
        self.assertEqual(message_rows["message.list"]["authority"], "message.central_im_identity_events")
        self.assertIn("active actor Central IM identity event feed", message_rows["message.list"]["visibility"])

        send_requires = "\n".join(message_rows["message.send"]["requires"]).lower()
        get_requires = "\n".join(message_rows["message.get"]["requires"]).lower()
        mark_requires = "\n".join(message_rows["message.mark"]["requires"]).lower()
        conversation_requires = "\n".join(message_rows["message.conversation"]["requires"]).lower()
        self.assertIn("active actor", send_requires)
        self.assertIn("active actor", get_requires)
        self.assertIn("active actor", mark_requires)
        self.assertNotIn("active role", send_requires)
        self.assertNotIn("active role", conversation_requires)

        serialized = json.dumps(
            {"catalog": message_desc, "operations": message_rows},
            ensure_ascii=True,
            sort_keys=True,
        ).lower()
        required = (
            "optional actor discovery",
            "central im target-identity sends",
            "im target resolver",
            "exact processable inbound reads",
            "disposition marking",
            "reply_to",
            "reply wrapper",
            "original sender into target_identity_id",
            "same im target resolver",
            "unified send path",
            "external",
            "external identities are valid central im direct targets",
            "replied",
            "previous disposition",
            "absorbed",
            "needs_parent",
            "message.send(reply_to=...)",
            "generic disposition editor",
            "target_identity_id",
            "actor runtime presence",
            "identity profiles",
            "actor runtime reachability",
        )
        for token in required:
            with self.subTest(required=token):
                self.assertIn(token, serialized)
        forbidden = (
            "role messages",
            "direct_role_channel",
            "active_role_inbox",
            "active-role inbox",
            "not the active role",
            "outside the active role",
            "same role id",
            "active role cannot",
            "target runtime actor actor id",
            "actor contact projection",
            "already present in a direct conversation",
            "central im derives the other " + "direct identity",
            "reply inside the existing " + "direct conversation",
            "target_identity_id is only required for a new " + "target-identity message",
            "before message.send",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, serialized)

    def test_adjacent_catalog_surfaces_do_not_teach_direct_role_inbox_or_role_taskbox(self) -> None:
        desc = self._desc()
        track_text = json.dumps(desc["track"], ensure_ascii=True, sort_keys=True).lower()
        task_text = json.dumps(desc["task_sys"], ensure_ascii=True, sort_keys=True).lower()

        for token in ("direct role inbox", "direct role messaging"):
            with self.subTest(surface="track", token=token):
                self.assertNotIn(token, track_text)
        for token in ("active-role taskbox", "active-role tasksnapshot", "current active-role taskbox task"):
            with self.subTest(surface="task", token=token):
                self.assertNotIn(token, task_text)

        self.assertIn("track-scoped", track_text)
        self.assertIn("env.tool role-action policy allows this action for the active role", task_text)

    def test_task_sys_operation_semantics_are_task_sys_only(self) -> None:
        op = catalog.operation_semantics()
        self.assertNotIn("task.current", op)
        self.assertNotIn("task_sys.checkpoint_update", op)
        for action in ("task_sys.list", "task_sys.get"):
            with self.subTest(action=action):
                self.assertIn(action, op)
                row = op[action]
                self.assertEqual(row["kind"], "read")
                self.assertEqual(row["mutates"], "none")
                self.assertTrue(str(row["required_permission"]).startswith("task_sys."))
                self.assertIn("task sys task record", row["reads"])
                self.assertEqual(row["writes"], [])
        for action in ("task_sys.update_task_analysis", "task_sys.close", "task_sys.need_parent"):
            self.assertIn(action, op)
            row = op[action]
            with self.subTest(action=action):
                self.assertEqual(row["kind"], "write")
                self.assertEqual(row["mutates"], "runtime_objects")
                self.assertTrue(str(row["required_permission"]).startswith("task_sys."))
                self.assertIn("task sys task record", row["reads"])
                self.assertIn("task sys task record", row["writes"])
                self.assertIn("tracks", " ".join(row["does_not_write"]).lower())
                self.assertIn("artifacts", " ".join(row["does_not_write"]).lower())

    def test_task_sys_operation_semantics_name_state_and_cleanup_feedback(self) -> None:
        op = catalog.operation_semantics()
        self.assertIn("task_sys.list", op)
        self.assertIn("task_sys.get", op)
        close_returns = set(op["task_sys.close"]["returns"])
        need_parent_returns = set(op["task_sys.need_parent"]["returns"])
        update_returns = set(op["task_sys.update_task_analysis"]["returns"])
        list_returns = set(op["task_sys.list"]["returns"])
        get_returns = set(op["task_sys.get"]["returns"])

        for field in ("tasks", "active_count", "recoverable_count"):
            with self.subTest(action="task_sys.list", field=field):
                self.assertIn(field, list_returns)
        for field in ("task_id", "task", "events"):
            with self.subTest(action="task_sys.get", field=field):
                self.assertIn(field, get_returns)
        for field in ("task_id", "task_status", "state_changed", "processor", "side_thread_id", "side_cleanup"):
            with self.subTest(action="task_sys.close", field=field):
                self.assertIn(field, close_returns)
        self.assertIn("execution_result", close_returns)
        self.assertNotIn("close_result", close_returns)
        for field in ("task_id", "task_status", "task_desc", "task_relation", "execution", "state_changed"):
            with self.subTest(action="task_sys.update_task_analysis", field=field):
                self.assertIn(field, update_returns)
        for field in (
            "task_id",
            "task_status",
            "state_changed",
            "processor",
            "side_thread_id",
            "side_cleanup",
            "execution_handoff",
            "parent_runtime",
        ):
            with self.subTest(action="task_sys.need_parent", field=field):
                self.assertIn(field, need_parent_returns)
        self.assertNotIn("parent_handoff_params", need_parent_returns)

    def test_high_risk_object_boundaries_are_explicit(self) -> None:
        desc = self._desc()
        track_model = str(desc["track"].get("object_model", "")).lower()
        task_model = str(desc["task_sys"].get("object_model", "")).lower()
        artifact_model = str(desc["artifact"].get("object_model", "")).lower()

        self.assertIn("owner_identity_id", track_model)
        self.assertIn("collaboration facts", track_model)
        self.assertIn("comments are the only actor-attention", track_model)
        self.assertIn("task sys tasks", task_model)
        self.assertIn("source refs", task_model)
        self.assertIn("draft", artifact_model)
        self.assertIn("track.add_material", artifact_model)

        task_close = desc["task_sys"]["action_semantics"]["close"]
        task_side_effects = task_close["side_effects"]
        self.assertIn("tracks", " ".join(task_side_effects["does_not_write"]).lower())
        self.assertIn("artifacts", " ".join(task_side_effects["does_not_write"]).lower())

        artifact_create = desc["artifact"]["action_semantics"]["create_revision"]
        self.assertIn("draft", artifact_create["success_means"].lower())
        self.assertIn("track artifact_relations", " ".join(artifact_create["side_effects"]["does_not_write"]))

        search_request = desc["search"]["action_semantics"]["request"]
        self.assertIn("does not fetch", search_request["success_means"].lower())
        self.assertEqual(search_request["durability"], "none")

    def test_broker_payload_action_ids_are_strict(self) -> None:
        hyphenated = catalog.dispatch_env_tool_request(
            payload={"tool": "search", "action": "open-browser", "args": {"query": "x"}},
            active_role="market",
            actor_id="act-market-5e0000000001",
            instance_json=ROOT / "tmp" / "does-not-matter.json",
            instance_payload={},
            manifest={"roles": [{"id": "market"}]},
            manifest_path=ROOT / "buddyswitch" / "manifest.toml",
        )
        self.assertFalse(hyphenated.get("ok"), msg=hyphenated)
        self.assertEqual((hyphenated.get("error") or {}).get("code"), "E_ENV_TOOL")
        self.assertIn("open-browser", str((hyphenated.get("error") or {}).get("message", "")))

        canonical = catalog.dispatch_env_tool_request(
            payload={"tool": "search", "action": "open_browser", "args": {"query": "x"}},
            active_role="market",
            actor_id="act-market-5e0000000001",
            instance_json=ROOT / "tmp" / "does-not-matter.json",
            instance_payload={"browser_port": None},
            manifest={"roles": [{"id": "market"}]},
            manifest_path=ROOT / "buddyswitch" / "manifest.toml",
        )
        self.assertFalse(canonical.get("ok"), msg=canonical)
        self.assertEqual((canonical.get("error") or {}).get("code"), "E_ENV_TOOL", msg=canonical)
        self.assertIn("open_browser", str((canonical.get("error") or {}).get("message", "")))
