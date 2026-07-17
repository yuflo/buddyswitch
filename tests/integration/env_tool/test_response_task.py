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
from env.domain import task_sys  # noqa: E402
from env.tool_runtime import registry as tool_catalog  # noqa: E402
from env.tool_runtime import results as tool_results  # noqa: E402
from env.tool_runtime import context as runtime_context  # noqa: E402
import env.tools.search._impl as search_impl  # noqa: E402
import turn_runtime  # noqa: E402
from tests.integration.env_tool._response_case import EnvToolResponseCase

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvToolTaskResponseTests(EnvToolResponseCase):
    def test_task_sys_close_response_exposes_side_cleanup_contract(self) -> None:
        actor_label = "act-dev-task-sys-feedback"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        task_id = task_sys.ingest(
            {
                "source": {"type": "test.feedback", "ref": {"id": "task-sys-close-feedback"}},
                "actor_target": {"actor_id": actor_id, "role_id": "dev"},
                "context": {"fixture": "task sys close feedback"},
            }
        )["task_id"]

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={
                "side_thread_id": "thr-side-response",
                "lease_unregistered": True,
                "turn_interrupt_ok": True,
            },
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

    def test_task_sys_cancel_response_exposes_side_cleanup_contract(self) -> None:
        actor_label = "act-dev-task-sys-cancel"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        task_id = task_sys.ingest(
            {
                "source": {"type": "test.cancel", "ref": {"id": "task-sys-cancel"}},
                "actor_target": {"actor_id": actor_id, "role_id": "dev"},
                "context": {"fixture": "task sys cancel"},
            }
        )["task_id"]

        with patch.object(
            runtime_context.TaskSysRuntimeAccess,
            "cleanup_side_lease",
            autospec=True,
            return_value={
                "side_thread_id": "thr-side-cancel",
                "lease_unregistered": True,
                "turn_interrupt_ok": True,
            },
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
        self._assert_no_retired_task_sys_fields(response)

    def test_task_sys_list_and_get_responses_expose_canonical_status_and_execution(self) -> None:
        actor_label = "act-dev-task-sys-read-contract"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        task_id = task_sys.ingest(
            {
                "source": {"type": "test.read_contract", "ref": {"id": "task-sys-read-contract"}},
                "actor_target": {"actor_id": actor_id, "role_id": "dev"},
                "context": {"fixture": "task sys read contract"},
            }
        )["task_id"]
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
        task_id = task_sys.ingest(
            {
                "source": {"type": "test.analysis", "ref": {"id": "task-sys-analysis"}},
                "actor_target": {"actor_id": actor_id, "role_id": "dev"},
                "context": {"fixture": "task sys analysis"},
            }
        )["task_id"]
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
        task_id = task_sys.ingest(
            {
                "source": {"type": "test.handoff", "ref": {"id": "task-sys-handoff"}},
                "actor_target": {"actor_id": actor_id, "role_id": "dev"},
                "context": {"fixture": "task sys handoff"},
            }
        )["task_id"]
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
        task_id = task_sys.ingest(
            {
                "source": {"type": "test.handoff_failure", "ref": {"id": "task-sys-handoff-failure"}},
                "actor_target": {"actor_id": actor_id, "role_id": "dev"},
                "context": {"fixture": "task sys handoff failure"},
            }
        )["task_id"]
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
