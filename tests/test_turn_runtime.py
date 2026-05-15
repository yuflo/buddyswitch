#!/usr/bin/env python3
"""Runless turn runtime command contract tests."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TurnRuntimeRunlessTests(unittest.TestCase):
    def _invoke(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(ROOT / "scripts" / "turn_runtime.py"), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_prepare_and_persist_commands_are_not_cli_entries(self) -> None:
        for args in (
            ("prepare", "hello"),
            ("persist", "--context", "{}", "--result", "{}"),
        ):
            with self.subTest(command=args[0]):
                completed = self._invoke(*args)
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout.strip(), "")
                self.assertIn("invalid choice", completed.stderr)
                self.assertIn(f"'{args[0]}'", completed.stderr)

    def test_status_lists_only_runless_tool_surfaces(self) -> None:
        completed = self._invoke("status")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runtime_mode"], "runless")
        tools = payload["env_tools"]
        self.assertIn("task", tools)
        self.assertIn("context", tools)
        self.assertIn("memory", tools)
        self.assertIn("buddybox", tools)
        self.assertNotIn("run", tools)
        self.assertNotIn("binding", tools)


if __name__ == "__main__":
    unittest.main()
