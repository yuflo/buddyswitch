#!/usr/bin/env python3
"""Tests for runtime broker request routing and identity checks."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import contextlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
import runtime_kernel.client as runtime_client  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"

PM_COMMIT = {
    "execution_summary": "PM wrote the AI schedule tool landing page PRD and created the delivery track.",
    "working_notes": ["The user requested PRD creation and track binding in one PM run."],
    "artifacts": [
        {
            "kind": "prd",
            "title": "AI Schedule Tool Landing Page PRD",
            "summary": "Defines landing page scope and acceptance criteria.",
            "content": {
                "problem": "Busy professionals need an AI-assisted way to reduce scheduling overhead.",
                "requirements": ["Explain the core promise in the hero", "Show concrete scheduling workflows"],
            },
        }
    ],
    "state_effects": {
        "track": {
            "action": "create",
            "track_id": "track-ai-schedule-landing-page",
            "title": "AI Schedule Tool Landing Page",
            "status": "active",
            "current_buddy": "pm",
            "next_buddy": "market",
            "summary": "Cross-buddy landing page iteration for an AI schedule tool.",
        },
        "task": {"status": "done", "summary": "PM PRD is ready for market positioning research."},
    },
    "handoff": {
        "next_buddy": "market",
        "reason": "Market should validate competitor landing page positioning before design.",
        "context": "Use the PRD artifact and track summary as source context.",
    },
    "contributors": {"skills": ["write-prd", "track-tool"], "agents": []},
}


class RuntimeBrokerTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = "inst-pm-example",
        buddy: str = "pm",
        status: str = "active",
    ) -> Path:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-06T00:00:00Z",
                    "updated_at": "2026-05-06T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _dispatch(
        self,
        *,
        method: str,
        payload: dict[str, object],
        instance_id: str = "inst-pm-example",
        buddy: str = "pm",
        instance_json: Path,
    ) -> dict[str, object]:
        request = {
            "protocol": "buddyswitch-runtime-broker/v1",
            "instance_id": instance_id,
            "active_buddy": buddy,
            "method": method,
            "payload": payload,
        }
        return runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def test_prepare_and_persist_succeed_with_matching_identity(self) -> None:
        instance_json = self._instance_json()
        before_prepare_instance = json.loads(instance_json.read_text(encoding="utf-8"))
        prepare = self._dispatch(
            method="prepare",
            payload={"text": PM_REQUEST},
            instance_json=instance_json,
        )
        self.assertTrue(prepare["ok"], msg=prepare)
        context = prepare["payload"]
        self.assertTrue(context["ok"])
        self.assertEqual(context["active_buddy"], "pm")
        self.assertEqual(context["instance_id"], "inst-pm-example")
        prepared_instance = json.loads(instance_json.read_text(encoding="utf-8"))
        self.assertEqual(prepared_instance, before_prepare_instance)

        persisted = self._dispatch(
            method="persist",
            payload={"context": context, "result": PM_COMMIT},
            instance_json=instance_json,
        )
        self.assertTrue(persisted["ok"], msg=persisted)
        receipt = persisted["payload"]["receipt"]
        run_id = receipt["run_id"]
        run_path = self._runtime_path(f"buddyswitch/content/runs/{run_id}.json")
        self.assertTrue(run_path.exists())
        persisted_instance = json.loads(instance_json.read_text(encoding="utf-8"))
        self.assertEqual(persisted_instance["current_task_id"], receipt["task_id"])
        self.assertEqual(persisted_instance["current_track_id"], receipt["track_id"])

    def test_prepare_and_persist_enter_shared_runtime_lock(self) -> None:
        instance_json = self._instance_json()
        lock_sessions: list[dict[str, object]] = []

        @contextlib.contextmanager
        def fake_lock(session: dict[str, object]):
            lock_sessions.append(session)
            yield

        with patch.object(runtime_broker.turn_runtime, "_hold_product_runtime_lock", side_effect=fake_lock):
            prepare = self._dispatch(
                method="prepare",
                payload={"text": PM_REQUEST},
                instance_json=instance_json,
            )
            self.assertTrue(prepare["ok"], msg=prepare)
            persisted = self._dispatch(
                method="persist",
                payload={"context": prepare["payload"], "result": PM_COMMIT},
                instance_json=instance_json,
            )
            self.assertTrue(persisted["ok"], msg=persisted)

        self.assertEqual([session["instance_id"] for session in lock_sessions], ["inst-pm-example", "inst-pm-example"])
        self.assertTrue(all(session["instance_json"] == instance_json for session in lock_sessions))

    def test_rejects_wrong_instance_id(self) -> None:
        instance_json = self._instance_json()
        response = self._dispatch(
            method="prepare",
            payload={"text": PM_REQUEST},
            instance_id="inst-other",
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER")
        self.assertIn("instance_id mismatch", response["error"]["message"])

    def test_rejects_wrong_active_buddy(self) -> None:
        instance_json = self._instance_json(buddy="pm")
        response = self._dispatch(
            method="prepare",
            payload={"text": PM_REQUEST},
            buddy="market",
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER")
        self.assertIn("active_buddy mismatch", response["error"]["message"])

    def test_rejects_inactive_instance(self) -> None:
        instance_json = self._instance_json(status="inactive")
        response = self._dispatch(
            method="prepare",
            payload={"text": PM_REQUEST},
            instance_json=instance_json,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "E_RUNTIME_BROKER")
        self.assertIn("instance is not active", response["error"]["message"])

    def test_env_tool_supports_active_instance_and_identity_checks(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev", status="active")

        supported = self._dispatch(
            method="env.tool",
            payload={"tool": "task", "action": "list", "args": {}},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(supported["ok"], msg=supported)

        wrong_instance = self._dispatch(
            method="env.tool",
            payload={"tool": "task", "action": "list", "args": {}},
            instance_json=instance_json,
            instance_id="inst-other",
            buddy="dev",
        )
        self.assertFalse(wrong_instance["ok"])
        self.assertEqual(wrong_instance["permission_boundary"], "active-instance")

        wrong_buddy = self._dispatch(
            method="env.tool",
            payload={"tool": "task", "action": "list", "args": {}},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="pm",
        )
        self.assertFalse(wrong_buddy["ok"])
        self.assertEqual(wrong_buddy["permission_boundary"], "active-buddy")

        inactive_instance_json = self._instance_json(instance_id="inst-dev-inactive", buddy="dev", status="inactive")
        inactive = self._dispatch(
            method="env.tool",
            payload={"tool": "task", "action": "list", "args": {}},
            instance_json=inactive_instance_json,
            instance_id="inst-dev-inactive",
            buddy="dev",
        )
        self.assertFalse(inactive["ok"])
        self.assertEqual(inactive["permission_boundary"], "active-instance-status")

    def test_legacy_env_task_method_is_rejected(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev", status="active")
        legacy_method = "env" + ".task"
        rejected_legacy = self._dispatch(
            method=legacy_method,
            payload={"action": "list", "args": {}},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertFalse(rejected_legacy["ok"])
        self.assertEqual(rejected_legacy["permission_boundary"], "broker-protocol")

    def test_runtime_broker_client_missing_socket_raises_unavailable(self) -> None:
        with patch.dict(
            os.environ,
            {
                "BUDDYSWITCH_INSTANCE_ID": "inst-pm-example",
                "BUDDYSWITCH_ACTIVE_BUDDY": "pm",
                "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": "",
            },
            clear=False,
        ):
            with self.assertRaises(runtime_client.RuntimeBrokerError) as raised:
                runtime_client.runtime_broker_socket_from_env()
        self.assertEqual(raised.exception.code, "E_RUNTIME_BROKER_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
