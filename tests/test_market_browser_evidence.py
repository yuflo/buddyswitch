#!/usr/bin/env python3
"""Tests for Market browser evidence issuance and persist gate."""

from __future__ import annotations

import hashlib
import json
import socket
import threading
import sys
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_profiles  # noqa: E402
import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
MARKET_REQUEST = "调研 AI 日程工具 landing page 竞品表达和定位方式"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"
DESIGN_REQUEST = "基于现有 PRD 和市场简报，整理 landing page 原型方向"
DEV_REQUEST = "实现 landing page hero 文案和 CTA 调整"
TEST_REQUEST = "验证 landing page hero 和 CTA 行为"


def _market_commit(
    tool_evidence: dict[str, str] | None = None,
    *,
    artifact_ids: list[str] | None = None,
) -> dict[str, object]:
    commit: dict[str, object] = {
        "execution_summary": "Market analyzed competitor landing pages and proposed positioning.",
        "working_notes": ["Market run for AI schedule tool landing page."],
        "handoff": {
            "next_buddy": "design",
            "reason": "Design should convert positioning into page flow.",
            "context": "Use PM PRD and this market brief.",
        },
        "contributors": {"skills": ["research-scan"], "agents": []},
    }
    if artifact_ids is not None:
        commit["artifact_ids"] = artifact_ids
    if tool_evidence is not None:
        commit["tool_evidence"] = tool_evidence
    return commit


def _pm_commit() -> dict[str, object]:
    return {
        "execution_summary": "PM created PRD.",
    }


def _design_commit() -> dict[str, object]:
    return {
        "execution_summary": "Design prepared the landing page handoff.",
    }


def _dev_commit() -> dict[str, object]:
    return {
        "execution_summary": "Dev implemented landing page copy updates.",
    }


def _test_commit() -> dict[str, object]:
    return {
        "execution_summary": "Test validated landing page hero and CTA behavior.",
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


class MarketBrowserEvidenceTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    @staticmethod
    def _result_hash(result: dict[str, object]) -> str:
        body = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(body).hexdigest()

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
        method = request.get("method")
        self.assertIsInstance(method, str, msg=request)
        assert isinstance(method, str)
        self.assertNotIn("payload", request)
        params_raw = request.get("params")
        self.assertIsInstance(params_raw, dict, msg=request)
        assert isinstance(params_raw, dict)
        params = dict(params_raw)
        request_instance = request.get("instance_id")
        request_buddy = request.get("active_buddy")
        if isinstance(request_instance, str):
            params.setdefault("instance_id", request_instance)
        if isinstance(request_buddy, str):
            params.setdefault("active_buddy", request_buddy)
        runtime_request: dict[str, object] = {
            "protocol": "buddyswitch-runtime-broker/v2",
            "request_id": f"req-market-browser-{uuid.uuid4().hex}",
            "method": method,
            "params": params,
            "deadline_ms": 35000,
        }
        if method == "persist" and isinstance(params, dict):
            context = params.get("context")
            result = params.get("result")
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
                    runtime_request["idempotency_key"] = f"persist:{run_id}:{result_hash}"
                    runtime_request["result_hash"] = result_hash
        envelope = runtime_broker.dispatch_runtime_request(
            request=runtime_request,
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
        payload: dict[str, object] = {
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
            payload[key] = value
        return payload

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

    def _prepare_market(self, *, instance_json: Path, instance_id: str = "inst-market-example") -> dict[str, object]:
        response = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": instance_id,
                "active_buddy": "market",
                "method": "prepare",
                "params": {"text": MARKET_REQUEST},
            },
            instance_json=instance_json,
        )
        self.assertTrue(response["ok"], msg=response)
        payload = response.get("payload") if isinstance(response.get("payload"), dict) else response
        self.assertIsInstance(payload, dict, msg=response)
        assert isinstance(payload, dict)
        return payload

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

    def _seed_market_artifact(
        self,
        *,
        task_id: str = "task-market-brief",
        artifact_id: str = "art-market-brief-r1",
    ) -> str:
        env_store.create_task(
            task_id,
            "Market Brief Task",
            buddy="market",
            track_id=None,
            status="active",
            summary="seed task for market evidence commit tests",
            initial_run_id="run-market-seed-r1",
        )
        env_store.create_artifact(
            artifact_id=artifact_id,
            title="AI Schedule Tool Market Brief",
            buddy="market",
            kind="market-scan",
            task_id=task_id,
            source_run_id="run-market-seed-r1",
            summary="seeded market artifact",
            content={"seeded": True},
        )
        return artifact_id

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

    def _assert_structured_options(self, payload: dict[str, object]) -> None:
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

    def test_market_profile_requires_browser_evidence(self) -> None:
        profile = env_profiles.require_env_profile("market", manifest_path=MANIFEST, repo_root=ROOT)
        self.assertEqual(profile["tool_capability"]["browser_cockpit"], "required")
        self.assertEqual(profile["tool_capability"]["market_research_evidence"], "required")

    def test_market_prepare_decision_surface_exposes_evidence_readiness(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        decision_surface = context["runtime_context"]["decision_surface"]
        evidence_readiness = decision_surface["evidence_readiness"]
        self.assertEqual(evidence_readiness["browser_cockpit"], "required")
        self.assertEqual(evidence_readiness["market_research_evidence"], "required")

    def test_market_persist_without_evidence_rejects_before_writes(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        artifact_id = self._seed_market_artifact()
        before_runs = list(self._runtime_path("buddyswitch/content/runs").glob("*.json"))
        response = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "params": {"context": context, "result": _market_commit(artifact_ids=[artifact_id])},
            },
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertIn("tool_evidence", response["error"]["message"])
        after_runs = list(self._runtime_path("buddyswitch/content/runs").glob("*.json"))
        self.assertEqual(after_runs, before_runs)

    def test_market_missing_evidence_rejection_names_exact_persist_fields_and_issue_option(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        artifact_id = self._seed_market_artifact()
        rejected = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "params": {"context": context, "result": _market_commit(artifact_ids=[artifact_id])},
            },
            instance_json=instance_json,
        )
        self.assertFalse(rejected["ok"], msg=rejected)
        self.assertEqual(rejected["permission_boundary"], "market.browser_evidence")
        self.assertIn("persist_payload_hint", rejected)
        hint = rejected["persist_payload_hint"]
        self.assertEqual(
            set(hint["tool_evidence"]["accepted_fields"]),
            {"browser_cockpit_token", "approved_downgrade_token"},
        )
        self._assert_structured_options(rejected)
        option_pairs = {(row["tool"], row["action"]) for row in rejected["allowed_next_action_options"]}
        self.assertIn(("evidence", "issue_browser"), option_pairs)

    def test_browser_evidence_issue_requires_market_profile(self) -> None:
        instance_json = self._instance_json(buddy="pm", instance_id="inst-pm-example")
        prepared = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-pm-example",
                "active_buddy": "pm",
                "method": "prepare",
                "params": {"text": PM_REQUEST},
            },
            instance_json=instance_json,
        )
        self.assertTrue(prepared["ok"], msg=prepared)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-pm-example",
                "active_buddy": "pm",
                "method": "env.tool",
                "params": self._evidence_payload(
                    context=prepared,
                    mode="browser-cockpit-preflight",
                ),
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
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "env.tool",
                "params": self._evidence_payload(context=context, mode="browser-cockpit-preflight"),
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
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "env.tool",
                "params": self._evidence_payload(context=context, mode="browser-cockpit-preflight"),
            },
            instance_json=instance_json,
        )
        self.assertFalse(issue["ok"])
        self.assertIn("browser cockpit endpoint is unreachable", issue["error"]["message"])
        self.assertEqual(self._evidence_token_paths(instance_json), [])

    def test_browser_preflight_rejects_endpoint_only_without_token(self) -> None:
        state = _CDPState(version_ok=True, pages=[], allow_put_new_about_blank=False, allow_get_new_about_blank=False)
        port = self._start_cdp_server(state)
        instance_json = self._instance_json(browser_port=port)
        context = self._prepare_market(instance_json=instance_json)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "env.tool",
                "params": self._evidence_payload(context=context, mode="browser-cockpit-preflight"),
            },
            instance_json=instance_json,
        )
        self.assertFalse(issue["ok"])
        error = issue["error"]
        self.assertEqual(error["code"], "E_RUNTIME_BROKER")
        self.assertEqual(issue["permission_boundary"], "browser-cockpit-ready")
        self.assertEqual(issue["stop_condition"], "browser cockpit is not ready for MCP page operations")
        self.assertIn("env browser ensure", issue["command_hint"])
        self.assertEqual(self._evidence_token_paths(instance_json), [])

    def test_browser_preflight_repairs_intro_only_with_put_json_new(self) -> None:
        state = _CDPState(
            version_ok=True,
            pages=[{"id": "intro", "type": "page", "url": "chrome://intro/"}],
            allow_put_new_about_blank=True,
            allow_get_new_about_blank=False,
        )
        port = self._start_cdp_server(state)
        instance_json = self._instance_json(browser_port=port)
        context = self._prepare_market(instance_json=instance_json)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "env.tool",
                "params": self._evidence_payload(context=context, mode="browser-cockpit-preflight"),
            },
            instance_json=instance_json,
        )
        self.assertTrue(issue["ok"], msg=issue)
        calls = state.snapshot_calls()
        self.assertTrue(any(call["method"] == "PUT" and call["path"] == "/json/new" and call["query"] == "about:blank" for call in calls))
        self.assertFalse(any(call["method"] == "GET" and call["path"] == "/json/new" and call["query"] == "about:blank" for call in calls))

    def test_market_persist_with_browser_token_succeeds_and_records_audit(self) -> None:
        state = _CDPState(
            version_ok=True,
            pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
        )
        port = self._start_cdp_server(state)

        instance_json = self._instance_json(browser_port=port)
        context = self._prepare_market(instance_json=instance_json)
        artifact_id = self._seed_market_artifact()
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "env.tool",
                "params": self._evidence_payload(context=context, mode="browser-cockpit-preflight"),
            },
            instance_json=instance_json,
        )
        self.assertTrue(issue["ok"], msg=issue)
        token = issue["tool_evidence"]["browser_cockpit_token"]

        persisted = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "params": {
                    "context": context,
                    "result": _market_commit({"browser_cockpit_token": token}, artifact_ids=[artifact_id]),
                },
            },
            instance_json=instance_json,
        )
        self.assertTrue(persisted["ok"], msg=persisted)
        run_id = persisted["receipt"]["run_id"]
        run_payload = json.loads(
            self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(run_payload["tool_evidence"]["kind"], "browser-cockpit-preflight")
        self.assertEqual(run_payload["tool_evidence"]["token"], token)

    def test_browser_evidence_response_exposes_token_scope_and_persist_payload_hint(self) -> None:
        state = _CDPState(
            version_ok=True,
            pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
        )
        port = self._start_cdp_server(state)
        instance_json = self._instance_json(browser_port=port)
        context = self._prepare_market(instance_json=instance_json)
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "env.tool",
                "params": self._evidence_payload(context=context, mode="browser-cockpit-preflight"),
            },
            instance_json=instance_json,
        )
        self.assertTrue(issue["ok"], msg=issue)
        feedback = issue["feedback"]
        token_scope = feedback["token_scope"]
        self.assertEqual(token_scope["run_id"], context["run_envelope"]["run_id"])
        self.assertEqual(token_scope["context_revision"], context["context_revision"])
        self.assertEqual(token_scope["instance_id"], context["instance_id"])
        self.assertEqual(token_scope["buddy_id"], context["active_buddy"])
        self.assertIsNone(context.get("current_task_id"))
        self.assertIsNone(token_scope["task_id"])
        self.assertEqual(feedback["persist_field"], "tool_evidence.browser_cockpit_token")
        self.assertIn("persist_payload_hint", issue)
        self.assertEqual(issue["persist_payload_hint"]["tool_evidence_field"], "tool_evidence.browser_cockpit_token")

    def test_market_persist_with_token_for_other_run_rejects(self) -> None:
        state = _CDPState(
            version_ok=True,
            pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
        )
        port = self._start_cdp_server(state)

        instance_json = self._instance_json(browser_port=port)
        context_a = self._prepare_market(instance_json=instance_json)
        artifact_id = self._seed_market_artifact()
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "env.tool",
                "params": self._evidence_payload(context=context_a, mode="browser-cockpit-preflight"),
            },
            instance_json=instance_json,
        )
        token = issue["tool_evidence"]["browser_cockpit_token"]
        consumed_a = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "params": {
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
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "params": {
                    "context": context_b,
                    "result": _market_commit({"browser_cockpit_token": token}, artifact_ids=[artifact_id]),
                },
            },
            instance_json=instance_json,
        )
        self.assertFalse(rejected["ok"])
        self.assertIn("not issued by runtime broker", rejected["error"]["message"])
        self._assert_structured_options(rejected)
        self.assertEqual(self._state_snapshot(), before_rejected)

    def test_market_persist_with_handwritten_token_rejects_before_writes(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        artifact_id = self._seed_market_artifact()
        before = self._state_snapshot()
        rejected = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "params": {
                    "context": context,
                    "result": _market_commit(
                        {"browser_cockpit_token": "evidence-run-fake-handwritten"},
                        artifact_ids=[artifact_id],
                    ),
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
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "env.tool",
                "params": self._evidence_payload(context=context, mode="approved-downgrade", reason=" "),
            },
            instance_json=instance_json,
        )
        self.assertFalse(issue["ok"])
        self.assertIn("approved downgrade requires a non-empty reason", issue["error"]["message"])
        self.assertEqual(self._evidence_token_paths(instance_json), [])

    def test_market_persist_with_approved_downgrade_token_records_reason(self) -> None:
        instance_json = self._instance_json()
        context = self._prepare_market(instance_json=instance_json)
        artifact_id = self._seed_market_artifact()
        issue = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "env.tool",
                "params": self._evidence_payload(
                    context=context,
                    mode="approved-downgrade",
                    reason="Browser-native cockpit blocked; user approved one-off downgrade.",
                ),
            },
            instance_json=instance_json,
        )
        self.assertTrue(issue["ok"], msg=issue)
        token = issue["tool_evidence"]["approved_downgrade_token"]
        persisted = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-market-example",
                "active_buddy": "market",
                "method": "persist",
                "params": {
                    "context": context,
                    "result": _market_commit({"approved_downgrade_token": token}, artifact_ids=[artifact_id]),
                },
            },
            instance_json=instance_json,
        )
        self.assertTrue(persisted["ok"], msg=persisted)
        run_id = persisted["receipt"]["run_id"]
        run_payload = json.loads(
            self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(run_payload["tool_evidence"]["kind"], "approved-downgrade")
        self.assertIn("reason", run_payload["tool_evidence"])

    def test_pm_persist_does_not_require_tool_evidence(self) -> None:
        instance_json = self._instance_json(buddy="pm", instance_id="inst-pm-example")
        prepared = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-pm-example",
                "active_buddy": "pm",
                "method": "prepare",
                "params": {"text": PM_REQUEST},
            },
            instance_json=instance_json,
        )
        self.assertTrue(prepared["ok"], msg=prepared)
        persisted = self._dispatch(
            request={
                "protocol": "buddyswitch-runtime-broker/v2",
                "instance_id": "inst-pm-example",
                "active_buddy": "pm",
                "method": "persist",
                "params": {"context": prepared, "result": _pm_commit()},
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
                        "protocol": "buddyswitch-runtime-broker/v2",
                        "instance_id": instance_id,
                        "active_buddy": buddy,
                        "method": "prepare",
                        "params": {"text": request_text},
                    },
                    instance_json=instance_json,
                )
                self.assertTrue(prepared["ok"], msg=prepared)
                persisted = self._dispatch(
                    request={
                        "protocol": "buddyswitch-runtime-broker/v2",
                        "instance_id": instance_id,
                        "active_buddy": buddy,
                        "method": "persist",
                        "params": {"context": prepared, "result": commit_factory()},
                    },
                    instance_json=instance_json,
                )
                self.assertTrue(persisted["ok"], msg=persisted)


if __name__ == "__main__":
    unittest.main()
