#!/usr/bin/env python3
"""Integration flows for buddy-run persistence collaboration."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import turn_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"
MARKET_REQUEST = "对于 track-id 这样一款产品的landing page，我们想了解这类产品在营销上应该怎么表达和展现，以及目前相关竞品的情况和它们的landing page"

PM_COMMIT = {
    "execution_summary": "PM wrote the AI schedule tool landing page PRD and created the delivery track.",
    "working_notes": ["The user requested PRD creation and track binding in one PM run."],
    "artifacts": [
        {
            "kind": "prd",
            "title": "AI Schedule Tool Landing Page PRD",
            "summary": "Defines landing page scope, sections, MVP requirements, and acceptance criteria.",
            "content": {
                "problem": "Busy professionals need an AI-assisted way to reduce scheduling overhead.",
                "target_users": ["calendar-heavy professionals", "small team operators"],
            },
        }
    ],
    "state_effects": {
        "track": {
            "action": "create",
            "track_id": "track-ai-schedule-landing-page",
            "title": "AI Schedule Tool Landing Page",
            "status": "active",
            "current_buddy": "pm",
            "next_buddy": "market",
            "summary": "Cross-buddy landing page iteration for an AI schedule tool.",
        },
        "task": {
            "status": "done",
            "summary": "PM PRD is ready for market positioning research.",
        },
    },
    "handoff": {
        "next_buddy": "market",
        "reason": "Market should validate competitor landing page positioning before design.",
        "context": "Use the PRD artifact and track summary as source context.",
    },
    "contributors": {
        "skills": ["write-prd", "track-manager"],
        "agents": [],
    },
}

MARKET_COMMIT = {
    "execution_summary": "Market analyzed AI scheduling landing page competitors and recommended positioning angles.",
    "working_notes": ["The request referenced the existing PM-created track."],
    "artifacts": [
        {
            "kind": "market-landing-page-brief",
            "title": "AI Schedule Tool Landing Page Market Brief",
            "summary": "Summarizes competitor messaging patterns and recommended landing page expression.",
            "content": {
                "research_question": "How should an AI schedule tool express and present itself on a landing page?",
                "recommended_angles": ["recover focus time", "reduce back-and-forth scheduling"],
            },
        }
    ],
    "handoff": {
        "next_buddy": "design",
        "reason": "Design can now combine PRD scope with market positioning.",
        "context": "Use the PRD artifact and market landing page brief on this track.",
    },
    "contributors": {
        "skills": ["research-scan", "positioning-copy"],
        "agents": [],
    },
}


class TurnRuntimeIntegrationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _session(self, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "instance_id": "instance-test",
            "active_buddy": buddy,
            "payload": payload or {},
        }

    def _prepare(self, request_text: str, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        with patch.object(turn_runtime, "_load_product_mode_session", return_value=self._session(buddy=buddy, payload=payload)):
            context = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)
        self.assertTrue(context["ok"], msg=context)
        return context

    def _persist(self, context: dict[str, object], result: dict[str, object]) -> dict[str, object]:
        payload = turn_runtime.persist_buddy_run(context, result=result, manifest_path=MANIFEST)
        self.assertTrue(payload["ok"], msg=payload)
        return payload

    def test_pm_to_market_collaboration_persists_on_one_track_without_skill_ids(self) -> None:
        pm_context = self._prepare(PM_REQUEST, buddy="pm")
        pm_persisted = self._persist(pm_context, PM_COMMIT)
        pm_receipt = pm_persisted["receipt"]
        track_id = pm_receipt["track_id"]

        market_context = self._prepare(
            MARKET_REQUEST,
            buddy="market",
            payload={"current_track_id": track_id},
        )
        market_persisted = self._persist(market_context, MARKET_COMMIT)
        market_receipt = market_persisted["receipt"]

        track = env_store.get_track(track_id)
        self.assertIsNotNone(track)
        assert track is not None
        self.assertEqual(track["id"], track_id)
        self.assertEqual(len(track["task_ids"]), 2)

        index = env_store.build_track_artifact_index(track_id)
        self.assertIsNotNone(index)
        assert index is not None
        kinds = {
            artifact["kind"]
            for task in index["tasks"]
            for artifact in task["artifacts"]
            if artifact.get("is_current")
        }
        self.assertIn("prd", kinds)
        self.assertIn("market-landing-page-brief", kinds)

        pm_run = json.loads(
            self._runtime_path(f"buddyswitch/content/runs/{pm_receipt['run_id']}.json").read_text(encoding="utf-8")
        )
        market_run = json.loads(
            self._runtime_path(f"buddyswitch/content/runs/{market_receipt['run_id']}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(pm_run["buddy_id"], "pm")
        self.assertEqual(market_run["buddy_id"], "market")
        self.assertNotIn("skill_id", pm_run)
        self.assertNotIn("skill_id", market_run)

    def test_design_prepare_on_market_handoff_track_exposes_prior_artifacts(self) -> None:
        pm_context = self._prepare(PM_REQUEST, buddy="pm")
        pm_persisted = self._persist(pm_context, PM_COMMIT)
        track_id = pm_persisted["receipt"]["track_id"]

        market_context = self._prepare(
            MARKET_REQUEST,
            buddy="market",
            payload={"current_track_id": track_id},
        )
        self._persist(market_context, MARKET_COMMIT)

        design_context = self._prepare(
            "根据已有track继续设计",
            buddy="design",
            payload={"current_track_id": track_id},
        )
        self.assertEqual(design_context["current_track_id"], track_id)

        track_context = design_context["track_context"]
        self.assertIsNotNone(track_context)
        assert isinstance(track_context, dict)
        tasks = track_context["tasks"]
        source_kinds = {
            artifact["kind"]
            for row in tasks
            for artifact in row.get("current_artifacts", {}).values()
        }
        self.assertIn("prd", source_kinds)
        self.assertIn("market-landing-page-brief", source_kinds)

        for row in tasks:
            for artifact in row.get("current_artifacts", {}).values():
                self.assertIn("buddy", artifact)
                self.assertIn("source_run_id", artifact)

        recent_handoffs = track_context.get("recent_handoffs")
        self.assertIsInstance(recent_handoffs, list)
        assert isinstance(recent_handoffs, list)
        market_handoff = next((row for row in recent_handoffs if row.get("next_buddy") == "design"), None)
        self.assertIsNotNone(market_handoff)
        assert isinstance(market_handoff, dict)
        self.assertEqual(
            market_handoff.get("reason"),
            "Design can now combine PRD scope with market positioning.",
        )
        self.assertEqual(
            market_handoff.get("context"),
            "Use the PRD artifact and market landing page brief on this track.",
        )


if __name__ == "__main__":
    unittest.main()
