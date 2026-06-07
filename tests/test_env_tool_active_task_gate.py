#!/usr/bin/env python3
"""Active task pre-dispatch gate tests for env.tool runtime."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
from env.tool_runtime import registry as tool_registry  # noqa: E402
from env.tool_runtime import results as tool_results  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"


class EnvToolActiveTaskGateTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manifest_path = MANIFEST
        self.manifest = env_manifest.load_manifest(self.manifest_path)

    def _instance(
        self,
        *,
        role: str = "market",
        label: str = "act-active-task-gate",
    ) -> dict[str, Any]:
        actor_id = self._runtime_actor_id(role=role, label=label)
        instance_root = self._runtime_path(f"instances/{actor_id}")
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        taskbox = instance_root / "taskbox" / role
        (taskbox / "tasks").mkdir(parents=True, exist_ok=True)
        (taskbox / "history.md").write_text("", encoding="utf-8")
        instance_json = instance_root / "instance.json"
        instance_payload = {
            "actor_id": actor_id,
            "role": role,
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "browser_port": None,
            "updated_at": "2026-06-07T10:00:00+08:00",
        }
        instance_json.write_text(json.dumps(instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return {
            "actor_id": actor_id,
            "role": role,
            "instance_root": instance_root,
            "instance_json": instance_json,
            "instance_payload": instance_payload,
        }

    def _dispatch(
        self,
        *,
        instance: dict[str, Any],
        tool: str,
        action: str,
        args: object,
    ) -> dict[str, Any]:
        response = tool_registry.dispatch_env_tool_request(
            payload={"tool": tool, "action": action, "args": args},
            active_role=str(instance["role"]),
            actor_id=str(instance["actor_id"]),
            instance_json=instance["instance_json"],
            instance_payload=instance["instance_payload"],
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        )
        self.assertIsInstance(response, dict)
        return response

    def _seed_active_task(self, *, instance: dict[str, Any], task_id: str = "task-0001-active-gate") -> None:
        role = str(instance["role"])
        actor_id = str(instance["actor_id"])
        taskbox = Path(instance["instance_root"]) / "taskbox" / role
        task_path = taskbox / "tasks" / f"{task_id}.json"
        task_path.write_text(
            json.dumps(
                {
                    "id": task_id,
                    "owner_actor": {"actor_id": actor_id, "role_id": role},
                    "title": "Active gate task",
                    "summary": "Current task anchor.",
                    "body": "Active task body.",
                    "status": "active",
                    "priority": "normal",
                    "origin": {"type": "manual"},
                    "track_id": None,
                    "refs": [],
                    "progress_summary": "Current task anchor.",
                    "created_at": "2026-06-07T10:00:00+08:00",
                    "updated_at": "2026-06-07T10:00:00+08:00",
                    "closed_at": None,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (taskbox / "history.md").write_text(
            f"- 2026-06-07T10:00:00+08:00 task.selected {task_id} reason=\"seed active task\"\n",
            encoding="utf-8",
        )

    def _snapshot_runtime_files(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for path in sorted(self.runtime_root.rglob("*")):
            if path.is_file():
                snapshot[str(path.relative_to(self.runtime_root))] = path.read_text(encoding="utf-8")
        return snapshot

    def test_active_task_required_action_rejects_before_handler_without_current_anchor(self) -> None:
        instance = self._instance(role="market")
        before = self._snapshot_runtime_files()
        with patch.object(tool_registry, "_invoke_tool", return_value={"ok": True}) as invoke_tool:
            response = self._dispatch(
                instance=instance,
                tool="search",
                action="request",
                args={"query": "active task gate", "backend": "browser"},
            )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ACTIVE_TASK_REQUIRED", msg=response)
        self.assertEqual(response.get("permission_boundary"), "task.active_anchor", msg=response)
        self.assertIs(response.get("state_changed"), False, msg=response)
        self.assertEqual(response.get("durability"), "none", msg=response)
        self.assertIs(response.get("retryable"), True, msg=response)
        self.assertIn("search.request", str(response.get("why_blocked", "")))
        self.assertIn("TaskViewModel.current_anchor", str(response.get("why_blocked", "")))
        allowed_next_actions = "\n".join(str(row) for row in response.get("allowed_next_actions", []))
        self.assertIn("task.current", allowed_next_actions)
        self.assertIn("task.capture", allowed_next_actions)
        self.assertIn("task.select", allowed_next_actions)
        self.assertEqual(response.get("category"), "task_required", msg=response)
        self.assertEqual(response.get("gate_source"), "env.tool task requirement", msg=response)
        self.assertEqual(response.get("gate_stage"), "pre_dispatch", msg=response)
        self.assertIs(response.get("executed"), False, msg=response)
        self.assertEqual(response.get("task_requirement"), "active_task_required", msg=response)
        invoke_tool.assert_not_called()
        self.assertEqual(self._snapshot_runtime_files(), before)

    def test_free_actions_dispatch_without_current_anchor(self) -> None:
        instance = self._instance(role="market")
        task_current = self._dispatch(instance=instance, tool="task", action="current", args={})
        self.assertNotEqual((task_current.get("error") or {}).get("code"), "E_ACTIVE_TASK_REQUIRED", msg=task_current)
        self.assertTrue(task_current.get("ok"), msg=task_current)

        context_summary = self._dispatch(instance=instance, tool="context", action="summarize", args={})
        self.assertNotEqual((context_summary.get("error") or {}).get("code"), "E_ACTIVE_TASK_REQUIRED", msg=context_summary)

        active_actor = {"actor_id": str(instance["actor_id"]), "role_id": str(instance["role"])}
        handler_response = tool_results.success(
            tool="search",
            action="search.status",
            active_actor=active_actor,
            active_role=str(instance["role"]),
            effect_summary="handler reached",
            state_changed=False,
            durability="none",
        )
        with patch.object(tool_registry, "_invoke_tool", return_value=handler_response) as invoke_tool:
            response = self._dispatch(instance=instance, tool="search", action="status", args={})
        self.assertEqual(response.get("effect_summary"), "handler reached", msg=response)
        invoke_tool.assert_called_once()

    def test_active_task_required_action_dispatches_when_current_anchor_exists(self) -> None:
        instance = self._instance(role="market")
        self._seed_active_task(instance=instance)
        active_actor = {"actor_id": str(instance["actor_id"]), "role_id": str(instance["role"])}
        handler_response = tool_results.success(
            tool="search",
            action="search.request",
            active_actor=active_actor,
            active_role=str(instance["role"]),
            effect_summary="handler reached with active task",
            state_changed=False,
            durability="none",
        )
        with patch.object(tool_registry, "_invoke_tool", return_value=handler_response) as invoke_tool:
            response = self._dispatch(
                instance=instance,
                tool="search",
                action="request",
                args={"query": "active task gate", "backend": "browser"},
            )
        self.assertEqual(response, handler_response)
        invoke_tool.assert_called_once()

    def test_dispatch_ordering_rejects_existing_failures_before_active_task_gate(self) -> None:
        market_instance = self._instance(role="market", label="act-gate-order-market")
        pm_only = self._dispatch(
            instance=market_instance,
            tool="track",
            action="create",
            args={
                "track_id": "track-gate-order",
                "title": "Gate order",
                "outcome": "Prove ordering.",
                "appetite": "small",
                "now": {"next": "test", "blocker": None},
            },
        )
        self.assertNotEqual((pm_only.get("error") or {}).get("code"), "E_ACTIVE_TASK_REQUIRED", msg=pm_only)
        self.assertEqual((pm_only.get("error") or {}).get("code"), "E_TOOL_ROLE_AUTH", msg=pm_only)

        malformed_args = self._dispatch(
            instance=market_instance,
            tool="search",
            action="request",
            args=["not", "an", "object"],
        )
        self.assertEqual((malformed_args.get("error") or {}).get("code"), "E_ENV_TOOL_PAYLOAD", msg=malformed_args)

        unsupported_action = self._dispatch(
            instance=market_instance,
            tool="search",
            action="missing_action",
            args={},
        )
        self.assertEqual((unsupported_action.get("error") or {}).get("code"), "E_ENV_TOOL", msg=unsupported_action)


if __name__ == "__main__":
    unittest.main()
