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

_EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment", "request"}
_EXPECTED_ACTIONS_BY_TOOL = {
    "task": {"create", "list", "get", "update", "archive"},
    "track": {"create", "list", "open", "update_now", "add_material", "add_update", "add_proof", "archive"},
    "artifact": {"get", "create_revision", "update_metadata"},
    "buddybox": {"desc", "list", "read", "write", "delete"},
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
            ("track", "add_material", ("material", "proof", "timeline")),
            ("track", "add_update", ("timeline", "material", "proof")),
            ("track", "add_proof", ("proof", "material", "timeline")),
            ("artifact", "get", ("full", "body", "draft")),
            ("artifact", "create_revision", ("draft", "publish", "update")),
            ("artifact", "update_metadata", ("patch", "publish", "revision")),
            ("task", "list", ("list", "summary", "get")),
            ("task", "get", ("task id", "list", "update")),
            ("task", "update", ("patch", "archive", "task")),
            ("task", "archive", ("archive", "active", "update")),
            ("comment", "add", ("discussion", "timeline", "message")),
            ("search", "request", ("target_url", "without opening", "open_browser")),
            ("search", "open_browser", ("browser", "open", "payload")),
            ("evidence", "issue_browser", ("artifact", "token", "downgrade")),
            ("evidence", "approve_downgrade", ("downgrade", "reason", "browser")),
            ("context", "get", ("full", "catalog", "summarize")),
            ("context", "summarize", ("compact", "summary", "get")),
            ("context", "list_sources", ("source", "descriptor", "catalog")),
            ("buddybox", "list", ("summary", "logical", "read")),
            ("buddybox", "read", ("exact", "logical_name", "list")),
            ("buddybox", "write", ("replace", "private", "artifact")),
            ("buddybox", "delete", ("delete", "private", "archive")),
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
