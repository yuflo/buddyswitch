#!/usr/bin/env python3
"""Functional coverage for prepare.runtime_context contract."""

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

import env_manifest  # noqa: E402
import env_profiles  # noqa: E402
import turn_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"

PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"
MARKET_REQUEST = "调研 AI 日程工具 landing page 竞品表达和定位方式"
DESIGN_REQUEST = "基于现有 PRD 和市场简报，整理 landing page 原型方向"
DEV_REQUEST = "实现 landing page hero 文案和 CTA 调整"
TEST_REQUEST = "验证 landing page hero 和 CTA 行为"

REQUESTS_BY_BUDDY = {
    "market": MARKET_REQUEST,
    "pm": PM_REQUEST,
    "design": DESIGN_REQUEST,
    "dev": DEV_REQUEST,
    "test": TEST_REQUEST,
}


def _pm_commit_with_track_and_handoff() -> dict[str, object]:
    return {
        "execution_summary": "PM wrote PRD, created track, and handed off to Market.",
        "working_notes": [
            "User asked for PRD creation and track binding in one PM turn.",
        ],
        "artifacts": [
            {
                "kind": "prd",
                "title": "AI Schedule Tool Landing Page PRD",
                "summary": "Defines MVP page scope, positioning hooks, and acceptance criteria.",
                "content": {
                    "problem": "Busy professionals need less scheduling back-and-forth.",
                    "requirements": [
                        "Hero explains the concrete value quickly.",
                        "CTA drives user to start a scheduling flow.",
                    ],
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
                "summary": "Cross-buddy landing page iteration for AI scheduling.",
            },
            "task": {
                "status": "done",
                "summary": "PM PRD is ready for market positioning research.",
            },
        },
        "handoff": {
            "next_buddy": "market",
            "reason": "Market should validate competitor positioning before design.",
            "context": "Use the PRD artifact plus track summary as source context.",
        },
        "contributors": {
            "skills": ["write-prd", "track-manager"],
            "agents": [],
        },
    }


class PrepareRuntimeContextTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _session(self, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "instance_id": "instance-test",
            "active_buddy": buddy,
            "payload": payload or {},
        }

    def _prepare(
        self,
        *,
        buddy: str,
        request_text: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with patch.object(
            turn_runtime,
            "_load_product_mode_session",
            return_value=self._session(buddy=buddy, payload=payload),
        ):
            prepared = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)
        self.assertTrue(prepared["ok"], msg=prepared)
        return prepared

    def _buddies_by_id(self) -> dict[str, dict[str, object]]:
        manifest = env_manifest.load_manifest(MANIFEST)
        return env_manifest.buddies_by_id(manifest)

    def _manifest_buddy_order(self) -> list[str]:
        manifest = env_manifest.load_manifest(MANIFEST)
        rows = manifest.get("buddies", [])
        ordered: list[str] = []
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                ordered.append(row["id"])
        return ordered

    def test_prepare_returns_runtime_context_for_each_buddy(self) -> None:
        buddy_order = self._manifest_buddy_order()
        for index, buddy in enumerate(buddy_order):
            switch_target = buddy_order[(index + 1) % len(buddy_order)]
            request_text = f"switch {switch_target}: {REQUESTS_BY_BUDDY[buddy]}"
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=request_text)
                self.assertEqual(payload["active_buddy"], buddy)
                self.assertEqual(payload["request_text"], request_text)

                runtime_context = payload["runtime_context"]
                self.assertIsInstance(runtime_context, dict)
                for key in (
                    "active_buddy",
                    "active_skill_ids",
                    "capability_boundary",
                    "tool_requirements",
                    "persist_payload_hint",
                    "current_context_summary",
                ):
                    self.assertIn(key, runtime_context)

                active_buddy = runtime_context["active_buddy"]
                self.assertIsInstance(active_buddy, dict)
                self.assertEqual(active_buddy["id"], buddy)

                self.assertEqual(payload["run_envelope"]["turn_identity"]["active_buddy"], buddy)

                forbidden_router_fields = (
                    "recommended_switch",
                    "selected_skill",
                    "selected_skill_packet",
                )
                for field in forbidden_router_fields:
                    self.assertNotIn(field, payload)

    def test_prepare_runtime_context_capability_boundary_matches_manifest_and_profiles(self) -> None:
        buddy_order = self._manifest_buddy_order()
        buddies = self._buddies_by_id()

        for buddy in buddy_order:
            with self.subTest(buddy=buddy):
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                runtime_context = payload["runtime_context"]

                self.assertEqual(runtime_context["active_skill_ids"], buddies[buddy]["skills"])

                boundary = runtime_context["capability_boundary"]
                self.assertEqual(boundary["allowed_artifact_kinds"], buddies[buddy]["artifact_kinds"])
                self.assertEqual(boundary["allowed_state_effects"]["task"], ["status", "summary"])

                expected_track_effects = ["create", "update", "advance", "archive"] if buddy == "pm" else []
                self.assertEqual(boundary["allowed_state_effects"]["track"], expected_track_effects)
                self.assertEqual(boundary["handoff_targets"], buddy_order)

    def test_prepare_exposes_project_scratch_and_raw_state_boundaries(self) -> None:
        required_raw_paths = {
            "buddyswitch/objects/tracks/*.json",
            "buddyswitch/objects/tasks/*.json",
            "buddyswitch/objects/artifacts/*.json",
            "buddyswitch/content/runs/*.json",
        }

        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                profile = env_profiles.require_env_profile(buddy, manifest_path=MANIFEST, repo_root=ROOT)
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                boundary = payload["runtime_context"]["capability_boundary"]

                project = boundary["project"]
                self.assertEqual(project["path"], "projects/app")
                self.assertEqual(project["access"], profile["project"]["access"])
                write_rule = str(project.get("write_rule", ""))
                if buddy == "dev":
                    self.assertIn("write", write_rule.lower())
                else:
                    self.assertIn("dev", write_rule.lower())

                scratch = boundary["scratch"]
                self.assertEqual(scratch["root"], f"runs/raw/{buddy}")
                self.assertEqual(scratch["access"], "write")

                raw_state = boundary["raw_state"]
                self.assertEqual(raw_state["access"], "broker-only")
                self.assertTrue(required_raw_paths.issubset(set(raw_state["paths"])))

    def test_prepare_exposes_tool_requirements_and_persist_payload_hints(self) -> None:
        required_optional = {
            "working_notes",
            "artifacts",
            "state_effects",
            "handoff",
            "contributors",
            "tool_evidence",
        }

        for buddy in self._manifest_buddy_order():
            with self.subTest(buddy=buddy):
                profile = env_profiles.require_env_profile(buddy, manifest_path=MANIFEST, repo_root=ROOT)
                payload = self._prepare(buddy=buddy, request_text=REQUESTS_BY_BUDDY[buddy])
                runtime_context = payload["runtime_context"]

                tool_requirements = runtime_context["tool_requirements"]
                self.assertEqual(tool_requirements["browser_cockpit"], profile["tool_capability"]["browser_cockpit"])
                self.assertEqual(
                    tool_requirements["market_research_evidence"],
                    profile["tool_capability"]["market_research_evidence"],
                )
                self.assertEqual(
                    tool_requirements["ordinary_web_fallback"],
                    profile["tool_capability"]["ordinary_web_fallback"],
                )

                hint = runtime_context["persist_payload_hint"]
                self.assertIn("execution_summary", hint["required"])
                self.assertTrue(required_optional.issubset(set(hint["optional"])))
                durable_rule = str(hint["durable_signal_rule"]).lower()
                self.assertIn("artifacts", durable_rule)
                self.assertIn("state_effects", durable_rule)
                self.assertIn("handoff", durable_rule)
                self.assertEqual(
                    hint["artifact_kind_source"],
                    "runtime_context.capability_boundary.allowed_artifact_kinds",
                )
                self.assertEqual(
                    hint["state_effect_source"],
                    "runtime_context.capability_boundary.allowed_state_effects",
                )
                self.assertEqual(
                    hint["handoff_target_source"],
                    "runtime_context.capability_boundary.handoff_targets",
                )

                if buddy == "market":
                    tool_evidence_hint = hint["tool_evidence"]
                    self.assertIn("Market", tool_evidence_hint["required_when"])
                    self.assertEqual(
                        set(tool_evidence_hint["accepted_fields"]),
                        {"browser_cockpit_token", "approved_downgrade_token"},
                    )

    def test_market_prepare_summarizes_track_artifact_and_recent_handoff_after_pm_persist(self) -> None:
        pm_context = self._prepare(buddy="pm", request_text=PM_REQUEST)
        persisted = turn_runtime.persist_buddy_run(
            pm_context,
            result=_pm_commit_with_track_and_handoff(),
            manifest_path=MANIFEST,
        )
        self.assertTrue(persisted["ok"], msg=persisted)

        receipt = persisted["receipt"]
        market_context = self._prepare(
            buddy="market",
            request_text=MARKET_REQUEST,
            payload={
                "current_task_id": receipt["task_id"],
                "current_track_id": receipt["track_id"],
            },
        )

        runtime_context = market_context["runtime_context"]
        summary = runtime_context["current_context_summary"]

        self.assertEqual(summary["task"]["id"], receipt["task_id"])
        self.assertEqual(summary["track"]["id"], "track-ai-schedule-landing-page")

        artifacts = summary["artifacts"]
        self.assertIsInstance(artifacts, list)
        prd_artifact = None
        for artifact in artifacts:
            if artifact.get("id") == receipt["artifact_ids"][0]:
                prd_artifact = artifact
                break
        self.assertIsNotNone(prd_artifact)
        assert prd_artifact is not None
        self.assertEqual(prd_artifact["kind"], "prd")
        self.assertEqual(prd_artifact["buddy"], "pm")
        self.assertEqual(prd_artifact["task_id"], receipt["task_id"])
        self.assertNotIn("problem", json.dumps(prd_artifact, ensure_ascii=True))

        recent_handoffs = summary["recent_handoffs"]
        self.assertIsInstance(recent_handoffs, list)
        self.assertGreaterEqual(len(recent_handoffs), 1)
        handoff = recent_handoffs[0]
        self.assertEqual(handoff["run_id"], receipt["run_id"])
        self.assertEqual(handoff["next_buddy"], "market")
        self.assertIn("Market", handoff["reason"])
        self.assertIn("PRD", handoff["context"])


if __name__ == "__main__":
    unittest.main()
