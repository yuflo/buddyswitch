"""Response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sys
import threading
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

from tests.support.paths import REPO_ROOT
from tests.support.fake_cdp import (
    read_client_text_frame as _read_client_text_frame,
    websocket_accept_value as _websocket_accept_value,
    write_server_text_frame as _write_server_text_frame,
)

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.domain import demand_sys, task_sys  # noqa: E402
from env.tool_runtime import registry as tool_catalog  # noqa: E402
from env.tool_runtime import results as tool_results  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
import env.tools.search._impl as search_impl  # noqa: E402
import turn_runtime  # noqa: E402
from tests.integration.env_tool._response_case import EnvToolResponseCase

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvToolTaskResponseTests(EnvToolResponseCase):
    def _seed_active_task(self, *, instance_json: Path, role: str, actor_id: str) -> None:
        del instance_json, role, actor_id

    @staticmethod
    def _direct_task(*, actor_id: str, label: str) -> dict[str, Any]:
        normalized_label = label.replace("_", "-")
        return task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": f"demand-response-{normalized_label}",
                "basis_revision": 1,
                "demand_ref": f"dref-response-{normalized_label}",
            },
            execution_brief={
                "description": f"Task response fixture: {label}.",
                "detail": f"Exercise the exact Task response contract for {label}.",
            },
        )

    @staticmethod
    def _actor_demand_ref(*, actor_id: str, label: str) -> str:
        actor_target = {"actor_id": actor_id, "role_id": "dev"}
        created = demand_sys.create(
            actor_target,
            f"actor-create:{label}",
            "Inspect the current product contract.",
            "Read the exact current product contract.",
            [{
                "type": "actor.self_requested",
                "ref": {"thread_id": "thr-main", "turn_id": f"turn-{label}"},
            }],
        )
        return str(created["demand_ref"])

    @staticmethod
    def _create_args(
        *,
        demand_ref: str,
        detail: str = "Read the exact current product contract.",
    ) -> dict[str, object]:
        return {
            "demand_ref": demand_ref,
            "execution_brief": {
                "description": "Inspect the current product contract.",
                "detail": detail,
            },
        }

    def test_task_sys_create_response_starts_side_once_and_replays_exactly(self) -> None:
        actor_label = "act-dev-task-sys-create"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        demand_ref = self._actor_demand_ref(actor_id=actor_id, label="create-response")
        create_args = self._create_args(demand_ref=demand_ref)

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            return_value={
                "action": "start_side",
                "status": "side_started",
                "side_thread_id": "thr-side-create-response",
            },
        ) as execute_instruction:
            created = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=create_args,
            )
            replay = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=create_args,
            )

        self._assert_write_success_contract(created)
        self._assert_success_contract(replay)
        self.assertEqual(created["outcome"], "created")
        self.assertEqual(replay["outcome"], "existing")
        self.assertEqual(replay["task_id"], created["task_id"])
        self.assertEqual(created["task_status"], task_sys.SIDE_PROCESSING)
        self.assertEqual(created["demand_ref"]["demand_ref"], demand_ref)
        self.assertEqual(created["runtime"]["action"], "start_side")
        self.assertIs(created["state_changed"], True)
        self.assertIs(replay["state_changed"], False)
        self.assertIsNone(replay["runtime"])
        execute_instruction.assert_called_once()
        self.assertEqual(
            len(task_sys.list_tasks(actor_target={"actor_id": actor_id, "role_id": "dev"})),
            1,
        )

    def test_task_sys_create_conflicts_return_targeted_rejections_without_runtime(self) -> None:
        actor_label = "act-dev-task-sys-create-conflict"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        active = self._direct_task(actor_id=actor_id, label="existing-active")
        demand_ref = self._actor_demand_ref(actor_id=actor_id, label="create-conflict")
        create_args = self._create_args(demand_ref=demand_ref)

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            side_effect=AssertionError("conflict must not execute Task runtime"),
        ):
            active_conflict = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=create_args,
            )

        self._assert_rejection_contract(active_conflict)
        self.assertEqual(active_conflict["error"]["code"], "E_TASK_SYS_ACTIVE_CONFLICT")
        self.assertEqual(active_conflict["active_task_id"], active["task_id"])

        task_sys.record_task_cancel(active["task_id"], {"reason": "Release conflict fixture."})
        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            return_value={"action": "start_side", "status": "side_started"},
        ):
            created = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=create_args,
            )
            source_conflict = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=self._create_args(
                    demand_ref=demand_ref,
                    detail="Changed brief for the same immutable source.",
                ),
            )

        self._assert_write_success_contract(created)
        self._assert_rejection_contract(source_conflict)
        self.assertEqual(source_conflict["error"]["code"], "E_TASK_SYS_SOURCE_CONFLICT")
        self.assertEqual(source_conflict["conflicting_task_id"], created["task_id"])

    def test_task_sys_create_reloads_runtime_failure_state(self) -> None:
        actor_label = "act-dev-task-sys-create-runtime-failure"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        demand_ref = self._actor_demand_ref(actor_id=actor_id, label="runtime-failure")

        def fail_side(_access: object, instruction: dict[str, object]) -> dict[str, object]:
            task_sys.record_side_runtime_failure(
                str(instruction["task_id"]),
                {
                    "reason": "runtime_failed",
                    "stage": "side_lifecycle",
                    "processor": "side",
                    "error": "real runtime could not start side",
                    "retryable": True,
                    "attempts": 2,
                },
            )
            return {
                "action": "start_side",
                "status": "runtime_failed",
                "task_id": instruction["task_id"],
            }

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            side_effect=fail_side,
        ):
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=self._create_args(demand_ref=demand_ref),
            )

        self._assert_write_success_contract(response)
        self.assertEqual(response["runtime"]["status"], "runtime_failed")
        self.assertEqual(response["execution"]["result"]["reason"], "runtime_failed")
        self.assertEqual(response["task_status"], task_sys.SIDE_PROCESSING)

    def test_task_sys_close_and_need_parent_reject_foreign_task_before_mutation(self) -> None:
        owner_label = "act-dev-task-owner"
        caller_label = "act-dev-task-foreign-caller"
        caller_instance = self._instance_json(role="dev", actor_id=caller_label)

        for action, args_tail in (
            ("close", {"summary": "Must not close another actor's Task."}),
            ("need_parent", {"params": {"parent_frame_context": {"next": "Forbidden."}}}),
        ):
            with self.subTest(action=action):
                owner_id = self._runtime_actor_id(role="dev", label=f"{owner_label}-{action}")
                task_id = self._direct_task(actor_id=owner_id, label=f"foreign-{action}")["task_id"]
                before = task_sys.get_task(task_id)
                with patch.object(
                    runtime_context.TaskSysRuntimeAccess,
                    "execute_instruction",
                    autospec=True,
                    side_effect=AssertionError("foreign Task must not execute runtime"),
                ), patch.object(
                    runtime_context.TaskSysRuntimeAccess,
                    "cleanup_side_lease",
                    autospec=True,
                    side_effect=AssertionError("foreign Task must not clean side runtime"),
                ):
                    response = self._dispatch(
                        instance_json=caller_instance,
                        actor_id=caller_label,
                        role="dev",
                        tool="task_sys",
                        action=action,
                        args={"task_id": task_id, **args_tail},
                    )

                self._assert_rejection_contract(response)
                self.assertEqual(task_sys.get_task(task_id), before)
                task_sys.record_task_cancel(task_id, {"reason": "Release foreign fixture."})

    def test_task_sys_close_response_exposes_side_cleanup_contract(self) -> None:
        actor_label = "act-dev-task-sys-feedback"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        task_id = self._direct_task(actor_id=actor_id, label="close-feedback")["task_id"]

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={
                "side_thread_id": "thr-side-response",
                "lease_unregistered": True,
                "turn_interrupt_ok": True,
            },
        ), patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            side_effect=AssertionError("non-Demand close must not submit completion attention"),
        ):
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="close",
                args={"task_id": task_id, "summary": "Side completed the feedback fixture."},
            )

        self._assert_write_success_contract(response)
        self.assertEqual(response["task_id"], task_id)
        self.assertEqual(response["task_status"], "completed")
        self.assertEqual(response["processor"], "side")
        self.assertEqual(response["side_thread_id"], "thr-side-response")
        self.assertEqual(response["side_cleanup"]["lease_unregistered"], True)
        self.assertEqual(response["side_cleanup"]["turn_interrupt_ok"], True)
        self.assertEqual(response["execution_result"]["type"], "completion")
        self.assertEqual(response["execution_result"]["processor"], "side")
        self.assertEqual(response["execution_result"]["side_thread_id"], "thr-side-response")
        self._assert_no_retired_task_sys_fields(response)

    def test_demand_task_side_close_submits_terminal_outcome_attention_and_replay_is_safe(self) -> None:
        actor_label = "act-dev-demand-side-close"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        created = task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-side-close",
                "basis_revision": 3,
                "demand_ref": "dref-side-close",
            },
            execution_brief={
                "description": "Complete the selected Demand.",
                "detail": "Perform the bounded side work and record its result.",
            },
        )
        instructions: list[dict[str, object]] = []

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={
                "side_thread_id": "thr-side-demand-close",
                "lease_unregistered": True,
                "turn_interrupt_ok": True,
            },
        ), patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            side_effect=lambda _access, instruction: (
                instructions.append(instruction)
                or {
                    "action": "submit_parent",
                    "task_id": instruction["task_id"],
                    "turn_id": f"turn-outcome-{len(instructions)}",
                }
            ),
        ):
            closed = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="close",
                args={"task_id": created["task_id"], "summary": "Demand snapshot work completed."},
            )
            replay = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="close",
                args={"task_id": created["task_id"], "summary": "Replay."},
            )

        self._assert_write_success_contract(closed)
        self._assert_success_contract(replay)
        self.assertEqual(closed["task_status"], task_sys.COMPLETED)
        self.assertEqual(closed["outcome_attention"]["status"], "submitted")
        self.assertEqual(replay["outcome_attention"]["status"], "submitted")
        self.assertEqual(len(instructions), 2)
        self.assertEqual({instruction["task_id"] for instruction in instructions}, {created["task_id"]})
        self.assertTrue(all(instruction["type"] == "submit_parent" for instruction in instructions))
        self.assertTrue(all(instruction["frame"]["kind"] == "task_sys.outcome_frame" for instruction in instructions))

    def test_demand_task_parent_close_submits_outcome_attention_for_same_task(self) -> None:
        actor_label = "act-dev-demand-parent-close"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        created = task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-parent-close",
                "basis_revision": 1,
                "demand_ref": "dref-parent-close",
            },
            execution_brief={
                "description": "Complete parent-required Demand work.",
                "detail": "Use the same Task through handoff and completion.",
            },
        )
        task_sys.record_side_need_parent(
            created["task_id"],
            {"params": {"parent_frame_context": {"next": "Finish in parent."}}},
        )
        task_sys.record_parent_handoff_started(created["task_id"])

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            return_value={
                "action": "submit_parent",
                "task_id": created["task_id"],
                "turn_id": "turn-parent-outcome-attention",
            },
        ) as execute_instruction:
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="close",
                args={"task_id": created["task_id"], "summary": "Parent work completed."},
            )

        self._assert_write_success_contract(response)
        self.assertEqual(response["processor"], "parent")
        self.assertEqual(response["outcome_attention"]["status"], "submitted")
        instruction = execute_instruction.call_args.args[1]
        self.assertEqual(instruction["task_id"], created["task_id"])
        self.assertEqual(instruction["frame"]["outcome"]["processor"], "parent")

    def test_outcome_attention_failure_is_explicit_while_task_stays_completed(self) -> None:
        actor_label = "act-dev-demand-completion-failure"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        created = task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-completion-failure",
                "basis_revision": 2,
                "demand_ref": "dref-completion-failure",
            },
            execution_brief={
                "description": "Complete work before attention failure.",
                "detail": "The Task truth must remain terminal if parent submission fails.",
            },
        )
        demand_root = self.runtime_state_root / "buddyswitch" / "objects" / "demand-sys"

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={"side_thread_id": "thr-side-attention-failure", "lease_unregistered": True},
        ), patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            side_effect=RuntimeError("parent outcome attention unavailable"),
        ):
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="close",
                args={"task_id": created["task_id"], "summary": "Work itself completed."},
            )

        self._assert_write_success_contract(response)
        self.assertEqual(response["task_status"], task_sys.COMPLETED)
        self.assertEqual(response["outcome_attention"]["status"], "failed")
        self.assertIn("parent outcome attention unavailable", response["outcome_attention"]["error"])
        self.assertEqual(task_sys.get_task(created["task_id"])["status"], task_sys.COMPLETED)
        self.assertFalse(demand_root.exists())

    def test_demand_task_side_cancel_submits_terminal_outcome_attention_and_replay_is_safe(self) -> None:
        actor_label = "act-dev-demand-side-cancel"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        created = task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-side-cancel",
                "basis_revision": 2,
                "demand_ref": "dref-side-cancel",
            },
            execution_brief={
                "description": "Attempt the selected Demand.",
                "detail": "Stop cleanly when the execution route is unavailable.",
            },
        )
        instructions: list[dict[str, object]] = []

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={
                "side_thread_id": "thr-side-demand-cancel",
                "lease_unregistered": True,
                "turn_interrupt_ok": True,
            },
        ), patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            side_effect=lambda _access, instruction: (
                instructions.append(instruction)
                or {
                    "action": "submit_parent",
                    "task_id": instruction["task_id"],
                    "turn_id": f"turn-cancel-outcome-{len(instructions)}",
                }
            ),
        ):
            canceled = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="cancel",
                args={"task_id": created["task_id"], "reason": "Execution route unavailable."},
            )
            replay = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="cancel",
                args={"task_id": created["task_id"], "reason": "Replay."},
            )

        self._assert_write_success_contract(canceled)
        self._assert_success_contract(replay)
        self.assertEqual(canceled["task_status"], task_sys.CANCELED)
        self.assertEqual(canceled["outcome_attention"]["status"], "submitted")
        self.assertEqual(replay["outcome_attention"]["status"], "submitted")
        self.assertEqual(len(instructions), 2)
        self.assertEqual({instruction["task_id"] for instruction in instructions}, {created["task_id"]})
        self.assertTrue(all(instruction["frame"]["status"] == task_sys.CANCELED for instruction in instructions))
        self.assertTrue(all(instruction["frame"]["outcome"]["type"] == "cancellation" for instruction in instructions))

    def test_demand_task_awaiting_parent_cancel_submits_side_owned_outcome_attention(self) -> None:
        actor_label = "act-dev-demand-awaiting-cancel"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        created = task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-awaiting-cancel",
                "basis_revision": 2,
                "demand_ref": "dref-awaiting-cancel",
            },
            execution_brief={
                "description": "Attempt a Demand that needs parent resources.",
                "detail": "Cancel cleanly if the parent handoff cannot start.",
            },
        )
        task_sys.record_side_need_parent(
            created["task_id"],
            {"params": {"parent_frame_context": {"next": "Finish in parent."}}},
        )
        instructions: list[dict[str, Any]] = []

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={"side_thread_id": None, "lease_unregistered": False},
        ), patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            side_effect=lambda _access, instruction: (
                instructions.append(instruction)
                or {
                    "action": "submit_parent",
                    "task_id": instruction["task_id"],
                    "turn_id": "turn-awaiting-cancel-outcome",
                }
            ),
        ):
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="cancel",
                args={"task_id": created["task_id"], "reason": "Parent handoff could not start."},
            )

        self._assert_write_success_contract(response)
        self.assertEqual(response["task_status"], task_sys.CANCELED)
        self.assertEqual(response["processor"], "side")
        self.assertEqual(response["outcome_attention"]["status"], "submitted")
        self.assertEqual(len(instructions), 1)
        self.assertEqual(instructions[0]["frame"]["outcome"]["processor"], "side")

    def test_cancel_outcome_attention_failure_is_explicit_while_task_stays_canceled(self) -> None:
        actor_label = "act-dev-demand-cancel-failure"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        created = task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-cancel-failure",
                "basis_revision": 1,
                "demand_ref": "dref-cancel-failure",
            },
            execution_brief={
                "description": "Attempt work before cancellation.",
                "detail": "Keep terminal Task truth when outcome submission fails.",
            },
        )

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={"side_thread_id": "thr-side-cancel-failure", "lease_unregistered": True},
        ), patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            side_effect=RuntimeError("parent canceled outcome attention unavailable"),
        ):
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="cancel",
                args={"task_id": created["task_id"], "reason": "Execution cannot continue."},
            )

        self._assert_write_success_contract(response)
        self.assertEqual(response["task_status"], task_sys.CANCELED)
        self.assertEqual(response["outcome_attention"]["status"], "failed")
        self.assertIn("parent canceled outcome attention unavailable", response["outcome_attention"]["error"])
        self.assertEqual(task_sys.get_task(created["task_id"])["status"], task_sys.CANCELED)

    def test_task_sys_cancel_response_exposes_side_cleanup_contract(self) -> None:
        actor_label = "act-dev-task-sys-cancel"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        task_id = self._direct_task(actor_id=actor_id, label="cancel")["task_id"]

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={
                "side_thread_id": "thr-side-cancel",
                "lease_unregistered": True,
                "turn_interrupt_ok": True,
            },
        ), patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            return_value={"action": "submit_parent", "turn_id": "turn-cancel-outcome"},
        ):
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="cancel",
                args={"task_id": task_id, "reason": "Request superseded."},
            )

        self._assert_write_success_contract(response)
        self.assertEqual(response["task_id"], task_id)
        self.assertEqual(response["task_status"], "canceled")
        self.assertEqual(response["processor"], "side")
        self.assertEqual(response["side_thread_id"], "thr-side-cancel")
        self.assertEqual(response["side_cleanup"]["lease_unregistered"], True)
        self.assertEqual(response["execution_result"]["type"], "cancellation")
        self.assertEqual(response["execution_result"]["reason"], "Request superseded.")
        self.assertEqual(response["outcome_attention"]["status"], "submitted")
        self._assert_no_retired_task_sys_fields(response)

    def test_task_sys_list_and_get_responses_expose_canonical_status_and_execution(self) -> None:
        actor_label = "act-dev-task-sys-read-contract"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        task_id = self._direct_task(actor_id=actor_id, label="read-contract")["task_id"]
        listed = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role="dev",
            tool="task_sys",
            action="list",
            args={"status": "all"},
        )
        self._assert_success_contract(listed)
        rows = listed.get("tasks")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        task_row = next(row for row in rows if isinstance(row, dict) and row.get("task_id") == task_id)
        self.assertEqual(task_row["status"], "in_progress.side_processing")
        self.assertNotIn("task_desc", task_row)
        self.assertNotIn("task_relation", task_row)
        self.assertEqual(task_row["execution"]["processor"], "side")
        self._assert_no_retired_task_sys_fields(task_row)

        fetched = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role="dev",
            tool="task_sys",
            action="get",
            args={"task_id": task_id},
        )
        self._assert_success_contract(fetched)
        task = fetched.get("task")
        self.assertIsInstance(task, dict, msg=fetched)
        assert isinstance(task, dict)
        self.assertEqual(task["status"], "in_progress.side_processing")
        self.assertNotIn("task_desc", task)
        self.assertNotIn("task_relation", task)
        self.assertEqual(task["execution"]["processor"], "side")
        self._assert_no_retired_task_sys_fields(task)

    def test_retired_task_analysis_action_is_rejected_without_state_change(self) -> None:
        actor_label = "act-dev-task-sys-analysis"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        task_id = self._direct_task(actor_id=actor_id, label="analysis")["task_id"]
        before = task_sys.get_task(task_id)

        response = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role="dev",
            tool="task_sys",
            action="update_task_analysis",
            args={
                "task_id": task_id,
                "task_desc": "Analyze source",
                "task_relation": {"kind": "independent", "target_task_id": None},
            },
        )

        self._assert_rejection_contract(response)
        self.assertIn("not supported", response["human_summary"])
        self.assertEqual(task_sys.get_task(task_id), before)

    def test_task_sys_need_parent_response_exposes_execution_handoff_contract(self) -> None:
        actor_label = "act-dev-task-sys-handoff"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        task_id = self._direct_task(actor_id=actor_id, label="handoff")["task_id"]
        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            return_value={"action": "submit_parent", "task_id": task_id, "turn_id": "turn-parent-response"},
        ), patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={
                "side_thread_id": "thr-side-handoff",
                "lease_unregistered": True,
                "turn_interrupt_ok": True,
            },
        ):
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="need_parent",
                args={
                    "task_id": task_id,
                    "params": {
                        "parent_frame_context": {"next": "Handle in parent."},
                        "interrupt": False,
                        "ordering": {"priority": "normal"},
                    },
                },
            )

        self._assert_write_success_contract(response)
        self.assertEqual(response["task_id"], task_id)
        self.assertEqual(response["task_status"], "in_progress.parent_processing")
        self.assertEqual(response["execution_handoff"]["parent_frame_context"], {"next": "Handle in parent."})
        self.assertEqual(response["execution_handoff"]["side_thread_id"], "thr-side-handoff")
        self.assertEqual(response["execution_handoff"]["cleanup"]["lease_unregistered"], True)
        self.assertEqual(response["parent_runtime"]["action"], "submit_parent")
        self._assert_no_retired_task_sys_fields(response)

    def test_task_sys_need_parent_submit_failure_keeps_same_task_awaiting_parent(self) -> None:
        actor_label = "act-dev-task-sys-handoff-failure"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        task_id = self._direct_task(actor_id=actor_id, label="handoff-failure")["task_id"]
        task_ids_before = {row["id"] for row in task_sys.list_tasks()}

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "execute_instruction",
            autospec=True,
            side_effect=RuntimeError("parent submit unavailable"),
        ), patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={
                "side_thread_id": "thr-side-handoff-failure",
                "lease_unregistered": True,
                "turn_interrupt_ok": True,
            },
        ):
            response = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="need_parent",
                args={
                    "task_id": task_id,
                    "params": {"parent_frame_context": {"next": "Retry parent submit."}},
                },
            )

        self.assertFalse(response["ok"], msg=response)
        record = task_sys.get_task(task_id)
        self.assertEqual(record["status"], "in_progress.awaiting_parent")
        self.assertEqual(record["execution"]["handoff"]["side_thread_id"], "thr-side-handoff-failure")
        self.assertEqual(record["execution"]["handoff"]["cleanup"]["lease_unregistered"], True)
        self.assertEqual({row["id"] for row in task_sys.list_tasks()}, task_ids_before)
