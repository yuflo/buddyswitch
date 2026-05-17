#!/usr/bin/env python3
"""End-to-end tests for direct track material flow."""

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
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvLayerEndToEndTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, buddy: str) -> Path:
        path = self._runtime_path(f"instance-{buddy}.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": f"inst-{buddy}",
                    "buddy": buddy,
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
        return path

    def _dispatch(self, *, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        instance_json = self._instance_json(buddy)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-e2e-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": f"inst-{buddy}",
                "active_buddy": buddy,
                "tool": tool,
                "action": action,
                "args": args,
            },
            "deadline_ms": 35000,
        }
        envelope = runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertIsInstance(envelope, dict)
        assert isinstance(envelope, dict)
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

    def test_pm_design_dev_test_direct_track_material_flow_without_tasks(self) -> None:
        created = self._dispatch(
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-e2e-main",
                "title": "Landing page first proof",
                "outcome": "Validate whether landing explains core value.",
                "appetite": "2 days",
                "now": {"next": "PM writes PRD", "blocker": None},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        pm_prd = self._dispatch(
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-e2e-main",
                "kind": "prd",
                "label": "PRD",
                "title": "Landing PRD",
                "summary": "scope, constraints, checks",
                "content": {"body": "PM PRD body"},
            },
        )
        self.assertTrue(pm_prd.get("ok"), msg=pm_prd)

        opened_design = self._dispatch(
            buddy="design",
            tool="track",
            action="open",
            args={"track_id": "track-e2e-main"},
        )
        self.assertTrue(opened_design.get("ok"), msg=opened_design)
        self.assertEqual(len(opened_design["track"]["shared_materials"]), 1)

        design_reads_prd = self._dispatch(
            buddy="design",
            tool="artifact",
            action="get",
            args={"artifact_id": pm_prd["artifact_id"]},
        )
        self.assertTrue(design_reads_prd.get("ok"), msg=design_reads_prd)

        design_draft = self._dispatch(
            buddy="design",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-e2e-main",
                "kind": "design-handoff",
                "label": "Draft",
                "title": "Design Draft",
                "summary": "first-screen structure",
                "content": {"body": "Design draft body"},
            },
        )
        self.assertTrue(design_draft.get("ok"), msg=design_draft)

        opened_dev = self._dispatch(
            buddy="dev",
            tool="track",
            action="open",
            args={"track_id": "track-e2e-main"},
        )
        self.assertTrue(opened_dev.get("ok"), msg=opened_dev)
        self.assertEqual(len(opened_dev["track"]["shared_materials"]), 2)

        dev_reads_pm = self._dispatch(
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": pm_prd["artifact_id"]},
        )
        dev_reads_design = self._dispatch(
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": design_draft["artifact_id"]},
        )
        self.assertTrue(dev_reads_pm.get("ok"), msg=dev_reads_pm)
        self.assertTrue(dev_reads_design.get("ok"), msg=dev_reads_design)

        proof = self._dispatch(
            buddy="test",
            tool="track",
            action="add_proof",
            args={
                "track_id": "track-e2e-main",
                "kind": "smoke-test",
                "label": "Smoke",
                "title": "Smoke result",
                "summary": "smoke pass",
                "content": {"result": "pass"},
            },
        )
        self.assertTrue(proof.get("ok"), msg=proof)

        done = self._dispatch(
            buddy="pm",
            tool="track",
            action="update_now",
            args={
                "track_id": "track-e2e-main",
                "state": "done",
                "health": "ok",
                "now": {"next": "ship", "blocker": None},
            },
        )
        self.assertTrue(done.get("ok"), msg=done)

        final_open = self._dispatch(
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-e2e-main"},
        )
        self.assertTrue(final_open.get("ok"), msg=final_open)
        track = final_open["track"]
        self.assertEqual(track["state"], "done")
        self.assertEqual(len(track["shared_materials"]), 2)
        self.assertEqual(len(track["close_proof"]), 1)

        serialized = json.dumps(
            {
                "created": created,
                "pm_prd": pm_prd,
                "opened_design": opened_design,
                "design_reads_prd": design_reads_prd,
                "design_draft": design_draft,
                "opened_dev": opened_dev,
                "dev_reads_pm": dev_reads_pm,
                "dev_reads_design": dev_reads_design,
                "proof": proof,
                "done": done,
                "final_open": final_open,
            },
            ensure_ascii=True,
        )
        for forbidden in (
            "track" + ".join",
            "track" + ".attach_" + "task",
            "track" + ".detach_" + "task",
            "track" + "_task",
            "source_" + "task_id",
            "task_ids",
            "artifact." + "task_id",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
