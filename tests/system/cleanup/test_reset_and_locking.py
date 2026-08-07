"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import buddyswitch.foundation.process_runtime.process_identity as process_identity
from tests.system.support.launcher import SystemLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import ResourceLedger, run_process
from tests.support.python import PYTHON

ROOT = REPO_ROOT
LOCK_TIMEOUT_SECONDS = "0.2"


class TestResetAndLocking(SystemLauncherHarness, unittest.TestCase):
    def test_runtime_lock_is_not_inherited_by_background_children(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            source_home_path = Path(source_home)
            temp_root_path = Path(temp_root)
            shared_root = source_home_path / ".codex-buddyswitch"
            child_pid_path = temp_root_path / "background-child.pid"

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_TEST_CHILD_PID"] = str(child_pid_path)
            env["BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"] = LOCK_TIMEOUT_SECONDS

            first = run_process(
                [
                    PYTHON,
                    str(ROOT / "src" / "buddyswitch" / "launcher" / "runtime_lock.py"),
                    "--",
                    "bash",
                    "-c",
                    'sleep 30 >/dev/null 2>&1 & printf "%s\\n" "$!" > "${BUDDYSWITCH_TEST_CHILD_PID}"',
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, msg=self._output_error_text(first))
            self.assertTrue(
                child_pid_path.exists(),
                "precondition: locked command started a background child",
            )
            child_pid = int(child_pid_path.read_text(encoding="utf-8").strip())
            child_identity = process_identity.start_identity(child_pid)
            self.assertIsNotNone(child_identity)
            ResourceLedger.from_environment().register_process(
                pid=child_pid,
                pgid=os.getpgid(child_pid),
                start_identity=str(child_identity),
                command=["sleep", "30"],
                cleanup_strategy="terminate_owned_pgid",
                cleanup_args={},
            )

            try:
                second = run_process(
                    [
                        PYTHON,
                        str(ROOT / "src" / "buddyswitch" / "launcher" / "runtime_lock.py"),
                        "--",
                        PYTHON,
                        "-c",
                        "print('lock reacquired')",
                    ],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                run_process(
                    ["kill", str(child_pid)],
                    text=True,
                    capture_output=True,
                    check=False,
                )

            self.assertEqual(second.returncode, 0, msg=self._output_error_text(second))
            self.assertIn("lock reacquired", second.stdout)

    def test_runtime_lock_terminates_child_before_releasing_lock_on_signal(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            source_home_path = Path(source_home)
            temp_root_path = Path(temp_root)
            shared_root = source_home_path / ".codex-buddyswitch"
            child_pid_path = temp_root_path / "child.pid"
            mutation_path = temp_root_path / "mutated.txt"

            child_script = (
                "import os, sys, time\n"
                "from pathlib import Path\n"
                "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
                "time.sleep(1)\n"
                "Path(sys.argv[2]).write_text('mutated\\n', encoding='utf-8')\n"
                "time.sleep(30)\n"
            )

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

            wrapper = self._ledger.start_process(
                [
                    PYTHON,
                    str(ROOT / "src" / "buddyswitch" / "launcher" / "runtime_lock.py"),
                    "--",
                    PYTHON,
                    "-c",
                    child_script,
                    str(child_pid_path),
                    str(mutation_path),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                for _ in range(50):
                    if child_pid_path.exists():
                        break
                    time.sleep(0.05)
                self.assertTrue(child_pid_path.exists(), "precondition: child process started")

                wrapper.terminate()
                wrapper.wait(timeout=5)
                time.sleep(1.2)

                self.assertFalse(mutation_path.exists(), "child must not keep mutating after lock wrapper terminates")
            finally:
                if wrapper.poll() is None:
                    wrapper.kill()
                    wrapper.wait(timeout=5)
                if child_pid_path.exists():
                    child_pid = child_pid_path.read_text(encoding="utf-8").strip()
                    run_process(["kill", child_pid], text=True, capture_output=True, check=False)
