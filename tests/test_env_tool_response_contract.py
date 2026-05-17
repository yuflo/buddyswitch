#!/usr/bin/env python3
"""Response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import runtime_kernel.broker as runtime_broker  # noqa: E402
from env.tools import contracts as tool_contracts  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvToolResponseContractTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, buddy: str, instance_id: str) -> Path:
        path = self._runtime_path(f"instances/{instance_id}/instance.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-15T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(
        self,
        *,
        instance_json: Path,
        instance_id: str,
        buddy: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        envelope = runtime_broker.dispatch_runtime_request(
            request={
                "protocol": PROTOCOL,
                "request_id": f"req-response-{uuid.uuid4().hex}",
                "method": "env.tool",
                "params": {
                    "instance_id": instance_id,
                    "active_buddy": buddy,
                    "tool": tool,
                    "action": action,
                    "args": args,
                },
                "deadline_ms": 35000,
            },
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
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
        self.assertIsInstance(payload.get("why_blocked"), str, msg=payload)
        self.assertIsInstance(payload.get("impact"), str, msg=payload)
        self.assertIsInstance(payload.get("retryable"), bool, msg=payload)
        self.assertIsInstance(payload.get("retry_guidance"), str, msg=payload)
        self.assertIsInstance(payload.get("allowed_next_actions"), list, msg=payload)

    def _assert_success_contract(self, payload: dict[str, object]) -> None:
        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertIsInstance(payload.get("effect_summary"), str, msg=payload)
        self.assertIsInstance(payload.get("state_changed"), bool, msg=payload)
        self.assertIsInstance(payload.get("durability"), str, msg=payload)

    def test_registry_excludes_removed_surfaces(self) -> None:
        tools = {row["tool"] for row in tool_contracts.TOOL_REGISTRY}
        self.assertNotIn("handoff", tools)
        self.assertNotIn("memory", tools)
        self.assertNotIn("run", tools)

    def test_context_get_and_summarize_catalog_scope(self) -> None:
        instance_id = "inst-pm-context-scope"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        full = self._dispatch(instance_json=instance_json, instance_id=instance_id, buddy="pm", tool="context", action="get", args={})
        summary = self._dispatch(instance_json=instance_json, instance_id=instance_id, buddy="pm", tool="context", action="summarize", args={})

        self._assert_success_contract(full)
        self._assert_success_contract(summary)
        self.assertIn("tool_catalog", full)
        self.assertIn("operation_semantics", full)
        self.assertNotIn("tool_catalog", summary)
        self.assertNotIn("operation_semantics", summary)

    def test_unknown_tool_rejection_contract(self) -> None:
        instance_id = "inst-pm-reject"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="unknown",
            action="list",
            args={},
        )
        self._assert_rejection_contract(payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_ENV_TOOL")

    def test_track_and_artifact_success_contract(self) -> None:
        instance_id = "inst-pm-success"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        track = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-response", "title": "Response"},
        )
        self._assert_success_contract(track)

        task = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="task",
            action="create",
            args={"task_id": "task-response", "title": "Task", "track_id": "track-response"},
        )
        self._assert_success_contract(task)

        artifact = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-response-r1",
                "task_id": "task-response",
                "kind": "prd",
                "title": "Title",
                "summary": "Summary",
                "content": {"body": "x"},
            },
        )
        self._assert_success_contract(artifact)
        self.assertTrue((artifact.get("artifact") or {}).get("id"))


if __name__ == "__main__":
    unittest.main()
