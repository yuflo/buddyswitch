"""Runless turn runtime command contract tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.cli import parse_json_stdout
from tests.support.processes import run_process

ROOT = REPO_ROOT

from buddyswitch.foundation.tool_runtime import registry as tool_catalog  # noqa: E402


class TurnRuntimeRunlessTests(unittest.TestCase):
    def _invoke(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run_process(
            [
                os.environ["BUDDYSWITCH_PYTHON"],
                "-m",
                "buddyswitch.application.entrypoints.diagnostics",
                *args,
            ],
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
        payload = parse_json_stdout(completed)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["runtime_mode"], "runless")
        tools = payload["env_tools"]
        self.assertIn("task_sys", tools)
        self.assertIn("context", tools)
        self.assertNotIn("memory", tools)
        self.assertNotIn("actor_private", tools)
        self.assertNotIn("run", tools)
        self.assertNotIn("binding", tools)
        self.assertEqual(set(tools), set(tool_catalog.env_tools_description(exclude_tools={"actor_private"})))
        self.assertEqual(tools, tool_catalog.env_tools_description(exclude_tools={"actor_private"}))
        desc = tool_catalog.env_tools_description()
        self.assertIn("object_model", desc["track"])
        for tool_name, row in sorted(tools.items()):
            with self.subTest(tool=tool_name):
                self.assertIn("object_model", row)
                self.assertIn("action_semantics", row)
                action_semantics = row["action_semantics"]
                self.assertIsInstance(action_semantics, dict, msg=row)
                self.assertTrue(action_semantics, msg=row)
                for action_name, action_row in action_semantics.items():
                    with self.subTest(action=f"{tool_name}.{action_name}"):
                        self.assertIn("reads", action_row["side_effects"])
                        self.assertNotIn(
                            "completed under declared capability boundary",
                            action_row["success_means"],
                        )
        track_create = tools["track"]["input_schemas"]["create"]
        self.assertEqual(track_create["properties"]["now"]["type"], "object")
        self.assertEqual(track_create["properties"]["now"]["required"], ["next"])
        compact = tool_catalog.compact_tool_affordances()
        for tool_name, row in sorted(tools.items()):
            with self.subTest(compact_tool=tool_name):
                self.assertGreater(len(row), len(compact.get(tool_name, {})))
                self.assertNotIn("action_semantics", compact.get(tool_name, {}))
