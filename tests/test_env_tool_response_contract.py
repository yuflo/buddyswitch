#!/usr/bin/env python3
"""Runless response contract tests for broker-routed env.tool actions."""

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

    def test_success_responses_cover_read_write_and_target_scoped_evidence(self) -> None:
        instance_id = "inst-pm-response"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)

        context_summary = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="context",
            action="summarize",
            args={},
        )
        self.assertTrue(context_summary.get("ok"), msg=context_summary)
        self.assertFalse(context_summary.get("state_changed"), msg=context_summary)
        self.assertEqual(context_summary.get("durability"), "none")

        created_task = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="task",
            action="create",
            args={"task_id": "task-pm-response", "title": "Response task", "summary": "seed"},
        )
        self.assertTrue(created_task.get("ok"), msg=created_task)
        self.assertTrue(created_task.get("state_changed"), msg=created_task)
        self.assertEqual(created_task.get("durability"), "durable")

        written_file = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"path": "pm/prototypes/response.html", "content": "<html>ok</html>"},
        )
        self.assertTrue(written_file.get("ok"), msg=written_file)
        self.assertTrue(written_file.get("state_changed"), msg=written_file)
        self.assertEqual(written_file.get("durability"), "durable")

        created_artifact = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "task_id": "task-pm-response",
                "kind": "prd",
                "title": "Response PRD",
                "summary": "seed",
                "content": {"body": "prd"},
                "source_refs": [
                    {"type": "note", "label": "response-seed"},
                    {"type": "buddybox", "path": "pm/prototypes/response.html"},
                ],
            },
        )
        self.assertTrue(created_artifact.get("ok"), msg=created_artifact)
        self.assertTrue(created_artifact.get("state_changed"), msg=created_artifact)
        artifact_id = str(created_artifact.get("artifact_id"))

        issued_evidence = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "artifact", "target_id": artifact_id},
        )
        self.assertTrue(issued_evidence.get("ok"), msg=issued_evidence)
        self.assertTrue(issued_evidence.get("state_changed"), msg=issued_evidence)
        self.assertEqual(issued_evidence.get("durability"), "transient token")
        evidence = issued_evidence.get("tool_evidence")
        self.assertIsInstance(evidence, dict, msg=issued_evidence)
        assert isinstance(evidence, dict)
        self.assertEqual(evidence.get("target_type"), "artifact")
        self.assertEqual(evidence.get("target_id"), artifact_id)
        self.assertNotIn("run_id", evidence)

    def test_rejections_expose_machine_readable_recovery_contract(self) -> None:
        pm_instance = self._instance_json(buddy="pm", instance_id="inst-pm-reject")
        design_instance = self._instance_json(buddy="design", instance_id="inst-design-reject")

        missing_task = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={"kind": "prd", "title": "bad", "content": {"body": "x"}},
        )
        self._assert_rejection_contract(missing_task)
        self.assertEqual((missing_task.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")

        traversal = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="buddybox",
            action="write",
            args={"path": "../escape.txt", "content": "x"},
        )
        self._assert_rejection_contract(traversal)
        self.assertEqual((traversal.get("error") or {}).get("code"), "E_BUDDYBOX_SCOPE")

        created_pm_task = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="task",
            action="create",
            args={"task_id": "task-pm-reject", "title": "Owned task", "summary": "seed"},
        )
        self.assertTrue(created_pm_task.get("ok"), msg=created_pm_task)
        created_pm_artifact = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-reject-r1",
                "task_id": "task-pm-reject",
                "kind": "spec",
                "title": "Owned artifact",
                "summary": "seed",
                "content": {"body": "pm"},
            },
        )
        self.assertTrue(created_pm_artifact.get("ok"), msg=created_pm_artifact)

        foreign_update = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-reject",
            buddy="design",
            tool="artifact",
            action="update_metadata",
            args={"artifact_id": "art-pm-reject-r1", "summary": "overwrite"},
        )
        self._assert_rejection_contract(foreign_update)
        self.assertEqual((foreign_update.get("error") or {}).get("code"), "E_ARTIFACT_BUDDY_SCOPE")

        bad_target = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-reject",
            buddy="pm",
            tool="evidence",
            action="issue_browser",
            args={"target_type": "run", "target_id": "run-old"},
        )
        self._assert_rejection_contract(bad_target)
        self.assertEqual((bad_target.get("error") or {}).get("code"), "E_EVIDENCE_TARGET_TYPE")

    def test_registry_and_response_hints_exclude_run_and_binding(self) -> None:
        supported = set(tool_contracts.supported_tools())
        self.assertNotIn("run", supported)
        self.assertNotIn("binding", supported)

        all_actions = {
            f"{tool}.{action}"
            for tool in tool_contracts.supported_tools()
            for action in tool_contracts.supported_actions(tool)
        }
        self.assertNotIn("task.get_current", all_actions)
        self.assertNotIn("track.get_current", all_actions)

        instance_id = "inst-pm-hints"
        instance_json = self._instance_json(buddy="pm", instance_id=instance_id)
        sample = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={"kind": "prd", "title": "bad", "content": {"body": "x"}},
        )
        self._assert_rejection_contract(sample)

        for hint in sample.get("allowed_next_actions", []):
            if not isinstance(hint, str):
                continue
            lowered = hint.lower()
            self.assertNotIn("run.", lowered)
            self.assertNotIn("binding.", lowered)
            self.assertNotIn("runs/raw", lowered)
            self.assertNotIn("content/runs", lowered)


if __name__ == "__main__":
    unittest.main()
