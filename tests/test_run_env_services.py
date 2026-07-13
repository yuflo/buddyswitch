#!/usr/bin/env python3
"""Runless runtime command guardrail coverage."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from tests.python_runtime import PYTHON

ROOT = Path(__file__).resolve().parents[1]


class RunlessRuntimeCommandTests(unittest.TestCase):
    def _invoke(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, str(ROOT / "scripts" / "turn_runtime.py"), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_prepare_command_is_not_exposed(self) -> None:
        completed = self._invoke("prepare", "draft summary")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("invalid choice", completed.stderr)
        self.assertIn("'prepare'", completed.stderr)

    def test_persist_command_is_not_exposed(self) -> None:
        completed = self._invoke("persist", "--context", "{}", "--result", "{}")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("invalid choice", completed.stderr)
        self.assertIn("'persist'", completed.stderr)

    def test_status_command_reports_runless_env_tools(self) -> None:
        completed = self._invoke("status")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runtime_mode"], "runless")
        self.assertIn("env_tools", payload)
        self.assertNotIn("run", payload["env_tools"])
        self.assertNotIn("binding", payload["env_tools"])


if __name__ == "__main__":
    unittest.main()
