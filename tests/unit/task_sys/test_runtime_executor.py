"""Tests for executing Task Sys runtime instructions."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Any

from tests.support.paths import REPO_ROOT
from tests.support.runtime import RuntimeWorkspaceTestCase

ROOT = REPO_ROOT
HELPER_DIR = ROOT / "tools" / "launcher"
SCRIPTS = ROOT / "scripts"

from env.repos import runtime_files  # noqa: E402
from env.domain import task_sys  # noqa: E402
import actor_capability  # noqa: E402

TASK_SYS_RUNTIME_PATH = ROOT / "tools" / "launcher" / ("task_sys_" + "runtime.py")
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    return importlib.reload(importlib.import_module(path.stem))


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


class TaskSysRuntimeExecutorTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.runtime_root
        self.module = load_module(TASK_SYS_RUNTIME_PATH)

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
            "task_id": "task-controlled-inbound-abcdef123456",
            "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
            "frame": {
                "kind": "task_sys.side_frame",
                "task_id": "task-controlled-inbound-abcdef123456",
                "source": {
                    "type": "demand",
                    "ref": {"demand_id": "demand-runtime-side", "demand_ref": "dref-runtime-side"},
                },
                "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
                "context": {
                    "execution_brief": {
                        "description": "Draft brief.",
                        "detail": "Draft the exact runtime fixture brief.",
                    }
                },
            },
        }

    def _ingested_instruction(self) -> tuple[str, dict[str, Any]]:
        result = task_sys.create(
            actor_target={"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-runtime-ingested",
                "basis_revision": 1,
                "demand_ref": "dref-runtime-ingested",
            },
            execution_brief={
                "description": "Draft brief.",
                "detail": "Draft the exact runtime fixture brief.",
            },
        )
        return str(result["task_id"]), dict(result["instruction"])

    def _parent_instruction(self, *, interrupt: bool = False) -> dict[str, Any]:
        return {
            "type": "interrupt_submit_parent" if interrupt else "submit_parent",
            "task_id": "task-controlled-inbound-abcdef123456",
            "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
            "frame": {
                "kind": "task_sys.parent_frame",
                "task_id": "task-controlled-inbound-abcdef123456",
                "source": {
                    "type": "demand",
                    "ref": {"demand_id": "demand-runtime-parent", "demand_ref": "dref-runtime-parent"},
                },
                "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
                "inbound_context": {
                    "execution_brief": {
                        "description": "Draft brief.",
                        "detail": "Draft the exact runtime fixture brief.",
                    }
                },
                "execution_handoff": {
                    "parent_frame_context": {
                        "next": "Draft the brief in parent.",
                    },
                    "interrupt": interrupt,
                    "ordering": {"after": "task-controlled-inbound-prior123"},
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

    def _outcome_instruction(self, *, status: str = "completed") -> dict[str, Any]:
        outcome = (
            {
                "type": "completion",
                "processor": "side",
                "summary": "Completed the selected Demand snapshot.",
                "updated_at": "2026-07-20T10:00:00+08:00",
            }
            if status == "completed"
            else {
                "type": "cancellation",
                "processor": "side",
                "reason": "The selected execution route is no longer viable.",
                "updated_at": "2026-07-20T10:00:00+08:00",
            }
        )
        return {
            "type": "submit_parent",
            "task_id": "task-demand-terminal123",
            "actor_target": {"actor_id": "act-dev-task-sys-runtime", "role_id": "dev"},
            "frame": {
                "kind": "task_sys.outcome_frame",
                "task_id": "task-demand-terminal123",
                "status": status,
                "source": {
                    "type": "demand",
                    "ref": {"demand_id": "demand-runtime-terminal", "demand_ref": "dref-runtime-terminal"},
                },
                "evidence_ref": {
                    "type": "task_sys.task",
                    "ref": {"task_id": "task-demand-terminal123"},
                },
                "outcome": outcome,
            },
        }

    def test_render_side_frame_is_task_sys_scoped_without_relation_gate(self) -> None:
        text = self.module.render_side_frame(self._instruction()["frame"])

        self.assertIn("task_sys.side_frame", text)
        self.assertIn("task-controlled-inbound-abcdef123456", text)
        self.assertNotIn("task_desc", text)
        self.assertNotIn("task_relation", text)
        self.assertNotIn("task_sys.update_task_analysis", text)
        self.assertNotIn("task_sys.list(status=all)", text)
        self.assertIn("task_sys.close", text)
        self.assertIn("task_sys.cancel", text)
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
        self.assertIn(
            "Do not inspect the local filesystem or run shell commands from side, even for read-only work.",
            text,
        )
        self.assertIn(
            "A request that requires projects/app or another workspace path must use task_sys.need_parent",
            text,
        )
        self.assertNotIn("Use local read-only inspection only", text)
        self.assertIn("artifacts, evidence, durable deliverables", text)
        self.assertNotIn("checkpoint", text.lower())
        self.assertNotIn("checkpoint_update", text)
        self.assertNotIn("no_actor_action", text)
        self.assertIn("Allowed frame completion operations:", text)
        self.assertNotIn("relation-analysis", text)
        self.assertNotIn("params={parent_frame_context, relation", text)
        stale_side_result = "Task Sys side " + "result"
        self.assertNotIn(stale_side_result, text)
        self.assertNotIn("[IM MESSAGE " + "TRIAGE]", text)
        self.assertNotIn("[TRACK COMMENT " + "TRIAGE]", text)
        self.assertNotIn("submit parent", text.lower())
        self.assertNotIn("side_" + "interrupt", text)

    def test_render_side_frame_rejects_non_demand_or_malformed_source(self) -> None:
        for source in (
            {"type": "test.inbound.created", "ref": {"id": "event-1"}},
            {"type": "demand", "ref": {"demand_id": "demand-runtime-side"}},
            {
                "type": "demand",
                "ref": {
                    "demand_id": "demand-runtime-side",
                    "demand_ref": "dref-runtime-side",
                    "extra": True,
                },
            },
        ):
            with self.subTest(source=source):
                frame = self._instruction()["frame"]
                frame["source"] = source
                with self.assertRaisesRegex(ValueError, "exact Demand"):
                    self.module.render_side_frame(frame)

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
        self.assertEqual(call["task_id"], "task-controlled-inbound-abcdef123456")
        self.assertNotIn("model", call)
        self.assertNotIn("model_reasoning_effort", call)
        self.assertIn("task_sys.side_frame", call["text"])
        self.assertIn("task_sys.close", call["text"])
        self.assertIn("task_sys.need_parent", call["text"])

    def test_execute_start_side_immediately_checks_an_idle_work_turn(self) -> None:
        context = self._context()
        task_id, instruction = self._ingested_instruction()
        original_start = self.module.actor_side_thread.start_actor_side_thread
        original_submit = self.module.submit_task_progress_check
        submissions: list[dict[str, Any]] = []

        def fake_start_side_thread(**kwargs: Any) -> dict[str, Any]:
            return {
                "action": "start",
                "purpose": "task_sys.side_frame",
                "parent_thread_id": kwargs["parent_thread_id"],
                "side_thread_id": "thr-side-fast-idle",
                "thread_action": "start",
                "turn_id": "turn-side-fast-work",
                "thread_status": "idle",
                "lease_registered": True,
            }

        def fake_submit(
            submit_context: Any,
            task: dict[str, Any],
            previous_turn: dict[str, Any],
            *,
            processor: str,
            side_thread_id: str | None = None,
        ) -> dict[str, Any]:
            submissions.append(
                {
                    "context": submit_context,
                    "task": task,
                    "previous_turn": previous_turn,
                    "processor": processor,
                    "side_thread_id": side_thread_id,
                }
            )
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-side-fast-check"}

        self.addCleanup(setattr, self.module.actor_side_thread, "start_actor_side_thread", original_start)
        self.addCleanup(setattr, self.module, "submit_task_progress_check", original_submit)
        self.module.actor_side_thread.start_actor_side_thread = fake_start_side_thread
        self.module.submit_task_progress_check = fake_submit

        result = self.module.execute_instruction(context, instruction)

        self.assertEqual(result["progress_check"]["turn_id"], "turn-side-fast-check")
        self.assertEqual(len(submissions), 1)
        self.assertIs(submissions[0]["context"], context)
        self.assertEqual(submissions[0]["task"]["id"], task_id)
        self.assertEqual(
            submissions[0]["previous_turn"],
            {
                "thread_id": "thr-side-fast-idle",
                "turn_id": "turn-side-fast-work",
                "status": "idle",
            },
        )
        self.assertEqual(submissions[0]["processor"], "side")
        self.assertEqual(submissions[0]["side_thread_id"], "thr-side-fast-idle")

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
        second_instruction["task_id"] = "task-controlled-inbound-second123"
        second_instruction["frame"]["task_id"] = "task-controlled-inbound-second123"
        second = self.module.execute_instruction(context, second_instruction)

        self.assertEqual(first["side_thread_id"], "thr-side-1")
        self.assertEqual(second["side_thread_id"], "thr-side-2")
        self.assertEqual(
            [call["task_id"] for call in calls],
            ["task-controlled-inbound-abcdef123456", "task-controlled-inbound-second123"],
        )
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
        self.assertEqual(record["status"], "in_progress.side_processing")
        self.assertNotIn("active_processor", record)
        execution = record["execution"]
        self.assertIsNone(execution["processor"])
        self.assertEqual(execution["result"]["type"], "failure")
        self.assertEqual(execution["result"]["reason"], "runtime_failed")
        self.assertEqual(execution["result"]["stage"], "side_lifecycle")
        self.assertEqual(execution["result"]["attempts"], 2)
        self.assertEqual(result["execution_result"], execution["result"])
        self.assertNotIn("failure_result", result)

    def test_execute_start_side_does_not_retry_when_lifecycle_cannot_prove_turn_stopped(self) -> None:
        context = self._context()
        task_id, instruction = self._ingested_instruction()
        calls: list[dict[str, Any]] = []
        original_start = self.module.actor_side_thread.start_actor_side_thread

        class UnsafeLifecycleFailure(RuntimeError):
            retryable = False
            cleanup = {
                "turn_interrupt_attempted": True,
                "turn_interrupt_ok": False,
                "turn_interrupt_error": "turn interrupt failed",
                "lease_unregistered": True,
            }

        def fake_start_side_thread(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            raise UnsafeLifecycleFailure("side processor may still be active")

        self.addCleanup(setattr, self.module.actor_side_thread, "start_actor_side_thread", original_start)
        self.module.actor_side_thread.start_actor_side_thread = fake_start_side_thread

        result = self.module.execute_instruction(context, instruction)

        self.assertEqual(result["status"], "runtime_failed")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(result["attempts"]), 1)
        self.assertFalse(result["attempts"][0]["retryable"])
        execution_result = task_sys.get_task(task_id)["execution"]["result"]
        self.assertFalse(execution_result["retryable"])
        self.assertEqual(execution_result["cleanup"]["turn_interrupt_error"], "turn interrupt failed")

    def test_execute_start_side_rejects_consumed_lease_while_task_is_still_side_owned(self) -> None:
        context = self._context()
        task_id, instruction = self._ingested_instruction()
        starts: list[dict[str, Any]] = []
        interrupts: list[dict[str, Any]] = []
        original_start = self.module.actor_side_thread.start_actor_side_thread
        original_interrupt = getattr(self.module.side_thread_lifecycle, "interrupt_unleased_side_turn", None)

        def fake_start_side_thread(**kwargs: Any) -> dict[str, Any]:
            starts.append(kwargs)
            return {
                "action": "start",
                "purpose": "task_sys.side_frame",
                "parent_thread_id": kwargs["parent_thread_id"],
                "side_thread_id": "thr-side-consumed-without-transition",
                "thread_action": "start",
                "turn_id": "turn-side-consumed-without-transition",
                "thread_status": "consumed",
                "lease_registered": False,
                "lease_consumed": True,
            }

        def fake_interrupt_unleased_side_turn(**kwargs: Any) -> dict[str, Any]:
            interrupts.append(kwargs)
            return {
                "turn_interrupt_attempted": True,
                "turn_interrupt_ok": True,
                "lease_unregistered": False,
            }

        def restore_interrupt() -> None:
            if original_interrupt is None:
                delattr(self.module.side_thread_lifecycle, "interrupt_unleased_side_turn")
            else:
                setattr(self.module.side_thread_lifecycle, "interrupt_unleased_side_turn", original_interrupt)

        self.addCleanup(setattr, self.module.actor_side_thread, "start_actor_side_thread", original_start)
        self.addCleanup(restore_interrupt)
        self.module.actor_side_thread.start_actor_side_thread = fake_start_side_thread
        self.module.side_thread_lifecycle.interrupt_unleased_side_turn = fake_interrupt_unleased_side_turn

        result = self.module.execute_instruction(context, instruction)

        self.assertEqual(result["status"], "runtime_failed")
        self.assertEqual(result["stage"], "side_lease_consumed")
        self.assertEqual(len(starts), 1)
        self.assertEqual(len(interrupts), 1)
        self.assertEqual(interrupts[0]["side_thread_id"], "thr-side-consumed-without-transition")
        self.assertEqual(interrupts[0]["turn_id"], "turn-side-consumed-without-transition")
        task = task_sys.get_task(task_id)
        self.assertEqual(task["status"], task_sys.SIDE_PROCESSING)
        self.assertEqual(task["execution"]["result"]["stage"], "side_lease_consumed")
        self.assertTrue(task["execution"]["result"]["cleanup"]["turn_interrupt_ok"])

    def test_execute_start_side_accepts_consumed_lease_after_task_left_side_processing(self) -> None:
        context = self._context()
        task_id, instruction = self._ingested_instruction()
        interrupts: list[dict[str, Any]] = []
        original_start = self.module.actor_side_thread.start_actor_side_thread
        original_interrupt = getattr(self.module.side_thread_lifecycle, "interrupt_unleased_side_turn", None)

        def fake_start_side_thread(**kwargs: Any) -> dict[str, Any]:
            task_sys.record_side_need_parent(
                task_id,
                {
                    "params": {
                        "parent_frame_context": {"next": "Continue in parent."},
                        "interrupt": False,
                    }
                },
            )
            return {
                "action": "start",
                "purpose": "task_sys.side_frame",
                "parent_thread_id": kwargs["parent_thread_id"],
                "side_thread_id": "thr-side-consumed-after-handoff",
                "thread_action": "start",
                "turn_id": "turn-side-consumed-after-handoff",
                "thread_status": "consumed",
                "lease_registered": False,
                "lease_consumed": True,
            }

        def unexpected_interrupt(**kwargs: Any) -> dict[str, Any]:
            interrupts.append(kwargs)
            return {}

        def restore_interrupt() -> None:
            if original_interrupt is None:
                delattr(self.module.side_thread_lifecycle, "interrupt_unleased_side_turn")
            else:
                setattr(self.module.side_thread_lifecycle, "interrupt_unleased_side_turn", original_interrupt)

        self.addCleanup(setattr, self.module.actor_side_thread, "start_actor_side_thread", original_start)
        self.addCleanup(restore_interrupt)
        self.module.actor_side_thread.start_actor_side_thread = fake_start_side_thread
        self.module.side_thread_lifecycle.interrupt_unleased_side_turn = unexpected_interrupt

        result = self.module.execute_instruction(context, instruction)

        self.assertEqual(result["action"], "start_side")
        self.assertTrue(result["lease_consumed"])
        self.assertNotIn("status", result)
        self.assertEqual(interrupts, [])
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.AWAITING_PARENT)

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

        result = self.module.cleanup_side_lease(context, "task-controlled-inbound-cleanup123")

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
                    "task_id": "task-controlled-inbound-cleanup123",
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
        self.assertIn("task-controlled-inbound-abcdef123456", text)
        self.assertIn("Task Sys source:", text)
        self.assertNotIn("Task desc:", text)
        self.assertNotIn("Task relation:", text)
        self.assertIn("Execution handoff:", text)
        self.assertIn("Draft the brief in parent.", text)
        self.assertNotIn("Side result:", text)
        self.assertNotIn("Parent handoff params:", text)
        self.assertNotIn("[MESSAGE NEEDS " + "PARENT]", text)
        self.assertNotIn("[TRACK COMMENT", text)

    def test_render_parent_frame_rejects_legacy_handoff_shape(self) -> None:
        instruction = self._parent_instruction()
        frame = instruction["frame"]
        frame.pop("execution_handoff")
        frame["side_result"] = {"outcome": "need_parent", "params": {"interrupt": False}}
        frame["parent_handoff_params"] = {"parent_frame_context": {"next": "Draft the brief in parent."}}

        with self.assertRaisesRegex(ValueError, "frame.execution_handoff"):
            self.module.render_parent_frame(frame)

    def test_render_parent_frame_requires_task_sys_close(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertIn("When the source task is complete, call task_sys.close(task_id=..., summary=...).", text)
        self.assertIn("Do not rely on parent turn completion to close this Task Sys task.", text)
        self.assertIn("Allowed parent frame operations:", text)
        self.assertIn("- task_sys.close(task_id=..., summary=...)", text)
        self.assertIn("- task_sys.cancel(task_id=..., reason=...)", text)

    def test_render_parent_frame_for_demand_source_uses_task_sys_actions(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertIn("For this parent source:", text)
        self.assertNotIn("message.send(target_identity_id=..., content=...)", text)
        self.assertIn("After required parent work is complete, call task_sys.close.", text)
        self.assertIn("execution_handoff", text)
        self.assertNotIn("parent_handoff_params", text)
        self.assertNotIn("For an IM source message:", text)
        self.assertNotIn("Only after the source-" + "bound IM action " + "succeeds", text)

    def test_render_parent_frame_rejects_non_demand_source(self) -> None:
        frame = self._parent_instruction()["frame"]
        frame["source"] = {
            "type": "track.comment.added",
            "ref": {"comment_id": "comment-old"},
        }

        with self.assertRaisesRegex(ValueError, "exact Demand"):
            self.module.render_parent_frame(frame)

    def test_render_parent_frame_does_not_mention_checkpoint_update(self) -> None:
        text = self.module.render_parent_frame(self._parent_instruction()["frame"])

        self.assertNotIn("checkpoint", text.lower())
        self.assertNotIn("checkpoint_update", text)

    def test_render_completed_outcome_frame_reconciles_latest_source_obligation(self) -> None:
        text = self.module.render_submit_parent_frame(self._outcome_instruction()["frame"])

        self.assertIn("task_sys.outcome_frame", text)
        self.assertIn("task-demand-terminal123", text)
        self.assertIn("demand-runtime-terminal", text)
        self.assertNotIn("basis_revision", text)
        self.assertIn("demand_ref", text)
        self.assertIn("$demand-orchestration", text)
        self.assertIn("Completed the selected Demand snapshot.", text)
        self.assertIn('"task_id": "task-demand-terminal123"', text)
        self.assertIn("Pass this evidence reference unchanged", text)
        self.assertNotIn("acknowledge the exact returned revision", text)
        self.assertIn("already terminal", text)
        self.assertIn("reconcile", text.lower())
        self.assertIn("source-owned obligation", text)
        self.assertNotIn("task_sys.close", text)
        self.assertNotIn("task_sys.cancel", text)
        self.assertIn("task_sys__create", text)
        self.assertIn("one other live Demand", text)
        self.assertNotIn("Demand status", text)
        self.assertNotIn("Demand lifecycle", text)

    def test_render_canceled_outcome_frame_requires_explicit_source_decision(self) -> None:
        text = self.module.render_submit_parent_frame(self._outcome_instruction(status="canceled")["frame"])

        self.assertIn("task_sys.outcome_frame", text)
        self.assertIn("$demand-orchestration", text)
        self.assertNotIn("basis_revision", text)
        self.assertIn("canceled", text.lower())
        self.assertIn("does not imply", text.lower())
        self.assertIn("complete, cancel, revise, or keep", text.lower())
        self.assertNotIn("acknowledge the exact returned revision", text)
        self.assertNotIn("task_sys.close", text)
        self.assertNotIn("task_sys.cancel(task_id", text)

    def test_render_outcome_frame_rejects_status_result_mismatch(self) -> None:
        completed = self._outcome_instruction()
        completed["frame"]["status"] = "canceled"
        canceled = self._outcome_instruction(status="canceled")
        canceled["frame"]["status"] = "completed"

        for frame in (completed["frame"], canceled["frame"]):
            with self.subTest(frame=frame):
                with self.assertRaisesRegex(ValueError, "outcome frame must contain"):
                    self.module.render_submit_parent_frame(frame)

    def test_execute_outcome_instruction_reuses_submit_parent_runtime(self) -> None:
        context = self._context()
        calls: list[dict[str, Any]] = []
        original_input = self.module.actor_session.input_actor_turn
        self.addCleanup(setattr, self.module.actor_session, "input_actor_turn", original_input)
        self.module.actor_session.input_actor_turn = lambda **kwargs: (
            calls.append(kwargs) or {"turn_id": "turn-outcome-attention"}
        )

        result = self.module.execute_instruction(context, self._outcome_instruction())

        self.assertEqual(result["action"], "submit_parent")
        self.assertEqual(result["task_id"], "task-demand-terminal123")
        self.assertEqual(result["turn_id"], "turn-outcome-attention")
        self.assertEqual(len(calls), 1)
        self.assertIn("task_sys.outcome_frame", calls[0]["text"])

    def test_render_side_frame_no_longer_calls_close_a_side_result(self) -> None:
        text = self.module.render_side_frame(self._instruction()["frame"])

        self.assertIn("Allowed frame completion operations:", text)
        self.assertIn("task_sys.close(task_id=..., summary=...) when the task is completed in side.", text)
        self.assertNotIn("task_sys.update_task_analysis", text)
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
        self.assertEqual(result["task_id"], "task-controlled-inbound-abcdef123456")
        self.assertEqual([call["helper"] for call in calls], ["input_actor_turn"])
        self.assertEqual(calls[0]["instance_json"], context.instance_json)
        self.assertEqual(calls[0]["thread_id"], "thr-main")
        self.assertIn("task_sys.parent_frame", calls[0]["text"])
        self.assertIn("task-controlled-inbound-abcdef123456", calls[0]["text"])

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

    def test_render_task_progress_check_for_parent_binds_existing_task_and_current_actions(self) -> None:
        task = {
            "id": "task-controlled-inbound-progress123",
            "source_type": "demand",
            "source_ref": {
                "demand_id": "demand-runtime-progress-parent",
                "demand_ref": "dref-runtime-progress-parent",
            },
            "status": "in_progress.parent_processing",
            "events": [
                {"type": "created", "at": "2026-07-16T00:00:00Z"},
                {"type": "parent_handoff_started", "at": "2026-07-16T00:01:00Z"},
            ],
        }
        previous_turn = {
            "thread_id": "thr-main",
            "turn_id": "turn-parent-work-1",
            "status": "completed",
        }

        prompt = self.module.render_task_progress_check(task, previous_turn, processor="parent")

        self.assertIn("[TASK PROGRESS CHECK]", prompt)
        self.assertIn("task-controlled-inbound-progress123", prompt)
        self.assertIn("in_progress.parent_processing", prompt)
        self.assertIn("parent_handoff_started", prompt)
        self.assertIn("turn-parent-work-1", prompt)
        self.assertIn("task_sys.close", prompt)
        self.assertIn("task_sys.cancel", prompt)
        self.assertIn("continue", prompt.lower())
        self.assertIn("status remains in_progress.parent_processing", prompt)
        lowered = prompt.lower()
        for retired in ("checkpoint_update", "status=checkpoint", "task_sys.ingest"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, lowered)

    def test_render_side_progress_check_binds_existing_side_task_and_current_actions(self) -> None:
        task = {
            "id": "task-controlled-inbound-side-progress123",
            "source_type": "demand",
            "source_ref": {
                "demand_id": "demand-runtime-progress-side",
                "demand_ref": "dref-runtime-progress-side",
            },
            "status": "in_progress.side_processing",
            "events": [
                {"type": "created", "at": "2026-07-16T00:00:00Z"},
                {"type": "side_frame_started", "at": "2026-07-16T00:00:01Z"},
            ],
        }
        previous_turn = {
            "thread_id": "thr-side-progress",
            "turn_id": "turn-side-work-1",
            "status": "idle",
        }

        prompt = self.module.render_task_progress_check(task, previous_turn, processor="side")

        self.assertIn("[TASK PROGRESS CHECK]", prompt)
        self.assertIn("existing side-owned Task", prompt)
        self.assertIn("side thread became idle", prompt)
        self.assertIn("task-controlled-inbound-side-progress123", prompt)
        self.assertIn("in_progress.side_processing", prompt)
        self.assertIn("turn-side-work-1", prompt)
        self.assertIn("task_sys.close", prompt)
        self.assertIn("task_sys.cancel", prompt)
        self.assertIn("task_sys.need_parent", prompt)
        self.assertIn("status remains in_progress.side_processing", prompt)

    def test_render_task_progress_check_rejects_non_demand_source(self) -> None:
        task = {
            "id": "task-controlled-inbound-progress-old",
            "source_type": "track.comment.added",
            "source_ref": {"comment_id": "comment-old"},
            "status": "in_progress.parent_processing",
            "events": [],
        }
        previous_turn = {
            "thread_id": "thr-main",
            "turn_id": "turn-parent-work-old",
            "status": "completed",
        }

        with self.assertRaisesRegex(ValueError, "exact Demand"):
            self.module.render_task_progress_check(task, previous_turn, processor="parent")

    def test_submit_task_progress_check_for_parent_uses_main_actor_thread(self) -> None:
        context = self._context()
        task = {
            "id": "task-controlled-inbound-progress123",
            "source_type": "demand",
            "source_ref": {
                "demand_id": "demand-runtime-submit-parent",
                "demand_ref": "dref-runtime-submit-parent",
            },
            "status": "in_progress.parent_processing",
            "events": [{"type": "parent_handoff_started", "at": "2026-07-16T00:01:00Z"}],
        }
        previous_turn = {
            "thread_id": "thr-main",
            "turn_id": "turn-parent-work-1",
            "status": "completed",
        }
        calls: list[dict[str, Any]] = []
        original_input = self.module.actor_session.input_actor_turn

        def fake_input_actor_turn(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"turn": {"id": "turn-progress-check-1"}}

        self.addCleanup(setattr, self.module.actor_session, "input_actor_turn", original_input)
        self.module.actor_session.input_actor_turn = fake_input_actor_turn

        result = self.module.submit_task_progress_check(context, task, previous_turn, processor="parent")

        self.assertEqual(
            result,
            {
                "action": "progress_check",
                "task_id": "task-controlled-inbound-progress123",
                "turn_id": "turn-progress-check-1",
            },
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["socket_path"], context.socket_path)
        self.assertEqual(calls[0]["instance_json"], context.instance_json)
        self.assertEqual(calls[0]["thread_id"], context.main_thread_id)
        self.assertEqual(calls[0]["permissions"], context.permissions)
        self.assertIn("[TASK PROGRESS CHECK]", calls[0]["text"])

    def test_submit_side_progress_check_uses_exact_registered_side_thread(self) -> None:
        context = self._context()
        side_thread_registry = importlib.import_module("side_thread_registry")
        side_thread_registry.register_side_thread(
            context.instance_json,
            actor_id=context.actor_id,
            parent_thread_id=context.main_thread_id,
            side_thread_id="thr-side-progress",
            task_id="task-controlled-inbound-side-progress123",
            purpose="task_sys.side_frame",
            turn_id="turn-side-work-1",
            turn_kind="work",
        )
        task = {
            "id": "task-controlled-inbound-side-progress123",
            "source_type": "demand",
            "source_ref": {
                "demand_id": "demand-runtime-submit-side",
                "demand_ref": "dref-runtime-submit-side",
            },
            "status": "in_progress.side_processing",
            "events": [{"type": "side_frame_started", "at": "2026-07-16T00:00:01Z"}],
        }
        previous_turn = {
            "thread_id": "thr-side-progress",
            "turn_id": "turn-side-work-1",
            "status": "idle",
        }
        calls: list[dict[str, Any]] = []
        original_send = self.module.side_thread_lifecycle.send_to_side_thread

        def fake_send_to_side_thread(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {"action": "send", "turn_id": "turn-side-progress-check-1"}

        self.addCleanup(setattr, self.module.side_thread_lifecycle, "send_to_side_thread", original_send)
        self.module.side_thread_lifecycle.send_to_side_thread = fake_send_to_side_thread

        result = self.module.submit_task_progress_check(
            context,
            task,
            previous_turn,
            processor="side",
            side_thread_id="thr-side-progress",
        )

        self.assertEqual(
            result,
            {
                "action": "progress_check",
                "task_id": "task-controlled-inbound-side-progress123",
                "turn_id": "turn-side-progress-check-1",
            },
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["socket_path"], context.socket_path)
        self.assertEqual(calls[0]["instance_json"], context.instance_json)
        self.assertEqual(calls[0]["actor_id"], context.actor_id)
        self.assertEqual(calls[0]["parent_thread_id"], context.main_thread_id)
        self.assertEqual(calls[0]["side_thread_id"], "thr-side-progress")
        self.assertEqual(calls[0]["permissions"], context.permissions)
        self.assertEqual(calls[0]["turn_kind"], "progress_check")
        self.assertIn("existing side-owned Task", calls[0]["text"])

    def test_side_progress_check_preserves_submit_failure_when_lease_is_concurrently_cleaned(self) -> None:
        context = self._context()
        side_thread_registry = importlib.import_module("side_thread_registry")
        side_thread_registry.register_side_thread(
            context.instance_json,
            actor_id=context.actor_id,
            parent_thread_id=context.main_thread_id,
            side_thread_id="thr-side-cleaned-during-check",
            task_id="task-controlled-inbound-side-cleaned123",
            purpose="task_sys.side_frame",
            turn_id="turn-side-cleaned-work",
            turn_kind="work",
        )
        task = {
            "id": "task-controlled-inbound-side-cleaned123",
            "source_type": "demand",
            "source_ref": {
                "demand_id": "demand-runtime-side-cleaned",
                "demand_ref": "dref-runtime-side-cleaned",
            },
            "status": "in_progress.side_processing",
            "events": [{"type": "side_frame_started", "at": "2026-07-16T00:00:01Z"}],
        }
        previous_turn = {
            "thread_id": "thr-side-cleaned-during-check",
            "turn_id": "turn-side-cleaned-work",
            "status": "idle",
        }
        original_send = self.module.side_thread_lifecycle.send_to_side_thread

        def fail_after_cleanup(**_kwargs: Any) -> dict[str, Any]:
            side_thread_registry.unregister_side_thread(
                context.instance_json,
                actor_id=context.actor_id,
                parent_thread_id=context.main_thread_id,
                side_thread_id="thr-side-cleaned-during-check",
            )
            raise RuntimeError("side progress submit failed")

        self.addCleanup(setattr, self.module.side_thread_lifecycle, "send_to_side_thread", original_send)
        self.module.side_thread_lifecycle.send_to_side_thread = fail_after_cleanup

        with self.assertRaisesRegex(RuntimeError, "side progress submit failed"):
            self.module.submit_task_progress_check(
                context,
                task,
                previous_turn,
                processor="side",
                side_thread_id="thr-side-cleaned-during-check",
            )

    def test_side_progress_check_keeps_pending_claim_when_external_submit_may_have_succeeded(self) -> None:
        context = self._context()
        side_thread_registry = importlib.import_module("side_thread_registry")
        side_thread_registry.register_side_thread(
            context.instance_json,
            actor_id=context.actor_id,
            parent_thread_id=context.main_thread_id,
            side_thread_id="thr-side-uncertain-check",
            task_id="task-controlled-inbound-side-uncertain123",
            purpose="task_sys.side_frame",
            turn_id="turn-side-uncertain-work",
            turn_kind="work",
        )
        task = {
            "id": "task-controlled-inbound-side-uncertain123",
            "source_type": "demand",
            "source_ref": {
                "demand_id": "demand-runtime-side-uncertain",
                "demand_ref": "dref-runtime-side-uncertain",
            },
            "status": "in_progress.side_processing",
            "events": [{"type": "side_frame_started", "at": "2026-07-16T00:00:01Z"}],
        }
        previous_turn = {
            "thread_id": "thr-side-uncertain-check",
            "turn_id": "turn-side-uncertain-work",
            "status": "idle",
        }
        original_send = self.module.side_thread_lifecycle.send_to_side_thread

        class SubmitPersistenceFailure(RuntimeError):
            input_submitted = True

        def fail_after_submit(**_kwargs: Any) -> dict[str, Any]:
            raise SubmitPersistenceFailure("external Progress Check may have been submitted")

        self.addCleanup(setattr, self.module.side_thread_lifecycle, "send_to_side_thread", original_send)
        self.module.side_thread_lifecycle.send_to_side_thread = fail_after_submit

        with self.assertRaisesRegex(SubmitPersistenceFailure, "may have been submitted"):
            self.module.submit_task_progress_check(
                context,
                task,
                previous_turn,
                processor="side",
                side_thread_id="thr-side-uncertain-check",
            )

        row = side_thread_registry.require_side_thread(
            context.instance_json,
            actor_id=context.actor_id,
            parent_thread_id=context.main_thread_id,
            side_thread_id="thr-side-uncertain-check",
        )
        self.assertEqual(row["turn_id"], "turn-side-uncertain-work")
        self.assertEqual(row["turn_kind"], "progress_check_pending")

    def test_side_progress_check_releases_pending_claim_when_submit_was_not_attempted(self) -> None:
        context = self._context()
        side_thread_registry = importlib.import_module("side_thread_registry")
        side_thread_registry.register_side_thread(
            context.instance_json,
            actor_id=context.actor_id,
            parent_thread_id=context.main_thread_id,
            side_thread_id="thr-side-safe-retry-check",
            task_id="task-controlled-inbound-side-safe-retry123",
            purpose="task_sys.side_frame",
            turn_id="turn-side-safe-retry-work",
            turn_kind="work",
        )
        task = {
            "id": "task-controlled-inbound-side-safe-retry123",
            "source_type": "demand",
            "source_ref": {
                "demand_id": "demand-runtime-side-safe-retry",
                "demand_ref": "dref-runtime-side-safe-retry",
            },
            "status": "in_progress.side_processing",
            "events": [{"type": "side_frame_started", "at": "2026-07-16T00:00:01Z"}],
        }
        previous_turn = {
            "thread_id": "thr-side-safe-retry-check",
            "turn_id": "turn-side-safe-retry-work",
            "status": "idle",
        }
        original_send = self.module.side_thread_lifecycle.send_to_side_thread

        class PreSubmitFailure(RuntimeError):
            input_submitted = False

        self.addCleanup(setattr, self.module.side_thread_lifecycle, "send_to_side_thread", original_send)
        self.module.side_thread_lifecycle.send_to_side_thread = lambda **_kwargs: (_ for _ in ()).throw(
            PreSubmitFailure("validation failed before submit")
        )

        with self.assertRaisesRegex(PreSubmitFailure, "before submit"):
            self.module.submit_task_progress_check(
                context,
                task,
                previous_turn,
                processor="side",
                side_thread_id="thr-side-safe-retry-check",
            )

        row = side_thread_registry.require_side_thread(
            context.instance_json,
            actor_id=context.actor_id,
            parent_thread_id=context.main_thread_id,
            side_thread_id="thr-side-safe-retry-check",
        )
        self.assertEqual(row["turn_id"], "turn-side-safe-retry-work")
        self.assertEqual(row["turn_kind"], "work")

    def test_task_sys_runtime_uses_actor_session_without_submit_turn_or_cli_imports(self) -> None:
        source = TASK_SYS_RUNTIME_PATH.read_text(encoding="utf-8")

        self.assertIn("import actor_session", source)
        self.assertNotIn("import parent_thread_" + "submit", source)
        self.assertNotIn("import submit_turn", source)
        self.assertNotIn("turn_start", source)
        self.assertNotIn("turn_steer", source)
