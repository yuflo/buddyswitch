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
from env.domain import task_sys  # noqa: E402

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

    def _ingested_instruction(self) -> tuple[str, dict[str, Any]]:
        result = task_sys.ingest(
            {
                "source": {"type": "user.input", "ref": {"id": "input-1", "surface": "cli"}},
                "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
                "context": {"text": "Draft brief"},
            }
        )
        return str(result["task_id"]), dict(result["instruction"])

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
        self.assertIn("Core policy: decide by required resources.", text)
        self.assertIn("Allowed side resources:", text)
        self.assertIn("Forbidden side resources:", text)
        self.assertIn("message.send(reply_to=source_message_id", text)
        self.assertIn("message.mark(message_id=source_message_id, disposition=absorbed)", text)
        self.assertIn("Do not call task_sys.need_parent merely because a user-facing reply is needed.", text)
        self.assertIn("Track shared state, including comments", text)
        self.assertIn("browser session, web search, webpage reading, evidence gathering, or research loops", text)
        self.assertIn("source files, git, config, dependencies, tests, builds, app runtime, or workspace state", text)
        self.assertIn("artifacts, evidence, durable deliverables", text)
        self.assertNotIn("checkpoint", text.lower())
        self.assertNotIn("checkpoint_update", text)
        self.assertNotIn("no_actor_action", text)
        self.assertIn("Allowed frame completion operations:", text)
        stale_side_result = "Task Sys side " + "result"
        self.assertNotIn(stale_side_result, text)
        self.assertNotIn("[IM MESSAGE " + "TRIAGE]", text)
        self.assertNotIn("[TRACK COMMENT " + "TRIAGE]", text)
        self.assertNotIn("submit parent", text.lower())
        self.assertNotIn("side_" + "interrupt", text)

    def test_execute_start_side_instruction_uses_explicit_dispatch_stages(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_thread_fork = self.module.app_server.thread_fork
        original_thread_inject_items = self.module.app_server.thread_inject_items
        original_input_turn = self.module.app_server.input_turn
        original_side_start = self.module.app_server.side_start

        def fake_thread_fork(socket_path: Path, parent_thread_id: str, **kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "thread_fork", "socket_path": socket_path, "parent_thread_id": parent_thread_id, **kwargs})
            return {"thread": {"id": "thr-side-1"}}

        def fake_thread_inject_items(socket_path: Path, thread_id: str, items: list[dict[str, object]]) -> dict[str, Any]:
            calls.append({"helper": "thread_inject_items", "socket_path": socket_path, "thread_id": thread_id, "items": items})
            return {"ok": True}

        def fake_input_turn(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, Any]:
            calls.append(
                {
                    "helper": "input_turn",
                    "socket_path": socket_path,
                    "thread_id": thread_id,
                    "text": text,
                    "permissions": permissions,
                }
            )
            return {"action": "start", "turn_id": "turn-side-1"}

        def fake_side_start(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("Task Sys runtime must own explicit side dispatch stages")

        self.addCleanup(setattr, self.module.app_server, "thread_fork", original_thread_fork)
        self.addCleanup(setattr, self.module.app_server, "thread_inject_items", original_thread_inject_items)
        self.addCleanup(setattr, self.module.app_server, "side_start", original_side_start)
        self.addCleanup(setattr, self.module.app_server, "input_turn", original_input_turn)
        self.module.app_server.thread_fork = fake_thread_fork
        self.module.app_server.thread_inject_items = fake_thread_inject_items
        self.module.app_server.input_turn = fake_input_turn
        self.module.app_server.side_start = fake_side_start

        result = self.module.execute_instruction(context, self._instruction())

        self.assertEqual(result["action"], "start_side")
        self.assertEqual(result["side_thread_id"], "thr-side-1")
        self.assertEqual(result["turn_id"], "turn-side-1")
        self.assertEqual(result["stage"], "side_turn_started")
        self.assertEqual([call["helper"] for call in calls], ["thread_fork", "thread_inject_items", "input_turn"])
        text = calls[2]["text"]
        self.assertIn("task_sys.side_frame", text)
        self.assertIn("task_sys.close", text)
        self.assertIn("task_sys.need_parent", text)
        self.assertEqual(calls[0]["parent_thread_id"], "thr-main")
        self.assertEqual(calls[1]["thread_id"], "thr-side-1")
        self.assertEqual(calls[2]["thread_id"], "thr-side-1")

        instance_payload = json.loads(context.instance_json.read_text(encoding="utf-8"))
        self.assertEqual(instance_payload["side_threads"][0]["thread_id"], "thr-side-1")

    def test_execute_start_side_ignores_stale_open_row_and_creates_task_bound_lease(self) -> None:
        context = self._context()
        payload = json.loads(context.instance_json.read_text(encoding="utf-8"))
        payload["side_threads"] = [
            {
                "thread_id": "thr-stale",
                "parent_thread_id": "thr-main",
                "status": "open",
                "created_at": "2026-06-30T00:00:00Z",
                "updated_at": "2026-06-30T00:00:00Z",
            }
        ]
        context.instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        calls: list[dict[str, Any]] = []
        original_thread_fork = self.module.app_server.thread_fork
        original_thread_inject_items = self.module.app_server.thread_inject_items
        original_input_turn = self.module.app_server.input_turn
        original_side_start = self.module.app_server.side_start

        def fake_thread_fork(socket_path: Path, parent_thread_id: str, **kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "thread_fork", "socket_path": socket_path, "parent_thread_id": parent_thread_id, **kwargs})
            return {"thread": {"id": "thr-side-fresh"}}

        def fake_thread_inject_items(socket_path: Path, thread_id: str, items: list[dict[str, object]]) -> dict[str, Any]:
            calls.append({"helper": "thread_inject_items", "socket_path": socket_path, "thread_id": thread_id, "items": items})
            return {"ok": True}

        def fake_input_turn(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, Any]:
            calls.append({"helper": "input_turn", "socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
            return {"action": "start", "turn_id": "turn-side-fresh"}

        def fake_side_start(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("Task Sys runtime must not use the old opaque side_start helper")

        self.addCleanup(setattr, self.module.app_server, "thread_fork", original_thread_fork)
        self.addCleanup(setattr, self.module.app_server, "thread_inject_items", original_thread_inject_items)
        self.addCleanup(setattr, self.module.app_server, "side_start", original_side_start)
        self.addCleanup(setattr, self.module.app_server, "input_turn", original_input_turn)
        self.module.app_server.thread_fork = fake_thread_fork
        self.module.app_server.thread_inject_items = fake_thread_inject_items
        self.module.app_server.input_turn = fake_input_turn
        self.module.app_server.side_start = fake_side_start

        result = self.module.execute_instruction(context, self._instruction())

        self.assertEqual(result["action"], "start_side")
        self.assertEqual(result["side_thread_id"], "thr-side-fresh")
        self.assertEqual([call["helper"] for call in calls], ["thread_fork", "thread_inject_items", "input_turn"])
        instance_payload = json.loads(context.instance_json.read_text(encoding="utf-8"))
        rows = instance_payload["side_threads"]
        self.assertEqual([row["thread_id"] for row in rows], ["thr-stale", "thr-side-fresh"])
        self.assertEqual(rows[1]["task_id"], "task-user-input-abcdef123456")
        self.assertEqual(rows[1]["purpose"], "task_sys.side_frame")

    def test_execute_start_side_creates_fresh_side_thread_for_each_task_sys_frame(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_thread_fork = self.module.app_server.thread_fork
        original_thread_inject_items = self.module.app_server.thread_inject_items
        original_input_turn = self.module.app_server.input_turn
        original_side_start = self.module.app_server.side_start

        def fake_thread_fork(socket_path: Path, parent_thread_id: str, **kwargs: Any) -> dict[str, Any]:
            next_index = 1 + sum(1 for call in calls if call["helper"] == "thread_fork")
            calls.append({"helper": "thread_fork", "socket_path": socket_path, "parent_thread_id": parent_thread_id, **kwargs})
            return {"thread": {"id": f"thr-side-{next_index}"}}

        def fake_thread_inject_items(socket_path: Path, thread_id: str, items: list[dict[str, object]]) -> dict[str, Any]:
            calls.append({"helper": "thread_inject_items", "socket_path": socket_path, "thread_id": thread_id, "items": items})
            return {"ok": True}

        def fake_input_turn(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, Any]:
            calls.append({"helper": "input_turn", "socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
            return {
                "action": "start",
                "turn_id": thread_id.replace("thr-side-", "turn-side-"),
            }

        def fake_side_start(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("Task Sys runtime must not use the old opaque side_start helper")

        self.addCleanup(setattr, self.module.app_server, "thread_fork", original_thread_fork)
        self.addCleanup(setattr, self.module.app_server, "thread_inject_items", original_thread_inject_items)
        self.addCleanup(setattr, self.module.app_server, "side_start", original_side_start)
        self.addCleanup(setattr, self.module.app_server, "input_turn", original_input_turn)
        self.module.app_server.thread_fork = fake_thread_fork
        self.module.app_server.thread_inject_items = fake_thread_inject_items
        self.module.app_server.input_turn = fake_input_turn
        self.module.app_server.side_start = fake_side_start

        first = self.module.execute_instruction(context, self._instruction())
        second_instruction = self._instruction()
        second_instruction["task_id"] = "task-user-input-second123"
        second_instruction["frame"]["task_id"] = "task-user-input-second123"
        second = self.module.execute_instruction(context, second_instruction)

        self.assertEqual(first["side_thread_id"], "thr-side-1")
        self.assertEqual(second["side_thread_id"], "thr-side-2")
        self.assertEqual(
            [call["helper"] for call in calls],
            ["thread_fork", "thread_inject_items", "input_turn", "thread_fork", "thread_inject_items", "input_turn"],
        )
        instance_payload = json.loads(context.instance_json.read_text(encoding="utf-8"))
        rows = instance_payload["side_threads"]
        self.assertEqual([row["thread_id"] for row in rows], ["thr-side-1", "thr-side-2"])
        self.assertEqual([row["task_id"] for row in rows], ["task-user-input-abcdef123456", "task-user-input-second123"])
        self.assertEqual({row["purpose"] for row in rows}, {"task_sys.side_frame"})

    def test_execute_start_side_retries_fork_failure_with_fresh_attempt(self) -> None:
        context = self._context()
        task_id, instruction = self._ingested_instruction()
        calls: list[dict[str, Any]] = []
        original_thread_fork = self.module.app_server.thread_fork
        original_thread_inject_items = self.module.app_server.thread_inject_items
        original_input_turn = self.module.app_server.input_turn
        original_side_close = self.module.app_server.side_close
        original_side_start = self.module.app_server.side_start

        def fake_thread_fork(socket_path: Path, parent_thread_id: str, **kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "thread_fork", "socket_path": socket_path, "parent_thread_id": parent_thread_id, **kwargs})
            if len([call for call in calls if call["helper"] == "thread_fork"]) == 1:
                raise self.module.app_server.AppServerUnavailableError("temporary fork failure")
            return {"thread": {"id": "thr-side-retry"}}

        def fake_thread_inject_items(socket_path: Path, thread_id: str, items: list[dict[str, object]]) -> dict[str, Any]:
            calls.append({"helper": "thread_inject_items", "socket_path": socket_path, "thread_id": thread_id, "items": items})
            return {"ok": True}

        def fake_input_turn(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, Any]:
            calls.append({"helper": "input_turn", "socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
            return {"action": "start", "turn_id": "turn-side-retry"}

        def fake_side_close(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("fork failure has no side thread to clean up")

        def fake_side_start(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("Task Sys runtime must not use the old opaque side_start helper")

        self.addCleanup(setattr, self.module.app_server, "thread_fork", original_thread_fork)
        self.addCleanup(setattr, self.module.app_server, "thread_inject_items", original_thread_inject_items)
        self.addCleanup(setattr, self.module.app_server, "input_turn", original_input_turn)
        self.addCleanup(setattr, self.module.app_server, "side_close", original_side_close)
        self.addCleanup(setattr, self.module.app_server, "side_start", original_side_start)
        self.module.app_server.thread_fork = fake_thread_fork
        self.module.app_server.thread_inject_items = fake_thread_inject_items
        self.module.app_server.input_turn = fake_input_turn
        self.module.app_server.side_close = fake_side_close
        self.module.app_server.side_start = fake_side_start

        result = self.module.execute_instruction(context, instruction)

        self.assertEqual(result["action"], "start_side")
        self.assertEqual(result["task_id"], task_id)
        self.assertEqual(result["side_thread_id"], "thr-side-retry")
        self.assertEqual(result["turn_id"], "turn-side-retry")
        self.assertEqual(result["stage"], "side_turn_started")
        self.assertEqual([attempt["stage"] for attempt in result["attempts"]], ["side_fork", "side_turn_started"])
        self.assertEqual([call["helper"] for call in calls], ["thread_fork", "thread_fork", "thread_inject_items", "input_turn"])

    def test_execute_start_side_records_runtime_failed_after_bounded_pre_turn_input_failures(self) -> None:
        context = self._context()
        task_id, instruction = self._ingested_instruction()
        calls: list[dict[str, Any]] = []
        original_thread_fork = self.module.app_server.thread_fork
        original_thread_inject_items = self.module.app_server.thread_inject_items
        original_input_turn = self.module.app_server.input_turn
        original_side_close = self.module.app_server.side_close
        original_side_start = self.module.app_server.side_start

        def fake_thread_fork(socket_path: Path, parent_thread_id: str, **kwargs: Any) -> dict[str, Any]:
            next_index = 1 + sum(1 for call in calls if call["helper"] == "thread_fork")
            calls.append({"helper": "thread_fork", "socket_path": socket_path, "parent_thread_id": parent_thread_id, **kwargs})
            return {"thread": {"id": f"thr-side-failed-{next_index}"}}

        def fake_thread_inject_items(socket_path: Path, thread_id: str, items: list[dict[str, object]]) -> dict[str, Any]:
            calls.append({"helper": "thread_inject_items", "socket_path": socket_path, "thread_id": thread_id, "items": items})
            return {"ok": True}

        def fake_input_turn(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, Any]:
            calls.append({"helper": "input_turn", "socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
            raise self.module.app_server.AppServerUnavailableError(f"input failed for {thread_id}")

        def fake_side_close(socket_path: Path, side_thread_id: str) -> dict[str, Any]:
            calls.append({"helper": "side_close", "socket_path": socket_path, "side_thread_id": side_thread_id})
            if side_thread_id == "thr-side-failed-2":
                raise self.module.app_server.AppServerUnavailableError("side already gone")
            return {"ok": True}

        def fake_side_start(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("Task Sys runtime must not use the old opaque side_start helper")

        self.addCleanup(setattr, self.module.app_server, "thread_fork", original_thread_fork)
        self.addCleanup(setattr, self.module.app_server, "thread_inject_items", original_thread_inject_items)
        self.addCleanup(setattr, self.module.app_server, "input_turn", original_input_turn)
        self.addCleanup(setattr, self.module.app_server, "side_close", original_side_close)
        self.addCleanup(setattr, self.module.app_server, "side_start", original_side_start)
        self.module.app_server.thread_fork = fake_thread_fork
        self.module.app_server.thread_inject_items = fake_thread_inject_items
        self.module.app_server.input_turn = fake_input_turn
        self.module.app_server.side_close = fake_side_close
        self.module.app_server.side_start = fake_side_start

        result = self.module.execute_instruction(context, instruction)

        self.assertEqual(result["action"], "start_side")
        self.assertEqual(result["task_id"], task_id)
        self.assertEqual(result["status"], "runtime_failed")
        self.assertEqual(result["stage"], "side_input")
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual([attempt["side_thread_id"] for attempt in result["attempts"]], ["thr-side-failed-1", "thr-side-failed-2"])
        self.assertTrue(all(attempt["cleanup"]["registry_unregistered"] for attempt in result["attempts"]))
        self.assertEqual(result["attempts"][1]["cleanup"]["physical_close_ok"], False)
        instance_payload = json.loads(context.instance_json.read_text(encoding="utf-8"))
        self.assertEqual(instance_payload["side_threads"], [])
        record = task_sys.get_task(task_id)
        self.assertEqual(record["status"], "runtime_failed")
        self.assertIsNone(record["active_processor"])
        self.assertEqual(record["failure_result"]["stage"], "side_input")
        self.assertEqual(record["failure_result"]["attempts"], 2)
        self.assertEqual(record["failure_result"]["last_side_thread_id"], "thr-side-failed-2")
        self.assertEqual(record["failure_result"]["cleanup"]["registry_unregistered"], True)
        self.assertEqual(
            [call["helper"] for call in calls],
            [
                "thread_fork",
                "thread_inject_items",
                "input_turn",
                "side_close",
                "thread_fork",
                "thread_inject_items",
                "input_turn",
                "side_close",
            ],
        )

    def test_execute_start_side_does_not_cleanup_or_retry_after_turn_id_exists(self) -> None:
        context = self._context()
        task_id, instruction = self._ingested_instruction()
        calls: list[dict[str, Any]] = []
        original_thread_fork = self.module.app_server.thread_fork
        original_thread_inject_items = self.module.app_server.thread_inject_items
        original_input_turn = self.module.app_server.input_turn
        original_side_close = self.module.app_server.side_close
        original_side_start = self.module.app_server.side_start

        def fake_thread_fork(socket_path: Path, parent_thread_id: str, **kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "thread_fork", "socket_path": socket_path, "parent_thread_id": parent_thread_id, **kwargs})
            return {"thread": {"id": "thr-side-started"}}

        def fake_thread_inject_items(socket_path: Path, thread_id: str, items: list[dict[str, object]]) -> dict[str, Any]:
            calls.append({"helper": "thread_inject_items", "socket_path": socket_path, "thread_id": thread_id, "items": items})
            return {"ok": True}

        def fake_input_turn(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, Any]:
            calls.append({"helper": "input_turn", "socket_path": socket_path, "thread_id": thread_id, "text": text, "permissions": permissions})
            return {"action": "start", "turn": {"id": "turn-side-started"}}

        def fake_side_close(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("runtime must not cleanup a side thread after turn_id exists")

        def fake_side_start(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("Task Sys runtime must not use the old opaque side_start helper")

        self.addCleanup(setattr, self.module.app_server, "thread_fork", original_thread_fork)
        self.addCleanup(setattr, self.module.app_server, "thread_inject_items", original_thread_inject_items)
        self.addCleanup(setattr, self.module.app_server, "input_turn", original_input_turn)
        self.addCleanup(setattr, self.module.app_server, "side_close", original_side_close)
        self.addCleanup(setattr, self.module.app_server, "side_start", original_side_start)
        self.module.app_server.thread_fork = fake_thread_fork
        self.module.app_server.thread_inject_items = fake_thread_inject_items
        self.module.app_server.input_turn = fake_input_turn
        self.module.app_server.side_close = fake_side_close
        self.module.app_server.side_start = fake_side_start

        result = self.module.execute_instruction(context, instruction)

        self.assertEqual(result["action"], "start_side")
        self.assertEqual(result["task_id"], task_id)
        self.assertEqual(result["turn_id"], "turn-side-started")
        self.assertEqual(result["stage"], "side_turn_started")
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual([call["helper"] for call in calls], ["thread_fork", "thread_inject_items", "input_turn"])
        self.assertEqual(task_sys.get_task(task_id)["status"], "side_processing")

    def test_cleanup_task_sys_side_lease_unregisters_even_when_physical_close_fails(self) -> None:
        context = self._context()
        self.module.side_thread_registry.register_side_thread(
            context.instance_json,
            actor_id=context.actor_id,
            parent_thread_id=context.main_thread_id,
            side_thread_id="thr-side-cleanup",
            task_id="task-user-input-cleanup123",
            purpose="task_sys.side_frame",
            now=lambda: "2026-06-30T00:00:00Z",
        )
        original_side_close = self.module.app_server.side_close
        calls: list[dict[str, Any]] = []

        def fake_side_close(socket_path: Path, side_thread_id: str) -> dict[str, Any]:
            calls.append({"socket_path": socket_path, "side_thread_id": side_thread_id})
            raise self.module.app_server.AppServerUnavailableError("thread not loaded")

        self.addCleanup(setattr, self.module.app_server, "side_close", original_side_close)
        self.module.app_server.side_close = fake_side_close

        result = self.module.cleanup_task_sys_side_lease(context, "task-user-input-cleanup123")

        self.assertEqual(result["side_thread_id"], "thr-side-cleanup")
        self.assertEqual(result["physical_close_ok"], False)
        self.assertEqual(result["physical_close_error"], "thread not loaded")
        self.assertEqual(result["registry_unregistered"], True)
        self.assertEqual(calls, [{"socket_path": context.socket_path, "side_thread_id": "thr-side-cleanup"}])
        instance_payload = json.loads(context.instance_json.read_text(encoding="utf-8"))
        self.assertEqual(instance_payload["side_threads"], [])

    def test_execute_start_side_rejects_wrong_actor_target(self) -> None:
        instruction = self._instruction()
        instruction["actor_target"] = {"actor_id": "act-other", "role_id": "dev"}

        with self.assertRaisesRegex(PermissionError, "wrong target actor"):
            self.module.execute_instruction(self._context(), instruction)

    def test_execute_no_actor_action_is_not_supported(self) -> None:
        context = self._context()
        original_side_start = self.module.app_server.side_start

        def fake_side_start(**_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("unsupported no_actor_action must not start side")

        self.addCleanup(setattr, self.module.app_server, "side_start", original_side_start)
        self.module.app_server.side_start = fake_side_start

        with self.assertRaisesRegex(ValueError, "unsupported Task Sys runtime instruction"):
            self.module.execute_instruction(
                context,
                {
                    "type": "no_actor_action",
                    "task_id": "task-turn-completed-abcdef123456",
                    "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
                },
            )

    def test_render_parent_frame_is_task_sys_scoped(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertIn("task_sys.parent_frame", text)
        self.assertIn("task-user-input-abcdef123456", text)
        self.assertIn("Task Sys source:", text)
        self.assertIn("Parent handoff params:", text)
        self.assertIn("Draft the brief in parent.", text)
        self.assertNotIn("[MESSAGE NEEDS " + "PARENT]", text)
        self.assertNotIn("[TRACK COMMENT", text)

    def test_render_parent_frame_requires_task_sys_close(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertIn("When the source task is complete, call task_sys.close(task_id=..., summary=...).", text)
        self.assertIn("Do not rely on parent turn completion to close this Task Sys task.", text)
        self.assertIn("Allowed parent frame operation:", text)
        self.assertIn("- task_sys.close(task_id=..., summary=...)", text)

    def test_render_parent_frame_names_im_closure_order(self) -> None:
        instruction = self._parent_instruction()
        instruction["frame"]["source"] = {"type": "im.message.created", "ref": {"message_id": "msg-1"}}

        text = self.module.render_parent_frame(instruction["frame"])

        self.assertIn("For an IM source message:", text)
        self.assertIn("first call message.send(reply_to=source_message_id, content=...)", text)
        self.assertIn("first call message.mark(message_id=source_message_id, disposition=absorbed)", text)
        self.assertIn("Only after the source-bound IM action succeeds, call task_sys.close.", text)
        self.assertIn("If the IM action succeeds but task_sys.close fails, retry task_sys.close and do not send a duplicate reply.", text)

    def test_render_parent_frame_does_not_mention_checkpoint_update(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertNotIn("checkpoint", text.lower())
        self.assertNotIn("checkpoint_update", text)

    def test_render_side_frame_no_longer_calls_close_a_side_result(self) -> None:
        text = self.module.render_side_frame(self._instruction()["frame"])

        self.assertIn("Allowed frame completion operations:", text)
        self.assertIn("task_sys.close(task_id=..., summary=...) when the task is completed in side.", text)
        stale_side_result = "Task Sys side " + "result"
        self.assertNotIn(stale_side_result, text)
        self.assertNotIn("side result:", text.lower())

    def test_submit_parent_frame_rejects_checkpoint_frame(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported submit_parent frame kind"):
            self.module.render_submit_parent_frame(self._checkpoint_instruction()["frame"])

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

    def test_execute_submit_parent_rejects_checkpoint_frame(self) -> None:
        context = self._context()
        original_submit = self.module.launcher_submit_turn.submit_turn

        def fake_submit_turn(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            return {"turn_id": "turn-checkpoint-1"}

        self.addCleanup(setattr, self.module.launcher_submit_turn, "submit_turn", original_submit)
        self.module.launcher_submit_turn.submit_turn = fake_submit_turn

        with self.assertRaisesRegex(ValueError, "unsupported submit_parent frame kind"):
            self.module.execute_instruction(context, self._checkpoint_instruction())

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

    def test_execute_interrupt_submit_parent_idle_parent_submits_without_interrupted_turn(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_submit = self.module.launcher_submit_turn.submit_turn
        original_interrupt = self.module.app_server.interrupt_turn

        def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, Any]:
            calls.append({"helper": "interrupt_turn", "socket_path": socket_path, "thread_id": thread_id})
            raise self.module.app_server.AppServerUnavailableError("thread thr-main has no active in-progress turn")

        def fake_submit_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "submit_turn", **kwargs})
            return {"turn_id": "turn-parent-idle"}

        self.addCleanup(setattr, self.module.launcher_submit_turn, "submit_turn", original_submit)
        self.addCleanup(setattr, self.module.app_server, "interrupt_turn", original_interrupt)
        self.module.launcher_submit_turn.submit_turn = fake_submit_turn
        self.module.app_server.interrupt_turn = fake_interrupt_turn

        result = self.module.execute_instruction(context, self._parent_instruction(interrupt=True))

        self.assertEqual(result["action"], "interrupt_submit_parent")
        self.assertEqual(result["turn_id"], "turn-parent-idle")
        self.assertNotIn("interrupted_turn_id", result)
        self.assertEqual([call["helper"] for call in calls], ["interrupt_turn", "submit_turn"])
        self.assertIn("task_sys.parent_frame", calls[1]["text"])

    def test_execute_interrupt_submit_parent_no_active_turn_race_submits_without_interrupted_turn(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_submit = self.module.launcher_submit_turn.submit_turn
        original_interrupt = self.module.app_server.interrupt_turn

        def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, Any]:
            calls.append({"helper": "interrupt_turn", "socket_path": socket_path, "thread_id": thread_id})
            raise self.module.app_server.AppServerUnavailableError(
                "thread thr-main is active but no in-progress turn was found"
            )

        def fake_submit_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "submit_turn", **kwargs})
            return {"turn_id": "turn-parent-race"}

        self.addCleanup(setattr, self.module.launcher_submit_turn, "submit_turn", original_submit)
        self.addCleanup(setattr, self.module.app_server, "interrupt_turn", original_interrupt)
        self.module.launcher_submit_turn.submit_turn = fake_submit_turn
        self.module.app_server.interrupt_turn = fake_interrupt_turn

        result = self.module.execute_instruction(context, self._parent_instruction(interrupt=True))

        self.assertEqual(result["action"], "interrupt_submit_parent")
        self.assertEqual(result["turn_id"], "turn-parent-race")
        self.assertNotIn("interrupted_turn_id", result)
        self.assertEqual([call["helper"] for call in calls], ["interrupt_turn", "submit_turn"])


if __name__ == "__main__":
    unittest.main()
