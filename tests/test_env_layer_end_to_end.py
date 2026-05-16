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

_OLD_BUDDYBOX_ROOT = "buddyswitch/content/" + "buddybox"


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

        buddybox = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"logical_name": "e2e/notes.md", "content": "# runless\n"},
        )
        self.assertTrue(buddybox["ok"], msg=buddybox)
        self.assertEqual(buddybox.get("logical_name"), "e2e/notes.md")

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
                "source_refs": [{"type": "artifact", "id": "art-pm-e2e-prd-r1"}],
                "reason": "implement",
                "context": "handoff context",
                "status": "active",
            },
        )
        self.assertTrue(handoff["ok"], msg=handoff)

        self.assertIsNotNone(env_store.get_track("track-e2e-runless"))
        self.assertIsNotNone(env_store.get_task("task-pm-e2e-runless"))
        self.assertIsNotNone(env_store.get_artifact("art-pm-e2e-prd-r1"))
        self.assertIsNotNone(env_store.get_handoff("handoff-pm-dev-e2e"))
        self.assertTrue(self._runtime_path("buddyswitch/local/buddybox/pm/e2e/notes.md").exists())
        self.assertFalse(self._runtime_path(f"{_OLD_BUDDYBOX_ROOT}/pm/e2e/notes.md").exists())
        self.assertFalse(self._runtime_path("runs/raw").exists())
        self.assertFalse(self._runtime_path("buddyswitch/content/runs").exists())

    def test_private_buddybox_logical_file_can_be_promoted_by_artifact_content_only(self) -> None:
        track = self._dispatch(
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-e2e-logical-promotion",
                "title": "Logical Promotion",
                "summary": "promote private file content",
                "next_buddy": "dev",
            },
        )
        self.assertTrue(track["ok"], msg=track)

        task = self._dispatch(
            buddy="pm",
            tool="task",
            action="create",
            args={
                "task_id": "task-pm-logical-promotion",
                "title": "Draft private notes",
                "summary": "pm private draft",
                "track_id": "track-e2e-logical-promotion",
            },
        )
        self.assertTrue(task["ok"], msg=task)

        written = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"logical_name": "drafts/prd.html", "content": "<h1>PRD draft</h1>\n"},
        )
        self.assertTrue(written["ok"], msg=written)

        read_pm = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="read",
            args={"logical_name": "drafts/prd.html", "encoding": "utf-8"},
        )
        self.assertTrue(read_pm["ok"], msg=read_pm)
        content = read_pm.get("content")
        self.assertIsInstance(content, str, msg=read_pm)
        assert isinstance(content, str)

        created_artifact = self._dispatch(
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-logical-promotion-r1",
                "task_id": "task-pm-logical-promotion",
                "kind": "prd",
                "title": "Promoted PRD Content",
                "summary": "from private draft",
                "content": {"body": content},
                "source_refs": [{"type": "buddybox", "logical_name": "drafts/prd.html"}],
            },
        )
        self.assertTrue(created_artifact["ok"], msg=created_artifact)

        read_as_dev = self._dispatch(
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-logical-promotion-r1"},
        )
        self.assertTrue(read_as_dev["ok"], msg=read_as_dev)
        artifact = read_as_dev.get("artifact")
        self.assertIsInstance(artifact, dict, msg=read_as_dev)
        assert isinstance(artifact, dict)
        self.assertEqual(((artifact.get("content") or {}).get("body")), content)

        denied_dev_prefixed = self._dispatch(
            buddy="dev",
            tool="buddybox",
            action="read",
            args={"logical_name": "pm/drafts/prd.html"},
        )
        self.assertFalse(denied_dev_prefixed["ok"], msg=denied_dev_prefixed)
        self.assertEqual((denied_dev_prefixed.get("error") or {}).get("code"), "E_BUDDYBOX_LOGICAL_NAME")

        denied_dev_local = self._dispatch(
            buddy="dev",
            tool="buddybox",
            action="read",
            args={"logical_name": "drafts/prd.html"},
        )
        self.assertFalse(denied_dev_local["ok"], msg=denied_dev_local)
        self.assertEqual((denied_dev_local.get("error") or {}).get("code"), "E_BUDDYBOX_NOT_FOUND")

    def test_cross_buddy_identity_scope_follows_service_permissions(self) -> None:
        env_store.create_task(
            "task-pm-private",
            "Private task",
            buddy="pm",
            track_id=None,
            summary="seed",
        )
        env_store.create_artifact(
            artifact_id="art-pm-private-r1",
            title="Private artifact",
            buddy="pm",
            kind="spec",
            task_id="task-pm-private",
            summary="private",
            content={"body": "private"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )
        denied = self._dispatch(
            buddy="design",
            tool="artifact",
            action="update_metadata",
            args={"artifact_id": "art-pm-private-r1", "summary": "mutate"},
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["permission_boundary"], "artifact.buddy_scope")

    def test_response_planes_distinguish_product_private_token_and_browser_session(self) -> None:
        track = self._dispatch(
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-e2e-planes", "title": "Planes", "summary": "planes"},
        )
        self.assertTrue(track["ok"], msg=track)
        task = self._dispatch(
            buddy="pm",
            tool="task",
            action="create",
            args={"task_id": "task-e2e-planes", "title": "Planes task", "track_id": "track-e2e-planes"},
        )
        self.assertTrue(task["ok"], msg=task)
        artifact = self._dispatch(
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-e2e-planes-r1",
                "task_id": "task-e2e-planes",
                "kind": "spec",
                "title": "Planes spec",
                "content": {"body": "seed"},
            },
        )
        self.assertTrue(artifact["ok"], msg=artifact)
        self.assertEqual(artifact.get("durability"), "durable")
        self.assertIsInstance(artifact.get("state_changes"), list, msg=artifact)

        buddybox_write = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"logical_name": "planes/private.txt", "content": "private"},
        )
        self.assertTrue(buddybox_write["ok"], msg=buddybox_write)
        self.assertEqual(buddybox_write.get("durability"), "active_instance_local")
        self.assertFalse(buddybox_write.get("mutates_product_state"), msg=buddybox_write)

        evidence = self._dispatch(
            buddy="pm",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": "art-e2e-planes-r1"},
        )
        self.assertTrue(evidence["ok"], msg=evidence)
        self.assertEqual(evidence.get("durability"), "transient token")
        self.assertFalse(evidence.get("mutates_product_state"), msg=evidence)


if __name__ == "__main__":
    unittest.main()
