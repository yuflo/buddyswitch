#!/usr/bin/env python3
"""Product-mode host decision surface scenarios for PM->Market->Design handoff flow."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v1"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"
MARKET_REQUEST = "调研 AI 日程工具 landing page 竞品表达和定位方式"
DESIGN_REQUEST = "基于现有 PRD 和市场简报，整理 landing page 原型方向"


def _pm_seed_commit(track_id: str) -> dict[str, object]:
    return {
        "execution_summary": "PM wrote PRD and handed off to Market.",
        "artifacts": [
            {
                "kind": "prd",
                "title": "Landing Page PRD",
                "summary": "Defines PM scope and constraints.",
                "content": {
                    "problem": "Scheduling overhead is too high.",
                    "requirements": ["clear value", "specific CTA"],
                },
            }
        ],
        "state_effects": {
            "track": {
                "action": "create",
                "track_id": track_id,
                "title": "Host Decision Surface Track",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "market",
                "summary": "PM -> Market -> Design decision surface fixture.",
            },
            "task": {
                "status": "done",
                "summary": "PM PRD is ready for Market continuation.",
            },
        },
        "handoff": {
            "next_buddy": "market",
            "reason": "Market should continue with evidence-backed positioning.",
            "context": "Use PM PRD and track context.",
        },
    }


def _market_commit(approved_downgrade_token: str) -> dict[str, object]:
    return {
        "execution_summary": "Market completed scan and handed off to Design.",
        "artifacts": [
            {
                "kind": "market-scan",
                "title": "Market Scan",
                "summary": "Competitor positioning and angle recommendations.",
                "content": {
                    "insights": ["Concrete workflow outcomes convert better."]
                },
            }
        ],
        "handoff": {
            "next_buddy": "design",
            "reason": "Design should continue from PM+Market context.",
            "context": "Use PRD summary and market scan artifact.",
        },
        "tool_evidence": {
            "approved_downgrade_token": approved_downgrade_token,
        },
    }


class HostDecisionSurfaceProductModeTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        buddy: str,
        instance_id: str,
        current_task_id: str | None = None,
        current_track_id: str | None = None,
    ) -> Path:
        path = self._runtime_path(f"instances/{instance_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "current_task_id": current_task_id,
                    "current_track_id": current_track_id,
                    "workspace_dir": str(path.parent / "workspace"),
                    "browser_port": None,
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(
        self,
        *,
        method: str,
        payload: dict[str, object],
        instance_json: Path,
        instance_id: str,
        buddy: str,
    ) -> dict[str, object]:
        return runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": method,
                "payload": payload,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _prepare(
        self,
        *,
        buddy: str,
        instance_id: str,
        instance_json: Path,
        text: str,
    ) -> dict[str, object]:
        prepared = self._dispatch(
            method="prepare",
            payload={"text": text},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )
        self.assertTrue(prepared.get("ok"), msg=prepared)
        payload = prepared.get("payload")
        self.assertIsInstance(payload, dict, msg=prepared)
        assert isinstance(payload, dict)
        return payload

    def _persist(
        self,
        *,
        buddy: str,
        instance_id: str,
        instance_json: Path,
        context: dict[str, object],
        result: dict[str, object],
    ) -> dict[str, object]:
        persisted = self._dispatch(
            method="persist",
            payload={"context": context, "result": result},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )
        self.assertTrue(persisted.get("ok"), msg=persisted)
        payload = persisted.get("payload")
        self.assertIsInstance(payload, dict, msg=persisted)
        assert isinstance(payload, dict)
        return payload

    def _seed_pm_handoff(self) -> tuple[str, dict[str, object]]:
        track_id = "track-host-decision-surface"
        pm_instance_id = "inst-pm-host-ds"
        pm_instance = self._instance_json(buddy="pm", instance_id=pm_instance_id)
        pm_context = self._prepare(
            buddy="pm",
            instance_id=pm_instance_id,
            instance_json=pm_instance,
            text=PM_REQUEST,
        )
        persisted = self._persist(
            buddy="pm",
            instance_id=pm_instance_id,
            instance_json=pm_instance,
            context=pm_context,
            result=_pm_seed_commit(track_id),
        )
        receipt = persisted["receipt"]
        self.assertIsInstance(receipt, dict, msg=persisted)
        assert isinstance(receipt, dict)
        return track_id, receipt

    def test_fresh_market_discovers_pm_handoff_track_without_inbox_or_binding_mutation(self) -> None:
        track_id, _ = self._seed_pm_handoff()
        market_instance_id = "inst-market-fresh-host-ds"
        market_instance = self._instance_json(buddy="market", instance_id=market_instance_id)
        before_instance = json.loads(market_instance.read_text(encoding="utf-8"))

        market_context = self._prepare(
            buddy="market",
            instance_id=market_instance_id,
            instance_json=market_instance,
            text=MARKET_REQUEST,
        )
        self.assertIn("decision_surface", market_context["runtime_context"])
        summary = self._dispatch(
            method="env.tool",
            payload={"tool": "context", "action": "summarize", "args": {}},
            instance_json=market_instance,
            instance_id=market_instance_id,
            buddy="market",
        )
        self.assertTrue(summary.get("ok"), msg=summary)
        self.assertIn("candidate_tracks", summary)
        candidate_ids = {row["track_id"] for row in summary["candidate_tracks"]}
        self.assertIn(track_id, candidate_ids)

        after_instance = json.loads(market_instance.read_text(encoding="utf-8"))
        self.assertEqual(after_instance, before_instance)
        summary_text = json.dumps(summary, ensure_ascii=True).lower()
        self.assertNotIn("handoff" + "_inbox", summary_text)
        self.assertNotIn("recommended_" + "route", summary_text)
        self.assertNotIn("auto_" + "bind", summary_text)

    def test_bound_market_sees_pm_prd_handoff_track_relation_evidence_and_design_handoff_constraints(self) -> None:
        track_id, _ = self._seed_pm_handoff()
        market_task_id = "task-market-host-ds-bound"
        env_store.create_task(
            market_task_id,
            "Market Host Decision Surface Bound Task",
            buddy="market",
            track_id=track_id,
            status="active",
            summary="Bound market task for host decision surface tests.",
            initial_run_id=None,
        )
        market_instance_id = "inst-market-bound-host-ds"
        market_instance = self._instance_json(
            buddy="market",
            instance_id=market_instance_id,
            current_task_id=market_task_id,
            current_track_id=track_id,
        )
        market_context = self._prepare(
            buddy="market",
            instance_id=market_instance_id,
            instance_json=market_instance,
            text="Continue PM handoff with bound market task and track.",
        )
        decision_surface = market_context["runtime_context"]["decision_surface"]
        self.assertEqual(decision_surface["binding_state"]["state"], "bound_task_and_track")
        self.assertEqual(decision_surface["active_buddy_relation"]["track_role"], "next_buddy")
        self.assertTrue(decision_surface["active_buddy_relation"]["latest_handoff_to_active_buddy"])
        self.assertEqual(decision_surface["evidence_readiness"]["market_research_evidence"], "required")

        summarized_artifacts = market_context["runtime_context"]["current_context_summary"]["artifacts"]
        prd_summary = next(row for row in summarized_artifacts if row.get("kind") == "prd")
        self.assertNotIn("problem", json.dumps(prd_summary, ensure_ascii=True))
        self.assertIn("design", market_context["runtime_context"]["capability_boundary"]["handoff_targets"])

    def test_full_buddy_loop_uses_decision_surface_and_persists_market_scan_to_design_handoff(self) -> None:
        track_id, _ = self._seed_pm_handoff()
        market_task_id = "task-market-host-ds-loop"
        env_store.create_task(
            market_task_id,
            "Market Host Decision Surface Loop Task",
            buddy="market",
            track_id=track_id,
            status="active",
            summary="Market loop task.",
            initial_run_id=None,
        )
        market_instance_id = "inst-market-loop-host-ds"
        market_instance = self._instance_json(
            buddy="market",
            instance_id=market_instance_id,
            current_task_id=market_task_id,
            current_track_id=track_id,
        )
        market_context = self._prepare(
            buddy="market",
            instance_id=market_instance_id,
            instance_json=market_instance,
            text="Produce market scan and handoff to Design.",
        )
        self.assertIn("decision_surface", market_context["runtime_context"])

        downgrade_issue = self._dispatch(
            method="env.tool",
            payload={
                "tool": "evidence",
                "action": "approve_downgrade",
                "args": {
                    "context": market_context,
                    "reason": "User explicitly approved a non-browser fallback for this run.",
                },
            },
            instance_json=market_instance,
            instance_id=market_instance_id,
            buddy="market",
        )
        self.assertTrue(downgrade_issue.get("ok"), msg=downgrade_issue)
        market_persisted = self._persist(
            buddy="market",
            instance_id=market_instance_id,
            instance_json=market_instance,
            context=market_context,
            result=_market_commit(downgrade_issue["tool_evidence"]["approved_downgrade_token"]),
        )
        market_receipt = market_persisted["receipt"]
        self.assertEqual(market_receipt["track_id"], track_id)
        self.assertEqual(market_receipt["handoff"]["next_buddy"], "design")

        design_task_id = "task-design-host-ds-loop"
        env_store.create_task(
            design_task_id,
            "Design Host Decision Surface Loop Task",
            buddy="design",
            track_id=track_id,
            status="active",
            summary="Design continuation task.",
            initial_run_id=None,
        )
        design_instance_id = "inst-design-loop-host-ds"
        design_instance = self._instance_json(
            buddy="design",
            instance_id=design_instance_id,
            current_task_id=design_task_id,
            current_track_id=track_id,
        )
        design_context = self._prepare(
            buddy="design",
            instance_id=design_instance_id,
            instance_json=design_instance,
            text=DESIGN_REQUEST,
        )
        self.assertIn("decision_surface", design_context["runtime_context"])
        handoffs = design_context["runtime_context"]["current_context_summary"]["recent_handoffs"]
        self.assertTrue(any(row.get("next_buddy") == "design" for row in handoffs))


if __name__ == "__main__":
    unittest.main()
