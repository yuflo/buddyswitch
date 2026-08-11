"""Real Web Actor proof for Demand -> Task -> native Goal -> Demand reconciliation."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from typing import Any
import unittest
from unittest import mock
from urllib import error as urllib_error
from urllib import request as urllib_request

from tests.support.paths import REPO_ROOT
from tests.support.processes import CleanupReport, ResourceLedger, run_process
from tests.system.goal_mode.support import (
    ResponseSpec,
    SequencedResponsesServer,
    assistant_message,
    function_call,
    response_completed,
    response_created,
)
import buddyswitch.foundation.app_server.runtime as app_server
from buddyswitch.foundation.daemon import central_process
from buddyswitch.foundation.daemon import central_service
from buddyswitch.foundation.actor_runtime import codex_runtime
from buddyswitch.foundation.daemon import instance
import buddyswitch.foundation.process_runtime.process_identity as process_identity


LAUNCHER = REPO_ROOT / "buddyswitch-codex"
TIMEOUT_SECONDS = 60.0
MULTI_DEMAND_PAUSE_SECONDS = 180.0
POLL_SECONDS = 0.05
REQUEST_TEXT = (
    "Reply with exactly: Phase 2 native Goal delivery verified. "
    "Treat this as one bounded need and finish it through the managed Task."
)
REPLY_TEXT = "Phase 2 native Goal delivery verified."
SUPPLEMENT_TEXT = (
    "Supplement the existing Phase 2 need: the durable reply must also confirm "
    "the exact originating message binding."
)
DEMAND_B_TEXT = "Independently deliver a short follow-up verification checklist."
ORDINARY_TEXT = "Thanks, no additional work is needed from this acknowledgement."
DEMAND_C_TEXT = "Independently prepare a temporary rollback note."
CANCEL_C_TEXT = "Withdraw the temporary rollback-note need completely."


def _task_objective(message_id: str) -> str:
    return (
        f"Originating Web message_id: {message_id}. "
        f"Reply with exactly '{REPLY_TEXT}' using message__send with reply_to "
        f"equal to {message_id}. Retain the returned reply message id and call "
        "message__get for that reply; verify its exact content and reply_to. "
        "Only after that durable user-facing delivery is verified, call native "
        "update_goal with status complete. Do not reconcile the Demand or select "
        "later work."
    )


def _later_task_objective() -> str:
    return (
        "Deliver the independent follow-up verification checklist with durable "
        "evidence. Do not reconcile any Demand or select later work."
    )


def _first_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _encode_demand_ref(demand_id: str, revision: int) -> str:
    body = json.dumps(
        {"demand_id": demand_id, "revision": revision},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    checksum = hashlib.sha256(body).hexdigest()[:16]
    return f"dref-{encoded}.{checksum}"


def _function_response(
    response_id: str,
    *,
    tool_name: str,
    arguments: dict[str, Any],
) -> ResponseSpec:
    return ResponseSpec.sse(
        response_created(response_id),
        function_call(f"call-{response_id}", tool_name, arguments),
        response_completed(response_id),
    )


def _assistant_response(response_id: str, text: str) -> ResponseSpec:
    return ResponseSpec.sse(
        response_created(response_id),
        assistant_message(f"msg-{response_id}", text),
        response_completed(response_id),
    )


def _custom_tool_response(
    response_id: str,
    *,
    tool_name: str,
    input_text: str,
) -> ResponseSpec:
    return ResponseSpec.sse(
        response_created(response_id),
        {
            "type": "response.output_item.done",
            "item": {
                "type": "custom_tool_call",
                "call_id": f"call-{response_id}",
                "name": tool_name,
                "input": input_text,
            },
        },
        response_completed(response_id),
    )


class ProductFlowController:
    """Deterministic model decisions while all product tools execute for real."""

    def __init__(self, *, state_root: Path) -> None:
        self.state_root = state_root
        self.stage = 0
        self.original_message_id: str | None = None
        self.goal_pause_reached = threading.Event()
        self.allow_goal_delivery = threading.Event()
        self.reply_pause_reached = threading.Event()
        self.allow_goal_complete = threading.Event()
        self.reconciliation_pause_reached = threading.Event()
        self.allow_reconciliation = threading.Event()
        self.later_goal_pause_reached = threading.Event()
        self.allow_later_goal_turn = threading.Event()
        self.failed = threading.Event()
        self.failure: str | None = None
        self.trace: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    @staticmethod
    def _tool_names(request_record: dict[str, Any]) -> list[str]:
        body = request_record.get("body")
        if not isinstance(body, dict):
            return []
        tool_groups: list[list[Any]] = []
        tools = body.get("tools")
        if isinstance(tools, list):
            tool_groups.append(tools)
        input_items = body.get("input")
        if isinstance(input_items, list):
            for item in input_items:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "additional_tools"
                    and isinstance(item.get("tools"), list)
                ):
                    tool_groups.append(item["tools"])
        names: list[str] = []
        for group in tool_groups:
            for tool in group:
                if not isinstance(tool, dict):
                    continue
                name = tool.get("name")
                if isinstance(name, str) and name not in names:
                    names.append(name)
        return names

    @staticmethod
    def _model_visible_input(request_record: dict[str, Any]) -> str:
        body = request_record.get("body")
        if not isinstance(body, dict):
            return ""
        return json.dumps(
            body.get("input"),
            ensure_ascii=False,
            sort_keys=True,
        )

    def _invoke(
        self,
        request_record: dict[str, Any],
        response_id: str,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        namespace: str | None = None,
    ) -> ResponseSpec:
        names = self._tool_names(request_record)
        direct = [
            name
            for name in names
            if name == tool_name
            or name.endswith(f"__{tool_name}")
            or tool_name in name
        ]
        if len(direct) == 1:
            return _function_response(
                response_id,
                tool_name=direct[0],
                arguments=arguments,
            )
        if "exec" in names:
            target = (
                f"tools.{namespace}__{tool_name}"
                if namespace is not None
                else f"tools.{tool_name}"
            )
            code = (
                f"var result = await {target}("
                f"{json.dumps(arguments, ensure_ascii=True, separators=(',', ':'))}"
                ");\ntext(JSON.stringify(result));"
            )
            return _custom_tool_response(
                response_id,
                tool_name="exec",
                input_text=code,
            )
        message = (
            f"expected direct {tool_name!r} or Code Mode exec; "
            f"observed={names!r}"
        )
        self.failure = message
        self.failed.set()
        raise AssertionError(message)

    def _demands(self) -> list[dict[str, Any]]:
        candidates = sorted(
            (
                self.state_root
                / "buddyswitch"
                / "objects"
                / "demand-sys"
                / "actors"
            ).glob("*.json")
        )
        if len(candidates) != 1:
            raise AssertionError(f"expected one Demand aggregate, observed={candidates!r}")
        aggregate = json.loads(candidates[0].read_text(encoding="utf-8"))
        demands = aggregate.get("demands")
        if not isinstance(demands, dict):
            raise AssertionError(f"expected Demand records, observed={demands!r}")
        return [dict(row) for row in demands.values() if isinstance(row, dict)]

    def _demand(self, description_fragment: str) -> dict[str, Any]:
        matches = [
            row
            for row in self._demands()
            if description_fragment.lower()
            in str(row.get("description", "")).lower()
        ]
        if len(matches) != 1:
            raise AssertionError(
                f"expected one Demand containing {description_fragment!r}, "
                f"observed={self._demands()!r}"
            )
        return matches[0]

    def _assert_side_surface(self, request_record: dict[str, Any]) -> None:
        visible = self._model_visible_input(request_record)
        names = self._tool_names(request_record)
        if (
            "<name>demand-triage</name>" not in visible
            or "demand_sys__resolve_inbound" not in visible
            or "exec" not in names
            or any(
                forbidden in name
                for name in names
                for forbidden in (
                    "demand_sys__complete",
                    "task_sys__create",
                    "task_sys__cancel",
                )
            )
        ):
            raise AssertionError(
                "Demand side did not receive the exact triage Skill/tool surface: "
                f"tools={names!r} visible={visible!r}"
            )

    def _assert_parent_surface(self, request_record: dict[str, Any]) -> None:
        visible = self._model_visible_input(request_record)
        names = self._tool_names(request_record)
        if (
            "<name>demand-orchestration</name>" not in visible
            or "exec" not in names
            or any("demand_sys__resolve_inbound" in name for name in names)
            or any(
                forbidden in name
                for name in names
                for forbidden in (
                    "demand_sys__create",
                    "demand_sys__revise",
                    "demand_sys__cancel",
                )
            )
        ):
            raise AssertionError(
                "Parent did not receive the exact orchestration Skill/tool surface: "
                f"tools={names!r} visible={visible!r}"
            )

    def _assert_goal_surface(self, request_record: dict[str, Any]) -> None:
        names = self._tool_names(request_record)
        if (
            "exec" not in names
            or any(
                forbidden in name
                for name in names
                for forbidden in (
                    "demand_sys__resolve_inbound",
                    "demand_sys__create",
                    "demand_sys__revise",
                    "demand_sys__cancel",
                )
            )
        ):
            raise AssertionError(
                "Goal request exposed a Demand creation/change/cancel path: "
                f"tools={names!r}"
            )

    def _task(self) -> dict[str, Any]:
        candidates = sorted(
            (
                self.state_root
                / "buddyswitch"
                / "objects"
                / "task-sys"
                / "tasks"
            ).glob("*.json")
        )
        if len(candidates) != 1:
            raise AssertionError(f"expected one Task, observed={candidates!r}")
        return json.loads(candidates[0].read_text(encoding="utf-8"))

    def _reply(self) -> dict[str, Any]:
        if self.original_message_id is None:
            raise AssertionError("originating Web message id was not captured")
        messages_dir = self.state_root / "im" / "messages"
        replies: list[dict[str, Any]] = []
        for path in sorted(messages_dir.glob("*.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("reply_to") == self.original_message_id:
                replies.append(row)
        if len(replies) != 1:
            raise AssertionError(
                "expected exactly one durable reply to "
                f"{self.original_message_id}, observed={replies!r}"
            )
        return replies[0]

    def _next_stage(self, request_record: dict[str, Any]) -> int:
        with self._lock:
            stage = self.stage
            self.stage += 1
            self.trace.append(
                {
                    "stage": stage,
                    "tools": self._tool_names(request_record),
                }
            )
            return stage

    def respond(self, request_record: dict[str, Any], _request_index: int) -> ResponseSpec:
        stage = self._next_stage(request_record)
        response_id = f"product-flow-{stage:02d}"

        if stage == 0:
            return _assistant_response(response_id, "Actor bootstrap complete.")
        if stage == 1:
            self._assert_side_surface(request_record)
            # This controller authors a deterministic decision to prove the
            # product plumbing. It does not prove real-model semantic
            # classification.
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__resolve_inbound",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "decision": "create",
                    "reason": "The Web request declares one independent bounded need.",
                    "demand_ref": None,
                    "description": "Return the Phase 2 native Goal verification reply.",
                    "detail": REQUEST_TEXT,
                    "reply_content": None,
                },
            )
        if stage == 2:
            self._assert_side_surface(request_record)
            return _assistant_response(response_id, "Demand ingress committed.")
        if stage == 3:
            self._assert_parent_surface(request_record)
            return self._invoke(
                request_record,
                response_id,
                tool_name="task_sys__list",
                namespace="mcp__buddyswitch_env",
                arguments={"status": "terminal"},
            )
        if stage == 4:
            self._assert_parent_surface(request_record)
            return self._invoke(
                request_record,
                response_id,
                tool_name="task_sys__list",
                namespace="mcp__buddyswitch_env",
                arguments={"status": "active"},
            )
        if stage == 5:
            self._assert_parent_surface(request_record)
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__list",
                namespace="mcp__buddyswitch_env",
                arguments={"state": "live"},
            )
        if stage == 6:
            self._assert_parent_surface(request_record)
            demand = self._demand("Phase 2")
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__get",
                namespace="mcp__buddyswitch_env",
                arguments={"demand_id": demand["id"]},
            )
        if stage == 7:
            self._assert_parent_surface(request_record)
            demand = self._demand("Phase 2")
            if self.original_message_id is None:
                return ResponseSpec.server_error(
                    "originating Web message id was not captured"
                )
            return self._invoke(
                request_record,
                response_id,
                tool_name="task_sys__create",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "demand_ref": _encode_demand_ref(
                        str(demand["id"]),
                        int(demand["revision"]),
                    ),
                    "objective": _task_objective(self.original_message_id),
                    "selection_reason": (
                        "This is the only live Demand and the Actor Task slot is empty."
                    ),
                },
            )
        if stage == 8:
            self._assert_parent_surface(request_record)
            return _assistant_response(response_id, "The native Goal now owns execution.")
        if stage == 9:
            self._assert_goal_surface(request_record)
            return _assistant_response(
                response_id,
                "The reply has not been delivered yet, so the Goal remains active.",
            )
        if stage == 10:
            self._assert_goal_surface(request_record)
            self.goal_pause_reached.set()
            if not self.allow_goal_delivery.wait(MULTI_DEMAND_PAUSE_SECONDS):
                return ResponseSpec.server_error("test did not release Goal delivery")
            if self.original_message_id is None:
                return ResponseSpec.server_error("originating Web message id was not captured")
            return self._invoke(
                request_record,
                response_id,
                tool_name="message__send",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "content": REPLY_TEXT,
                    "reply_to": self.original_message_id,
                },
            )
        if stage == 11:
            self._assert_side_surface(request_record)
            demand = self._demand("Phase 2")
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__resolve_inbound",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "decision": "merge_intake",
                    "reason": "This supplement tightens the same delivery obligation.",
                    "demand_ref": _encode_demand_ref(
                        str(demand["id"]),
                        int(demand["revision"]),
                    ),
                    "description": (
                        "Return the Phase 2 native Goal verification reply with exact "
                        "originating-message binding."
                    ),
                    "detail": f"{REQUEST_TEXT} {SUPPLEMENT_TEXT}",
                    "reply_content": None,
                },
            )
        if stage == 12:
            self._assert_side_surface(request_record)
            return _assistant_response(response_id, "Demand A supplement merged.")
        if stage == 13:
            self._assert_side_surface(request_record)
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__resolve_inbound",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "decision": "create",
                    "reason": "This is an independent follow-up obligation.",
                    "demand_ref": None,
                    "description": "Deliver an independent follow-up verification checklist.",
                    "detail": DEMAND_B_TEXT,
                    "reply_content": None,
                },
            )
        if stage == 14:
            self._assert_side_surface(request_record)
            return _assistant_response(response_id, "Independent Demand B committed.")
        if stage == 15:
            self._assert_side_surface(request_record)
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__resolve_inbound",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "decision": "no_action_needed",
                    "reason": "This acknowledgement creates no unmet obligation.",
                    "demand_ref": None,
                    "description": None,
                    "detail": None,
                    "reply_content": None,
                },
            )
        if stage == 16:
            self._assert_side_surface(request_record)
            return _assistant_response(response_id, "Ordinary inbound settled.")
        if stage == 17:
            self._assert_side_surface(request_record)
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__resolve_inbound",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "decision": "create",
                    "reason": "This is a temporary independent obligation.",
                    "demand_ref": None,
                    "description": "Prepare a temporary rollback note.",
                    "detail": DEMAND_C_TEXT,
                    "reply_content": None,
                },
            )
        if stage == 18:
            self._assert_side_surface(request_record)
            return _assistant_response(response_id, "Temporary Demand C committed.")
        if stage == 19:
            self._assert_side_surface(request_record)
            demand = self._demand("temporary rollback")
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__resolve_inbound",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "decision": "cancel",
                    "reason": "The requester explicitly withdrew this temporary need.",
                    "demand_ref": _encode_demand_ref(
                        str(demand["id"]),
                        int(demand["revision"]),
                    ),
                    "description": None,
                    "detail": None,
                    "reply_content": None,
                },
            )
        if stage == 20:
            self._assert_side_surface(request_record)
            return _assistant_response(response_id, "Demand C canceled.")
        if stage == 21:
            self._assert_goal_surface(request_record)
            reply = self._reply()
            return self._invoke(
                request_record,
                response_id,
                tool_name="message__get",
                namespace="mcp__buddyswitch_env",
                arguments={"message_id": reply["id"]},
            )
        if stage == 22:
            self._assert_goal_surface(request_record)
            self.reply_pause_reached.set()
            if not self.allow_goal_complete.wait(TIMEOUT_SECONDS):
                return ResponseSpec.server_error("test did not release Goal completion")
            return self._invoke(
                request_record,
                response_id,
                tool_name="update_goal",
                arguments={"status": "complete"},
            )
        if stage == 23:
            self._assert_goal_surface(request_record)
            return _assistant_response(response_id, "Delivery and native Goal are complete.")
        if stage == 24:
            self._assert_parent_surface(request_record)
            self.reconciliation_pause_reached.set()
            if not self.allow_reconciliation.wait(TIMEOUT_SECONDS):
                return ResponseSpec.server_error(
                    "test did not release Demand reconciliation"
                )
            return self._invoke(
                request_record,
                response_id,
                tool_name="task_sys__list",
                namespace="mcp__buddyswitch_env",
                arguments={"status": "terminal"},
            )
        if stage == 25:
            self._assert_parent_surface(request_record)
            task = self._task()
            return self._invoke(
                request_record,
                response_id,
                tool_name="task_sys__get",
                namespace="mcp__buddyswitch_env",
                arguments={"task_id": task["id"]},
            )
        if stage == 26:
            self._assert_parent_surface(request_record)
            demand = self._demand("Phase 2")
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__get",
                namespace="mcp__buddyswitch_env",
                arguments={"demand_id": demand["id"]},
            )
        if stage == 27:
            self._assert_parent_surface(request_record)
            reply = self._reply()
            return self._invoke(
                request_record,
                response_id,
                tool_name="message__get",
                namespace="mcp__buddyswitch_env",
                arguments={"message_id": reply["id"]},
            )
        if stage == 28:
            self._assert_parent_surface(request_record)
            demand = self._demand("Phase 2")
            task = self._task()
            reply = self._reply()
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__complete",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "demand_ref": _encode_demand_ref(
                        str(demand["id"]),
                        int(demand["revision"]),
                    ),
                    "summary": (
                        "The exact requested reply was delivered to the originating "
                        "Web conversation and the bound native Goal completed."
                    ),
                    "evidence_refs": [
                        {
                            "type": "task_sys.task",
                            "ref": {"task_id": task["id"]},
                        },
                        {
                            "type": "im.message.reply",
                            "ref": {
                                "id": reply["id"],
                                "key": f"reply_to:{self.original_message_id}",
                            },
                        },
                    ],
                },
            )
        if stage == 29:
            self._assert_parent_surface(request_record)
            return self._invoke(
                request_record,
                response_id,
                tool_name="task_sys__list",
                namespace="mcp__buddyswitch_env",
                arguments={"status": "active"},
            )
        if stage == 30:
            self._assert_parent_surface(request_record)
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__list",
                namespace="mcp__buddyswitch_env",
                arguments={"state": "live"},
            )
        if stage == 31:
            self._assert_parent_surface(request_record)
            demand = self._demand("follow-up verification checklist")
            return self._invoke(
                request_record,
                response_id,
                tool_name="demand_sys__get",
                namespace="mcp__buddyswitch_env",
                arguments={"demand_id": demand["id"]},
            )
        if stage == 32:
            self._assert_parent_surface(request_record)
            demand = self._demand("follow-up verification checklist")
            return self._invoke(
                request_record,
                response_id,
                tool_name="task_sys__create",
                namespace="mcp__buddyswitch_env",
                arguments={
                    "demand_ref": _encode_demand_ref(
                        str(demand["id"]),
                        int(demand["revision"]),
                    ),
                    "objective": _later_task_objective(),
                    "selection_reason": (
                        "Demand B is the only remaining live Demand after Demand A "
                        "completion and Demand C cancellation."
                    ),
                },
            )
        if stage == 33:
            self._assert_parent_surface(request_record)
            return _assistant_response(
                response_id,
                "Demand A reconciled and Demand B selected into the empty Task slot.",
            )
        if stage == 34:
            self._assert_goal_surface(request_record)
            return _assistant_response(
                response_id,
                "The later Demand B now owns the active native Goal.",
            )
        if stage == 35:
            self._assert_goal_surface(request_record)
            self.later_goal_pause_reached.set()
            if not self.allow_later_goal_turn.wait(TIMEOUT_SECONDS):
                return ResponseSpec.server_error(
                    "test did not release later Goal turn"
                )
            return _assistant_response(
                response_id,
                "The later Demand B remains active for future execution.",
            )
        return ResponseSpec.server_error(f"unexpected product-flow model stage {stage}")


class NativeGoalProductFlowSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = ResourceLedger.from_environment()
        self.runtime = codex_runtime.resolve_codex_runtime()
        self.root = Path(
            tempfile.mkdtemp(prefix="buddyswitch-phase2-product-")
        ).resolve()
        self.ledger.register_path(self.root, path_type="phase2_product_root")
        self.source_home = self.root / "source-home"
        self.source_codex_home = self.root / "source-codex-home"
        self.shared_root = self.source_home / ".codex-buddyswitch"
        self.state_root = self.shared_root / "state"
        self.source_home.mkdir()
        self.source_codex_home.mkdir()
        self.shared_root.mkdir()
        self.state_root.mkdir()
        self.ledger.register_cleanup_action(
            cleanup_strategy="central_daemon_stop",
            cleanup_args={"shared_root": str(self.shared_root)},
        )
        (self.source_codex_home / "auth.json").write_text(
            json.dumps(
                {
                    "auth_mode": "apikey",
                    "openai_api_key": "buddyswitch-product-flow",
                    "tokens": None,
                    "last_refresh": None,
                    "agent_identity": None,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.controller = ProductFlowController(state_root=self.state_root)
        self.responses = SequencedResponsesServer(
            [self.controller.respond for _index in range(40)]
        )
        self.responses.start()
        self.codex_wrapper = self.root / "codex-product-test"
        model_provider = (
            '{ name = "BuddySwitch native Goal product test", '
            f'base_url = "{self.responses.base_url}/v1", '
            'wire_api = "responses", request_max_retries = 0, '
            'stream_max_retries = 0, supports_websockets = false }'
        )
        self.codex_wrapper.write_text(
            "\n".join(
                (
                    "#!/usr/bin/env python3",
                    "import os",
                    "import sys",
                    f"REAL_CODEX = {str(self.runtime.executable)!r}",
                    "os.execv(",
                    "    REAL_CODEX,",
                    "    [",
                    "        REAL_CODEX,",
                    '        "-c",',
                    '        \'model="mock-model"\',',
                    '        "-c",',
                    '        \'model_provider="mock_provider"\',',
                    '        "-c",',
                    f"        {'model_providers.mock_provider=' + model_provider!r},",
                    "        *sys.argv[1:],",
                    "    ],",
                    ")",
                    "",
                )
            ),
            encoding="utf-8",
        )
        self.codex_wrapper.chmod(0o755)
        self.port = _first_local_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.http = urllib_request.build_opener(urllib_request.ProxyHandler({}))
        self.web_log = self.root / "web.log"
        self.env = dict(os.environ)
        self.env.update(
            {
                "HOME": str(self.source_home),
                "BUDDYSWITCH_SOURCE_HOME": str(self.source_home),
                "BUDDYSWITCH_SOURCE_CODEX_HOME": str(self.source_codex_home),
                "BUDDYSWITCH_SHARED_ROOT": str(self.shared_root),
                "BUDDYSWITCH_STATE_ROOT": str(self.state_root),
                "BUDDYSWITCH_CODEX_BIN": str(self.codex_wrapper),
                "OPENAI_API_KEY": "buddyswitch-product-flow",
                "OPENAI_BASE_URL": f"{self.responses.base_url}/v1",
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
                "RUST_LOG": "warn",
            }
        )
        self.actor_id: str | None = None
        self.web_process: subprocess.Popen[str] | None = None
        self._closed = False
        self.cleanup_report: CleanupReport | None = None
        self.addCleanup(self._cleanup)

    def _http(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = (
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else None
        )
        req = urllib_request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with self.http.open(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AssertionError(f"{method} {path} failed: {exc.code} {detail}") from exc

    def _wait_until(self, predicate: Any, description: str) -> Any:
        deadline = time.monotonic() + TIMEOUT_SECONDS
        last: Any = None
        while time.monotonic() < deadline:
            try:
                last = predicate()
            except (
                FileNotFoundError,
                json.JSONDecodeError,
                KeyError,
                OSError,
                ValueError,
            ) as exc:
                last = exc
            else:
                if last:
                    return last
            if self.web_process is not None and self.web_process.poll() is not None:
                raise AssertionError(
                    f"Web exited early ({self.web_process.returncode}):\n"
                    f"{self.web_log.read_text(encoding='utf-8', errors='replace')}"
                )
            time.sleep(POLL_SECONDS)
        raise AssertionError(
            f"timed out waiting for {description}; last={last!r}; "
            f"model_trace={self.controller.trace!r}"
        )

    def _start_web(self) -> None:
        with self.web_log.open("w", encoding="utf-8") as log_handle:
            self.web_process = self.ledger.start_process(
                [
                    str(LAUNCHER),
                    "web",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(self.port),
                ],
                cwd=REPO_ROOT,
                env=self.env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )
        self._wait_until(
            lambda: self._http("GET", "/api/health").get("ok"),
            "BuddySwitch Web health",
        )

    def _wait_operation(self, operation_id: str) -> dict[str, Any]:
        def read_terminal() -> dict[str, Any] | None:
            operation = self._http(
                "GET",
                f"/api/operations/{operation_id}",
            )["operation"]
            status = operation.get("status")
            if status == "failed":
                raise AssertionError(
                    f"Web lifecycle operation failed: {operation!r}\n"
                    f"web log:\n{self.web_log.read_text(encoding='utf-8', errors='replace')}"
                )
            return operation if status == "succeeded" else None

        return self._wait_until(read_terminal, f"operation {operation_id}")

    def _demand_aggregate(self) -> dict[str, Any]:
        candidates = sorted(
            (
                self.state_root
                / "buddyswitch"
                / "objects"
                / "demand-sys"
                / "actors"
            ).glob("*.json")
        )
        if len(candidates) != 1:
            return {}
        return json.loads(candidates[0].read_text(encoding="utf-8"))

    def _demands(self) -> list[dict[str, Any]]:
        demands = self._demand_aggregate().get("demands")
        if not isinstance(demands, dict):
            return []
        return [dict(row) for row in demands.values() if isinstance(row, dict)]

    def _demand(self, fragment: str) -> dict[str, Any] | None:
        matches = [
            row
            for row in self._demands()
            if fragment.lower() in str(row.get("description", "")).lower()
        ]
        return matches[0] if len(matches) == 1 else None

    def _tasks(self) -> list[dict[str, Any]]:
        candidates = sorted(
            (
                self.state_root
                / "buddyswitch"
                / "objects"
                / "task-sys"
                / "tasks"
            ).glob("*.json")
        )
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in candidates
        ]

    def _single_task(self) -> dict[str, Any] | None:
        tasks = self._tasks()
        return tasks[0] if len(tasks) == 1 else None

    def _send_inbound(self, content: str) -> dict[str, Any]:
        if self.actor_id is None:
            raise AssertionError("Actor id is not available")
        sent = self._http(
            "POST",
            "/api/im/messages",
            {
                "target_identity_id": self.actor_id,
                "content": content,
                "reply_to": None,
            },
        )
        self.assertEqual(sent["delivery_status"], "accepted", msg=sent)
        self.assertEqual(sent["actor_handling_status"], "submitted", msg=sent)
        return sent

    def _settled_receipt(self, message_id: str) -> dict[str, Any] | None:
        receipt = self._demand_aggregate().get("ingress_receipts", {}).get(
            f"im.message.created:{message_id}"
        )
        return (
            dict(receipt)
            if isinstance(receipt, dict) and receipt.get("state") == "settled"
            else None
        )

    def _instance(self) -> dict[str, Any]:
        if self.actor_id is None:
            raise AssertionError("Actor id is not available")
        path = self.shared_root / "instances" / self.actor_id / "instance.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _goal(self) -> dict[str, Any] | None:
        instance = self._instance()
        socket_path = Path(str(instance["app_server_socket"]))
        result = app_server.goal_get(socket_path, str(instance["thread_id"]))
        goal = result.get("goal")
        return dict(goal) if isinstance(goal, dict) else None

    def _diagnostics(self) -> str:
        request_shapes: list[dict[str, Any]] = []
        for request in self.responses.requests:
            body = request.get("body")
            request_shapes.append(
                {
                    "path": request.get("path"),
                    "body_keys": sorted(body) if isinstance(body, dict) else None,
                    "tools": body.get("tools") if isinstance(body, dict) else None,
                }
            )
        rows = [
            f"model_trace={self.controller.trace!r}",
            f"model_failure={self.controller.failure!r}",
            f"request_shapes={request_shapes!r}",
        ]
        for path in sorted(self.root.rglob("*.log")):
            rows.append(
                f"\n--- {path.relative_to(self.root)} ---\n"
                f"{path.read_text(encoding='utf-8', errors='replace')[-12000:]}"
            )
        return "\n".join(rows)

    def _wait_for_controller(self, event: threading.Event, description: str) -> None:
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if event.wait(POLL_SECONDS):
                return
            if self.controller.failed.is_set():
                self.fail(f"{description} failed:\n{self._diagnostics()}")
        self.fail(f"timed out waiting for {description}:\n{self._diagnostics()}")

    def _cleanup(self) -> CleanupReport:
        if self._closed:
            assert self.cleanup_report is not None
            return self.cleanup_report
        self._closed = True
        self.controller.allow_goal_delivery.set()
        self.controller.allow_goal_complete.set()
        self.controller.allow_reconciliation.set()
        self.controller.allow_later_goal_turn.set()

        report = CleanupReport()
        if self.actor_id is not None:
            stopped = run_process(
                [str(LAUNCHER), "instance", "stop", self.actor_id],
                cwd=REPO_ROOT,
                env=self.env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if stopped.returncode != 0:
                report.residuals.append(
                    "instance stop failed: "
                    f"stdout={stopped.stdout!r} stderr={stopped.stderr!r}"
                )

        if self.web_process is not None:
            process_report = self.ledger.cleanup_registered_process(
                self.web_process.pid,
                expected_pgid=os.getpgid(self.web_process.pid)
                if self.web_process.poll() is None
                else None,
            )
            report.terminated_pids.extend(process_report.terminated_pids)
            report.killed_pids.extend(process_report.killed_pids)
            report.identity_mismatches.extend(process_report.identity_mismatches)
            report.removed_paths.extend(process_report.removed_paths)
            report.residuals.extend(process_report.residuals)

        reset = run_process(
            [str(LAUNCHER), "env", "reset", "--yes"],
            cwd=REPO_ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if reset.returncode != 0:
            report.residuals.append(
                f"env reset failed: stdout={reset.stdout!r} stderr={reset.stderr!r}"
            )

        central_paths = central_service.central_daemon_paths(self.shared_root)
        try:
            central_result = central_process.stop_central_daemon(central_paths)
        except Exception as exc:
            report.residuals.append(f"central daemon cleanup failed: {exc}")
        else:
            if central_result.get("ok") is not True:
                report.residuals.append(
                    f"central daemon cleanup failed: {central_result!r}"
                )

        self.responses.close()
        if self.root.exists():
            try:
                shutil.rmtree(self.root)
            except OSError as exc:
                report.residuals.append(f"phase2 root cleanup failed: {exc}")
        if self.root.exists():
            report.residuals.append(f"phase2 root remains: {self.root}")
        self.cleanup_report = report
        return report

    def test_web_actor_delivers_then_goal_and_demand_complete(self) -> None:
        self._start_web()
        started = self._http("POST", "/api/instances", {"role": "dev"})
        operation = self._wait_operation(started["operation"]["id"])
        self.actor_id = str(operation["result"]["actor_id"])

        session = self._http("GET", "/api/im/session")
        self.assertEqual(session["identity"]["type"], "external")
        sent = self._send_inbound(REQUEST_TEXT)
        self.controller.original_message_id = str(sent["message"]["id"])

        self._wait_for_controller(
            self.controller.goal_pause_reached,
            "Goal delivery pause",
        )
        demand = self._wait_until(
            lambda: self._demand("Phase 2"),
            "one live Demand A",
        )
        task = self._wait_until(
            lambda: (
                row
                if (row := self._single_task()) is not None
                and row.get("status") == "active"
                and isinstance(row.get("goal_binding"), dict)
                else None
            ),
            "one bound active Task",
        )
        goal = self._wait_until(
            lambda: (
                row
                if (row := self._goal()) is not None
                and row.get("status") == "active"
                else None
            ),
            "matching active native Goal",
        )
        self.assertIsNone(demand["terminal"])
        self.assertEqual(task["demand_ref"]["demand_id"], demand["id"])
        expected_objective = _task_objective(str(sent["message"]["id"]))
        self.assertEqual(task["objective"], expected_objective)
        self.assertIn(str(sent["message"]["id"]), task["objective"])
        self.assertEqual(task["goal_binding"]["thread_id"], self._instance()["thread_id"])
        self.assertEqual(goal["objective"], expected_objective)
        self.assertEqual(goal["threadId"], self._instance()["thread_id"])
        self.assertGreaterEqual(self.controller.stage, 11)

        def settle_inbound(
            content: str,
            *,
            decision: str,
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            inbound = self._send_inbound(content)
            message_id = str(inbound["message"]["id"])
            receipt = self._wait_until(
                lambda: self._settled_receipt(message_id),
                f"settled inbound {message_id}",
            )
            self._wait_until(
                lambda: self._instance().get("side_threads") == [],
                f"side cleanup for {message_id}",
            )
            self.assertEqual(receipt["outcome"]["decision"], decision)
            active_tasks = [
                row for row in self._tasks() if row.get("status") == "active"
            ]
            self.assertEqual([row["id"] for row in active_tasks], [task["id"]])
            self.assertEqual(self._goal()["status"], "active")
            return inbound, receipt

        supplement, _supplement_receipt = settle_inbound(
            SUPPLEMENT_TEXT,
            decision="merge_intake",
        )
        demand = self._wait_until(
            lambda: (
                row
                if (row := self._demand("originating-message binding")) is not None
                and row.get("revision") == 2
                else None
            ),
            "merged Demand A",
        )
        self.assertEqual(len(demand["source_refs"]), 2)
        self.assertEqual(
            demand["source_refs"][1]["ref"]["message_id"],
            supplement["message"]["id"],
        )

        _inbound_b, _b_receipt = settle_inbound(
            DEMAND_B_TEXT,
            decision="create",
        )
        self.assertEqual(len(self._demands()), 2)
        self.assertIsNotNone(self._demand("follow-up verification checklist"))

        _ordinary, ordinary_receipt = settle_inbound(
            ORDINARY_TEXT,
            decision="no_action_needed",
        )
        self.assertFalse(ordinary_receipt["outcome"]["demand_changed"])
        self.assertEqual(len(self._demands()), 2)

        _inbound_c, _c_create_receipt = settle_inbound(
            DEMAND_C_TEXT,
            decision="create",
        )
        self.assertEqual(len(self._demands()), 3)
        self.assertIsNone(self._demand("temporary rollback")["terminal"])

        _cancel_c, c_cancel_receipt = settle_inbound(
            CANCEL_C_TEXT,
            decision="cancel",
        )
        self.assertTrue(c_cancel_receipt["outcome"]["demand_changed"])
        canceled_c = self._demand("temporary rollback")
        self.assertEqual(canceled_c["terminal"]["type"], "canceled")
        self.assertEqual(
            self._demand_aggregate()["demand_pool_revision"],
            5,
        )
        self.assertGreaterEqual(self.controller.stage, 21)

        self.controller.allow_goal_delivery.set()
        self._wait_for_controller(
            self.controller.reply_pause_reached,
            "reply delivery pause",
        )

        def reply_event() -> dict[str, Any] | None:
            events = self._http("GET", "/api/im/events?wait_ms=0")["events"]
            return events[0] if events else None

        event = self._wait_until(reply_event, "readable Actor reply event")
        fetched = self._http("GET", f"/api/im/messages/{event['message_id']}")
        self.assertEqual(fetched["message"]["content"], REPLY_TEXT)
        self.assertEqual(fetched["message"]["reply_to"], sent["message"]["id"])
        self.assertEqual(self._goal()["status"], "active")

        self.controller.allow_goal_complete.set()
        self._wait_for_controller(
            self.controller.reconciliation_pause_reached,
            "Demand reconciliation pause",
        )
        completed_task = self._wait_until(
            lambda: (
                next(
                    (
                        row
                        for row in self._tasks()
                        if row.get("id") == task["id"]
                        and row.get("status") == "completed"
                    ),
                    None,
                )
            ),
            "host-recorded completed Task",
        )
        completed_goal = self._wait_until(
            lambda: (
                row
                if (row := self._goal()) is not None
                and row.get("status") == "complete"
                else None
            ),
            "native Goal complete",
        )
        self.assertEqual(completed_task["result"]["type"], "goal_terminal")
        self.assertEqual(completed_task["result"]["goal_status"], "complete")
        self.assertEqual(
            completed_task["result"]["goal_updated_at"],
            completed_goal["updatedAt"],
        )

        self.controller.allow_reconciliation.set()
        self._wait_for_controller(
            self.controller.later_goal_pause_reached,
            "later Demand Goal pause",
        )
        completed_demand = self._wait_until(
            lambda: (
                row
                if (row := self._demand("originating-message binding")) is not None
                and isinstance(row.get("terminal"), dict)
                and row["terminal"].get("type") == "completed"
                else None
            ),
            "later parent Demand reconciliation",
        )
        self.assertEqual(
            completed_demand["terminal"]["evidence_refs"][0]["ref"]["task_id"],
            completed_task["id"],
        )
        reply_evidence = completed_demand["terminal"]["evidence_refs"][1]
        self.assertEqual(reply_evidence["type"], "im.message.reply")
        self.assertEqual(reply_evidence["ref"]["id"], fetched["message"]["id"])
        self.assertEqual(
            reply_evidence["ref"]["key"],
            f"reply_to:{sent['message']['id']}",
        )

        console = self._http("GET", f"/api/actors/{self.actor_id}/console")["console"]
        self.assertEqual(console["task_sys"]["active_count"], 1)
        self.assertEqual(console["task_sys"]["terminal_count"], 1)
        self.assertEqual(
            console["task_sys"]["terminal_tasks"][0]["task_id"],
            completed_task["id"],
        )
        self.assertNotIn("recoverable_tasks", console["task_sys"])
        active_task = console["task_sys"]["active_tasks"][0]
        demand_b = self._demand("follow-up verification checklist")
        self.assertEqual(active_task["demand_ref"]["demand_id"], demand_b["id"])
        self.assertEqual(
            next(
                row
                for row in self._tasks()
                if row["id"] == active_task["task_id"]
            )["objective"],
            _later_task_objective(),
        )
        self.assertEqual(self._goal()["status"], "active")
        self.assertEqual(self._goal()["objective"], _later_task_objective())
        self.assertIsNone(demand_b["terminal"])
        self.assertEqual(
            self._demand("temporary rollback")["terminal"]["type"],
            "canceled",
        )
        self.assertEqual(
            len(self._tasks()),
            2,
        )

        instance_root = self.shared_root / "instances" / self.actor_id
        self._wait_until(
            lambda: self._instance().get("side_threads") == [],
            "settled triage side cleanup",
        )
        side_rows = self._instance().get("side_threads")
        self.assertEqual(side_rows, [])
        daemon_log = instance.daemon_log_file(instance_root).read_text(
            encoding="utf-8",
            errors="replace",
        )
        handler_results = {
            (row.get("handler"), row.get("result"))
            for line in daemon_log.splitlines()
            if line.strip()
            for row in [json.loads(line)]
            if row.get("event") in {"handler_result", "handler_reconcile_result"}
        }
        self.assertIn(("task_goal", "handled"), handler_results)
        self.assertIn(("demand_orchestration", "handled"), handler_results)

        report = self._cleanup()
        self.assertEqual(report.identity_mismatches, [])
        self.assertEqual(report.residuals, [])
        self.assertFalse(self.root.exists())

    def test_failed_env_reset_still_stops_central_daemon_and_removes_owned_paths(
        self,
    ) -> None:
        paths = central_service.central_daemon_paths(self.shared_root)
        central_process.start_central_daemon(paths)
        record = process_identity.read_record(paths.pid_file)
        self.assertIsNotNone(record)
        assert record is not None
        lock_path = self.root / "cleanup.lock"
        lock_path.write_text("owned\n", encoding="utf-8")
        failed_reset = subprocess.CompletedProcess(
            [str(LAUNCHER), "env", "reset", "--yes"],
            1,
            stdout="",
            stderr="forced reset failure",
        )

        try:
            with mock.patch(
                f"{__name__}.run_process",
                return_value=failed_reset,
            ):
                report = self._cleanup()

            self.assertIn("env reset failed", "\n".join(report.residuals))
            self.assertFalse(process_identity.is_running(record))
            self.assertFalse(paths.socket_path.exists())
            self.assertFalse(paths.pid_file.exists())
            self.assertFalse(paths.pid_identity_file.exists())
            self.assertFalse(lock_path.exists())
            self.assertFalse(self.root.exists())
        finally:
            if process_identity.is_running(record):
                central_process.terminate_record(record)
            central_process.cleanup_runtime_files(paths)
            if self.root.exists():
                shutil.rmtree(self.root)


if __name__ == "__main__":
    unittest.main()
