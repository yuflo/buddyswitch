"""Response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sys
import threading
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

from tests.support.paths import REPO_ROOT
from tests.support.fake_cdp import (
    read_client_text_frame as _read_client_text_frame,
    websocket_accept_value as _websocket_accept_value,
    write_server_text_frame as _write_server_text_frame,
)

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.domain import task_sys  # noqa: E402
from env.repos import messages as message_repo  # noqa: E402
from env.services import messages as message_service  # noqa: E402
from env.tool_runtime import registry as tool_catalog  # noqa: E402
from env.tool_runtime import results as tool_results  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
import env.tools.search._impl as search_impl  # noqa: E402
import turn_runtime  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
def _make_cdp_handler(state: dict[str, object]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            state.setdefault("requests", []).append({"method": "GET", "path": self.path})
            parsed = urlparse(self.path)
            if parsed.path == "/json/list":
                payload = state.get("targets", [])
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
                return
            if parsed.path == "/json/version":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = {
                    "Browser": "test",
                    "webSocketDebuggerUrl": (
                        f"ws://127.0.0.1:{self.server.server_port}/devtools/browser/test"  # type: ignore[attr-defined]
                    ),
                }
                self.wfile.write(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
                return
            if parsed.path == "/devtools/browser/test":
                key = self.headers.get("Sec-WebSocket-Key")
                if not key:
                    self.send_response(400)
                    self.end_headers()
                    return
                self.send_response(101)
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", _websocket_accept_value(key))
                self.end_headers()
                message = json.loads(_read_client_text_frame(self.rfile))
                state.setdefault("rpc_requests", []).append(message)
                response = {"id": message.get("id"), "result": {"targetId": "target-search"}}
                _write_server_text_frame(self.wfile, json.dumps(response, ensure_ascii=True))
                return
            self.send_response(404)
            self.end_headers()

        def do_PUT(self) -> None:  # noqa: N802
            state.setdefault("requests", []).append({"method": "PUT", "path": self.path})
            self.send_response(500)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


class EnvToolResponseCase(RuntimeWorkspaceTestCase):
    _ACTION_PLACEHOLDERS = {
        "tbd",
        "todo",
        "n/a",
        "na",
        "none",
        "unknown",
        "placeholder",
    }

    def setUp(self) -> None:
        super().setUp()
        self._browser_open_results: list[dict[str, object]] = []
        had_browser_client = hasattr(search_impl, "browser_client")
        original_browser_client = getattr(search_impl, "browser_client", None)

        test_case = self

        class FakeBrowserClient:
            @staticmethod
            def open_url(**kwargs: object) -> dict[str, object]:
                if test_case._browser_open_results:
                    return dict(test_case._browser_open_results.pop(0))
                target_url = kwargs.get("target_url")
                return {
                    "ok": True,
                    "kind": "opened",
                    "target_url": target_url if isinstance(target_url, str) else "",
                    "page_count": 0,
                    "projected_page_count": 1,
                    "browser_page_count": 1,
                    "target_id": "target-search-contract",
                    "page_opened": True,
                    "page_reused": False,
                    "idle_refreshed": True,
                    "idle_seconds": 40,
                    "idle_expires_at": "2026-06-24T00:00:40Z",
                    "message": "opened",
                    "state_changed": True,
                    "durability": "runtime",
                }

        if had_browser_client:
            search_impl.browser_client = FakeBrowserClient
            self.addCleanup(setattr, search_impl, "browser_client", original_browser_client)

    @classmethod
    def _meaningful_text_entries(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        rows: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                continue
            normalized = entry.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in cls._ACTION_PLACEHOLDERS:
                continue
            rows.append(normalized)
        return rows

    @staticmethod
    def _meaningful_tool_action_options(value: object) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        rows: list[dict[str, str]] = []
        for entry in value:
            if not isinstance(entry, dict):
                continue
            tool = entry.get("tool")
            action = entry.get("action")
            if isinstance(tool, str) and tool.strip() and isinstance(action, str) and action.strip():
                rows.append({"tool": tool.strip(), "action": action.strip()})
        return rows

    def _assert_actionable_next_guidance(self, payload: dict[str, object]) -> None:
        meaningful_next_actions = self._meaningful_text_entries(payload.get("allowed_next_actions"))
        meaningful_next_options = self._meaningful_tool_action_options(payload.get("allowed_next_action_options"))
        has_next_actions = len(meaningful_next_actions) > 0
        has_next_options = len(meaningful_next_options) > 0
        self.assertTrue(has_next_actions or has_next_options, msg=payload)

    def _instance_json(self, *, role: str, actor_id: str) -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        path = self._runtime_path(f"instances/{actor_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-18T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._seed_active_task(instance_json=path, role=role, actor_id=actor_id)
        return path

    def _seed_active_task(self, *, instance_json: Path, role: str, actor_id: str) -> None:
        task_id = f"task-0001-{role}-response-contract"
        task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": role},
            demand_ref={
                "demand_id": f"demand-response-contract-{role}",
                "basis_revision": 1,
                "demand_ref": f"dref-response-contract-{role}",
            },
            objective=f"Exercise response contracts for {task_id}.",
            selection_reason="The response-contract fixture requires one active Task.",
        )

    def _dispatch(
        self,
        *,
        instance_json: Path,
        actor_id: str,
        role: str,
        tool: str,
        action: str,
        args: dict[str, object],
        invocation: dict[str, str] | None = None,
    ) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-response-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "actor_id": actor_id,
                    "active_role": role,
                    "tool": tool,
                    "action": action,
                    "args": args,
                    **({"invocation": invocation} if invocation is not None else {}),
                },
                "deadline_ms": 35000,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
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

    def _start_cdp_server(self, state: dict[str, object]) -> tuple[HTTPServer, threading.Thread, int]:
        server = HTTPServer(("127.0.0.1", 0), _make_cdp_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return server, thread, int(server.server_port)

    def _assert_rejection_contract(self, payload: dict[str, object]) -> None:
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertIsInstance(payload.get("permission_boundary"), str, msg=payload)
        self.assertTrue(str(payload.get("permission_boundary", "")).strip(), msg=payload)
        self.assertIsInstance(payload.get("why_blocked"), str, msg=payload)
        self.assertTrue(str(payload.get("why_blocked", "")).strip(), msg=payload)
        self.assertIsInstance(payload.get("impact"), str, msg=payload)
        self.assertTrue(str(payload.get("impact", "")).strip(), msg=payload)
        self.assertIsInstance(payload.get("retryable"), bool, msg=payload)
        self.assertIsInstance(payload.get("retry_guidance"), str, msg=payload)
        self.assertTrue(str(payload.get("retry_guidance", "")).strip(), msg=payload)
        self.assertIn("allowed_next_actions", payload, msg=payload)
        self.assertIsInstance(payload.get("allowed_next_actions"), list, msg=payload)
        if "allowed_next_action_options" in payload:
            self.assertIsInstance(payload.get("allowed_next_action_options"), list, msg=payload)
        next_actions = self._meaningful_text_entries(payload.get("allowed_next_actions"))
        next_options = self._meaningful_tool_action_options(payload.get("allowed_next_action_options"))
        self.assertTrue(
            bool(next_actions) or bool(next_options),
            msg=payload,
        )
        self.assertEqual(payload.get("state_changed"), False, msg=payload)
        self.assertEqual(payload.get("durability"), "none", msg=payload)

    def _assert_success_contract(self, payload: dict[str, object]) -> None:
        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertIsInstance(payload.get("effect_summary"), str, msg=payload)
        self.assertIsInstance(payload.get("state_changed"), bool, msg=payload)
        self.assertIsInstance(payload.get("durability"), str, msg=payload)

    def _assert_write_success_contract(self, payload: dict[str, object]) -> None:
        self._assert_success_contract(payload)
        self.assertTrue(payload.get("state_changed"), msg=payload)
        self.assertIsInstance(payload.get("state_changes"), list, msg=payload)
        self.assertGreater(len(payload.get("state_changes", [])), 0, msg=payload)
        self.assertNotEqual(payload.get("durability"), "none", msg=payload)
        self._assert_actionable_next_guidance(payload)

    def _assert_no_retired_task_sys_fields(self, payload: dict[str, object]) -> None:
        for field in ("active_processor", "side_result", "parent_handoff_params", "failure_result", "close_result"):
            with self.subTest(field=field):
                self.assertNotIn(field, payload, msg=payload)

    def _assert_success_matches_declared_action_semantics(self, action_key: str, payload: dict[str, object]) -> None:
        self._assert_success_contract(payload)
        semantics = tool_catalog.operation_semantics()[action_key]
        self.assertEqual(payload.get("durability"), semantics["durability"], msg=payload)
        if semantics["durability"] == "none":
            self.assertFalse(payload.get("state_changed"), msg=payload)
        else:
            self.assertTrue(payload.get("state_changed"), msg=payload)
            self.assertIsInstance(payload.get("state_changes"), list, msg=payload)
            self.assertGreater(len(payload.get("state_changes", [])), 0, msg=payload)
        if semantics["mutates"] == "runtime_objects":
            self.assertTrue(payload.get("created_ids") or payload.get("updated_ids") or payload.get("state_changes"), msg=payload)
        if semantics["mutates"] == "runtime_files":
            self.assertIn("private_file", json.dumps(payload.get("state_changes", [])), msg=payload)
        if semantics["mutates"] == "broker_token":
            self.assertFalse(payload.get("mutates_product_state"), msg=payload)
            self.assertIn("token", json.dumps(payload.get("state_changes", [])), msg=payload)
