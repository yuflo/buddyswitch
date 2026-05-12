#!/usr/bin/env python3
"""Functional coverage for structured runtime tool feedback."""

from __future__ import annotations

import copy
import json
import os
import socket
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"

PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"
MARKET_REQUEST = "调研 AI 日程工具 landing page 竞品表达和定位方式"
DESIGN_REQUEST = "基于现有 PRD 和市场简报，整理 landing page 原型方向"
DEV_REQUEST = "实现 landing page hero 文案和 CTA 调整"
TEST_REQUEST = "验证 landing page hero 和 CTA 行为"


def _pm_commit() -> dict[str, object]:
    return {
        "execution_summary": "PM wrote the PRD.",
    }


PM_ARTIFACT = {
    "kind": "prd",
    "title": "AI Schedule Tool Landing Page PRD",
    "summary": "Defines product scope.",
    "content": {"problem": "Scheduling back-and-forth is costly."},
}


def _market_commit(tool_evidence: dict[str, str] | None = None) -> dict[str, object]:
    commit: dict[str, object] = {
        "execution_summary": "Market analyzed competitor positioning.",
    }
    if tool_evidence is not None:
        commit["tool_evidence"] = tool_evidence
    return commit


MARKET_ARTIFACT = {
    "kind": "market-scan",
    "title": "AI Schedule Market Scan",
    "summary": "Competitor positioning notes.",
    "content": {"insights": ["Concrete workflow claims are stronger."]},
}


def _design_commit() -> dict[str, object]:
    return {
        "execution_summary": "Design prepared the landing page handoff.",
    }


DESIGN_ARTIFACT = {
    "kind": "design-handoff",
    "title": "Landing Page Design Handoff",
    "summary": "Hero and CTA direction.",
    "content": {"sections": ["hero", "cta"]},
}


def _dev_commit() -> dict[str, object]:
    return {
        "execution_summary": "Dev implemented landing page copy changes.",
    }


DEV_ARTIFACT = {
    "kind": "implementation-report",
    "title": "Landing Page Implementation Report",
    "summary": "Source changes recorded.",
    "content": {"changed_files": ["projects/app/src/landing-page.md"]},
}


def _test_commit() -> dict[str, object]:
    return {
        "execution_summary": "Test validated landing page hero and CTA.",
    }


TEST_ARTIFACT = {
    "kind": "test-report",
    "title": "Landing Page Test Report",
    "summary": "Smoke test result.",
    "content": {"passed_items": ["hero renders", "cta clickable"]},
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


class RuntimeToolFeedbackTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        buddy: str = "pm",
        instance_id: str = "inst-pm-example",
        status: str = "active",
        browser_port: int | None = None,
    ) -> Path:
        path = self._runtime_path(f"instances/{instance_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(path.parent / "workspace"),
                    "browser_port": browser_port,
                    "created_at": "2026-05-08T00:00:00Z",
                    "updated_at": "2026-05-08T00:00:00Z",
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
        instance_id: str = "inst-pm-example",
        buddy: str = "pm",
        protocol: str = "buddyswitch-runtime-broker/v1",
    ) -> dict[str, object]:
        return runtime_broker.dispatch_runtime_request(
            request={
                "protocol": protocol,
                "instance_id": instance_id,
                "active_buddy": buddy,
                "method": method,
                "payload": payload,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

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
            method="env.tool",
            payload={"tool": tool, "action": action, "args": args},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), tool)
        return response

    def _create_bound_task(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        task_id: str,
        title: str,
    ) -> None:
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="task",
            action="create",
            args={"task_id": task_id, "title": title, "summary": f"{buddy} feedback fixture task."},
        )
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="binding",
            action="set_task",
            args={"task_id": task_id},
        )

    def _create_track(self, *, instance_json: Path, instance_id: str, track_id: str) -> None:
        self._env_tool(
            buddy="pm",
            instance_json=instance_json,
            instance_id=instance_id,
            tool="track",
            action="create",
            args={
                "track_id": track_id,
                "title": "PM Validation Track",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "market",
            },
        )

    def _attach_task_to_track(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        task_id: str,
        track_id: str,
    ) -> None:
        self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="track",
            action="attach_task",
            args={"track_id": track_id, "task_id": task_id},
        )

    def _create_artifact(
        self,
        *,
        buddy: str,
        instance_json: Path,
        instance_id: str,
        context: dict[str, object],
        task_id: str,
        spec: dict[str, object],
    ) -> str:
        run_envelope = context["run_envelope"]
        self.assertIsInstance(run_envelope, dict)
        assert isinstance(run_envelope, dict)
        source_run_id = run_envelope["run_id"]
        self.assertIsInstance(source_run_id, str)
        kind = spec["kind"]
        self.assertIsInstance(kind, str)
        created = self._env_tool(
            buddy=buddy,
            instance_json=instance_json,
            instance_id=instance_id,
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": f"art-{task_id}-{kind}-{source_run_id.replace('run-', '')[:8]}",
                "task_id": task_id,
                "kind": kind,
                "title": spec["title"],
                "summary": spec["summary"],
                "content": spec["content"],
                "source_run_id": source_run_id,
            },
        )
        return str(created["artifact_id"])

    def _audit_result(
        self,
        base: dict[str, object],
        *,
        task_id: str,
        artifact_ids: list[str],
        track_id: str | None = None,
        tool_evidence: dict[str, object] | None = None,
    ) -> dict[str, object]:
        result = copy.deepcopy(base)
        result["task_id"] = task_id
        result["artifact_ids"] = artifact_ids
        if track_id is not None:
            result["track_id"] = track_id
        if tool_evidence is not None:
            result["tool_evidence"] = tool_evidence
        return result

    def _prepare(
        self,
        *,
        buddy: str,
        instance_id: str,
        request_text: str,
        instance_json: Path,
    ) -> dict[str, object]:
        prepared = self._dispatch(
            method="prepare",
            payload={"text": request_text},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )
        self.assertTrue(prepared["ok"], msg=prepared)
        return prepared["payload"]

    def _evidence_payload(
        self,
        *,
        context: dict[str, object],
        mode: str,
        reason: str | None = None,
    ) -> dict[str, object]:
        if mode == "browser-cockpit-preflight":
            return {"tool": "evidence", "action": "issue_browser", "args": {"context": context}}
        if mode == "approved-downgrade":
            args: dict[str, object] = {"context": context}
            if reason is not None:
                args["reason"] = reason
            return {"tool": "evidence", "action": "approve_downgrade", "args": args}
        raise AssertionError(f"unsupported test evidence mode: {mode}")

    def _state_snapshot(self) -> dict[str, object]:
        def _load_dir(path: Path) -> dict[str, object]:
            if not path.exists():
                return {}
            return {
                row.name: json.loads(row.read_text(encoding="utf-8"))
                for row in sorted(path.glob("*.json"))
            }

        return {
            "tracks": _load_dir(self._runtime_path("buddyswitch/objects/tracks")),
            "tasks": _load_dir(self._runtime_path("buddyswitch/objects/tasks")),
            "artifacts": _load_dir(self._runtime_path("buddyswitch/objects/artifacts")),
            "runs": _load_dir(self._runtime_path("buddyswitch/content/runs")),
            "reserved": _load_dir(self._runtime_path("buddyswitch/content/runs/reserved")),
        }

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

    def _assert_stop_feedback(self, payload: dict[str, object]) -> None:
        self.assertFalse(payload["ok"])
        error = payload["error"]
        self.assertEqual(error["code"], "E_RUNTIME_BROKER_UNAVAILABLE")
        self.assertEqual(payload["permission_boundary"], "product-mode-runtime-broker")
        self.assertEqual(payload["stop_condition"], "stop_and_report_do_not_bypass_broker")
        actions = " ".join(payload["allowed_next_actions"])
        self.assertIn("broker", actions.lower())
        self.assertIn("raw", actions.lower())
        self.assertIn("bypass", actions.lower())

    def _assert_structured_next_action_options(self, payload: dict[str, object]) -> None:
        self.assertIn("allowed_next_action_options", payload)
        options = payload["allowed_next_action_options"]
        self.assertIsInstance(options, list, msg=payload)
        assert isinstance(options, list)
        self.assertGreaterEqual(len(options), 1, msg=payload)
        for row in options:
            self.assertIsInstance(row, dict, msg=payload)
            assert isinstance(row, dict)
            for key in ("id", "tool", "action", "mutates", "preconditions", "reason", "source_refs"):
                self.assertIn(key, row)

    def _assert_authoritative_feedback_fields(self, payload: dict[str, object]) -> None:
        self.assertIn("permission_boundary", payload)
        self.assertIn("allowed_next_actions", payload)
        if "command_hint" in payload:
            self.assertIsInstance(payload["command_hint"], str)
        if "stop_condition" in payload:
            self.assertIsInstance(payload["stop_condition"], str)
        error = payload.get("error")
        self.assertIsInstance(error, dict, msg=payload)
        assert isinstance(error, dict)
        self.assertNotIn("permission_boundary", error)
        self.assertNotIn("allowed_next_actions", error)
        self.assertNotIn("command_hint", error)
        self.assertNotIn("stop_condition", error)

    def _run_product_cli_without_broker(self, args: list[str], *, buddy: str = "pm") -> dict[str, object]:
        instance_id = f"inst-{buddy}-missing-broker"
        instance_json = self._instance_json(buddy=buddy, instance_id=instance_id)
        env = os.environ.copy()
        env.update(
            {
                "BUDDYSWITCH_INSTANCE_ID": instance_id,
                "BUDDYSWITCH_ACTIVE_BUDDY": buddy,
                "BUDDYSWITCH_INSTANCE_JSON": str(instance_json),
                "BUDDYSWITCH_SHARED_ROOT": str(self.runtime_root),
                "BUDDYSWITCH_STATE_ROOT": str(self.runtime_root / "state"),
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(self.runtime_root / "missing.sock"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        completed = subprocess.run(
            ["python3", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0, msg=completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def test_product_cli_missing_broker_returns_stop_feedback_for_prepare_persist_and_evidence(self) -> None:
        before = self._state_snapshot()
        raw_dir = self._runtime_path("runs/raw/pm")
        raw_dir.mkdir(parents=True, exist_ok=True)
        context_path = raw_dir / "context.json"
        result_path = raw_dir / "result.json"
        context_path.write_text(json.dumps({"ok": True}, ensure_ascii=True), encoding="utf-8")
        result_path.write_text(json.dumps({"execution_summary": "x"}, ensure_ascii=True), encoding="utf-8")

        prepare_payload = self._run_product_cli_without_broker(
            [str(ROOT / "scripts" / "turn_runtime.py"), "prepare", PM_REQUEST],
        )
        self._assert_stop_feedback(prepare_payload)

        persist_payload = self._run_product_cli_without_broker(
            [
                str(ROOT / "scripts" / "turn_runtime.py"),
                "persist",
                "--context",
                str(context_path),
                "--result",
                str(result_path),
            ],
        )
        self._assert_stop_feedback(persist_payload)

        evidence_payload = self._run_product_cli_without_broker(
            [
                str(ROOT / "scripts" / "browser_evidence.py"),
                "issue",
                "--context",
                str(context_path),
                "--mode",
                "browser-cockpit-preflight",
            ],
            buddy="market",
        )
        self._assert_stop_feedback(evidence_payload)
        self.assertEqual(self._state_snapshot(), before)

    def test_broker_dispatch_rejections_include_structured_boundaries(self) -> None:
        instance_json = self._instance_json()
        cases = (
            (
                "wrong-instance",
                {
                    "protocol": "buddyswitch-runtime-broker/v1",
                    "instance_id": "inst-other",
                    "active_buddy": "pm",
                    "method": "prepare",
                    "payload": {"text": PM_REQUEST},
                },
                "active-instance",
            ),
            (
                "wrong-buddy",
                {
                    "protocol": "buddyswitch-runtime-broker/v1",
                    "instance_id": "inst-pm-example",
                    "active_buddy": "market",
                    "method": "prepare",
                    "payload": {"text": PM_REQUEST},
                },
                "active-buddy",
            ),
            (
                "malformed-payload",
                {
                    "protocol": "buddyswitch-runtime-broker/v1",
                    "instance_id": "inst-pm-example",
                    "active_buddy": "pm",
                    "method": "prepare",
                    "payload": [],
                },
                "request-payload",
            ),
            (
                "unsupported-method",
                {
                    "protocol": "buddyswitch-runtime-broker/v1",
                    "instance_id": "inst-pm-example",
                    "active_buddy": "pm",
                    "method": "continue",
                    "payload": {},
                },
                "broker-protocol",
            ),
        )
        before = self._state_snapshot()
        for label, request, boundary in cases:
            with self.subTest(label=label):
                response = runtime_broker.dispatch_runtime_request(
                    request=request,
                    instance_json_path=instance_json,
                    manifest_path=MANIFEST,
                )
                self.assertFalse(response["ok"])
                error = response["error"]
                self.assertEqual(error["code"], "E_RUNTIME_BROKER")
                self.assertEqual(response["permission_boundary"], boundary)
                self.assertIn("allowed_next_actions", response)
        self.assertEqual(self._state_snapshot(), before)

        inactive_json = self._instance_json(status="inactive")
        inactive = self._dispatch(
            method="prepare",
            payload={"text": PM_REQUEST},
            instance_json=inactive_json,
        )
        self.assertFalse(inactive["ok"])
        self.assertEqual(inactive["permission_boundary"], "active-instance-status")

    def test_persist_rejections_include_feedback_and_do_not_write_state(self) -> None:
        cases = []

        market_json = self._instance_json(buddy="market", instance_id="inst-market-example")
        market_context = self._prepare(
            buddy="market",
            instance_id="inst-market-example",
            request_text=MARKET_REQUEST,
            instance_json=market_json,
        )
        cases.append(
            (
                "market-track-create",
                market_json,
                "inst-market-example",
                "market",
                market_context,
                {
                    "execution_summary": "Market tried to create a track.",
                    "state_effects": {
                        "track": {
                            "action": "create",
                            "track_id": "track-ai-schedule-landing-page",
                            "title": "AI Schedule",
                        }
                    },
                },
                "persist.state_effects",
            )
        )

        dev_json = self._instance_json(buddy="dev", instance_id="inst-dev-example")
        dev_context = self._prepare(
            buddy="dev",
            instance_id="inst-dev-example",
            request_text=DEV_REQUEST,
            instance_json=dev_json,
        )
        cases.append(
            (
                "dev-prd",
                dev_json,
                "inst-dev-example",
                "dev",
                dev_context,
                {"execution_summary": "Dev tried to embed PM artifact content.", "artifacts": [PM_ARTIFACT]},
                "persist.artifacts",
            )
        )

        pm_json = self._instance_json()
        pm_context = self._prepare(
            buddy="pm",
            instance_id="inst-pm-example",
            request_text=PM_REQUEST,
            instance_json=pm_json,
        )
        invalid_handoff = {
            "execution_summary": "PM tried to hand off to sales.",
            "handoff": {"next_buddy": "sales", "reason": "Need sales input.", "context": "x"},
        }
        cases.append(("unknown-handoff", pm_json, "inst-pm-example", "pm", pm_context, invalid_handoff, "manifest.buddies"))

        invalid_task = {
            "execution_summary": "PM tried to update an unsupported task field.",
            "state_effects": {"task": {"owner": "pm"}},
        }
        cases.append(
            (
                "unsupported-task-field",
                pm_json,
                "inst-pm-example",
                "pm",
                pm_context,
                invalid_task,
                "persist.state_effects",
            )
        )

        for label, instance_json, instance_id, buddy, context, result, boundary in cases:
            with self.subTest(label=label):
                before = self._state_snapshot()
                rejected = self._dispatch(
                    method="persist",
                    payload={"context": context, "result": result},
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy=buddy,
                )
                self.assertFalse(rejected["ok"], msg=rejected)
                error = rejected["error"]
                self.assertEqual(error["code"], "E_RUNTIME_PERSIST")
                self.assertEqual(rejected["permission_boundary"], boundary)
                self.assertIn("allowed_next_actions", rejected)
                self.assertIsInstance(rejected["allowed_next_actions"], list)
                self.assertGreaterEqual(len(rejected["allowed_next_actions"]), 1)
                if "persist_payload_hint" in rejected:
                    self.assertIsInstance(rejected["persist_payload_hint"], dict)
                self.assertEqual(self._state_snapshot(), before)

    def test_persist_common_validation_failures_return_structured_feedback_and_keep_state_atomic(self) -> None:
        unbound_pm_json = self._instance_json(instance_id="inst-pm-unbound")
        base_context = self._prepare(
            buddy="pm",
            instance_id="inst-pm-unbound",
            request_text=PM_REQUEST,
            instance_json=unbound_pm_json,
        )

        bound_pm_json = self._instance_json(instance_id="inst-pm-bound")
        track_id = "track-pm-validation"
        task_id = "task-pm-validation"
        self._create_track(instance_json=bound_pm_json, instance_id="inst-pm-bound", track_id=track_id)
        self._create_bound_task(
            buddy="pm",
            instance_json=bound_pm_json,
            instance_id="inst-pm-bound",
            task_id=task_id,
            title="PM Validation Task",
        )
        self._attach_task_to_track(
            buddy="pm",
            instance_json=bound_pm_json,
            instance_id="inst-pm-bound",
            task_id=task_id,
            track_id=track_id,
        )
        bound_context = self._prepare(
            buddy="pm",
            instance_id="inst-pm-bound",
            request_text="继续当前track",
            instance_json=bound_pm_json,
        )
        self.assertEqual(bound_context["current_task_id"], task_id)
        self.assertEqual(bound_context["current_track_id"], track_id)

        missing_execution_summary = _pm_commit()
        missing_execution_summary.pop("execution_summary", None)

        empty_execution_summary = _pm_commit()
        empty_execution_summary["execution_summary"] = "   "

        embedded_artifact = {"execution_summary": "PM attempted embedded artifact content.", "artifacts": [PM_ARTIFACT]}

        unsupported_task_key = {
            "execution_summary": "PM attempted unsupported task field.",
            "state_effects": {"task": {"owner": "pm"}},
        }

        cases = (
            (
                "missing-execution-summary",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                missing_execution_summary,
                "persist.execution_summary",
            ),
            (
                "empty-execution-summary",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                empty_execution_summary,
                "persist.execution_summary",
            ),
            (
                "embedded-artifact-content",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                embedded_artifact,
                "persist.artifacts",
            ),
            (
                "missing-task-association",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                {"execution_summary": "PM associated a missing task.", "task_id": "task-missing-feedback"},
                "persist.task_id",
            ),
            (
                "missing-track-association",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                {"execution_summary": "PM associated a missing track.", "track_id": "track-missing-feedback"},
                "persist.track_id",
            ),
            (
                "missing-artifact-association",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                {"execution_summary": "PM associated a missing artifact.", "artifact_ids": ["art-missing-feedback"]},
                "persist.artifact_ids",
            ),
            (
                "invalid-track-action",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                {
                    "execution_summary": "PM attempted unsupported track action.",
                    "state_effects": {"track": {"action": "pause"}},
                },
                "persist.state_effects",
            ),
            (
                "track-create-when-already-bound",
                bound_pm_json,
                "inst-pm-bound",
                bound_context,
                {
                    "execution_summary": "PM attempted duplicate track create.",
                    "state_effects": {"track": {"action": "create"}},
                },
                "persist.state_effects",
            ),
            (
                "non-create-without-track-id",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                {
                    "execution_summary": "PM attempted track update without existing track binding.",
                    "state_effects": {"track": {"action": "update", "summary": "missing target"}},
                },
                "persist.state_effects",
            ),
            (
                "track-update-references-missing-track",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                {
                    "execution_summary": "PM attempted track update for a missing track.",
                    "state_effects": {
                        "track": {
                            "action": "update",
                            "track_id": "track-missing-feedback",
                            "summary": "missing target",
                        }
                    },
                },
                "persist.state_effects",
            ),
            (
                "track-update-without-mutable-fields",
                bound_pm_json,
                "inst-pm-bound",
                bound_context,
                {
                    "execution_summary": "PM attempted track update without mutable fields.",
                    "state_effects": {"track": {"action": "update", "track_id": track_id}},
                },
                "persist.state_effects",
            ),
            (
                "handoff-missing-reason-context",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                {
                    "execution_summary": "PM attempted handoff without reason/context.",
                    "handoff": {"next_buddy": "market"},
                },
                "persist.handoff",
            ),
            (
                "handoff-missing-next-buddy",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                {
                    "execution_summary": "PM attempted handoff without next buddy.",
                    "handoff": {"reason": "Need another buddy.", "context": "Continue with context."},
                },
                "persist.handoff",
            ),
            (
                "handoff-target-unknown",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                {
                    "execution_summary": "PM attempted handoff to an unknown buddy.",
                    "handoff": {"next_buddy": "sales", "reason": "Need sales.", "context": "Continue."},
                },
                "manifest.buddies",
            ),
            (
                "handoff-target-conflicts-with-track-next-buddy",
                bound_pm_json,
                "inst-pm-bound",
                bound_context,
                {
                    "execution_summary": "PM submitted conflicting handoff and track next buddy.",
                    "state_effects": {
                        "track": {
                            "action": "advance",
                            "track_id": track_id,
                            "next_buddy": "design",
                        }
                    },
                    "handoff": {
                        "next_buddy": "market",
                        "reason": "handoff conflict check",
                        "context": "conflicting target",
                    },
                },
                "persist.state_effects",
            ),
            (
                "unsupported-task-key",
                unbound_pm_json,
                "inst-pm-unbound",
                base_context,
                unsupported_task_key,
                "persist.state_effects",
            ),
        )

        for label, instance_json, instance_id, context, result, boundary in cases:
            with self.subTest(label=label):
                before = self._state_snapshot()
                rejected = self._dispatch(
                    method="persist",
                    payload={"context": context, "result": result},
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy="pm",
                )
                self.assertFalse(rejected["ok"], msg=rejected)
                error = rejected["error"]
                self.assertEqual(error["code"], "E_RUNTIME_PERSIST")
                self.assertEqual(rejected["permission_boundary"], boundary)
                self.assertIn("allowed_next_actions", rejected)
                self.assertIsInstance(rejected["allowed_next_actions"], list)
                self.assertGreaterEqual(len(rejected["allowed_next_actions"]), 1)
                if "persist_payload_hint" in rejected:
                    self.assertIsInstance(rejected["persist_payload_hint"], dict)
                self.assertEqual(self._state_snapshot(), before)

    def test_stale_context_and_buddy_mismatch_feedback_tell_buddy_to_prepare_again(self) -> None:
        pm_json = self._instance_json()
        context = self._prepare(
            buddy="pm",
            instance_id="inst-pm-example",
            request_text=PM_REQUEST,
            instance_json=pm_json,
        )
        persisted = self._dispatch(
            method="persist",
            payload={"context": context, "result": _pm_commit()},
            instance_json=pm_json,
        )
        self.assertTrue(persisted["ok"], msg=persisted)
        before = self._state_snapshot()

        stale = self._dispatch(
            method="persist",
            payload={"context": context, "result": _pm_commit()},
            instance_json=pm_json,
        )
        self.assertFalse(stale["ok"])
        self.assertEqual(stale["permission_boundary"], "prepare.context_revision")
        self.assertIn("prepare", " ".join(stale["allowed_next_actions"]).lower())
        self.assertEqual(self._state_snapshot(), before)

        mismatch_context = copy.deepcopy(context)
        mismatch_context["active_buddy"] = "market"
        before_mismatch = self._state_snapshot()
        mismatch = self._dispatch(
            method="persist",
            payload={"context": mismatch_context, "result": _market_commit()},
            instance_json=pm_json,
        )
        self.assertFalse(mismatch["ok"])
        self.assertEqual(mismatch["permission_boundary"], "active-buddy")
        self.assertIn("prepare", " ".join(mismatch["allowed_next_actions"]).lower())
        self.assertEqual(self._state_snapshot(), before_mismatch)

    def test_market_browser_preflight_endpoint_only_returns_ready_boundary_feedback(self) -> None:
        state = _CDPState(version_ok=True, pages=[], allow_put_new_about_blank=False, allow_get_new_about_blank=False)
        port = self._start_cdp_server(state)
        market_json = self._instance_json(buddy="market", instance_id="inst-market-example", browser_port=port)
        context = self._prepare(
            buddy="market",
            instance_id="inst-market-example",
            request_text=MARKET_REQUEST,
            instance_json=market_json,
        )

        issue = self._dispatch(
            method="env.tool",
            payload=self._evidence_payload(context=context, mode="browser-cockpit-preflight"),
            instance_json=market_json,
            instance_id="inst-market-example",
            buddy="market",
        )
        self.assertFalse(issue["ok"])
        error = issue["error"]
        self.assertEqual(error["code"], "E_RUNTIME_BROKER")
        self.assertEqual(issue["permission_boundary"], "browser-cockpit-ready")
        self.assertEqual(issue["stop_condition"], "browser cockpit is not ready for MCP page operations")
        self.assertIn("restart", " ".join(issue["allowed_next_actions"]).lower())
        self.assertIn("open", " ".join(issue["allowed_next_actions"]).lower())
        self.assertIn("browser ensure", " ".join(issue["allowed_next_actions"]).lower())
        self.assertEqual(
            issue["command_hint"],
            "./buddyswitch-codex env browser ensure --instance inst-market-example",
        )
        self.assertEqual(self._evidence_token_paths(market_json), [])
        calls = state.snapshot_calls()
        self.assertTrue(any(call["method"] == "GET" and call["path"] == "/json/version" for call in calls))
        self.assertEqual(
            len([call for call in calls if call["method"] == "PUT" and call["path"] == "/json/new" and call["query"] == "about:blank"]),
            1,
        )

    def test_market_evidence_rejection_and_success_feedback(self) -> None:
        state = _CDPState(
            version_ok=True,
            pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
            allow_put_new_about_blank=False,
            allow_get_new_about_blank=False,
        )
        port = self._start_cdp_server(state)
        market_json = self._instance_json(buddy="market", instance_id="inst-market-example", browser_port=port)
        market_task_id = "task-market-feedback"
        self._create_bound_task(
            buddy="market",
            instance_json=market_json,
            instance_id="inst-market-example",
            task_id=market_task_id,
            title="Market Feedback Task",
        )
        context = self._prepare(
            buddy="market",
            instance_id="inst-market-example",
            request_text=MARKET_REQUEST,
            instance_json=market_json,
        )
        market_artifact_id = self._create_artifact(
            buddy="market",
            instance_json=market_json,
            instance_id="inst-market-example",
            context=context,
            task_id=market_task_id,
            spec=MARKET_ARTIFACT,
        )
        market_result = self._audit_result(
            _market_commit(),
            task_id=market_task_id,
            artifact_ids=[market_artifact_id],
        )

        before = self._state_snapshot()
        missing = self._dispatch(
            method="persist",
            payload={"context": context, "result": market_result},
            instance_json=market_json,
            instance_id="inst-market-example",
            buddy="market",
        )
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["permission_boundary"], "market.browser_evidence")
        self.assertIn("command_hint", missing)
        self.assertEqual(self._state_snapshot(), before)

        handwritten = self._dispatch(
            method="persist",
            payload={
                "context": context,
                "result": {
                    **market_result,
                    "tool_evidence": {"browser_cockpit_token": "handwritten-token"},
                },
            },
            instance_json=market_json,
            instance_id="inst-market-example",
            buddy="market",
        )
        self.assertFalse(handwritten["ok"])
        self.assertEqual(handwritten["permission_boundary"], "market.browser_evidence")
        self.assertEqual(self._state_snapshot(), before)

        browser_issue = self._dispatch(
            method="env.tool",
            payload=self._evidence_payload(context=context, mode="browser-cockpit-preflight"),
            instance_json=market_json,
            instance_id="inst-market-example",
            buddy="market",
        )
        self.assertTrue(browser_issue["ok"], msg=browser_issue)
        payload = browser_issue
        self.assertIn("browser_cockpit_token", payload["tool_evidence"])
        feedback = payload["feedback"]
        self.assertEqual(feedback["mode"], "browser-cockpit-preflight")
        self.assertEqual(feedback["browser_url"], f"http://127.0.0.1:{port}")
        self.assertEqual(feedback["persist_field"], "tool_evidence.browser_cockpit_token")
        self.assertEqual(feedback["token_scope"]["run_id"], context["run_envelope"]["run_id"])
        self.assertIn("next", feedback["next_action"].lower())

        wrong_instance_token = payload["tool_evidence"]["browser_cockpit_token"]
        token_record = (
            market_json.parent
            / "runtime"
            / "evidence-tokens"
            / context["run_envelope"]["run_id"]
            / f"{wrong_instance_token}.json"
        )
        token_payload = json.loads(token_record.read_text(encoding="utf-8"))
        token_payload["instance_id"] = "inst-other"
        token_record.write_text(json.dumps(token_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        before_wrong_instance = self._state_snapshot()
        wrong_instance = self._dispatch(
            method="persist",
            payload={
                "context": context,
                "result": {
                    **market_result,
                    "tool_evidence": {"browser_cockpit_token": wrong_instance_token},
                },
            },
            instance_json=market_json,
            instance_id="inst-market-example",
            buddy="market",
        )
        self.assertFalse(wrong_instance["ok"])
        self.assertEqual(wrong_instance["permission_boundary"], "market.browser_evidence")
        self.assertEqual(self._state_snapshot(), before_wrong_instance)

        downgrade_issue = self._dispatch(
            method="env.tool",
            payload=self._evidence_payload(
                context=context,
                mode="approved-downgrade",
                reason="Browser cockpit is unavailable and user approved a fallback.",
            ),
            instance_json=market_json,
            instance_id="inst-market-example",
            buddy="market",
        )
        self.assertTrue(downgrade_issue["ok"], msg=downgrade_issue)
        downgrade_payload = downgrade_issue
        self.assertIn("approved_downgrade_token", downgrade_payload["tool_evidence"])
        self.assertEqual(downgrade_payload["feedback"]["mode"], "approved-downgrade")
        self.assertEqual(downgrade_payload["feedback"]["persist_field"], "tool_evidence.approved_downgrade_token")
        self.assertIn("reason", downgrade_payload["feedback"])

        wrong_mode = self._dispatch(
            method="persist",
            payload={
                "context": context,
                "result": {
                    **market_result,
                    "tool_evidence": {
                        "browser_cockpit_token": downgrade_payload["tool_evidence"]["approved_downgrade_token"]
                    },
                },
            },
            instance_json=market_json,
            instance_id="inst-market-example",
            buddy="market",
        )
        self.assertFalse(wrong_mode["ok"])
        self.assertEqual(wrong_mode["permission_boundary"], "market.browser_evidence")
        self.assertEqual(self._state_snapshot(), before_wrong_instance)

    def test_non_market_valid_commits_do_not_require_tool_evidence(self) -> None:
        matrix = (
            ("pm", "inst-pm-example", PM_REQUEST, _pm_commit),
            ("design", "inst-design-example", DESIGN_REQUEST, _design_commit),
            ("dev", "inst-dev-example", DEV_REQUEST, _dev_commit),
            ("test", "inst-test-example", TEST_REQUEST, _test_commit),
        )
        for buddy, instance_id, request_text, commit_factory in matrix:
            with self.subTest(buddy=buddy):
                instance_json = self._instance_json(buddy=buddy, instance_id=instance_id)
                context = self._prepare(
                    buddy=buddy,
                    instance_id=instance_id,
                    request_text=request_text,
                    instance_json=instance_json,
                )
                persisted = self._dispatch(
                    method="persist",
                    payload={"context": context, "result": commit_factory()},
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy=buddy,
                )
                self.assertTrue(persisted["ok"], msg=persisted)
                self.assertNotIn("tool_evidence", json.dumps(persisted, ensure_ascii=True))

    def test_runtime_feedback_projection_keeps_authoritative_fields_top_level(self) -> None:
        market_json = self._instance_json(buddy="market", instance_id="inst-market-top-level")
        market_context = self._prepare(
            buddy="market",
            instance_id="inst-market-top-level",
            request_text=MARKET_REQUEST,
            instance_json=market_json,
        )
        rejected = self._dispatch(
            method="persist",
            payload={
                "context": market_context,
                "result": {"execution_summary": "Market tried embedded artifact content.", "artifacts": [MARKET_ARTIFACT]},
            },
            instance_json=market_json,
            instance_id="inst-market-top-level",
            buddy="market",
        )
        self.assertFalse(rejected["ok"], msg=rejected)
        self._assert_authoritative_feedback_fields(rejected)
        self._assert_structured_next_action_options(rejected)

    def test_foreign_scope_rejections_offer_safe_non_raw_state_options(self) -> None:
        dev_json = self._instance_json(buddy="dev", instance_id="inst-dev-safe-options")
        dev_context = self._prepare(
            buddy="dev",
            instance_id="inst-dev-safe-options",
            request_text=DEV_REQUEST,
            instance_json=dev_json,
        )
        mismatch_context = copy.deepcopy(dev_context)
        mismatch_context["active_buddy"] = "market"
        rejected = self._dispatch(
            method="persist",
            payload={"context": mismatch_context, "result": _market_commit()},
            instance_json=dev_json,
            instance_id="inst-dev-safe-options",
            buddy="dev",
        )
        self.assertFalse(rejected["ok"], msg=rejected)
        self._assert_structured_next_action_options(rejected)
        options_text = json.dumps(rejected["allowed_next_action_options"], ensure_ascii=True)
        self.assertNotIn("buddyswitch/objects", options_text)
        self.assertNotIn("raw_state", options_text)


if __name__ == "__main__":
    unittest.main()
