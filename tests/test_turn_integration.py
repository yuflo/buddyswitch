#!/usr/bin/env python3
"""Integration flows for buddy-run persistence collaboration."""

from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
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
            "kind": "market-scan",
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


DESIGN_COMMIT = {
    "execution_summary": "Design shaped the landing page handoff for Dev.",
    "working_notes": ["Design used the PM PRD and Market positioning brief."],
    "artifacts": [
        {
            "kind": "design-handoff",
            "title": "AI Schedule Tool Landing Page Design Handoff",
            "summary": "Defines the hero flow, page structure, and interaction direction for implementation.",
            "content": {
                "design_goal": "Make recovered focus time concrete in the first viewport.",
                "sections": ["hero", "workflow proof", "trust cues", "CTA"],
                "handoff_notes": ["Dev should implement a simple static landing page first."],
            },
        }
    ],
    "handoff": {
        "next_buddy": "dev",
        "reason": "Dev can implement the approved landing page structure.",
        "context": "Use the PRD, market brief, and design handoff.",
    },
    "contributors": {
        "skills": ["shape-prototype"],
        "agents": [],
    },
}

DEV_COMMIT = {
    "execution_summary": "Dev implemented the landing page source marker and recorded implementation notes.",
    "working_notes": ["Dev changed project source as the only source-writing buddy in this smoke."],
    "artifacts": [
        {
            "kind": "implementation-report",
            "title": "AI Schedule Tool Landing Page Implementation Report",
            "summary": "Reports the source implementation completed for smoke coverage.",
            "content": {
                "implementation_notes": ["Created a Dev-owned source marker."],
                "changed_files": ["projects/app/dev-smoke.txt"],
            },
        }
    ],
    "handoff": {
        "next_buddy": "test",
        "reason": "Test can validate the implemented landing page behavior.",
        "context": "Use the implementation report and project source marker.",
    },
    "contributors": {
        "skills": ["implement-task"],
        "agents": [],
    },
}

TEST_COMMIT = {
    "execution_summary": "Test ran landing page smoke checks and reported readiness without editing source.",
    "working_notes": ["Test inspected behavior and wrote report state only."],
    "artifacts": [
        {
            "kind": "test-report",
            "title": "Landing Page Smoke Test Report",
            "summary": "Reports pass/fail results for landing page hero and CTA behavior.",
            "content": {
                "test_scope": ["landing page hero", "CTA click behavior"],
                "checks_run": ["manual DOM smoke", "static asset load check"],
                "passed_items": ["hero renders", "source marker exists"],
                "failed_items": [],
                "blocked_items": [],
                "reproduction_notes": [],
                "readiness": "ready-for-pm-review",
            },
        }
    ],
    "handoff": {
        "next_buddy": "pm",
        "reason": "PM can review readiness.",
        "context": "Use the smoke test report artifact.",
    },
    "contributors": {
        "skills": ["smoke-test"],
        "agents": [],
    },
}


class _VersionHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/json/version":
            body = b'{"Browser":"test"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        return


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

    def _instance_json(
        self,
        *,
        buddy: str,
        instance_id: str,
        current_track_id: str | None = None,
        browser_port: int | None = None,
    ) -> Path:
        path = self._runtime_path(f"instances/{instance_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": current_track_id,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": browser_port,
                    "created_at": "2026-05-06T00:00:00Z",
                    "updated_at": "2026-05-06T00:00:00Z",
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
        buddy: str,
        method: str,
        payload: dict[str, object],
        instance_json: Path,
        instance_id: str,
    ) -> dict[str, object]:
        return runtime_broker.dispatch_runtime_request(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": method,
                "payload": payload,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _broker_prepare(
        self,
        *,
        buddy: str,
        text: str,
        instance_json: Path,
        instance_id: str,
    ) -> dict[str, object]:
        response = self._dispatch(
            buddy=buddy,
            method="prepare",
            payload={"text": text},
            instance_json=instance_json,
            instance_id=instance_id,
        )
        self.assertTrue(response["ok"], msg=response)
        return response["payload"]

    def _broker_persist(
        self,
        *,
        buddy: str,
        context: dict[str, object],
        result: dict[str, object],
        instance_json: Path,
        instance_id: str,
    ) -> dict[str, object]:
        response = self._dispatch(
            buddy=buddy,
            method="persist",
            payload={"context": context, "result": result},
            instance_json=instance_json,
            instance_id=instance_id,
        )
        self.assertTrue(response["ok"], msg=response)
        return response["payload"]

    def _issue_market_browser_evidence(
        self,
        *,
        context: dict[str, object],
        instance_json: Path,
        instance_id: str,
    ) -> dict[str, str]:
        response = self._dispatch(
            buddy="market",
            method="issue_browser_evidence",
            payload={"context": context, "mode": "browser-cockpit-preflight", "reason": None},
            instance_json=instance_json,
            instance_id=instance_id,
        )
        self.assertTrue(response["ok"], msg=response)
        payload = response["payload"]
        self.assertIsInstance(payload, dict)
        tool_evidence = payload["tool_evidence"]
        self.assertIsInstance(tool_evidence, dict)
        return tool_evidence

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
        self.assertIn("market-scan", kinds)

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
        self.assertIn("market-scan", source_kinds)

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

    def test_cross_buddy_flow_smoke_persists_pm_market_design_dev_and_test(self) -> None:
        pm_instance_id = "inst-pm-flow"
        pm_instance = self._instance_json(buddy="pm", instance_id=pm_instance_id)
        pm_context = self._broker_prepare(
            buddy="pm",
            text=PM_REQUEST,
            instance_json=pm_instance,
            instance_id=pm_instance_id,
        )
        pm_persisted = self._broker_persist(
            buddy="pm",
            context=pm_context,
            result=PM_COMMIT,
            instance_json=pm_instance,
            instance_id=pm_instance_id,
        )
        track_id = pm_persisted["receipt"]["track_id"]

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            browser_port = sock.getsockname()[1]
        server = HTTPServer(("127.0.0.1", browser_port), _VersionHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)

        market_instance_id = "inst-market-flow"
        market_instance = self._instance_json(
            buddy="market",
            instance_id=market_instance_id,
            current_track_id=track_id,
            browser_port=browser_port,
        )
        market_context = self._broker_prepare(
            buddy="market",
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        market_result = json.loads(json.dumps(MARKET_COMMIT))
        market_result["tool_evidence"] = self._issue_market_browser_evidence(
            context=market_context,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        market_persisted = self._broker_persist(
            buddy="market",
            context=market_context,
            result=market_result,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )

        design_instance_id = "inst-design-flow"
        design_instance = self._instance_json(buddy="design", instance_id=design_instance_id, current_track_id=track_id)
        design_context = self._broker_prepare(
            buddy="design",
            text="根据已有 track 继续设计 landing page",
            instance_json=design_instance,
            instance_id=design_instance_id,
        )
        design_persisted = self._broker_persist(
            buddy="design",
            context=design_context,
            result=DESIGN_COMMIT,
            instance_json=design_instance,
            instance_id=design_instance_id,
        )

        project_source = self._runtime_path("projects/app/dev-smoke.txt")
        project_source.parent.mkdir(parents=True, exist_ok=True)
        project_source.write_text("dev-only-change\n", encoding="utf-8")

        dev_instance_id = "inst-dev-flow"
        dev_instance = self._instance_json(buddy="dev", instance_id=dev_instance_id, current_track_id=track_id)
        dev_context = self._broker_prepare(
            buddy="dev",
            text="实现 landing page source marker",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
        )
        dev_persisted = self._broker_persist(
            buddy="dev",
            context=dev_context,
            result=DEV_COMMIT,
            instance_json=dev_instance,
            instance_id=dev_instance_id,
        )

        test_instance_id = "inst-test-flow"
        test_instance = self._instance_json(buddy="test", instance_id=test_instance_id, current_track_id=track_id)
        test_context = self._broker_prepare(
            buddy="test",
            text="验证 landing page smoke behavior",
            instance_json=test_instance,
            instance_id=test_instance_id,
        )
        test_persisted = self._broker_persist(
            buddy="test",
            context=test_context,
            result=TEST_COMMIT,
            instance_json=test_instance,
            instance_id=test_instance_id,
        )

        index = env_store.build_track_artifact_index(track_id)
        self.assertIsNotNone(index)
        assert index is not None
        kinds = {
            artifact["kind"]
            for task in index["tasks"]
            for artifact in task["artifacts"]
            if artifact.get("is_current")
        }
        self.assertEqual(
            {"prd", "market-scan", "design-handoff", "implementation-report", "test-report"},
            kinds,
        )

        receipts = [
            ("pm", pm_persisted["receipt"]),
            ("market", market_persisted["receipt"]),
            ("design", design_persisted["receipt"]),
            ("dev", dev_persisted["receipt"]),
            ("test", test_persisted["receipt"]),
        ]
        for buddy, receipt in receipts:
            run = json.loads(
                self._runtime_path(f"buddyswitch/content/runs/{receipt['run_id']}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(run["buddy_id"], buddy)
            if buddy == "market":
                self.assertEqual(run["tool_evidence"]["kind"], "browser-cockpit-preflight")

        self.assertEqual(project_source.read_text(encoding="utf-8"), "dev-only-change\n")


if __name__ == "__main__":
    unittest.main()
