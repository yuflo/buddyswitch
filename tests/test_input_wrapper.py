#!/usr/bin/env python3
"""Tests for launcher-owned input wrapper selection and composition."""

from __future__ import annotations

import importlib.util
import json
import unittest
from itertools import count
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_WRAPPER_PATH = ROOT / "tools" / "launcher" / "input_wrapper.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module_name = f"buddyswitch_{path.stem}_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LauncherInputWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.input_wrapper = load_module(INPUT_WRAPPER_PATH)

    def _make_instance_context(self, temp_root: Path, *, actor_id: str = "act-dev-task-context", role: str = "dev") -> dict[str, object]:
        instance_root = temp_root / "instances" / actor_id
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        taskbox_root = instance_root / "taskbox" / role
        (taskbox_root / "tasks").mkdir(parents=True, exist_ok=True)
        (taskbox_root / "history.md").write_text("", encoding="utf-8")
        instance_payload: dict[str, object] = {
            "actor_id": actor_id,
            "role": role,
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "browser_port": None,
            "updated_at": "2026-05-28T10:00:00+08:00",
        }
        instance_json = instance_root / "instance.json"
        instance_json.write_text(json.dumps(instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return {
            "instance_root": instance_root,
            "instance_json": instance_json,
            "instance_payload": instance_payload,
            "role": role,
        }

    def _seed_current_task(
        self,
        *,
        instance_root: Path,
        role: str,
        task_id: str = "task-0001-launcher-context",
        title: str = "Launcher context task",
        summary: str = "Render task context before user input.",
    ) -> None:
        taskbox_root = instance_root / "taskbox" / role
        tasks_dir = taskbox_root / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        task_payload = {
            "id": task_id,
            "owner_actor": {"actor_id": instance_root.name, "role_id": role},
            "title": title,
            "summary": summary,
            "body": "Detailed launcher task body.",
            "status": "active",
            "priority": "normal",
            "track_id": None,
            "refs": [],
            "created_at": "2026-05-28T10:00:00+08:00",
            "updated_at": "2026-05-28T10:00:00+08:00",
            "closed_at": None,
        }
        (tasks_dir / f"{task_id}.json").write_text(json.dumps(task_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        (taskbox_root / "history.md").write_text(
            f"- 2026-05-28T10:00:00+08:00 task.create {task_id} title={json.dumps(title, ensure_ascii=True, separators=(',', ':'))} status=\"active\"\n",
            encoding="utf-8",
        )

    def test_raw_wrapper_returns_raw_text_unchanged(self) -> None:
        with self.subTest("raw"):
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as temp_root:
                instance = self._make_instance_context(Path(temp_root))

                text = self.input_wrapper.compose_input_text(
                    wrapper_name="raw",
                    raw_text="Draft brief",
                    instance_json=instance["instance_json"],
                )

                self.assertEqual(text, "Draft brief")

    def test_task_tui_wrapper_renders_task_context_and_user_input(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_root:
            instance = self._make_instance_context(Path(temp_root))
            instance_root = instance["instance_root"]
            role = str(instance["role"])
            assert isinstance(instance_root, Path)
            self._seed_current_task(instance_root=instance_root, role=role)

            text = self.input_wrapper.compose_input_text(
                wrapper_name="task-tui",
                raw_text="Draft brief",
                instance_json=instance["instance_json"],
            )

            self.assertTrue(text.startswith("[TASK CONTEXT]"), msg=text)
            self.assertIn("Current Anchor: task-0001-launcher-context - Launcher context task", text)
            self.assertIn("State: active", text)
            self.assertIn("[USER INPUT]", text)
            self.assertIn("Draft brief", text)
            self.assertLess(text.index("[USER INPUT]"), text.index("Draft brief"))

    def test_unknown_wrapper_name_is_rejected(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_root:
            instance = self._make_instance_context(Path(temp_root))

            with self.assertRaises(self.input_wrapper.InputWrapperSelectionError):
                self.input_wrapper.compose_input_text(
                    wrapper_name="task-ui",
                    raw_text="Draft brief",
                    instance_json=instance["instance_json"],
                )

            with self.assertRaises(self.input_wrapper.InputWrapperSelectionError):
                self.input_wrapper.compose_input_text(
                    wrapper_name="unknown-wrapper",
                    raw_text="Draft brief",
                    instance_json=instance["instance_json"],
                )


if __name__ == "__main__":
    unittest.main()
