#!/usr/bin/env python3
"""Tests for the BuddySwitch local web management API."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
import unittest
from dataclasses import dataclass
from pathlib import Path
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


def active_status(instance_id: str, thread_id: str, thread_status: str) -> dict[str, object]:
    return {
        "instance_id": instance_id,
        "buddy": "pm",
        "status": "active",
        "workspace_dir": f"/tmp/shared/instances/{instance_id}/workspace",
        "browser_port": 9222,
        "updated_at": "2026-05-25T10:00:00Z",
        "thread_id": thread_id,
        "app_server": {"healthy": True},
        "thread": {"status": thread_status, "raw": {}},
    }


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
    def _start_server(self, runner: FakeRunner | None = None) -> tuple[FakeRunner, str]:
        fake_runner = runner or FakeRunner()
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=fake_runner.run)
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

    def test_validate_instance_id_rejects_traversal_like_values(self) -> None:
        for instance_id in ("", "../bad", "/tmp/inst-demo", "inst bad", "demo"):
            with self.subTest(instance_id=instance_id):
                with self.assertRaisesRegex(ValueError, "instance id"):
                    WEB_MANAGEMENT.validate_instance_id(instance_id)
        self.assertEqual(WEB_MANAGEMENT.validate_instance_id("inst-pm-demo"), "inst-pm-demo")

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
        self.assertTrue(guard.acquire("instance:inst-pm-demo"))
        self.assertFalse(guard.acquire("instance:inst-pm-demo"))
        guard.release("instance:inst-pm-demo")

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
            ["instance", "buddies", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "buddies": [
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
        status, payload = self._request_json(base_url, method="GET", path="/api/buddies")
        self.assertEqual(status, 200)
        self.assertEqual(
            payload,
            {
                "ok": True,
                "buddies": [
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
        self.assertEqual(runner.calls, [["instance", "buddies", "--json"]])

    def test_buddies_route_returns_structured_error_for_malformed_launcher_json(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "buddies", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout="{bad json",
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/buddies")
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
                                "instance_id": "inst-pm-demo",
                                "buddy": "pm",
                                "status": "active",
                                "app_server_health": "healthy",
                                "thread_id": "thread-pm",
                                "browser_port": 9222,
                                "updated_at": "2026-05-24T10:00:00Z",
                                "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
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
                        "instance_id": "inst-pm-demo",
                        "buddy": "pm",
                        "status": "active",
                        "app_server_health": "healthy",
                        "thread_id": "thread-pm",
                        "browser_port": 9222,
                        "updated_at": "2026-05-24T10:00:00Z",
                        "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
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
            ["instance", "status", "inst-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "instance_id": "inst-pm-demo",
                        "buddy": "pm",
                        "status": "active",
                        "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
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
        status, payload = self._request_json(base_url, method="GET", path="/api/instances/inst-pm-demo/status")
        self.assertEqual(status, 200)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["instance"]["thread"]["status"], "idle")
        self.assertEqual(payload["instance"]["app_server"]["healthy"], True)
        self.assertEqual(payload["instance"]["thread_id"], "thread-demo")

    def test_create_route_validates_buddy_before_start(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "buddies", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "buddies": [
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
            payload={"buddy": "unknown"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(runner.calls, [["instance", "buddies", "--json"]])

    def test_create_instance_delegates_to_launcher_start_without_initialize_input(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "buddies", "--json"],
                    command_json({"buddies": [{"id": "pm", "label": "PM", "scope": "product"}]}),
                ),
                CommandStep(
                    ["instance", "start", "--buddy", "pm", "--json"],
                    command_json({"instance_id": "inst-pm-demo"}),
                ),
                CommandStep(
                    ["instance", "status", "inst-pm-demo", "--json"],
                    command_json(active_status("inst-pm-demo", "thread-1", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances", b'{"buddy":"pm"}')

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["instance_id"], "inst-pm-demo")
        self.assertEqual(payload["instance"]["thread"]["status"], "idle")
        self.assertEqual(payload["instance"]["thread_id"], "thread-1")
        self.assertEqual(len(runner.calls), 3)
        self.assertNotIn("Initialize this " "BuddySwitch thread", json.dumps(runner.calls))
        self.assertEqual(runner.steps, [])

    def test_create_instance_returns_launcher_start_error_without_initialize_retry(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "buddies", "--json"],
                    command_json({"buddies": [{"id": "pm", "label": "PM", "scope": "product"}]}),
                ),
                CommandStep(
                    ["instance", "start", "--buddy", "pm", "--json"],
                    command_error(returncode=1, stderr="Thread bootstrap failed for thread-1."),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances", b'{"buddy":"pm"}')

        self.assertEqual(raised.exception.status, 502)
        self.assertEqual(raised.exception.code, "COMMAND_FAILED")
        self.assertIn("Thread bootstrap failed", raised.exception.message)
        self.assertEqual(len(runner.calls), 2)

    def test_clear_route_delegates_to_launcher_clear_without_initialize_input(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "clear", "inst-pm-demo", "--json"],
                    command_json(
                        {
                            "instance_id": "inst-pm-demo",
                            "previous_thread_id": "thread-old",
                            "thread_id": "thread-new",
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "inst-pm-demo", "--json"],
                    command_json(active_status("inst-pm-demo", "thread-new", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances/inst-pm-demo/clear", b"")

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
                    ["instance", "clear", "inst-pm-demo", "--json"],
                    command_error(returncode=1, stderr="Daemon start failed for inst-pm-demo."),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/inst-pm-demo/clear", b"")

        self.assertEqual(raised.exception.status, 502)
        self.assertEqual(raised.exception.code, "COMMAND_FAILED")
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0][0], ["instance", "clear", "inst-pm-demo", "--json"])

    def test_initialize_route_is_removed(self) -> None:
        runner = OrderedRunner([])
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/inst-pm-demo/" + "initialize", b"")

        self.assertEqual(raised.exception.status, 404)
        self.assertEqual(raised.exception.code, "NOT_FOUND")
        self.assertEqual(runner.calls, [])

    def test_resume_route_delegates_to_launcher_resume(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "resume", "inst-pm-demo", "--json"],
                    command_json({"instance_id": "inst-pm-demo", "thread_id": "thread-1", "status": "active"}),
                ),
                CommandStep(
                    ["instance", "status", "inst-pm-demo", "--json"],
                    command_json(active_status("inst-pm-demo", "thread-1", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances/inst-pm-demo/resume", b"")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["instance"]["status"], "active")
        self.assertEqual(runner.calls[0][0], ["instance", "resume", "inst-pm-demo", "--json"])

    def test_create_route_returns_structured_error_for_malformed_launcher_json(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "buddies", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "buddies": [
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
            ["instance", "start", "--buddy", "pm", "--json"],
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
            payload={"buddy": "pm"},
        )
        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["code"], "COMMAND_FAILED")

    def test_input_route_rejects_empty_text(self) -> None:
        runner, base_url = self._start_server()
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/inst-pm-demo/input",
            payload={"text": "   "},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])

    def test_input_route_delegates_and_reports_started_vs_steered_turn(self) -> None:
        for command_payload, expected_action, expected_turn_id in (
            (
                {
                    "instance_id": "inst-pm-demo",
                    "thread_id": "thread-demo",
                    "action": "start",
                    "turn_id": "turn-demo",
                },
                "start",
                None,
            ),
            (
                {
                    "instance_id": "inst-pm-demo",
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
                        "inst-pm-demo",
                        "--text",
                        "Advance the brief",
                        "--input-wrapper",
                        "task-tui",
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
                    ["instance", "status", "inst-pm-demo", "--json"],
                    WEB_MANAGEMENT.CommandResult(
                        returncode=0,
                        stdout=json.dumps(
                            {
                                "instance_id": "inst-pm-demo",
                                "buddy": "pm",
                                "status": "active",
                                "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
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
                    path="/api/instances/inst-pm-demo/input",
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
                            "inst-pm-demo",
                            "--text",
                            "Advance the brief",
                            "--input-wrapper",
                            "task-tui",
                            "--json",
                        ],
                        ["instance", "status", "inst-pm-demo", "--json"],
                    ],
                )

    def test_side_create_route_delegates_and_reports_side_thread_id(self) -> None:
        runner = OrderedRunner(
            [
                CommandStep(
                    ["instance", "side", "inst-pm-demo", "--text", "Explore", "--json"],
                    command_json(
                        {
                            "instance_id": "inst-pm-demo",
                            "action": "start",
                            "thread_action": "start",
                            "parent_thread_id": "thread-main",
                            "side_thread_id": "thread-side-1",
                            "turn_id": "turn-side-1",
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "inst-pm-demo", "--json"],
                    command_json(active_status("inst-pm-demo", "thread-main", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances/inst-pm-demo/side", b'{"text":"Explore"}')

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
                        "inst-pm-demo",
                        "--side-thread-id",
                        "thread-side-1",
                        "--text",
                        "Follow up",
                        "--json",
                    ],
                    command_json(
                        {
                            "instance_id": "inst-pm-demo",
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
                    ["instance", "status", "inst-pm-demo", "--json"],
                    command_json(active_status("inst-pm-demo", "thread-main", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api(
            "POST",
            "/api/instances/inst-pm-demo/side",
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
                        "inst-pm-demo",
                        "--side-thread-id",
                        "thread-side-1",
                        "--json",
                    ],
                    command_json(
                        {
                            "instance_id": "inst-pm-demo",
                            "action": "close",
                            "parent_thread_id": "thread-main",
                            "side_thread_id": "thread-side-1",
                            "turn_id": "turn-side-1",
                            "startup_interrupt": False,
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "inst-pm-demo", "--json"],
                    command_json(active_status("inst-pm-demo", "thread-main", "idle")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api(
            "POST",
            "/api/instances/inst-pm-demo/side/close",
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
            path="/api/instances/inst-pm-demo/side",
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
            path="/api/instances/inst-pm-demo/side/close",
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
                        "inst-pm-demo",
                        "--text",
                        "User task",
                        "--input-wrapper",
                        "task-tui",
                        "--json",
                    ],
                    command_json(
                        {
                            "instance_id": "inst-pm-demo",
                            "thread_id": "thread-1",
                            "action": "start",
                            "turn_id": "turn-user",
                        }
                    ),
                ),
                CommandStep(
                    ["instance", "status", "inst-pm-demo", "--json"],
                    command_json(active_status("inst-pm-demo", "thread-1", "active")),
                ),
            ]
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, command_runner=runner.run)

        status, payload = service.handle_api("POST", "/api/instances/inst-pm-demo/input", b'{"text":"User task"}')

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
                "inst-pm-demo",
                "--text",
                "Advance the brief",
                "--input-wrapper",
                "task-tui",
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
            path="/api/instances/inst-pm-demo/input",
            payload={"text": "Advance the brief"},
        )
        self.assertEqual(status, 502)
        self.assertEqual(payload["error"]["code"], "COMMAND_FAILED")

    def test_interrupt_route_delegates_and_parses_turn_id(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "status", "inst-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "instance_id": "inst-pm-demo",
                        "buddy": "pm",
                        "status": "active",
                        "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
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
            ["instance", "interrupt", "inst-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "instance_id": "inst-pm-demo",
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
            path="/api/instances/inst-pm-demo/interrupt",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["turn_id"], "turn-demo")
        self.assertEqual(payload["instance"]["thread"]["status"], "interrupted")
        self.assertEqual(
            runner.calls,
            [
                ["instance", "interrupt", "inst-pm-demo", "--json"],
                ["instance", "status", "inst-pm-demo", "--json"],
            ],
        )

    def test_stop_route_delegates_and_refreshes_status(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "stop", "inst-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {"instance_id": "inst-pm-demo", "status": "inactive"},
                    ensure_ascii=True,
                ),
                stderr="",
                timed_out=False,
            ),
        )
        runner.add(
            ["instance", "status", "inst-pm-demo", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {
                        "instance_id": "inst-pm-demo",
                        "buddy": "pm",
                        "status": "inactive",
                        "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
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
            path="/api/instances/inst-pm-demo/stop",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["instance"]["status"], "inactive")
        self.assertEqual(
            runner.calls,
            [
                ["instance", "stop", "inst-pm-demo", "--json"],
                ["instance", "status", "inst-pm-demo", "--json"],
            ],
        )

    def test_delete_route_delegates_and_maps_active_block(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "delete", "inst-pm-demo", "--yes", "--json"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=json.dumps(
                    {"instance_id": "inst-pm-demo", "deleted": True},
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
            path="/api/instances/inst-pm-demo",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True, "instance_id": "inst-pm-demo"})
        self.assertEqual(runner.calls, [["instance", "delete", "inst-pm-demo", "--yes", "--json"]])

        blocked_runner = FakeRunner()
        blocked_runner.add(
            ["instance", "delete", "inst-pm-demo", "--yes", "--json"],
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
            path="/api/instances/inst-pm-demo",
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

    def test_invalid_instance_ids_are_rejected_before_runner(self) -> None:
        for instance_id in ("../bad", "/tmp/demo", "inst bad"):
            with self.subTest(instance_id=instance_id):
                runner, base_url = self._start_server()
                status, payload = self._request_json(
                    base_url,
                    method="GET",
                    path=f"/api/instances/{instance_id}/status",
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
