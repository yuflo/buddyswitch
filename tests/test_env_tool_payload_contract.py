#!/usr/bin/env python3
"""Payload field contract alignment for env.tool actions."""

from __future__ import annotations

import ast
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
from env.tool_runtime.registry import dispatch_env_tool_request  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"


class EnvToolPayloadContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self) -> Path:
        path = self._runtime_path("instance-payload-contract.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": "inst-payload-contract",
                    "buddy": "dev",
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-19T00:00:00Z",
                    "updated_at": "2026-05-19T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(self, *, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        instance_json = self._instance_json()
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        return dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy="dev",
            instance_id="inst-payload-contract",
            instance_json=instance_json,
            instance_payload=instance_payload,
            manifest=env_manifest.load_manifest(MANIFEST),
            manifest_path=MANIFEST,
        )

    def test_payload_field_helper_matches_registry(self) -> None:
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                with self.subTest(tool=tool, action=action):
                    action_def = catalog.get_action_definition(tool, action)
                    expected = sorted((action_def.input_schema.get("properties") or {}).keys())
                    self.assertEqual(
                        set(catalog.payload_fields_for_action(tool, action)),
                        set(expected),
                    )

    def test_runtime_catalog_payload_fields_match_registry_order(self) -> None:
        desc = catalog.env_tools_description()
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                with self.subTest(tool=tool, action=action):
                    action_def = catalog.get_action_definition(tool, action)
                    expected = [name for name in (action_def.input_schema.get("properties") or {}) if isinstance(name, str)]
                    self.assertEqual(
                        desc[tool]["payload_fields"][action],
                        expected,
                    )

    def test_every_action_rejects_unregistered_payload_field_without_state_change(self) -> None:
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                with self.subTest(tool=tool, action=action):
                    response = self._dispatch(
                        tool=tool,
                        action=action,
                        args={"__unexpected_payload_field__": True},
                    )
                    self.assertFalse(response.get("ok"), msg=response)
                    self.assertIs(response.get("state_changed"), False, msg=response)
                    self.assertIn("__unexpected_payload_field__", json.dumps(response, ensure_ascii=True))

    def test_services_and_message_domain_do_not_define_duplicate_payload_field_sets(self) -> None:
        service_root = ROOT / "scripts" / "env" / "tools"
        violations: list[str] = []
        for path in sorted(service_root.glob("*/service.py")):
            if path.name != "service.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.endswith("_FIELDS"):
                        violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: {target.id}")

        message_domain = ROOT / "scripts" / "env" / "domain" / "messages.py"
        message_tree = ast.parse(message_domain.read_text(encoding="utf-8"), filename=str(message_domain))
        for node in ast.walk(message_tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"_SEND_FIELDS", "_LIST_FIELDS"}:
                    violations.append(f"{message_domain.relative_to(ROOT)}:{node.lineno}: {target.id}")

        self.assertEqual(violations, [], msg="\n".join(violations))


if __name__ == "__main__":
    unittest.main()
