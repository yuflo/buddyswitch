#!/usr/bin/env python3
"""Runless end-to-end env layer coverage."""

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
import env_store  # noqa: E402
from env.tools import router as tool_router  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class EnvLayerEndToEndTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_json = self._runtime_path("instance.json")
        self.instance_payload = {
            "instance_id": "inst-e2e-runless",
            "buddy": "pm",
            "status": "active",
            "workspace_dir": str(self.runtime_root),
            "browser_port": 9333,
        }
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _dispatch(self, *, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy=buddy,
            instance_id="inst-e2e-runless",
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "buddy": buddy},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def test_full_flow_persists_only_runless_product_state(self) -> None:
        track = self._dispatch(
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-e2e-runless", "title": "E2E Runless", "summary": "flow"},
        )
        self.assertTrue(track["ok"], msg=track)

        task = self._dispatch(
            buddy="pm",
            tool="task",
            action="create",
            args={"task_id": "task-pm-e2e-runless", "title": "Draft PRD", "summary": "flow", "track_id": "track-e2e-runless"},
        )
        self.assertTrue(task["ok"], msg=task)

        artifact = self._dispatch(
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-e2e-prd-r1",
                "task_id": "task-pm-e2e-runless",
                "kind": "prd",
                "title": "PRD",
                "summary": "runless artifact",
                "content": {"body": "v1"},
            },
        )
        self.assertTrue(artifact["ok"], msg=artifact)

        memory = self._dispatch(
            buddy="pm",
            tool="memory",
            action="write",
            args={
                "memory_id": "mem-pm-e2e-decision",
                "kind": "decision",
                "title": "Decision",
                "summary": "runless memory",
                "content": {"body": "keep runless"},
            },
        )
        self.assertTrue(memory["ok"], msg=memory)

        buddybox = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"path": "pm/e2e/notes.md", "content": "# runless\n"},
        )
        self.assertTrue(buddybox["ok"], msg=buddybox)

        handoff = self._dispatch(
            buddy="pm",
            tool="handoff",
            action="create",
            args={
                "handoff_id": "handoff-pm-dev-e2e",
                "track_id": "track-e2e-runless",
                "source_task_id": "task-pm-e2e-runless",
                "target_buddy": "dev",
                "artifact_ids": ["art-pm-e2e-prd-r1"],
                "memory_ids": ["mem-pm-e2e-decision"],
                "buddybox_paths": ["pm/e2e/notes.md"],
                "reason": "implement",
                "context": "handoff context",
                "status": "active",
            },
        )
        self.assertTrue(handoff["ok"], msg=handoff)

        self.assertIsNotNone(env_store.get_track("track-e2e-runless"))
        self.assertIsNotNone(env_store.get_task("task-pm-e2e-runless"))
        self.assertIsNotNone(env_store.get_artifact("art-pm-e2e-prd-r1"))
        self.assertIsNotNone(env_store.get_memory("mem-pm-e2e-decision"))
        self.assertIsNotNone(env_store.get_handoff("handoff-pm-dev-e2e"))
        self.assertTrue(self._runtime_path("buddyswitch/content/buddybox/pm/e2e/notes.md").exists())
        self.assertFalse(self._runtime_path("runs/raw").exists())
        self.assertFalse(self._runtime_path("buddyswitch/content/runs").exists())

    def test_cross_buddy_identity_scope_follows_service_permissions(self) -> None:
        env_store.create_memory(
            memory_id="mem-pm-private",
            buddy="pm",
            kind="fact",
            title="private",
            summary="private",
            content={"body": "private"},
            source_refs=None,
        )
        denied = self._dispatch(
            buddy="design",
            tool="memory",
            action="update",
            args={"memory_id": "mem-pm-private", "summary": "mutate"},
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["permission_boundary"], "memory.buddy_scope")


if __name__ == "__main__":
    unittest.main()
