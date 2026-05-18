#!/usr/bin/env python3
"""Integration tests for PM/product publication route."""

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

    def test_pm_product_request_uses_track_artifact_publication_not_project_write(self) -> None:
        track = self._dispatch(
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-runless-flow",
                "title": "Runless Flow",
                "outcome": "Integration path",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self.assertTrue(track["ok"], msg=track)
        track_id = (track.get("track") or {}).get("id")
        self.assertEqual(track_id, "track-runless-flow")

        draft = self._dispatch(
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-runless-prd-r1",
                "title": "Landing brief",
                "summary": "PM product definition",
                "template": "brief",
                "body": "# Landing brief\n\n- audience\n- positioning\n- acceptance criteria",
            },
        )
        self.assertTrue(draft["ok"], msg=draft)
        self.assertEqual((draft.get("artifact") or {}).get("status"), "draft")

        publish = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-runless-flow",
                "artifact_id": "art-runless-prd-r1",
                "label": "PM Brief",
                "summary": "Landing scope and acceptance",
            },
        )
        self.assertTrue(publish["ok"], msg=publish)
        self.assertEqual(publish.get("durability"), "durable")
        state_changes = publish.get("state_changes")
        self.assertIsInstance(state_changes, list, msg=publish)
        assert isinstance(state_changes, list)
        changes = {row.get("change") for row in state_changes if isinstance(row, dict)}
        self.assertIn("published_material", changes)
        self.assertIn("material_added", changes)

        opened = self._dispatch(
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-runless-flow"},
        )
        self.assertTrue(opened["ok"], msg=opened)
        self.assertEqual(
            [row.get("artifact_id") for row in (opened.get("track") or {}).get("shared_materials", [])],
            ["art-runless-prd-r1"],
        )

        design_read = self._dispatch(
            buddy="design",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-runless-prd-r1"},
        )
        self.assertTrue(design_read["ok"], msg=design_read)
        self.assertIn("acceptance criteria", (design_read.get("artifact") or {}).get("body", ""))

        project_app = self._runtime_path("projects/app")
        if project_app.exists():
            if project_app.is_file():
                self.assertEqual(project_app.stat().st_size, 0)
            else:
                self.assertEqual(list(project_app.rglob("*")), [])

    def test_market_evidence_requires_target_model(self) -> None:
        rejected = self._dispatch(buddy="market", tool="evidence", action="issue_browser", args={})
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["permission_boundary"], "request-payload")


if __name__ == "__main__":
    unittest.main()
