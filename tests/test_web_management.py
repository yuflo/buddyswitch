#!/usr/bin/env python3
"""Tests for the BuddySwitch local web management API."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
import unittest
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

    def test_parse_buddies_tsv_returns_expected_rows(self) -> None:
        payload = WEB_MANAGEMENT.parse_buddies_tsv(
            "pm\tPM\tOwn product iteration and track progression.\n"
            "dev\tDev\tImplement approved scope in project code.\n"
        )
        self.assertEqual(
            payload,
            [
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
        )

    def test_parse_instance_list_handles_empty_and_rows(self) -> None:
        self.assertEqual(
            WEB_MANAGEMENT.parse_instance_list_tsv(
                "No BuddySwitch instances found.\n"
                "Start one with: ./buddyswitch-codex instance start --buddy <buddy>\n"
            ),
            [],
        )
        payload = WEB_MANAGEMENT.parse_instance_list_tsv(
            "instance_id\tbuddy\tstatus\tapp_server_health\tthread_id\tbrowser_port\tupdated_at\tworkspace_dir\n"
            "inst-pm-demo\tpm\tactive\thealthy\tthread-pm\t9222\t2026-05-24T10:00:00Z\t/tmp/shared/instances/inst-pm-demo/workspace\n"
            "inst-dev-demo\tdev\tinactive\tunhealthy\t\t9223\t2026-05-24T10:01:00Z\t/tmp/shared/instances/inst-dev-demo/workspace\n"
        )
        self.assertEqual(
            payload,
            [
                {
                    "instance_id": "inst-pm-demo",
                    "buddy": "pm",
                    "status": "active",
                    "app_server_health": "healthy",
                    "thread_id": "thread-pm",
                    "browser_port": 9222,
                    "updated_at": "2026-05-24T10:00:00Z",
                    "workspace_dir": "/tmp/shared/instances/inst-pm-demo/workspace",
                },
                {
                    "instance_id": "inst-dev-demo",
                    "buddy": "dev",
                    "status": "inactive",
                    "app_server_health": "unhealthy",
                    "thread_id": None,
                    "browser_port": 9223,
                    "updated_at": "2026-05-24T10:01:00Z",
                    "workspace_dir": "/tmp/shared/instances/inst-dev-demo/workspace",
                },
            ],
        )

    def test_parse_start_and_turn_output(self) -> None:
        self.assertEqual(
            WEB_MANAGEMENT.parse_started_instance_id(
                "BuddySwitch instance: inst-pm-20260524-demo (pm)\nWorkspace: /tmp/demo\n"
            ),
            "inst-pm-20260524-demo",
        )
        self.assertEqual(
            WEB_MANAGEMENT.parse_turn_action_output("Started turn: turn-demo\n"),
            {"action": "start", "turn_id": "turn-demo"},
        )
        self.assertEqual(
            WEB_MANAGEMENT.parse_turn_action_output("Steered turn: turn-demo\n"),
            {"action": "steer", "turn_id": "turn-demo"},
        )
        self.assertEqual(
            WEB_MANAGEMENT.parse_interrupt_turn_id("Interrupted turn: turn-demo\n"),
            "turn-demo",
        )

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

    def test_buddies_route_comes_from_cli_tsv(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "buddies"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=(
                    "pm\tPM\tOwn product iteration and track progression.\n"
                    "dev\tDev\tImplement approved scope in project code.\n"
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
        self.assertEqual(runner.calls, [["instance", "buddies"]])

    def test_instances_route_returns_empty_array_for_empty_cli_output(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "list"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=(
                    "No BuddySwitch instances found.\n"
                    "Start one with: ./buddyswitch-codex instance start --buddy <buddy>\n"
                ),
                stderr="",
                timed_out=False,
            ),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/instances")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True, "instances": []})

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
            ["instance", "buddies"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout="pm\tPM\tOwn product iteration and track progression.\n",
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
        self.assertEqual(runner.calls, [["instance", "buddies"]])

    def test_create_route_starts_instance_and_refreshes_status(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "buddies"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout="pm\tPM\tOwn product iteration and track progression.\n",
                stderr="",
                timed_out=False,
            ),
        )
        runner.add(
            ["instance", "start", "--buddy", "pm"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout=(
                    "BuddySwitch instance: inst-pm-demo (pm)\n"
                    "Workspace: /tmp/shared/instances/inst-pm-demo/workspace\n"
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
            path="/api/instances",
            payload={"buddy": "pm"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["instance_id"], "inst-pm-demo")
        self.assertEqual(payload["instance"]["thread_id"], "thread-demo")
        self.assertEqual(
            runner.calls,
            [
                ["instance", "buddies"],
                ["instance", "start", "--buddy", "pm"],
                ["instance", "status", "inst-pm-demo", "--json"],
            ],
        )

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
        for stdout, expected_action in (
            ("Started turn: turn-demo\n", "start"),
            ("Steered turn: turn-steer\n", "steer"),
        ):
            with self.subTest(stdout=stdout):
                runner = FakeRunner()
                runner.add(
                    ["instance", "input", "inst-pm-demo", "--text", "Advance the brief"],
                    WEB_MANAGEMENT.CommandResult(
                        returncode=0,
                        stdout=stdout,
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
                self.assertEqual(
                    runner.calls,
                    [
                        ["instance", "input", "inst-pm-demo", "--text", "Advance the brief"],
                        ["instance", "status", "inst-pm-demo", "--json"],
                    ],
                )

    def test_interrupt_route_delegates_and_parses_turn_id(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "interrupt", "inst-pm-demo"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout="Interrupted turn: turn-demo\n",
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
                        "thread": {"status": "interrupted", "raw": {}},
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

    def test_stop_route_delegates_and_refreshes_status(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "stop", "inst-pm-demo"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout="Instance stopped: inst-pm-demo\n",
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
                ["instance", "stop", "inst-pm-demo"],
                ["instance", "status", "inst-pm-demo", "--json"],
            ],
        )

    def test_delete_route_delegates_and_maps_active_block(self) -> None:
        runner = FakeRunner()
        runner.add(
            ["instance", "delete", "inst-pm-demo", "--yes"],
            WEB_MANAGEMENT.CommandResult(
                returncode=0,
                stdout="Instance deleted: inst-pm-demo\n",
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
        self.assertEqual(runner.calls, [["instance", "delete", "inst-pm-demo", "--yes"]])

        blocked_runner = FakeRunner()
        blocked_runner.add(
            ["instance", "delete", "inst-pm-demo", "--yes"],
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
        self.assertIn(".management-shell", css)


if __name__ == "__main__":
    unittest.main()
