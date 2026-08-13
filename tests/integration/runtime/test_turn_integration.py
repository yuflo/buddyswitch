"""Integration tests for PM/product artifact relation route."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.foundation.tool_runtime import registry as tool_router  # noqa: E402
from tests.support.runtime import RuntimeTestWorkspace  # noqa: E402


class TurnRuntimeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = RuntimeTestWorkspace()
        self.addCleanup(self.workspace.close)
        self.runtime_root = self.workspace.root
        self.actor_id = self.workspace.actor_id(role="pm", label="act-runless-integration")
        self.instance_json = self.workspace.path("instance.json")
        self.instance_json.write_text(
            json.dumps(
                {
                    "actor_id": self.actor_id,
                    "role": "pm",
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

    def _dispatch(self, *, role: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        actor_id = self.workspace.actor_id(role=role, label="act-runless-integration")
        self.workspace.seed_active_task(
            instance_json=self.instance_json,
            role=role,
            actor_id=actor_id,
            task_slug=f"{role}-turn-integration",
        )
        instance_payload = {
            "actor_id": actor_id,
            "role": role,
            "status": "active",
            "workspace_dir": str(self.runtime_root),
            "browser_port": 9222,
        }
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_role=role,
            actor_id=actor_id,
            instance_json=self.instance_json,
            instance_payload=instance_payload,
        )

    def test_pm_product_relation_uses_track_artifact_relation_not_project_write(self) -> None:
        track = self._dispatch(
            role="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-runless-flow",
                "title": "Runless Flow",
                "outcome": "Integration path",
                "now": {"next": "seed", "blocker": None},
            },
        )
        self.assertTrue(track["ok"], msg=track)
        track_id = (track.get("track") or {}).get("id")
        self.assertEqual(track_id, "track-runless-flow")

        draft = self._dispatch(
            role="pm",
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
        self.assertNotIn("status", draft.get("artifact") or {})

        publish = self._dispatch(
            role="pm",
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
        self.assertIn("material_relation_added", changes)

        context_summary = self._dispatch(
            role="pm",
            tool="context",
            action="summarize",
            args={"track_id": "track-runless-flow", "limit": 5},
        )
        self.assertTrue(context_summary.get("ok"), msg=context_summary)
        affordances = context_summary.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=context_summary)
        assert isinstance(affordances, dict)
        for tool_name in ("track", "artifact", "context"):
            self.assertIn(tool_name, affordances)
        self.assertNotIn("actor_private", affordances)

        opened = self._dispatch(
            role="pm",
            tool="track",
            action="open",
            args={"track_id": "track-runless-flow"},
        )
        self.assertTrue(opened["ok"], msg=opened)
        current_materials = [
            row
            for row in (opened.get("track") or {}).get("artifact_relations", [])
            if isinstance(row, dict) and row.get("role") == "material" and bool(row.get("current"))
        ]
        self.assertEqual(
            [row.get("artifact_id") for row in current_materials],
            ["art-runless-prd-r1"],
        )

        design_read = self._dispatch(
            role="design",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-runless-prd-r1"},
        )
        self.assertTrue(design_read["ok"], msg=design_read)
        self.assertIn("acceptance criteria", (design_read.get("artifact") or {}).get("body", ""))

        project_app = self.workspace.path("projects/app")
        if project_app.exists():
            if project_app.is_file():
                self.assertEqual(project_app.stat().st_size, 0)
            else:
                self.assertEqual(list(project_app.rglob("*")), [])

    def test_market_evidence_requires_target_model(self) -> None:
        rejected = self._dispatch(role="market", tool="evidence", action="issue_browser", args={})
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["permission_boundary"], "request-payload")
