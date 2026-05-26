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
        self.instance_payload = {
            "instance_id": "inst-identity-runless",
            "buddy": "pm",
            "status": "active",
            "workspace_dir": str(self.runtime_root),
        }
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _dispatch(self, *, active_buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy=active_buddy,
            instance_id="inst-identity-runless",
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "buddy": active_buddy},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def test_task_propose_rejects_payload_owner_fields(self) -> None:
        payload = self._dispatch(
            active_buddy="pm",
            tool="task",
            action="propose",
            args={
                "type": "start",
                "reason": "Identity boundary test.",
                "evidence": "Payload tries to override owner.",
                "task": {
                    "title": "Identity",
                    "body": "runless",
                    "buddy": "design",
                    "active_buddy": "design",
                },
            },
        )
        self.assertFalse(payload["ok"], msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_TASK_PAYLOAD")
        self.assertEqual(payload.get("permission_boundary"), "request-payload")
        self.assertIs(payload.get("state_changed"), False)

    def test_runtime_surface_has_no_run_or_binding_identity_tools(self) -> None:
        payload = self._dispatch(
            active_buddy="pm",
            tool="context",
            action="list_sources",
            args={},
        )
        self.assertTrue(payload["ok"], msg=payload)
        sources = payload["sources"]
        self.assertNotIn("memories", sources)
        self.assertNotIn("buddybox", sources)
        self.assertIn("writable_surfaces", sources)
        writable = sources["writable_surfaces"] or {}
        self.assertFalse(writable.get("mutates_product_state"))
        self.assertFalse(writable.get("grants_write_authority"))
        self.assertNotIn("runs", sources)


if __name__ == "__main__":
    unittest.main()
