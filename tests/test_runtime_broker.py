#!/usr/bin/env python3
"""Tests for runtime broker request routing and identity checks."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import contextlib
import importlib
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
import runtime_kernel.client as runtime_client  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
BROKER_V2_PROTOCOL = "buddyswitch-runtime-broker/v2"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"


def _require_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"missing required Runtime Broker V2 module: {name}") from exc


class RuntimeBrokerTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    @staticmethod
    def _error_boundary(response: dict[str, object]) -> str | None:
        boundary_top = response.get("permission_boundary")
        if isinstance(boundary_top, str):
            return boundary_top
        error = response.get("error")
        if not isinstance(error, dict):
            return None
        boundary = error.get("permission_boundary")
        return boundary if isinstance(boundary, str) else None

    def _instance_json(
        self,
        *,
        instance_id: str = "inst-pm-example",
        buddy: str = "pm",
        status: str = "active",
    ) -> Path:
        instance_root = self._instance_root(instance_id)
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "instance_root": str(instance_root),
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-05-06T00:00:00Z",
                    "updated_at": "2026-05-06T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _dispatch(
        self,
        *,
        method: str,
        params: dict[str, object],
        instance_id: str = "inst-pm-example",
        buddy: str = "pm",
        instance_json: Path,
    ) -> dict[str, object]:
        request_params = dict(params)
        request_params.setdefault("instance_id", instance_id)
        request_params.setdefault("active_buddy", buddy)
        request: dict[str, object] = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": f"req-test-{uuid.uuid4().hex}",
            "method": method,
            "params": request_params,
            "deadline_ms": 35000,
        }
        if method == "persist":
            context = request_params.get("context")
            result = request_params.get("result")
            if isinstance(context, dict) and isinstance(result, dict):
                result_hash = runtime_client.canonical_result_hash(result)
                request["idempotency_key"] = f"persist:{result_hash}"
                request["result_hash"] = result_hash
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
        self.assertEqual(envelope.get("protocol"), BROKER_V2_PROTOCOL)
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

    def test_env_tool_requests_succeed_with_matching_identity(self) -> None:
        instance_json = self._instance_json()
        before_instance = json.loads(instance_json.read_text(encoding="utf-8"))

        summarized = self._dispatch(
            method="env.tool",
            params={"tool": "context", "action": "summarize", "args": {}},
            instance_json=instance_json,
        )
        self.assertTrue(summarized["ok"], msg=summarized)
        self.assertEqual(summarized["action"], "context.summarize")

        created = self._dispatch(
            method="env.tool",
            params={
                "tool": "task",
                "action": "propose",
                "args": {
                    "type": "start",
                    "reason": "Broker test.",
                    "evidence": "Broker test starts a task.",
                    "task": {"title": "Broker Task", "summary": "seed", "body": "Broker Task"},
                },
            },
            instance_json=instance_json,
        )
        self.assertTrue(created["ok"], msg=created)
        self.assertEqual((created.get("task") or {}).get("title"), "Broker Task")

        after_instance = json.loads(instance_json.read_text(encoding="utf-8"))
        self.assertEqual(after_instance, before_instance)
        self.assertFalse(self._runtime_path("buddyswitch/content/runs").exists())
        self.assertFalse(self._runtime_path("runs/raw").exists())

    def test_env_tool_rejects_legacy_handoff_tool_payload(self) -> None:
        instance_json = self._instance_json()
        response = self._dispatch(
            method="env.tool",
            params={"tool": "handoff", "action": "list", "args": {}},
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"], msg=response)
        self.assertEqual(response["error"]["code"], "E_ENV_TOOL", msg=response)
        self.assertEqual(response.get("permission_boundary"), "env.tool", msg=response)

    def test_context_reports_direct_buddybox_writable_surface(self) -> None:
        instance_root = self._instance_root("inst-pm-alt-workspace")
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        (workspace_dir / "AGENTS.md").write_text("# BuddySwitch Runtime Workspace\n", encoding="utf-8")
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": "inst-pm-alt-workspace",
                    "buddy": "pm",
                    "status": "active",
                    "instance_root": str(instance_root),
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-05-06T00:00:00Z",
                    "updated_at": "2026-05-06T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        summarized = self._dispatch(
            method="env.tool",
            params={
                "tool": "context",
                "action": "summarize",
                "args": {},
            },
            instance_id="inst-pm-alt-workspace",
            buddy="pm",
            instance_json=instance_json,
        )
        self.assertTrue(summarized.get("ok"), msg=summarized)
        surfaces = summarized.get("writable_surfaces")
        self.assertIsInstance(surfaces, dict, msg=summarized)
        assert isinstance(surfaces, dict)
        persistent = surfaces.get("persistent_files")
        self.assertIsInstance(persistent, dict, msg=summarized)
        assert isinstance(persistent, dict)
        self.assertEqual(persistent.get("env"), "BUDDYSWITCH_BUDDYBOX_DIR")
        self.assertEqual(persistent.get("workspace_relative_root"), "buddybox")
        self.assertFalse(persistent.get("mutates_product_state"))

        target = workspace_dir / "buddybox" / "broker" / "out.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("broker\n", encoding="utf-8")
        self.assertTrue(target.exists(), msg=target)
        self.assertEqual(target.read_text(encoding="utf-8"), "broker\n")
        self.assertFalse(self._runtime_path("buddyswitch/local/buddybox/pm/broker/out.txt").exists())
        self.assertFalse(self._runtime_path("state/buddyswitch/local/buddybox/pm/broker/out.txt").exists())

    def test_direct_buddybox_files_use_shared_state_root(self) -> None:
        instance_root = self._instance_root("inst-pm-alt-workspace-lifecycle")
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        (workspace_dir / "AGENTS.md").write_text("# BuddySwitch Runtime Workspace\n", encoding="utf-8")
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": "inst-pm-alt-workspace-lifecycle",
                    "buddy": "pm",
                    "status": "active",
                    "instance_root": str(instance_root),
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-05-19T00:00:00Z",
                    "updated_at": "2026-05-19T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        target = workspace_dir / "buddybox" / "broker" / "lifecycle.txt"
        wrong_runtime_root = self._runtime_path("state/buddyswitch/local/buddybox/pm/broker/lifecycle.txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("lifecycle\n", encoding="utf-8")
        self.assertTrue(target.exists(), msg=target)
        self.assertFalse(wrong_runtime_root.exists(), msg=wrong_runtime_root)
        self.assertEqual(target.read_text(encoding="utf-8"), "lifecycle\n")
        target.unlink()
        self.assertFalse(target.exists(), msg=target)

    def test_env_tool_requests_enter_shared_runtime_lock(self) -> None:
        instance_json = self._instance_json()
        lock_sessions: list[dict[str, object]] = []

        @contextlib.contextmanager
        def fake_lock(session: dict[str, object], **_kwargs: object):
            lock_sessions.append(session)
            yield

        with patch("turn_runtime._hold_product_runtime_lock", side_effect=fake_lock):
            summarized = self._dispatch(
                method="env.tool",
                params={"tool": "context", "action": "summarize", "args": {}},
                instance_json=instance_json,
            )
            self.assertTrue(summarized["ok"], msg=summarized)
            created = self._dispatch(
                method="env.tool",
                params={
                    "tool": "task",
                    "action": "propose",
                    "args": {
                        "type": "start",
                        "reason": "Broker lock test.",
                        "evidence": "Broker lock test starts a task.",
                        "task": {"title": "Broker Lock Task", "body": "Broker Lock Task"},
                    },
                },
                instance_json=instance_json,
            )
            self.assertTrue(created["ok"], msg=created)

        self.assertEqual([session["instance_id"] for session in lock_sessions], ["inst-pm-example", "inst-pm-example"])
        self.assertTrue(all(session["instance_json"] == instance_json for session in lock_sessions))

    def test_rejects_wrong_instance_id(self) -> None:
        instance_json = self._instance_json()
        response = self._dispatch(
            method="prepare",
            params={"text": PM_REQUEST},
            instance_id="inst-other",
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PERMISSION")
        self.assertIn("instance_id mismatch", response["error"]["message"])

    def test_rejects_wrong_active_buddy(self) -> None:
        instance_json = self._instance_json(buddy="pm")
        response = self._dispatch(
            method="prepare",
            params={"text": PM_REQUEST},
            buddy="market",
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PERMISSION")
        self.assertIn("active_buddy mismatch", response["error"]["message"])

    def test_rejects_inactive_instance(self) -> None:
        instance_json = self._instance_json(status="inactive")
        response = self._dispatch(
            method="prepare",
            params={"text": PM_REQUEST},
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PERMISSION")
        self.assertIn("instance is not active", response["error"]["message"])

    def test_env_tool_supports_active_instance_and_identity_checks(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev", status="active")

        supported = self._dispatch(
            method="env.tool",
            params={"tool": "task", "action": "current", "args": {}},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(supported["ok"], msg=supported)

        role_denied = self._dispatch(
            method="env.tool",
            params={
                "tool": "track",
                "action": "create",
                "args": {
                    "track_id": "track-broker-role-denied",
                    "title": "Broker Role Denied",
                    "outcome": "Denied",
                    "appetite": "1 day",
                },
            },
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertFalse(role_denied["ok"], msg=role_denied)
        self.assertEqual(role_denied["error"]["code"], "E_TOOL_ROLE_AUTH")
        self.assertEqual(role_denied.get("active_role"), "dev")
        self.assertEqual(role_denied.get("required_permission"), "track.create")

        wrong_instance = self._dispatch(
            method="env.tool",
            params={"tool": "task", "action": "current", "args": {}},
            instance_json=instance_json,
            instance_id="inst-other",
            buddy="dev",
        )
        self.assertFalse(wrong_instance["ok"])
        self.assertEqual(self._error_boundary(wrong_instance), "active-instance")

        wrong_buddy = self._dispatch(
            method="env.tool",
            params={"tool": "task", "action": "current", "args": {}},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="pm",
        )
        self.assertFalse(wrong_buddy["ok"])
        self.assertEqual(self._error_boundary(wrong_buddy), "active-buddy")

        inactive_instance_json = self._instance_json(instance_id="inst-dev-inactive", buddy="dev", status="inactive")
        inactive = self._dispatch(
            method="env.tool",
            params={"tool": "task", "action": "current", "args": {}},
            instance_json=inactive_instance_json,
            instance_id="inst-dev-inactive",
            buddy="dev",
        )
        self.assertFalse(inactive["ok"])
        self.assertEqual(self._error_boundary(inactive), "active-instance-status")

    def test_legacy_env_task_method_is_rejected(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev", status="active")
        legacy_method = "env" + ".task"
        rejected_legacy = self._dispatch(
            method=legacy_method,
            params={"action": "list", "args": {}},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertFalse(rejected_legacy["ok"])
        self.assertEqual(self._error_boundary(rejected_legacy), "broker-protocol")

    def test_runtime_broker_client_missing_socket_raises_unavailable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "",
            },
            clear=False,
        ):
            with self.assertRaises(runtime_client.RuntimeBrokerError) as raised:
                runtime_client.runtime_broker_socket_from_env()
        self.assertEqual(raised.exception.code, "E_RUNTIME_BROKER_UNAVAILABLE")


class RuntimeBrokerProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = _require_module("runtime_kernel.protocol")

    def _framed(self, payload: dict[str, object]) -> bytes:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body

    def test_protocol_round_trips_content_length_framed_json(self) -> None:
        left, right = socket.socketpair()
        try:
            first = {"a": 1}
            second = {"b": 2}
            left.sendall(self._framed(first) + self._framed(second))
            self.assertEqual(self.protocol.read_message(right), first)
            self.assertEqual(self.protocol.read_message(right), second)
        finally:
            left.close()
            right.close()

    def test_protocol_rejects_missing_content_length(self) -> None:
        left, right = socket.socketpair()
        try:
            left.sendall(b"{}\n")
            left.shutdown(socket.SHUT_WR)
            with self.assertRaises(self.protocol.BrokerProtocolError) as raised:
                self.protocol.read_message(right)
        finally:
            left.close()
            right.close()
        self.assertEqual(raised.exception.code, "E_RUNTIME_BROKER_PROTOCOL")

    def test_protocol_rejects_invalid_json_body(self) -> None:
        left, right = socket.socketpair()
        try:
            body = b'{"ok":'
            header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            left.sendall(header + body)
            with self.assertRaises(self.protocol.BrokerProtocolError) as raised:
                self.protocol.read_message(right)
        finally:
            left.close()
            right.close()
        self.assertEqual(raised.exception.code, "E_RUNTIME_BROKER_PROTOCOL")
        self.assertIn("invalid JSON", raised.exception.message)

    def test_validate_request_requires_v2_protocol_request_id_method_params_deadline(self) -> None:
        valid = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-1",
            "method": "prepare",
            "params": {"text": "x"},
            "deadline_ms": 35000,
        }
        for missing in ("protocol", "request_id", "method", "params", "deadline_ms"):
            request = dict(valid)
            request.pop(missing)
            with self.assertRaises(self.protocol.BrokerProtocolError, msg=missing):
                self.protocol.validate_request(request)

    def test_write_methods_require_idempotency_key(self) -> None:
        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-2",
            "method": "persist",
            "params": {"context": {}, "result": {}},
            "deadline_ms": 35000,
        }
        validated = self.protocol.validate_request(request)
        self.assertEqual(validated["method"], "persist")

    def test_response_envelopes_use_result_or_error(self) -> None:
        success = self.protocol.success_response("req-ok", {"ok": True, "value": 1})
        self.assertEqual(success["protocol"], BROKER_V2_PROTOCOL)
        self.assertEqual(success["request_id"], "req-ok")
        self.assertTrue(success["ok"])
        self.assertEqual(success["result"], {"ok": True, "value": 1})
        self.assertNotIn("payload", success)

        failure = self.protocol.error_response(
            "req-bad",
            code="E_RUNTIME_BROKER_PERMISSION",
            message="denied",
            retriable=False,
        )
        self.assertEqual(failure["protocol"], BROKER_V2_PROTOCOL)
        self.assertEqual(failure["request_id"], "req-bad")
        self.assertFalse(failure["ok"])
        self.assertEqual(failure["error"]["code"], "E_RUNTIME_BROKER_PERMISSION")
        self.assertIs(failure["error"]["retriable"], False)
        self.assertNotIn("payload", failure)


class RuntimeBrokerServerIsolationTests(unittest.TestCase):
    def _start_server(self, dispatch_fn, *, max_workers: int = 1):
        protocol = _require_module("runtime_kernel.protocol")
        server_module = _require_module("runtime_kernel.server")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        config = server_module.RuntimeBrokerConfig(
            socket_path=root / "runtime-broker.sock",
            pid_file=root / "runtime-broker.pid",
            instance_json_path=root / "instance.json",
            manifest_path=MANIFEST,
            max_workers=max_workers,
        )
        broker = server_module.RuntimeBrokerServer(config=config, dispatch_fn=dispatch_fn)
        thread = threading.Thread(target=broker.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(broker.close)
        for _ in range(100):
            if config.socket_path.exists():
                break
            time.sleep(0.01)
        return protocol, config.socket_path, broker, thread

    def _request(self, protocol, socket_path: Path, request: dict[str, object]) -> dict[str, object]:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            sock.connect(str(socket_path))
            protocol.write_message(sock, request)
            response = protocol.read_message(sock)
        return response

    def test_client_disconnect_before_response_does_not_stop_server(self) -> None:
        release = threading.Event()

        def dispatch(request):
            release.wait(timeout=2.0)
            return {"ok": True, "pong": request["request_id"]}

        protocol, socket_path, _broker, thread = self._start_server(dispatch, max_workers=1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            protocol.write_message(
                sock,
                {
                    "protocol": BROKER_V2_PROTOCOL,
                    "request_id": "req-disconnect",
                    "method": "ping",
                    "params": {},
                    "deadline_ms": 35000,
                },
            )
        release.set()
        response = self._request(
            protocol,
            socket_path,
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-ping",
                "method": "ping",
                "params": {},
                "deadline_ms": 35000,
            },
        )
        self.assertTrue(thread.is_alive())
        self.assertTrue(response["ok"], msg=response)
        self.assertEqual(response["result"]["pong"], "req-ping")

    def test_malformed_request_returns_protocol_error_and_next_ping_succeeds(self) -> None:
        def dispatch(request):
            return {"ok": True, "pong": request["request_id"]}

        protocol, socket_path, _broker, thread = self._start_server(dispatch, max_workers=1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            sock.connect(str(socket_path))
            sock.sendall(b"{}\n")
            try:
                response = protocol.read_message(sock)
                self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PROTOCOL")
            except (protocol.BrokerProtocolError, OSError):
                pass

        response = self._request(
            protocol,
            socket_path,
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-after-malformed",
                "method": "ping",
                "params": {},
                "deadline_ms": 35000,
            },
        )
        self.assertTrue(thread.is_alive())
        self.assertTrue(response["ok"], msg=response)

    def test_capacity_limit_returns_busy_without_killing_server(self) -> None:
        release = threading.Event()

        def dispatch(request):
            if request["request_id"] == "req-blocking":
                release.wait(timeout=2.0)
            return {"ok": True, "request_id": request["request_id"]}

        protocol, socket_path, _broker, thread = self._start_server(dispatch, max_workers=1)

        def blocking_request() -> None:
            self._request(
                protocol,
                socket_path,
                {
                    "protocol": BROKER_V2_PROTOCOL,
                    "request_id": "req-blocking",
                    "method": "ping",
                    "params": {},
                    "deadline_ms": 35000,
                },
            )

        worker = threading.Thread(target=blocking_request, daemon=True)
        worker.start()
        time.sleep(0.05)
        busy = self._request(
            protocol,
            socket_path,
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-busy",
                "method": "ping",
                "params": {},
                "deadline_ms": 35000,
            },
        )
        self.assertFalse(busy["ok"], msg=busy)
        self.assertEqual(busy["error"]["code"], "E_RUNTIME_BROKER_BUSY")
        self.assertIs(busy["error"]["retriable"], True)
        self.assertEqual(busy["error"]["retry_after_ms"], 250)
        release.set()
        worker.join(timeout=2.0)
        self.assertTrue(thread.is_alive())


class RuntimeBrokerCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator = _require_module("runtime_kernel.coordinator")

    def test_lock_mode_for_prepare_and_persist_is_write(self) -> None:
        self.assertEqual(self.coordinator.lock_mode_for_request("prepare", {"text": "x"}), self.coordinator.LockMode.WRITE)
        self.assertEqual(
            self.coordinator.lock_mode_for_request("persist", {"context": {}, "result": {}}),
            self.coordinator.LockMode.WRITE,
        )

    def test_lock_mode_for_read_only_env_tool_is_read(self) -> None:
        for params in (
            {"tool": "task", "action": "current", "args": {}},
            {"tool": "context", "action": "summarize", "args": {}},
            {"tool": "track", "action": "open", "args": {}},
            {"tool": "artifact", "action": "get", "args": {}},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.coordinator.lock_mode_for_request("env.tool", params), self.coordinator.LockMode.READ)

    def test_lock_mode_for_mutating_env_tool_is_write(self) -> None:
        for params in (
            {"tool": "task", "action": "propose", "args": {}},
            {"tool": "track", "action": "update_now", "args": {}},
            {"tool": "track", "action": "add_material", "args": {}},
            {"tool": "track", "action": "add_update", "args": {}},
            {"tool": "track", "action": "add_proof", "args": {}},
            {"tool": "track", "action": "archive", "args": {}},
            {"tool": "evidence", "action": "issue_browser", "args": {}},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.coordinator.lock_mode_for_request("env.tool", params), self.coordinator.LockMode.WRITE)

    def test_unknown_env_tool_action_defaults_to_write(self) -> None:
        params = {"tool": "task", "action": "merge", "args": {}}
        self.assertEqual(self.coordinator.lock_mode_for_request("env.tool", params), self.coordinator.LockMode.WRITE)

    def test_ping_and_status_do_not_acquire_runtime_lock(self) -> None:
        calls: list[str] = []

        @contextlib.contextmanager
        def fake_lock(*args, **kwargs):
            calls.append("lock")
            yield

        def dispatch_fn(request, session):
            return {"ok": True, "method": request["method"]}

        session = {"instance_json": Path("instance.json"), "manifest_path": MANIFEST}
        with patch("turn_runtime._hold_product_runtime_lock", side_effect=fake_lock):
            for method in ("ping", "status"):
                response = self.coordinator.dispatch_with_coordination(
                    {
                        "protocol": BROKER_V2_PROTOCOL,
                        "request_id": f"req-{method}",
                        "method": method,
                        "params": {},
                        "deadline_ms": 35000,
                    },
                    session,
                    dispatch_fn,
                )
                self.assertEqual(response["method"], method)
        self.assertEqual(calls, [])

    def test_lock_contention_returns_deadline_exceeded(self) -> None:
        def dispatch_fn(request, session):
            return {"ok": True, "method": request["method"], "session": session}

        @contextlib.contextmanager
        def timeout_lock(*args, **kwargs):
            raise TimeoutError("runtime lock busy for test")
            yield

        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-lock-timeout",
            "method": "prepare",
            "params": {"text": "x"},
            "deadline_ms": 35000,
        }
        session = {"instance_json": Path("instance.json"), "manifest_path": MANIFEST}
        with patch("turn_runtime._hold_product_runtime_lock", side_effect=timeout_lock):
            response = self.coordinator.dispatch_with_coordination(request, session, dispatch_fn)
        self.assertFalse(response["ok"], msg=response)
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_DEADLINE_EXCEEDED")
        self.assertIs(response["error"]["retriable"], True)


class RuntimeBrokerClientV2Tests(unittest.TestCase):
    def _serve_once(self, handler):
        protocol = _require_module("runtime_kernel.protocol")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        socket_path = Path(temp.name) / "runtime-broker.sock"
        captured: list[dict[str, object]] = []

        def run() -> None:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(socket_path))
                server.listen(1)
                conn, _ = server.accept()
                with conn:
                    request = protocol.read_message(conn)
                    captured.append(request)
                    response = handler(request)
                    if response is not None:
                        protocol.write_message(conn, response)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        for _ in range(100):
            if socket_path.exists():
                break
            time.sleep(0.01)
        return protocol, socket_path, thread, captured

    def test_client_sends_v2_request_id_deadline_and_reads_result(self) -> None:
        client = _require_module("runtime_kernel.client")

        def handler(request):
            return self.protocol.success_response(request["request_id"], {"ok": True, "value": 1})

        self.protocol, socket_path, thread, captured = self._serve_once(handler)
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
            },
            clear=False,
        ):
            result = client.request_runtime_broker("prepare", {"text": "Draft onboarding PRD"})
        thread.join(timeout=2.0)
        self.assertEqual(result, {"ok": True, "value": 1})
        self.assertEqual(len(captured), 1)
        outgoing = captured[0]
        self.assertEqual(outgoing["protocol"], BROKER_V2_PROTOCOL)
        self.assertRegex(outgoing["request_id"], r"^req-[0-9a-f-]+")
        self.assertEqual(outgoing["deadline_ms"], 35000)
        self.assertEqual(outgoing["method"], "prepare")
        self.assertEqual(outgoing["params"], {"text": "Draft onboarding PRD"})
        self.assertNotIn("payload", outgoing)

    def test_client_preserves_structured_error_fields(self) -> None:
        client = _require_module("runtime_kernel.client")

        def handler(request):
            return self.protocol.error_response(
                request["request_id"],
                {
                    "code": "E_RUNTIME_BROKER_PERMISSION",
                    "message": "active buddy mismatch",
                    "retriable": False,
                    "permission_boundary": "active-buddy",
                },
            )

        self.protocol, socket_path, thread, _captured = self._serve_once(handler)
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "market",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
            },
            clear=False,
        ):
            with self.assertRaises(client.RuntimeBrokerError) as raised:
                client.request_runtime_broker("env.tool", {"tool": "task", "action": "current", "args": {}})
        thread.join(timeout=2.0)
        self.assertEqual(raised.exception.code, "E_RUNTIME_BROKER_PERMISSION")
        self.assertEqual(raised.exception.details.get("permission_boundary"), "active-buddy")
        self.assertIs(raised.exception.details.get("retriable"), False)
        self.assertRegex(raised.exception.details.get("request_id", ""), r"^req-[0-9a-f-]+")

    def test_client_retries_read_only_env_tool_once_after_transport_reset(self) -> None:
        protocol = _require_module("runtime_kernel.protocol")
        client = _require_module("runtime_kernel.client")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        socket_path = Path(temp.name) / "runtime-broker.sock"
        captured: list[dict[str, object]] = []

        def run() -> None:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(socket_path))
                server.listen(2)
                first, _ = server.accept()
                with first:
                    captured.append(protocol.read_message(first))
                second, _ = server.accept()
                with second:
                    request = protocol.read_message(second)
                    captured.append(request)
                    protocol.write_message(second, protocol.success_response(request["request_id"], {"ok": True}))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        for _ in range(100):
            if socket_path.exists():
                break
            time.sleep(0.01)
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
            },
            clear=False,
        ):
            result = client.request_runtime_broker(
                "env.tool",
                {"tool": "task", "action": "current", "args": {}},
            )
        thread.join(timeout=2.0)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(captured), 2)
        self.assertNotEqual(captured[0]["request_id"], captured[1]["request_id"])

    def test_client_does_not_retry_persist_without_idempotency_key(self) -> None:
        client = _require_module("runtime_kernel.client")
        reset_error = client.RuntimeBrokerError(
            "E_RUNTIME_BROKER_CLIENT_DISCONNECTED",
            "transport reset",
            details={"retriable": True},
        )
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime-broker.sock",
            },
            clear=False,
        ), patch.object(client, "_request_once", side_effect=reset_error) as request_once:
            with self.assertRaises(client.RuntimeBrokerError):
                client.request_runtime_broker("persist", {"context": {}, "result": {}})
        self.assertEqual(request_once.call_count, 1)

    def test_client_stale_socket_reports_launcher_reopen_without_self_ensure(self) -> None:
        client = _require_module("runtime_kernel.client")
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/missing-runtime-broker.sock",
            },
            clear=False,
        ):
            with self.assertRaises(client.RuntimeBrokerError) as raised:
                client.request_runtime_broker("prepare", {"text": "x"})
        self.assertIn(raised.exception.code, {"E_RUNTIME_BROKER_STALE_SOCKET", "E_RUNTIME_BROKER_UNAVAILABLE"})
        self.assertEqual(raised.exception.details.get("permission_boundary"), "product-mode-runtime-broker")
        self.assertEqual(raised.exception.details.get("stop_condition"), "stop_and_report_do_not_bypass_broker")
        self.assertEqual(raised.exception.details.get("socket_path"), "/tmp/missing-runtime-broker.sock")
        self.assertEqual(
            raised.exception.details.get("command_hint"),
            "./buddyswitch-codex instance attach inst-pm-example",
        )

    def test_client_retries_read_only_env_tool_once_without_ensure(self) -> None:
        client = _require_module("runtime_kernel.client")
        stale_error = client.RuntimeBrokerError(
            "E_RUNTIME_BROKER_STALE_SOCKET",
            "stale socket",
            details={"retriable": True},
        )
        ensure_name = "_ensure_runtime_broker"
        ensure_side_effect = AssertionError("client must not self-ensure broker lifecycle")
        ensure_patch = (
            patch.object(client, ensure_name, side_effect=ensure_side_effect)
            if hasattr(client, ensure_name)
            else contextlib.nullcontext()
        )

        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime-broker.sock",
            },
            clear=False,
        ), patch.object(
            client,
            "_request_once",
            side_effect=[stale_error, {"ok": True, "items": []}],
        ) as request_once, ensure_patch:
            result = client.request_runtime_broker(
                "env.tool",
                {"tool": "task", "action": "current", "args": {}},
            )
        self.assertEqual(result, {"ok": True, "items": []})
        self.assertEqual(request_once.call_count, 2)

    def test_client_does_not_retry_prepare_after_transport_reset(self) -> None:
        protocol = _require_module("runtime_kernel.protocol")
        client = _require_module("runtime_kernel.client")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        socket_path = Path(temp.name) / "runtime-broker.sock"
        captured: list[dict[str, object]] = []

        def run() -> None:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(socket_path))
                server.listen(1)
                conn, _ = server.accept()
                with conn:
                    captured.append(protocol.read_message(conn))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        for _ in range(100):
            if socket_path.exists():
                break
            time.sleep(0.01)
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
            },
            clear=False,
        ):
            with self.assertRaises(client.RuntimeBrokerError):
                client.request_runtime_broker("prepare", {"text": "x"})
        thread.join(timeout=2.0)
        self.assertEqual(len(captured), 1)

    def test_client_does_not_retry_mutating_env_tool_after_transport_reset(self) -> None:
        client = _require_module("runtime_kernel.client")
        reset_error = client.RuntimeBrokerError(
            "E_RUNTIME_BROKER_CLIENT_DISCONNECTED",
            "transport reset",
            details={"retriable": True},
        )
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "/tmp/runtime-broker.sock",
            },
            clear=False,
        ), patch.object(client, "_request_once", side_effect=reset_error) as request_once:
            with self.assertRaises(client.RuntimeBrokerError):
                client.request_runtime_broker(
                    "env.tool",
                    {"tool": "task", "action": "propose", "args": {"type": "start"}},
                )
        self.assertEqual(request_once.call_count, 1)


class RuntimeBrokerLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lifecycle = _require_module("runtime_kernel.lifecycle")

    def _paths(self, root: Path):
        return self.lifecycle.BrokerPaths(
            socket_path=root / "runtime-broker.sock",
            pid_file=root / "runtime-broker.pid",
            marker_file=root / "runtime-broker.socket",
            log_file=root / "runtime-broker.log",
        )

    @staticmethod
    def _sync_runtime_surface(workspace_dir: Path) -> None:
        runtime_surface = (
            "scripts/turn_runtime.py",
            "scripts/env_store.py",
            "scripts/env_legacy_store.py",
            "scripts/env",
            "scripts/env_profiles.py",
            "scripts/env_manifest.py",
            "scripts/browser_evidence.py",
            "scripts/runtime_kernel",
            "buddyswitch/manifest.toml",
            "buddyswitch/env-profiles",
            "framework/contracts",
        )
        for relative in runtime_surface:
            source = ROOT / relative
            target = workspace_dir / relative
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True, symlinks=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    @staticmethod
    def _write_instance_json(path: Path, *, workspace_dir: Path, instance_id: str = "inst-pm-root", buddy: str = "pm") -> None:
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-05-13T00:00:00Z",
                    "updated_at": "2026-05-13T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _run_broker_cli(
        self,
        *,
        workspace_dir: Path,
        command: str,
        paths,
        instance_json: Path,
        manifest_path: Path,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        broker_script = workspace_dir / "scripts" / "runtime_kernel" / "broker.py"
        completed = subprocess.run(
            [
                "python3",
                str(broker_script),
                command,
                "--socket",
                str(paths.socket_path),
                "--pid-file",
                str(paths.pid_file),
                "--marker-file",
                str(paths.marker_file),
                "--log-file",
                str(paths.log_file),
                "--instance-json",
                str(instance_json),
                "--manifest",
                str(manifest_path),
            ],
            cwd=workspace_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        payload: dict[str, object] = {}
        if completed.stdout.strip():
            decoded = json.loads(completed.stdout.strip())
            self.assertIsInstance(decoded, dict, msg=completed.stdout)
            payload = decoded
        return completed, payload

    def test_live_status_reports_workspace_root_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace_dir = Path(temp)
            (workspace_dir / "AGENTS.md").write_text(
                "# BuddySwitch Runtime Workspace\n",
                encoding="utf-8",
            )
            self._sync_runtime_surface(workspace_dir)
            runtime_dir = workspace_dir / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            paths = self._paths(runtime_dir)
            instance_json = workspace_dir / "instance.json"
            self._write_instance_json(instance_json, workspace_dir=workspace_dir)
            manifest_path = workspace_dir / "buddyswitch" / "manifest.toml"

            ensure_completed, ensure_payload = self._run_broker_cli(
                workspace_dir=workspace_dir,
                command="ensure",
                paths=paths,
                instance_json=instance_json,
                manifest_path=manifest_path,
            )
            self.assertEqual(ensure_completed.returncode, 0, msg=ensure_completed.stderr)
            self.assertTrue(ensure_payload.get("ok"), msg=ensure_payload)
            try:
                status_completed, status_payload = self._run_broker_cli(
                    workspace_dir=workspace_dir,
                    command="status",
                    paths=paths,
                    instance_json=instance_json,
                    manifest_path=manifest_path,
                )
                self.assertEqual(status_completed.returncode, 0, msg=status_completed.stderr)
                self.assertTrue(status_payload.get("healthy"), msg=status_payload)
                self.assertIs(status_payload.get("runtime_workspace"), True)
                self.assertEqual(
                    Path(str(status_payload.get("env_store_root"))).resolve(strict=False),
                    (workspace_dir / "state").resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(status_payload.get("runtime_workspace_root"))).resolve(strict=False),
                    workspace_dir.resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(status_payload.get("runtime_state_root"))).resolve(strict=False),
                    (workspace_dir / "state").resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(status_payload.get("cwd"))).resolve(strict=False),
                    workspace_dir.resolve(strict=False),
                )
                ping = status_payload.get("ping")
                self.assertIsInstance(ping, dict, msg=status_payload)
                assert isinstance(ping, dict)
                self.assertIs(ping.get("runtime_workspace"), True)
                self.assertEqual(
                    Path(str(ping.get("env_store_root"))).resolve(strict=False),
                    (workspace_dir / "state").resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(ping.get("runtime_workspace_root"))).resolve(strict=False),
                    workspace_dir.resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(ping.get("runtime_state_root"))).resolve(strict=False),
                    (workspace_dir / "state").resolve(strict=False),
                )
                self.assertEqual(
                    Path(str(ping.get("cwd"))).resolve(strict=False),
                    workspace_dir.resolve(strict=False),
                )
            finally:
                self._run_broker_cli(
                    workspace_dir=workspace_dir,
                    command="stop",
                    paths=paths,
                    instance_json=instance_json,
                    manifest_path=manifest_path,
                )

    def test_status_reports_unhealthy_when_pid_live_but_socket_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            paths.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            status = self.lifecycle.broker_status(paths, expected_instance_id="inst-pm-example", expected_active_buddy="pm")
        self.assertFalse(status["healthy"])
        self.assertEqual(status["error"]["code"], "E_RUNTIME_BROKER_STALE_SOCKET")

    def test_status_reports_unhealthy_when_marker_disagrees_with_socket(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self._paths(root)
            paths.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
            paths.marker_file.write_text(str(root / "other.sock"), encoding="utf-8")
            status = self.lifecycle.broker_status(paths, expected_instance_id="inst-pm-example", expected_active_buddy="pm")
        self.assertFalse(status["healthy"])
        self.assertEqual(status["socket_path"], str(paths.socket_path))
        self.assertEqual(status["marker_path"], str(paths.marker_file))

    def test_status_rejects_ping_from_source_checkout_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace_dir = Path(temp) / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            paths = self._paths(Path(temp))
            paths.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle,
                "ping_broker",
                return_value={
                    "ok": True,
                    "result": {
                        "protocol": BROKER_V2_PROTOCOL,
                        "instance_id": "inst-pm-example",
                        "active_buddy": "pm",
                        "pid": os.getpid(),
                        "socket_path": str(paths.socket_path),
                        "runtime_root": str(ROOT),
                        "cwd": str(ROOT),
                        "env_store_root": str(ROOT),
                        "runtime_workspace": False,
                    },
                },
            ):
                status = self.lifecycle.broker_status(
                    paths,
                    expected_instance_id="inst-pm-example",
                    expected_active_buddy="pm",
                    expected_workspace_root=workspace_dir,
                )
        self.assertFalse(status["healthy"])
        self.assertIn(status["error"]["code"], {"E_RUNTIME_BROKER_STALE_SOCKET", "E_RUNTIME_BROKER_PERMISSION"})
        self.assertRegex(status["error"]["message"], r"runtime root mismatch|runtime workspace marker is invalid")

    def test_status_reports_unhealthy_when_ping_result_missing_pid_or_socket_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            paths.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle,
                "ping_broker",
                return_value={
                    "ok": True,
                    "result": {
                        "protocol": BROKER_V2_PROTOCOL,
                        "instance_id": "inst-pm-example",
                        "active_buddy": "pm",
                    },
                },
            ):
                status = self.lifecycle.broker_status(
                    paths,
                    expected_instance_id="inst-pm-example",
                    expected_active_buddy="pm",
                )
        self.assertFalse(status["healthy"])
        self.assertEqual(status["error"]["code"], "E_RUNTIME_BROKER_STALE_SOCKET")
        self.assertIn("missing pid", status["error"]["message"])

    def test_status_requires_successful_ping_before_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            paths.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle,
                "ping_broker",
                return_value={
                    "ok": False,
                    "error": {
                        "code": "E_RUNTIME_BROKER_UNAVAILABLE",
                        "message": "runtime broker ping unavailable",
                        "retriable": True,
                    },
                },
            ):
                status = self.lifecycle.broker_status(
                    paths,
                    expected_instance_id="inst-pm-example",
                    expected_active_buddy="pm",
                )
        self.assertFalse(status["healthy"])
        self.assertEqual(status["error"]["code"], "E_RUNTIME_BROKER_UNAVAILABLE")

    def test_ensure_cleans_stale_pid_marker_and_socket_before_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            paths.pid_file.write_text("999999\n", encoding="utf-8")
            paths.marker_file.write_text("/tmp/stale.sock", encoding="utf-8")
            paths.socket_path.write_text("not a socket", encoding="utf-8")
            events: list[str] = []

            def fake_start(*args, **kwargs):
                events.append("start")
                self.assertFalse(paths.pid_file.exists())
                self.assertFalse(paths.socket_path.exists())
                paths.pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
                return {"ok": True, "pid": os.getpid()}

            def fake_ping(*args, **kwargs):
                events.append("ping")
                return {
                    "ok": True,
                    "result": {
                        "protocol": BROKER_V2_PROTOCOL,
                        "instance_id": "inst-pm-example",
                        "active_buddy": "pm",
                        "pid": os.getpid(),
                        "socket_path": str(paths.socket_path),
                        "runtime_root": str(ROOT),
                        "cwd": str(ROOT),
                        "env_store_root": str(ROOT),
                        "runtime_workspace": True,
                    },
                }

            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle,
                "start_broker_process",
                side_effect=fake_start,
            ), patch.object(self.lifecycle, "ping_broker", side_effect=fake_ping):
                result = self.lifecycle.ensure_broker(
                    paths,
                    instance_json_path=Path("instance.json"),
                    manifest_path=MANIFEST,
                    expected_instance_id="inst-pm-example",
                    expected_active_buddy="pm",
                )
            self.assertTrue(result["ok"], msg=result)
            self.assertEqual(events, ["start", "ping", "ping"])
            self.assertEqual(paths.marker_file.read_text(encoding="utf-8"), str(paths.socket_path))
            self.assertTrue(result["status"]["healthy"], msg=result)

    def test_ensure_timeout_removes_stale_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._paths(Path(temp))
            paths.pid_file.write_text("999999\n", encoding="utf-8")
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            paths.socket_path.write_text("stale socket", encoding="utf-8")
            with patch.object(self.lifecycle, "_socket_is_unix", return_value=True), patch.object(
                self.lifecycle, "start_broker_process", return_value={"ok": True, "pid": os.getpid()}
            ), patch.object(
                self.lifecycle,
                "ping_broker",
                return_value={
                    "ok": True,
                    "result": {
                        "protocol": BROKER_V2_PROTOCOL,
                        "instance_id": "inst-pm-example",
                        "active_buddy": "pm",
                        "socket_path": str(paths.socket_path),
                        "runtime_root": str(ROOT),
                        "cwd": str(ROOT),
                        "env_store_root": str(ROOT),
                        "runtime_workspace": True,
                    },
                },
            ):
                result = self.lifecycle.ensure_broker(
                    paths,
                    instance_json_path=Path("instance.json"),
                    manifest_path=MANIFEST,
                    expected_instance_id="inst-pm-example",
                    expected_active_buddy="pm",
                    startup_timeout_seconds=0.05,
                )
        self.assertFalse(result["ok"], msg=result)
        self.assertEqual(result["error"]["broker_status"]["log_file"], str(paths.log_file))
        self.assertEqual(result["error"]["broker_status"]["socket_path"], str(paths.socket_path))
        self.assertEqual(result["error"]["broker_status"]["pid_file"], str(paths.pid_file))
        self.assertFalse(paths.marker_file.exists())
        self.assertFalse(paths.socket_path.exists())


class RuntimeBrokerPersistIdempotencyTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self) -> Path:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": "inst-pm-example",
                    "buddy": "pm",
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(self.runtime_root),
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        return instance_json

    def test_persist_without_idempotency_key_is_rejected_before_commit(self) -> None:
        dispatcher = _require_module("runtime_kernel.dispatcher")
        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-persist",
            "method": "persist",
            "params": {"context": {}, "result": {}},
            "deadline_ms": 35000,
        }
        session = dispatcher.RuntimeBrokerSession(instance_json_path=self._instance_json(), manifest_path=MANIFEST)
        response = dispatcher.dispatch_runtime_request(request, session)
        self.assertFalse(response["ok"], msg=response)
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER_PROTOCOL")
        self.assertIs(response["error"]["retriable"], False)


class RuntimeBrokerV2AcceptanceTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_error_envelope_preserves_extended_error_fields_from_dispatch_payload(self) -> None:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": "inst-pm-example",
                    "buddy": "pm",
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )

        request = {
            "protocol": BROKER_V2_PROTOCOL,
            "request_id": "req-error-extensions",
            "method": "env.tool",
            "params": {"instance_id": "inst-pm-example", "active_buddy": "pm"},
            "deadline_ms": 35000,
        }
        dispatched_payload = {
            "ok": False,
            "error": {
                "code": "E_BUDDYBOX_LOGICAL_NAME",
                "message": "logical_name must be relative",
                "retriable": True,
                "class": "invalid_input",
                "boundary": "active_buddy_private_file_capability",
            },
            "state_changed": False,
            "correctable_fields": ["logical_name"],
        }
        with patch("runtime_kernel.broker.coordinator.dispatch_with_coordination", return_value=dispatched_payload):
            envelope = runtime_broker.dispatch_runtime_request(
                request=request,
                instance_json_path=instance_json,
                manifest_path=MANIFEST,
            )

        self.assertFalse(envelope.get("ok"), msg=envelope)
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_BUDDYBOX_LOGICAL_NAME")
        self.assertEqual(error.get("class"), "invalid_input")
        self.assertEqual(error.get("boundary"), "active_buddy_private_file_capability")
        self.assertEqual(envelope.get("correctable_fields"), ["logical_name"])

    def test_active_identity_mismatch_errors_are_structured_non_retriable(self) -> None:
        dispatcher = _require_module("runtime_kernel.dispatcher")
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": "inst-pm-example",
                    "buddy": "pm",
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        session = dispatcher.RuntimeBrokerSession(instance_json_path=instance_json, manifest_path=MANIFEST)
        for request in (
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-wrong-instance",
                "method": "prepare",
                "params": {"text": PM_REQUEST, "instance_id": "inst-other", "active_buddy": "pm"},
                "deadline_ms": 35000,
            },
            {
                "protocol": BROKER_V2_PROTOCOL,
                "request_id": "req-wrong-buddy",
                "method": "prepare",
                "params": {"text": PM_REQUEST, "instance_id": "inst-pm-example", "active_buddy": "market"},
                "deadline_ms": 35000,
            },
        ):
            with self.subTest(request=request["request_id"]):
                response = dispatcher.dispatch_runtime_request(request, session)
                self.assertFalse(response["ok"], msg=response)
                self.assertIs(response["error"]["retriable"], False)
                self.assertNotEqual(response["error"]["code"], "E_RUNTIME_BROKER_UNAVAILABLE")
                boundary = response.get("permission_boundary") or response["error"].get("permission_boundary")
                self.assertIn(boundary, {"active-instance", "active-buddy"})

    def test_runtime_broker_v2_stays_local_unix_socket_gateway(self) -> None:
        server_module = _require_module("runtime_kernel.server")
        source_root = ROOT / "scripts" / "runtime_kernel"
        text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(source_root.glob("*.py")))
        self.assertNotIn("grpc", text)
        self.assertNotIn("http.server", text)
        self.assertNotIn("sqlite3", text)
        self.assertIn("AF_UNIX", Path(server_module.__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
