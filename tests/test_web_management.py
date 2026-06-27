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


class FakeWebMessageSender:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def send(self, *, target_actor_address: dict[str, object], content: str) -> dict[str, object]:
        self.calls.append({"target_actor_address": target_actor_address, "content": content})
        return dict(self.result)


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
        web_message_sender: Callable[..., dict[str, object]] | None = None,
    ) -> tuple[FakeRunner, str]:
        fake_runner = runner or FakeRunner()
        service_kwargs: dict[str, object] = {}
        if terminal_opener is not None:
            service_kwargs["terminal_opener"] = terminal_opener
        if platform_name is not None:
            service_kwargs["platform_name"] = platform_name
        if web_message_sender is not None:
            service_kwargs["web_message_sender"] = web_message_sender
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

    def test_web_runtime_binds_shared_state_for_central_im_without_actor_identity(self) -> None:
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
            status, payload = service.handle_api(
                "POST",
                "/api/im/connections",
                json.dumps({"display_name": "probe"}).encode("utf-8"),
                {},
            )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertIn("connection_key", payload)
            self.assertEqual(os.environ.get("BUDDYSWITCH_STATE_ROOT"), str(shared_root / "state"))
            self.assertNotIn("BUDDYSWITCH_ACTOR_ID", os.environ)

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
                WEB_MANAGEMENT.CommandResult(
                    returncode=1,
                    stdout="",
                    stderr="Instance input blocked: active turn is not healthy",
                    timed_out=False,
                ),
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
            "target_actor_address": {"role_id": "pm", "actor_id": "act-pm-demo"},
            "message_id": "msg-1",
            "conversation_id": "conv-1",
            "event_id": "imev-1",
        }
        with mock.patch.object(
            WEB_MANAGEMENT.daemon_client,
            "wake_im_actor",
            return_value={"wake_status": "submitted", "runtime_target": "parent", "error": None},
        ) as wake_im_actor:
            result = service._wake_im_actor(payload)

        self.assertEqual(result["wake_status"], "submitted")
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

    def test_input_route_rejects_empty_text(self) -> None:
        runner, base_url = self._start_server()
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/input",
            payload={"text": "   "},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])

    def test_input_route_delegates_and_reports_started_vs_steered_turn(self) -> None:
        for command_payload, expected_action, expected_turn_id in (
            (
                {
                    "actor_id": "act-pm-demo",
                    "thread_id": "thread-demo",
                    "action": "start",
                    "turn_id": "turn-demo",
                },
                "start",
                None,
            ),
            (
                {
                    "actor_id": "act-pm-demo",
                    "thread_id": "thread-demo",
                    "action": "steer",
                    "turn_id": "turn-steer",
                    "expected_turn_id": "turn-steer",
                },
                "steer",
                "turn-steer",
            ),
        ):
            with self.subTest(command_payload=command_payload):
                runner = FakeRunner()
                runner.add(
                    [
                        "instance",
                        "input",
                        "act-pm-demo",
                        "--text",
                        "Advance the brief",
                        "--json",
                    ],
                    WEB_MANAGEMENT.CommandResult(
                        returncode=0,
                        stdout=json.dumps(command_payload, ensure_ascii=True),
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
                status, payload = self._request_json(
                    base_url,
                    method="POST",
                    path="/api/instances/act-pm-demo/input",
                    payload={"text": "Advance the brief"},
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["action"], expected_action)
                if expected_turn_id is None:
                    self.assertNotIn("expected_turn_id", payload)
                else:
                    self.assertEqual(payload["expected_turn_id"], expected_turn_id)
                self.assertEqual(
                    runner.calls,
                    [
                        [
                            "instance",
                            "input",
                            "act-pm-demo",
                            "--text",
                            "Advance the brief",
                            "--json",
                        ],
                        ["instance", "status", "act-pm-demo", "--json"],
                    ],
                )

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
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

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
                            "startup_interrupt": False,
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
        self.assertFalse(payload["startup_interrupt"])
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

    def test_user_input_does_not_use_internal_bootstrap_marker(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    [
                        "instance",
                        "input",
                        "act-pm-demo",
                        "--text",
                        "User task",
                        "--json",
                    ],
                    command_json(
                        {
                            "actor_id": "act-pm-demo",
                            "thread_id": "thread-1",
                            "action": "start",
                            "turn_id": "turn-user",
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "act-pm-demo", "--json"],
                    command_json(active_status("act-pm-demo", "thread-1", "active")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/input", b'{"text":"User task"}')

        self.assertEqual(status, 200)
        self.assertEqual(payload["turn_id"], "turn-user")
        self.assertNotIn("Initialize this " "BuddySwitch thread", json.dumps(runner.calls))
        self.assertNotIn("[BuddySwitch internal bootstrap marker]", json.dumps(runner.calls))

    def test_input_route_returns_structured_error_for_malformed_launcher_json(self) -> None:
        runner = FakeRunner()
        runner.add(
            [
                "instance",
                "input",
                "act-pm-demo",
                "--text",
                "Advance the brief",
                "--json",
            ],
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
            path="/api/instances/act-pm-demo/input",
            payload={"text": "Advance the brief"},
        )
        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["code"], "COMMAND_FAILED")

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
        self.assertIn("/api/instances", html)
        self.assertEqual(js_status, 200)
        self.assertIn("computeInstanceActionState", js)
        self.assertEqual(css_status, 200)
        self.assertIn(".app-shell", css)


if __name__ == "__main__":
    unittest.main()
