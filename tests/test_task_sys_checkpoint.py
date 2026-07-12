#!/usr/bin/env python3
"""Retired checkpoint-task contract guards for Task Sys."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tool_runtime import registry as tool_registry  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


def _task_sys() -> Any:
    return importlib.import_module("env.domain.task_sys")


class TaskSysCheckpointRetirementTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _actor_target(self) -> dict[str, str]:
        return {
            "role_id": "dev",
            "actor_id": self._runtime_actor_id(role="dev", label="act-dev-task-sys-checkpoint"),
        }

    def test_turn_completed_source_is_not_task_sys_ingest_input(self) -> None:
        task_sys = _task_sys()

        with self.assertRaisesRegex(ValueError, "app_server.turn_completed"):
            task_sys.ingest(
                {
                    "source": {
                        "type": "app_server.turn_completed",
                        "ref": {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
                    },
                    "actor_target": self._actor_target(),
                    "context": {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
                }
            )

    def test_checkpoint_update_domain_api_is_retired(self) -> None:
        task_sys = _task_sys()

        self.assertFalse(hasattr(task_sys, "record_checkpoint_update"))

    def test_actor_facing_task_sys_tool_does_not_register_checkpoint_update(self) -> None:
        tool_registry.clear_cache()

        self.assertEqual(
            tool_registry.supported_actions("task_sys"),
            {"list", "get", "update_task_analysis", "close", "need_parent"},
        )


if __name__ == "__main__":
    unittest.main()
