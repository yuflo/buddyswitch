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
from env.tools import router as tool_router  # noqa: E402
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

    def test_task_create_uses_runtime_active_buddy_not_payload_buddy(self) -> None:
        payload = self._dispatch(
            active_buddy="pm",
            tool="task",
            action="create",
            args={
                "task_id": "task-identity-owner",
                "title": "Identity",
                "summary": "runless",
                "buddy": "design",
                "active_buddy": "design",
            },
        )
        self.assertTrue(payload["ok"], msg=payload)
        self.assertEqual(payload["active_buddy"], "pm")
        self.assertEqual(payload["task"]["buddy"], "pm")

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
        self.assertIn("buddybox", sources)
        self.assertNotIn("runs", sources)


if __name__ == "__main__":
    unittest.main()
