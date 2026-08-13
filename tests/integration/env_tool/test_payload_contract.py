"""Payload field contract alignment for env.tool actions."""

from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.application.build import activate_application  # noqa: E402
from tests.support import task_fixtures  # noqa: E402
from buddyswitch.foundation.tool_runtime import registry as catalog  # noqa: E402
from buddyswitch.foundation.tool_runtime.registry import dispatch_env_tool_request  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

class EnvToolPayloadContractTests(RuntimeWorkspaceTestCase):
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
        task_fixtures.create_task(
            actor_target={"actor_id": actor_id, "role_id": role},
            demand_ref={
                "demand_id": f"demand-payload-contract-{role}",
                "basis_revision": 1,
                "demand_ref": f"dref-payload-contract-{role}",
            },
            objective=f"Exercise payload contracts for {task_id}.",
            selection_reason="The payload-contract fixture requires one active Task.",
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
        )

    def test_catalog_payload_fields_match_definitions(self) -> None:
        descriptions = catalog.env_tools_description()
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                with self.subTest(tool=tool, action=action):
                    action_def = catalog.get_action_definition(tool, action)
                    expected = sorted((action_def.input_schema.get("properties") or {}).keys())
                    self.assertEqual(
                        set(descriptions[tool]["payload_fields"][action]),
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
        application = activate_application()
        role_ids = application.role_host.valid_role_ids
        for tool in sorted(catalog.supported_tools()):
            for action in sorted(catalog.supported_actions(tool)):
                with self.subTest(tool=tool, action=action):
                    action_def = catalog.get_action_definition(tool, action)
                    allowed_roles = {
                        role
                        for role in role_ids
                        if application.role_authority.authorize(
                            action_def.required_permission,
                            role,
                        ).allowed
                    }
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

    def test_retired_tool_package_and_legacy_message_domain_are_absent(self) -> None:
        retired_tool_root = ROOT / "src" / "buddyswitch" / "env" / "tools"
        message_domain = ROOT / "src" / "buddyswitch" / "env" / "domain" / "messages.py"

        self.assertFalse(retired_tool_root.exists(), msg=retired_tool_root)
        self.assertFalse(message_domain.exists(), msg=message_domain)

    def test_current_im_surfaces_do_not_contain_retired_processing_model(self) -> None:
        current_surfaces = (
            "src/buddyswitch/modules/communication/private/state/messages.py",
            "src/buddyswitch/modules/communication/private/domain/messages.py",
            "src/buddyswitch/modules/communication/private/adapters/tool/tool.py",
            "src/buddyswitch/modules/communication/private/adapters/tool/_impl.py",
            "src/buddyswitch/modules/communication/private/adapters/actor/im_client.py",
            "src/buddyswitch/application/role_authority.py",
            "src/buddyswitch/modules/communication/private/adapters/web/external_im_session.py",
            "src/buddyswitch/modules/communication/private/adapters/web/im_http_router.py",
            "src/buddyswitch/modules/task/private/adapters/goal/handler.py",
            "src/buddyswitch/modules/demand/skills/demand-orchestration/SKILL.md",
            "docs/arch/web-interface-call-architecture.md",
        )
        retired = (
            "message_" + "states",
            "update_im_" + "disposition",
            "message." + "mark",
            "original_final_" + "disposition",
            "processable " + "inbound",
            "per-identity " + "dispositions",
            "disposition " + "marking",
            "disposition " + "behavior",
        )
        violations: list[str] = []
        for relative_path in current_surfaces:
            text = (ROOT / relative_path).read_text(encoding="utf-8").lower()
            for token in retired:
                if token in text:
                    violations.append(f"{relative_path}: {token}")

        self.assertEqual(violations, [], msg="\n".join(violations))
