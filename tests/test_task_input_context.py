#!/usr/bin/env python3
"""TaskViewModel and innerTUI rendering tests."""

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
            "updated_at": "2026-06-06T10:00:00+08:00",
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
        status: str = "captured",
        priority: str = "normal",
        refs: list[dict[str, object]] | None = None,
        progress_summary: str = "",
        updated_at: str = "2026-06-06T10:00:00+08:00",
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
                    "origin": {"type": "manual"},
                    "refs": refs or [],
                    "progress_summary": progress_summary,
                    "created_at": "2026-06-06T09:00:00+08:00",
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
        return f"- 2026-06-06T10:00:00+08:00 {event} {task_id}{suffix}"

    def _write_history(self, *, instance_root: Path, role: str, lines: list[str]) -> None:
        self._history_file(instance_root=instance_root, role=role).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _task_files(self, *, instance_root: Path, role: str) -> dict[str, str]:
        tasks_dir = instance_root / "taskbox" / role / "tasks"
        return {path.name: path.read_text(encoding="utf-8") for path in sorted(tasks_dir.glob("*.json"))}

    def test_current_view_empty_state_is_read_only_task_view_model(self) -> None:
        instance = self._make_instance_context()
        instance_root = instance["instance_root"]
        role = str(instance["role"])
        assert isinstance(instance_root, Path)
        before_history = self._history_file(instance_root=instance_root, role=role).read_text(encoding="utf-8")
        before_tasks = self._task_files(instance_root=instance_root, role=role)

        view = task_management.current_view(
            active_role=role,
            active_actor={"actor_id": str(instance["actor_id"]), "role_id": role},
            instance_json=instance["instance_json"],
            instance_payload=instance["instance_payload"],
        )

        self.assertEqual(set(view), {
            "owner_actor",
            "current_anchor",
            "task_state",
            "shelf",
            "pending_switch",
            "recent_events",
            "recent_evidence",
            "available_actions",
            "checkout_cue",
            "warnings",
        })
        self.assertEqual(view["task_state"], "none")
        self.assertIsNone(view["current_anchor"])
        self.assertEqual(view["shelf"], [])
        self.assertIsNone(view["pending_switch"])
        self.assertEqual(view["recent_events"], [])
        self.assertEqual(view["recent_evidence"], [])
        self.assertGreaterEqual(set(view["available_actions"]), {"capture", "review"})
        self.assertEqual(self._history_file(instance_root=instance_root, role=role).read_text(encoding="utf-8"), before_history)
        self.assertEqual(self._task_files(instance_root=instance_root, role=role), before_tasks)

    def test_current_view_replays_events_into_anchor_shelf_pending_and_evidence(self) -> None:
        instance = self._make_instance_context()
        instance_root = instance["instance_root"]
        role = str(instance["role"])
        assert isinstance(instance_root, Path)
        self._write_task_doc(
            instance_root=instance_root,
            role=role,
            task_id="task-0001-alpha",
            title="Alpha",
            summary="Active task summary",
            body="Active task body.",
            status="active",
            progress_summary="Focused implementation in progress.",
            refs=[{"type": "track", "id": "track-alpha", "label": "Primary track"}],
        )
        self._write_task_doc(
            instance_root=instance_root,
            role=role,
            task_id="task-0002-beta",
            title="Beta",
            summary="Captured task summary",
            body="Captured body.",
            status="captured",
        )
        self._write_history(
            instance_root=instance_root,
            role=role,
            lines=[
                self._history_line(event="task.selected", task_id="task-0001-alpha", fields={"reason": "seed"}),
                self._history_line(
                    event="task.progress.appended",
                    task_id="task-0001-alpha",
                    fields={"evidence": "Tests cover TaskViewModel", "summary": "Focused implementation in progress."},
                ),
                self._history_line(
                    event="task.switch.requested",
                    task_id="task-0001-alpha",
                    fields={
                        "confirmation_id": "confirm-0001",
                        "target": {"mode": "existing", "task_id": "task-0002-beta"},
                        "reason": "switch",
                        "evidence": "User asked to switch",
                    },
                ),
            ],
        )

        view = task_management.current_view(
            active_role=role,
            active_actor={"actor_id": str(instance["actor_id"]), "role_id": role},
            instance_json=instance["instance_json"],
            instance_payload=instance["instance_payload"],
            history_limit=8,
        )

        self.assertEqual(view["current_anchor"]["id"], "task-0001-alpha")
        self.assertEqual(view["current_anchor"]["progress_summary"], "Focused implementation in progress.")
        self.assertEqual([row["id"] for row in view["shelf"]], ["task-0002-beta"])
        self.assertEqual(view["pending_switch"]["confirmation_id"], "confirm-0001")
        self.assertEqual(view["recent_evidence"][-1]["evidence"], "User asked to switch")
        self.assertGreaterEqual(set(view["available_actions"]), {"switch_confirm", "checkout"})

    def test_stop_task_tui_renders_checkpoint_for_status_and_next_work(self) -> None:
        view = {
            "owner_actor": {"actor_id": "act-dev-render", "role_id": "dev"},
            "task_state": "active",
            "current_anchor": {
                "id": "task-0003-clean-runtime-env",
                "title": "Clean runtime env",
                "status": "active",
                "progress_summary": "task input TUI and task tools are being implemented",
            },
            "shelf": [],
            "pending_switch": None,
            "recent_events": [{"event": "task.progress.appended", "task_id": "task-0003-clean-runtime-env"}],
            "recent_evidence": [{"task_id": "task-0003-clean-runtime-env", "evidence": "Focused test added."}],
            "available_actions": ["progress", "checkout"],
            "checkout_cue": {"choices": ["continue", "finish", "block"], "requires": {"finish": "evidence", "block": "reason"}},
            "warnings": [],
        }

        tui = task_tui.render_stop_task_tui(view, {"turn_id": "turn_123"})

        for expected in (
            "[TASK CHECKPOINT]",
            "Previous turn completed: turn_123",
            "task-0003-clean-runtime-env - Clean runtime env",
            "Focused test added.",
            "If the task is active, keep working in this turn when there is a clear path forward.",
            "task.checkout continue: pause an unfinished task",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, tui)
        for forbidden in (
            "[TASK CHECKOUT]",
            "No capture, select, switch_request, or switch_confirm in checkout.",
            "Stay silent if no checkout update is needed.",
            "task.propose",
            "task.confirm",
            "Task Handling Cue",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, tui)


if __name__ == "__main__":
    unittest.main()
