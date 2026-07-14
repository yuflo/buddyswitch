"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

from contextlib import ExitStack
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT
LAUNCHER = ROOT / "buddyswitch-codex"
from tests.system.support.launcher import SystemLauncherHarness


class TestInstanceInteraction(SystemLauncherHarness, unittest.TestCase):
    def test_input_reports_non_steerable_active_turn_without_task_sys_fallback(
        self,
    ) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                cleanup_stack=cleanup,
                state_payload={
                    "thread_status": {"type": "active", "activeFlags": []},
                    "turns": [
                        {
                            "id": "turn-123",
                            "items": [],
                            "itemsView": "summary",
                            "status": "inProgress",
                            "error": None,
                            "startedAt": 0,
                            "completedAt": None,
                            "durationMs": None,
                        }
                    ],
                    "errors": {
                        "turn/steer": {
                            "code": -32005,
                            "message": "turn not steerable",
                        }
                    },
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(
                completed.returncode,
                0,
                msg=self._output_error_text(completed),
            )

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            input_result = run_process(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    str(ctx["actor_id"]),
                    "--text",
                    "Steer current turn",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(input_result.returncode, 0)
            self.assertIn("turn not steerable", self._output_error_text(input_result))
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            methods = [
                row["rpc_method"]
                for row in rpc_rows
                if row["rpc_method"] not in {"initialize", "initialized"}
            ]
            self.assertIn("thread/settings/update", methods)
            self.assertIn("thread/read", methods)
            self.assertIn("thread/turns/list", methods)
            self.assertIn("turn/steer", methods)
            self.assertNotIn("thread/fork", methods)
            self.assertNotIn("thread/inject_items", methods)
            self.assertNotIn("turn/start", methods)

    def test_attach_blocks_when_thread_resume_preflight_fails(self) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                cleanup_stack=cleanup,
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(
                completed.returncode,
                0,
                msg=self._output_error_text(completed),
            )

            state_path = Path(str(ctx["state_file"]))
            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            state_payload["errors"] = {
                "thread/resume": {
                    "code": -32004,
                    "message": "thread not loaded: thread-test",
                }
            }
            state_path.write_text(
                json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )
            capture_path = Path(str(ctx["capture_path"]))
            capture_path.unlink(missing_ok=True)
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            attach_result = run_process(
                [str(LAUNCHER), "instance", "attach", str(ctx["actor_id"])],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(attach_result.returncode, 0)
            self.assertIn("thread/resume failed", self._output_error_text(attach_result))
            self.assertFalse(
                capture_path.exists(),
                "TUI must not launch after failed preflight",
            )

    def test_resume_after_clear_daemon_failure_uses_new_thread(self) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                cleanup_stack=cleanup,
                state_payload={
                    "clear_thread_id": "thread-cleared",
                    "thread_resume_error_on_count": 2,
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))

            clear_result = run_process(
                [str(LAUNCHER), "instance", "clear", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(clear_result.returncode, 0)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            state_payload.pop("thread_resume_error_on_count", None)
            Path(str(ctx["state_file"])).write_text(json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            resume_result = run_process(
                [str(LAUNCHER), "instance", "resume", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resume_result.returncode, 0, msg=self._output_error_text(resume_result))
            payload = self._cli_success_data(resume_result)
            self.assertEqual(payload["thread_id"], "thread-cleared")
            calls = self._read_json_lines(Path(str(ctx["calls_path"])))
            resume_calls = [row for row in calls if row.get("rpc_method") == "thread/resume"]
            self.assertTrue(resume_calls)
            self.assertEqual(resume_calls[-1]["params"]["threadId"], "thread-cleared")
            self._stop_service_instance(ctx)
            self._reset_service_environment(ctx)
    def test_attach_after_clear_uses_new_thread_id(self) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                cleanup_stack=cleanup,
                state_payload={"clear_thread_id": "thread-cleared"},
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))

            clear_result = run_process(
                [str(LAUNCHER), "instance", "clear", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(clear_result.returncode, 0, msg=self._output_error_text(clear_result))
            self.assertEqual(self._cli_success_data(clear_result)["thread_id"], "thread-cleared")

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            attach_result = run_process(
                [str(LAUNCHER), "instance", "attach", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(attach_result.returncode, 0, msg=self._output_error_text(attach_result))

            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            resume_rpc = next(row for row in calls if row.get("rpc_method") == "thread/resume")
            self.assertEqual(resume_rpc["params"]["threadId"], "thread-cleared")
            self._stop_service_instance(ctx)
            self._reset_service_environment(ctx)
