"""Safety tests for the launcher fake Codex executable."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAKE_CODEX = ROOT / "tests" / "helpers" / "fake_codex.py"
PYTHON = os.environ["BUDDYSWITCH_PYTHON"]


class FakeCodexTests(unittest.TestCase):
    def test_version_is_available_without_actor_environment(self) -> None:
        env = {key: value for key, value in os.environ.items() if key != "CODEX_HOME"}

        completed = subprocess.run(
            [PYTHON, str(FAKE_CODEX), "--version"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "codex-cli fake-test")

    def test_non_version_command_rejects_non_temporary_shared_root(self) -> None:
        registry_paths = (
            lambda temp_root: Path(temp_root) / "processes.jsonl",
            lambda _temp_root: Path.home() / ".codex-buddyswitch" / "test-processes.jsonl",
        )
        for registry_path in registry_paths:
            with self.subTest(registry_path=registry_path), tempfile.TemporaryDirectory() as temp_root:
                env = os.environ.copy()
                env["CODEX_HOME"] = str(Path(temp_root) / "codex-home")
                env["BUDDYSWITCH_SHARED_ROOT"] = str(Path.home() / ".codex-buddyswitch")
                env["BUDDYSWITCH_TEST_PROCESS_REGISTRY"] = str(registry_path(temp_root))

                completed = subprocess.run(
                    [PYTHON, str(FAKE_CODEX), "noop"],
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
            env["BUDDYSWITCH_TEST_PROCESS_REGISTRY"] = str(root / "processes.jsonl")

            completed = subprocess.run(
                [PYTHON, str(FAKE_CODEX), "noop"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)


if __name__ == "__main__":
    unittest.main()
