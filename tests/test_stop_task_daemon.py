#!/usr/bin/env python3
"""Tests for the STOP Task TUI daemon."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from typing import Any
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAEMON_PATH = ROOT / "tools" / "launcher" / "instance_daemon.py"
SPEC = importlib.util.spec_from_file_location("buddyswitch_instance_daemon", DAEMON_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load spec for {DAEMON_PATH}")
INSTANCE_DAEMON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTANCE_DAEMON)


class StopTaskDaemonStateTests(unittest.TestCase):
    def _instance_root(self, temp_root: str) -> Path:
        root = Path(temp_root) / "instances" / "inst-dev-daemon"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_missing_state_initializes_empty_valid_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)

            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )

            self.assertEqual(state.payload["instance_id"], "inst-dev-daemon")
            self.assertEqual(state.payload["main_thread_id"], "thr-main")
            self.assertEqual(state.payload["daemon_origin_turn_ids"], [])
            self.assertIsNone(state.payload["last_error"])

    def test_recording_daemon_origin_turn_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )

            state.record_stop_tui_turn(origin_turn_id="turn-user-1", stop_tui_turn_id="turn-daemon-1")

            saved = json.loads(INSTANCE_DAEMON.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["last_origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["last_stop_tui_turn_id"], "turn-daemon-1")
            self.assertEqual(saved["daemon_origin_turn_ids"], ["turn-daemon-1"])
            self.assertTrue(state.is_daemon_origin_turn("turn-daemon-1"))
            self.assertFalse(state.is_daemon_origin_turn("turn-user-1"))

    def test_daemon_origin_turn_ids_keep_latest_50(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )

            for index in range(55):
                state.record_stop_tui_turn(origin_turn_id=f"turn-user-{index}", stop_tui_turn_id=f"turn-daemon-{index}")

            saved = json.loads(INSTANCE_DAEMON.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(len(saved["daemon_origin_turn_ids"]), 50)
            self.assertEqual(saved["daemon_origin_turn_ids"][0], "turn-daemon-5")
            self.assertEqual(saved["daemon_origin_turn_ids"][-1], "turn-daemon-54")

    def test_recording_error_persists_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )

            state.record_error(origin_turn_id="turn-user-1", message="turn/start failed")

            saved = json.loads(INSTANCE_DAEMON.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["last_error"]["message"], "turn/start failed")
            self.assertRegex(saved["last_error"]["at"], r"^\d{4}-\d{2}-\d{2}T")


class StopTaskDaemonFilterTests(unittest.TestCase):
    def _state(self, temp_root: str) -> object:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        instance_root.mkdir(parents=True, exist_ok=True)
        return INSTANCE_DAEMON.DaemonState.load(
            instance_root=instance_root,
            instance_id="inst-dev-daemon",
            main_thread_id="thr-main",
        )

    def _completed(self, *, thread_id: str = "thr-main", turn_id: str = "turn-user-1", status: str = "completed") -> dict[str, object]:
        return {
            "method": "turn/completed",
            "params": {
                "thread_id": thread_id,
                "turn_id": turn_id,
                "status": status,
            },
        }

    def test_other_thread_completed_notification_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state = self._state(temp_root)

            previous_turn = INSTANCE_DAEMON.completed_turn_for_stop_tui(
                self._completed(thread_id="thr-side"),
                state,
            )

            self.assertIsNone(previous_turn)

    def test_non_completed_main_thread_notifications_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state = self._state(temp_root)

            self.assertIsNone(INSTANCE_DAEMON.completed_turn_for_stop_tui(self._completed(status="failed"), state))
            self.assertIsNone(INSTANCE_DAEMON.completed_turn_for_stop_tui(self._completed(status="interrupted"), state))

    def test_completed_daemon_origin_turn_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state = self._state(temp_root)
            state.record_stop_tui_turn(origin_turn_id="turn-user-1", stop_tui_turn_id="turn-daemon-1")

            previous_turn = INSTANCE_DAEMON.completed_turn_for_stop_tui(
                self._completed(turn_id="turn-daemon-1"),
                state,
            )

            self.assertIsNone(previous_turn)

    def test_completed_main_thread_user_turn_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state = self._state(temp_root)

            previous_turn = INSTANCE_DAEMON.completed_turn_for_stop_tui(self._completed(), state)

            self.assertEqual(
                previous_turn,
                {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
            )


class FakeDaemonClient:
    def __init__(self, *, result: dict[str, object] | None = None, error: BaseException | None = None) -> None:
        self.result = result or {"turn": {"id": "turn-daemon-1"}}
        self.error = error
        self.requests: list[dict[str, object]] = []

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if self.error is not None:
            raise self.error
        return self.result


class StopTaskDaemonSendTests(unittest.TestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "instance_id": "inst-dev-daemon",
            "buddy": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(instance_root / "workspace"),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {
            "instance_root": instance_root,
            "instance_json": instance_json,
            "payload": payload,
        }

    def _patch_snapshot_render(self) -> list[tuple[str, object]]:
        calls: list[tuple[str, object]] = []

        def fake_current_snapshot(**kwargs: object) -> dict[str, object]:
            calls.append(("snapshot", kwargs))
            return {
                "current_task": {"id": "task-1", "status": "active", "summary": "summary"},
                "last_event": None,
                "progress_summary": "summary",
            }

        def fake_render_stop_task_tui(snapshot: object, previous_turn: object) -> str:
            calls.append(("render", {"snapshot": snapshot, "previous_turn": previous_turn}))
            return "[TASK CHECKOUT]\nContinue -> no task update"

        self.addCleanup(setattr, INSTANCE_DAEMON.task_management, "current_snapshot", INSTANCE_DAEMON.task_management.current_snapshot)
        self.addCleanup(setattr, INSTANCE_DAEMON.task_tui, "render_stop_task_tui", INSTANCE_DAEMON.task_tui.render_stop_task_tui)
        INSTANCE_DAEMON.task_management.current_snapshot = fake_current_snapshot
        INSTANCE_DAEMON.task_tui.render_stop_task_tui = fake_render_stop_task_tui
        return calls

    def test_accepted_completed_turn_sends_one_stop_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = INSTANCE_DAEMON.load_daemon_context(instance["instance_json"])
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance["instance_root"],
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )
            calls = self._patch_snapshot_render()
            client = FakeDaemonClient(result={"turn": {"id": "turn-daemon-1"}})

            sent = INSTANCE_DAEMON.handle_notification(
                context,
                state,
                client,
                {
                    "method": "turn/completed",
                    "params": {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
                },
            )

            self.assertTrue(sent)
            self.assertEqual([request["method"] for request in client.requests], ["turn/start"])
            params = client.requests[0]["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thr-main")
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            input_payload = params["input"]
            assert isinstance(input_payload, list)
            prompt = input_payload[0]["text"]
            self.assertTrue(prompt.startswith("[TASK CHECKOUT]"))
            self.assertNotIn("[TASK CONTEXT]", prompt)
            self.assertNotIn("[USER INPUT]", prompt)
            self.assertEqual([name for name, _payload in calls], ["snapshot", "render"])
            self.assertTrue(state.is_daemon_origin_turn("turn-daemon-1"))

    def test_turn_start_failure_records_error_without_retry_or_steer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = INSTANCE_DAEMON.load_daemon_context(instance["instance_json"])
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance["instance_root"],
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )
            self._patch_snapshot_render()
            client = FakeDaemonClient(
                error=INSTANCE_DAEMON.app_server.AppServerRequestError("turn/start", -32000, "active thread"),
            )

            sent = INSTANCE_DAEMON.handle_notification(
                context,
                state,
                client,
                {
                    "method": "turn/completed",
                    "params": {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
                },
            )

            self.assertFalse(sent)
            self.assertEqual([request["method"] for request in client.requests], ["turn/start"])
            saved = json.loads(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertIn("turn/start failed", saved["last_error"]["message"])
            self.assertFalse(state.is_daemon_origin_turn("turn-user-1"))

            client.error = None
            client.result = {"turn": {"id": "turn-daemon-2"}}
            sent_later = INSTANCE_DAEMON.handle_notification(
                context,
                state,
                client,
                {
                    "method": "turn/completed",
                    "params": {"thread_id": "thr-main", "turn_id": "turn-user-2", "status": "completed"},
                },
            )
            self.assertTrue(sent_later)
            self.assertEqual([request["method"] for request in client.requests], ["turn/start", "turn/start"])
            self.assertNotIn("turn/steer", [request["method"] for request in client.requests])


class StopTaskDaemonLifecycleTests(unittest.TestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload = {
            "instance_id": "inst-dev-daemon",
            "buddy": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(instance_root / "workspace"),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {"instance_root": instance_root, "instance_json": instance_json}

    def _patch_process_start(self, pids: list[int]) -> list[list[str]]:
        commands: list[list[str]] = []
        original_popen = INSTANCE_DAEMON.subprocess.Popen

        class FakeProcess:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def poll(self) -> None:
                return None

        def fake_popen(command: list[str], **_kwargs: object) -> FakeProcess:
            commands.append(command)
            return FakeProcess(pids.pop(0))

        self.addCleanup(setattr, INSTANCE_DAEMON.subprocess, "Popen", original_popen)
        INSTANCE_DAEMON.subprocess.Popen = fake_popen
        return commands

    def _patch_exited_process_start(self, pid: int) -> None:
        original_popen = INSTANCE_DAEMON.subprocess.Popen

        class FakeExitedProcess:
            def __init__(self) -> None:
                self.pid = pid

            def poll(self) -> int:
                return 1

        def fake_popen(command: list[str], **_kwargs: object) -> FakeExitedProcess:
            return FakeExitedProcess()

        self.addCleanup(setattr, INSTANCE_DAEMON.subprocess, "Popen", original_popen)
        INSTANCE_DAEMON.subprocess.Popen = fake_popen

    def _patch_pid_live(self, live_pids: set[int]) -> None:
        original_pid_is_live = INSTANCE_DAEMON._pid_is_live
        self.addCleanup(setattr, INSTANCE_DAEMON, "_pid_is_live", original_pid_is_live)
        INSTANCE_DAEMON._pid_is_live = lambda pid: pid in live_pids

    def test_start_creates_runtime_files_and_is_idempotent_when_pid_is_live(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            commands = self._patch_process_start([4321])
            self._patch_pid_live({4321})

            first = INSTANCE_DAEMON.start_daemon(instance["instance_json"])
            second = INSTANCE_DAEMON.start_daemon(instance["instance_json"])

            self.assertTrue(first["started"])
            self.assertFalse(second["started"])
            self.assertEqual(first["pid"], 4321)
            self.assertEqual(second["pid"], 4321)
            self.assertEqual(len(commands), 1)
            self.assertTrue(INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).exists())
            self.assertTrue(INSTANCE_DAEMON.daemon_log_file(instance["instance_root"]).exists())
            self.assertTrue(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"]).exists())

    def test_start_cleans_stale_pid_before_starting_new_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).write_text("9999\n", encoding="utf-8")
            commands = self._patch_process_start([4322])
            self._patch_pid_live({4322})

            payload = INSTANCE_DAEMON.start_daemon(instance["instance_json"])

            self.assertTrue(payload["started"])
            self.assertEqual(payload["pid"], 4322)
            self.assertEqual(len(commands), 1)
            self.assertEqual(INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).read_text(encoding="utf-8").strip(), "4322")

    def test_start_removes_pid_and_fails_when_daemon_exits_early(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self._patch_exited_process_start(4323)
            self._patch_pid_live(set())

            with self.assertRaises(RuntimeError):
                INSTANCE_DAEMON.start_daemon(instance["instance_json"])

            self.assertFalse(INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).exists())

    def test_stop_terminates_live_daemon_and_removes_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).write_text("4321\n", encoding="utf-8")
            terminated: list[int] = []
            self._patch_pid_live({4321})
            original_terminate = INSTANCE_DAEMON._terminate_pid
            self.addCleanup(setattr, INSTANCE_DAEMON, "_terminate_pid", original_terminate)
            INSTANCE_DAEMON._terminate_pid = lambda pid: terminated.append(pid) or True

            payload = INSTANCE_DAEMON.stop_daemon(instance["instance_json"])

            self.assertTrue(payload["terminated"])
            self.assertEqual(terminated, [4321])
            self.assertFalse(INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).exists())

    def test_status_reports_paths_live_state_and_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance["instance_root"],
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )
            state.record_error(origin_turn_id="turn-user-1", message="turn/start failed")
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).write_text("4321\n", encoding="utf-8")
            self._patch_pid_live({4321})

            payload = INSTANCE_DAEMON.daemon_status(instance["instance_json"])

            self.assertEqual(payload["pid"], 4321)
            self.assertTrue(payload["pid_live"])
            self.assertTrue(payload["live"])
            self.assertEqual(payload["log_path"], str(INSTANCE_DAEMON.daemon_log_file(instance["instance_root"])))
            self.assertEqual(payload["state_path"], str(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"])))
            self.assertEqual(payload["last_error"]["origin_turn_id"], "turn-user-1")


if __name__ == "__main__":
    unittest.main()
