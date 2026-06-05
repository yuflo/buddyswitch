#!/usr/bin/env python3
"""Task input context snapshot and TUI rendering tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.domain import task_management, task_tui  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class TaskInputContextTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _make_instance_context(self, *, actor_id: str = "instance-task-context", role: str = "dev") -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_root = self._runtime_path(f"instances/{actor_id}")
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
            "updated_at": "2026-05-27T10:00:00+08:00",
        }
        instance_json = instance_root / "instance.json"
        instance_json.write_text(json.dumps(instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return {
            "actor_id": actor_id,
            "instance_root": instance_root,
            "instance_json": instance_json,
            "instance_payload": instance_payload,
            "role": role,
        }

    def _actor_payload(self, *, instance_root: Path, role: str) -> dict[str, str]:
        return {"actor_id": instance_root.name, "role_id": role}

    def _history_file(self, *, instance_root: Path, role: str) -> Path:
        return instance_root / "taskbox" / role / "history.md"

    def _task_file(self, *, instance_root: Path, role: str, task_id: str) -> Path:
        return instance_root / "taskbox" / role / "tasks" / f"{task_id}.json"

    def _write_task_doc(
        self,
        *,
        instance_root: Path,
        role: str,
        task_id: str,
        title: str,
        summary: str,
        body: str,
        status: str = "active",
        priority: str = "normal",
        refs: list[dict[str, object]] | None = None,
        updated_at: str = "2026-05-27T10:00:00+08:00",
    ) -> None:
        self._task_file(instance_root=instance_root, role=role, task_id=task_id).write_text(
            json.dumps(
                {
                    "id": task_id,
                    "owner_actor": self._actor_payload(instance_root=instance_root, role=role),
                    "title": title,
                    "summary": summary,
                    "body": body,
                    "status": status,
                    "priority": priority,
                    "track_id": None,
                    "refs": refs or [],
                    "created_at": "2026-05-27T09:00:00+08:00",
                    "updated_at": updated_at,
                    "closed_at": None,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _history_line(self, *, event: str, task_id: str, fields: dict[str, Any] | None = None) -> str:
        parts = [
            f"{key}={json.dumps(value, ensure_ascii=True, separators=(',', ':'))}"
            for key, value in sorted((fields or {}).items())
        ]
        suffix = f" {' '.join(parts)}" if parts else ""
        return f"- 2026-05-27T10:00:00+08:00 {event} {task_id}{suffix}"

    def _write_history(self, *, instance_root: Path, role: str, lines: list[str]) -> None:
        self._history_file(instance_root=instance_root, role=role).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _task_files(self, *, instance_root: Path, role: str) -> dict[str, str]:
        tasks_dir = instance_root / "taskbox" / role / "tasks"
        return {path.name: path.read_text(encoding="utf-8") for path in sorted(tasks_dir.glob("*.json"))}

    def test_current_snapshot_empty_state_is_read_only(self) -> None:
        instance = self._make_instance_context()
        instance_root = instance["instance_root"]
        role = str(instance["role"])
        assert isinstance(instance_root, Path)
        before_history = self._history_file(instance_root=instance_root, role=role).read_text(encoding="utf-8")
        before_tasks = self._task_files(instance_root=instance_root, role=role)

        snapshot = task_management.current_snapshot(
            active_role=role,
            active_actor={"actor_id": str(instance["actor_id"]), "role_id": role},
            instance_json=instance["instance_json"],
            instance_payload=instance["instance_payload"],
        )

        self.assertEqual(snapshot["task_state"], "none")
        self.assertIsNone(snapshot["current_task"])
        self.assertIsNone(snapshot["pending_confirmation"])
        self.assertEqual(snapshot["recent_events"], [])
        self.assertIsNone(snapshot["last_event"])
        self.assertEqual(snapshot["progress_summary"], "")
        self.assertEqual(self._history_file(instance_root=instance_root, role=role).read_text(encoding="utf-8"), before_history)
        self.assertEqual(self._task_files(instance_root=instance_root, role=role), before_tasks)

    def test_task_tui_empty_state_rendering(self) -> None:
        snapshot = {
            "owner_actor": {"actor_id": "act-dev-render", "role_id": "dev"},
            "task_state": "none",
            "current_task": None,
            "pending_confirmation": None,
            "recent_events": [],
            "last_event": None,
            "progress_summary": "",
        }

        tui = task_tui.render_task_tui(snapshot)

        self.assertIn("[TASK CONTEXT]", tui)
        self.assertIn("Current Task: none", tui)
        self.assertIn("State: none", tui)
        self.assertIn("Pending Confirmation: none", tui)
        self.assertNotIn("[USER INPUT]", tui)

    def test_current_snapshot_replays_history_before_loading_current_task(self) -> None:
        instance = self._make_instance_context()
        instance_root = instance["instance_root"]
        role = str(instance["role"])
        assert isinstance(instance_root, Path)
        self._write_task_doc(
            instance_root=instance_root,
            role=role,
            task_id="task-0001-alpha",
            title="Alpha",
            summary="Older task summary",
            body="Older task body.",
        )
        self._write_task_doc(
            instance_root=instance_root,
            role=role,
            task_id="task-0002-beta",
            title="Beta",
            summary="Refine task input context.",
            body="Detailed body for beta task with enough text to show an excerpt.",
            refs=[{"type": "track", "id": "track-alpha", "label": "Primary track"}],
            updated_at="2026-05-27T10:30:00+08:00",
        )
        self._write_task_doc(
            instance_root=instance_root,
            role=role,
            task_id="task-9999-directory-sentinel",
            title="Directory Sentinel",
            summary="This task should not be selected.",
            body="This catches directory-only selection.",
        )
        self._write_history(
            instance_root=instance_root,
            role=role,
            lines=[
                self._history_line(event="task.create", task_id="task-0001-alpha"),
                self._history_line(event="task.create", task_id="task-0002-beta"),
            ],
        )

        snapshot = task_management.current_snapshot(
            active_role=role,
            active_actor={"actor_id": str(instance["actor_id"]), "role_id": role},
            instance_json=instance["instance_json"],
            instance_payload=instance["instance_payload"],
            history_limit=8,
        )

        current_task = snapshot["current_task"]
        self.assertIsInstance(current_task, dict)
        assert isinstance(current_task, dict)
        self.assertEqual(current_task["id"], "task-0002-beta")
        self.assertEqual(current_task["title"], "Beta")
        self.assertEqual(current_task["status"], "active")
        self.assertEqual(current_task["summary"], "Refine task input context.")
        self.assertIn("Detailed body for beta", current_task["body_excerpt"])
        self.assertEqual(current_task["refs"][0]["id"], "track-alpha")
        self.assertEqual(current_task["updated_at"], "2026-05-27T10:30:00+08:00")
        self.assertEqual(snapshot["task_state"], "active")
        self.assertEqual(snapshot["progress_summary"], "Refine task input context.")
        self.assertEqual(
            [event["event"] for event in snapshot["recent_events"]],
            ["task.create", "task.create"],
        )

    def test_task_tui_current_task_and_pending_confirmation_rendering(self) -> None:
        snapshot = {
            "owner_actor": {"actor_id": "act-dev-render", "role_id": "dev"},
            "task_state": "active",
            "current_task": {
                "id": "task-0001-clean-runtime-environment",
                "title": "Clean runtime environment",
                "status": "active",
                "summary": "Refine task input context.",
                "body_excerpt": "Detailed body for the task.",
                "priority": "normal",
                "track_id": None,
                "refs": [],
                "updated_at": "2026-05-27T10:00:00+08:00",
            },
            "pending_confirmation": {
                "confirmation_id": "confirm-0001",
                "type": "task.switch",
                "from_task_id": "task-0001-clean-runtime-environment",
                "target": {
                    "mode": "existing",
                    "task_id": "task-0002-next-task",
                    "task": None,
                },
                "reason": "User asked to switch tasks.",
                "evidence": "Switch request.",
            },
            "recent_events": [
                {
                    "event": "task.create",
                    "task_id": "task-0001-clean-runtime-environment",
                    "line": "- 2026-05-27T10:00:00+08:00 task.create task-0001-clean-runtime-environment",
                },
                {
                    "event": "task.switch.requested",
                    "task_id": "task-0001-clean-runtime-environment",
                    "line": "- 2026-05-27T10:01:00+08:00 task.switch.requested task-0001-clean-runtime-environment confirmation_id=\"confirm-0001\"",
                },
            ],
            "last_event": {
                "event": "task.switch.requested",
                "task_id": "task-0001-clean-runtime-environment",
                "line": "- 2026-05-27T10:01:00+08:00 task.switch.requested task-0001-clean-runtime-environment confirmation_id=\"confirm-0001\"",
            },
            "progress_summary": "Refine task input context.",
        }

        tui = task_tui.render_task_tui(snapshot)

        self.assertIn("Current Task: task-0001-clean-runtime-environment", tui)
        self.assertIn("Title: Clean runtime environment", tui)
        self.assertIn("State: active", tui)
        self.assertIn("Progress: Refine task input context.", tui)
        self.assertIn("Pending Confirmation: confirm-0001", tui)
        self.assertIn("task-0002-next-task", tui)
        self.assertIn("$task-management", tui)
        self.assertIn("task.switch.requested", tui)
        for forbidden_heading in ("Create New Task", "Switch Task", "Tool Reference"):
            self.assertNotIn(forbidden_heading, tui)

    def test_stop_task_tui_current_task_rendering(self) -> None:
        snapshot = {
            "owner_actor": {"actor_id": "act-dev-render", "role_id": "dev"},
            "task_state": "active",
            "current_task": {
                "id": "task-0003-clean-runtime-env",
                "title": "Clean runtime env",
                "status": "active",
                "summary": "task input TUI and task tools are being implemented",
                "body_excerpt": "Detailed body for the task.",
            },
            "pending_confirmation": None,
            "recent_events": [],
            "last_event": {
                "event": "task.update",
                "task_id": "task-0003-clean-runtime-env",
                "line": "- 2026-05-27T10:01:00+08:00 task.update task-0003-clean-runtime-env",
            },
            "progress_summary": "task input TUI and task tools are being implemented",
        }

        tui = task_tui.render_stop_task_tui(snapshot, {"turn_id": "turn_123"})

        self.assertIn("[TASK CHECKOUT]", tui)
        self.assertIn("Previous turn completed: turn_123", tui)
        self.assertIn("Active task", tui)
        self.assertIn("task-0003-clean-runtime-env", tui)
        self.assertIn("Status: active", tui)
        self.assertIn("Progress: task input TUI and task tools are being implemented", tui)
        self.assertIn("Last event: task.update task-0003-clean-runtime-env", tui)
        self.assertNotIn("[TASK CONTEXT]", tui)
        self.assertNotIn("[USER INPUT]", tui)

    def test_stop_task_tui_empty_state_rendering(self) -> None:
        snapshot = {
            "owner_actor": {"actor_id": "act-dev-render", "role_id": "dev"},
            "task_state": "none",
            "current_task": None,
            "pending_confirmation": None,
            "recent_events": [],
            "last_event": None,
            "progress_summary": "",
        }

        tui = task_tui.render_stop_task_tui(snapshot, {"id": "turn_empty"})

        self.assertIn("[TASK CHECKOUT]", tui)
        self.assertIn("Previous turn completed: turn_empty", tui)
        self.assertIn("Active task", tui)
        self.assertIn("none", tui)
        self.assertNotIn("[USER INPUT]", tui)

if __name__ == "__main__":
    unittest.main()
