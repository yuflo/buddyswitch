"""Single public multi-service instance lifecycle proof."""

from __future__ import annotations

from contextlib import ExitStack
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.system.support.launcher import SystemLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process


LAUNCHER = REPO_ROOT / "buddyswitch-codex"


class TestInstanceMainFlow(SystemLauncherHarness, unittest.TestCase):
    def test_start_input_status_stop_delete(self) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                cleanup_stack=cleanup,
                role="pm",
            )
            started = ctx["completed"]
            assert isinstance(started, subprocess.CompletedProcess)
            self.assertEqual(started.returncode, 0, msg=self._output_error_text(started))

            actor_id = str(ctx["actor_id"])
            command_env = ctx["env"]
            shared_root = Path(str(ctx["shared_root"]))
            instance_root = Path(str(ctx["instance_root"]))
            workspace_dir = instance_root / "workspace"
            capture = ctx["payload"]
            assert isinstance(capture, dict)
            instance_payload = json.loads(
                (instance_root / "instance.json").read_text(encoding="utf-8")
            )

            self.assertEqual(capture["active_role"], "pm")
            self.assertEqual(capture["actor_id"], actor_id)
            self.assertEqual(capture["cwd"], str(workspace_dir.resolve()))
            self.assertEqual(capture["actor_private_dir"], str(workspace_dir / "private"))
            self.assertTrue(capture["runtime_broker_socket"])
            self.assertEqual(capture["argv"][:2], ["app-server", "--listen"])
            self.assertEqual(instance_payload["status"], "active")
            self.assertEqual(instance_payload["actor_id"], actor_id)
            self.assertEqual(instance_payload["role"], "pm")
            self.assertEqual(instance_payload["instance_root"], str(instance_root))
            self.assertEqual(instance_payload["workspace_dir"], str(workspace_dir))
            self.assertIsNone(instance_payload["browser_port"])
            self.assertTrue(instance_payload["thread_id"])
            self.assertTrue(instance_payload["app_server_pid"])
            self.assertTrue(instance_payload["app_server_socket"])
            self.assertTrue(instance_payload["app_server_log"])
            self.assertFalse((shared_root / "workspace").exists())
            self._assert_pm_runtime_shape(workspace_dir, shared_root)
            self._assert_runtime_workspace_excludes_source_surfaces(workspace_dir)
            project_workspace = shared_root / "project" / "workspace"
            self.assertEqual(list(instance_root.rglob(".git")), [])
            self.assertEqual(list(project_workspace.rglob(".git")), [])
            self.assertTrue((workspace_dir / "projects" / "app").is_symlink())
            self.assertEqual(
                (workspace_dir / "projects" / "app").resolve(),
                (project_workspace / "projects" / "app").resolve(),
            )

            capability_config = json.loads(
                (instance_root / "capability-config.json").read_text(encoding="utf-8")
            )
            self.assertEqual(capability_config["parent"]["level"], "balanced")
            self.assertEqual(capability_config["side"]["level"], "fast")
            bootstrap_methods = [
                row["rpc_method"]
                for row in self._read_rpc_rows(Path(str(ctx["calls_path"])))
            ]
            self.assertIn("thread/start", bootstrap_methods)
            self.assertIn("thread/inject_items", bootstrap_methods)
            self.assertIn("thread/resume", bootstrap_methods)

            input_result = run_process(
                [str(LAUNCHER), "instance", "input", actor_id, "--text", "advance the main flow"],
                cwd=REPO_ROOT,
                env=command_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=self._output_error_text(input_result))
            input_methods = [
                row["rpc_method"]
                for row in self._read_rpc_rows(Path(str(ctx["calls_path"])))
            ]
            self.assertIn("turn/start", input_methods)

            status_result = run_process(
                [str(LAUNCHER), "instance", "status", actor_id],
                cwd=REPO_ROOT,
                env=command_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_result.returncode, 0, msg=self._output_error_text(status_result))
            status = self._cli_success_data(status_result, kind="instance.status")
            self.assertEqual(status["actor_id"], actor_id)

            stop_result = run_process(
                [str(LAUNCHER), "instance", "stop", actor_id],
                cwd=REPO_ROOT,
                env=command_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=self._output_error_text(stop_result))
            stopped_payload = json.loads(
                (instance_root / "instance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(stopped_payload["status"], "inactive")
            self.assertFalse((instance_root / "runtime" / "app-server.pid").exists())
            self.assertFalse((instance_root / "runtime" / "runtime-broker.pid").exists())
            self.assertFalse(
                (instance_root / "runtime" / "daemon" / "daemon.pid").exists()
            )

            resume_result = run_process(
                [str(LAUNCHER), "instance", "resume", actor_id],
                cwd=REPO_ROOT,
                env=command_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(resume_result.returncode, 0, msg=self._output_error_text(resume_result))
            resumed = self._cli_success_data(resume_result, kind="instance.resume")
            self.assertEqual(resumed["actor_id"], actor_id)
            self.assertEqual(resumed["status"], "active")

            second_stop = run_process(
                [str(LAUNCHER), "instance", "stop", actor_id],
                cwd=REPO_ROOT,
                env=command_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(second_stop.returncode, 0, msg=self._output_error_text(second_stop))

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", actor_id, "--yes"],
                cwd=REPO_ROOT,
                env=command_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(delete_result.returncode, 0, msg=self._output_error_text(delete_result))
            self.assertFalse(instance_root.exists())
            self.assertTrue(shared_root.joinpath("project", "workspace").exists())
