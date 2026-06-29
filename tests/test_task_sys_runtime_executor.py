#!/usr/bin/env python3
"""Tests for executing Task Sys runtime instructions."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HELPER_DIR = ROOT / "tools" / "launcher"
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from env.repos import runtime_files  # noqa: E402

TASK_SYS_RUNTIME_PATH = ROOT / "tools" / "launcher" / "task_sys_runtime.py"
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


@dataclass
class _Context:
    actor_id: str
    role: str
    main_thread_id: str
    socket_path: Path
    permissions: str
    instance_json: Path
    workspace_dir: Path
    project_workspace_dir: Path


class TaskSysRuntimeExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp_dir.name)
        runtime_files.set_runtime_root_override(self.root)
        self.module = load_module(TASK_SYS_RUNTIME_PATH)

    def tearDown(self) -> None:
        runtime_files.reset_runtime_root_override()
        self._tmp_dir.cleanup()
        super().tearDown()

    def _context(self) -> _Context:
        instance_root = self.root / "instances" / "act-dev-task-sys-runtime"
        workspace_dir = instance_root / "workspace"
        project_workspace_dir = self.root / "project" / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        project_workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": "act-dev-task-sys-runtime",
                    "role": "dev",
                    "thread_id": "thr-main",
                    "workspace_dir": str(workspace_dir),
                    "project_workspace_dir": str(project_workspace_dir),
                    "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return _Context(
            actor_id="act-dev-task-sys-runtime",
            role="dev",
            main_thread_id="thr-main",
            socket_path=Path("/tmp/task-sys-runtime.sock"),
            permissions="buddyswitch-runtime",
            instance_json=instance_json,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
        )

    def _instruction(self) -> dict[str, Any]:
        return {
            "type": "start_side",
            "task_id": "task-user-input-abcdef123456",
            "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
            "frame": {
                "kind": "task_sys.side_frame",
                "task_id": "task-user-input-abcdef123456",
                "source": {"type": "user.input", "ref": {"id": "input-1", "surface": "cli"}},
                "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
                "context": {"text": "Draft brief"},
            },
        }

    def _parent_instruction(self, *, interrupt: bool = False) -> dict[str, Any]:
        return {
            "type": "interrupt_submit_parent" if interrupt else "submit_parent",
            "task_id": "task-user-input-abcdef123456",
            "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
            "frame": {
                "kind": "task_sys.parent_frame",
                "task_id": "task-user-input-abcdef123456",
                "source": {"type": "user.input", "ref": {"id": "input-1", "surface": "cli"}},
                "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
                "inbound_context": {"text": "Draft brief"},
                "side_result": {"outcome": "need_parent", "params": {"interrupt": interrupt}},
                "parent_handoff_params": {
                    "parent_frame_context": {"next": "Draft the brief in parent."},
                    "relation": "User input requires main-thread work.",
                    "interrupt": interrupt,
                },
            },
        }

    def _checkpoint_instruction(self) -> dict[str, Any]:
        return {
            "type": "submit_parent",
            "task_id": "task-turn-completed-abcdef123456",
            "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
            "frame": {
                "kind": "task_sys.checkpoint",
                "task_id": "task-turn-completed-abcdef123456",
                "source": {"type": "app_server.turn_completed", "ref": {"turn_id": "turn-user-1"}},
                "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
                "completed_turn": {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
                "checkpoint_state": "awaiting_update",
                "current_task_context": {},
                "pending_task_context": [],
                "legal_operations": [
                    {
                        "tool": "task_sys",
                        "action": "checkpoint_update",
                        "required_params": ["task_id", "outcome"],
                        "outcomes": ["close", "continue"],
                    }
                ],
                "constraints": [
                    "Do not recommend the next task.",
                    "Choose a legal operation based on current work state.",
                ],
            },
        }

    def test_render_side_frame_is_task_sys_scoped_and_names_only_two_results(self) -> None:
        text = self.module.render_side_frame(self._instruction()["frame"])

        self.assertIn("task_sys.side_frame", text)
        self.assertIn("task-user-input-abcdef123456", text)
        self.assertIn("task_sys.close", text)
        self.assertIn("task_sys.need_parent", text)
        self.assertNotIn("[IM MESSAGE TRIAGE]", text)
        self.assertNotIn("[TRACK COMMENT TRIAGE]", text)
        self.assertNotIn("submit parent", text.lower())
        self.assertNotIn("side_interrupt", text)

    def test_execute_start_side_instruction_uses_physical_side_start(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_side_start = self.module.app_server.side_start
        original_input_turn = self.module.app_server.input_turn

        def fake_side_start(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "side_start", **kwargs})
            return {"action": "start", "side_thread_id": "thr-side-1", "turn_id": "turn-side-1"}

        def fake_input_turn(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("no existing side thread should be reused in this test")

        self.addCleanup(setattr, self.module.app_server, "side_start", original_side_start)
        self.addCleanup(setattr, self.module.app_server, "input_turn", original_input_turn)
        self.module.app_server.side_start = fake_side_start
        self.module.app_server.input_turn = fake_input_turn

        result = self.module.execute_instruction(context, self._instruction())

        self.assertEqual(result["action"], "start_side")
        self.assertEqual(result["side_thread_id"], "thr-side-1")
        self.assertEqual([call["helper"] for call in calls], ["side_start"])
        text = calls[0]["text"]
        self.assertIn("task_sys.side_frame", text)
        self.assertIn("task_sys.close", text)
        self.assertIn("task_sys.need_parent", text)
        self.assertEqual(calls[0]["parent_thread_id"], "thr-main")

        instance_payload = json.loads(context.instance_json.read_text(encoding="utf-8"))
        self.assertEqual(instance_payload["side_threads"][0]["thread_id"], "thr-side-1")

    def test_execute_start_side_rejects_wrong_actor_target(self) -> None:
        instruction = self._instruction()
        instruction["actor_target"] = {"actor_id": "act-other", "role_id": "dev"}

        with self.assertRaisesRegex(PermissionError, "wrong target actor"):
            self.module.execute_instruction(self._context(), instruction)

    def test_execute_no_actor_action_does_not_touch_app_server(self) -> None:
        context = self._context()
        original_side_start = self.module.app_server.side_start

        def fake_side_start(**_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("no_actor_action must not start side")

        self.addCleanup(setattr, self.module.app_server, "side_start", original_side_start)
        self.module.app_server.side_start = fake_side_start

        result = self.module.execute_instruction(
            context,
            {
                "type": "no_actor_action",
                "task_id": "task-turn-completed-abcdef123456",
                "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
            },
        )

        self.assertEqual(result, {"action": "no_actor_action", "task_id": "task-turn-completed-abcdef123456"})

    def test_render_parent_frame_is_task_sys_scoped(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertIn("task_sys.parent_frame", text)
        self.assertIn("task-user-input-abcdef123456", text)
        self.assertIn("Task Sys source:", text)
        self.assertIn("Parent handoff params:", text)
        self.assertIn("Draft the brief in parent.", text)
        self.assertNotIn("[MESSAGE NEEDS PARENT]", text)
        self.assertNotIn("[TRACK COMMENT", text)

    def test_render_checkpoint_frame_is_task_sys_scoped_without_legacy_prompt(self) -> None:
        text = self.module.render_checkpoint_frame(self._checkpoint_instruction()["frame"])

        self.assertIn("task_sys.checkpoint", text)
        self.assertIn("task-turn-completed-abcdef123456", text)
        self.assertIn("checkpoint_update", text)
        self.assertIn("Do not recommend", text)
        self.assertNotIn("[TASK CHECKPOINT]", text)
        self.assertNotIn("task.checkout finish", text)

    def test_execute_submit_parent_uses_instruction_frame_without_interrupt(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_submit = self.module.launcher_submit_turn.submit_turn
        original_interrupt = self.module.app_server.interrupt_turn

        def fake_submit_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "submit_turn", **kwargs})
            return {"turn_id": "turn-parent-1"}

        def fake_interrupt_turn(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("submit_parent must not interrupt")

        self.addCleanup(setattr, self.module.launcher_submit_turn, "submit_turn", original_submit)
        self.addCleanup(setattr, self.module.app_server, "interrupt_turn", original_interrupt)
        self.module.launcher_submit_turn.submit_turn = fake_submit_turn
        self.module.app_server.interrupt_turn = fake_interrupt_turn

        result = self.module.execute_instruction(context, self._parent_instruction())

        self.assertEqual(result["action"], "submit_parent")
        self.assertEqual(result["turn_id"], "turn-parent-1")
        self.assertEqual(result["task_id"], "task-user-input-abcdef123456")
        self.assertEqual([call["helper"] for call in calls], ["submit_turn"])
        self.assertEqual(calls[0]["thread_id"], "thr-main")
        self.assertIn("task_sys.parent_frame", calls[0]["text"])
        self.assertIn("task-user-input-abcdef123456", calls[0]["text"])

    def test_execute_submit_parent_renders_checkpoint_frame(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_submit = self.module.launcher_submit_turn.submit_turn

        def fake_submit_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "submit_turn", **kwargs})
            return {"turn_id": "turn-checkpoint-1"}

        self.addCleanup(setattr, self.module.launcher_submit_turn, "submit_turn", original_submit)
        self.module.launcher_submit_turn.submit_turn = fake_submit_turn

        result = self.module.execute_instruction(context, self._checkpoint_instruction())

        self.assertEqual(result["action"], "submit_parent")
        self.assertEqual(result["turn_id"], "turn-checkpoint-1")
        self.assertEqual(result["task_id"], "task-turn-completed-abcdef123456")
        self.assertIn("task_sys.checkpoint", calls[0]["text"])
        self.assertIn("checkpoint_update", calls[0]["text"])
        self.assertNotIn("[TASK CHECKPOINT]", calls[0]["text"])

    def test_execute_interrupt_submit_parent_interrupts_before_submit(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_submit = self.module.launcher_submit_turn.submit_turn
        original_interrupt = self.module.app_server.interrupt_turn

        def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, Any]:
            calls.append({"helper": "interrupt_turn", "socket_path": socket_path, "thread_id": thread_id})
            return {"turn_id": "turn-active-1"}

        def fake_submit_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "submit_turn", **kwargs})
            return {"turn_id": "turn-parent-2"}

        self.addCleanup(setattr, self.module.launcher_submit_turn, "submit_turn", original_submit)
        self.addCleanup(setattr, self.module.app_server, "interrupt_turn", original_interrupt)
        self.module.launcher_submit_turn.submit_turn = fake_submit_turn
        self.module.app_server.interrupt_turn = fake_interrupt_turn

        result = self.module.execute_instruction(context, self._parent_instruction(interrupt=True))

        self.assertEqual(result["action"], "interrupt_submit_parent")
        self.assertEqual(result["turn_id"], "turn-parent-2")
        self.assertEqual(result["interrupted_turn_id"], "turn-active-1")
        self.assertEqual([call["helper"] for call in calls], ["interrupt_turn", "submit_turn"])
        self.assertEqual(calls[0]["thread_id"], "thr-main")
        self.assertIn("task_sys.parent_frame", calls[1]["text"])


if __name__ == "__main__":
    unittest.main()
