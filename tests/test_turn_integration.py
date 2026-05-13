#!/usr/bin/env python3
"""Integration flows for buddy-run persistence collaboration."""

from __future__ import annotations

import hashlib
import json
import socket
import sys
import threading
import unittest
import uuid
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
    "handoff": {
        "next_buddy": "market",
        "reason": "Market should validate competitor landing page positioning before design.",
        "context": "Use the PRD artifact and track summary as source context.",
    },
    "contributors": {
        "skills": ["write-prd", "track-tool"],
        "agents": [],
    },
}

PM_ARTIFACTS = [
    {
        "kind": "prd",
        "title": "AI Schedule Tool Landing Page PRD",
        "summary": "Defines landing page scope, sections, MVP requirements, and acceptance criteria.",
        "content": {
            "problem": "Busy professionals need an AI-assisted way to reduce scheduling overhead.",
            "target_users": ["calendar-heavy professionals", "small team operators"],
        },
    }
]

PM_TASK_UPDATE = {
    "status": "done",
    "summary": "PM PRD is ready for market positioning research.",
}

PM_TRACK_CREATE = {
    "track_id": "track-ai-schedule-landing-page",
    "title": "AI Schedule Tool Landing Page",
    "status": "active",
    "current_buddy": "pm",
    "next_buddy": "market",
    "summary": "Cross-buddy landing page iteration for an AI schedule tool.",
}

MARKET_COMMIT = {
    "execution_summary": "Market analyzed AI scheduling landing page competitors and recommended positioning angles.",
    "working_notes": ["The request referenced the existing PM-created track."],
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

MARKET_ARTIFACTS = [
    {
        "kind": "market-scan",
        "title": "AI Schedule Tool Landing Page Market Brief",
        "summary": "Summarizes competitor messaging patterns and recommended landing page expression.",
        "content": {
            "research_question": "How should an AI schedule tool express and present itself on a landing page?",
            "recommended_angles": ["recover focus time", "reduce back-and-forth scheduling"],
        },
    }
]


DESIGN_COMMIT = {
    "execution_summary": "Design shaped the landing page handoff for Dev.",
    "working_notes": ["Design used the PM PRD and Market positioning brief."],
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

DESIGN_ARTIFACTS = [
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
]

DEV_COMMIT = {
    "execution_summary": "Dev implemented the landing page source marker and recorded implementation notes.",
    "working_notes": ["Dev changed project source as the only source-writing buddy in this smoke."],
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

DEV_ARTIFACTS = [
    {
        "kind": "implementation-report",
        "title": "AI Schedule Tool Landing Page Implementation Report",
        "summary": "Reports the source implementation completed for smoke coverage.",
        "content": {
            "implementation_notes": ["Created a Dev-owned source marker."],
            "changed_files": ["projects/app/dev-smoke.txt"],
        },
    }
]

DEV_TASK_UPDATE = {
    "status": "done",
    "summary": "Dev implementation is ready for Test smoke validation.",
}

TEST_COMMIT = {
    "execution_summary": "Test ran landing page smoke checks and reported readiness without editing source.",
    "working_notes": ["Test inspected behavior and wrote report state only."],
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

TEST_ARTIFACTS = [
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
]

TEST_TASK_UPDATE = {
    "status": "done",
    "summary": "Test report completed and ready for PM review.",
}


class _CDPState:
    def __init__(
        self,
        *,
        version_ok: bool,
        pages: list[dict[str, object]] | None = None,
        allow_put_new_about_blank: bool = False,
        allow_get_new_about_blank: bool = False,
    ) -> None:
        self.version_ok = version_ok
        self.pages = list(pages or [])
        self.allow_put_new_about_blank = allow_put_new_about_blank
        self.allow_get_new_about_blank = allow_get_new_about_blank
        self.calls: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def record_call(self, *, method: str, path: str, query: str) -> None:
        with self._lock:
            self.calls.append({"method": method, "path": path, "query": query})

    def snapshot_calls(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self.calls)

    def has_usable_page(self) -> bool:
        for page in self.pages:
            if not isinstance(page, dict):
                continue
            if page.get("type") != "page":
                continue
            url = page.get("url")
            if not isinstance(url, str):
                continue
            normalized = url.strip().lower()
            if normalized == "about:blank":
                return True
            if not normalized.startswith("chrome://") and not normalized.startswith("chrome-untrusted://") and not normalized.startswith("devtools://"):
                return True
        return False


def _make_cdp_handler(state: _CDPState) -> type[BaseHTTPRequestHandler]:
    class _CDPHandler(BaseHTTPRequestHandler):
        def _handle(self, method: str) -> None:
            path = self.path
            query = ""
            if "?" in self.path:
                path, query = self.path.split("?", 1)
            state.record_call(method=method, path=path, query=query)

            if path == "/json/version":
                if state.version_ok:
                    body = b'{"Browser":"test"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(503)
                self.end_headers()
                return

            if path == "/json/list":
                body = json.dumps(state.pages, ensure_ascii=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/json/new" and query == "about:blank":
                if method == "PUT" and state.allow_put_new_about_blank:
                    if not state.has_usable_page():
                        state.pages.append({"id": "target-about-blank", "type": "page", "url": "about:blank"})
                    body = b'{"id":"target-about-blank"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if method == "GET" and state.allow_get_new_about_blank:
                    body = b'{"id":"target-about-blank"}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(405)
                self.end_headers()
                return

            self.send_response(404)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            self._handle("GET")

        def do_PUT(self) -> None:  # noqa: N802
            self._handle("PUT")

        def log_message(self, *_args: object) -> None:
            return

    return _CDPHandler


class TurnRuntimeIntegrationTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    @staticmethod
    def _result_hash(result: dict[str, object]) -> str:
        body = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(body).hexdigest()

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
        request: dict[str, object] = {
            "protocol": "buddyswitch-runtime-broker/v2",
            "request_id": f"req-turn-integration-{uuid.uuid4().hex}",
            "method": method,
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                **payload,
            },
            "deadline_ms": 35000,
        }
        if method == "persist":
            context = payload.get("context")
            result = payload.get("result")
            if isinstance(context, dict) and isinstance(result, dict):
                run_envelope = context.get("run_envelope")
                run_id = None
                if isinstance(run_envelope, dict):
                    run_id_raw = run_envelope.get("run_id")
                    if isinstance(run_id_raw, str) and run_id_raw:
                        run_id = run_id_raw
                    turn_identity = run_envelope.get("turn_identity")
                    if run_id is None and isinstance(turn_identity, dict):
                        turn_run_id = turn_identity.get("run_id")
                        if isinstance(turn_run_id, str) and turn_run_id:
                            run_id = turn_run_id
                if isinstance(run_id, str):
                    result_hash = self._result_hash(result)
                    request["idempotency_key"] = f"persist:{run_id}:{result_hash}"
                    request["result_hash"] = result_hash
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertEqual(envelope.get("protocol"), "buddyswitch-runtime-broker/v2")
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        response: dict[str, object] = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            response[key] = value
        return response

    def _env_tool(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        response = self._dispatch(
            buddy=buddy,
            method="env.tool",
            payload={"tool": tool, "action": action, "args": args},
            instance_json=instance_json,
            instance_id=instance_id,
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), tool)
        return response

    def _create_track(
        self,
        *,
        track_id: str,
        instance_json: Path,
        instance_id: str,
    ) -> None:
        payload = json.loads(json.dumps(PM_TRACK_CREATE))
        payload["track_id"] = track_id
        self._env_tool(
            buddy="pm",
            instance_json=instance_json,
            instance_id=instance_id,
            tool="track",
            action="create",
            args=payload,
        )

    def _create_tracked_task(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        task_id: str,
        track_id: str,
        title: str,
    ) -> None:
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="task",
            action="create",
            args={"task_id": task_id, "title": title, "summary": f"{buddy} task for integration flow."},
        )
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="track",
            action="attach_task",
            args={"track_id": track_id, "task_id": task_id},
        )
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="binding",
            action="set_task",
            args={"task_id": task_id},
        )

    def _update_task(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        task_id: str,
        patch: dict[str, object],
    ) -> None:
        args = {"task_id": task_id, **patch}
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="task",
            action="update",
            args=args,
        )

    def _create_artifacts(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        context: dict[str, object],
        task_id: str,
        artifact_specs: list[dict[str, object]],
    ) -> list[str]:
        run_envelope = context["run_envelope"]
        self.assertIsInstance(run_envelope, dict)
        assert isinstance(run_envelope, dict)
        source_run_id = run_envelope["run_id"]
        self.assertIsInstance(source_run_id, str)
        artifact_ids: list[str] = []
        for spec in artifact_specs:
            kind = spec["kind"]
            self.assertIsInstance(kind, str)
            artifact_id = f"art-{task_id}-{kind}-{source_run_id.replace('run-', '')[:8]}"
            created = self._env_tool(
                buddy=buddy,
                instance_json=instance_json,
                instance_id=instance_id,
                tool="artifact",
                action="create_revision",
                args={
                    "artifact_id": artifact_id,
                    "task_id": task_id,
                    "kind": kind,
                    "title": spec["title"],
                    "summary": spec["summary"],
                    "content": spec["content"],
                    "source_run_id": source_run_id,
                },
            )
            artifact = created.get("artifact")
            self.assertIsInstance(artifact, dict, msg=created)
            artifact_ids.append(str(created["artifact_id"]))
        return artifact_ids

    def _audit_result(
        self,
        base: dict[str, object],
        *,
        task_id: str,
        track_id: str,
        artifact_ids: list[str],
        tool_evidence: dict[str, object] | None = None,
    ) -> dict[str, object]:
        result = json.loads(json.dumps(base))
        result["task_id"] = task_id
        result["track_id"] = track_id
        result["artifact_ids"] = artifact_ids
        if tool_evidence is not None:
            result["tool_evidence"] = tool_evidence
        return result

    def _evidence_payload(self, *, context: dict[str, object]) -> dict[str, object]:
        return {"tool": "evidence", "action": "issue_browser", "args": {"context": context}}

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
        payload = response.get("payload") if isinstance(response.get("payload"), dict) else response
        self.assertIsInstance(payload, dict, msg=response)
        assert isinstance(payload, dict)
        return payload

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
        payload = response.get("payload") if isinstance(response.get("payload"), dict) else response
        self.assertIsInstance(payload, dict, msg=response)
        assert isinstance(payload, dict)
        return payload

    def _issue_market_browser_evidence(
        self,
        *,
        context: dict[str, object],
        instance_json: Path,
        instance_id: str,
    ) -> dict[str, str]:
        response = self._dispatch(
            buddy="market",
            method="env.tool",
            payload=self._evidence_payload(context=context),
            instance_json=instance_json,
            instance_id=instance_id,
        )
        self.assertTrue(response["ok"], msg=response)
        payload = response
        self.assertIsInstance(payload, dict)
        tool_evidence = payload["tool_evidence"]
        self.assertIsInstance(tool_evidence, dict)
        return tool_evidence

    def _approve_market_downgrade_evidence(
        self,
        *,
        context: dict[str, object],
        instance_json: Path,
        instance_id: str,
    ) -> dict[str, object]:
        response = self._env_tool(
            buddy="market",
            instance_json=instance_json,
            instance_id=instance_id,
            tool="evidence",
            action="approve_downgrade",
            args={
                "context": context,
                "reason": "Test fixture uses a non-browser fallback for this market integration path.",
            },
        )
        tool_evidence = response["tool_evidence"]
        self.assertIsInstance(tool_evidence, dict)
        return tool_evidence

    def _start_cdp_server(self, state: _CDPState) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = HTTPServer(("127.0.0.1", port), _make_cdp_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)
        return port

    def _evidence_token_paths(self, instance_json: Path) -> list[Path]:
        root = instance_json.parent / "runtime" / "evidence-tokens"
        return sorted(root.glob("*/*.json")) if root.exists() else []

    def test_market_browser_evidence_rejects_endpoint_only_cockpit_in_broker_flow(self) -> None:
        state = _CDPState(version_ok=True, pages=[], allow_put_new_about_blank=False, allow_get_new_about_blank=False)
        browser_port = self._start_cdp_server(state)

        market_instance_id = "inst-market-gate"
        market_instance = self._instance_json(buddy="market", instance_id=market_instance_id, browser_port=browser_port)
        market_context = self._broker_prepare(
            buddy="market",
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        issue = self._dispatch(
            buddy="market",
            method="env.tool",
            payload=self._evidence_payload(context=market_context),
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        self.assertFalse(issue["ok"])
        self.assertEqual(issue["permission_boundary"], "browser-cockpit-ready")
        self.assertEqual(issue["stop_condition"], "browser cockpit is not ready for MCP page operations")
        self.assertEqual(self._evidence_token_paths(market_instance), [])

    def test_market_browser_evidence_wrong_instance_fails_before_any_browser_cdp_call(self) -> None:
        state = _CDPState(
            version_ok=True,
            pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
            allow_put_new_about_blank=False,
            allow_get_new_about_blank=False,
        )
        browser_port = self._start_cdp_server(state)
        market_instance_id = "inst-market-gate"
        market_instance = self._instance_json(buddy="market", instance_id=market_instance_id, browser_port=browser_port)
        market_context = self._broker_prepare(
            buddy="market",
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        issue = self._dispatch(
            buddy="market",
            method="env.tool",
            payload=self._evidence_payload(context=market_context),
            instance_json=market_instance,
            instance_id="inst-other",
        )
        self.assertFalse(issue["ok"])
        self.assertEqual(issue["permission_boundary"], "active-instance")
        self.assertEqual(state.snapshot_calls(), [])
        self.assertEqual(self._evidence_token_paths(market_instance), [])

    def test_pm_to_market_collaboration_persists_on_one_track_without_skill_ids(self) -> None:
        track_id = "track-ai-schedule-landing-page"
        pm_task_id = "task-pm-ai-schedule-prd"
        pm_instance_id = "inst-pm-one-track"
        pm_instance = self._instance_json(buddy="pm", instance_id=pm_instance_id)
        pm_context = self._broker_prepare(
            buddy="pm",
            text=PM_REQUEST,
            instance_json=pm_instance,
            instance_id=pm_instance_id,
        )
        self._create_track(track_id=track_id, instance_json=pm_instance, instance_id=pm_instance_id)
        self._create_tracked_task(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            task_id=pm_task_id,
            track_id=track_id,
            title="PM PRD",
        )
        self._update_task(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            task_id=pm_task_id,
            patch=PM_TASK_UPDATE,
        )
        pm_artifact_ids = self._create_artifacts(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            context=pm_context,
            task_id=pm_task_id,
            artifact_specs=PM_ARTIFACTS,
        )
        pm_persisted = self._broker_persist(
            buddy="pm",
            context=pm_context,
            result=self._audit_result(PM_COMMIT, task_id=pm_task_id, track_id=track_id, artifact_ids=pm_artifact_ids),
            instance_json=pm_instance,
            instance_id=pm_instance_id,
        )
        pm_receipt = pm_persisted["receipt"]

        market_task_id = "task-market-ai-schedule-scan"
        market_instance_id = "inst-market-one-track"
        market_instance = self._instance_json(buddy="market", instance_id=market_instance_id, current_track_id=track_id)
        self._create_tracked_task(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            task_id=market_task_id,
            track_id=track_id,
            title="Market scan",
        )
        market_context = self._broker_prepare(
            buddy="market",
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        market_tool_evidence = self._approve_market_downgrade_evidence(
            context=market_context,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        market_artifact_ids = self._create_artifacts(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            context=market_context,
            task_id=market_task_id,
            artifact_specs=MARKET_ARTIFACTS,
        )
        market_persisted = self._broker_persist(
            buddy="market",
            context=market_context,
            result=self._audit_result(
                MARKET_COMMIT,
                task_id=market_task_id,
                track_id=track_id,
                artifact_ids=market_artifact_ids,
                tool_evidence=market_tool_evidence,
            ),
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
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
        track_id = "track-ai-schedule-design-context"
        pm_task_id = "task-pm-design-context-prd"
        pm_instance_id = "inst-pm-design-context"
        pm_instance = self._instance_json(buddy="pm", instance_id=pm_instance_id)
        pm_context = self._broker_prepare(
            buddy="pm",
            text=PM_REQUEST,
            instance_json=pm_instance,
            instance_id=pm_instance_id,
        )
        self._create_track(track_id=track_id, instance_json=pm_instance, instance_id=pm_instance_id)
        self._create_tracked_task(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            task_id=pm_task_id,
            track_id=track_id,
            title="PM PRD",
        )
        pm_artifact_ids = self._create_artifacts(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            context=pm_context,
            task_id=pm_task_id,
            artifact_specs=PM_ARTIFACTS,
        )
        self._broker_persist(
            buddy="pm",
            context=pm_context,
            result=self._audit_result(PM_COMMIT, task_id=pm_task_id, track_id=track_id, artifact_ids=pm_artifact_ids),
            instance_json=pm_instance,
            instance_id=pm_instance_id,
        )

        market_task_id = "task-market-design-context-scan"
        market_instance_id = "inst-market-design-context"
        market_instance = self._instance_json(buddy="market", instance_id=market_instance_id, current_track_id=track_id)
        self._create_tracked_task(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            task_id=market_task_id,
            track_id=track_id,
            title="Market scan",
        )
        market_context = self._broker_prepare(
            buddy="market",
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        market_tool_evidence = self._approve_market_downgrade_evidence(
            context=market_context,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        market_artifact_ids = self._create_artifacts(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            context=market_context,
            task_id=market_task_id,
            artifact_specs=MARKET_ARTIFACTS,
        )
        self._broker_persist(
            buddy="market",
            context=market_context,
            result=self._audit_result(
                MARKET_COMMIT,
                task_id=market_task_id,
                track_id=track_id,
                artifact_ids=market_artifact_ids,
                tool_evidence=market_tool_evidence,
            ),
            instance_json=market_instance,
            instance_id=market_instance_id,
        )

        design_instance_id = "inst-design-context"
        design_instance = self._instance_json(buddy="design", instance_id=design_instance_id, current_track_id=track_id)
        design_context = self._broker_prepare(
            buddy="design",
            text="根据已有track继续设计",
            instance_json=design_instance,
            instance_id=design_instance_id,
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
        track_id = "track-ai-schedule-cross-buddy"
        task_ids = {
            "pm": "task-pm-cross-buddy-prd",
            "market": "task-market-cross-buddy-scan",
            "design": "task-design-cross-buddy-handoff",
            "dev": "task-dev-cross-buddy-implementation",
            "test": "task-test-cross-buddy-report",
        }
        pm_instance_id = "inst-pm-flow"
        pm_instance = self._instance_json(buddy="pm", instance_id=pm_instance_id)
        pm_context = self._broker_prepare(
            buddy="pm",
            text=PM_REQUEST,
            instance_json=pm_instance,
            instance_id=pm_instance_id,
        )
        self._create_track(track_id=track_id, instance_json=pm_instance, instance_id=pm_instance_id)
        self._create_tracked_task(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            task_id=task_ids["pm"],
            track_id=track_id,
            title="PM PRD",
        )
        self._update_task(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            task_id=task_ids["pm"],
            patch=PM_TASK_UPDATE,
        )
        pm_artifact_ids = self._create_artifacts(
            buddy="pm",
            instance_json=pm_instance,
            instance_id=pm_instance_id,
            context=pm_context,
            task_id=task_ids["pm"],
            artifact_specs=PM_ARTIFACTS,
        )
        pm_persisted = self._broker_persist(
            buddy="pm",
            context=pm_context,
            result=self._audit_result(PM_COMMIT, task_id=task_ids["pm"], track_id=track_id, artifact_ids=pm_artifact_ids),
            instance_json=pm_instance,
            instance_id=pm_instance_id,
        )

        state = _CDPState(
            version_ok=True,
            pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
            allow_put_new_about_blank=False,
            allow_get_new_about_blank=False,
        )
        browser_port = self._start_cdp_server(state)

        market_instance_id = "inst-market-flow"
        market_instance = self._instance_json(
            buddy="market",
            instance_id=market_instance_id,
            current_track_id=track_id,
            browser_port=browser_port,
        )
        self._create_tracked_task(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            task_id=task_ids["market"],
            track_id=track_id,
            title="Market scan",
        )
        market_context = self._broker_prepare(
            buddy="market",
            text=MARKET_REQUEST,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        market_tool_evidence = self._issue_market_browser_evidence(
            context=market_context,
            instance_json=market_instance,
            instance_id=market_instance_id,
        )
        market_artifact_ids = self._create_artifacts(
            buddy="market",
            instance_json=market_instance,
            instance_id=market_instance_id,
            context=market_context,
            task_id=task_ids["market"],
            artifact_specs=MARKET_ARTIFACTS,
        )
        market_result = json.loads(json.dumps(MARKET_COMMIT))
        market_persisted = self._broker_persist(
            buddy="market",
            context=market_context,
            result=self._audit_result(
                market_result,
                task_id=task_ids["market"],
                track_id=track_id,
                artifact_ids=market_artifact_ids,
                tool_evidence=market_tool_evidence,
            ),
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
        self._create_tracked_task(
            buddy="design",
            instance_json=design_instance,
            instance_id=design_instance_id,
            task_id=task_ids["design"],
            track_id=track_id,
            title="Design handoff",
        )
        design_artifact_ids = self._create_artifacts(
            buddy="design",
            instance_json=design_instance,
            instance_id=design_instance_id,
            context=design_context,
            task_id=task_ids["design"],
            artifact_specs=DESIGN_ARTIFACTS,
        )
        design_persisted = self._broker_persist(
            buddy="design",
            context=design_context,
            result=self._audit_result(
                DESIGN_COMMIT,
                task_id=task_ids["design"],
                track_id=track_id,
                artifact_ids=design_artifact_ids,
            ),
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
        self._create_tracked_task(
            buddy="dev",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            task_id=task_ids["dev"],
            track_id=track_id,
            title="Dev implementation",
        )
        self._update_task(
            buddy="dev",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            task_id=task_ids["dev"],
            patch=DEV_TASK_UPDATE,
        )
        dev_artifact_ids = self._create_artifacts(
            buddy="dev",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            context=dev_context,
            task_id=task_ids["dev"],
            artifact_specs=DEV_ARTIFACTS,
        )
        self._update_task(
            buddy="dev",
            instance_json=dev_instance,
            instance_id=dev_instance_id,
            task_id=task_ids["dev"],
            patch=DEV_TASK_UPDATE,
        )
        dev_persisted = self._broker_persist(
            buddy="dev",
            context=dev_context,
            result=self._audit_result(
                DEV_COMMIT,
                task_id=task_ids["dev"],
                track_id=track_id,
                artifact_ids=dev_artifact_ids,
            ),
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
        self._create_tracked_task(
            buddy="test",
            instance_json=test_instance,
            instance_id=test_instance_id,
            task_id=task_ids["test"],
            track_id=track_id,
            title="Test report",
        )
        self._update_task(
            buddy="test",
            instance_json=test_instance,
            instance_id=test_instance_id,
            task_id=task_ids["test"],
            patch=TEST_TASK_UPDATE,
        )
        test_artifact_ids = self._create_artifacts(
            buddy="test",
            instance_json=test_instance,
            instance_id=test_instance_id,
            context=test_context,
            task_id=task_ids["test"],
            artifact_specs=TEST_ARTIFACTS,
        )
        test_persisted = self._broker_persist(
            buddy="test",
            context=test_context,
            result=self._audit_result(
                TEST_COMMIT,
                task_id=task_ids["test"],
                track_id=track_id,
                artifact_ids=test_artifact_ids,
            ),
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

        expected_handoffs = {
            "pm": "market",
            "market": "design",
            "design": "dev",
            "dev": "test",
            "test": "pm",
        }
        for buddy, receipt in receipts:
            handoff = receipt.get("handoff")
            self.assertIsInstance(handoff, dict, msg=receipt)
            assert isinstance(handoff, dict)
            self.assertEqual(handoff.get("next_buddy"), expected_handoffs[buddy])

        dev_task = env_store.get_task(dev_persisted["receipt"]["task_id"])
        self.assertIsNotNone(dev_task)
        assert dev_task is not None
        self.assertEqual(dev_task["status"], "done")
        self.assertEqual(dev_task["summary"], "Dev implementation is ready for Test smoke validation.")

        self.assertEqual(project_source.read_text(encoding="utf-8"), "dev-only-change\n")


if __name__ == "__main__":
    unittest.main()
