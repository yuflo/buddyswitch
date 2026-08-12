"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import buddyswitch.foundation.process_runtime.process_identity as process_identity
from tests.process.launcher._harness import ProcessLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process
from tests.support.python import PYTHON
from tests.support.cli import write_executable
from tests.support.fake_cdp import FakeCdpServer

ROOT = REPO_ROOT
LAUNCHER = ROOT / "buddyswitch-codex"
HOST_CONTROL = (
    Path(os.environ["BUDDYSWITCH_PACKAGE_ROOT"])
    / "foundation"
    / "host_control"
    / "shell"
    / "host_control.sh"
)


class TestInstanceCommands(ProcessLauncherHarness, unittest.TestCase):
    def test_start_with_unknown_role_fails_before_shared_root_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            capture_path = temp_root_path / "capture.json"

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = run_process(
                [str(LAUNCHER), "instance", "start", "--role", "unknown"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Unknown role 'unknown'", self._output_error_text(completed))
            self.assertFalse(capture_path.exists(), "codex should not launch when role validation fails")
            self.assertFalse(shared_root.exists(), "invalid role must fail before shared root mutation")
    def test_role_list_prints_manifest_buddies_without_runtime_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = run_process(
                [str(LAUNCHER), "instance", "roles"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            payload = self._cli_success_data(completed, kind="instance.roles")
            self.assertIsInstance(payload, dict)
            assert isinstance(payload, dict)
            role_ids = {row["id"] for row in payload["roles"]}
            self.assertIn("pm", role_ids)
            self.assertIn("dev", role_ids)
            self.assertIn("market", role_ids)
            self.assertFalse(shared_root.exists(), "instance roles must not create runtime state")
    def test_instance_buddies_json_is_structured_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = run_process(
                [str(LAUNCHER), "instance", "roles"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            payload = self._cli_success_data(completed)
            role_ids = {row["id"] for row in payload["roles"]}
            self.assertIn("pm", role_ids)
            self.assertIn("dev", role_ids)
            self.assertIn("market", role_ids)
            for row in payload["roles"]:
                self.assertIsInstance(row["id"], str)
                self.assertIsInstance(row["label"], str)
                self.assertIsInstance(row["scope"], str)
            self.assertFalse(shared_root.exists(), "instance roles --json must not create runtime state")
    def test_instance_list_empty_points_to_start_role(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)

            completed = run_process(
                [str(LAUNCHER), "instance", "list"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertEqual(self._cli_success_data(completed, kind="instance.list"), {"instances": []})
    def test_instance_list_json_empty_returns_empty_array(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)

            completed = run_process(
                [str(LAUNCHER), "instance", "list"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            self.assertEqual(self._cli_success_data(completed), {"instances": []})
            self.assertNotIn("No BuddySwitch instances found.", completed.stdout)
    def test_instance_list_prints_stored_instances_and_filters_by_role(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            for actor_id, role in (
                ("act-pm-a", "pm"),
                ("act-dev-b", "dev"),
            ):
                instance_root = shared_root / "instances" / actor_id
                instance_root.mkdir(parents=True, exist_ok=True)
                (instance_root / "instance.json").write_text(
                    json.dumps(
                        {
                            "actor_id": actor_id,
                            "role": role,
                            "status": "inactive",
                            "workspace_dir": str(instance_root / "workspace"),
                            "browser_port": None,
                            "created_at": "2026-04-26T00:00:00Z",
                            "updated_at": "2026-04-26T00:00:01Z",
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = run_process(
                [str(LAUNCHER), "instance", "list", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            payload = self._cli_success_data(completed, kind="instance.list")
            self.assertIsInstance(payload, dict)
            assert isinstance(payload, dict)
            self.assertEqual([row["actor_id"] for row in payload["instances"]], ["act-pm-a"])
            self.assertEqual(payload["instances"][0]["role"], "pm")
    def test_instance_list_json_filters_by_role(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            for actor_id, role in (
                ("act-pm-a", "pm"),
                ("act-dev-b", "dev"),
            ):
                instance_root = shared_root / "instances" / actor_id
                instance_root.mkdir(parents=True, exist_ok=True)
                (instance_root / "instance.json").write_text(
                    json.dumps(
                        {
                            "actor_id": actor_id,
                            "role": role,
                            "status": "inactive",
                            "workspace_dir": str(instance_root / "workspace"),
                            "browser_port": None,
                            "created_at": "2026-04-26T00:00:00Z",
                            "updated_at": "2026-04-26T00:00:01Z",
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = run_process(
                [str(LAUNCHER), "instance", "list", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            payload = self._cli_success_data(completed)
            self.assertEqual(len(payload["instances"]), 1)
            row = payload["instances"][0]
            self.assertEqual(row["actor_id"], "act-pm-a")
            self.assertEqual(row["role"], "pm")
            self.assertEqual(row["status"], "inactive")
            self.assertEqual(row["app_server_health"], "unhealthy")
            self.assertIsNone(row["thread_id"])
            self.assertIsNone(row["browser_port"])
    def test_instance_delete_removes_only_target_instance_without_shared_state(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _target_workspace = self._write_instance_record(shared_root, "act-pm-delete")
            other_root, _ = self._write_instance_record(shared_root, "act-dev-keep", role="dev")
            state_task = shared_root / "state" / "buddyswitch" / "objects" / "tasks" / "task-keep.json"
            state_task.parent.mkdir(parents=True, exist_ok=True)
            state_task.write_text('{"id":"task-keep"}\n', encoding="utf-8")
            identity_profile = (
                shared_root
                / "state"
                / "buddyswitch"
                / "objects"
                / "identities"
                / "actors"
                / "act-pm-delete.json"
            )
            identity_profile.parent.mkdir(parents=True, exist_ok=True)
            identity_profile.write_text(
                json.dumps({"identity": {"id": "act-pm-delete", "type": "actor"}, "role_id": "pm"}) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-delete", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=self._output_error_text(delete_result))
            self.assertEqual(
                self._cli_success_data(delete_result, kind="instance.delete"),
                {"actor_id": "act-pm-delete", "deleted": True},
            )
            self.assertFalse(target_root.exists())
            self.assertTrue(other_root.exists())
            self.assertTrue(state_task.exists())
            self.assertTrue(identity_profile.exists())
    def test_instance_delete_json_removes_only_target_instance_without_shared_state(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _target_workspace = self._write_instance_record(shared_root, "act-pm-delete")
            other_root, _ = self._write_instance_record(shared_root, "act-dev-keep", role="dev")
            state_task = shared_root / "state" / "buddyswitch" / "objects" / "tasks" / "task-keep.json"
            state_task.parent.mkdir(parents=True, exist_ok=True)
            state_task.write_text('{"id":"task-keep"}\n', encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-delete", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=self._output_error_text(delete_result))
            self.assertEqual(
                self._cli_success_data(delete_result),
                {"actor_id": "act-pm-delete", "deleted": True},
            )
            self.assertFalse(target_root.exists())
            self.assertTrue(other_root.exists())
            self.assertTrue(state_task.exists())
    def test_instance_delete_without_yes_previews_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "act-pm-keep")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-keep"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 4)
            self._cli_error(delete_result, code="CONFIRMATION_REQUIRED")
            self.assertTrue(target_root.exists())
    def test_instance_delete_rejects_traversal_actor_id(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            outside_path = source_home_path / "bad"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "../bad", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 2)
            self.assertIn("Invalid actor id", self._output_error_text(delete_result))
            self.assertFalse(outside_path.exists())
    def test_instance_delete_rejects_missing_target(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-missing", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            error = self._cli_error(delete_result, code="NOT_FOUND")
            self.assertEqual(error.get("message"), "Instance not found: act-pm-missing")
            self.assertNotIn(str(Path(source_home)), delete_result.stdout)
    def test_instance_delete_blocks_active_target_browser_pid(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "act-pm-live-browser-pid")
            browser_dir = target_root / "browser"
            browser_dir.mkdir(parents=True, exist_ok=True)
            process_identity.write_record(browser_dir / "chrome.pid", os.getpid())
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-live-browser-pid", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 4)
            self._cli_error(delete_result, code="CONFLICT")
            self.assertIn("active browser cockpit", self._output_error_text(delete_result))
            self.assertTrue(target_root.exists())
    def test_instance_delete_blocks_live_target_browser_endpoint(self) -> None:
        with closing(FakeCdpServer().start()) as server, tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(
                shared_root,
                "act-pm-live-browser-endpoint",
                browser_port=server.port,
            )
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            write_executable(
                fake_bin / "lsof",
                """#!/usr/bin/env bash
printf '12345\n'
""",
            )
            write_executable(
                fake_bin / "ps",
                f"""#!/usr/bin/env bash
printf '%s\\n' 'Google Chrome --remote-debugging-port={server.port} --user-data-dir={target_root / "browser" / "profile"}'
""",
            )
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-live-browser-endpoint", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 4)
            self._cli_error(delete_result, code="CONFLICT")
            self.assertIn("active browser cockpit", self._output_error_text(delete_result))
            self.assertTrue(target_root.exists())
    def test_instance_delete_ignores_foreign_browser_endpoint_on_stale_port(self) -> None:
        with closing(FakeCdpServer().start()) as server, tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(
                shared_root,
                "act-pm-stale-port",
                browser_port=server.port,
            )
            market_root, _ = self._write_instance_record(
                shared_root,
                "act-market-live-port",
                role="market",
                browser_port=server.port,
            )
            market_browser = market_root / "browser"
            market_browser.mkdir(parents=True, exist_ok=True)
            (market_browser / "chrome.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            write_executable(
                fake_bin / "lsof",
                """#!/usr/bin/env bash
printf '12345\n'
""",
            )
            write_executable(
                fake_bin / "ps",
                f"""#!/usr/bin/env bash
printf '%s\\n' 'Google Chrome --remote-debugging-port={server.port} --user-data-dir={market_root / "browser" / "profile"}'
""",
            )
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-stale-port", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=self._output_error_text(delete_result))
            self.assertEqual(
                self._cli_success_data(delete_result, kind="instance.delete"),
                {"actor_id": "act-pm-stale-port", "deleted": True},
            )
            self.assertFalse(target_root.exists())
            self.assertTrue(market_root.exists())
            self.assertTrue((market_browser / "chrome.pid").exists())
    def test_instance_delete_ignores_stale_legacy_pid_file_without_active_service(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "act-pm-stale-legacy-delete")
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / ("launcher" + "-" + "current" + ".pid")).write_text(f"{os.getpid()}\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-stale-legacy-delete", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=self._output_error_text(delete_result))
            self.assertEqual(
                self._cli_success_data(delete_result, kind="instance.delete"),
                {"actor_id": "act-pm-stale-legacy-delete", "deleted": True},
            )
            self.assertFalse(target_root.exists())
    def test_instance_delete_rejects_symlinked_instance_root_without_touching_external_directory(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as external_root:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instances_root = shared_root / "instances"
            instances_root.mkdir(parents=True, exist_ok=True)
            external_instance_root = Path(external_root) / "external-instance"
            external_workspace = external_instance_root / "workspace"
            external_instance_root.mkdir(parents=True, exist_ok=True)
            (external_instance_root / "instance.json").write_text(
                json.dumps(
                    {
                        "actor_id": "act-pm-symlink",
                        "role": "pm",
                        "status": "inactive",
                        "current_task_id": "task-existing",
                        "current_track_id": "track-existing",
                        "workspace_dir": str(external_workspace),
                        "browser_port": None,
                        "created_at": "2026-04-26T00:00:00Z",
                        "updated_at": "2026-04-26T00:00:01Z",
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            sentinel = external_instance_root / "sentinel.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            (instances_root / "act-pm-symlink").symlink_to(external_instance_root, target_is_directory=True)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-symlink", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 4)
            self._cli_error(delete_result, code="CONFLICT")
            self.assertIn("unsafe instance root", self._output_error_text(delete_result))
            self.assertTrue((instances_root / "act-pm-symlink").is_symlink())
            self.assertTrue(sentinel.exists())
    def test_instance_delete_rejects_symlinked_shared_root_without_touching_target_instance(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as external_root:
            source_home_path = Path(source_home)
            external_root_path = Path(external_root)
            real_shared_root = external_root_path / ".codex-buddyswitch"
            instance_root, _ = self._write_instance_record(
                real_shared_root,
                "act-pm-shared-root-symlink",
            )
            sentinel = instance_root / "sentinel.txt"
            sentinel.write_text("keep\n", encoding="utf-8")

            shared_root_link = source_home_path / ".codex-buddyswitch"
            shared_root_link.symlink_to(real_shared_root, target_is_directory=True)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = run_process(
                [str(LAUNCHER), "instance", "delete", "act-pm-shared-root-symlink", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 4)
            self._cli_error(delete_result, code="CONFLICT")
            self.assertIn("unsafe shared root", self._output_error_text(delete_result))
            self.assertTrue(shared_root_link.is_symlink())
            self.assertTrue(instance_root.exists())
            self.assertTrue(sentinel.exists())
    def test_locked_instance_delete_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_DELETE_ACTOR_ID"] = "act-pm-direct"

            completed = run_process(
                [str(HOST_CONTROL), "instance-delete-locked"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            error = json.loads(completed.stdout)["error"]
            self.assertIn("host control internal operation is not public", error["message"])
    def test_start_without_role_does_not_set_instance_env_vars(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True, exist_ok=True)
            (source_codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "apikey",
                        "openai_api_key": "test-key",
                        "tokens": None,
                        "last_refresh": None,
                        "agent_identity": None,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            capture_path = temp_root_path / "capture.json"
            calls_path = temp_root_path / "calls.jsonl"
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_ROLE_ID"] = "leaked-role"
            env["BUDDYSWITCH_ACTOR_ID"] = "leaked-actor-id"
            env["BUDDYSWITCH_INSTANCE_JSON"] = str(temp_root_path / "leaked-instance.json")

            completed = run_process(
                [str(LAUNCHER), "start", "debug", "prompt-input", "Draft the onboarding PRD"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self._cli_error(completed, code="UNKNOWN_COMMAND")
            self.assertIn("Unknown top-level command: start", self._output_error_text(completed))
            self.assertFalse(capture_path.exists(), "removed start command must not invoke codex")
            self.assertFalse((source_home_path / ".codex-buddyswitch").exists())
    def test_start_with_role_requires_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            capture_path = temp_root_path / "capture.json"

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = run_process(
                [str(LAUNCHER), "instance", "start", "--role"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self._cli_error(completed, code="INVALID_ARGUMENT")
            self.assertIn("instance start requires --role <value>", self._output_error_text(completed))
            self.assertFalse(capture_path.exists(), "codex should not launch when --role is malformed")
            self.assertFalse(shared_root.exists(), "malformed --role must fail before shared root mutation")
    def test_instance_start_help_has_no_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True, exist_ok=True)
            (source_codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "apikey",
                        "openai_api_key": "test-key",
                        "tokens": None,
                        "last_refresh": None,
                        "agent_identity": None,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            capture_path = temp_root_path / "capture.json"
            calls_path = temp_root_path / "calls.jsonl"
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)

            completed = run_process(
                [str(LAUNCHER), "instance", "start", "--role", "pm", "--help"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertIn("buddyswitch-codex instance start --role <role>", completed.stdout)
            self.assertFalse(capture_path.exists(), "help path must not launch Codex")
            self.assertFalse(calls_path.exists(), "help path must not call Codex binary")
            self.assertFalse(ready_file.exists(), "help path must not start browser")
            self.assertFalse(shared_root.exists(), "help path must not create shared instance state")
    def test_locked_start_bootstrap_requires_explicit_application_input_before_instance_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_START_ROLE"] = "unknown"
            env["BUDDYSWITCH_START_ACTOR_ID"] = "act-unknown-demo"
            env["BUDDYSWITCH_START_CODEX_BIN"] = PYTHON
            env["BUDDYSWITCH_START_CODEX_VERSION"] = "test-runtime"
            env["BUDDYSWITCH_HOST_CONTROL_INTERNAL"] = "1"

            direct_start = run_process(
                [
                    PYTHON,
                    "-m",
                    "buddyswitch.foundation.process_runtime.runtime_lock",
                    "--",
                    str(HOST_CONTROL),
                    "start-bootstrap-locked",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(direct_start.returncode, 0)
            error = json.loads(direct_start.stdout)["error"]
            self.assertIn("application start input is required", error["message"])
            self.assertFalse((shared_root / "instances").exists(), "missing application input must not create instances")

    def test_locked_start_builder_failure_blocks_record_and_runtime_services(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            project_app = shared_root / "project" / "workspace" / "projects" / "app"
            project_app.mkdir(parents=True)
            (project_app / ".git").mkdir()
            actor_id = "act-pm-build-failure"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_START_ROLE"] = "pm"
            env["BUDDYSWITCH_START_ACTOR_ID"] = actor_id
            env["BUDDYSWITCH_START_CODEX_BIN"] = PYTHON
            env["BUDDYSWITCH_START_CODEX_VERSION"] = "test-runtime"
            env["BUDDYSWITCH_HOST_CONTROL_INTERNAL"] = "1"
            env["BUDDYSWITCH_HOST_CONTROL_START_MODULE"] = (
                "buddyswitch.application.entrypoints.host_control_start"
            )

            completed = run_process(
                [
                    PYTHON,
                    "-m",
                    "buddyswitch.foundation.process_runtime.runtime_lock",
                    "--shared-root",
                    str(shared_root),
                    "--",
                    str(HOST_CONTROL),
                    "start-bootstrap-locked",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            error = json.loads(completed.stdout)["error"]
            self.assertIn("must be Git-free", error["message"])
            actor_root = shared_root / "instances" / actor_id
            self.assertFalse(actor_root.exists())
            self.assertFalse((actor_root / "instance.json").exists())
            self.assertFalse((actor_root / "runtime").exists())
            self.assertTrue((project_app / ".git").is_dir())
    def test_locked_instance_inactive_rejects_traversal_actor_id(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            outside_path = source_home_path / "outside.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_HOST_CONTROL_INTERNAL"] = "1"

            direct_inactive = run_process(
                [
                    PYTHON,
                    "-m",
                    "buddyswitch.foundation.process_runtime.runtime_lock",
                    "--",
                    str(HOST_CONTROL),
                    "instance-set-inactive-locked",
                    "../outside",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_inactive.returncode, 2)
            error = json.loads(direct_inactive.stdout)["error"]
            self.assertIn("Invalid actor id", error["message"])
            self.assertFalse(outside_path.exists(), "traversal actor id must not write outside instances root")
    def test_locked_start_bootstrap_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_HOST_CONTROL_INTERNAL"] = "1"

            direct_start = run_process(
                [str(HOST_CONTROL), "start-bootstrap-locked"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_start.returncode, 2)
            error = json.loads(direct_start.stdout)["error"]
            self.assertIn("runtime lock required", error["message"])
            self.assertFalse(shared_root.exists(), "direct locked start bootstrap must not mutate shared root")
    def test_locked_start_bootstrap_requires_role_env_before_workspace_setup(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env.pop("BUDDYSWITCH_START_ROLE", None)
            env.pop("BUDDYSWITCH_START_ACTOR_ID", None)
            env["BUDDYSWITCH_HOST_CONTROL_INTERNAL"] = "1"

            completed = run_process(
                [
                    PYTHON,
                    "-m",
                    "buddyswitch.foundation.process_runtime.runtime_lock",
                    "--shared-root",
                    str(shared_root),
                    "--",
                    str(HOST_CONTROL),
                    "start-bootstrap-locked",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            error = json.loads(completed.stdout)["error"]
            self.assertIn("BUDDYSWITCH_START_ROLE is required", error["message"])
            self.assertFalse((shared_root / "workspace").exists(), "missing role env must fail before workspace prep")
    def test_locked_start_bootstrap_requires_actor_id_env(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_START_ROLE"] = "pm"
            env.pop("BUDDYSWITCH_START_ACTOR_ID", None)
            env["BUDDYSWITCH_HOST_CONTROL_INTERNAL"] = "1"

            completed = run_process(
                [
                    PYTHON,
                    "-m",
                    "buddyswitch.foundation.process_runtime.runtime_lock",
                    "--shared-root",
                    str(shared_root),
                    "--",
                    str(HOST_CONTROL),
                    "start-bootstrap-locked",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            error = json.loads(completed.stdout)["error"]
            self.assertIn("BUDDYSWITCH_START_ACTOR_ID is required", error["message"])
            self.assertFalse((shared_root / "workspace").exists(), "missing actor id must fail before workspace prep")
