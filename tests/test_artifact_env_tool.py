#!/usr/bin/env python3
"""Artifact env.tool integration tests for track publication visibility."""

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


class ArtifactEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, instance_id: str, buddy: str) -> Path:
        path = self._runtime_path(f"instance-{instance_id}.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "active",
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "updated_at": "2026-05-17T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _dispatch(self, *, instance_json: Path, instance_id: str, buddy: str, tool: str, action: str, args: dict[str, object]) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-art-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "instance_id": instance_id,
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

    def _seed_track_with_pm_material(self, track_id: str = "track-art") -> tuple[Path, str]:
        pm_instance = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        created_track = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": track_id,
                "title": "Artifact flow",
                "outcome": "outcome",
                "appetite": "1 day",
                "now": {"next": "publish", "blocker": None},
            },
        )
        self.assertTrue(created_track.get("ok"), msg=created_track)

        material = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": track_id,
                "kind": "prd",
                "label": "PRD",
                "title": "PM PRD",
                "summary": "summary",
                "content": {"body": "PM-PRD-BODY"},
            },
        )
        self.assertTrue(material.get("ok"), msg=material)
        artifact_id = material.get("artifact_id")
        self.assertIsInstance(artifact_id, str)
        assert isinstance(artifact_id, str)
        return pm_instance, artifact_id

    def test_non_owner_reads_current_material_without_task_relation(self) -> None:
        _, artifact_id = self._seed_track_with_pm_material(track_id="track-read-current")
        dev_instance = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        payload = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": artifact_id},
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        artifact = payload.get("artifact")
        self.assertIsInstance(artifact, dict)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("relation"), "track_material")
        self.assertEqual(artifact.get("content", {}).get("body"), "PM-PRD-BODY")
        encoded = json.dumps(artifact, ensure_ascii=True)
        self.assertNotIn("track" + "_task", encoded)
        self.assertNotIn("source_" + "task_id", encoded)

    def test_non_owner_cannot_read_private_draft_artifact(self) -> None:
        design_instance = self._instance_json(instance_id="inst-design-art", buddy="design")
        created = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-art",
            buddy="design",
            tool="artifact",
            action="create_revision",
            args={
                "kind": "design-handoff",
                "title": "Draft",
                "summary": "private draft",
                "content": {"body": "DESIGN-DRAFT"},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        artifact_id = created["artifact_id"]

        dev_instance = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        denied = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": artifact_id},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual((denied.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")
        self.assertEqual(denied.get("permission_boundary"), "artifact.publication")

    def test_non_owner_cannot_read_superseded_material(self) -> None:
        pm_instance, _ = self._seed_track_with_pm_material(track_id="track-superseded")
        first = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-superseded",
                "kind": "prd",
                "label": "PRD",
                "title": "PRD r1",
                "summary": "r1",
                "content": {"body": "R1"},
            },
        )
        second = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-superseded",
                "kind": "prd",
                "label": "PRD",
                "title": "PRD r2",
                "summary": "r2",
                "content": {"body": "R2"},
            },
        )
        self.assertTrue(first.get("ok"), msg=first)
        self.assertTrue(second.get("ok"), msg=second)

        dev_instance = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        denied = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": first["artifact_id"]},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual((denied.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")
        self.assertEqual(denied.get("permission_boundary"), "artifact.currentness")

    def test_create_revision_creates_private_artifact_without_task_id(self) -> None:
        design_instance = self._instance_json(instance_id="inst-design-art", buddy="design")
        created = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-art",
            buddy="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-design-private-r1",
                "kind": "design-handoff",
                "title": "Design private draft",
                "summary": "private",
                "content": {"body": "draft"},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        artifact = created.get("artifact")
        self.assertIsInstance(artifact, dict)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("created_by"), "design")
        self.assertIsNone(artifact.get("published_to_track"))

        invalid = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-art",
            buddy="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-design-invalid-r2",
                "task_id": "task-old",
                "kind": "design-handoff",
                "title": "Invalid",
                "summary": "invalid",
                "content": {"body": "invalid"},
            },
        )
        self.assertFalse(invalid.get("ok"), msg=invalid)
        self.assertEqual((invalid.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")

    def test_task_hint_does_not_grant_artifact_access(self) -> None:
        pm_instance = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        track = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-task-hint",
                "title": "Task hint",
                "outcome": "outcome",
                "appetite": "1 day",
                "now": {"next": "x", "blocker": None},
            },
        )
        self.assertTrue(track.get("ok"), msg=track)

        private = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-private-r1",
                "kind": "prd",
                "title": "Private",
                "summary": "private",
                "content": {"body": "PRIVATE"},
            },
        )
        self.assertTrue(private.get("ok"), msg=private)

        dev_instance = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        self.assertTrue(
            self._dispatch(
                instance_json=dev_instance,
                instance_id="inst-dev-art",
                buddy="dev",
                tool="task",
                action="create",
                args={
                    "task_id": "task-dev-hint",
                    "title": "hint",
                    "track_id": "track-task-hint",
                    "summary": "hint only",
                },
            ).get("ok")
        )

        denied = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": private["artifact_id"]},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual(denied.get("permission_boundary"), "artifact.publication")

    def test_archived_published_artifact_rejects_owner_and_non_owner_reads(self) -> None:
        pm_instance, artifact_id = self._seed_track_with_pm_material(track_id="track-archived-material")
        archived = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-archived-material"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)

        for buddy, instance_id in (("pm", "inst-pm-art"), ("dev", "inst-dev-art")):
            instance_json = pm_instance if buddy == "pm" else self._instance_json(instance_id=instance_id, buddy=buddy)
            denied = self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy=buddy,
                tool="artifact",
                action="get",
                args={"artifact_id": artifact_id},
            )
            with self.subTest(buddy=buddy):
                self.assertFalse(denied.get("ok"), msg=denied)
                self.assertEqual(denied.get("permission_boundary"), "track.lifecycle_status")


if __name__ == "__main__":
    unittest.main()
