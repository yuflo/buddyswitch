#!/usr/bin/env python3
"""Tests for Market browser evidence issuance and persist gate."""

from __future__ import annotations

import json
import socket
import threading
import sys
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_profiles  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
MARKET_REQUEST = "调研 AI 日程工具 landing page 竞品表达和定位方式"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"
DESIGN_REQUEST = "基于现有 PRD 和市场简报，整理 landing page 原型方向"
DEV_REQUEST = "实现 landing page hero 文案和 CTA 调整"
TEST_REQUEST = "验证 landing page hero 和 CTA 行为"


def _market_commit(tool_evidence: dict[str, str] | None = None) -> dict[str, object]:
    commit: dict[str, object] = {
        "execution_summary": "Market analyzed competitor landing pages and proposed positioning.",
        "working_notes": ["Market run for AI schedule tool landing page."],
        "artifacts": [
            {
                "kind": "market-scan",
                "title": "AI Schedule Tool Landing Page Market Brief",
                "summary": "Summarizes competitor messaging and recommended angle.",
                "content": {
                    "research_question": "How should an AI schedule tool present itself?",
                    "evidence": [{"source": "browser-cockpit-preflight", "claim": "preflight passed"}],
                    "insights": ["Concrete workflow language is stronger than generic automation claims."],
                    "assumptions": [],
                    "risks": [],
                    "conclusion": "Lead with reduced scheduling back-and-forth.",
                    "recommended_next_step": "Design should shape a concrete before/after hero flow.",
                },
            }
        ],
        "handoff": {
            "next_buddy": "design",
            "reason": "Design should convert positioning into page flow.",
            "context": "Use PM PRD and this market brief.",
        },
        "contributors": {"skills": ["research-scan"], "agents": []},
    }
    if tool_evidence is not None:
        commit["tool_evidence"] = tool_evidence
    return commit


def _pm_commit() -> dict[str, object]:
    return {
        "execution_summary": "PM created PRD.",
        "artifacts": [
            {
                "kind": "prd",
                "title": "PRD",
                "summary": "prd",
                "content": {"problem": "x"},
            }
        ],
    }


def _design_commit() -> dict[str, object]:
    return {
        "execution_summary": "Design prepared the landing page handoff.",
        "artifacts": [
            {
                "kind": "design-handoff",
                "title": "Landing Page Design Handoff",
                "summary": "Defines hero and CTA direction.",
                "content": {
                    "design_goal": "Make AI scheduling value concrete in hero copy.",
                    "sections": ["hero", "proof", "cta"],
                },
            }
        ],
    }


def _dev_commit() -> dict[str, object]:
    return {
        "execution_summary": "Dev implemented landing page copy updates.",
        "artifacts": [
            {
                "kind": "implementation-report",
                "title": "Landing Page Implementation Report",
                "summary": "Records source changes for hero and CTA copy.",
                "content": {
                    "implementation_notes": ["Updated hero copy and CTA wording."],
                    "changed_files": ["projects/app/src/landing-page.md"],
                },
            }
        ],
    }


def _test_commit() -> dict[str, object]:
    return {
        "execution_summary": "Test validated landing page hero and CTA behavior.",
        "artifacts": [
            {
                "kind": "test-report",
                "title": "Landing Page Smoke Test Report",
                "summary": "Reports smoke checks for hero and CTA.",
                "content": {
                    "test_scope": ["hero", "cta"],
                    "checks_run": ["manual smoke"],
                    "passed_items": ["hero renders", "cta is clickable"],
                    "failed_items": [],
                    "blocked_items": [],
                },
            }
        ],
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


class MarketBrowserEvidenceTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        buddy: str = "market",
        browser_port: int | None = None,
        instance_id: str = "inst-market-example",
    ) -> Path:
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
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
        request: dict[str, object],
        instance_json: Path,
    ) -> dict[str, object]:
        return runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _prepare_market(self, *, instance_json: Path, instance_id: str = "inst-market-example") -> dict[str, object]:
        response = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": instance_id,
                "active_buddy": "market",
                "method": "prepare",
                "payload": {"text": MARKET_REQUEST},
            },
            instance_json=instance_json,
        )
        self.assertTrue(response["ok"], msg=response)
        return response["payload"]

    def _evidence_token_paths(self, instance_json: Path) -> list[Path]:
        root = instance_json.parent / "runtime" / "evidence-tokens"
        return sorted(root.glob("*/*.json")) if root.exists() else []

    def _state_snapshot(self) -> dict[str, list[str]]:
        return {
            "tracks": sorted(path.name for path in self._runtime_path("buddyswitch/objects/tracks").glob("*.json")),
            "tasks": sorted(path.name for path in self._runtime_path("buddyswitch/objects/tasks").glob("*.json")),
            "artifacts": sorted(path.name for path in self._runtime_path("buddyswitch/objects/artifacts").glob("*.json")),
            "runs": sorted(path.name for path in self._runtime_path("buddyswitch/content/runs").glob("*.json")),
        }

    def test_market_profile_requires_browser_evidence(self) -> None:
        profile = env_profiles.require_env_profile("market", manifest_path=MANIFEST, repo_root=ROOT)
        self.assertEqual(profile["tool_capability"]["browser_cockpit"], "required")
        self.assertEqual(profile["tool_capability"]["market_research_evidence"], "required")

    def test_market_persist_without_evidence_rejects_before_writes(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        before_runs = list(self._runtime_path("buddyswitch/content/runs").glob("*.json"))
        response = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "payload": {"context": context, "result": _market_commit()},
            },
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertIn("tool_evidence", response["error"]["message"])
        after_runs = list(self._runtime_path("buddyswitch/content/runs").glob("*.json"))
        self.assertEqual(after_runs, before_runs)

    def test_browser_evidence_issue_requires_market_profile(self) -> None:
        instance_json = self._instance_json(buddy="pm", instance_id="inst-pm-example")
        prepared = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-pm-example",
                "active_buddy": "pm",
                "method": "prepare",
                "payload": {"text": PM_REQUEST},
            },
            instance_json=instance_json,
        )
        self.assertTrue(prepared["ok"], msg=prepared)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-pm-example",
                "active_buddy": "pm",
                "method": "issue_browser_evidence",
                "payload": {
                    "context": prepared["payload"],
                    "mode": "browser-cockpit-preflight",
                    "reason": None,
                },
            },
            instance_json=instance_json,
        )
        self.assertFalse(issue["ok"])
        self.assertIn("does not require browser cockpit evidence", issue["error"]["message"])
        self.assertEqual(self._evidence_token_paths(instance_json), [])

    def test_browser_preflight_requires_current_run_envelope(self) -> None:
        instance_json = self._instance_json(browser_port=9)
        context = self._prepare_market(instance_json=instance_json)
        context.pop("run_envelope", None)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "issue_browser_evidence",
                "payload": {"context": context, "mode": "browser-cockpit-preflight", "reason": None},
            },
            instance_json=instance_json,
        )
        self.assertFalse(issue["ok"])
        self.assertIn("run_envelope", issue["error"]["message"])
        self.assertEqual(self._evidence_token_paths(instance_json), [])

    def test_browser_preflight_requires_reachable_endpoint(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        instance_json = self._instance_json(browser_port=port)
        context = self._prepare_market(instance_json=instance_json)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "issue_browser_evidence",
                "payload": {"context": context, "mode": "browser-cockpit-preflight", "reason": None},
            },
            instance_json=instance_json,
        )
        self.assertFalse(issue["ok"])
        self.assertIn("browser cockpit endpoint is unreachable", issue["error"]["message"])
        self.assertEqual(self._evidence_token_paths(instance_json), [])

    def test_market_persist_with_browser_token_succeeds_and_records_audit(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = HTTPServer(("127.0.0.1", port), _VersionHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        instance_json = self._instance_json(browser_port=port)
        context = self._prepare_market(instance_json=instance_json)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "issue_browser_evidence",
                "payload": {"context": context, "mode": "browser-cockpit-preflight", "reason": None},
            },
            instance_json=instance_json,
        )
        self.assertTrue(issue["ok"], msg=issue)
        token = issue["payload"]["tool_evidence"]["browser_cockpit_token"]

        persisted = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "payload": {
                    "context": context,
                    "result": _market_commit({"browser_cockpit_token": token}),
                },
            },
            instance_json=instance_json,
        )
        self.assertTrue(persisted["ok"], msg=persisted)
        run_id = persisted["payload"]["receipt"]["run_id"]
        run_payload = json.loads(
            self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(run_payload["tool_evidence"]["kind"], "browser-cockpit-preflight")
        self.assertEqual(run_payload["tool_evidence"]["token"], token)

    def test_market_persist_with_token_for_other_run_rejects(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = HTTPServer(("127.0.0.1", port), _VersionHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        instance_json = self._instance_json(browser_port=port)
        context_a = self._prepare_market(instance_json=instance_json)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "issue_browser_evidence",
                "payload": {"context": context_a, "mode": "browser-cockpit-preflight", "reason": None},
            },
            instance_json=instance_json,
        )
        token = issue["payload"]["tool_evidence"]["browser_cockpit_token"]
        consumed_a = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "payload": {
                    "context": context_a,
                    "result": {
                        "execution_summary": "Market consumed the first run before preparing another context.",
                        "handoff": {
                            "next_buddy": "design",
                            "reason": "Design can continue after the first market run.",
                            "context": "Use the next market artifact when it is available.",
                        },
                    },
                },
            },
            instance_json=instance_json,
        )
        self.assertTrue(consumed_a["ok"], msg=consumed_a)
        context_b = self._prepare_market(instance_json=instance_json)
        before_rejected = self._state_snapshot()
        rejected = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "payload": {
                    "context": context_b,
                    "result": _market_commit({"browser_cockpit_token": token}),
                },
            },
            instance_json=instance_json,
        )
        self.assertFalse(rejected["ok"])
        self.assertIn("not issued by runtime broker", rejected["error"]["message"])
        self.assertEqual(self._state_snapshot(), before_rejected)

    def test_market_persist_with_handwritten_token_rejects_before_writes(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        before = self._state_snapshot()
        rejected = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "payload": {
                    "context": context,
                    "result": _market_commit({"browser_cockpit_token": "evidence-run-fake-handwritten"}),
                },
            },
            instance_json=instance_json,
        )
        self.assertFalse(rejected["ok"])
        self.assertIn("not issued by runtime broker", rejected["error"]["message"])
        self.assertEqual(self._state_snapshot(), before)

    def test_approved_downgrade_token_requires_reason(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "issue_browser_evidence",
                "payload": {"context": context, "mode": "approved-downgrade", "reason": " "},
            },
            instance_json=instance_json,
        )
        self.assertFalse(issue["ok"])
        self.assertIn("approved downgrade requires a non-empty reason", issue["error"]["message"])
        self.assertEqual(self._evidence_token_paths(instance_json), [])

    def test_market_persist_with_approved_downgrade_token_records_reason(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "issue_browser_evidence",
                "payload": {
                    "context": context,
                    "mode": "approved-downgrade",
                    "reason": "Browser-native cockpit blocked; user approved one-off downgrade.",
                },
            },
            instance_json=instance_json,
        )
        self.assertTrue(issue["ok"], msg=issue)
        token = issue["payload"]["tool_evidence"]["approved_downgrade_token"]
        persisted = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "payload": {
                    "context": context,
                    "result": _market_commit({"approved_downgrade_token": token}),
                },
            },
            instance_json=instance_json,
        )
        self.assertTrue(persisted["ok"], msg=persisted)
        run_id = persisted["payload"]["receipt"]["run_id"]
        run_payload = json.loads(
            self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(run_payload["tool_evidence"]["kind"], "approved-downgrade")
        self.assertIn("reason", run_payload["tool_evidence"])

    def test_pm_persist_does_not_require_tool_evidence(self) -> None:
        instance_json = self._instance_json(buddy="pm", instance_id="inst-pm-example")
        prepared = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-pm-example",
                "active_buddy": "pm",
                "method": "prepare",
                "payload": {"text": PM_REQUEST},
            },
            instance_json=instance_json,
        )
        self.assertTrue(prepared["ok"], msg=prepared)
        persisted = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v1",
                "instance_id": "inst-pm-example",
                "active_buddy": "pm",
                "method": "persist",
                "payload": {"context": prepared["payload"], "result": _pm_commit()},
            },
            instance_json=instance_json,
        )
        self.assertTrue(persisted["ok"], msg=persisted)

    def test_non_market_buddies_can_persist_without_tool_evidence(self) -> None:
        matrix = (
            ("pm", "inst-pm-example", PM_REQUEST, _pm_commit),
            ("design", "inst-design-example", DESIGN_REQUEST, _design_commit),
            ("dev", "inst-dev-example", DEV_REQUEST, _dev_commit),
            ("test", "inst-test-example", TEST_REQUEST, _test_commit),
        )
        for buddy, instance_id, request_text, commit_factory in matrix:
            with self.subTest(buddy=buddy):
                instance_json = self._instance_json(buddy=buddy, instance_id=instance_id)
                prepared = self._dispatch(
                    request={
                        "protocol": "buddyswitch-runtime-broker/v1",
                        "instance_id": instance_id,
                        "active_buddy": buddy,
                        "method": "prepare",
                        "payload": {"text": request_text},
                    },
                    instance_json=instance_json,
                )
                self.assertTrue(prepared["ok"], msg=prepared)
                persisted = self._dispatch(
                    request={
                        "protocol": "buddyswitch-runtime-broker/v1",
                        "instance_id": instance_id,
                        "active_buddy": buddy,
                        "method": "persist",
                        "payload": {"context": prepared["payload"], "result": commit_factory()},
                    },
                    instance_json=instance_json,
                )
                self.assertTrue(persisted["ok"], msg=persisted)


if __name__ == "__main__":
    unittest.main()
