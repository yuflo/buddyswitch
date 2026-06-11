#!/usr/bin/env python3
"""Runless env.tool identity boundary tests."""

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
from env.tool_runtime import registry as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class EnvToolIdentityTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_json = self._runtime_path("instance.json")
        self.actor_id = self._actor_id_for("pm")
        self.instance_payload = {
            "actor_id": self.actor_id,
            "role": "pm",
            "status": "active",
            "workspace_dir": str(self.runtime_root),
        }
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _actor_id_for(self, role: str) -> str:
        suffix = {
            "dev": "1de000000001",
            "pm": "1de000000002",
            "design": "1de000000003",
            "market": "1de000000004",
            "test": "1de000000005",
        }[role]
        return f"act-{role}-{suffix}"

    def _dispatch(self, *, active_role: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        actor_id = self._actor_id_for(active_role)
        self._seed_active_task_for_instance(
            instance_json=self.instance_json,
            role=active_role,
            actor_id=actor_id,
            task_slug=f"{active_role}-identity",
        )
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_role=active_role,
            actor_id=actor_id,
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "actor_id": actor_id, "role": active_role},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def test_task_capture_rejects_payload_owner_fields(self) -> None:
        payload = self._dispatch(
            active_role="pm",
            tool="task",
            action="capture",
            args={
                "reason": "Identity boundary test.",
                "evidence": "Payload tries to override owner.",
                "task": {
                    "title": "Identity",
                    "body": "runless",
                    "role": "design",
                    "active_role": "design",
                },
            },
        )
        self.assertFalse(payload["ok"], msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_TASK_PAYLOAD")
        self.assertEqual(payload.get("permission_boundary"), "request-payload")
        self.assertIs(payload.get("state_changed"), False)

    def test_role_auth_uses_runtime_actor_not_payload_identity_hints(self) -> None:
        payload = self._dispatch(
            active_role="dev",
            tool="track",
            action="create",
            args={
                "track_id": "track-identity-spoof",
                "title": "Identity spoof",
                "outcome": "x",
                "now": {"next": "seed", "blocker": None},
                "active_role": "pm",
                "role": "pm",
            },
        )

        self.assertFalse(payload["ok"], msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")
        self.assertEqual(payload.get("permission_boundary"), "request-payload")
        self.assertEqual(payload.get("active_role"), "dev")
        self.assertIs(payload.get("state_changed"), False)

    def test_runtime_surface_has_no_run_or_binding_identity_tools(self) -> None:
        payload = self._dispatch(
            active_role="pm",
            tool="context",
            action="list_sources",
            args={},
        )
        self.assertTrue(payload["ok"], msg=payload)
        sources = payload["sources"]
        self.assertNotIn("memories", sources)
        self.assertNotIn("actor_private", sources)
        self.assertIn("writable_surfaces", sources)
        writable = sources["writable_surfaces"] or {}
        self.assertFalse(writable.get("mutates_product_state"))
        self.assertFalse(writable.get("grants_write_authority"))
        self.assertNotIn("runs", sources)


if __name__ == "__main__":
    unittest.main()
