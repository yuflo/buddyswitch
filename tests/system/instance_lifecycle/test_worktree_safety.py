"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.system.support.launcher import SystemLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process

ROOT = REPO_ROOT
LAUNCHER = ROOT / "buddyswitch-codex"


class TestWorktreeSafety(SystemLauncherHarness, unittest.TestCase):
    def test_workspace_sync_rebuilds_valid_stale_worktree_to_repo_head(self) -> None:
        parent_head = run_process(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD~1"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if parent_head.returncode != 0:
            self.skipTest("repository does not have HEAD~1 available for stale-worktree test")
        stale_head = parent_head.stdout.strip()
        repo_head = run_process(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(repo_head.returncode, 0, msg=self._output_error_text(repo_head))
        current_head = repo_head.stdout.strip()
        self.assertNotEqual(stale_head, current_head)

        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"
            shared_root.mkdir(parents=True, exist_ok=True)

            add_worktree = run_process(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(workspace_dir), stale_head],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(add_worktree.returncode, 0, msg=self._output_error_text(add_worktree))

            try:
                before_sync = run_process(
                    ["git", "-C", str(workspace_dir), "rev-parse", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(before_sync.returncode, 0, msg=self._output_error_text(before_sync))
                self.assertEqual(before_sync.stdout.strip(), stale_head)

                env = os.environ.copy()
                env["HOME"] = str(source_home_path)
                env.pop("CODEX_HOME", None)

                sync_result = run_process(
                    [str(LAUNCHER), "workspace", "sync"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(sync_result.returncode, 2)
                self._cli_error(sync_result, code="UNKNOWN_COMMAND")
                self.assertIn("Unknown top-level command: workspace", self._output_error_text(sync_result))

                after_sync = run_process(
                    ["git", "-C", str(workspace_dir), "rev-parse", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(after_sync.returncode, 0, msg=self._output_error_text(after_sync))
                self.assertEqual(after_sync.stdout.strip(), stale_head)
            finally:
                run_process(
                    ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(workspace_dir)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                run_process(
                    ["git", "-C", str(ROOT), "worktree", "prune"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
    def test_reset_removes_registered_instance_worktrees(self) -> None:
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

            ready_file = temp_root_path / "browser-ready.flag"
            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = run_process(
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / payload["actor_id"]
            workspace_dir = instance_root / "workspace"
            self.assertTrue(workspace_dir.exists())

            stop_result = run_process(
                [str(LAUNCHER), "instance", "stop", payload["actor_id"]],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=self._output_error_text(stop_result))
            ready_file.unlink(missing_ok=True)

            try:
                reset_with_yes = run_process(
                    [str(LAUNCHER), "env", "reset", "--yes"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(reset_with_yes.returncode, 0, msg=self._output_error_text(reset_with_yes))
                worktrees = run_process(
                    ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout
                self.assertNotIn(str(workspace_dir), worktrees)
            finally:
                run_process(
                    ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(workspace_dir)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                run_process(
                    ["git", "-C", str(ROOT), "worktree", "prune"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
            self.assertFalse(shared_root.exists(), "reset should remove the shared launcher root")
    def test_start_rejects_project_workspace_dir_existing_worktree_outside_shared_root(self) -> None:
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

            external_project_workspace = temp_root_path / "external-project-workspace"
            run_process(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(external_project_workspace), "HEAD"],
                text=True,
                capture_output=True,
                check=True,
            )
            sentinel = external_project_workspace / "outside-sentinel.txt"
            sentinel.write_text("do-not-delete\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")
            env["BUDDYSWITCH_PROJECT_WORKSPACE_DIR"] = str(external_project_workspace)

            try:
                completed = run_process(
                    [str(LAUNCHER), "instance", "start", "--role", "pm"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("project workspace dir must be under BUDDYSWITCH_SHARED_ROOT", self._output_error_text(completed))
                self.assertTrue(sentinel.exists(), "external project workspace sentinel must be preserved")
            finally:
                run_process(
                    ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(external_project_workspace)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                run_process(
                    ["git", "-C", str(ROOT), "worktree", "prune"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
