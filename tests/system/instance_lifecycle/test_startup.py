"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

from contextlib import ExitStack
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.system.support.launcher import SystemLauncherHarness


class TestInstanceStartup(SystemLauncherHarness, unittest.TestCase):
    def test_start_bootstrap_timeout_retries_once_and_succeeds(self) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                cleanup_stack=cleanup,
                role="pm",
                state_payload={
                    "error_on_attempts": {
                        "thread/inject_items": {
                            "1": {
                                "code": -32000,
                                "message": "timed out waiting for thread/inject_items",
                            }
                        }
                    }
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(
                completed.returncode,
                0,
                msg=self._output_error_text(completed),
            )

            instance_payload = json.loads(
                (Path(str(ctx["instance_root"])) / "instance.json").read_text(
                    encoding="utf-8"
                )
            )
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            thread_start_calls = [
                row for row in rpc_rows if row.get("rpc_method") == "thread/start"
            ]
            bootstrap_calls = [
                row
                for row in rpc_rows
                if row.get("rpc_method") == "thread/inject_items"
            ]
            daemon_resume = next(
                row
                for row in rpc_rows
                if row.get("rpc_method") == "thread/resume"
                and row.get("client_name") == "buddyswitch_daemon"
            )

            self.assertEqual(len(thread_start_calls), 1)
            self.assertEqual(len(bootstrap_calls), 2)
            self.assertEqual(
                bootstrap_calls[0]["params"]["threadId"],
                bootstrap_calls[1]["params"]["threadId"],
            )
            self.assertEqual(
                bootstrap_calls[0]["params"]["threadId"],
                instance_payload["thread_id"],
            )
            self.assertEqual(
                daemon_resume["params"]["threadId"],
                instance_payload["thread_id"],
            )
            self.assertEqual(instance_payload["status"], "active")
            self.assertNotIn("last_failure", instance_payload)

    def test_start_bootstrap_retry_failure_cleans_state_and_records_failure(self) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                cleanup_stack=cleanup,
                role="pm",
                state_payload={
                    "error_on_attempts": {
                        "thread/inject_items": {
                            "1": {
                                "code": -32000,
                                "message": "timed out waiting for thread/inject_items",
                            },
                            "2": {
                                "code": -32000,
                                "message": "timed out waiting for thread/inject_items again",
                            },
                        }
                    }
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("timed out waiting for thread/inject_items", self._output_error_text(completed))

            instance_root = Path(str(ctx["instance_root"]))
            instance_payload = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            bootstrap_calls = [row for row in rpc_rows if row.get("rpc_method") == "thread/inject_items"]

            self.assertEqual(len(bootstrap_calls), 2)
            self.assertEqual(instance_payload["status"], "inactive")
            self.assertIsNone(instance_payload["app_server_pid"])
            self.assertIsNone(instance_payload["app_server_socket"])
            self.assertIsNone(instance_payload["app_server_log"])
            self.assertIsNone(instance_payload["browser_port"])
            self.assertIsNone(instance_payload.get("thread_id"))
            self.assertEqual(instance_payload["last_failure"]["phase"], "thread_bootstrap")
            self.assertEqual(instance_payload["last_failure"]["thread_id"], bootstrap_calls[0]["params"]["threadId"])
            self.assertIn("timed out waiting for thread/inject_items", instance_payload["last_failure"]["message"])
            self.assertNotIn("browser_port", instance_payload["last_failure"])
            self.assertTrue(instance_payload["last_failure"].get("failed_at"))
            self.assertFalse((instance_root / "runtime" / "app-server.pid").exists())
            self.assertFalse((instance_root / "runtime" / "app-server.sock").exists())
            self.assertFalse((instance_root / "runtime" / "app-server.socket").exists())
            self.assertFalse((instance_root / "runtime" / "runtime-broker.pid").exists())
            self.assertFalse((instance_root / "runtime" / "daemon" / "daemon.pid").exists())
            self.assertFalse((instance_root / "browser" / "chrome.pid").exists())
