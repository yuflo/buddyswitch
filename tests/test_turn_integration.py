#!/usr/bin/env python3
"""Integration tests for explicit-id collaboration flow."""

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


class TurnRuntimeIntegrationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_json = self._runtime_path("instance.json")
        self.instance_json.write_text(
            json.dumps(
                {
                    "instance_id": "inst-runless-integration",
                    "buddy": "pm",
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": 9222,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _dispatch(self, *, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        instance_payload = {
            "instance_id": "inst-runless-integration",
            "buddy": buddy,
            "status": "active",
            "workspace_dir": str(self.runtime_root),
            "browser_port": 9222,
        }
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy=buddy,
            instance_id="inst-runless-integration",
            instance_json=self.instance_json,
            instance_payload=instance_payload,
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def test_cross_buddy_flow_uses_track_publication_and_artifact_get(self) -> None:
        track = self._dispatch(
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-runless-flow", "title": "Runless Flow", "summary": "Integration path"},
        )
        self.assertTrue(track["ok"], msg=track)
        track_id = track["track"]["id"]

        artifact = self._dispatch(
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-runless-flow-prd-r1",
                "title": "PRD",
                "summary": "Runless PRD",
                "template": "brief",
                "body": "v1",
                "status": "published",
                "published_to_track": track_id,
            },
        )
        self.assertTrue(artifact["ok"], msg=artifact)
        artifact_id = artifact["artifact"]["id"]

        design_read = self._dispatch(
            buddy="design",
            tool="artifact",
            action="get",
            args={"artifact_id": artifact_id},
        )
        self.assertTrue(design_read["ok"], msg=design_read)
        self.assertEqual(design_read.get("read_scope"), "one readable artifact markdown page")
        self.assertEqual((design_read["artifact"] or {}).get("id"), artifact_id)
        self.assertEqual((design_read["artifact"] or {}).get("template"), "brief")
        self.assertEqual((design_read["artifact"] or {}).get("published_to_track"), track_id)

        track_context = self._dispatch(
            buddy="design",
            tool="track",
            action="get",
            args={"track_id": track_id},
        )
        self.assertTrue(track_context["ok"], msg=track_context)
        self.assertEqual(
            [row.get("artifact_id") for row in track_context.get("shared_materials", [])],
            [artifact_id],
        )

        self.assertFalse(self._runtime_path("runs/raw").exists())
        self.assertFalse(self._runtime_path("buddyswitch/content/runs").exists())

    def test_market_evidence_requires_target_model(self) -> None:
        rejected = self._dispatch(buddy="market", tool="evidence", action="issue_browser", args={})
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["permission_boundary"], "request-payload")


if __name__ == "__main__":
    unittest.main()
