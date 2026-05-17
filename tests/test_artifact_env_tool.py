#!/usr/bin/env python3
"""Artifact env.tool integration tests."""

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

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class ArtifactEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, instance_id: str, buddy: str, status: str = "active") -> Path:
        path = self._runtime_path("instance.json")
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
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

    def _seed_track_task_artifact(self, *, track_id: str, task_id: str, artifact_id: str, buddy: str) -> str:
        if env_store.get_track(track_id) is None:
            env_store.create_track(track_id, f"Track {track_id}", owner_buddy="pm")
        if env_store.get_task(task_id) is None:
            env_store.create_task(task_id, f"Task {task_id}", buddy=buddy, track_id=track_id)
        artifact = env_store.create_artifact(
            artifact_id=artifact_id,
            title=f"Artifact {artifact_id}",
            buddy=buddy,
            kind="prd" if buddy == "pm" else "design-handoff",
            task_id=task_id,
            summary="seed",
            content={"body": f"content for {artifact_id}"},
            created_by=buddy,
            source_refs=[{"type": "note", "label": "seed"}],
        )
        return str(artifact["id"])

    def test_artifact_source_refs_reject_handoff_type(self) -> None:
        env_store.create_task("task-pm-src-ref", "Task", buddy="pm")
        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="validate_payload",
            args={
                "task_id": "task-pm-src-ref",
                "kind": "prd",
                "title": "Bad ref",
                "summary": "",
                "content": {"body": "x"},
                "source_refs": [{"type": "handoff", "id": "handoff-old"}],
            },
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_SOURCE_REFS")

    def test_non_owner_reads_current_artifact_through_active_track_task_relation(self) -> None:
        self._seed_track_task_artifact(
            track_id="track-read-rel",
            task_id="task-pm-read-rel",
            artifact_id="art-pm-read-rel-r1",
            buddy="pm",
        )
        env_store.create_task("task-dev-read-rel", "Dev relation", buddy="dev", track_id="track-read-rel")

        instance_json = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-read-rel-r1"},
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        artifact = payload.get("artifact")
        self.assertIsInstance(artifact, dict, msg=payload)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("relation"), "track_task")
        self.assertIn("content", artifact)

    def test_non_owner_without_track_task_relation_cannot_read_artifact(self) -> None:
        self._seed_track_task_artifact(
            track_id="track-read-none",
            task_id="task-pm-read-none",
            artifact_id="art-pm-read-none-r1",
            buddy="pm",
        )
        instance_json = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-read-none-r1"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")

    def test_owner_buddy_metadata_does_not_grant_foreign_artifact_read(self) -> None:
        env_store.create_track("track-owner-meta", "Owner meta", owner_buddy="pm")
        env_store.create_task("task-design-owner-meta", "Design task", buddy="design", track_id="track-owner-meta")
        env_store.create_artifact(
            artifact_id="art-design-owner-meta-r1",
            title="Design artifact",
            buddy="design",
            kind="design-handoff",
            task_id="task-design-owner-meta",
            summary="seed",
            content={"body": "design content"},
            created_by="design",
            source_refs=[{"type": "note", "label": "seed"}],
        )

        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-design-owner-meta-r1"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")

    def test_owner_reads_owned_artifact_when_not_archived(self) -> None:
        env_store.create_task("task-pm-owned-read", "Owned task", buddy="pm")
        env_store.create_artifact(
            artifact_id="art-pm-owned-read-r1",
            title="Owned artifact",
            buddy="pm",
            kind="prd",
            task_id="task-pm-owned-read",
            summary="seed",
            content={"body": "owner content"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )

        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-owned-read-r1"},
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        artifact = payload.get("artifact")
        self.assertIsInstance(artifact, dict, msg=payload)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("relation"), "owner")
        self.assertIn("content", artifact)

    def test_artifact_list_rejects_archived_track(self) -> None:
        env_store.create_track("track-arch-list", "Archived list", owner_buddy="pm", status="archived")
        env_store.create_task("task-pm-arch-list", "Task", buddy="pm", track_id="track-arch-list")
        env_store.create_artifact(
            artifact_id="art-pm-arch-list-r1",
            title="Artifact",
            buddy="pm",
            kind="prd",
            task_id="task-pm-arch-list",
            summary="seed",
            content={"body": "x"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )

        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-arch-list"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_TRACK_ARCHIVED")

    def test_artifact_get_rejects_archived_track_even_for_owner(self) -> None:
        env_store.create_track("track-arch-get-owner", "Archived get", owner_buddy="pm", status="archived")
        env_store.create_task("task-pm-arch-get-owner", "Task", buddy="pm", track_id="track-arch-get-owner")
        env_store.create_artifact(
            artifact_id="art-pm-arch-get-owner-r1",
            title="Artifact",
            buddy="pm",
            kind="prd",
            task_id="task-pm-arch-get-owner",
            summary="seed",
            content={"body": "owner body"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )

        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-arch-get-owner-r1"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")
        self.assertEqual(payload.get("permission_boundary"), "track.lifecycle_status")

    def test_artifact_get_rejects_archived_track_for_track_relation(self) -> None:
        env_store.create_track("track-arch-get-rel", "Archived get rel", owner_buddy="pm", status="archived")
        env_store.create_task("task-pm-arch-get-rel", "PM Task", buddy="pm", track_id="track-arch-get-rel")
        env_store.create_task("task-dev-arch-get-rel", "DEV Task", buddy="dev", track_id="track-arch-get-rel")
        env_store.create_artifact(
            artifact_id="art-pm-arch-get-rel-r1",
            title="Artifact",
            buddy="pm",
            kind="prd",
            task_id="task-pm-arch-get-rel",
            summary="seed",
            content={"body": "x"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )

        instance_json = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-arch-get-rel-r1"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")
        self.assertEqual(payload.get("permission_boundary"), "track.lifecycle_status")

    def test_artifact_list_returns_current_revisions_only(self) -> None:
        env_store.create_track("track-current-only", "Current only", owner_buddy="pm")
        env_store.create_task("task-pm-current-only", "Task", buddy="pm", track_id="track-current-only")
        env_store.create_artifact(
            artifact_id="art-pm-current-only-r1",
            title="v1",
            buddy="pm",
            kind="prd",
            task_id="task-pm-current-only",
            summary="v1",
            content={"body": "v1"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.create_artifact(
            artifact_id="art-pm-current-only-r2",
            title="v2",
            buddy="pm",
            kind="prd",
            task_id="task-pm-current-only",
            summary="v2",
            content={"body": "v2"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )

        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-current-only"},
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        rows = payload.get("artifacts")
        self.assertIsInstance(rows, list, msg=payload)
        assert isinstance(rows, list)
        ids = [row.get("artifact_id") for row in rows if isinstance(row, dict)]
        self.assertEqual(ids, ["art-pm-current-only-r2"])

    def test_non_owner_cannot_get_superseded_revision(self) -> None:
        env_store.create_track("track-superseded", "Superseded", owner_buddy="pm")
        env_store.create_task("task-pm-superseded", "PM Task", buddy="pm", track_id="track-superseded")
        env_store.create_task("task-dev-superseded", "DEV Task", buddy="dev", track_id="track-superseded")
        env_store.create_artifact(
            artifact_id="art-pm-superseded-r1",
            title="v1",
            buddy="pm",
            kind="prd",
            task_id="task-pm-superseded",
            summary="v1",
            content={"body": "v1"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.create_artifact(
            artifact_id="art-pm-superseded-r2",
            title="v2",
            buddy="pm",
            kind="prd",
            task_id="task-pm-superseded",
            summary="v2",
            content={"body": "v2"},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )

        instance_json = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-superseded-r1"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("permission_boundary"), "artifact.currentness")

    def test_artifact_read_does_not_depend_on_next_buddy_or_handoff(self) -> None:
        self._seed_track_task_artifact(
            track_id="track-read-direct-rel",
            task_id="task-pm-direct-rel",
            artifact_id="art-pm-direct-rel-r1",
            buddy="pm",
        )
        env_store.create_task("task-dev-direct-rel", "Dev relation", buddy="dev", track_id="track-read-direct-rel")

        instance_json = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-direct-rel-r1"},
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        serialized = json.dumps(payload, ensure_ascii=True)
        self.assertNotIn("next_buddy", serialized)
        self.assertNotIn("\"handoff\":", serialized)
        self.assertNotIn("target_buddy", serialized)
        artifact = payload.get("artifact")
        self.assertIsInstance(artifact, dict, msg=payload)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("relation"), "track_task")
        self.assertIn("content", artifact)

    def test_create_revision_rejects_foreign_task_scope(self) -> None:
        env_store.create_task("task-pm-foreign", "Foreign PM Task", buddy="pm")
        instance_json = self._instance_json(instance_id="inst-dev-art", buddy="dev")

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="create_revision",
            args={
                "task_id": "task-pm-foreign",
                "kind": "implementation-report",
                "title": "Should Fail",
                "summary": "bad",
                "content": {"body": "..."},
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_TASK_SCOPE")

    def test_update_metadata_rejects_non_owner_even_with_track_relation(self) -> None:
        self._seed_track_task_artifact(
            track_id="track-update-metadata",
            task_id="task-pm-update-metadata",
            artifact_id="art-pm-update-metadata-r1",
            buddy="pm",
        )
        env_store.create_task("task-dev-update-metadata", "DEV Task", buddy="dev", track_id="track-update-metadata")

        instance_json = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="update_metadata",
            args={"artifact_id": "art-pm-update-metadata-r1", "summary": "illegal"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_ARTIFACT_BUDDY_SCOPE")

    def test_artifact_summary_relation_labels_are_neutral(self) -> None:
        self._seed_track_task_artifact(
            track_id="track-neutral-rel",
            task_id="task-pm-neutral-rel",
            artifact_id="art-pm-neutral-rel-r1",
            buddy="pm",
        )
        env_store.create_task("task-dev-neutral-rel", "DEV Task", buddy="dev", track_id="track-neutral-rel")

        instance_json = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="list",
            args={"track_id": "track-neutral-rel"},
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        rows = payload.get("artifacts")
        self.assertIsInstance(rows, list, msg=payload)
        assert isinstance(rows, list)
        row = rows[0]
        self.assertIn(row.get("relation"), {"owner", "track_task", "none"})
        self.assertIn("readable_by_active_buddy", row)
        self.assertNotIn("readable_by_current_buddy", row)


if __name__ == "__main__":
    unittest.main()
