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
from env.domain import task_sys  # noqa: E402
from env.tool_runtime import registry as catalog  # noqa: E402
from env.tool_runtime import role_auth  # noqa: E402
from env.tool_runtime.registry import dispatch_env_tool_request  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"


class EnvToolPayloadContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, role: str = "dev") -> Path:
        actor_id = self._runtime_actor_id(role=role, label="act-payload-contract")
        path = self._runtime_path("instance-payload-contract.json")
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
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
        self._seed_active_task(instance_json=path, role=role, actor_id=actor_id)
        return path

    def _seed_active_task(self, *, instance_json: Path, role: str, actor_id: str) -> None:
        task_id = f"task-0001-{role}-payload-contract"
        task_sys.ingest(
            {
                "source": {"type": "test.payload_contract", "ref": {"id": task_id}},
                "actor_target": {"actor_id": actor_id, "role_id": role},
                "context": {"fixture": "payload contract"},
            }
        )

    def _dispatch(self, *, tool: str, action: str, args: dict[str, object], role: str = "dev") -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label="act-payload-contract")
        instance_json = self._instance_json(role=role)
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        return dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_role=role,
            actor_id=actor_id,
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
        manifest = env_manifest.load_manifest(MANIFEST)
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                with self.subTest(tool=tool, action=action):
                    action_def = catalog.get_action_definition(tool, action)
                    allowed_roles = role_auth.allowed_roles_for_permission(action_def.required_permission, manifest)
                    self.assertTrue(allowed_roles, msg=f"{tool}.{action}")
                    active_role = sorted(allowed_roles)[0]
                    response = self._dispatch(
                        tool=tool,
                        action=action,
                        args={"__unexpected_payload_field__": True},
                        role=active_role,
                    )
                    self.assertFalse(response.get("ok"), msg=response)
                    self.assertIs(response.get("state_changed"), False, msg=response)
                    self.assertIn("__unexpected_payload_field__", json.dumps(response, ensure_ascii=True))

    def test_services_do_not_define_duplicate_payload_field_sets_and_legacy_message_domain_is_retired(self) -> None:
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
        if message_domain.exists():
            violations.append(f"{message_domain.relative_to(ROOT)}: legacy actor-address message domain must stay retired")

        self.assertEqual(violations, [], msg="\n".join(violations))


if __name__ == "__main__":
    unittest.main()
