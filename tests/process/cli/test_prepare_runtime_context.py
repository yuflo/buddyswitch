"""Runless replacement tests for retired prepare runtime context flow."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from tests.support.python import PYTHON

from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process
from tests.support.cli import parse_json_stdout

ROOT = REPO_ROOT


class PrepareRuntimeContextRunlessTests(unittest.TestCase):
    def _invoke_turn_runtime(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run_process(
            [PYTHON, "-m", "buddyswitch.application.entrypoints.diagnostics", *args],
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
        payload = parse_json_stdout(completed)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runtime_mode"], "runless")
        env_tools = payload.get("env_tools", {})
        self.assertIn("context", env_tools)
        self.assertNotIn("memory", env_tools)
        self.assertNotIn("actor_private", env_tools)
        self.assertNotIn("run", env_tools)
        self.assertNotIn("binding", env_tools)
