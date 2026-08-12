"""Response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.support.paths import REPO_ROOT
from buddyswitch.runtime_support import env_manifest  # noqa: E402

ROOT = REPO_ROOT

import buddyswitch.foundation.runtime_broker.broker as runtime_broker  # noqa: E402
from tests.support import task_fixtures  # noqa: E402
from buddyswitch.modules.communication.private.state import messages as message_repo  # noqa: E402
from buddyswitch.modules.communication.private.domain import messages as message_service  # noqa: E402
from buddyswitch.foundation.tool_runtime import registry as tool_catalog  # noqa: E402
from buddyswitch.foundation.tool_runtime import results as tool_results  # noqa: E402
from buddyswitch.foundation.tool_runtime import context as runtime_context  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvToolResponseCase(RuntimeWorkspaceTestCase):
    _ACTION_PLACEHOLDERS = {
        "tbd",
        "todo",
        "n/a",
        "na",
        "none",
        "unknown",
        "placeholder",
    }

    @classmethod
    def _meaningful_text_entries(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        rows: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                continue
            normalized = entry.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in cls._ACTION_PLACEHOLDERS:
                continue
            rows.append(normalized)
        return rows

    @staticmethod
    def _meaningful_tool_action_options(value: object) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        rows: list[dict[str, str]] = []
        for entry in value:
            if not isinstance(entry, dict):
                continue
            tool = entry.get("tool")
            action = entry.get("action")
            if isinstance(tool, str) and tool.strip() and isinstance(action, str) and action.strip():
                rows.append({"tool": tool.strip(), "action": action.strip()})
        return rows

    def _assert_actionable_next_guidance(self, payload: dict[str, object]) -> None:
        meaningful_next_actions = self._meaningful_text_entries(payload.get("allowed_next_actions"))
        meaningful_next_options = self._meaningful_tool_action_options(payload.get("allowed_next_action_options"))
        has_next_actions = len(meaningful_next_actions) > 0
        has_next_options = len(meaningful_next_options) > 0
        self.assertTrue(has_next_actions or has_next_options, msg=payload)

    def _instance_json(self, *, role: str, actor_id: str) -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        path = self._runtime_path(f"instances/{actor_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-18T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._seed_active_task(instance_json=path, role=role, actor_id=actor_id)
        return path

    def _seed_active_task(self, *, instance_json: Path, role: str, actor_id: str) -> None:
        task_id = f"task-0001-{role}-response-contract"
        task_fixtures.create_task(
            actor_target={"actor_id": actor_id, "role_id": role},
            demand_ref={
                "demand_id": f"demand-response-contract-{role}",
                "basis_revision": 1,
                "demand_ref": f"dref-response-contract-{role}",
            },
            objective=f"Exercise response contracts for {task_id}.",
            selection_reason="The response-contract fixture requires one active Task.",
        )

    def _dispatch(
        self,
        *,
        instance_json: Path,
        actor_id: str,
        role: str,
        tool: str,
        action: str,
        args: dict[str, object],
        invocation: dict[str, str] | None = None,
    ) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-response-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "actor_id": actor_id,
                    "active_role": role,
                    "tool": tool,
                    "action": action,
                    "args": args,
                    **({"invocation": invocation} if invocation is not None else {}),
                },
                "deadline_ms": 35000,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
            manifest_loader=env_manifest.load_manifest,
        )
        self.assertEqual(envelope.get("protocol"), PROTOCOL)
        if envelope.get("ok") is True:
            result = envelope.get("result")
            self.assertIsInstance(result, dict, msg=envelope)
            assert isinstance(result, dict)
            return result
        error = envelope.get("error") if isinstance(envelope.get("error"), dict) else {}
        payload: dict[str, object] = {
            "ok": False,
            "error": {
                "code": error.get("code"),
                "message": error.get("message"),
                "retriable": error.get("retriable"),
            },
        }
        for key, value in envelope.items():
            if key in {"protocol", "request_id", "ok", "error"}:
                continue
            payload[key] = value
        return payload

    def _assert_rejection_contract(self, payload: dict[str, object]) -> None:
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertIsInstance(payload.get("permission_boundary"), str, msg=payload)
        self.assertTrue(str(payload.get("permission_boundary", "")).strip(), msg=payload)
        self.assertIsInstance(payload.get("why_blocked"), str, msg=payload)
        self.assertTrue(str(payload.get("why_blocked", "")).strip(), msg=payload)
        self.assertIsInstance(payload.get("impact"), str, msg=payload)
        self.assertTrue(str(payload.get("impact", "")).strip(), msg=payload)
        self.assertIsInstance(payload.get("retryable"), bool, msg=payload)
        self.assertIsInstance(payload.get("retry_guidance"), str, msg=payload)
        self.assertTrue(str(payload.get("retry_guidance", "")).strip(), msg=payload)
        self.assertIn("allowed_next_actions", payload, msg=payload)
        self.assertIsInstance(payload.get("allowed_next_actions"), list, msg=payload)
        if "allowed_next_action_options" in payload:
            self.assertIsInstance(payload.get("allowed_next_action_options"), list, msg=payload)
        next_actions = self._meaningful_text_entries(payload.get("allowed_next_actions"))
        next_options = self._meaningful_tool_action_options(payload.get("allowed_next_action_options"))
        self.assertTrue(
            bool(next_actions) or bool(next_options),
            msg=payload,
        )
        self.assertEqual(payload.get("state_changed"), False, msg=payload)
        self.assertEqual(payload.get("durability"), "none", msg=payload)

    def _assert_success_contract(self, payload: dict[str, object]) -> None:
        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertIsInstance(payload.get("effect_summary"), str, msg=payload)
        self.assertIsInstance(payload.get("state_changed"), bool, msg=payload)
        self.assertIsInstance(payload.get("durability"), str, msg=payload)

    def _assert_write_success_contract(self, payload: dict[str, object]) -> None:
        self._assert_success_contract(payload)
        self.assertTrue(payload.get("state_changed"), msg=payload)
        self.assertIsInstance(payload.get("state_changes"), list, msg=payload)
        self.assertGreater(len(payload.get("state_changes", [])), 0, msg=payload)
        self.assertNotEqual(payload.get("durability"), "none", msg=payload)
        self._assert_actionable_next_guidance(payload)

    def _assert_no_retired_task_sys_fields(self, payload: dict[str, object]) -> None:
        for field in ("active_processor", "side_result", "parent_handoff_params", "failure_result", "close_result"):
            with self.subTest(field=field):
                self.assertNotIn(field, payload, msg=payload)

    def _assert_success_matches_declared_action_semantics(self, action_key: str, payload: dict[str, object]) -> None:
        self._assert_success_contract(payload)
        semantics = tool_catalog.operation_semantics()[action_key]
        self.assertEqual(payload.get("durability"), semantics["durability"], msg=payload)
        if semantics["durability"] == "none":
            self.assertFalse(payload.get("state_changed"), msg=payload)
        else:
            self.assertTrue(payload.get("state_changed"), msg=payload)
            self.assertIsInstance(payload.get("state_changes"), list, msg=payload)
            self.assertGreater(len(payload.get("state_changes", [])), 0, msg=payload)
        if semantics["mutates"] == "runtime_objects":
            self.assertTrue(payload.get("created_ids") or payload.get("updated_ids") or payload.get("state_changes"), msg=payload)
        if semantics["mutates"] == "runtime_files":
            self.assertIn("private_file", json.dumps(payload.get("state_changes", [])), msg=payload)
        if semantics["mutates"] == "broker_token":
            self.assertFalse(payload.get("mutates_product_state"), msg=payload)
            self.assertIn("token", json.dumps(payload.get("state_changes", [])), msg=payload)
