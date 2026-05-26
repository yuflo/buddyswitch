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

_EXPECTED_TOOLS = {"task", "track", "artifact", "context", "evidence", "search", "message", "comment", "request"}
_EXPECTED_ACTIONS_BY_TOOL = {
    "task": {"current", "propose", "confirm"},
    "track": {"create", "list", "open", "update_now", "add_material", "add_update", "add_proof", "archive"},
    "artifact": {"list", "get", "create_revision", "update_metadata", "attach_file", "list_attachments", "get_attachment"},
    "context": {"get", "summarize", "list_sources"},
    "evidence": {"issue_browser", "approve_downgrade"},
    "search": {"status", "request", "open_browser"},
    "message": {"send", "list"},
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
            ("artifact", "attach_file", ("draft", "buddybox", "attachment")),
            ("artifact", "list_attachments", ("attachment", "summary", "get_attachment")),
            ("artifact", "get_attachment", ("attachment_id", "content_base64", "artifact_id")),
            ("task", "current", ("current", "snapshot", "history")),
            ("task", "propose", ("start", "switch", "finish")),
            ("task", "confirm", ("pending", "switch", "confirmation")),
            ("comment", "add", ("discussion", "timeline", "message")),
            ("search", "request", ("target_url", "without opening", "open_browser")),
            ("search", "open_browser", ("browser", "open", "payload")),
            ("evidence", "issue_browser", ("artifact", "token", "downgrade")),
            ("evidence", "approve_downgrade", ("downgrade", "reason", "browser")),
            ("context", "get", ("full", "catalog", "summarize")),
            ("context", "summarize", ("compact", "summary", "get")),
            ("context", "list_sources", ("source", "descriptor", "catalog")),
            ("message", "send", ("inbox", "buddy", "comment")),
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

        forbidden_action_ids = {"artifact_index", "artifact_search", "relation", "insight", "experiment", "roadmap", "review", "approval"}
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

    def test_task_current_operation_semantics_are_read_only(self) -> None:
        current = catalog.operation_semantics()["task.current"]
        self.assertEqual(current["kind"], "read")
        self.assertEqual(current["mutates"], "none")
        self.assertEqual(current["required_permission"], "task.read")
        self.assertEqual(current["authority"], "task.buddy_scope")
        self.assertEqual(current["visibility"], "active-buddy private")
        self.assertEqual(current["durability"], "none")
        self.assertEqual(current["result_content_level"], "TaskSnapshot")
        self.assertIn("instance-local taskbox history", current["reads"])
        self.assertEqual(current["writes"], [])
        self.assertIn("taskbox history", " ".join(current["does_not_write"]).lower())
        self.assertIs(current["risk_hints"]["read_only"], True)
        self.assertIs(current["risk_hints"]["destructive"], False)
        self.assertIs(current["risk_hints"]["idempotent"], True)

    def test_task_mutation_operation_semantics_are_taskbox_only(self) -> None:
        op = catalog.operation_semantics()
        for action in ("task.propose", "task.confirm"):
            row = op[action]
            with self.subTest(action=action):
                self.assertEqual(row["kind"], "write")
                self.assertEqual(row["mutates"], "runtime_files")
                self.assertIn(row["required_permission"], {"task.propose", "task.confirm"})
                self.assertIn("instance-local active-buddy taskbox task", row["writes"])
                self.assertIn("instance-local taskbox history", row["writes"])
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

        task_propose = desc["task"]["action_semantics"]["propose"]
        task_side_effects = task_propose["side_effects"]
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
            active_buddy="market",
            instance_id="inst-semantic-check",
            instance_json=ROOT / "tmp" / "does-not-matter.json",
            instance_payload={},
            manifest={"buddies": [{"id": "market"}]},
            manifest_path=ROOT / "buddyswitch" / "manifest.toml",
        )
        self.assertFalse(hyphenated.get("ok"), msg=hyphenated)
        self.assertEqual((hyphenated.get("error") or {}).get("code"), "E_ENV_TOOL")
        self.assertIn("open-browser", str((hyphenated.get("error") or {}).get("message", "")))

        canonical = catalog.dispatch_env_tool_request(
            payload={"tool": "search", "action": "open_browser", "args": {"query": "x"}},
            active_buddy="market",
            instance_id="inst-semantic-check",
            instance_json=ROOT / "tmp" / "does-not-matter.json",
            instance_payload={"browser_port": None},
            manifest={"buddies": [{"id": "market"}]},
            manifest_path=ROOT / "buddyswitch" / "manifest.toml",
        )
        self.assertNotEqual((canonical.get("error") or {}).get("code"), "E_ENV_TOOL", msg=canonical)


if __name__ == "__main__":
    unittest.main()
