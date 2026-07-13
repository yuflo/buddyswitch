#!/usr/bin/env python3
"""Runless replacement tests for retired prepare runtime context flow."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from tests.python_runtime import PYTHON

ROOT = Path(__file__).resolve().parents[1]


class PrepareRuntimeContextRunlessTests(unittest.TestCase):
    def _invoke_turn_runtime(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, str(ROOT / "scripts" / "turn_runtime.py"), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_prepare_command_is_not_exposed(self) -> None:
        completed = self._invoke_turn_runtime("prepare", "please summarize")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("invalid choice", completed.stderr)
        self.assertIn("'prepare'", completed.stderr)

    def test_status_payload_has_runless_context_only(self) -> None:
        completed = self._invoke_turn_runtime("status")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runtime_mode"], "runless")
        env_tools = payload.get("env_tools", {})
        self.assertIn("context", env_tools)
        self.assertNotIn("memory", env_tools)
        self.assertNotIn("actor_private", env_tools)
        self.assertNotIn("run", env_tools)
        self.assertNotIn("binding", env_tools)


if __name__ == "__main__":
    unittest.main()
