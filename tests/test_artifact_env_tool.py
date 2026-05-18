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

    def test_legacy_kind_fixture_loads_as_template_without_shared_publication(self) -> None:
        legacy = {
            "id": "art-legacy-normalize-r1",
            "title": "Legacy normalize",
            "task_id": "task-design-legacy",
            "buddy": "design",
            "kind": "design-handoff",
            "summary": "legacy summary",
            "content": {"body": "legacy body"},
            "revision": 1,
            "is_current": True,
            "supersedes_artifact_id": None,
            "created_by": "design",
            "created_at": "2026-05-18T10:00:00+08:00",
            "updated_at": "2026-05-18T10:01:00+08:00",
        }
        path = env_store.artifact_file("art-legacy-normalize-r1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(legacy, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        normalized = env_store.get_artifact("art-legacy-normalize-r1")
        self.assertIsNotNone(normalized)
        assert isinstance(normalized, dict)
        self.assertEqual(normalized.get("template"), "design")
        self.assertEqual(normalized.get("body"), "legacy body")
        self.assertEqual(normalized.get("status"), "draft")
        self.assertIsNone(normalized.get("published_to_track"))
        self.assertIn("design", normalized.get("authors", []))

    def test_validate_payload_rejects_retired_fields(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        for field, value in (
            ("task_id", "task-old"),
            ("kind", "prd"),
            ("content", {"body": "legacy"}),
        ):
            payload = self._dispatch(
                instance_json=instance_json,
                instance_id="inst-pm-art",
                buddy="pm",
                tool="artifact",
                action="create_revision",
                args={
                    "artifact_id": "art-invalid-retired-r1",
                    "title": "Invalid",
                    "summary": "",
                    "template": "brief",
                    "body": "# body",
                    field: value,
                },
            )
            with self.subTest(field=field):
                self.assertFalse(payload.get("ok"), msg=payload)
                self.assertEqual((payload.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")
                self.assertFalse(bool(payload.get("state_changed")), msg=payload)

    def test_create_revision_creates_private_draft_without_task(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-draft-r1",
                "title": "Draft",
                "summary": "Draft summary",
                "template": "brief",
                "body": "# Draft\n\nPrivate draft body.",
                "status": "draft",
                "source_refs": [{"type": "note", "label": "draft-seed"}],
            },
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        artifact = payload.get("artifact")
        self.assertIsInstance(artifact, dict, msg=payload)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("status"), "draft")
        self.assertIsNone(artifact.get("published_to_track"))
        self.assertEqual(artifact.get("template"), "brief")
        self.assertIn("body", artifact)
        self.assertNotIn("task_id", artifact)
        self.assertNotIn("kind", artifact)
        self.assertNotIn("content", artifact)

    def test_draft_is_private_before_publication(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-draft-private-r1",
                "title": "Private Draft",
                "summary": "",
                "template": "note",
                "body": "private",
                "status": "draft",
            },
        )

        owner_read = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-draft-private-r1"},
        )
        self.assertTrue(owner_read.get("ok"), msg=owner_read)

        instance_dev = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        non_owner = self._dispatch(
            instance_json=instance_dev,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-draft-private-r1"},
        )
        self.assertFalse(non_owner.get("ok"), msg=non_owner)
        self.assertEqual((non_owner.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")
        self.assertEqual(non_owner.get("permission_boundary"), "artifact.status")

    def test_publish_exposes_current_artifact_to_all_buddies(self) -> None:
        env_store.create_track("track-art-pub", "Artifact publication", owner_buddy="pm")
        instance_pm = self._instance_json(instance_id="inst-pm-art", buddy="pm")

        created = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-publish-r1",
                "title": "Publish me",
                "summary": "",
                "template": "proposal",
                "body": "public body",
                "status": "draft",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        published = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-art-pub",
                "artifact_id": "art-pm-publish-r1",
                "kind": "proposal",
                "label": "Proposal",
                "summary": "public",
            },
        )
        self.assertTrue(published.get("ok"), msg=published)

        instance_dev = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        readable = self._dispatch(
            instance_json=instance_dev,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-publish-r1"},
        )
        self.assertTrue(readable.get("ok"), msg=readable)
        artifact = readable.get("artifact")
        self.assertIsInstance(artifact, dict, msg=readable)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("status"), "published")
        self.assertEqual(artifact.get("published_to_track"), "track-art-pub")

        opened = self._dispatch(
            instance_json=instance_dev,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="track",
            action="open",
            args={"track_id": "track-art-pub"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict, msg=opened)
        assert isinstance(track, dict)
        rows = track.get("shared_materials")
        self.assertIsInstance(rows, list, msg=opened)
        assert isinstance(rows, list)
        self.assertEqual([row.get("artifact_id") for row in rows], ["art-pm-publish-r1"])
        self.assertEqual(rows[0].get("current"), True)

    def test_archive_track_blocks_track_open_and_published_artifact_reads(self) -> None:
        env_store.create_track("track-art-archive", "Artifact archive", owner_buddy="pm")
        instance_pm = self._instance_json(instance_id="inst-pm-art", buddy="pm")

        created = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-archive-r1",
                "title": "Archive me",
                "summary": "",
                "template": "decision",
                "body": "archive body",
                "status": "draft",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        published = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-art-archive",
                "artifact_id": "art-pm-archive-r1",
                "kind": "decision",
                "label": "Decision",
                "summary": "archive material",
            },
        )
        self.assertTrue(published.get("ok"), msg=published)

        archived = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-art-archive"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)

        track_open = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-art-archive"},
        )
        self.assertFalse(track_open.get("ok"), msg=track_open)
        self.assertEqual(track_open.get("permission_boundary"), "track.lifecycle_status")

        for buddy, instance_id in (("pm", "inst-pm-art"), ("dev", "inst-dev-art")):
            instance_json = instance_pm if buddy == "pm" else self._instance_json(instance_id=instance_id, buddy=buddy)
            denied = self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy=buddy,
                tool="artifact",
                action="get",
                args={"artifact_id": "art-pm-archive-r1"},
            )
            with self.subTest(buddy=buddy):
                self.assertFalse(denied.get("ok"), msg=denied)
                self.assertEqual(denied.get("permission_boundary"), "track.lifecycle_status")

    def test_create_revision_supersedes_current_and_keeps_old_body(self) -> None:
        env_store.create_track("track-art-rev", "Artifact revisions", owner_buddy="pm")
        instance_pm = self._instance_json(instance_id="inst-pm-art", buddy="pm")

        r1 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-rev-r1",
                "title": "Scope v1",
                "summary": "v1",
                "template": "brief",
                "body": "body-v1",
                "status": "draft",
            },
        )
        self.assertTrue(r1.get("ok"), msg=r1)

        r2 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-rev-r2",
                "title": "Scope v2",
                "summary": "v2",
                "template": "brief",
                "body": "body-v2",
                "supersedes_artifact_id": "art-pm-rev-r1",
            },
        )
        self.assertTrue(r2.get("ok"), msg=r2)

        previous = env_store.get_artifact("art-pm-rev-r1")
        self.assertIsNotNone(previous)
        assert isinstance(previous, dict)
        self.assertFalse(previous.get("is_current"))
        self.assertEqual(previous.get("body"), "body-v1")
        latest_before_publish = env_store.get_artifact("art-pm-rev-r2")
        self.assertIsNotNone(latest_before_publish)
        assert isinstance(latest_before_publish, dict)
        self.assertEqual(latest_before_publish.get("revision"), 2)
        self.assertTrue(bool(latest_before_publish.get("is_current")))
        self.assertEqual(latest_before_publish.get("supersedes_artifact_id"), "art-pm-rev-r1")

        published = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-art-rev",
                "artifact_id": "art-pm-rev-r2",
                "kind": "brief",
                "label": "Scope",
                "summary": "v2",
            },
        )
        self.assertTrue(published.get("ok"), msg=published)

        latest = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-pm-rev-r2"},
        )
        self.assertTrue(latest.get("ok"), msg=latest)
        artifact = latest.get("artifact")
        self.assertIsInstance(artifact, dict, msg=latest)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("revision"), 2)
        self.assertEqual(artifact.get("currentness"), "current")

        opened = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-art-rev"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict, msg=opened)
        assert isinstance(track, dict)
        shared_materials = track.get("shared_materials")
        self.assertIsInstance(shared_materials, list, msg=opened)
        assert isinstance(shared_materials, list)
        self.assertEqual([row.get("artifact_id") for row in shared_materials], ["art-pm-rev-r2"])

    def test_create_revision_rejects_non_current_supersedes_target(self) -> None:
        env_store.create_track("track-art-rev-reject", "Artifact revision reject", owner_buddy="pm")
        instance_pm = self._instance_json(instance_id="inst-pm-art", buddy="pm")

        self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-reject-r1",
                "title": "v1",
                "summary": "",
                "template": "note",
                "body": "v1",
                "status": "published",
                "published_to_track": "track-art-rev-reject",
            },
        )
        self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-reject-r2",
                "title": "v2",
                "summary": "",
                "template": "note",
                "body": "v2",
                "supersedes_artifact_id": "art-pm-reject-r1",
            },
        )

        rejected = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-reject-r3",
                "title": "v3",
                "summary": "",
                "template": "note",
                "body": "v3",
                "supersedes_artifact_id": "art-pm-reject-r1",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_PAYLOAD")
        message = str((rejected.get("error") or {}).get("message") or "").lower()
        self.assertIn("current", message)


if __name__ == "__main__":
    unittest.main()
