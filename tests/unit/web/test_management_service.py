from __future__ import annotations

import importlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.support.paths import REPO_ROOT
from tests.support.runtime import RuntimeWorkspaceTestCase


ROOT = REPO_ROOT
WEB_MANAGEMENT_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "web_management.py"
WEB_MANAGEMENT = importlib.import_module("buddyswitch.launcher.web_management")


def _restore_env_value(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


class RecordingHostControl:
    """Small same-process fake for Web service delegation tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def _record(
        self,
        operation: str,
        args: tuple[object, ...],
        result: dict[str, object],
    ) -> dict[str, object]:
        self.calls.append((operation, args))
        return dict(result)

    def start(self, role_id: str) -> dict[str, object]:
        actor_id = f"act-{role_id}-demo"
        return self._record(
            "start",
            (role_id,),
            {
                "actor_id": actor_id,
                "role": role_id,
                "workspace_dir": f"/tmp/shared/instances/{actor_id}/workspace",
                "project_workspace_dir": "/tmp/shared/projects/app",
                "instance_record": f"/tmp/shared/instances/{actor_id}/instance.json",
            },
        )

    def status(self, actor_id: str) -> dict[str, object]:
        return self._record(
            "status",
            (actor_id,),
            {
                "actor_id": actor_id,
                "role": "pm",
                "status": "active",
                "workspace_dir": f"/tmp/shared/instances/{actor_id}/workspace",
                "updated_at": "2026-05-25T10:00:00Z",
                "thread_id": "thread-main",
                "browser_port": 9222,
                "app_server": {"healthy": True},
                "daemon": {"connected": True},
                "runtime_broker": {"connected": True},
                "thread": {"status": "idle", "raw": {}},
            },
        )

    def resume(self, actor_id: str) -> dict[str, object]:
        return self._record(
            "resume",
            (actor_id,),
            {"actor_id": actor_id, "thread_id": "thread-main", "status": "active"},
        )

    def interrupt(self, actor_id: str) -> dict[str, object]:
        return self._record(
            "interrupt",
            (actor_id,),
            {"actor_id": actor_id, "thread_id": "thread-main", "turn_id": None},
        )

    def compact(self, actor_id: str) -> dict[str, object]:
        return self._record(
            "compact",
            (actor_id,),
            {"actor_id": actor_id, "thread_id": "thread-main", "started": True},
        )


class WebManagementUnitTests(RuntimeWorkspaceTestCase):
    def test_validate_bind_host_accepts_loopback_only(self) -> None:
        self.assertEqual(WEB_MANAGEMENT.validate_bind_host("127.0.0.1"), "127.0.0.1")
        self.assertEqual(WEB_MANAGEMENT.validate_bind_host("localhost"), "localhost")
        with self.assertRaisesRegex(ValueError, "local"):
            WEB_MANAGEMENT.validate_bind_host("0.0.0.0")

    def test_web_management_source_does_not_own_actor_id_validation(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        self.assertNotIn("VALID_INSTANCE_ID_RE", source)
        self.assertNotIn("def validate_actor_id", source)
        self.assertIn("host_control_module.validate_actor_id", source)

    def test_web_management_tests_do_not_recreate_public_cli_harness(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        forbidden = [
            "Command" + "Result",
            "Fake" + "Runner",
            "Ordered" + "Runner",
            "command_" + "json",
            "command_" + "error",
            "--" + "json",
            '"instance", "' + '"start"',
        ]

        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_build_attach_cli_command_is_short_shell_safe_and_paste_ready(self) -> None:
        command = WEB_MANAGEMENT.build_attach_cli_command("act-pm.demo")

        self.assertEqual(
            command,
            " ".join(
                [
                    WEB_MANAGEMENT.current_runtime_identity().python_executable,
                    "-m",
                    "buddyswitch.application.entrypoints.cli",
                    "instance",
                    "attach",
                    "act-pm.demo",
                ]
            ),
        )

    def test_open_macos_terminal_app_targets_one_window_for_running_and_stopped_terminal(self) -> None:
        completed = WEB_MANAGEMENT.subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )
        command = "cd '/tmp/Buddy Switch' && ./buddyswitch-codex instance attach act-pm.demo"

        with mock.patch.object(WEB_MANAGEMENT.subprocess, "run", return_value=completed) as run:
            WEB_MANAGEMENT.open_macos_terminal_app(command)

        self.assertEqual(
            run.call_args.args[0],
            [
                "osascript",
                "-e",
                "\n".join(
                    [
                        'set terminalWasRunning to application "Terminal" is running',
                        'tell application "Terminal"',
                        "  if terminalWasRunning then",
                        f'    do script "{command}"',
                        "    activate",
                        "  else",
                        "    activate",
                        f'    do script "{command}" in front window',
                        "  end if",
                        "end tell",
                    ]
                ),
            ],
        )

    def test_recording_host_control_defaults_match_host_control_schemas(self) -> None:
        host_control = RecordingHostControl()

        started = host_control.start("pm")
        status = host_control.status("act-pm-demo")
        resumed = host_control.resume("act-pm-demo")
        interrupted = host_control.interrupt("act-pm-demo")
        compacted = host_control.compact("act-pm-demo")

        for field_name in ("actor_id", "role", "workspace_dir", "project_workspace_dir", "instance_record"):
            with self.subTest(operation="start", field=field_name):
                self.assertIsInstance(started.get(field_name), str)
                self.assertTrue(started[field_name])
        for field_name in ("actor_id", "role", "status", "workspace_dir", "updated_at"):
            with self.subTest(operation="status", field=field_name):
                self.assertIsInstance(status.get(field_name), str)
                self.assertTrue(status[field_name])
        for field_name in ("app_server", "daemon", "runtime_broker", "thread"):
            with self.subTest(operation="status", field=field_name):
                self.assertIsInstance(status.get(field_name), dict)
        self.assertIn("thread_id", status)
        self.assertTrue(status["thread_id"] is None or isinstance(status["thread_id"], str))
        self.assertIn("browser_port", status)
        self.assertTrue(status["browser_port"] is None or isinstance(status["browser_port"], int))
        for payload, operation in ((resumed, "resume"), (interrupted, "interrupt"), (compacted, "compact")):
            for field_name in ("actor_id", "thread_id"):
                with self.subTest(operation=operation, field=field_name):
                    self.assertIsInstance(payload.get(field_name), str)
                    self.assertTrue(payload[field_name])
        self.assertIsInstance(resumed.get("status"), str)
        self.assertIn("turn_id", interrupted)
        self.assertTrue(interrupted["turn_id"] is None or isinstance(interrupted["turn_id"], str))
        self.assertIsInstance(compacted.get("started"), bool)

    def test_open_macos_terminal_app_preserves_osascript_diagnostic_line(self) -> None:
        completed = WEB_MANAGEMENT.subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="\nignored stdout detail\n",
            stderr="\n  automation denied\nextra stderr detail\n",
        )

        with (
            mock.patch.object(WEB_MANAGEMENT.subprocess, "run", return_value=completed),
            self.assertRaises(WEB_MANAGEMENT.TerminalOpenError) as raised,
        ):
            WEB_MANAGEMENT.open_macos_terminal_app("echo hello")

        self.assertEqual(str(raised.exception), "automation denied")

    def test_open_tui_task_does_not_expand_launcher_public_surface(self) -> None:
        source = (ROOT / "src" / "buddyswitch" / "launcher" / "cli.py").read_text(encoding="utf-8")

        self.assertNotIn("attach-open", source)
        self.assertIn("instance attach", source)

    def test_web_launcher_ensures_central_daemon_for_web_user_actor(self) -> None:
        source = (ROOT / "src" / "buddyswitch" / "launcher" / "cli.py").read_text(encoding="utf-8")
        start = source.index("def _run_web(")
        end = source.index("\ndef _actor_session(", start)
        block = source[start:end]

        ensure_index = block.index("central_process.start_central_daemon")
        run_index = block.index("subprocess.run")
        helper_index = block.index("buddyswitch.application.entrypoints.web")
        stop_index = block.index("central_process.stop_if_idle")
        self.assertLess(ensure_index, run_index)
        self.assertLess(helper_index, run_index)
        self.assertLess(run_index, stop_index)
        self.assertIn("BUDDYSWITCH_CENTRAL_DAEMON_SOCKET", block)
        self.assertIn("return int(completed.returncode)", block)

    def test_serve_with_workers_starts_stops_and_closes_server(self) -> None:
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
            WEB_MANAGEMENT.serve_with_workers(server, (worker,))

        self.assertTrue(server.served)
        self.assertTrue(server.closed)
        self.assertEqual(worker.started, 1)
        self.assertEqual(worker.stopped, 1)

    def test_serve_with_workers_keeps_server_available_when_worker_start_fails(self) -> None:
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
            WEB_MANAGEMENT.serve_with_workers(server, (worker,))

        self.assertTrue(server.served)
        self.assertTrue(server.closed)
        self.assertEqual(worker.stopped, 0)
        stderr.write.assert_any_call("Web worker 'FakeWorker' disabled: imsg unavailable\n")

    def test_web_management_source_does_not_parse_imessage_control_messages(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        self.assertNotRegex(source, r"""["']/actors["']""")
        self.assertNotIn("pending_actor_choices", source)
        self.assertNotIn("active_actor_id", source)
        self.assertNotIn("[Message From", source)

    def test_web_runtime_binds_shared_state_for_server_owned_web_im_identity(self) -> None:
        import buddyswitch.foundation.state.runtime as state_runtime

        original_state_root = os.environ.get("BUDDYSWITCH_STATE_ROOT")
        original_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
        original_actor_id = os.environ.get("BUDDYSWITCH_ACTOR_ID")
        self.addCleanup(state_runtime.refresh_runtime_roots_from_env)
        self.addCleanup(_restore_env_value, "BUDDYSWITCH_STATE_ROOT", original_state_root)
        self.addCleanup(_restore_env_value, "BUDDYSWITCH_SHARED_ROOT", original_shared_root)
        self.addCleanup(_restore_env_value, "BUDDYSWITCH_ACTOR_ID", original_actor_id)

        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / ".codex-buddyswitch"
            shared_root.mkdir()
            os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            os.environ.pop("BUDDYSWITCH_STATE_ROOT", None)
            os.environ.pop("BUDDYSWITCH_ACTOR_ID", None)
            state_runtime.refresh_runtime_roots_from_env()

            WEB_MANAGEMENT.bind_web_runtime_state()
            from buddyswitch.application.build import build_application

            service = WEB_MANAGEMENT.WebManagementService(
                host_control=RecordingHostControl(),
                web_routes=build_application().web_routes,
            )
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

    def test_map_host_control_failure_uses_required_status_codes(self) -> None:
        cases = [
            (
                WEB_MANAGEMENT.host_control_module.HostControlError("INVALID_REQUEST", "Bad request", returncode=2),
                400,
                "INVALID_REQUEST",
            ),
            (
                WEB_MANAGEMENT.host_control_module.HostControlError(
                    "LIFECYCLE_BLOCKED",
                    "Instance delete blocked: active",
                    returncode=3,
                ),
                409,
                "LIFECYCLE_BLOCKED",
            ),
            (
                WEB_MANAGEMENT.host_control_module.HostControlError(
                    "COMMAND_TIMEOUT",
                    "internal error",
                    timed_out=True,
                ),
                504,
                "COMMAND_TIMEOUT",
            ),
            (
                WEB_MANAGEMENT.host_control_module.HostControlError("COMMAND_FAILED", "internal error"),
                502,
                "COMMAND_FAILED",
            ),
            (
                WEB_MANAGEMENT.host_control_module.HostControlError(
                    "RUNTIME_MISMATCH",
                    "recorded runtime changed",
                    returncode=5,
                ),
                409,
                "RUNTIME_MISMATCH",
            ),
            (
                WEB_MANAGEMENT.host_control_module.HostControlError(
                    "RUNTIME_UNAVAILABLE",
                    "runtime not found",
                    returncode=5,
                ),
                503,
                "RUNTIME_UNAVAILABLE",
            ),
        ]
        for host_error, expected_status, expected_code in cases:
            with self.subTest(host_error=host_error):
                error = WEB_MANAGEMENT.map_host_control_failure(host_error)
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

    def test_web_entrypoint_rejects_non_local_web_host(self) -> None:
        stderr = io.StringIO()

        with mock.patch("sys.stderr", stderr):
            result = WEB_MANAGEMENT.main(
                ["--host", "0.0.0.0"],
                host_control=RecordingHostControl(),
            )

        self.assertEqual(result, 2)
        self.assertIn("local", stderr.getvalue())

    def test_web_host_does_not_own_im_delivery(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        self.assertNotIn("im_actor_delivery", source)
        self.assertNotIn("check_reachability", source)
        self.assertNotIn("_deliver_im_actor", source)
