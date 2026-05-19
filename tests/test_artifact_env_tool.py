#!/usr/bin/env python3
"""Artifact env.tool integration tests for the single publication path."""

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

import env_legacy_store as env_store  # noqa: E402
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
                    "updated_at": "2026-05-18T00:00:00Z",
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

    def _create_track(self, *, instance_json: Path, instance_id: str, track_id: str) -> dict[str, object]:
        return self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": track_id,
                "title": track_id,
                "outcome": "outcome",
                "appetite": "1 day",
                "now": {"next": "seed", "blocker": None},
            },
        )

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

    def test_create_revision_rejects_direct_publication_without_orphan(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        created_track = self._create_track(instance_json=instance_json, instance_id="inst-pm-art", track_id="track-orphan-guard")
        self.assertTrue(created_track.get("ok"), msg=created_track)

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-orphan-r1",
                "title": "Orphan attempt",
                "summary": "should reject",
                "template": "brief",
                "body": "# Body",
                "published_to_track": "track-orphan-guard",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_PUBLICATION_PATH")
        self.assertEqual(rejected.get("permission_boundary"), "artifact.publication_path")
        self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
        self.assertEqual(rejected.get("durability"), "none")
        self.assertIn("published_to_track", rejected.get("correctable_fields", []))

        self.assertFalse(env_store.artifact_file("art-orphan-r1").exists())

        opened = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-orphan-guard"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict, msg=opened)
        assert isinstance(track, dict)
        self.assertEqual(track.get("shared_materials"), [])
        self.assertEqual(track.get("close_proof"), [])

    def test_create_revision_rejects_status_published_without_mutation(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-reject-status-r1",
                "title": "Status reject",
                "summary": "reject",
                "template": "brief",
                "body": "body",
                "status": "published",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_PUBLICATION_PATH")
        self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
        self.assertEqual(rejected.get("durability"), "none")
        self.assertEqual(rejected.get("correctable_fields"), ["status"])
        self.assertFalse(env_store.artifact_file("art-reject-status-r1").exists())

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
                "source_refs": [{"type": "note", "label": "draft-seed"}],
            },
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        self.assertTrue(bool(payload.get("state_changed")), msg=payload)
        self.assertEqual(payload.get("durability"), "durable")
        artifact = payload.get("artifact")
        self.assertIsInstance(artifact, dict, msg=payload)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("status"), "draft")
        self.assertIsNone(artifact.get("published_to_track"))
        self.assertEqual(artifact.get("template"), "brief")
        self.assertIn("body", artifact)
        self.assertEqual(artifact.get("currentness"), "draft")
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

    def test_draft_revision_does_not_replace_current_shared_material(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        self.assertTrue(
            self._create_track(instance_json=instance_pm, instance_id="inst-pm-art", track_id="track-revision-draft").get("ok")
        )
        r1 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-revision-r1",
                "title": "Brief v1",
                "summary": "v1",
                "template": "brief",
                "body": "v1",
            },
        )
        self.assertTrue(r1.get("ok"), msg=r1)
        publish_r1 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-revision-draft",
                "artifact_id": "art-revision-r1",
                "label": "Brief",
                "summary": "v1",
            },
        )
        self.assertTrue(publish_r1.get("ok"), msg=publish_r1)

        r2 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-revision-r2",
                "title": "Brief v2",
                "summary": "v2",
                "template": "brief",
                "body": "v2",
                "supersedes_artifact_id": "art-revision-r1",
            },
        )
        self.assertTrue(r2.get("ok"), msg=r2)
        r2_artifact = r2.get("artifact")
        self.assertIsInstance(r2_artifact, dict, msg=r2)
        assert isinstance(r2_artifact, dict)
        self.assertEqual(r2_artifact.get("status"), "draft")
        self.assertIsNone(r2_artifact.get("published_to_track"))
        self.assertEqual(r2_artifact.get("supersedes_artifact_id"), "art-revision-r1")
        self.assertEqual(r2_artifact.get("currentness"), "draft")

        r1_store = env_store.get_artifact("art-revision-r1")
        self.assertIsInstance(r1_store, dict)
        assert isinstance(r1_store, dict)
        self.assertEqual(r1_store.get("status"), "published")
        self.assertEqual(r1_store.get("published_to_track"), "track-revision-draft")
        self.assertTrue(bool(r1_store.get("is_current")), msg=r1_store)

        opened = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-revision-draft"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict, msg=opened)
        assert isinstance(track, dict)
        self.assertEqual([row.get("artifact_id") for row in track.get("shared_materials", [])], ["art-revision-r1"])

        instance_dev = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        denied = self._dispatch(
            instance_json=instance_dev,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-revision-r2"},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual((denied.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")

    def test_publish_exposes_current_artifact_to_all_buddies(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        self.assertTrue(self._create_track(instance_json=instance_pm, instance_id="inst-pm-art", track_id="track-art-pub").get("ok"))
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
        self.assertEqual(artifact.get("currentness"), "current")

    def test_source_ref_invalid_artifact_id_rejects_without_artifact(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-art-source-invalid", buddy="pm")
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art-source-invalid",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-source-invalid-r1",
                "title": "Invalid source id",
                "summary": "",
                "template": "note",
                "body": "invalid source refs",
                "source_refs": [{"type": "artifact", "id": "Bad.ID"}],
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_SOURCE_REFS")
        self.assertEqual(rejected.get("permission_boundary"), "source_refs.required_fields")
        self.assertFalse(env_store.artifact_file("art-source-invalid-r1").exists())

    def test_source_ref_full_read_claim_accepts_readable_published_artifact(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art-source-read", buddy="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                instance_id="inst-pm-art-source-read",
                track_id="track-source-ref-readable",
            ).get("ok")
        )

        created = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-source-read",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-source-readable-r1",
                "title": "Readable source artifact",
                "summary": "seed",
                "template": "brief",
                "body": "readable shared body",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        published = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-source-read",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-source-ref-readable",
                "artifact_id": "art-source-readable-r1",
                "label": "Readable source artifact",
                "summary": "seed",
            },
        )
        self.assertTrue(published.get("ok"), msg=published)

        instance_dev = self._instance_json(instance_id="inst-dev-art-source-read", buddy="dev")
        derived = self._dispatch(
            instance_json=instance_dev,
            instance_id="inst-dev-art-source-read",
            buddy="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-source-derived-r1",
                "title": "Derived from readable source",
                "summary": "derived",
                "template": "proposal",
                "body": "derived body",
                "source_refs": [{"type": "artifact", "id": "art-source-readable-r1"}],
                "read_claim": "summarized-full-content",
            },
        )
        self.assertTrue(derived.get("ok"), msg=derived)
        artifact = derived.get("artifact")
        self.assertIsInstance(artifact, dict, msg=derived)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("status"), "draft")
        self.assertIn({"type": "artifact", "id": "art-source-readable-r1"}, artifact.get("source_refs") or [])

        persisted = env_store.get_artifact("art-source-derived-r1")
        self.assertIsInstance(persisted, dict)
        assert isinstance(persisted, dict)
        self.assertNotIn("source_run_id", persisted)

    def test_source_ref_full_read_claim_rejects_unreadable_private_draft(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art-source-private", buddy="pm")
        created = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-source-private",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-source-private-r1",
                "title": "Private source artifact",
                "summary": "",
                "template": "brief",
                "body": "private draft source",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        instance_dev = self._instance_json(instance_id="inst-dev-art-source-private", buddy="dev")
        rejected = self._dispatch(
            instance_json=instance_dev,
            instance_id="inst-dev-art-source-private",
            buddy="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-source-private-denied-r1",
                "title": "Should reject unreadable source",
                "summary": "",
                "template": "note",
                "body": "no access",
                "source_refs": [{"type": "artifact", "id": "art-source-private-r1"}],
                "read_claim": "summarized-full-content",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_SOURCE_REFS_READ_SCOPE")
        self.assertEqual(rejected.get("permission_boundary"), "source_refs.read_scope")
        self.assertFalse(env_store.artifact_file("art-source-private-denied-r1").exists())

    def test_superseded_published_artifact_remains_readable_and_traceable(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        self.assertTrue(self._create_track(instance_json=instance_pm, instance_id="inst-pm-art", track_id="track-revision-trace").get("ok"))

        created_r1 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-trace-r1",
                "title": "art-trace-r1",
                "summary": "v1",
                "template": "brief",
                "body": "v1",
            },
        )
        self.assertTrue(created_r1.get("ok"), msg=created_r1)

        publish_r1 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-revision-trace", "artifact_id": "art-trace-r1", "label": "Brief", "summary": "v1"},
        )
        self.assertTrue(publish_r1.get("ok"), msg=publish_r1)

        created_r2 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-trace-r2",
                "title": "art-trace-r2",
                "summary": "v2",
                "template": "brief",
                "body": "v2",
                "supersedes_artifact_id": "art-trace-r1",
            },
        )
        self.assertTrue(created_r2.get("ok"), msg=created_r2)
        publish_r2 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-revision-trace", "artifact_id": "art-trace-r2", "label": "Brief", "summary": "v2"},
        )
        self.assertTrue(publish_r2.get("ok"), msg=publish_r2)
        state_changes = publish_r2.get("state_changes")
        self.assertIsInstance(state_changes, list, msg=publish_r2)
        assert isinstance(state_changes, list)
        changes = {row.get("change") for row in state_changes if isinstance(row, dict)}
        self.assertIn("superseded", changes)

        opened = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-revision-trace"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict, msg=opened)
        assert isinstance(track, dict)
        self.assertEqual([row.get("artifact_id") for row in track.get("shared_materials", [])], ["art-trace-r2"])

        track_store = env_store.get_track("track-revision-trace")
        self.assertIsInstance(track_store, dict)
        assert isinstance(track_store, dict)
        refs = [row for row in track_store.get("shared_materials", []) if isinstance(row, dict)]
        self.assertEqual(len(refs), 2)
        current_map = {str(row.get("artifact_id")): bool(row.get("current")) for row in refs}
        self.assertFalse(current_map["art-trace-r1"])
        self.assertTrue(current_map["art-trace-r2"])

        instance_dev = self._instance_json(instance_id="inst-dev-art", buddy="dev")
        r1_read = self._dispatch(
            instance_json=instance_dev,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-trace-r1"},
        )
        self.assertTrue(r1_read.get("ok"), msg=r1_read)
        self.assertEqual((r1_read.get("artifact") or {}).get("body"), "v1")
        self.assertEqual((r1_read.get("artifact") or {}).get("currentness"), "superseded")

        r2_read = self._dispatch(
            instance_json=instance_dev,
            instance_id="inst-dev-art",
            buddy="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-trace-r2"},
        )
        self.assertTrue(r2_read.get("ok"), msg=r2_read)
        self.assertEqual((r2_read.get("artifact") or {}).get("body"), "v2")
        self.assertEqual((r2_read.get("artifact") or {}).get("currentness"), "current")

    def test_create_revision_from_archived_published_artifact_rejects_without_new_artifact(self) -> None:
        track = env_store.create_track("track-art-revision-archived", "Archived Revision", owner_buddy="pm")
        artifact = env_store.create_artifact_revision(
            artifact_id="art-revision-archived-r1",
            title="Archived source",
            summary="source",
            body="source body",
            template="brief",
            supersedes_artifact_id=None,
            created_by="pm",
            authors=["pm"],
            source_refs=[{"type": "note", "label": "seed"}],
        )
        env_store.publish_track_material(
            track_id=str(track["id"]),
            artifact_id=str(artifact["id"]),
            label="Archived source",
            from_buddy="pm",
            summary="source",
        )
        env_store.update_track(str(track["id"]), {"archived_at": "2026-05-19T00:00:00Z"})
        before_artifacts = {row["id"] for row in env_store.list_artifacts()}
        instance_json = self._instance_json(instance_id="inst-pm-art-archived-revision", buddy="pm")

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-art-archived-revision",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-revision-archived-r2",
                "title": "New archived revision",
                "summary": "new",
                "template": "brief",
                "body": "new body",
                "supersedes_artifact_id": str(artifact["id"]),
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(set(row["id"] for row in env_store.list_artifacts()), before_artifacts)

    def test_archive_track_blocks_track_open_and_published_artifact_reads(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art", buddy="pm")
        self.assertTrue(self._create_track(instance_json=instance_pm, instance_id="inst-pm-art", track_id="track-art-archive").get("ok"))

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


if __name__ == "__main__":
    unittest.main()
