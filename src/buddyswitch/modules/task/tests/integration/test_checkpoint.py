"""Retired checkpoint-task contract guards for Task Sys."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.foundation.tool_runtime import registry as tool_registry  # noqa: E402
from buddyswitch.modules.task.private.domain import task_sys  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402


def _task_sys() -> Any:
    return task_sys


class TaskSysCheckpointRetirementTests(RuntimeWorkspaceTestCase):
    def _actor_target(self) -> dict[str, str]:
        return {
            "role_id": "dev",
            "actor_id": self._runtime_actor_id(role="dev", label="act-dev-task-sys-checkpoint"),
        }

    def test_task_sys_has_no_generic_ingest_action(self) -> None:
        task_sys = _task_sys()

        self.assertFalse(hasattr(task_sys, "ingest"))

    def test_checkpoint_update_domain_api_is_retired(self) -> None:
        task_sys = _task_sys()

        self.assertFalse(hasattr(task_sys, "record_checkpoint_update"))

    def test_actor_facing_task_sys_tool_registers_only_current_lifecycle_actions(self) -> None:
        self.assertEqual(
            tool_registry.supported_actions("task_sys"),
            {"create", "list", "get", "cancel"},
        )
