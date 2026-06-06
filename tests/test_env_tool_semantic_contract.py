#!/usr/bin/env python3
"""Semantic contract coverage for env.tool registry projection."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
from env.tool_runtime import registry as catalog  # noqa: E402
from env.tool_runtime import role_auth  # noqa: E402

_EXPECTED_TOOLS = {"task", "track", "artifact", "context", "evidence", "search", "message", "comment", "request"}
_EXPECTED_ACTIONS_BY_TOOL = {
    "task": {"current", "capture", "select", "switch_request", "switch_confirm", "progress", "checkout", "review"},
    "track": {"create", "list", "open", "update_now", "add_material", "add_update", "add_proof", "archive"},
    "artifact": {"list", "get", "create_revision", "update_metadata", "attach_file", "list_attachments", "get_attachment"},
    "context": {"get", "summarize", "list_sources"},
    "evidence": {"issue_browser", "approve_downgrade"},
    "search": {"status", "request", "open_browser"},
    "message": {"contacts", "send", "get", "mark", "list", "conversation"},
    "comment": {"add", "list", "resolve"},
    "request": {"create", "list", "get", "accept", "block", "complete", "cancel"},
}
_PLACEHOLDER_SNIPPETS = ("is the intended action", "closer semantic match")


class EnvToolSemanticContractTests(unittest.TestCase):
    def _desc(self) -> dict[str, dict[str, object]]:
        return catalog.env_tools_description()

    def _semantic_text(self, *, tool: str, action: str) -> str:
        semantic = self._desc()[tool]["action_semantics"][action]
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
            ("artifact", "create_revision", ("draft", "publish", "update")),
            ("artifact", "update_metadata", ("patch", "publish", "revision")),
            ("artifact", "attach_file", ("draft", "actor_private", "attachment")),
            ("artifact", "list_attachments", ("attachment", "summary", "get_attachment")),
            ("artifact", "get_attachment", ("attachment_id", "content_base64", "artifact_id")),
            ("task", "current", ("current", "taskviewmodel", "history")),
            ("task", "capture", ("capture", "shelf", "captured")),
            ("task", "select", ("select", "captured", "blocked", "active")),
            ("task", "switch_request", ("pending", "switch", "current")),
            ("task", "switch_confirm", ("accept", "reject", "confirmation")),
            ("task", "progress", ("progress", "evidence", "refs")),
            ("task", "checkout", ("continue", "finish", "block")),
            ("task", "review", ("captured", "blocked", "review")),
            ("comment", "add", ("discussion", "timeline", "message")),
            ("search", "request", ("target_url", "without opening", "open_browser")),
            ("search", "open_browser", ("browser", "open", "payload")),
            ("evidence", "issue_browser", ("artifact", "token", "downgrade")),
            ("evidence", "approve_downgrade", ("downgrade", "reason", "browser")),
            ("context", "get", ("full", "catalog", "summarize")),
            ("context", "summarize", ("compact", "summary", "get")),
            ("context", "list_sources", ("source", "descriptor", "catalog")),
            ("message", "contacts", ("contact", "actor", "send")),
            ("message", "send", ("inbox", "actor address", "comment")),
            ("message", "get", ("exact", "message_id", "disposition")),
            ("message", "mark", ("absorbed", "needs_parent", "disposition")),
            ("message", "list", ("inbox", "read", "comment")),
            ("comment", "resolve", ("pm", "thread", "resolved")),
            ("request", "create", ("track", "request", "recipient")),
            ("request", "list", ("inbox", "outbox", "status")),
            ("request", "get", ("request", "visibility", "track")),
            ("request", "accept", ("recipient", "accepted", "request")),
            ("request", "block", ("recipient", "blocker", "request")),
            ("request", "complete", ("recipient", "result", "done")),
            ("request", "cancel", ("requester", "canceled", "request")),
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
            "owns task.read permission",
            "owns task.capture permission",
            "owns task.switch_confirm permission",
            "owns artifact.create permission",
            "owns track.read permission",
        )
        for text in forbidden:
            with self.subTest(text=text):
                self.assertNotIn(text, combined)
        self.assertIn("env.tool role-action policy allows this action for the active role", combined)

    def test_message_catalog_uses_actor_address_identity_language(self) -> None:
        desc = self._desc()
        message_desc = desc["message"]
        operation_rows = catalog.operation_semantics()
        message_rows = {
            key: value
            for key, value in operation_rows.items()
            if key.startswith("message.")
        }

        self.assertEqual(message_desc["title"], "Direct Actor Messages")
        self.assertEqual(message_rows["message.send"]["authority"], "message.direct_actor_address_channel")
        self.assertEqual(message_rows["message.get"]["authority"], "message.active_actor_exact_message")
        self.assertEqual(message_rows["message.mark"]["authority"], "message.active_actor_message_disposition")
        self.assertEqual(message_rows["message.list"]["authority"], "message.active_actor_inbox")
        self.assertIn("active actor inbox", message_rows["message.list"]["visibility"])

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
            "online actor contact discovery",
            "direct actor-address sends",
            "exact processable inbound reads",
            "non-reply disposition marking",
            "reply_to",
            "replied",
            "previous disposition",
            "absorbed",
            "needs_parent",
            "message.send(reply_to=...)",
            "generic disposition editor",
            "full actoraddress",
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
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, serialized)

    def test_adjacent_catalog_surfaces_do_not_teach_direct_role_inbox_or_role_taskbox(self) -> None:
        desc = self._desc()
        comment_text = json.dumps(desc["comment"], ensure_ascii=True, sort_keys=True).lower()
        task_text = json.dumps(desc["task"], ensure_ascii=True, sort_keys=True).lower()

        for token in ("direct role inbox", "direct role messaging"):
            with self.subTest(surface="comment", token=token):
                self.assertNotIn(token, comment_text)
        for token in ("active-role taskbox", "active-role tasksnapshot", "current active-role taskbox task"):
            with self.subTest(surface="task", token=token):
                self.assertNotIn(token, task_text)

        self.assertIn("active-role readability", comment_text)
        self.assertIn("env.tool role-action policy allows this action for the active role", task_text)

    def test_task_current_operation_semantics_are_read_only(self) -> None:
        current = catalog.operation_semantics()["task.current"]
        self.assertEqual(current["kind"], "read")
        self.assertEqual(current["mutates"], "none")
        self.assertEqual(current["required_permission"], "task.read")
        self.assertEqual(current["authority"], "task.role_scope")
        self.assertEqual(current["visibility"], "active actor private")
        self.assertEqual(current["durability"], "none")
        self.assertEqual(current["result_content_level"], "TaskViewModel")
        self.assertIn("instance-local taskbox history", current["reads"])
        self.assertEqual(current["writes"], [])
        self.assertIn("taskbox history", " ".join(current["does_not_write"]).lower())
        self.assertIs(current["risk_hints"]["read_only"], True)
        self.assertIs(current["risk_hints"]["destructive"], False)
        self.assertIs(current["risk_hints"]["idempotent"], True)

    def test_task_mutation_operation_semantics_are_taskbox_only(self) -> None:
        op = catalog.operation_semantics()
        for action in (
            "task.capture",
            "task.select",
            "task.switch_request",
            "task.switch_confirm",
            "task.progress",
            "task.checkout",
            "task.review",
        ):
            row = op[action]
            with self.subTest(action=action):
                if action == "task.review":
                    self.assertIn(row["kind"], {"read", "write"})
                else:
                    self.assertEqual(row["kind"], "write")
                self.assertEqual(row["mutates"], "runtime_files" if action != "task.review" else "none")
                self.assertTrue(str(row["required_permission"]).startswith("task."))
                if action not in {"task.review", "task.switch_request"}:
                    self.assertIn("instance-local active actor taskbox task docs", row["writes"])
                    self.assertIn("instance-local taskbox history", row["writes"])
                elif action == "task.switch_request":
                    self.assertEqual(row["writes"], ["instance-local taskbox history"])
                self.assertIn("track state", " ".join(row["does_not_write"]).lower())
                self.assertIn("artifact visibility", " ".join(row["does_not_write"]).lower())

    def test_high_risk_object_boundaries_are_explicit(self) -> None:
        desc = self._desc()
        track_model = str(desc["track"].get("object_model", "")).lower()
        task_model = str(desc["task"].get("object_model", "")).lower()
        artifact_model = str(desc["artifact"].get("object_model", "")).lower()

        self.assertIn("shared product outcome thread", track_model)
        self.assertIn("feature iteration", track_model)
        self.assertIn("not every feature", track_model)
        self.assertIn("private work item", task_model)
        self.assertIn("context link", task_model)
        self.assertIn("draft", artifact_model)
        self.assertIn("track.add_material", artifact_model)

        task_capture = desc["task"]["action_semantics"]["capture"]
        task_side_effects = task_capture["side_effects"]
        self.assertIn("track state", " ".join(task_side_effects["does_not_write"]).lower())
        self.assertIn("artifact visibility", " ".join(task_side_effects["does_not_write"]).lower())

        artifact_create = desc["artifact"]["action_semantics"]["create_revision"]
        self.assertIn("draft", artifact_create["success_means"].lower())
        self.assertIn("track.add_material", " ".join(artifact_create["side_effects"]["does_not_write"]))

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
        self.assertNotEqual((canonical.get("error") or {}).get("code"), "E_ENV_TOOL", msg=canonical)


if __name__ == "__main__":
    unittest.main()
