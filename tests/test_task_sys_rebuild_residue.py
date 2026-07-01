#!/usr/bin/env python3
"""Live-surface residue checks for the Task Sys rebuild."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TaskSysRebuildResidueTests(unittest.TestCase):
    def test_live_task_sys_surfaces_do_not_teach_checkpoint_task_semantics(self) -> None:
        live_paths = [
            ROOT / "scripts" / "env" / "domain" / "task_sys.py",
            ROOT / "tools" / "launcher" / "task_sys_ingress.py",
            ROOT / "tools" / "launcher" / "task_checkout_handler.py",
            ROOT / "tools" / "launcher" / "task_sys_runtime.py",
            ROOT / "scripts" / "env" / "tools" / "task_sys" / "tool.py",
            ROOT / "scripts" / "env" / "tools" / "task_sys" / "_impl.py",
            ROOT / "scripts" / "env" / "tool_runtime" / "context.py",
            ROOT / "scripts" / "env" / "tool_runtime" / "role_auth.py",
            ROOT / "scripts" / "env" / "tool_runtime" / "registry.py",
            ROOT / "scripts" / "env" / "tools" / "context" / "_impl.py",
            ROOT / "buddyswitch" / "skills" / "shared" / "task-management" / "SKILL.md",
            *sorted((ROOT / "tools" / "launcher" / "assets" / "roles").glob("*/AGENTS.md")),
        ]
        forbidden_tokens = (
            "task_sys.checkpoint",
            "checkpoint_update",
            "checkpoint_metadata",
            "INITIAL_PROCESSORS",
            "initial_processor",
            "no_actor_action",
        )

        violations: list[str] = []
        for path in live_paths:
            self.assertTrue(path.exists(), msg=path)
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                if token in text:
                    violations.append(f"{path.relative_to(ROOT)} contains {token}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
