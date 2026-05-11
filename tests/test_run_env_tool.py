#!/usr/bin/env python3
"""Functional coverage for broker-routed env.tool run-manager operations."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
import turn_runtime  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v1"
INSTANCE_ID = "inst-pm-run-example"
PM_REQUEST = "给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track"


def _pm_commit() -> dict[str, object]:
    return {
        "execution_summary": "PM wrote the AI schedule tool landing page PRD and created the delivery track.",
        "artifacts": [
            {
                "kind": "prd",
                "title": "AI Schedule Tool Landing Page PRD",
                "summary": "Defines landing page scope, sections, MVP requirements, and acceptance criteria.",
                "content": {
                    "problem": "Busy professionals need an AI-assisted way to reduce scheduling overhead.",
                    "requirements": [
                        "Explain the core promise in the hero",
                        "Show concrete scheduling workflows",
                    ],
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
            "task": {
                "status": "done",
                "summary": "PM PRD is ready for market positioning research.",
            },
        },
        "handoff": {
            "next_buddy": "market",
            "reason": "Market should validate competitor landing page positioning before design.",
            "context": "Use the PRD artifact and track summary as source context.",
        },
        "contributors": {
            "skills": ["write-prd", "track-manager"],
            "agents": [],
        },
    }


class RunManagerEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _session(self, *, buddy: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "instance_id": INSTANCE_ID,
            "active_buddy": buddy,
            "payload": payload or {},
        }

    def _instance_json(
        self,
        *,
        instance_id: str = INSTANCE_ID,
        buddy: str = "pm",
        status: str = "active",
        current_task_id: str | None = None,
        current_track_id: str | None = None,
    ) -> Path:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "current_task_id": current_task_id,
                    "current_track_id": current_track_id,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-10T00:00:00Z",
                    "updated_at": "2026-05-10T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _prepare(self, request_text: str = PM_REQUEST, *, buddy: str = "pm") -> dict[str, object]:
        with patch.object(turn_runtime, "_load_product_mode_session", return_value=self._session(buddy=buddy)):
            context = turn_runtime.prepare_turn_context(request_text, manifest_path=MANIFEST)
        self.assertTrue(context["ok"], msg=context)
        return context

    def _dispatch(
        self,
        *,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = INSTANCE_ID,
        buddy: str = "pm",
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "instance_id": instance_id,
            "active_buddy": buddy,
            "method": "env.tool",
            "payload": {"tool": "run", "action": action, "args": args},
        }
        return runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _runtime_state_snapshot(self) -> dict[str, object]:
        def _load_dir(dir_path: Path) -> dict[str, object]:
            rows: dict[str, object] = {}
            if not dir_path.exists():
                return rows
            for path in sorted(dir_path.glob("*.json")):
                rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
            return rows

        return {
            "tracks": _load_dir(self._runtime_path("buddyswitch/objects/tracks")),
            "tasks": _load_dir(self._runtime_path("buddyswitch/objects/tasks")),
            "artifacts": _load_dir(self._runtime_path("buddyswitch/objects/artifacts")),
            "runs": _load_dir(self._runtime_path("buddyswitch/content/runs")),
            "reservations": _load_dir(self._runtime_path("buddyswitch/content/runs/reserved")),
        }

    def _load_instance(self, instance_json: Path) -> dict[str, object]:
        return json.loads(instance_json.read_text(encoding="utf-8"))

    def test_run_commit_persists_buddy_run_and_updates_instance_binding(self) -> None:
        context = self._prepare()
        instance_json = self._instance_json()

        response = self._dispatch(
            action="commit",
            args={"context": context, "result": _pm_commit()},
            instance_json=instance_json,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "run")
        self.assertEqual(response.get("action"), "run.commit")
        receipt = response.get("receipt")
        self.assertIsInstance(receipt, dict, msg=response)
        assert isinstance(receipt, dict)
        run_id = receipt.get("run_id")
        self.assertIsInstance(run_id, str, msg=response)
        assert isinstance(run_id, str)
        self.assertTrue(self._runtime_path(f"buddyswitch/content/runs/{run_id}.json").exists())
        self.assertFalse(self._runtime_path(f"buddyswitch/content/runs/reserved/{run_id}.json").exists())

        instance_payload = self._load_instance(instance_json)
        self.assertEqual(instance_payload["current_task_id"], receipt["task_id"])
        self.assertEqual(instance_payload["current_track_id"], receipt["track_id"])

    def test_invalid_run_commit_returns_feedback_without_mutating_state(self) -> None:
        context = self._prepare()
        instance_json = self._instance_json()
        state_before = copy.deepcopy(self._runtime_state_snapshot())
        instance_before = self._load_instance(instance_json)

        response = self._dispatch(
            action="commit",
            args={"context": context, "result": {"execution_summary": "summary only"}},
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "run")
        self.assertEqual(response.get("action"), "run.commit")
        error = response.get("error")
        self.assertIsInstance(error, dict, msg=response)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_RUNTIME_PERSIST")
        self.assertEqual(response.get("permission_boundary"), "persist.durable_signal")
        self.assertEqual(self._runtime_state_snapshot(), state_before)
        self.assertEqual(self._load_instance(instance_json), instance_before)


if __name__ == "__main__":
    unittest.main()
