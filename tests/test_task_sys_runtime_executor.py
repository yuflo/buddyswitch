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
import actor_capability  # noqa: E402

TASK_SYS_RUNTIME_PATH = ROOT / "tools" / "launcher" / ("task_sys_" + "runtime.py")
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

    def _im_instruction(self) -> dict[str, Any]:
        instruction = self._instruction()
        instruction["type"] = "start_side"
        instruction["task_id"] = "task-im-message-created-abcdef123456"
        frame = instruction["frame"]
        frame["task_id"] = "task-im-message-created-abcdef123456"
        frame["source"] = {
            "type": "im.message.created",
            "ref": {
                "message_id": "msg-source-1",
                "conversation_id": "conv-source-1",
                "event_id": "imev-source-1",
            },
        }
        frame["context"] = {
            "message_id": "msg-source-1",
            "conversation_id": "conv-source-1",
            "event_id": "imev-source-1",
        }
        return instruction

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
                "task_desc": "Draft brief",
                "task_relation": {"kind": "after", "target_task_id": "task-user-input-prior123"},
                "execution_handoff": {
                    "parent_frame_context": {
                        "next": "Draft the brief in parent.",
                        "task_desc": "Draft brief",
                        "task_relation": {"kind": "after", "target_task_id": "task-user-input-prior123"},
                    },
                    "interrupt": interrupt,
                    "ordering": {"after": "task-user-input-prior123"},
                    "side_thread_id": "thr-side-1",
                    "cleanup": {},
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
        self.assertIn("task_desc", text)
        self.assertIn("task_relation", text)
        self.assertIn("task_sys.update_task_analysis", text)
        self.assertIn("task_sys.list(status=all)", text)
        self.assertIn("task_sys.get(task_id=...)", text)
        self.assertIn("task_relation.kind", text)
        self.assertIn("task_sys.close", text)
        self.assertIn("task_sys.need_parent", text)
        self.assertIn("Core policy: decide by required resources.", text)
        self.assertIn("Allowed side resources:", text)
        self.assertIn("Forbidden side resources:", text)
        self.assertNotIn("Current-source IM " + "closure", text)
        self.assertNotIn("Do not start a new IM " + "conversation", text)
        self.assertNotIn("Do not send to target_identity_id " + "from side", text)
        self.assertNotIn("source-" + "bound", text)
        self.assertIn("Track shared state, including comments", text)
        self.assertIn("browser session, web search, webpage reading, evidence gathering, or research loops", text)
        self.assertIn("source files, git, config, dependencies, tests, builds, app runtime, or workspace state", text)
        self.assertIn("artifacts, evidence, durable deliverables", text)
        self.assertNotIn("checkpoint", text.lower())
        self.assertNotIn("checkpoint_update", text)
        self.assertNotIn("no_actor_action", text)
        self.assertIn("Allowed frame completion operations:", text)
        self.assertIn("Allowed relation-analysis operation:", text)
        self.assertNotIn("params={parent_frame_context, relation", text)
        stale_side_result = "Task Sys side " + "result"
        self.assertNotIn(stale_side_result, text)
        self.assertNotIn("[IM MESSAGE " + "TRIAGE]", text)
        self.assertNotIn("[TRACK COMMENT " + "TRIAGE]", text)
        self.assertNotIn("submit parent", text.lower())
        self.assertNotIn("side_" + "interrupt", text)

    def test_render_side_frame_for_im_source_allows_full_message_tool_surface(self) -> None:
        text = self.module.render_side_frame(self._im_instruction()["frame"])

        self.assertIn("For an IM source message:", text)
        self.assertIn("message.contacts", text)
        self.assertIn("message.list", text)
        self.assertIn("message.get", text)
        self.assertIn("message.conversation", text)
        self.assertIn("message.send(reply_to=source_message_id, content=...)", text)
        self.assertIn("message.send(target_identity_id=..., content=...)", text)
        self.assertIn("message.mark(message_id=..., disposition=absorbed)", text)
        self.assertIn("task_sys.close(task_id=..., summary=...)", text)
        self.assertIn("task_sys.need_parent", text)
        self.assertNotIn("Do not start a new IM " + "conversation", text)
        self.assertNotIn("Do not send to target_identity_id " + "from side", text)
        self.assertNotIn("new " + "outbound " + "communication", text)
        self.assertNotIn("source-" + "bound", text)

    def test_im_message_frames_share_the_same_message_capability_contract(self) -> None:
        side_text = self.module.render_side_frame(self._im_instruction()["frame"])
        parent_instruction = self._parent_instruction()
        parent_instruction["frame"]["source"] = self._im_instruction()["frame"]["source"]
        parent_text = self.module.render_parent_frame(parent_instruction["frame"])

        required_tokens = (
            "message.contacts",
            "message.list",
            "message.get",
            "message.conversation",
            "message.send(reply_to=source_message_id, content=...)",
            "message.send(target_identity_id=..., content=...)",
            "message.mark(message_id=..., disposition=absorbed)",
        )
        for token in required_tokens:
            with self.subTest(surface="side", token=token):
                self.assertIn(token, side_text)
            with self.subTest(surface="parent", token=token):
                self.assertIn(token, parent_text)

    def test_execute_start_side_instruction_delegates_to_actor_side_boundary(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_start = self.module.actor_side_thread.start_actor_side_thread

        def fake_start_side_thread(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {
                "action": "start",
                "purpose": "task_sys.side_frame",
                "parent_thread_id": kwargs["parent_thread_id"],
                "side_thread_id": "thr-side-1",
                "thread_action": "start",
                "turn_id": "turn-side-1",
                "lease_registered": True,
            }

        self.addCleanup(setattr, self.module.actor_side_thread, "start_actor_side_thread", original_start)
        self.module.actor_side_thread.start_actor_side_thread = fake_start_side_thread

        result = self.module.execute_instruction(context, self._instruction())

        self.assertEqual(result["action"], "start_side")
        self.assertEqual(result["side_thread_id"], "thr-side-1")
        self.assertEqual(result["turn_id"], "turn-side-1")
        self.assertEqual(result["stage"], "side_started")
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["socket_path"], context.socket_path)
        self.assertEqual(call["instance_json"], context.instance_json)
        self.assertEqual(call["actor_id"], context.actor_id)
        self.assertEqual(call["parent_thread_id"], context.main_thread_id)
        self.assertEqual(call["purpose"], "task_sys.side_frame")
        self.assertEqual(call["workspace_dir"], context.workspace_dir)
        self.assertEqual(call["shared_project_workspace_dir"], context.project_workspace_dir)
        self.assertEqual(call["permissions"], context.permissions)
        self.assertEqual(call["task_id"], "task-user-input-abcdef123456")
        self.assertNotIn("model", call)
        self.assertNotIn("model_reasoning_effort", call)
        self.assertIn("task_sys.side_frame", call["text"])
        self.assertIn("task_sys.close", call["text"])
        self.assertIn("task_sys.need_parent", call["text"])

    def test_execute_start_side_creates_fresh_lifecycle_call_for_each_task_sys_frame(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_start = self.module.actor_side_thread.start_actor_side_thread

        def fake_start_side_thread(**kwargs: Any) -> dict[str, Any]:
            index = len(calls) + 1
            calls.append(kwargs)
            return {
                "action": "start",
                "purpose": "task_sys.side_frame",
                "parent_thread_id": kwargs["parent_thread_id"],
                "side_thread_id": f"thr-side-{index}",
                "thread_action": "start",
                "turn_id": f"turn-side-{index}",
                "lease_registered": True,
            }

        self.addCleanup(setattr, self.module.actor_side_thread, "start_actor_side_thread", original_start)
        self.module.actor_side_thread.start_actor_side_thread = fake_start_side_thread

        first = self.module.execute_instruction(context, self._instruction())
        second_instruction = self._instruction()
        second_instruction["task_id"] = "task-user-input-second123"
        second_instruction["frame"]["task_id"] = "task-user-input-second123"
        second = self.module.execute_instruction(context, second_instruction)

        self.assertEqual(first["side_thread_id"], "thr-side-1")
        self.assertEqual(second["side_thread_id"], "thr-side-2")
        self.assertEqual([call["task_id"] for call in calls], ["task-user-input-abcdef123456", "task-user-input-second123"])
        self.assertNotEqual(calls[0]["text"], calls[1]["text"])

    def test_execute_start_side_retries_lifecycle_failure_with_fresh_attempt(self) -> None:
        context = self._context()
        task_id, instruction = self._ingested_instruction()
        calls: list[dict[str, Any]] = []
        original_start = self.module.actor_side_thread.start_actor_side_thread

        def fake_start_side_thread(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("temporary lifecycle failure")
            return {
                "action": "start",
                "purpose": "task_sys.side_frame",
                "parent_thread_id": kwargs["parent_thread_id"],
                "side_thread_id": "thr-side-retry",
                "thread_action": "start",
                "turn_id": "turn-side-retry",
                "lease_registered": True,
            }

        self.addCleanup(setattr, self.module.actor_side_thread, "start_actor_side_thread", original_start)
        self.module.actor_side_thread.start_actor_side_thread = fake_start_side_thread

        result = self.module.execute_instruction(context, instruction)

        self.assertEqual(result["action"], "start_side")
        self.assertEqual(result["task_id"], task_id)
        self.assertEqual(result["side_thread_id"], "thr-side-retry")
        self.assertEqual(result["turn_id"], "turn-side-retry")
        self.assertEqual(result["stage"], "side_started")
        self.assertEqual([attempt["stage"] for attempt in result["attempts"]], ["side_lifecycle", "side_started"])
        self.assertEqual(len(calls), 2)

    def test_execute_start_side_records_runtime_failed_after_bounded_lifecycle_failures(self) -> None:
        context = self._context()
        task_id, instruction = self._ingested_instruction()
        calls: list[dict[str, Any]] = []
        original_start = self.module.actor_side_thread.start_actor_side_thread

        def fake_start_side_thread(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            raise RuntimeError(f"side lifecycle failed attempt {len(calls)}")

        self.addCleanup(setattr, self.module.actor_side_thread, "start_actor_side_thread", original_start)
        self.module.actor_side_thread.start_actor_side_thread = fake_start_side_thread

        result = self.module.execute_instruction(context, instruction)

        self.assertEqual(result["action"], "start_side")
        self.assertEqual(result["task_id"], task_id)
        self.assertEqual(result["status"], "runtime_failed")
        self.assertEqual(result["stage"], "side_lifecycle")
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(len(calls), 2)
        record = task_sys.get_task(task_id)
        self.assertEqual(record["status"], "in_progress")
        self.assertNotIn("active_processor", record)
        execution = record["execution"]
        self.assertIsNone(execution["processor"])
        self.assertEqual(execution["result"]["type"], "failure")
        self.assertEqual(execution["result"]["reason"], "runtime_failed")
        self.assertEqual(execution["result"]["stage"], "side_lifecycle")
        self.assertEqual(execution["result"]["attempts"], 2)
        self.assertEqual(result["execution_result"], execution["result"])
        self.assertNotIn("failure_result", result)

    def test_cleanup_side_lease_delegates_to_lifecycle_owner(self) -> None:
        context = self._context()
        original_cleanup = self.module.side_thread_lifecycle.cleanup_task_side_lease
        calls: list[dict[str, Any]] = []

        def fake_cleanup_task_side_lease(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {
                "action": "cleanup",
                "side_thread_id": "thr-side-cleanup",
                "turn_id": "turn-side-cleanup",
                "turn_interrupt_attempted": True,
                "turn_interrupt_ok": False,
                "turn_interrupt_error": "thread not loaded",
                "lease_unregistered": True,
            }

        self.addCleanup(setattr, self.module.side_thread_lifecycle, "cleanup_task_side_lease", original_cleanup)
        self.module.side_thread_lifecycle.cleanup_task_side_lease = fake_cleanup_task_side_lease

        result = self.module.cleanup_side_lease(context, "task-user-input-cleanup123")

        self.assertEqual(result["side_thread_id"], "thr-side-cleanup")
        self.assertEqual(result["turn_interrupt_attempted"], True)
        self.assertEqual(result["turn_interrupt_ok"], False)
        self.assertEqual(result["turn_interrupt_error"], "thread not loaded")
        self.assertEqual(result["lease_unregistered"], True)
        self.assertEqual(
            calls,
            [
                {
                    "socket_path": context.socket_path,
                    "instance_json": context.instance_json,
                    "actor_id": context.actor_id,
                    "parent_thread_id": context.main_thread_id,
                    "task_id": "task-user-input-cleanup123",
                }
            ],
        )

    def test_execute_start_side_rejects_wrong_actor_target(self) -> None:
        instruction = self._instruction()
        instruction["actor_target"] = {"actor_id": "act-other", "role_id": "dev"}

        with self.assertRaisesRegex(PermissionError, "wrong target actor"):
            self.module.execute_instruction(self._context(), instruction)

    def test_execute_no_actor_action_is_not_supported(self) -> None:
        context = self._context()
        original_start = self.module.actor_side_thread.start_actor_side_thread

        def fake_start_side_thread(**_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("unsupported no_actor_action must not start side")

        self.addCleanup(setattr, self.module.actor_side_thread, "start_actor_side_thread", original_start)
        self.module.actor_side_thread.start_actor_side_thread = fake_start_side_thread

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
        self.assertIn("Task desc:", text)
        self.assertIn("Task relation:", text)
        self.assertIn("Execution handoff:", text)
        self.assertIn("Draft the brief in parent.", text)
        self.assertIn("task-user-input-prior123", text)
        self.assertNotIn("Side result:", text)
        self.assertNotIn("Parent handoff params:", text)
        self.assertNotIn("[MESSAGE NEEDS " + "PARENT]", text)
        self.assertNotIn("[TRACK COMMENT", text)

    def test_render_parent_frame_rejects_legacy_handoff_shape(self) -> None:
        instruction = self._parent_instruction()
        frame = instruction["frame"]
        frame.pop("task_desc")
        frame.pop("task_relation")
        frame.pop("execution_handoff")
        frame["side_result"] = {"outcome": "need_parent", "params": {"interrupt": False}}
        frame["parent_handoff_params"] = {"parent_frame_context": {"next": "Draft the brief in parent."}}

        with self.assertRaisesRegex(ValueError, "frame.task_desc"):
            self.module.render_parent_frame(frame)

    def test_render_parent_frame_requires_task_sys_close(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertIn("When the source task is complete, call task_sys.close(task_id=..., summary=...).", text)
        self.assertIn("Do not rely on parent turn completion to close this Task Sys task.", text)
        self.assertIn("Allowed parent frame operations:", text)
        self.assertIn("- task_sys.close(task_id=..., summary=...)", text)

    def test_render_parent_frame_allows_user_input_parent_communication_before_close(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertIn("For a user.input source:", text)
        self.assertIn("message.send(target_identity_id=..., content=...)", text)
        self.assertIn("After required parent work is complete, call task_sys.close.", text)
        self.assertIn("execution_handoff", text)
        self.assertNotIn("parent_handoff_params", text)
        self.assertNotIn("For an IM source message:", text)
        self.assertNotIn("Only after the source-" + "bound IM action " + "succeeds", text)

    def test_render_parent_frame_for_im_source_allows_full_message_tool_surface(self) -> None:
        instruction = self._parent_instruction()
        instruction["frame"]["source"] = {
            "type": "im.message.created",
            "ref": {
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "event_id": "imev-1",
            },
        }

        text = self.module.render_parent_frame(instruction["frame"])

        self.assertIn("For an IM source message:", text)
        self.assertIn("message.contacts", text)
        self.assertIn("message.list", text)
        self.assertIn("message.get", text)
        self.assertIn("message.conversation", text)
        self.assertIn("message.send(reply_to=source_message_id, content=...)", text)
        self.assertIn("message.send(target_identity_id=..., content=...)", text)
        self.assertIn("message.mark(message_id=..., disposition=absorbed)", text)
        self.assertIn("- task_sys.close(task_id=..., summary=...)", text)
        self.assertNotIn("Only after the source-" + "bound IM action " + "succeeds", text)
        self.assertNotIn("source-" + "bound", text)

    def test_render_parent_frame_does_not_mention_checkpoint_update(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertNotIn("checkpoint", text.lower())
        self.assertNotIn("checkpoint_update", text)

    def test_render_side_frame_no_longer_calls_close_a_side_result(self) -> None:
        text = self.module.render_side_frame(self._instruction()["frame"])

        self.assertIn("Allowed frame completion operations:", text)
        self.assertIn("task_sys.close(task_id=..., summary=...) when the task is completed in side.", text)
        self.assertIn("task_sys.update_task_analysis", text)
        stale_side_result = "Task Sys side " + "result"
        self.assertNotIn(stale_side_result, text)
        self.assertNotIn("side result:", text.lower())

    def test_submit_parent_frame_rejects_checkpoint_frame(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported submit_parent frame kind"):
            self.module.render_submit_parent_frame(self._checkpoint_instruction()["frame"])

    def test_execute_submit_parent_uses_instruction_frame_without_interrupt(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_submit = self.module.actor_session.input_actor_turn
        original_interrupt = self.module.app_server.interrupt_turn

        def fake_input_actor_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "input_actor_turn", **kwargs})
            return {"turn_id": "turn-parent-1"}

        def fake_interrupt_turn(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("submit_parent must not interrupt")

        self.addCleanup(setattr, self.module.actor_session, "input_actor_turn", original_submit)
        self.addCleanup(setattr, self.module.app_server, "interrupt_turn", original_interrupt)
        self.module.actor_session.input_actor_turn = fake_input_actor_turn
        self.module.app_server.interrupt_turn = fake_interrupt_turn

        result = self.module.execute_instruction(context, self._parent_instruction())

        self.assertEqual(result["action"], "submit_parent")
        self.assertEqual(result["turn_id"], "turn-parent-1")
        self.assertEqual(result["task_id"], "task-user-input-abcdef123456")
        self.assertEqual([call["helper"] for call in calls], ["input_actor_turn"])
        self.assertEqual(calls[0]["instance_json"], context.instance_json)
        self.assertEqual(calls[0]["thread_id"], "thr-main")
        self.assertIn("task_sys.parent_frame", calls[0]["text"])
        self.assertIn("task-user-input-abcdef123456", calls[0]["text"])

    def test_execute_submit_parent_delegates_capability_and_start_steer_to_actor_session(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_input = self.module.actor_session.input_actor_turn

        def fake_input_actor_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"action": "start", "turn_id": "turn-parent-contract"}

        self.addCleanup(setattr, self.module.actor_session, "input_actor_turn", original_input)
        self.module.actor_session.input_actor_turn = fake_input_actor_turn

        result = self.module.execute_instruction(context, self._parent_instruction())

        self.assertEqual(result["action"], "submit_parent")
        self.assertEqual(result["turn_id"], "turn-parent-contract")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["socket_path"], context.socket_path)
        self.assertEqual(calls[0]["instance_json"], context.instance_json)
        self.assertEqual(calls[0]["thread_id"], "thr-main")
        self.assertEqual(calls[0]["permissions"], context.permissions)
        self.assertIn("task_sys.parent_frame", calls[0]["text"])

    def test_execute_submit_parent_rejects_checkpoint_frame(self) -> None:
        context = self._context()
        original_submit = self.module.actor_session.input_actor_turn

        def fake_input_actor_turn(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            return {"turn_id": "turn-checkpoint-1"}

        self.addCleanup(setattr, self.module.actor_session, "input_actor_turn", original_submit)
        self.module.actor_session.input_actor_turn = fake_input_actor_turn

        with self.assertRaisesRegex(ValueError, "unsupported submit_parent frame kind"):
            self.module.execute_instruction(context, self._checkpoint_instruction())

    def test_execute_interrupt_submit_parent_interrupts_before_submit(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_submit = self.module.actor_session.input_actor_turn
        original_interrupt = self.module.app_server.interrupt_turn

        def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, Any]:
            calls.append({"helper": "interrupt_turn", "socket_path": socket_path, "thread_id": thread_id})
            return {"turn_id": "turn-active-1"}

        def fake_input_actor_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "input_actor_turn", **kwargs})
            return {"turn_id": "turn-parent-2"}

        self.addCleanup(setattr, self.module.actor_session, "input_actor_turn", original_submit)
        self.addCleanup(setattr, self.module.app_server, "interrupt_turn", original_interrupt)
        self.module.actor_session.input_actor_turn = fake_input_actor_turn
        self.module.app_server.interrupt_turn = fake_interrupt_turn

        result = self.module.execute_instruction(context, self._parent_instruction(interrupt=True))

        self.assertEqual(result["action"], "interrupt_submit_parent")
        self.assertEqual(result["turn_id"], "turn-parent-2")
        self.assertEqual(result["interrupted_turn_id"], "turn-active-1")
        self.assertEqual([call["helper"] for call in calls], ["interrupt_turn", "input_actor_turn"])
        self.assertEqual(calls[0]["thread_id"], "thr-main")
        self.assertIn("task_sys.parent_frame", calls[1]["text"])

    def test_execute_interrupt_submit_parent_idle_parent_submits_without_interrupted_turn(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_submit = self.module.actor_session.input_actor_turn
        original_interrupt = self.module.app_server.interrupt_turn

        def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, Any]:
            calls.append({"helper": "interrupt_turn", "socket_path": socket_path, "thread_id": thread_id})
            raise self.module.app_server.AppServerUnavailableError("thread thr-main has no active in-progress turn")

        def fake_input_actor_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "input_actor_turn", **kwargs})
            return {"turn_id": "turn-parent-idle"}

        self.addCleanup(setattr, self.module.actor_session, "input_actor_turn", original_submit)
        self.addCleanup(setattr, self.module.app_server, "interrupt_turn", original_interrupt)
        self.module.actor_session.input_actor_turn = fake_input_actor_turn
        self.module.app_server.interrupt_turn = fake_interrupt_turn

        result = self.module.execute_instruction(context, self._parent_instruction(interrupt=True))

        self.assertEqual(result["action"], "interrupt_submit_parent")
        self.assertEqual(result["turn_id"], "turn-parent-idle")
        self.assertNotIn("interrupted_turn_id", result)
        self.assertEqual([call["helper"] for call in calls], ["interrupt_turn", "input_actor_turn"])
        self.assertIn("task_sys.parent_frame", calls[1]["text"])

    def test_execute_interrupt_submit_parent_no_active_turn_race_submits_without_interrupted_turn(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_submit = self.module.actor_session.input_actor_turn
        original_interrupt = self.module.app_server.interrupt_turn

        def fake_interrupt_turn(socket_path: Path, thread_id: str) -> dict[str, Any]:
            calls.append({"helper": "interrupt_turn", "socket_path": socket_path, "thread_id": thread_id})
            raise self.module.app_server.AppServerUnavailableError(
                "thread thr-main is active but no in-progress turn was found"
            )

        def fake_input_actor_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append({"helper": "input_actor_turn", **kwargs})
            return {"turn_id": "turn-parent-race"}

        self.addCleanup(setattr, self.module.actor_session, "input_actor_turn", original_submit)
        self.addCleanup(setattr, self.module.app_server, "interrupt_turn", original_interrupt)
        self.module.actor_session.input_actor_turn = fake_input_actor_turn
        self.module.app_server.interrupt_turn = fake_interrupt_turn

        result = self.module.execute_instruction(context, self._parent_instruction(interrupt=True))

        self.assertEqual(result["action"], "interrupt_submit_parent")
        self.assertEqual(result["turn_id"], "turn-parent-race")
        self.assertNotIn("interrupted_turn_id", result)
        self.assertEqual([call["helper"] for call in calls], ["interrupt_turn", "input_actor_turn"])

    def test_task_sys_runtime_uses_actor_session_without_submit_turn_or_cli_imports(self) -> None:
        source = TASK_SYS_RUNTIME_PATH.read_text(encoding="utf-8")

        self.assertIn("import actor_session", source)
        self.assertNotIn("import parent_thread_submit", source)
        self.assertNotIn("import submit_turn", source)
        self.assertNotIn("turn_start", source)
        self.assertNotIn("turn_steer", source)


if __name__ == "__main__":
    unittest.main()
