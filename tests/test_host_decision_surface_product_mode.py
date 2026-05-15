#!/usr/bin/env python3
"""Runless decision-surface coverage for product mode host flows."""

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


class HostDecisionSurfaceProductModeTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = ROOT / "buddyswitch" / "manifest.toml"
        self.manifest = env_manifest.load_manifest(self.manifest_path)
        self.instance_json = self._runtime_path("instance.json")
        self.instance_payload = {
            "instance_id": "inst-market-decision-surface",
            "buddy": "market",
            "status": "active",
            "workspace_dir": str(self.runtime_root),
            "browser_port": 9555,
        }
        self.instance_json.write_text(json.dumps(self.instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _dispatch(self, *, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        return tool_router.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_buddy=buddy,
            instance_id="inst-market-decision-surface",
            instance_json=self.instance_json,
            instance_payload={**self.instance_payload, "buddy": buddy},
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )

    def test_context_summarize_projects_runless_decision_surface(self) -> None:
        track = env_store.create_track("track-market-decision", "Market Decision", current_buddy="market", next_buddy="design")
        env_store.create_task("task-market-decision", "Scan market", buddy="market", track_id=track["id"])
        env_store.create_memory(
            memory_id="mem-market-decision",
            buddy="market",
            kind="fact",
            title="Decision memory",
            summary="Context row",
            content={"body": "facts"},
            source_refs=None,
        )

        response = self._dispatch(buddy="market", tool="context", action="summarize", args={})
        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(response["decision_surface"]["binding_state"]["state"], "runless")
        self.assertIn("candidate_tracks", response)
        self.assertTrue(any(row.get("track_id") == "track-market-decision" for row in response["candidate_tracks"]))

    def test_market_evidence_requires_target_scoped_args(self) -> None:
        response = self._dispatch(buddy="market", tool="evidence", action="issue_browser", args={"reason": "no target"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["permission_boundary"], "request-payload")
        self.assertIn("unsupported payload fields", response["why_blocked"].lower())

    def test_non_pm_track_write_rejected_by_authority_boundary(self) -> None:
        response = self._dispatch(
            buddy="design",
            tool="track",
            action="create",
            args={"track_id": "track-design-unauthorized", "title": "No", "summary": "denied"},
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["permission_boundary"], "track.lifecycle_authority")


if __name__ == "__main__":
    unittest.main()
