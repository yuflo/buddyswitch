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
        track = env_store.create_track("track-market-decision", "Market Decision", owner_buddy="market")
        env_store.create_task("task-market-decision", "Scan market", buddy="market", track_id=track["id"])

        response = self._dispatch(buddy="market", tool="context", action="summarize", args={})
        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(response["decision_surface"]["binding_state"]["state"], "runless")
        self.assertNotIn("has_memories", response["decision_surface"]["context_readiness"])
        self.assertNotIn("memory_summaries", response)
        self.assertIn("candidate_tracks", response)
        self.assertTrue(any(row.get("track_id") == "track-market-decision" for row in response["candidate_tracks"]))
        affordances = response.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=response)
        assert isinstance(affordances, dict)
        self.assertTrue({"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment"}.issubset(set(affordances)))
        self.assertNotIn("handoff", affordances)
        self.assertNotIn("project_source", affordances)

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

    def test_pm_page_prototype_decision_surface_prefers_private_buddybox_without_phrase_rule(self) -> None:
        pm_agents = (ROOT / "tools" / "launcher" / "assets" / "buddies" / "pm" / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("project.access=read-only", pm_agents)

        summary = self._dispatch(buddy="pm", tool="context", action="summarize", args={})
        self.assertTrue(summary["ok"], msg=summary)
        affordances = summary.get("tool_affordances")
        self.assertIsInstance(affordances, dict, msg=summary)
        assert isinstance(affordances, dict)
        buddybox = affordances.get("buddybox")
        artifact = affordances.get("artifact")
        task = affordances.get("task")
        track = affordances.get("track")
        context_tool = affordances.get("context")
        evidence = affordances.get("evidence")
        search = affordances.get("search")
        self.assertIsInstance(buddybox, dict, msg=summary)
        self.assertIsInstance(artifact, dict, msg=summary)
        self.assertIsInstance(task, dict, msg=summary)
        self.assertIsInstance(track, dict, msg=summary)
        self.assertIsInstance(context_tool, dict, msg=summary)
        self.assertIsInstance(evidence, dict, msg=summary)
        self.assertIsInstance(search, dict, msg=summary)
        assert isinstance(buddybox, dict)
        assert isinstance(artifact, dict)
        assert isinstance(task, dict)
        assert isinstance(track, dict)
        assert isinstance(context_tool, dict)
        assert isinstance(evidence, dict)
        assert isinstance(search, dict)
        for compact in (buddybox, artifact, task, track, context_tool, evidence, search):
            for key in ("capability", "when_to_use", "when_not_to_use", "returns", "state_effect"):
                self.assertIn(key, compact, msg=compact)

        context_get = self._dispatch(buddy="pm", tool="context", action="get", args={})
        self.assertTrue(context_get["ok"], msg=context_get)
        buddybox_catalog = context_get["tool_catalog"]["buddybox"]
        write_semantics = buddybox_catalog["action_semantics"]["write"]
        self.assertEqual(write_semantics.get("title"), "buddybox.write")
        self.assertIn("side_effects", write_semantics)
        semantic_payload = json.dumps(
            {"summary": affordances, "buddybox_write": write_semantics},
            ensure_ascii=True,
        ).lower()
        self.assertNotIn("prototype means", semantic_payload)
        self.assertNotIn("quickly build means", semantic_payload)

        written = self._dispatch(
            buddy="pm",
            tool="buddybox",
            action="write",
            args={
                "logical_name": "prototypes/simple-page.html",
                "content": "<!doctype html><html><body><h1>Prototype</h1></body></html>",
                "content_type": "text/html",
            },
        )
        self.assertTrue(written["ok"], msg=written)
        self.assertTrue(self._runtime_path("buddyswitch/local/buddybox/pm/prototypes/simple-page.html").exists())
        self.assertFalse(written.get("mutates_product_state"), msg=written)
        self.assertEqual(written.get("mutated_product_objects"), [], msg=written)

        options = written.get("allowed_next_action_options")
        self.assertIsInstance(options, list, msg=written)
        assert isinstance(options, list)
        option_pairs = {
            (row.get("tool"), row.get("action"))
            for row in options
            if isinstance(row, dict)
        }
        self.assertIn(("buddybox", "read"), option_pairs)
        self.assertIn(("buddybox", "list"), option_pairs)
        self.assertIn(("artifact", "create_revision"), option_pairs)
        promotion = next(
            row
            for row in options
            if isinstance(row, dict) and row.get("tool") == "artifact" and row.get("action") == "create_revision"
        )
        self.assertIn("when", str(promotion.get("reason", "")).lower())
        self.assertNotIn("must", str(promotion.get("reason", "")).lower())
        self.assertNotIn("always", str(promotion.get("reason", "")).lower())
        for row in options:
            if not isinstance(row, dict):
                continue
            for key in ("tool", "action", "mutates", "preconditions", "reason", "source_refs"):
                self.assertIn(key, row, msg=row)


if __name__ == "__main__":
    unittest.main()
