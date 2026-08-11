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
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.support.paths import REPO_ROOT
from tests.support.cli import pid_alive, wait_until
from tests.support.fake_cdp import FakeCdpServer, write_fake_chrome
from tests.support.processes import ResourceLedger

ROOT = REPO_ROOT

from buddyswitch.foundation.browser_runtime import runtime as manager  # noqa: E402
from buddyswitch.foundation.daemon import state as daemon_state  # noqa: E402


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
    def setUp(self) -> None:
        super().setUp()
        self._ledger = ResourceLedger.from_environment()

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
        write_fake_chrome(path, argv_path)

    def _start_parent_cdp(self, activation_path: Path | None = None) -> FakeCdpServer:
        server = FakeCdpServer(activation_path=activation_path).start()
        self.addCleanup(server.close)
        return server

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
        proc = self._ledger.start_process(
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
        )
        self.addCleanup(self._cleanup_process, proc, log_handle)
        self.assertTrue(wait_until(lambda: port_accepts(port), timeout=3.0), "fake Chrome endpoint did not become ready")
        return proc

    def test_acquire_starts_chrome_records_port_and_pid_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            instance_json = self._write_instance(instance_root)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            port = self._start_parent_cdp(activation_path=chrome_argv).port

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
            self.assertTrue(manager.process_identity.identity_file(pid_file).exists())
            self.assertTrue(pid_alive(browser_pid))
            argv = [json.loads(line) for line in chrome_argv.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(argv), 1)
            self.assertIn(f"--remote-debugging-port={port}", argv[0])
            self.assertIn(f"--user-data-dir={instance_root / 'browser' / 'profile'}", argv[0])
            browser_proc = next(proc for proc in manager._DETACHED_BROWSER_PROCESSES if proc.pid == browser_pid)

            release = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="test_cleanup")
            self.assertTrue(release.get("ok"), msg=release)
            self.assertIsNotNone(browser_proc.poll(), "release must reap the fake Chrome child")
            self.assertEqual(manager._DETACHED_BROWSER_PROCESSES, [])

    def test_terminate_owned_record_reaps_child_when_group_disappears_during_wait(self) -> None:
        proc = mock.Mock()
        proc.pid = 4242
        proc.poll.return_value = 0
        manager._DETACHED_BROWSER_PROCESSES[:] = [proc]
        self.addCleanup(manager._DETACHED_BROWSER_PROCESSES.clear)
        record = manager.process_identity.RecordedProcess(pid=proc.pid, start_identity="test")

        with (
            mock.patch.object(manager.process_identity, "is_running", side_effect=[True, True, False]),
            mock.patch.object(manager.os, "getpgid", side_effect=[5252, 6262]),
            mock.patch.object(manager.os, "killpg"),
            mock.patch.object(manager, "_wait_pgid_gone", return_value=False),
            mock.patch.object(manager, "_pgid_alive", return_value=False),
        ):
            self.assertTrue(manager._terminate_owned_record(record))

        self.assertEqual(manager._DETACHED_BROWSER_PROCESSES, [])

    def test_terminate_owned_record_reconciles_tracked_child_on_all_terminal_exits(self) -> None:
        self.addCleanup(manager._DETACHED_BROWSER_PROCESSES.clear)
        record = manager.process_identity.RecordedProcess(
            pid=4242,
            start_identity="test",
        )
        terminal_cases = (
            {
                "name": "identity disappears before signal",
                "is_running": [True, False],
                "killpg": [],
                "expected": False,
            },
            {
                "name": "process group disappears before SIGTERM",
                "is_running": [True, True],
                "killpg": [ProcessLookupError()],
                "expected": False,
            },
            {
                "name": "process group disappears before SIGKILL",
                "is_running": [True, True, True],
                "killpg": [None, ProcessLookupError()],
                "expected": True,
            },
        )

        for case in terminal_cases:
            with self.subTest(case["name"]):
                proc = mock.Mock()
                proc.pid = record.pid
                proc.poll.return_value = 0
                manager._DETACHED_BROWSER_PROCESSES[:] = [proc]

                with (
                    mock.patch.object(
                        manager.process_identity,
                        "is_running",
                        side_effect=case["is_running"],
                    ),
                    mock.patch.object(
                        manager.os,
                        "getpgid",
                        side_effect=[5252, 6262],
                    ),
                    mock.patch.object(
                        manager.os,
                        "killpg",
                        side_effect=case["killpg"],
                    ),
                    mock.patch.object(
                        manager,
                        "_wait_pgid_gone",
                        return_value=False,
                    ),
                    mock.patch.object(manager, "_pgid_alive", return_value=False),
                ):
                    self.assertEqual(
                        manager._terminate_owned_record(record),
                        case["expected"],
                    )

                self.assertEqual(manager._DETACHED_BROWSER_PROCESSES, [])

        with self.subTest("same process group retains a live tracked child"):
            proc = mock.Mock()
            proc.pid = record.pid
            proc.poll.return_value = None
            manager._DETACHED_BROWSER_PROCESSES[:] = [proc]

            with (
                mock.patch.object(
                    manager.process_identity,
                    "is_running",
                    return_value=True,
                ),
                mock.patch.object(manager.os, "getpgid", return_value=5252),
                mock.patch.object(manager.os, "killpg") as killpg,
            ):
                self.assertFalse(manager._terminate_owned_record(record))

            killpg.assert_not_called()
            self.assertEqual(manager._DETACHED_BROWSER_PROCESSES, [proc])

    def test_acquire_reuses_owned_recorded_ready_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = self._start_parent_cdp().port
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
            manager.process_identity.write_record(
                instance_root / "browser" / "chrome.pid",
                proc.pid,
            )

            result = manager.acquire(instance_root=instance_root, actor_id="act-dev-browser")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("browser_port"), port)
            self.assertEqual(result.get("state_changed"), False)
            self.assertTrue(
                wait_until(
                    lambda: chrome_argv.exists() and chrome_argv.stat().st_size > 0,
                    timeout=5.0,
                )
            )
            argv = [json.loads(line) for line in chrome_argv.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(argv), 1, "acquire should not start another Chrome when owned endpoint is ready")

    def test_release_cleans_owned_runtime_state(self) -> None:
        upstream_proc = self._ledger.start_process(["sleep", "60"])
        upstream_pgid = os.getpgid(upstream_proc.pid)
        self.addCleanup(self._cleanup_process, upstream_proc)

        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = self._start_parent_cdp().port
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
            manager.process_identity.write_record(browser_dir / "chrome.pid", chrome_proc.pid)
            manager.process_identity.write_record(
                runtime_browser_dir / "cockpit-upstream.pid",
                upstream_proc.pid,
            )
            (runtime_browser_dir / "cockpit-upstream.pgid").write_text(f"{upstream_pgid}\n", encoding="utf-8")
            (runtime_browser_dir / "page_idle.json").write_text("{}", encoding="utf-8")
            (runtime_browser_dir / "page_idle.lock").write_text("", encoding="utf-8")

            result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="page_idle_empty")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("handled"), True)
            self.assertEqual(result.get("state_changed"), True)
            self.assertTrue(wait_until(lambda: not pid_alive(chrome_proc.pid), timeout=3.0), "release must stop Chrome pid")
            self.assertTrue(wait_until(lambda: not pid_alive(upstream_proc.pid), timeout=3.0), "release must stop upstream pid")
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
            port = self._start_parent_cdp().port
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

    def test_release_does_not_signal_profile_listener_without_identity_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = self._start_parent_cdp().port
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
            self.assertEqual(result.get("ownership"), "unknown")
            self.assertTrue(pid_alive(chrome_proc.pid))
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertIsNone(instance_payload["browser_port"])

    def test_cli_release_does_not_signal_profile_listener_without_identity_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = self._start_parent_cdp().port
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
            self.assertEqual(payload.get("ownership"), "unknown")
            self.assertTrue(pid_alive(chrome_proc.pid))

    def test_release_does_not_claim_profile_listener_when_browser_port_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = self._start_parent_cdp().port
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
            self.assertEqual(result.get("handled"), False)
            self.assertEqual(result.get("ownership"), "inactive")
            self.assertTrue(pid_alive(chrome_proc.pid))
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertIsNone(instance_payload["browser_port"])

    def test_release_failure_preserves_state_until_process_gone(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = self._start_parent_cdp().port
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
            manager.process_identity.write_record(pid_file, chrome_proc.pid)
            page_idle_file.write_text('{"targets": {}}\n', encoding="utf-8")
            state = self._daemon_state(instance_root)
            browser_schedule = state.create_schedule(
                delay_seconds=600,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-1"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:00Z",
            )

            with mock.patch.object(manager, "_terminate_owned_record", return_value=False):
                result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="test_cleanup")

            self.assertFalse(result.get("ok"), msg=result)
            self.assertTrue(pid_alive(chrome_proc.pid), "test setup must leave Chrome alive when termination fails")
            self.assertTrue(pid_file.exists(), "failed release must preserve pid marker for diagnosis")
            self.assertTrue(page_idle_file.exists(), "failed release must preserve page idle state for diagnosis")
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertEqual(instance_payload["browser_port"], port)
            saved = self._saved_daemon_state(instance_root)
            self.assertEqual(saved["scheduled_triggers"][browser_schedule["schedule_id"]]["status"], "pending")

    def test_status_does_not_claim_unrecorded_browser_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = self._start_parent_cdp().port
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
            self.assertEqual(result.get("ownership"), "inactive")

    def test_release_clears_foreign_endpoint_without_killing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = self._start_parent_cdp().port
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
