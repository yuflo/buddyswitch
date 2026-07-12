#!/usr/bin/env python3
"""Tests for launcher-owned browser runtime manager."""

from __future__ import annotations

import json
import contextlib
import io
import os
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.launcher import browser_runtime_manager as manager  # noqa: E402
from tools.launcher import daemon_state  # noqa: E402


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def wait_until(predicate: object, *, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(0.05)
    return bool(predicate())  # type: ignore[operator]


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def port_accepts(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.2)
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


class BrowserRuntimeManagerTests(unittest.TestCase):
    def _write_instance(self, instance_root: Path, actor_id: str = "act-dev-browser", *, browser_port: int | None = None) -> Path:
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": "dev",
                    "status": "active",
                    "instance_root": str(instance_root),
                    "workspace_dir": str(instance_root / "workspace"),
                    "thread_id": "thr-main",
                    "browser_port": browser_port,
                    "created_at": "2026-07-02T00:00:00Z",
                    "updated_at": "2026-07-02T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _daemon_state(self, instance_root: Path, actor_id: str = "act-dev-browser") -> Any:
        return daemon_state.DaemonState.load(
            instance_root=instance_root,
            actor_id=actor_id,
            main_thread_id="thr-main",
        )

    def _saved_daemon_state(self, instance_root: Path) -> dict[str, Any]:
        return json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))

    def _write_fake_chrome(self, path: Path, argv_path: Path) -> None:
        path.write_text(
            textwrap.dedent(
                f"""\
                #!/usr/bin/env python3
                from http.server import BaseHTTPRequestHandler, HTTPServer
                import json
                import sys

                argv_path = {str(argv_path)!r}
                port = None
                for arg in sys.argv[1:]:
                    if arg.startswith("--remote-debugging-port="):
                        port = int(arg.split("=", 1)[1])
                if port is None:
                    raise SystemExit("missing remote debugging port")
                with open(argv_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(sys.argv[1:], ensure_ascii=True) + "\\n")

                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *_args):
                        return

                    def do_GET(self):
                        if self.path == "/json/version":
                            payload = {{
                                "Browser": "fake",
                                "webSocketDebuggerUrl": f"ws://127.0.0.1:{{port}}/devtools/browser/fake",
                            }}
                        elif self.path == "/json/list":
                            payload = [{{"id": "ready", "type": "page", "url": "about:blank"}}]
                        else:
                            self.send_response(404)
                            self.end_headers()
                            return
                        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)

                server = HTTPServer(("127.0.0.1", port), Handler)
                server.serve_forever()
                """
            ),
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | 0o700)

    def _terminate_process(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        if not wait_until(lambda: not pid_alive(pid), timeout=2.0):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                return

    def _cleanup_process(self, proc: subprocess.Popen[str], log_handle: Any | None = None) -> None:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=2.0)
        if log_handle is not None:
            try:
                if not log_handle.closed:
                    log_handle.close()
            except OSError:
                pass

    def _start_fake_chrome(self, chrome_bin: Path, *, port: int, profile_dir: Path, log_file: Path) -> subprocess.Popen[str]:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_file.open("a", encoding="utf-8")
        proc = subprocess.Popen(
            [
                str(chrome_bin),
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "about:blank",
            ],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        self.addCleanup(self._cleanup_process, proc, log_handle)
        self.assertTrue(wait_until(lambda: port_accepts(port)), "fake Chrome endpoint did not become ready")
        return proc

    def test_acquire_starts_chrome_records_port_and_pid_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            instance_json = self._write_instance(instance_root)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            port = free_port()

            result = manager.acquire(
                instance_root=instance_root,
                actor_id="act-dev-browser",
                requested_port=port,
                chrome_bin=chrome_bin,
            )

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("browser_port"), port)
            self.assertEqual(result.get("browser_url"), f"http://127.0.0.1:{port}")
            self.assertEqual(result.get("state_changed"), True)
            self.assertEqual(result.get("durability"), "runtime")
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertEqual(instance_payload["browser_port"], port)
            pid_file = instance_root / "browser" / "chrome.pid"
            self.assertTrue(pid_file.exists())
            browser_pid = int(pid_file.read_text(encoding="utf-8").strip())
            self.assertTrue(pid_alive(browser_pid))
            argv = [json.loads(line) for line in chrome_argv.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(argv), 1)
            self.assertIn(f"--remote-debugging-port={port}", argv[0])
            self.assertIn(f"--user-data-dir={instance_root / 'browser' / 'profile'}", argv[0])

            release = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="test_cleanup")
            self.assertTrue(release.get("ok"), msg=release)
            self.assertTrue(wait_until(lambda: not pid_alive(browser_pid)), "release must stop fake Chrome")
            self.assertEqual(manager._DETACHED_BROWSER_PROCESSES, [])

    def test_acquire_reuses_owned_recorded_ready_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            self._write_instance(instance_root, browser_port=port)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=instance_root / "browser" / "profile",
                log_file=instance_root / "browser" / "chrome.log",
            )
            (instance_root / "browser").mkdir(parents=True, exist_ok=True)
            (instance_root / "browser" / "chrome.pid").write_text(f"{proc.pid}\n", encoding="utf-8")

            result = manager.acquire(instance_root=instance_root, actor_id="act-dev-browser")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("browser_port"), port)
            self.assertEqual(result.get("state_changed"), False)
            argv = [json.loads(line) for line in chrome_argv.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(argv), 1, "acquire should not start another Chrome when owned endpoint is ready")

    def test_release_cleans_owned_runtime_state(self) -> None:
        upstream_proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
        upstream_pgid = os.getpgid(upstream_proc.pid)
        self.addCleanup(self._cleanup_process, upstream_proc)

        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            instance_json = self._write_instance(instance_root, browser_port=port)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            chrome_proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=instance_root / "browser" / "profile",
                log_file=instance_root / "browser" / "chrome.log",
            )
            browser_dir = instance_root / "browser"
            runtime_browser_dir = instance_root / "runtime" / "browser"
            browser_dir.mkdir(parents=True, exist_ok=True)
            runtime_browser_dir.mkdir(parents=True, exist_ok=True)
            (browser_dir / "chrome.pid").write_text(f"{chrome_proc.pid}\n", encoding="utf-8")
            (runtime_browser_dir / "cockpit-upstream.pid").write_text(f"{upstream_proc.pid}\n", encoding="utf-8")
            (runtime_browser_dir / "cockpit-upstream.pgid").write_text(f"{upstream_pgid}\n", encoding="utf-8")
            (runtime_browser_dir / "page_idle.json").write_text("{}", encoding="utf-8")
            (runtime_browser_dir / "page_idle.lock").write_text("", encoding="utf-8")

            result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="page_idle_empty")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("handled"), True)
            self.assertEqual(result.get("state_changed"), True)
            self.assertTrue(wait_until(lambda: not pid_alive(chrome_proc.pid)), "release must stop Chrome pid")
            self.assertTrue(wait_until(lambda: not pid_alive(upstream_proc.pid)), "release must stop upstream pid")
            self.assertFalse((browser_dir / "chrome.pid").exists())
            self.assertFalse((runtime_browser_dir / "cockpit-upstream.pid").exists())
            self.assertFalse((runtime_browser_dir / "cockpit-upstream.pgid").exists())
            self.assertFalse((runtime_browser_dir / "page_idle.json").exists())
            self.assertFalse((runtime_browser_dir / "page_idle.lock").exists())
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertIsNone(instance_payload["browser_port"])

    def test_release_cancels_browser_owned_pending_schedules_after_runtime_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            instance_json = self._write_instance(instance_root, browser_port=port)
            runtime_browser_dir = instance_root / "runtime" / "browser"
            runtime_browser_dir.mkdir(parents=True, exist_ok=True)
            (runtime_browser_dir / "page_idle.json").write_text("{}", encoding="utf-8")
            (runtime_browser_dir / "page_idle.lock").write_text("", encoding="utf-8")
            state = self._daemon_state(instance_root)
            page_expired = state.create_schedule(
                delay_seconds=600,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-1"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:00Z",
            )
            cockpit_release = state.create_schedule(
                delay_seconds=600,
                trigger_type="browser.cockpit.release",
                payload={"reason": "idle_empty"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:01Z",
            )
            task_schedule = state.create_schedule(
                delay_seconds=600,
                trigger_type="task.example",
                payload={"task_id": "task-1"},
                source_context={"owner": "task"},
                now="2026-07-04T00:00:02Z",
            )

            result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="page_idle_empty")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("canceled_browser_schedule_ids"), [page_expired["schedule_id"], cockpit_release["schedule_id"]])
            self.assertEqual(result.get("canceled_browser_schedule_count"), 2)
            self.assertFalse((runtime_browser_dir / "page_idle.json").exists())
            self.assertFalse((runtime_browser_dir / "page_idle.lock").exists())
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertIsNone(instance_payload["browser_port"])
            saved = self._saved_daemon_state(instance_root)
            self.assertEqual(saved["scheduled_triggers"][page_expired["schedule_id"]]["status"], "canceled")
            self.assertEqual(saved["scheduled_triggers"][cockpit_release["schedule_id"]]["status"], "canceled")
            self.assertEqual(saved["scheduled_triggers"][task_schedule["schedule_id"]]["status"], "pending")

    def test_stop_cancels_browser_owned_pending_schedules_when_runtime_is_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_instance(instance_root, browser_port=None)
            state = self._daemon_state(instance_root)
            page_expired = state.create_schedule(
                delay_seconds=600,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-1"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:00Z",
            )
            task_schedule = state.create_schedule(
                delay_seconds=600,
                trigger_type="task.example",
                payload={"task_id": "task-1"},
                source_context={"owner": "task"},
                now="2026-07-04T00:00:01Z",
            )

            result = manager.stop(instance_root=instance_root, actor_id="act-dev-browser")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("canceled_browser_schedule_ids"), [page_expired["schedule_id"]])
            self.assertEqual(result.get("canceled_browser_schedule_count"), 1)
            saved = self._saved_daemon_state(instance_root)
            self.assertEqual(saved["scheduled_triggers"][page_expired["schedule_id"]]["status"], "canceled")
            self.assertEqual(saved["scheduled_triggers"][task_schedule["schedule_id"]]["status"], "pending")

    def test_stop_reports_daemon_schedule_save_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_instance(instance_root, browser_port=None)

            with mock.patch.object(
                manager.daemon_state,
                "cancel_pending_schedules_by_source_owner",
                side_effect=OSError("state save failed"),
            ):
                result = manager.stop(instance_root=instance_root, actor_id="act-dev-browser")

            self.assertFalse(result.get("ok"), msg=result)
            self.assertEqual(result["error"]["code"], "E_BROWSER_RUNTIME_MANAGER")
            self.assertIn("state save failed", result["error"]["message"])
            self.assertIs(result["state_changed"], False)

    def test_release_cleans_owned_profile_listener_when_pid_marker_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            instance_json = self._write_instance(instance_root, browser_port=port)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            chrome_proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=instance_root / "browser" / "profile",
                log_file=instance_root / "browser" / "chrome.log",
            )
            (instance_root / "browser" / "chrome.pid").unlink(missing_ok=True)

            result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="test_cleanup")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("handled"), True)
            self.assertEqual(result.get("ownership"), "owned")
            self.assertTrue(wait_until(lambda: not pid_alive(chrome_proc.pid)), "release must stop profile-owned Chrome without a pid marker")
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertIsNone(instance_payload["browser_port"])

    def test_cli_release_cleans_owned_profile_listener_when_pid_marker_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            self._write_instance(instance_root, browser_port=port)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            chrome_proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=instance_root / "browser" / "profile",
                log_file=instance_root / "browser" / "chrome.log",
            )
            (instance_root / "browser" / "chrome.pid").unlink(missing_ok=True)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = manager.main(
                    [
                        "release",
                        "--instance-root",
                        str(instance_root),
                        "--actor-id",
                        "act-dev-browser",
                        "--reason",
                        "test_cleanup",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload.get("ok"), msg=payload)
            self.assertEqual(payload.get("handled"), True)
            self.assertEqual(payload.get("ownership"), "owned")
            self.assertTrue(wait_until(lambda: not pid_alive(chrome_proc.pid)), "CLI release must stop profile-owned Chrome without a pid marker")

    def test_release_cleans_owned_profile_listener_when_browser_port_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            instance_json = self._write_instance(instance_root, browser_port=None)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            chrome_proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=instance_root / "browser" / "profile",
                log_file=instance_root / "browser" / "chrome.log",
            )

            result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="orphan_repair")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("handled"), True)
            self.assertEqual(result.get("ownership"), "orphaned_owned")
            self.assertTrue(wait_until(lambda: not pid_alive(chrome_proc.pid)), "release must stop profile-owned Chrome even when browser_port is missing")
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertIsNone(instance_payload["browser_port"])

    def test_profile_owned_processes_matches_canonical_user_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            real_root = temp_root_path / "real-root"
            alias_root = temp_root_path / "alias-root"
            real_profile = real_root / "instances" / "act-dev-browser" / "browser" / "profile"
            real_profile.mkdir(parents=True, exist_ok=True)
            os.symlink(real_root, alias_root)
            alias_profile = alias_root / "instances" / "act-dev-browser" / "browser" / "profile"
            canonical_profile = alias_profile.resolve(strict=False)
            self.assertNotEqual(str(alias_profile), str(canonical_profile))
            process = manager.ProcessInfo(
                pid=424242,
                pgid=424242,
                command_line=f"Google Chrome --user-data-dir={canonical_profile} --remote-debugging-port=9222",
            )

            with (
                mock.patch.object(manager, "_all_processes", return_value=[process]),
                mock.patch.object(manager, "_pid_alive", return_value=True),
            ):
                owned = manager._profile_owned_processes(alias_profile)

            self.assertEqual([row.pid for row in owned], [process.pid])

    def test_release_failure_preserves_state_until_process_gone(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            instance_json = self._write_instance(instance_root, browser_port=port)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            chrome_proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=instance_root / "browser" / "profile",
                log_file=instance_root / "browser" / "chrome.log",
            )
            browser_dir = instance_root / "browser"
            runtime_browser_dir = instance_root / "runtime" / "browser"
            browser_dir.mkdir(parents=True, exist_ok=True)
            runtime_browser_dir.mkdir(parents=True, exist_ok=True)
            pid_file = browser_dir / "chrome.pid"
            page_idle_file = runtime_browser_dir / "page_idle.json"
            pid_file.write_text(f"{chrome_proc.pid}\n", encoding="utf-8")
            page_idle_file.write_text('{"pages": {}}\n', encoding="utf-8")
            state = self._daemon_state(instance_root)
            browser_schedule = state.create_schedule(
                delay_seconds=600,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-1"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:00Z",
            )

            with (
                mock.patch.object(manager, "_terminate_pid", lambda _pid: None),
                mock.patch.object(manager, "_terminate_pgid", lambda _pgid: False),
            ):
                result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="test_cleanup")

            self.assertFalse(result.get("ok"), msg=result)
            self.assertTrue(pid_alive(chrome_proc.pid), "test setup must leave Chrome alive when termination fails")
            self.assertTrue(pid_file.exists(), "failed release must preserve pid marker for diagnosis")
            self.assertTrue(page_idle_file.exists(), "failed release must preserve page idle state for diagnosis")
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertEqual(instance_payload["browser_port"], port)
            saved = self._saved_daemon_state(instance_root)
            self.assertEqual(saved["scheduled_triggers"][browser_schedule["schedule_id"]]["status"], "pending")

    def test_status_reports_orphaned_owned_browser_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            self._write_instance(instance_root, browser_port=None)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=instance_root / "browser" / "profile",
                log_file=instance_root / "browser" / "chrome.log",
            )

            result = manager.status(instance_root=instance_root, actor_id="act-dev-browser")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertFalse(result.get("ready"), msg=result)
            self.assertEqual(result.get("browser_port"), None)
            self.assertEqual(result.get("ownership"), "orphaned_owned")

    def test_release_clears_foreign_endpoint_without_killing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            instance_json = self._write_instance(instance_root, browser_port=port)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            foreign_proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=temp_root_path / "foreign-profile",
                log_file=temp_root_path / "foreign.log",
            )

            result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="page_idle_empty")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("handled"), True)
            self.assertIn(result.get("ownership"), {"foreign", "unknown"})
            self.assertTrue(pid_alive(foreign_proc.pid), "foreign endpoint process must not be killed")
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertIsNone(instance_payload["browser_port"])


if __name__ == "__main__":
    unittest.main()
