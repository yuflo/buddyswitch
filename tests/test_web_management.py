#!/usr/bin/env python3
"""Tests for the BuddySwitch local web management API."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import sys
import threading
import tempfile
import unittest
from unittest import mock
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "buddyswitch-codex"
WEB_MANAGEMENT_PATH = ROOT / "tools" / "launcher" / "web_management.py"
SPEC = importlib.util.spec_from_file_location("buddyswitch_web_management", WEB_MANAGEMENT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load spec for {WEB_MANAGEMENT_PATH}")
WEB_MANAGEMENT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = WEB_MANAGEMENT
SPEC.loader.exec_module(WEB_MANAGEMENT)
NO_PROXY_OPENER = build_opener(ProxyHandler({}))

from env.services import messages as message_service  # noqa: E402
from env.repos import identities as identity_repo  # noqa: E402


def save_test_actor_identity_profile(*, actor_id: str, role_id: str) -> None:
    identity_repo.save_actor_identity_profile(
        {
            "identity": {"id": actor_id, "type": "actor"},
            "role_id": role_id,
        }
    )


def _restore_env_value(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.timeouts: list[float] = []
        self.responses: dict[tuple[str, ...], WEB_MANAGEMENT.CommandResult] = {}
        self.blockers: dict[tuple[str, ...], threading.Event] = {}

    def add(self, args: list[str], result: WEB_MANAGEMENT.CommandResult) -> None:
        self.responses[tuple(args)] = result

    def block(self, args: list[str], event: threading.Event) -> None:
        self.blockers[tuple(args)] = event

    def run(self, args: list[str], *, timeout_seconds: float) -> WEB_MANAGEMENT.CommandResult:
        self.calls.append(list(args))
        self.timeouts.append(timeout_seconds)
        key = tuple(args)
        blocker = self.blockers.get(key)
        if blocker is not None:
            blocker.wait(timeout=5)
        if key not in self.responses:
            raise AssertionError(f"unexpected command: {args!r}")
        return self.responses[key]


@dataclass(frozen=True)
class CommandStep:
    args: list[str]
    result: WEB_MANAGEMENT.CommandResult


def command_json(payload: dict[str, object]) -> WEB_MANAGEMENT.CommandResult:
    return WEB_MANAGEMENT.CommandResult(
        returncode=0,
        stdout=json.dumps(payload, ensure_ascii=True),
        stderr="",
        timed_out=False,
    )


def command_error(*, returncode: int, stderr: str, timed_out: bool = False) -> WEB_MANAGEMENT.CommandResult:
    return WEB_MANAGEMENT.CommandResult(returncode=returncode, stdout="", stderr=stderr, timed_out=timed_out)


def active_status(actor_id: str, thread_id: str, thread_status: str) -> dict[str, object]:
    return {
        "actor_id": actor_id,
        "role": "pm",
        "status": "active",
        "workspace_dir": f"/tmp/shared/instances/{actor_id}/workspace",
        "browser_port": 9222,
        "updated_at": "2026-05-25T10:00:00Z",
        "thread_id": thread_id,
        "app_server": {"healthy": True},
        "thread": {"status": thread_status, "raw": {}},
    }


OPEN_TUI_HEADERS = {
    "Content-Type": "application/json",
    "X-BuddySwitch-Web": "1",
    "Host": "127.0.0.1:8765",
    "Origin": "http://127.0.0.1:8765",
}


def expected_attach_command(actor_id: str) -> str:
    return f"cd {shlex.quote(str(ROOT))} && ./buddyswitch-codex instance attach {shlex.quote(actor_id)}"


class FakeTerminalOpener:
    def __init__(self, error: Exception | None = None) -> None:
        self.commands: list[str] = []
        self.error = error

    def open(self, command: str) -> None:
        self.commands.append(command)
        if self.error is not None:
            raise self.error


class OrderedRunner:
    def __init__(self, steps: list[CommandStep]) -> None:
        self.steps = list(steps)
        self.calls: list[tuple[list[str], float]] = []

    def run(self, args: list[str], *, timeout_seconds: float) -> WEB_MANAGEMENT.CommandResult:
        self.calls.append((list(args), timeout_seconds))
        if not self.steps:
            raise AssertionError(f"unexpected command with no steps left: {args!r}")
        step = self.steps.pop(0)
        if step.args != args:
            raise AssertionError(f"expected command {step.args!r}, got {args!r}")
        return step.result


class WebManagementServerTestCase(unittest.TestCase):
    def _start_server(
        self,
        runner: FakeRunner | None = None,
        *,
        terminal_opener: Callable[[str], None] | None = None,
        platform_name: str | None = None,
    ) -> tuple[FakeRunner, str]:
        fake_runner = runner or FakeRunner()
        service_kwargs: dict[str, object] = {}
        if terminal_opener is not None:
            service_kwargs["terminal_opener"] = terminal_opener
        if platform_name is not None:
            service_kwargs["platform_name"] = platform_name
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            command_runner=fake_runner.run,
            **service_kwargs,
        )
        server = WEB_MANAGEMENT.create_server("127.0.0.1", 0, service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(thread.join, 5)
        return fake_runner, f"http://127.0.0.1:{server.server_port}"

    @staticmethod
    def _request_json(
        base_url: str,
        *,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        raw_body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, object]]:
        request_headers = dict(headers or {})
        data: bytes | None = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        elif raw_body is not None:
            data = raw_body
        request = Request(base_url + quote(path, safe="/:?=&"), data=data, headers=request_headers, method=method)
        try:
            with NO_PROXY_OPENER.open(request, timeout=5) as response:
                return int(response.status), json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return int(exc.code), json.loads(exc.read().decode("utf-8"))

    @staticmethod
    def _request_text(base_url: str, *, method: str, path: str) -> tuple[int, str]:
        request = Request(base_url + quote(path, safe="/:?=&"), method=method)
        try:
            with NO_PROXY_OPENER.open(request, timeout=5) as response:
                return int(response.status), response.read().decode("utf-8")
        except HTTPError as exc:
            return int(exc.code), exc.read().decode("utf-8")


class WebManagementUnitTests(unittest.TestCase):
    def test_validate_bind_host_accepts_loopback_only(self) -> None:
        self.assertEqual(WEB_MANAGEMENT.validate_bind_host("127.0.0.1"), "127.0.0.1")
        self.assertEqual(WEB_MANAGEMENT.validate_bind_host("localhost"), "localhost")
        with self.assertRaisesRegex(ValueError, "local"):
            WEB_MANAGEMENT.validate_bind_host("0.0.0.0")

    def test_validate_actor_id_rejects_traversal_like_values(self) -> None:
        for actor_id in ("", "../bad", "/tmp/act-demo", "inst bad", "demo"):
            with self.subTest(actor_id=actor_id):
                with self.assertRaisesRegex(ValueError, "actor id"):
                    WEB_MANAGEMENT.validate_actor_id(actor_id)
        self.assertEqual(WEB_MANAGEMENT.validate_actor_id("act-pm-demo"), "act-pm-demo")

    def test_open_tui_task_does_not_expand_launcher_public_surface(self) -> None:
        self.assertNotIn("attach-open", LAUNCHER.read_text(encoding="utf-8"))
        result = subprocess.run(
            [str(LAUNCHER), "instance", "help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("attach-open", result.stdout + result.stderr)
        self.assertIn("instance attach <actor-id>", result.stdout)

    def test_web_launcher_ensures_central_daemon_for_web_user_actor(self) -> None:
        source = LAUNCHER.read_text(encoding="utf-8")
        start = source.index("web_main() {")
        end = source.index("\n}\n\nmain() {", start)
        block = source[start:end]

        ensure_index = block.index("buddyswitch_central_daemon_ensure || return $?")
        run_index = block.index('python3 "${WEB_MANAGEMENT_HELPER}" "$@"')
        stop_index = block.index("buddyswitch_central_daemon_stop_if_idle")
        self.assertLess(ensure_index, run_index)
        self.assertLess(run_index, stop_index)
        self.assertIn('return "${status}"', block)

    def test_serve_with_imessage_worker_starts_stops_and_closes_server(self) -> None:
        class StopServer(Exception):
            pass

        class FakeServer:
            def __init__(self) -> None:
                self.served = False
                self.closed = False

            def serve_forever(self) -> None:
                self.served = True
                raise StopServer()

            def server_close(self) -> None:
                self.closed = True

        class FakeWorker:
            def __init__(self) -> None:
                self.started = 0
                self.stopped = 0

            def start(self) -> None:
                self.started += 1

            def stop(self) -> None:
                self.stopped += 1

        server = FakeServer()
        worker = FakeWorker()

        with self.assertRaises(StopServer):
            WEB_MANAGEMENT.serve_with_imessage_worker(server, worker)

        self.assertTrue(server.served)
        self.assertTrue(server.closed)
        self.assertEqual(worker.started, 1)
        self.assertEqual(worker.stopped, 1)

    def test_serve_with_imessage_worker_keeps_server_available_when_worker_start_fails(self) -> None:
        class StopServer(Exception):
            pass

        class FakeServer:
            def __init__(self) -> None:
                self.served = False
                self.closed = False

            def serve_forever(self) -> None:
                self.served = True
                raise StopServer()

            def server_close(self) -> None:
                self.closed = True

        class FakeWorker:
            def __init__(self) -> None:
                self.stopped = 0

            def start(self) -> None:
                raise RuntimeError("imsg unavailable")

            def stop(self) -> None:
                self.stopped += 1

        server = FakeServer()
        worker = FakeWorker()

        with mock.patch("sys.stderr") as stderr, self.assertRaises(StopServer):
            WEB_MANAGEMENT.serve_with_imessage_worker(server, worker)

        self.assertTrue(server.served)
        self.assertTrue(server.closed)
        self.assertEqual(worker.stopped, 0)
        stderr.write.assert_any_call("iMessage channel worker disabled: imsg unavailable\n")

    def test_web_management_source_does_not_parse_imessage_control_messages(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        self.assertNotRegex(source, r"""["']/actors["']""")
        self.assertNotIn("pending_actor_choices", source)
        self.assertNotIn("active_actor_id", source)
        self.assertNotIn("[Message From", source)

    def test_web_runtime_binds_shared_state_for_server_owned_web_im_identity(self) -> None:
        from env.repos import runtime_files

        original_state_root = os.environ.get("BUDDYSWITCH_STATE_ROOT")
        original_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
        original_actor_id = os.environ.get("BUDDYSWITCH_ACTOR_ID")
        self.addCleanup(runtime_files.reset_runtime_root_override)
        self.addCleanup(runtime_files.refresh_runtime_roots_from_env)
        self.addCleanup(_restore_env_value, "BUDDYSWITCH_STATE_ROOT", original_state_root)
        self.addCleanup(_restore_env_value, "BUDDYSWITCH_SHARED_ROOT", original_shared_root)
        self.addCleanup(_restore_env_value, "BUDDYSWITCH_ACTOR_ID", original_actor_id)

        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / ".codex-buddyswitch"
            shared_root.mkdir()
            os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            os.environ.pop("BUDDYSWITCH_STATE_ROOT", None)
            os.environ.pop("BUDDYSWITCH_ACTOR_ID", None)
            runtime_files.reset_runtime_root_override()
            runtime_files.refresh_runtime_roots_from_env()

            WEB_MANAGEMENT.bind_web_runtime_state()
            service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=FakeRunner().run)
            status, payload = service.handle_api("GET", "/api/im/session", b"", {})

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["identity"]["type"], "external")
            self.assertNotIn("participant_token", payload)
            self.assertNotIn("participant", payload)
            self.assertNotIn("external_session_key", payload)
            self.assertNotIn("event_cursor", payload)
            self.assertEqual(os.environ.get("BUDDYSWITCH_STATE_ROOT"), str(shared_root / "state"))
            self.assertNotIn("BUDDYSWITCH_ACTOR_ID", os.environ)
            self.assertTrue((shared_root / "state" / "buddyswitch" / "local" / "web-management" / "im-session.json").is_file())

    def test_map_command_failure_uses_required_status_codes(self) -> None:
        cases = [
            (
                WEB_MANAGEMENT.CommandResult(returncode=2, stdout="", stderr="Bad request", timed_out=False),
                400,
                "INVALID_REQUEST",
            ),
            (
                WEB_MANAGEMENT.CommandResult(returncode=3, stdout="", stderr="Instance delete blocked: active", timed_out=False),
                409,
                "LIFECYCLE_BLOCKED",
            ),
            (
                WEB_MANAGEMENT.CommandResult(returncode=1, stdout="", stderr="internal error", timed_out=True),
                504,
                "COMMAND_TIMEOUT",
            ),
            (
                WEB_MANAGEMENT.CommandResult(returncode=1, stdout="", stderr="internal error", timed_out=False),
                502,
                "COMMAND_FAILED",
            ),
        ]
        for result, expected_status, expected_code in cases:
            with self.subTest(result=result):
                error = WEB_MANAGEMENT.map_command_failure("instance list", result)
                self.assertEqual(error.status, expected_status)
                self.assertEqual(error.code, expected_code)

    def test_busy_guard_blocks_duplicate_keys(self) -> None:
        guard = WEB_MANAGEMENT.BusyGuard()
        self.assertTrue(guard.acquire("start"))
        self.assertFalse(guard.acquire("start"))
        guard.release("start")
        self.assertTrue(guard.acquire("start"))
        guard.release("start")
        self.assertTrue(guard.acquire("instance:act-pm-demo"))
        self.assertFalse(guard.acquire("instance:act-pm-demo"))
        guard.release("instance:act-pm-demo")

    def test_launcher_rejects_non_local_web_host(self) -> None:
        result = subprocess.run(
            [str(LAUNCHER), "web", "--host", "0.0.0.0"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("local", result.stderr)

    def test_im_wake_delegates_to_runtime_wake_bridge(self) -> None:
        runner = OrderedRunner([])
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)
        payload = {
            "type": "im.message.created",
            "target_identity_id": "act-pm-demo",
            "message_id": "msg-1",
            "conversation_id": "conv-1",
            "event_id": "imev-1",
        }
        with mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "check_reachability",
            side_effect=lambda **kwargs: {
                "reachability_status": "online",
                "target_identity_id": kwargs["target_identity_id"],
                "record": {"identity_id": kwargs["target_identity_id"]},
            },
        ), mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "wake_im_actor",
            return_value={"actor_handling_status": "submitted", "runtime_target": "parent", "error": None},
        ) as wake_im_actor:
            result = service._wake_im_actor(payload)

        self.assertEqual(result["actor_handling_status"], "submitted")
        wake_im_actor.assert_called_once_with(payload)
        self.assertEqual(runner.calls, [])


class WebManagementHTTPTests(WebManagementServerTestCase):
    def test_health_route_is_read_only(self) -> None:
        runner, base_url = self._start_server()
        status, payload = self._request_json(base_url, method="GET", path="/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(runner.calls, [])

    def test_buddies_route_comes_from_launcher_json(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "roles", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "roles": [
                            {
                                "id": "pm",
                                "label": "PM",
                                "scope": "Own product iteration and track progression.",
                            },
                            {
                                "id": "dev",
                                "label": "Dev",
                                "scope": "Implement approved scope in project code.",
                            },
                        ]
                    },
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/roles")
        self.assertEqual(status, 200)
        self.assertEqual(
            payload,
            {
                "ok": True,
                "roles": [
                    {
                        "id": "pm",
                        "label": "PM",
                        "scope": "Own product iteration and track progression.",
                    },
                    {
                        "id": "dev",
                        "label": "Dev",
                        "scope": "Implement approved scope in project code.",
                    },
                ],
            },
        )
        self.assertEqual(runner.calls, [["instance", "roles", "--json"]])

    def test_buddies_route_returns_structured_error_for_malformed_launcher_json(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "roles", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout="{bad json",
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/roles")
        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["code"], "COMMAND_FAILED")

    def test_instances_route_preserves_launcher_json_summary_shape(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "list", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "instances": [
                            {
                                "actor_id": "act-pm-demo",
                                "role": "pm",
                                "status": "active",
                                "app_server_health": "healthy",
                                "thread_id": "thread-pm",
                                "browser_port": 9222,
                                "updated_at": "2026-05-24T10:00:00Z",
                                "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
                            }
                        ]
                    },
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/instances")
        self.assertEqual(status, 200)
        self.assertEqual(
            payload,
            {
                "ok": True,
                "instances": [
                    {
                        "actor_id": "act-pm-demo",
                        "role": "pm",
                        "status": "active",
                        "app_server_health": "healthy",
                        "thread_id": "thread-pm",
                        "browser_port": 9222,
                        "updated_at": "2026-05-24T10:00:00Z",
                        "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
                    }
                ],
            },
        )
        self.assertEqual(runner.calls, [["instance", "list", "--json"]])

    def test_instances_route_returns_structured_error_for_malformed_launcher_json(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "list", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout="{bad json",
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/instances")
        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["code"], "COMMAND_FAILED")

    def test_status_route_preserves_cli_json_shape(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "status", "act-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "actor_id": "act-pm-demo",
                        "role": "pm",
                        "status": "active",
                        "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
                        "browser_port": 9222,
                        "updated_at": "2026-05-24T10:00:00Z",
                        "thread_id": "thread-demo",
                        "app_server": {"healthy": True},
                        "thread": {"status": "idle", "raw": {}},
                    },
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/instances/act-pm-demo/status")
        self.assertEqual(status, 200)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["instance"]["thread"]["status"], "idle")
        self.assertEqual(payload["instance"]["app_server"]["healthy"], True)
        self.assertEqual(payload["instance"]["thread_id"], "thread-demo")

    def test_create_route_validates_role_before_start(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "roles", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "roles": [
                            {
                                "id": "pm",
                                "label": "PM",
                                "scope": "Own product iteration and track progression.",
                            }
                        ]
                    },
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances",
            payload={"role": "unknown"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(runner.calls, [["instance", "roles", "--json"]])

    def test_create_instance_delegates_to_launcher_start_without_initialize_input(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "roles", "--json"],
                    command_json({"roles": [{"id": "pm", "label": "PM", "scope": "product"}]}),
                ),
                CommandStep(
                    ["instance", "start", "--role", "pm", "--json"],
                    command_json({"actor_id": "act-pm-demo"}),
                ),
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-1", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances", b'{"role":"pm"}')

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["actor_id"], "act-pm-demo")
        self.assertEqual(payload["instance"]["thread"]["status"], "idle")
        self.assertEqual(payload["instance"]["thread_id"], "thread-1")
        self.assertEqual(len(runner.calls), 3)
        self.assertNotIn("Initialize this " "BuddySwitch thread", json.dumps(runner.calls))
        self.assertEqual(runner.steps, [])

    def test_create_instance_returns_launcher_start_error_without_initialize_retry(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "roles", "--json"],
                    command_json({"roles": [{"id": "pm", "label": "PM", "scope": "product"}]}),
                ),
                CommandStep(
                    ["instance", "start", "--role", "pm", "--json"],
                    command_error(returncode=1, stderr="Thread bootstrap failed for thread-1."),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances", b'{"role":"pm"}')

        self.assertEqual(raised.exception.status, 502)
        self.assertEqual(raised.exception.code, "COMMAND_FAILED")
        self.assertIn("Thread bootstrap failed", raised.exception.message)
        self.assertEqual(len(runner.calls), 2)

    def test_clear_route_delegates_to_launcher_clear_without_initialize_input(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "clear", "act-pm-demo", "--json"],
                    command_json(
                        {
                            "actor_id": "act-pm-demo",
                            "previous_thread_id": "thread-old",
                            "thread_id": "thread-new",
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-new", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/clear", b"")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["previous_thread_id"], "thread-old")
        self.assertEqual(payload["thread_id"], "thread-new")
        self.assertEqual(payload["instance"]["thread_id"], "thread-new")
        self.assertEqual(len(runner.calls), 2)
        self.assertNotIn("Initialize this " "BuddySwitch thread", json.dumps(runner.calls))

    def test_clear_route_returns_command_failure_when_launcher_clear_fails(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "clear", "act-pm-demo", "--json"],
                    command_error(returncode=1, stderr="Daemon start failed for act-pm-demo."),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/act-pm-demo/clear", b"")

        self.assertEqual(raised.exception.status, 502)
        self.assertEqual(raised.exception.code, "COMMAND_FAILED")
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0][0], ["instance", "clear", "act-pm-demo", "--json"])

    def test_initialize_route_is_removed(self) -> None:
        runner = OrderedRunner([])
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/act-pm-demo/" + "initialize", b"")

        self.assertEqual(raised.exception.status, 404)
        self.assertEqual(raised.exception.code, "NOT_FOUND")
        self.assertEqual(runner.calls, [])

    def test_resume_route_delegates_to_launcher_resume(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "resume", "act-pm-demo", "--json"],
                    command_json({"actor_id": "act-pm-demo", "thread_id": "thread-1", "status": "active"}),
                ),
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-1", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/resume", b"")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["instance"]["status"], "active")
        self.assertEqual(runner.calls[0][0], ["instance", "resume", "act-pm-demo", "--json"])

    def test_open_tui_route_requires_web_headers_before_status_lookup(self) -> None:
        for headers in (
            {},
            {"Content-Type": "application/json"},
            {"X-BuddySwitch-Web": "1", "Content-Type": "text/plain"},
        ):
            with self.subTest(headers=headers):
                runner = OrderedRunner([])
                opener = FakeTerminalOpener()
                service = WEB_MANAGEMENT.WebManagementService(
                    repo_root=ROOT,
                    command_runner=runner.run,
                    terminal_opener=opener.open,
                    platform_name="darwin",
                )

                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api("POST", "/api/instances/act-pm-demo/open-tui", b"{}", headers)

                self.assertEqual(raised.exception.status, 400)
                self.assertEqual(raised.exception.code, "INVALID_REQUEST")
                self.assertEqual(runner.calls, [])
                self.assertEqual(opener.commands, [])

    def test_open_tui_route_rejects_bad_host_or_origin_before_status_lookup(self) -> None:
        for headers in (
            {**OPEN_TUI_HEADERS, "Host": "evil.example"},
            {**OPEN_TUI_HEADERS, "Origin": "https://evil.example"},
            {**OPEN_TUI_HEADERS, "Host": "127.0.0.1:8765", "Origin": "http://localhost:8765"},
            {**OPEN_TUI_HEADERS, "Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:9999"},
        ):
            with self.subTest(headers=headers):
                runner = OrderedRunner([])
                opener = FakeTerminalOpener()
                service = WEB_MANAGEMENT.WebManagementService(
                    repo_root=ROOT,
                    command_runner=runner.run,
                    terminal_opener=opener.open,
                    platform_name="darwin",
                )

                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api("POST", "/api/instances/act-pm-demo/open-tui", b"{}", headers)

                self.assertEqual(raised.exception.status, 403)
                self.assertEqual(raised.exception.code, "FORBIDDEN")
                self.assertEqual(runner.calls, [])
                self.assertEqual(opener.commands, [])

    def test_open_tui_route_rejects_arbitrary_request_fields_before_status_lookup(self) -> None:
        runner = OrderedRunner([])
        opener = FakeTerminalOpener()
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            command_runner=runner.run,
            terminal_opener=opener.open,
            platform_name="darwin",
        )

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api(
                "POST",
                "/api/instances/act-pm-demo/open-tui",
                b'{"command":"open calculator"}',
                OPEN_TUI_HEADERS,
            )

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])
        self.assertEqual(opener.commands, [])

    def test_open_tui_route_rejects_invalid_actor_id_before_status_lookup(self) -> None:
        runner = OrderedRunner([])
        opener = FakeTerminalOpener()
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            command_runner=runner.run,
            terminal_opener=opener.open,
            platform_name="darwin",
        )

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/demo/open-tui", b"{}", OPEN_TUI_HEADERS)

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])
        self.assertEqual(opener.commands, [])

    def test_open_tui_route_blocks_invalid_runtime_states_before_opener(self) -> None:
        inactive = active_status("act-pm-demo", "thread-1", "idle")
        inactive["status"] = "inactive"
        inactive["app_server"] = {"healthy": False}
        unhealthy = active_status("act-pm-demo", "thread-1", "idle")
        unhealthy["app_server"] = {"healthy": False}
        missing_thread = active_status("act-pm-demo", "thread-1", "idle")
        missing_thread["thread_id"] = None
        cases = [
            (inactive, "Resume this instance first."),
            (unhealthy, "Instance is unhealthy."),
            (missing_thread, "No thread to attach."),
        ]
        for status_payload, expected_message in cases:
            with self.subTest(expected_message=expected_message):
                runner = OrderedRunner(
                    [
                        CommandStep(
                            ["instance", "status", "act-pm-demo", "--json"],
                            command_json(status_payload),
                        )
                    ]
                )
                opener = FakeTerminalOpener()
                service = WEB_MANAGEMENT.WebManagementService(
                    repo_root=ROOT,
                    command_runner=runner.run,
                    terminal_opener=opener.open,
                    platform_name="darwin",
                )

                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api("POST", "/api/instances/act-pm-demo/open-tui", b"{}", OPEN_TUI_HEADERS)

                self.assertEqual(raised.exception.status, 409)
                self.assertEqual(raised.exception.code, "OPEN_TUI_BLOCKED")
                self.assertEqual(raised.exception.message, expected_message)
                self.assertEqual(len(runner.calls), 1)
                self.assertEqual(opener.commands, [])

    def test_open_tui_route_rejects_unsupported_os_with_copy_command(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-1", "idle")),
                )
            ]
        )
        opener = FakeTerminalOpener()
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            command_runner=runner.run,
            terminal_opener=opener.open,
            platform_name="linux",
        )

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/act-pm-demo/open-tui", b"{}", OPEN_TUI_HEADERS)

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "UNSUPPORTED_PLATFORM")
        self.assertEqual(raised.exception.message, "Could not open Terminal.")
        self.assertEqual(raised.exception.details["command"], expected_attach_command("act-pm-demo"))
        self.assertEqual(opener.commands, [])

    def test_open_tui_route_delegates_to_fake_terminal_opener(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "status", "act-pm-demo", "--json"],
            command_json(active_status("act-pm-demo", "thread-1", "idle")),
        )
        opener = FakeTerminalOpener()
        _, base_url = self._start_server(runner, terminal_opener=opener.open, platform_name="darwin")

        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/open-tui",
            payload={},
            headers={"X-BuddySwitch-Web": "1", "Origin": base_url},
        )

        expected_command = expected_attach_command("act-pm-demo")
        self.assertEqual(status, 200)
        self.assertEqual(
            payload,
            {
                "ok": True,
                "actor_id": "act-pm-demo",
                "command": expected_command,
                "terminal": "Terminal.app",
            },
        )
        self.assertEqual(opener.commands, [expected_command])
        self.assertEqual(runner.calls, [["instance", "status", "act-pm-demo", "--json"]])

    def test_open_tui_route_returns_copy_command_when_terminal_open_fails(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-1", "idle")),
                )
            ]
        )
        opener = FakeTerminalOpener(WEB_MANAGEMENT.TerminalOpenError("automation denied"))
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            command_runner=runner.run,
            terminal_opener=opener.open,
            platform_name="darwin",
        )

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/act-pm-demo/open-tui", b"{}", OPEN_TUI_HEADERS)

        expected_command = expected_attach_command("act-pm-demo")
        self.assertEqual(raised.exception.status, 502)
        self.assertEqual(raised.exception.code, "TERMINAL_OPEN_FAILED")
        self.assertEqual(raised.exception.message, "Could not open Terminal.")
        self.assertEqual(raised.exception.details["command"], expected_command)
        self.assertEqual(opener.commands, [expected_command])

    def test_create_route_returns_structured_error_for_malformed_launcher_json(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "roles", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "roles": [
                            {
                                "id": "pm",
                                "label": "PM",
                                "scope": "Own product iteration and track progression.",
                            }
                        ]
                    },
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        runner.add(
            ["instance", "start", "--role", "pm", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout="{bad json",
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances",
            payload={"role": "pm"},
        )
        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["code"], "COMMAND_FAILED")

    def test_input_route_returns_404_without_launcher_call(self) -> None:
        runner, base_url = self._start_server()
        removed_route = "/".join(("", "api", "instances", "act-pm-demo", "input"))
        status, payload = self._request_json(
            base_url,
            method="POST",
            path=removed_route,
            payload={"text": "Advance the brief"},
        )
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")
        self.assertEqual(runner.calls, [])

    def test_web_management_does_not_write_message_rows_or_construct_signals(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        for forbidden in (
            "env.repos.messages",
            "create_message",
            "save_message",
            "delete_message",
            "message." + "available",
            "signal_id",
            "daemon_client.deliver_signal",
            "Instance " + "input blocked:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_web_management_product_api_boundaries_do_not_import_tool_handlers_or_track_service(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        for forbidden in (
            "env.tools.track" + "._impl",
            "env.services" + ".tracks",
            "dispatch_env_tool_request",
            "dispatch_runtime_request",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

        self.assertFalse((ROOT / "scripts/env/services/tracks.py").exists())

    def test_web_management_product_api_does_not_split_first_cut_subpanel_routes(self) -> None:
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=FakeRunner().run)

        for path in (
            "/api/actors/act-pm-demo/tasks",
            "/api/actors/act-pm-demo/tracks",
            "/api/tracks/track-alpha/comments",
        ):
            with self.subTest(path=path):
                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api("GET", path, b"")
                self.assertEqual(raised.exception.status, 404)


class WebManagementStableImIdentityTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _service(self, runner: FakeRunner | None = None) -> WEB_MANAGEMENT.WebManagementService:
        command_runner = runner.run if runner is not None else FakeRunner().run
        return WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=command_runner)

    def _identity_path(self) -> Path:
        return self.runtime_state_root / "buddyswitch" / "local" / "web-management" / "im-session.json"

    def _external_identity_files(self) -> list[Path]:
        identities_dir = self.runtime_state_root / "buddyswitch" / "objects" / "identities" / "externals"
        return sorted(identities_dir.glob("*.json")) if identities_dir.is_dir() else []

    @staticmethod
    def _seed_actor_identity_profiles(identity_routes: list[dict[str, str]]) -> None:
        for route in identity_routes:
            save_test_actor_identity_profile(actor_id=route["actor_id"], role_id=route["role_id"])

    @staticmethod
    def _instance_list_for_identity_routes(identity_routes: list[dict[str, str]]) -> dict[str, object]:
        return {
            "instances": [
                {
                    "actor_id": route["actor_id"],
                    "role": route["role_id"],
                    "status": "active",
                    "app_server_health": "healthy",
                    "thread_id": f"thread-{index}",
                    "browser_port": None,
                    "updated_at": "2026-06-26T10:10:00Z",
                    "workspace_dir": f"/tmp/buddyswitch/instances/{route['actor_id']}/workspace",
                }
                for index, route in enumerate(identity_routes)
            ]
        }

    def test_retired_web_im_routes_are_not_live(self) -> None:
        service = self._service()
        retired_prefix = "/api/web/" + "im"

        for method, path, body in (
            ("GET", retired_prefix + "/session", b""),
            ("POST", retired_prefix + "/messages", b'{"target_identity_id":"act-market-demo","content":"ping"}'),
            ("GET", retired_prefix + "/events?identity_id=act-market-demo&wait_ms=0", b""),
            ("GET", retired_prefix + "/conversations/direct?identity_id=act-market-demo&limit=20", b""),
        ):
            with self.subTest(method=method, path=path):
                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api(method, path, body, {})
                self.assertEqual(raised.exception.status, 404)
                self.assertEqual(raised.exception.code, "NOT_FOUND")

    def test_web_im_actor_roster_does_not_create_actor_identity_profile(self) -> None:
        routes = [{"actor_id": "act-web-profile-missing", "role_id": "dev"}]
        runner = FakeRunner()
        runner.add(["instance", "list", "--json"], command_json(self._instance_list_for_identity_routes(routes)))
        service = self._service(runner)

        status, payload = service.handle_api("GET", "/api/im/actors", b"", {})

        self.assertEqual(status, 200)
        self.assertEqual(payload["count"], 1)
        self.assertIsNone(identity_repo.get_actor_identity_profile("act-web-profile-missing"))

    def test_im_session_creates_one_stable_web_identity_per_runtime(self) -> None:
        first = self._service()
        first_status, first_payload = first.handle_api("GET", "/api/im/session", b"", {})
        second = self._service()
        second_status, second_payload = second.handle_api("GET", "/api/im/session", b"", {})

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertTrue(first_payload["ok"])
        self.assertEqual(first_payload["identity"], second_payload["identity"])
        self.assertEqual(first_payload["identity"]["type"], "external")
        self.assertNotIn("role_id", first_payload["identity"])
        self.assertNotIn("participant", first_payload)
        self.assertNotIn("participant", second_payload)
        self.assertNotIn("participant_token", first_payload)
        self.assertNotIn("participant_token", second_payload)
        self.assertNotIn("external_session_key", first_payload)
        self.assertNotIn("external_session_key", second_payload)
        self.assertNotIn("event_cursor", first_payload)
        self.assertNotIn("event_cursor", second_payload)
        self.assertEqual(len(self._external_identity_files()), 1)
        identity = json.loads(self._identity_path().read_text(encoding="utf-8"))
        self.assertEqual(identity["client_kind"], "web-management")
        self.assertEqual(identity["display_name"], "BuddySwitch Web")
        self.assertEqual(identity["identity"], first_payload["identity"])
        self.assertIn("external_session_key", identity)
        self.assertNotIn("participant", identity)
        self.assertNotIn("participant_token", identity)
        self.assertNotIn("event_cursor", identity)
        self.assertNotIn("messages", identity)
        self.assertNotIn("conversation", identity)
        self.assertNotIn("actor_history", identity)

    def test_invalid_web_im_identity_is_replaced_once_then_reused(self) -> None:
        first_status, first_payload = self._service().handle_api("GET", "/api/im/session", b"", {})
        self.assertEqual(first_status, 200)
        first_external_id = first_payload["identity"]["id"]
        identity_path = self._identity_path()
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["external_session_key"] = "imsk-invalid"
        identity_path.write_text(json.dumps(identity, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        replaced_status, replaced_payload = self._service().handle_api("GET", "/api/im/session", b"", {})
        reused_status, reused_payload = self._service().handle_api("GET", "/api/im/session", b"", {})

        self.assertEqual(replaced_status, 200)
        self.assertEqual(reused_status, 200)
        self.assertNotEqual(replaced_payload["identity"]["id"], first_external_id)
        self.assertEqual(replaced_payload["identity"], reused_payload["identity"])
        self.assertEqual(len(self._external_identity_files()), 2)

    def test_browser_style_im_routes_send_read_fetch_ack_and_restore_history_without_browser_token(self) -> None:
        """Browser-style Web request sends target-identity IM through /api/im/messages, actor reply becomes visible through /api/im/events, browser fetches the reply through /api/im/messages/<id>, browser acks through /api/im/events/ack, and direct conversation shows both messages without exposing external_session_key."""
        actor_route = {
            "role_id": "market",
            "actor_id": self._runtime_actor_id(role="market", label="web-im-history"),
        }
        self._seed_actor_identity_profiles([actor_route])
        runner = FakeRunner()
        runner.add(["instance", "list", "--json"], command_json(self._instance_list_for_identity_routes([actor_route])))
        service = self._service(runner)
        status, session = service.handle_api("GET", "/api/im/session", b"", {})
        self.assertEqual(status, 200)
        web_identity = session["identity"]

        with mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "check_reachability",
            side_effect=lambda **kwargs: {
                "reachability_status": "online",
                "target_identity_id": kwargs["target_identity_id"],
                "record": {"identity_id": kwargs["target_identity_id"]},
            },
        ), mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "wake_im_actor",
            return_value={"actor_handling_status": "submitted", "runtime_target": "parent", "error": None},
        ) as wake_im_actor:
            status, sent = service.handle_api(
                "POST",
                "/api/im/messages",
                json.dumps(
                    {
                        "target_identity_id": actor_route["actor_id"],
                        "content": "ping",
                        "reply_to": None,
                    }
                ).encode("utf-8"),
                {},
            )

        self.assertEqual(status, 200, msg=sent)
        self.assertEqual(sent["delivery_status"], "accepted")
        self.assertEqual(sent["actor_handling_status"], "submitted")
        self.assertNotIn("wake_" + "status", sent)
        wake_im_actor.assert_called_once()
        self.assertNotIn("target_" + "role_id", wake_im_actor.call_args.args[0])
        sent_message_id = sent["message"]["id"]

        reply = message_service.send_im_reply(
            sender_identity={"id": actor_route["actor_id"], "type": "actor"},
            content="pong",
            reply_to=sent_message_id,
        )
        self.assertTrue(reply["ok"], msg=reply)

        status, events = service.handle_api(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {},
        )
        self.assertEqual(status, 200, msg=events)
        self.assertEqual([event["message_id"] for event in events["events"]], [reply["message"]["id"]])
        self.assertNotIn("messages", events)
        self.assertNotIn("participant_token", events)
        self.assertNotIn("external_session_key", events)
        self.assertNotIn("next_cursor", events)
        self.assertNotIn("ack", events)

        status, repeated_events = service.handle_api(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {},
        )
        self.assertEqual(status, 200, msg=repeated_events)
        self.assertEqual([event["message_id"] for event in repeated_events["events"]], [reply["message"]["id"]])

        reply_id = reply["message"]["id"]
        status, fetched = service.handle_api("GET", f"/api/im/messages/{reply_id}", b"", {})
        self.assertEqual(status, 200, msg=fetched)
        self.assertEqual(fetched["message"]["content"], "pong")
        self.assertNotIn("external_session_key", fetched)

        status, acked = service.handle_api(
            "POST",
            "/api/im/events/ack",
            json.dumps({"event_id": reply["event_id"]}).encode("utf-8"),
            {},
        )
        self.assertEqual(status, 200, msg=acked)
        self.assertTrue(acked["ok"])
        self.assertNotIn("external_session_key", acked)

        status, after_ack = service.handle_api("GET", "/api/im/events?wait_ms=0", b"", {})
        self.assertEqual(status, 200, msg=after_ack)
        self.assertEqual(after_ack["events"], [])

        status, history = service.handle_api(
            "GET",
            f"/api/im/conversations/direct?identity_id={actor_route['actor_id']}&limit=20",
            b"",
            {},
        )
        self.assertEqual(status, 200, msg=history)
        self.assertEqual([row["id"] for row in history["messages"]], [sent_message_id, reply_id])
        self.assertNotIn("external_session_key", history)

    def test_im_events_are_external_session_wide_and_do_not_fetch_or_ack_messages(self) -> None:
        market_actor = {
            "role_id": "market",
            "actor_id": self._runtime_actor_id(role="market", label="web-im-market"),
        }
        dev_actor = {
            "role_id": "dev",
            "actor_id": self._runtime_actor_id(role="dev", label="web-im-dev"),
        }
        self._seed_actor_identity_profiles([market_actor, dev_actor])
        runner = FakeRunner()
        runner.add(["instance", "list", "--json"], command_json(self._instance_list_for_identity_routes([market_actor, dev_actor])))
        service = self._service(runner)
        session_status, session = service.handle_api("GET", "/api/im/session", b"", {})
        self.assertEqual(session_status, 200)
        web_identity = session["identity"]
        sent_by_actor: dict[str, dict[str, object]] = {}
        with mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "check_reachability",
            side_effect=lambda **kwargs: {
                "reachability_status": "online",
                "target_identity_id": kwargs["target_identity_id"],
                "record": {"identity_id": kwargs["target_identity_id"]},
            },
        ):
            for actor_route, content in (
                (market_actor, "market ping"),
                (dev_actor, "dev ping"),
            ):
                status, payload = service.handle_api(
                    "POST",
                    "/api/im/messages",
                    json.dumps(
                        {
                            "target_identity_id": actor_route["actor_id"],
                            "content": content,
                            "reply_to": None,
                        }
                    ).encode("utf-8"),
                    {},
                )
                self.assertEqual(status, 200, msg=payload)
                sent_by_actor[actor_route["actor_id"]] = payload

        for actor_route, content in (
            (market_actor, "market pong"),
            (dev_actor, "dev pong"),
        ):
            reply = message_service.send_im_reply(
                sender_identity={"id": actor_route["actor_id"], "type": "actor"},
                content=content,
                reply_to=sent_by_actor[actor_route["actor_id"]]["message"]["id"],
            )
            self.assertTrue(reply["ok"], msg=reply)

        status, events = service.handle_api(
            "GET",
            "/api/im/events?wait_ms=0&limit=50",
            b"",
            {},
        )

        self.assertEqual(status, 200, msg=events)
        self.assertEqual(
            [event["sender_identity"]["id"] for event in events["events"]],
            [market_actor["actor_id"], dev_actor["actor_id"]],
        )
        self.assertNotIn("messages", events)

        status, repeated = service.handle_api("GET", "/api/im/events?wait_ms=0&limit=50", b"", {})
        self.assertEqual(status, 200, msg=repeated)
        self.assertEqual(
            [event["sender_identity"]["id"] for event in repeated["events"]],
            [market_actor["actor_id"], dev_actor["actor_id"]],
        )

        for event in events["events"]:
            status, fetched = service.handle_api("GET", f"/api/im/messages/{event['message_id']}", b"", {})
            self.assertEqual(status, 200, msg=fetched)
            self.assertIn(fetched["message"]["content"], {"market pong", "dev pong"})
            status, acked = service.handle_api(
                "POST",
                "/api/im/events/ack",
                json.dumps({"event_id": event["event_id"]}).encode("utf-8"),
                {},
            )
            self.assertEqual(status, 200, msg=acked)

        status, market_history = service.handle_api(
            "GET",
            f"/api/im/conversations/direct?identity_id={market_actor['actor_id']}&limit=20",
            b"",
            {},
        )
        self.assertEqual(status, 200, msg=market_history)
        self.assertEqual(
            [row["content"] for row in market_history["messages"]],
            ["market ping", "market pong"],
        )

    def test_im_events_rejects_browser_supplied_cursor(self) -> None:
        service = self._service()
        service.handle_api("GET", "/api/im/session", b"", {})

        status, payload = service.handle_api("GET", "/api/im/events?cursor=imev-000000000000&wait_ms=0", b"", {})

        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_IM_PAYLOAD")


class WebManagementProductApiTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _service(self, runner: FakeRunner | OrderedRunner | None = None) -> WEB_MANAGEMENT.WebManagementService:
        command_runner = runner.run if runner is not None else FakeRunner().run
        return WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=command_runner)

    @staticmethod
    def _instance_list_payload() -> dict[str, object]:
        return {
            "instances": [
                {
                    "actor_id": "act-pm-demo",
                    "role": "pm",
                    "status": "active",
                    "app_server_health": "healthy",
                    "thread_id": "thread-main",
                    "browser_port": 9222,
                    "updated_at": "2026-06-26T10:00:00Z",
                    "workspace_dir": "/tmp/buddyswitch/instances/act-pm-demo/workspace",
                },
                {
                    "actor_id": "act-dev-demo",
                    "role": "dev",
                    "status": "inactive",
                    "app_server_health": "unhealthy",
                    "thread_id": None,
                    "browser_port": None,
                    "updated_at": "2026-06-26T10:05:00Z",
                    "workspace_dir": "/tmp/buddyswitch/instances/act-dev-demo/workspace",
                },
            ]
        }

    @staticmethod
    def _instance_status_payload() -> dict[str, object]:
        return {
            "actor_id": "act-pm-demo",
            "role": "pm",
            "status": "active",
            "workspace_dir": "/tmp/buddyswitch/instances/act-pm-demo/workspace",
            "browser_port": 9222,
            "updated_at": "2026-06-26T10:00:00Z",
            "thread_id": "thread-main",
            "app_server_health": "healthy",
            "app_server": {"healthy": True},
            "thread": {"status": "idle", "raw": {}},
        }

    def _seed_track_pages(self) -> None:
        from env.repos import track_comments as track_comment_repo
        from env.repos import tracks as track_repo

        actor = {"role_id": "pm", "actor_id": "act-pm-demo"}
        actor_id = actor["actor_id"]
        track_repo.save_track(
            {
                "id": "track-alpha",
                "title": "Actor console",
                "outcome": "Ship actor-centered Web management.",
                "owner_identity_id": actor_id,
                "state": "active",
                "now": {"next": "Implement Web DTOs.", "blocker": None},
                "acceptance_criteria": ["Actor is the primary object."],
                "non_goals": ["Do not add lower actor.tasks API."],
                "artifact_relations": [
                    {
                        "type": "artifact",
                        "relation_id": "rel-material",
                        "artifact_id": "artifact-material",
                        "role": "material",
                        "label": "Brief",
                        "template": "markdown",
                        "from_identity_id": actor_id,
                        "summary": "Source brief.",
                        "current": True,
                        "created_at": "2026-06-26T09:00:00Z",
                    },
                    {
                        "type": "artifact",
                        "relation_id": "rel-proof",
                        "artifact_id": "artifact-proof",
                        "role": "proof",
                        "label": "Plan",
                        "template": "markdown",
                        "from_identity_id": actor_id,
                        "summary": "Implementation plan.",
                        "current": True,
                        "created_at": "2026-06-26T09:10:00Z",
                    },
                ],
                "updates": [
                    {
                        "id": "upd-plan",
                        "by_identity_id": actor_id,
                        "summary": "Phase two boundary confirmed.",
                        "kind": "decision",
                        "refs": [{"type": "artifact", "id": "artifact-proof"}],
                        "created_at": "2026-06-26T09:15:00Z",
                    }
                ],
                "created_at": "2026-06-26T08:00:00Z",
                "updated_at": "2026-06-26T10:00:00Z",
                "archived_at": None,
            }
        )
        track_repo.save_track(
            {
                "id": "track-archived",
                "title": "Archived work",
                "outcome": "Do not show archived Track pages.",
                "owner_identity_id": actor_id,
                "state": "active",
                "now": {"next": "Archived.", "blocker": None},
                "acceptance_criteria": [],
                "non_goals": [],
                "artifact_relations": [],
                "updates": [],
                "created_at": "2026-06-25T08:00:00Z",
                "updated_at": "2026-06-25T10:00:00Z",
                "archived_at": "2026-06-25T11:00:00Z",
            }
        )
        track_comment_repo.save_track_comment(
            {
                "id": "comment-root",
                "track_id": "track-alpha",
                "thread_id": "thread-open",
                "by_identity_id": "act-dev-demo",
                "content": "Need Track detail to include comments.",
                "reply_to": None,
                "mentioned_identity_ids": [actor_id],
                "status": "open",
                "created_at": "2026-06-26T10:01:00Z",
                "resolved_by_identity_id": None,
                "resolved_at": None,
                "resolution_summary": None,
            }
        )
        track_comment_repo.save_track_comment(
            {
                "id": "comment-reply",
                "track_id": "track-alpha",
                "thread_id": "thread-open",
                "by_identity_id": actor_id,
                "content": "Comments stay inside Track detail for phase two.",
                "reply_to": "comment-root",
                "mentioned_identity_ids": [],
                "status": "open",
                "created_at": "2026-06-26T10:02:00Z",
                "resolved_by_identity_id": None,
                "resolved_at": None,
                "resolution_summary": None,
            }
        )
        track_comment_repo.save_track_comment(
            {
                "id": "comment-resolved",
                "track_id": "track-alpha",
                "thread_id": "thread-resolved",
                "by_identity_id": actor_id,
                "content": "Resolved discussion.",
                "reply_to": None,
                "mentioned_identity_ids": [],
                "status": "resolved",
                "created_at": "2026-06-26T10:03:00Z",
                "resolved_by_identity_id": actor_id,
                "resolved_at": "2026-06-26T10:04:00Z",
                "resolution_summary": "Closed.",
            }
        )

    def test_actor_roster_api_projects_instance_list_as_actor_rows(self) -> None:
        runner = FakeRunner()
        runner.add(["instance", "list", "--json"], command_json(self._instance_list_payload()))
        service = self._service(runner)

        status, payload = service.handle_api("GET", "/api/actors", b"")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual([row["actor_id"] for row in payload["actors"]], ["act-pm-demo", "act-dev-demo"])
        self.assertEqual(payload["actors"][0]["runtime"]["status"], "active")
        self.assertEqual(payload["actors"][0]["runtime"]["app_server_health"], "healthy")
        self.assertEqual(payload["actors"][1]["runtime"]["status"], "inactive")
        self.assertEqual(runner.calls, [["instance", "list", "--json"]])

    def test_web_im_send_resolves_actor_route_from_instance_list_not_identity_id_text(self) -> None:
        target_identity_id = "act-web-identity-route"
        save_test_actor_identity_profile(actor_id=target_identity_id, role_id="market")
        runner = FakeRunner()
        runner.add(
            ["instance", "list", "--json"],
            command_json(
                {
                    "instances": [
                        {
                            "actor_id": target_identity_id,
                            "role": "market",
                            "status": "active",
                            "app_server_health": "healthy",
                            "thread_id": "thread-market",
                            "browser_port": None,
                            "updated_at": "2026-06-26T10:10:00Z",
                            "workspace_dir": "/tmp/buddyswitch/instances/act-web-identity-route/workspace",
                        }
                    ]
                }
            ),
        )
        service = self._service(runner)

        with mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "check_reachability",
            return_value={
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {"identity_id": target_identity_id},
            },
        ), mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "wake_im_actor",
            return_value={"actor_handling_status": "submitted", "runtime_target": "parent", "error": None},
        ) as wake_im_actor:
            status, payload = service.handle_api(
                "POST",
                "/api/im/messages",
                json.dumps({"target_identity_id": target_identity_id, "content": "ping"}).encode("utf-8"),
                {},
            )

        self.assertEqual(status, 200, msg=payload)
        self.assertEqual(payload["actor_handling_status"], "submitted")
        self.assertNotIn("wake_" + "status", payload)
        wake_im_actor.assert_called_once()
        self.assertEqual(wake_im_actor.call_args.args[0]["target_identity_id"], target_identity_id)
        self.assertNotIn("target_" + "role_id", wake_im_actor.call_args.args[0])

    def test_actor_console_api_composes_runtime_task_sys_track_and_im_projection(self) -> None:
        from env.domain import task_sys

        self._seed_track_pages()
        runner = FakeRunner()
        runner.add(["instance", "status", "act-pm-demo", "--json"], command_json(self._instance_status_payload()))
        service = self._service(runner)
        task_result = task_sys.ingest(
            {
                "source": {"type": "test.console", "ref": {"id": "console"}},
                "actor_target": {"actor_id": "act-pm-demo", "role_id": "pm"},
                "context": {"fixture": "web console"},
            }
        )
        failed_result = task_sys.ingest(
            {
                "source": {"type": "test.console", "ref": {"id": "console-failed"}},
                "actor_target": {"actor_id": "act-pm-demo", "role_id": "pm"},
                "context": {"fixture": "web console recoverable"},
            }
        )
        task_sys.record_side_runtime_failure(
            failed_result["task_id"],
            {
                "status": "runtime_failed",
                "stage": "side_input",
                "processor": "side",
                "error": "thread not loaded",
                "retryable": True,
                "attempts": 2,
            },
        )

        status, payload = service.handle_api("GET", "/api/actors/act-pm-demo/console", b"")

        self.assertEqual(status, 200)
        console = payload["console"]
        self.assertEqual(console["actor"], {"actor_id": "act-pm-demo", "role": "pm"})
        self.assertEqual(console["runtime"]["thread_status"], "idle")
        self.assertEqual(console["task_sys"]["active_count"], 1)
        self.assertEqual(console["task_sys"]["recoverable_count"], 1)
        self.assertEqual(console["task_sys"]["active_tasks"][0]["task_id"], task_result["task_id"])
        self.assertEqual(console["task_sys"]["recoverable_tasks"][0]["task_id"], failed_result["task_id"])
        self.assertEqual(console["task_sys"]["recoverable_tasks"][0]["status"], "runtime_failed")
        self.assertEqual(console["task_sys"]["recoverable_tasks"][0]["failure_result"]["stage"], "side_input")
        self.assertEqual(console["im"]["target"]["identity"], {"id": "act-pm-demo", "type": "actor"})
        self.assertEqual(console["im"]["target"]["identity_id"], "act-pm-demo")
        self.assertEqual(console["im"]["target"]["role_id"], "pm")
        self.assertNotIn("actor_address", console["im"]["target"])
        self.assertEqual([row["id"] for row in console["tracks"]["items"]], ["track-alpha"])

    def test_actor_console_api_rejects_invalid_actor_ids(self) -> None:
        service = self._service()

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("GET", "/api/actors/not-an-actor/console", b"")

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "INVALID_REQUEST")

    def test_track_list_api_returns_non_archived_track_summaries(self) -> None:
        self._seed_track_pages()
        service = self._service()

        status, payload = service.handle_api("GET", "/api/tracks", b"")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual([row["id"] for row in payload["tracks"]], ["track-alpha"])
        summary = payload["tracks"][0]
        self.assertEqual(summary["title"], "Actor console")
        self.assertEqual(summary["comment_summary"]["comment_count"], 3)
        self.assertEqual(summary["comment_summary"]["open_thread_count"], 1)

    def test_track_detail_api_includes_materials_proofs_updates_and_comment_threads(self) -> None:
        self._seed_track_pages()
        service = self._service()

        status, payload = service.handle_api("GET", "/api/tracks/track-alpha", b"")

        self.assertEqual(status, 200)
        track = payload["track"]
        self.assertEqual(track["id"], "track-alpha")
        self.assertEqual([row["artifact_id"] for row in track["materials"]], ["artifact-material"])
        self.assertEqual([row["artifact_id"] for row in track["proofs"]], ["artifact-proof"])
        self.assertEqual([row["id"] for row in track["updates"]], ["upd-plan"])
        self.assertEqual(track["comment_summary"]["comment_count"], 3)
        self.assertEqual(track["comment_summary"]["open_thread_count"], 1)
        self.assertEqual(track["comment_summary"]["resolved_thread_count"], 1)
        self.assertEqual([row["thread_id"] for row in track["comment_threads"]], ["thread-resolved", "thread-open"])
        open_thread = next(row for row in track["comment_threads"] if row["thread_id"] == "thread-open")
        self.assertEqual(open_thread["status"], "open")
        self.assertEqual(open_thread["comment_count"], 2)
        self.assertEqual(open_thread["latest_comment_id"], "comment-reply")
        self.assertEqual(open_thread["latest_comment_preview"], "Comments stay inside Track detail for phase two.")

    def test_track_detail_api_returns_not_found_for_missing_or_archived_tracks(self) -> None:
        self._seed_track_pages()
        service = self._service()

        for track_id in ("track-missing", "track-archived"):
            with self.subTest(track_id=track_id):
                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api("GET", f"/api/tracks/{track_id}", b"")
                self.assertEqual(raised.exception.status, 404)
                self.assertEqual(raised.exception.code, "NOT_FOUND")


class WebManagementHTTPActionTests(WebManagementServerTestCase):
    def test_side_create_route_delegates_and_reports_side_thread_id(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "side", "act-pm-demo", "--text", "Explore", "--json"],
                    command_json(
                        {
                            "actor_id": "act-pm-demo",
                            "action": "start",
                            "thread_action": "start",
                            "parent_thread_id": "thread-main",
                            "side_thread_id": "thread-side-1",
                            "turn_id": "turn-side-1",
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-main", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/side", b'{"text":"Explore"}')

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "start")
        self.assertEqual(payload["thread_action"], "start")
        self.assertEqual(payload["side_thread_id"], "thread-side-1")
        self.assertEqual(payload["parent_thread_id"], "thread-main")
        self.assertEqual(payload["turn_id"], "turn-side-1")
        self.assertEqual(payload["instance"]["thread_id"], "thread-main")

    def test_side_route_passes_model_and_effort_only_for_new_side_thread(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    [
                        "instance",
                        "side",
                        "act-pm-demo",
                        "--text",
                        "Start side",
                        "--model",
                        "gpt-5.4",
                        "--effort",
                        "high",
                        "--json",
                    ],
                    command_json(
                        {
                            "actor_id": "act-pm-demo",
                            "action": "start",
                            "thread_action": "start",
                            "parent_thread_id": "thread-main",
                            "side_thread_id": "thread-side-1",
                            "turn_id": "turn-side-1",
                            "model": "gpt-5.4",
                            "model_reasoning_effort": "high",
                            "model_source": "override",
                            "model_reasoning_effort_source": "override",
                            "model_config_durability": "thread_fork_only",
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-main", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api(
            "POST",
            "/api/instances/act-pm-demo/side",
            b'{"text":"Start side","model":"gpt-5.4","effort":"high"}',
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["side_thread_id"], "thread-side-1")
        self.assertEqual(payload["model"], "gpt-5.4")
        self.assertEqual(payload["model_reasoning_effort"], "high")
        self.assertEqual(payload["model_config_durability"], "thread_fork_only")

    def test_side_send_route_delegates_existing_side(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    [
                        "instance",
                        "side",
                        "act-pm-demo",
                        "--side-thread-id",
                        "thread-side-1",
                        "--text",
                        "Follow up",
                        "--json",
                    ],
                    command_json(
                        {
                            "actor_id": "act-pm-demo",
                            "action": "send",
                            "thread_action": "steer",
                            "parent_thread_id": "thread-main",
                            "side_thread_id": "thread-side-1",
                            "turn_id": "turn-side-1",
                            "expected_turn_id": "turn-side-1",
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-main", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api(
            "POST",
            "/api/instances/act-pm-demo/side",
            b'{"side_thread_id":"thread-side-1","text":"Follow up"}',
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "send")
        self.assertEqual(payload["thread_action"], "steer")
        self.assertEqual(payload["side_thread_id"], "thread-side-1")
        self.assertEqual(payload["parent_thread_id"], "thread-main")
        self.assertEqual(payload["expected_turn_id"], "turn-side-1")
        self.assertEqual(payload["instance"]["thread_id"], "thread-main")

    def test_side_close_route_delegates_and_reports_side_thread_id(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    [
                        "instance",
                        "side",
                        "close",
                        "act-pm-demo",
                        "--side-thread-id",
                        "thread-side-1",
                        "--json",
                    ],
                    command_json(
                        {
                            "actor_id": "act-pm-demo",
                            "action": "close",
                            "parent_thread_id": "thread-main",
                            "side_thread_id": "thread-side-1",
                            "turn_id": "turn-side-1",
                            "turn_interrupt_attempted": True,
                            "turn_interrupt_ok": True,
                            "lease_unregistered": True,
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-main", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api(
            "POST",
            "/api/instances/act-pm-demo/side/close",
            b'{"side_thread_id":"thread-side-1"}',
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "close")
        self.assertEqual(payload["side_thread_id"], "thread-side-1")
        self.assertEqual(payload["parent_thread_id"], "thread-main")
        self.assertEqual(payload["turn_id"], "turn-side-1")
        self.assertTrue(payload["turn_interrupt_attempted"])
        self.assertTrue(payload["turn_interrupt_ok"])
        self.assertTrue(payload["lease_unregistered"])
        self.assertEqual(payload["instance"]["thread_id"], "thread-main")

    def test_side_route_rejects_empty_text(self) -> None:
        runner, base_url = self._start_server()
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/side",
            payload={"text": "   "},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])

    def test_side_route_rejects_model_or_effort_with_existing_side_thread_id(self) -> None:
        runner, base_url = self._start_server()
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/side",
            payload={
                "side_thread_id": "thread-side-1",
                "text": "Follow up",
                "model": "gpt-5.4",
                "effort": "high",
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertIn("only applies when starting a new side thread", payload["error"]["message"])
        self.assertEqual(runner.calls, [])

    def test_side_close_route_rejects_missing_side_thread_id(self) -> None:
        runner, base_url = self._start_server()
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/side/close",
            payload={},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])

    def test_interrupt_route_delegates_and_parses_turn_id(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "status", "act-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "actor_id": "act-pm-demo",
                        "role": "pm",
                        "status": "active",
                        "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
                        "browser_port": 9222,
                        "updated_at": "2026-05-24T10:00:00Z",
                        "thread_id": "thread-demo",
                        "app_server": {"healthy": True},
                        "thread": {"status": "interrupted", "raw": {}},
                    },
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        runner.add(
            ["instance", "interrupt", "act-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "actor_id": "act-pm-demo",
                        "thread_id": "thread-demo",
                        "turn_id": "turn-demo",
                    },
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/interrupt",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["turn_id"], "turn-demo")
        self.assertEqual(payload["instance"]["thread"]["status"], "interrupted")
        self.assertEqual(
            runner.calls,
            [
                ["instance", "interrupt", "act-pm-demo", "--json"],
                ["instance", "status", "act-pm-demo", "--json"],
            ],
        )

    def test_stop_route_delegates_and_refreshes_status(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "stop", "act-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {"actor_id": "act-pm-demo", "status": "inactive"},
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        runner.add(
            ["instance", "status", "act-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "actor_id": "act-pm-demo",
                        "role": "pm",
                        "status": "inactive",
                        "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
                        "browser_port": 9222,
                        "updated_at": "2026-05-24T10:00:00Z",
                        "thread_id": None,
                        "app_server": {"healthy": False},
                        "thread": {"status": "stopped", "raw": {}},
                    },
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/stop",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["instance"]["status"], "inactive")
        self.assertEqual(
            runner.calls,
            [
                ["instance", "stop", "act-pm-demo", "--json"],
                ["instance", "status", "act-pm-demo", "--json"],
            ],
        )

    def test_delete_route_delegates_and_maps_active_block(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "delete", "act-pm-demo", "--yes", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {"actor_id": "act-pm-demo", "deleted": True},
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(
            base_url,
            method="DELETE",
            path="/api/instances/act-pm-demo",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True, "actor_id": "act-pm-demo"})
        self.assertEqual(runner.calls, [["instance", "delete", "act-pm-demo", "--yes", "--json"]])

        blocked_runner = FakeRunner()
        blocked_runner.add(
            ["instance", "delete", "act-pm-demo", "--yes", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=3,
                stdout="",
                stderr="Instance delete blocked: active app-server still running.",
                timed_out=False,
            ),
        )
        _, blocked_base_url = self._start_server(blocked_runner)
        status, payload = self._request_json(
            blocked_base_url,
            method="DELETE",
            path="/api/instances/act-pm-demo",
        )
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["code"], "LIFECYCLE_BLOCKED")

    def test_invalid_json_body_returns_structured_error(self) -> None:
        runner, base_url = self._start_server()
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances",
            raw_body=b"{bad json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])

    def test_invalid_actor_ids_are_rejected_before_runner(self) -> None:
        for actor_id in ("../bad", "/tmp/demo", "inst bad"):
            with self.subTest(actor_id=actor_id):
                runner, base_url = self._start_server()
                status, payload = self._request_json(
                    base_url,
                    method="GET",
                    path=f"/api/instances/{actor_id}/status",
                )
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
                self.assertEqual(runner.calls, [])

    def test_unknown_api_route_returns_json_404(self) -> None:
        _, base_url = self._start_server()
        status, payload = self._request_json(base_url, method="GET", path="/api/unknown")
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")

    def test_static_assets_are_served(self) -> None:
        _, base_url = self._start_server()
        html_status, html = self._request_text(base_url, method="GET", path="/")
        js_status, js = self._request_text(base_url, method="GET", path="/static/app.js")
        css_status, css = self._request_text(base_url, method="GET", path="/static/styles.css")
        self.assertEqual(html_status, 200)
        self.assertIn("BuddySwitch Web Management", html)
        self.assertIn("webui-root", html)
        self.assertIn("Team room", html)
        self.assertIn("Track Studio", html)
        self.assertNotIn("app-shell", html)
        self.assertNotIn("workspace-page", html)
        self.assertNotIn("Actor Console", html)
        self.assertNotIn("Create Actor", html)
        self.assertEqual(js_status, 200)
        self.assertIn("buildActorConsoleUrl", js)
        self.assertIn("/api/instances", js)
        self.assertEqual(css_status, 200)
        self.assertIn(".webui-root", css)
        self.assertIn(".proto-shell", css)
        self.assertIn(".team-room", css)
        self.assertIn(".track-studio", css)
        self.assertNotIn(".app-shell", css)
        self.assertNotIn(".actor-console-grid", css)
        self.assertNotIn(".team-room-grid", css)


if __name__ == "__main__":
    unittest.main()
