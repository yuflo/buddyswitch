"""Safety tests for the launcher fake Codex executable."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process
from tests.support.fake_codex import write_fake_codex

ROOT = REPO_ROOT
PYTHON = os.environ["BUDDYSWITCH_PYTHON"]


class FakeCodexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.fake_codex = write_fake_codex(Path(self.temp_dir.name) / "codex")

    def test_version_is_available_without_actor_environment(self) -> None:
        env = {key: value for key, value in os.environ.items() if key != "CODEX_HOME"}

        completed = run_process(
            [str(self.fake_codex), "--version"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "codex-cli fake-test")

    def test_executable_disables_bytecode_when_parent_flag_is_absent(self) -> None:
        cache_root = Path(self.temp_dir.name) / "pycache"
        env = os.environ.copy()
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        env["PYTHONPYCACHEPREFIX"] = str(cache_root)

        completed = run_process(
            [str(self.fake_codex), "--version"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertFalse(cache_root.exists())

    def test_non_version_command_rejects_non_temporary_shared_root(self) -> None:
        run_roots = (Path("/"), ROOT)
        for run_root in run_roots:
            with self.subTest(run_root=run_root), tempfile.TemporaryDirectory() as temp_root:
                env = os.environ.copy()
                env["CODEX_HOME"] = str(Path(temp_root) / "codex-home")
                env["BUDDYSWITCH_SHARED_ROOT"] = str(ROOT / ".unsafe-fake-shared-root")
                env["BUDDYSWITCH_TEST_RUN_ROOT"] = str(run_root)

                completed = run_process(
                    [str(self.fake_codex), "noop"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("temporary BUDDYSWITCH_SHARED_ROOT", completed.stderr)

    def test_non_version_command_accepts_temporary_shared_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            codex_home = root / "codex-home"
            codex_home.mkdir()
            env = os.environ.copy()
            env["CODEX_HOME"] = str(codex_home)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(root / "shared")
            env["BUDDYSWITCH_TEST_RUN_ROOT"] = str(root)

            completed = run_process(
                [str(self.fake_codex), "noop"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
