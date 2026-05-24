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
from env.repos import artifacts as artifact_repo  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class ArtifactEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, instance_id: str, buddy: str, status: str = "active") -> Path:
        instance_root = self._runtime_path(f"instances/{instance_id}")
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        path = instance_root / "instance.json"
        path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "instance_root": str(instance_root),
                    "workspace_dir": str(workspace_dir),
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

    def test_validate_artifact_normalizes_missing_attachments_to_empty_list(self) -> None:
        normalized = env_store.validate_artifact(
            {
                "id": "art-attachments-normalize-r1",
                "title": "Normalize attachments",
                "summary": "seed",
                "body": "body",
                "template": "brief",
                "status": "draft",
                "published_to_track": None,
                "revision": 1,
                "is_current": True,
                "supersedes_artifact_id": None,
                "created_by": "pm",
                "authors": ["pm"],
                "source_refs": None,
                "created_at": "2026-05-22T10:00:00+08:00",
                "updated_at": "2026-05-22T10:00:00+08:00",
            }
        )
        self.assertEqual(normalized.get("attachments"), [])

    def test_validate_artifact_rejects_unsafe_attachment_metadata(self) -> None:
        base_artifact = {
            "id": "art-attachments-invalid-r1",
            "title": "Invalid attachments",
            "summary": "seed",
            "body": "body",
            "template": "brief",
            "status": "draft",
            "published_to_track": None,
            "revision": 1,
            "is_current": True,
            "supersedes_artifact_id": None,
            "created_by": "pm",
            "authors": ["pm"],
            "source_refs": None,
            "created_at": "2026-05-22T10:00:00+08:00",
            "updated_at": "2026-05-22T10:00:00+08:00",
        }
        invalid_rows = (
            {"attachment_id": "att-unsafe", "filename": "../escape.txt", "content_type": "text/plain", "size_bytes": 1, "sha256": "a" * 64, "created_by": "pm", "created_at": "2026-05-22T10:00:00+08:00"},
            {"attachment_id": "att-missing-hash", "filename": "safe.txt", "content_type": "text/plain", "size_bytes": 1, "created_by": "pm", "created_at": "2026-05-22T10:00:00+08:00"},
            {"attachment_id": "att-bad-buddy", "filename": "safe.txt", "content_type": "text/plain", "size_bytes": 1, "sha256": "a" * 64, "created_by": "unknown", "created_at": "2026-05-22T10:00:00+08:00"},
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    env_store.validate_artifact({**base_artifact, "attachments": [row]})

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

    def test_create_revision_enforces_manifest_template_permissions(self) -> None:
        buddy_cases = (
            ("pm", ("brief", "decision", "note"), ("design", "proof")),
            ("design", ("design", "brief"), ("decision", "note", "proof")),
            ("dev", ("brief", "note"), ()),
            ("test", ("proof",), ("brief",)),
            ("market", ("brief",), ("design",)),
        )

        for buddy, allowed_templates, rejected_templates in buddy_cases:
            for template in allowed_templates:
                artifact_id = f"art-{buddy}-{template}-allowed"
                instance_id = f"inst-{buddy}-{template}-allowed"
                instance_json = self._instance_json(instance_id=instance_id, buddy=buddy)
                created = self._dispatch(
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy=buddy,
                    tool="artifact",
                    action="create_revision",
                    args={
                        "artifact_id": artifact_id,
                        "title": f"{buddy} {template} draft",
                        "summary": "allowed template",
                        "template": template,
                        "body": f"{buddy} can write {template}",
                    },
                )
                with self.subTest(buddy=buddy, template=template, expected="allowed"):
                    self.assertTrue(created.get("ok"), msg=created)
                    stored = env_store.get_artifact(artifact_id)
                    self.assertIsInstance(stored, dict, msg=created)
                    assert isinstance(stored, dict)
                    self.assertEqual(stored.get("template"), template)
                    self.assertEqual(stored.get("created_by"), buddy)

            for template in rejected_templates:
                artifact_id = f"art-{buddy}-{template}-denied"
                instance_id = f"inst-{buddy}-{template}-denied"
                instance_json = self._instance_json(instance_id=instance_id, buddy=buddy)
                rejected = self._dispatch(
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy=buddy,
                    tool="artifact",
                    action="create_revision",
                    args={
                        "artifact_id": artifact_id,
                        "title": f"{buddy} {template} denied",
                        "summary": "rejected template",
                        "template": template,
                        "body": f"{buddy} should not write {template}",
                    },
                )
                with self.subTest(buddy=buddy, template=template, expected="rejected"):
                    self.assertFalse(rejected.get("ok"), msg=rejected)
                    self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_TEMPLATE_PERMISSION")
                    self.assertEqual(rejected.get("permission_boundary"), "artifact.template_permission")
                    self.assertEqual(rejected.get("correctable_fields"), ["template"])
                    self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
                    self.assertEqual(rejected.get("durability"), "none")
                    self.assertFalse(env_store.artifact_file(artifact_id).exists())

    def test_update_metadata_rejects_template_not_declared_for_active_buddy_without_mutation(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-template-update", buddy="pm")
        created = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-template-update",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-template-update",
                "title": "PM note",
                "summary": "seed",
                "template": "note",
                "body": "seed",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-template-update",
            buddy="pm",
            tool="artifact",
            action="update_metadata",
            args={"artifact_id": "art-pm-template-update", "template": "design"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_TEMPLATE_PERMISSION")
        self.assertEqual(rejected.get("permission_boundary"), "artifact.template_permission")
        self.assertEqual(rejected.get("correctable_fields"), ["template"])
        self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
        self.assertEqual(rejected.get("durability"), "none")

        stored = env_store.get_artifact("art-pm-template-update")
        self.assertIsInstance(stored, dict, msg=rejected)
        assert isinstance(stored, dict)
        self.assertEqual(stored.get("template"), "note")

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
                "template": "brief",
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
                "template": "note",
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

    def test_list_returns_owner_draft_summaries_without_body(self) -> None:
        shared_instance_id = "inst-art-list-owner"
        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        created_pm_brief = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-pm-brief",
                "title": "PM Brief",
                "summary": "Owner brief",
                "template": "brief",
                "body": "brief body",
                "source_refs": [{"type": "note", "label": "seed-brief"}],
            },
        )
        self.assertTrue(created_pm_brief.get("ok"), msg=created_pm_brief)
        created_pm_note = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-pm-note",
                "title": "PM Note",
                "summary": "Owner note",
                "template": "note",
                "body": "note body",
                "source_refs": [{"type": "note", "label": "seed-note"}],
            },
        )
        self.assertTrue(created_pm_note.get("ok"), msg=created_pm_note)

        instance_dev = self._instance_json(instance_id=shared_instance_id, buddy="dev")
        created_dev_private = self._dispatch(
            instance_json=instance_dev,
            instance_id=shared_instance_id,
            buddy="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-dev-private",
                "title": "Dev Private",
                "summary": "Private to dev",
                "template": "note",
                "body": "dev draft body",
            },
        )
        self.assertTrue(created_dev_private.get("ok"), msg=created_dev_private)

        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        listed = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="list",
            args={},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(listed.get("state_changed"), False, msg=listed)
        self.assertEqual(listed.get("durability"), "none", msg=listed)
        rows = listed.get("artifacts")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        rows_by_id = {
            str(row.get("artifact_id")): row
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertIn("art-list-pm-brief", rows_by_id)
        self.assertIn("art-list-pm-note", rows_by_id)
        self.assertNotIn("art-list-dev-private", rows_by_id)
        for artifact_id in ("art-list-pm-brief", "art-list-pm-note"):
            row = rows_by_id[artifact_id]
            self.assertEqual(row.get("status"), "draft", msg=row)
            self.assertEqual(row.get("currentness"), "draft", msg=row)
            self.assertEqual(row.get("relation"), "owner", msg=row)
            self.assertNotIn("body", row, msg=row)
            self.assertIsInstance(row.get("source_refs_summary"), list, msg=row)
            for key in (
                "open_comment_count",
                "resolved_comment_count",
                "incoming_source_ref_count",
                "target_request_count",
                "result_request_count",
                "track_update_ref_count",
                "comment_count",
            ):
                self.assertIn(key, row, msg=row)

    def test_list_returns_published_material_proof_and_history_summaries(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art-list-published", buddy="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                instance_id="inst-pm-art-list-published",
                track_id="track-art-list-published",
            ).get("ok")
        )

        created_r1 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-list-published",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-brief-r1",
                "title": "Brief v1",
                "summary": "v1",
                "template": "brief",
                "body": "v1 body",
            },
        )
        self.assertTrue(created_r1.get("ok"), msg=created_r1)
        published_r1 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-list-published",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-art-list-published",
                "artifact_id": "art-list-brief-r1",
                "label": "Brief",
                "summary": "v1",
            },
        )
        self.assertTrue(published_r1.get("ok"), msg=published_r1)

        instance_test = self._instance_json(instance_id="inst-pm-art-list-published", buddy="test")
        created_proof = self._dispatch(
            instance_json=instance_test,
            instance_id="inst-pm-art-list-published",
            buddy="test",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-proof-r1",
                "title": "Proof v1",
                "summary": "proof",
                "template": "proof",
                "body": "proof body",
            },
        )
        self.assertTrue(created_proof.get("ok"), msg=created_proof)
        published_proof = self._dispatch(
            instance_json=instance_test,
            instance_id="inst-pm-art-list-published",
            buddy="test",
            tool="track",
            action="add_proof",
            args={
                "track_id": "track-art-list-published",
                "artifact_id": "art-list-proof-r1",
                "label": "Close proof",
                "summary": "proof",
            },
        )
        self.assertTrue(published_proof.get("ok"), msg=published_proof)

        instance_pm = self._instance_json(instance_id="inst-pm-art-list-published", buddy="pm")
        created_r2 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-list-published",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-brief-r2",
                "title": "Brief v2",
                "summary": "v2",
                "template": "brief",
                "body": "v2 body",
                "supersedes_artifact_id": "art-list-brief-r1",
            },
        )
        self.assertTrue(created_r2.get("ok"), msg=created_r2)
        published_r2 = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-list-published",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-art-list-published",
                "artifact_id": "art-list-brief-r2",
                "label": "Brief",
                "summary": "v2",
            },
        )
        self.assertTrue(published_r2.get("ok"), msg=published_r2)

        listed = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-list-published",
            buddy="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-art-list-published"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        rows = listed.get("artifacts")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        rows_by_id = {
            str(row.get("artifact_id")): row
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertIn("art-list-brief-r1", rows_by_id)
        self.assertIn("art-list-brief-r2", rows_by_id)
        self.assertIn("art-list-proof-r1", rows_by_id)
        self.assertEqual(rows_by_id["art-list-brief-r2"].get("relation"), "track_material")
        self.assertEqual(rows_by_id["art-list-brief-r2"].get("currentness"), "current")
        self.assertEqual(rows_by_id["art-list-proof-r1"].get("relation"), "track_proof")
        self.assertEqual(rows_by_id["art-list-proof-r1"].get("currentness"), "proof")
        self.assertEqual(rows_by_id["art-list-brief-r1"].get("relation"), "track_history")
        self.assertEqual(rows_by_id["art-list-brief-r1"].get("currentness"), "superseded")
        for row in rows:
            if isinstance(row, dict):
                self.assertNotIn("body", row, msg=row)

    def test_list_filters_are_simple_and_title_summary_only(self) -> None:
        shared_instance_id = "inst-art-list-filter"
        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                instance_id=shared_instance_id,
                track_id="track-art-list-filter",
            ).get("ok")
        )

        created_pm_brief = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-alpha-brief",
                "title": "Alpha Brief",
                "summary": "Signup flow",
                "template": "brief",
                "body": "brief body",
            },
        )
        self.assertTrue(created_pm_brief.get("ok"), msg=created_pm_brief)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                instance_id=shared_instance_id,
                buddy="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-list-filter",
                    "artifact_id": "art-alpha-brief",
                    "label": "Brief",
                    "summary": "Signup flow",
                },
            ).get("ok")
        )

        instance_design = self._instance_json(instance_id=shared_instance_id, buddy="design")
        created_design = self._dispatch(
            instance_json=instance_design,
            instance_id=shared_instance_id,
            buddy="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-alpha-design",
                "title": "Alpha Design",
                "summary": "Visual state",
                "template": "design",
                "body": "design body",
            },
        )
        self.assertTrue(created_design.get("ok"), msg=created_design)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_design,
                instance_id=shared_instance_id,
                buddy="design",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-list-filter",
                    "artifact_id": "art-alpha-design",
                    "label": "Design",
                    "summary": "Visual state",
                },
            ).get("ok")
        )

        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        instance_test = self._instance_json(instance_id=shared_instance_id, buddy="test")
        created_body_only = self._dispatch(
            instance_json=instance_test,
            instance_id=shared_instance_id,
            buddy="test",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-beta-proof",
                "title": "Beta Proof",
                "summary": "Release evidence",
                "template": "proof",
                "body": "Contains SIGNUP keyword only in body.",
            },
        )
        self.assertTrue(created_body_only.get("ok"), msg=created_body_only)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_test,
                instance_id=shared_instance_id,
                buddy="test",
                tool="track",
                action="add_proof",
                args={
                    "track_id": "track-art-list-filter",
                    "artifact_id": "art-beta-proof",
                    "label": "Proof",
                    "summary": "Release evidence",
                },
            ).get("ok")
        )

        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        created_draft = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-filter-draft",
                "title": "Draft Only",
                "summary": "still draft",
                "template": "note",
                "body": "draft body",
            },
        )
        self.assertTrue(created_draft.get("ok"), msg=created_draft)

        q_signup = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="list",
            args={"q": "signup"},
        )
        self.assertTrue(q_signup.get("ok"), msg=q_signup)
        q_ids = {
            str(row.get("artifact_id"))
            for row in (q_signup.get("artifacts") or [])
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertIn("art-alpha-brief", q_ids)
        self.assertNotIn("art-beta-proof", q_ids)

        created_by_design = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="list",
            args={"created_by": "design"},
        )
        self.assertTrue(created_by_design.get("ok"), msg=created_by_design)
        for row in created_by_design.get("artifacts", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("created_by"), "design", msg=row)

        template_brief = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="list",
            args={"template": "brief"},
        )
        self.assertTrue(template_brief.get("ok"), msg=template_brief)
        for row in template_brief.get("artifacts", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("template"), "brief", msg=row)

        published_only = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="list",
            args={"status": "published"},
        )
        self.assertTrue(published_only.get("ok"), msg=published_only)
        published_ids = {
            str(row.get("artifact_id"))
            for row in (published_only.get("artifacts") or [])
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertNotIn("art-filter-draft", published_ids)

        limited = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="list",
            args={"limit": 1},
        )
        self.assertTrue(limited.get("ok"), msg=limited)
        limited_rows = limited.get("artifacts")
        self.assertIsInstance(limited_rows, list, msg=limited)
        assert isinstance(limited_rows, list)
        self.assertEqual(len(limited_rows), 1, msg=limited_rows)

        track_scoped = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-art-list-filter"},
        )
        self.assertTrue(track_scoped.get("ok"), msg=track_scoped)
        for row in track_scoped.get("artifacts", []):
            if isinstance(row, dict):
                self.assertEqual(row.get("published_to_track"), "track-art-list-filter", msg=row)

        default_limit = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="list",
            args={},
        )
        self.assertTrue(default_limit.get("ok"), msg=default_limit)
        default_rows = default_limit.get("artifacts")
        self.assertIsInstance(default_rows, list, msg=default_limit)
        assert isinstance(default_rows, list)
        self.assertLessEqual(len(default_rows), 20)

    def test_list_rejects_invalid_filters_without_state_change(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art-list-invalid", buddy="pm")
        cases = [
            {"unsupported": "x"},
            {"template": "prd"},
            {"status": "live"},
            {"created_by": "unknown"},
            {"q": 123},
            {"limit": 0},
            {"limit": "1"},
            {"track_id": "   "},
            {"track_id": "track-missing"},
        ]
        for args in cases:
            result = self._dispatch(
                instance_json=instance_pm,
                instance_id="inst-pm-art-list-invalid",
                buddy="pm",
                tool="artifact",
                action="list",
                args=args,
            )
            with self.subTest(args=args):
                self.assertFalse(result.get("ok"), msg=result)
                self.assertEqual(result.get("state_changed"), False, msg=result)
                self.assertEqual(result.get("durability"), "none", msg=result)
                self.assertIsInstance(result.get("permission_boundary"), str, msg=result)
                self.assertTrue(str(result.get("permission_boundary")).strip(), msg=result)
                self.assertIsInstance(result.get("why_blocked"), str, msg=result)
                self.assertTrue(str(result.get("why_blocked")).strip(), msg=result)

    def test_list_hides_archived_track_artifacts_and_rejects_archived_track_filter(self) -> None:
        instance_pm = self._instance_json(instance_id="inst-pm-art-list-archived", buddy="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                instance_id="inst-pm-art-list-archived",
                track_id="track-art-list-archived",
            ).get("ok")
        )
        created = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-list-archived",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-list-archived-r1",
                "title": "Archived material",
                "summary": "archive me",
                "template": "brief",
                "body": "archive body",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                instance_id="inst-pm-art-list-archived",
                buddy="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-list-archived",
                    "artifact_id": "art-list-archived-r1",
                    "label": "Archived",
                    "summary": "archive me",
                },
            ).get("ok")
        )
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                instance_id="inst-pm-art-list-archived",
                buddy="pm",
                tool="track",
                action="archive",
                args={"track_id": "track-art-list-archived"},
            ).get("ok")
        )

        listed = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-list-archived",
            buddy="pm",
            tool="artifact",
            action="list",
            args={},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        listed_ids = {
            str(row.get("artifact_id"))
            for row in (listed.get("artifacts") or [])
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertNotIn("art-list-archived-r1", listed_ids)

        track_filtered = self._dispatch(
            instance_json=instance_pm,
            instance_id="inst-pm-art-list-archived",
            buddy="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-art-list-archived"},
        )
        self.assertFalse(track_filtered.get("ok"), msg=track_filtered)
        self.assertEqual(track_filtered.get("state_changed"), False, msg=track_filtered)
        self.assertEqual(track_filtered.get("durability"), "none", msg=track_filtered)

    def test_attach_file_creates_artifact_owned_attachment_summary_without_body_blob(self) -> None:
        instance_id = "inst-design-attach"
        instance_json = self._instance_json(instance_id=instance_id, buddy="design")
        source = self._runtime_path(f"instances/{instance_id}/tmp/chrome-devtools/desktop.png")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"\x89PNG\r\n\x1a\n")

        imported = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="design",
            tool="buddybox",
            action="import_file",
            args={
                "logical_name": "screenshots/desktop.png",
                "source_path": str(source),
                "content_type": "image/png",
            },
        )
        self.assertTrue(imported.get("ok"), msg=imported)

        created = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-design-attach-r1",
                "title": "Design handoff",
                "summary": "handoff",
                "template": "design",
                "body": "# Handoff",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        attached = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="design",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-design-attach-r1",
                "filename": "desktop.png",
                "content_type": "image/png",
                "source_buddybox_logical_name": "screenshots/desktop.png",
            },
        )
        self.assertTrue(attached.get("ok"), msg=attached)
        self.assertTrue(attached.get("state_changed"), msg=attached)
        attachment = attached.get("attachment")
        self.assertIsInstance(attachment, dict, msg=attached)
        assert isinstance(attachment, dict)
        self.assertEqual(attachment.get("filename"), "desktop.png")
        self.assertEqual(attachment.get("content_type"), "image/png")
        self.assertIn("attachment_id", attachment)
        self.assertIn("sha256", attachment)
        self.assertNotIn("content", attachment)
        self.assertNotIn("content_base64", attachment)
        self.assertNotIn("source_buddybox_logical_name", attachment)
        self.assertNotIn("path", attachment)

        attachment_id = str(attachment.get("attachment_id"))
        self.assertTrue(artifact_repo.attachment_file("art-design-attach-r1", attachment_id).exists())

        read = self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="design",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-design-attach-r1"},
        )
        self.assertTrue(read.get("ok"), msg=read)
        artifact = read.get("artifact")
        self.assertIsInstance(artifact, dict, msg=read)
        assert isinstance(artifact, dict)
        attachments = artifact.get("attachments")
        self.assertIsInstance(attachments, list, msg=artifact)
        assert isinstance(attachments, list)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get("attachment_id"), attachment_id)
        self.assertNotIn("content_base64", attachments[0])
        self.assertNotIn("source_buddybox_logical_name", attachments[0])
        self.assertNotIn("path", attachments[0])

    def test_list_attachments_returns_empty_list_for_readable_artifact_without_attachments(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-empty-attachments", buddy="pm")
        created = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-empty-attachments",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-empty-attachments",
                "title": "PM brief",
                "summary": "seed",
                "template": "brief",
                "body": "# Brief",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        listed = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-empty-attachments",
            buddy="pm",
            tool="artifact",
            action="list_attachments",
            args={"artifact_id": "art-pm-empty-attachments"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(listed.get("attachments"), [])

    def test_published_attachment_is_readable_by_other_buddy_through_artifact_visibility(self) -> None:
        instance_id = "inst-attach-published"
        instance_pm = self._instance_json(instance_id=instance_id, buddy="pm")
        created_track = self._create_track(instance_json=instance_pm, instance_id=instance_id, track_id="track-attach-published")
        self.assertTrue(created_track.get("ok"), msg=created_track)
        created = self._dispatch(
            instance_json=instance_pm,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-pm-attach-published",
                "title": "PM brief with attachment",
                "summary": "brief",
                "template": "brief",
                "body": "# Brief",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        source = self._runtime_path(f"instances/{instance_id}/tmp/pm/evidence.txt")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("hello from PM", encoding="utf-8")
        imported = self._dispatch(
            instance_json=instance_pm,
            instance_id=instance_id,
            buddy="pm",
            tool="buddybox",
            action="import_file",
            args={
                "logical_name": "evidence/evidence.txt",
                "source_path": str(source),
                "content_type": "text/plain",
            },
        )
        self.assertTrue(imported.get("ok"), msg=imported)
        attached = self._dispatch(
            instance_json=instance_pm,
            instance_id=instance_id,
            buddy="pm",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-pm-attach-published",
                "filename": "evidence.txt",
                "source_buddybox_logical_name": "evidence/evidence.txt",
                "content_type": "text/plain",
            },
        )
        self.assertTrue(attached.get("ok"), msg=attached)
        attachment_id = attached["attachment"]["attachment_id"]
        published = self._dispatch(
            instance_json=instance_pm,
            instance_id=instance_id,
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-attach-published",
                "artifact_id": "art-pm-attach-published",
                "label": "Brief",
                "summary": "publish",
            },
        )
        self.assertTrue(published.get("ok"), msg=published)

        instance_dev = self._instance_json(instance_id=instance_id, buddy="dev")
        listed = self._dispatch(
            instance_json=instance_dev,
            instance_id=instance_id,
            buddy="dev",
            tool="artifact",
            action="list_attachments",
            args={"artifact_id": "art-pm-attach-published"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual([row["attachment_id"] for row in listed["attachments"]], [attachment_id])

        fetched = self._dispatch(
            instance_json=instance_dev,
            instance_id=instance_id,
            buddy="dev",
            tool="artifact",
            action="get_attachment",
            args={
                "artifact_id": "art-pm-attach-published",
                "attachment_id": attachment_id,
            },
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        self.assertEqual(fetched.get("content_base64"), "aGVsbG8gZnJvbSBQTQ==")

    def test_attach_file_rejects_inline_blob_payload_without_mutation(self) -> None:
        instance_json = self._instance_json(instance_id="inst-attach-inline-reject", buddy="design")
        created = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-attach-inline-reject",
            buddy="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-attach-inline-reject",
                "title": "Design handoff",
                "summary": "seed",
                "template": "design",
                "body": "# Handoff",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-attach-inline-reject",
            buddy="design",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-attach-inline-reject",
                "filename": "desktop.png",
                "source_buddybox_logical_name": "screenshots/desktop.png",
                "content_base64": "aGVsbG8=",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("state_changed"), False, msg=rejected)
        self.assertEqual(rejected.get("durability"), "none")
        stored = env_store.get_artifact("art-attach-inline-reject")
        self.assertIsInstance(stored, dict, msg=rejected)
        assert isinstance(stored, dict)
        self.assertEqual(stored.get("attachments"), [])

    def test_get_attachment_rejects_unknown_attachment_id_without_mutation(self) -> None:
        instance_json = self._instance_json(instance_id="inst-unknown-attachment", buddy="pm")
        created = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-unknown-attachment",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-unknown-attachment",
                "title": "PM brief",
                "summary": "seed",
                "template": "brief",
                "body": "# Brief",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-unknown-attachment",
            buddy="pm",
            tool="artifact",
            action="get_attachment",
            args={"artifact_id": "art-unknown-attachment", "attachment_id": "att-missing"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("state_changed"), False, msg=rejected)
        self.assertEqual(rejected.get("durability"), "none")

    def test_get_relation_summary_includes_publication_and_lineage(self) -> None:
        shared_instance_id = "inst-art-rel-lineage"
        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                instance_id=shared_instance_id,
                track_id="track-art-rel-lineage",
            ).get("ok")
        )
        created_r1 = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-lineage-r1",
                "title": "Lineage v1",
                "summary": "v1",
                "template": "brief",
                "body": "v1",
            },
        )
        self.assertTrue(created_r1.get("ok"), msg=created_r1)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                instance_id=shared_instance_id,
                buddy="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-rel-lineage",
                    "artifact_id": "art-lineage-r1",
                    "label": "Brief",
                    "summary": "v1",
                },
            ).get("ok")
        )

        instance_dev = self._instance_json(instance_id=shared_instance_id, buddy="dev")
        created_dev_private = self._dispatch(
            instance_json=instance_dev,
            instance_id=shared_instance_id,
            buddy="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-lineage-private-r2",
                "title": "Private supersede",
                "summary": "private",
                "template": "brief",
                "body": "private",
                "supersedes_artifact_id": "art-lineage-r1",
            },
        )
        self.assertTrue(created_dev_private.get("ok"), msg=created_dev_private)

        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        created_r2 = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-lineage-r2",
                "title": "Lineage v2",
                "summary": "v2",
                "template": "brief",
                "body": "v2",
                "supersedes_artifact_id": "art-lineage-r1",
            },
        )
        self.assertTrue(created_r2.get("ok"), msg=created_r2)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                instance_id=shared_instance_id,
                buddy="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-rel-lineage",
                    "artifact_id": "art-lineage-r2",
                    "label": "Brief",
                    "summary": "v2",
                },
            ).get("ok")
        )

        fetched = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-lineage-r1"},
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        artifact = fetched.get("artifact")
        self.assertIsInstance(artifact, dict, msg=fetched)
        assert isinstance(artifact, dict)
        relation_summary = artifact.get("relation_summary")
        self.assertIsInstance(relation_summary, dict, msg=artifact)
        assert isinstance(relation_summary, dict)
        publication = relation_summary.get("publication")
        self.assertIsInstance(publication, dict, msg=relation_summary)
        assert isinstance(publication, dict)
        self.assertEqual(publication.get("track_id"), "track-art-rel-lineage")
        self.assertEqual(publication.get("relation"), "track_history")
        self.assertEqual(publication.get("currentness"), "superseded")
        lineage = relation_summary.get("lineage")
        self.assertIsInstance(lineage, dict, msg=relation_summary)
        assert isinstance(lineage, dict)
        self.assertIsNone(lineage.get("supersedes_artifact_id"))
        superseded_by = lineage.get("superseded_by_artifact_ids")
        self.assertIsInstance(superseded_by, list, msg=lineage)
        assert isinstance(superseded_by, list)
        self.assertIn("art-lineage-r2", superseded_by)
        self.assertNotIn("art-lineage-private-r2", superseded_by)

    def test_get_relation_summary_includes_permission_filtered_incoming_refs(self) -> None:
        shared_instance_id = "inst-art-rel-incoming"
        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                instance_id=shared_instance_id,
                track_id="track-art-rel-incoming",
            ).get("ok")
        )
        created_target = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-rel-target",
                "title": "Relation target",
                "summary": "target",
                "template": "brief",
                "body": "target body",
            },
        )
        self.assertTrue(created_target.get("ok"), msg=created_target)
        self.assertTrue(
            self._dispatch(
                instance_json=instance_pm,
                instance_id=shared_instance_id,
                buddy="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-art-rel-incoming",
                    "artifact_id": "art-rel-target",
                    "label": "Target",
                    "summary": "target",
                },
            ).get("ok")
        )

        visible_source = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-rel-source-visible",
                "title": "Visible source",
                "summary": "visible",
                "template": "note",
                "body": "visible",
                "source_refs": [{"type": "artifact", "id": "art-rel-target"}],
            },
        )
        self.assertTrue(visible_source.get("ok"), msg=visible_source)

        instance_dev = self._instance_json(instance_id=shared_instance_id, buddy="dev")
        private_source = self._dispatch(
            instance_json=instance_dev,
            instance_id=shared_instance_id,
            buddy="dev",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-rel-source-private",
                "title": "Private source",
                "summary": "private",
                "template": "note",
                "body": "private",
                "source_refs": [{"type": "artifact", "id": "art-rel-target"}],
            },
        )
        self.assertTrue(private_source.get("ok"), msg=private_source)

        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        request_target = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="request",
            action="create",
            args={
                "track_id": "track-art-rel-incoming",
                "to_buddy": "dev",
                "title": "Use target",
                "summary": "Target ref request",
                "target_refs": [{"type": "artifact", "id": "art-rel-target"}],
            },
        )
        self.assertTrue(request_target.get("ok"), msg=request_target)
        request_target_id = str(request_target.get("request_id") or "")
        self.assertTrue(request_target_id)

        request_result = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="request",
            action="create",
            args={
                "track_id": "track-art-rel-incoming",
                "to_buddy": "dev",
                "title": "Produce result",
                "summary": "Result ref request",
                "target_refs": [{"type": "track", "id": "track-art-rel-incoming"}],
            },
        )
        self.assertTrue(request_result.get("ok"), msg=request_result)
        request_result_id = str(request_result.get("request_id") or "")
        self.assertTrue(request_result_id)
        instance_dev = self._instance_json(instance_id=shared_instance_id, buddy="dev")
        accepted = self._dispatch(
            instance_json=instance_dev,
            instance_id=shared_instance_id,
            buddy="dev",
            tool="request",
            action="accept",
            args={"request_id": request_result_id},
        )
        self.assertTrue(accepted.get("ok"), msg=accepted)
        completed = self._dispatch(
            instance_json=instance_dev,
            instance_id=shared_instance_id,
            buddy="dev",
            tool="request",
            action="complete",
            args={
                "request_id": request_result_id,
                "result_refs": [{"type": "artifact", "id": "art-rel-target"}],
            },
        )
        self.assertTrue(completed.get("ok"), msg=completed)

        instance_pm = self._instance_json(instance_id=shared_instance_id, buddy="pm")
        added_update = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="track",
            action="add_update",
            args={
                "track_id": "track-art-rel-incoming",
                "kind": "progress",
                "summary": "Target update",
                "refs": [{"type": "artifact", "id": "art-rel-target"}],
            },
        )
        self.assertTrue(added_update.get("ok"), msg=added_update)
        update_id = str(added_update.get("update_id") or "")
        if not update_id:
            track = env_store.get_track("track-art-rel-incoming")
            self.assertIsInstance(track, dict, msg=added_update)
            assert isinstance(track, dict)
            updates = [row for row in track.get("updates", []) if isinstance(row, dict)]
            self.assertTrue(updates, msg=track)
            update_id = str(updates[-1].get("id") or "")
        self.assertTrue(update_id)

        comment_root = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="comment",
            action="add",
            args={
                "target_type": "artifact",
                "target_id": "art-rel-target",
                "content": "root comment",
            },
        )
        self.assertTrue(comment_root.get("ok"), msg=comment_root)
        root_comment_id = str(comment_root.get("comment_id") or "")
        self.assertTrue(root_comment_id)

        comment_section = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="comment",
            action="add",
            args={
                "target_type": "artifact_section",
                "target_id": "art-rel-target",
                "content": "section comment",
                "anchor": "#section-1",
            },
        )
        self.assertTrue(comment_section.get("ok"), msg=comment_section)
        section_comment_id = str(comment_section.get("comment_id") or "")
        self.assertTrue(section_comment_id)

        fetched = self._dispatch(
            instance_json=instance_pm,
            instance_id=shared_instance_id,
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-rel-target"},
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        artifact = fetched.get("artifact")
        self.assertIsInstance(artifact, dict, msg=fetched)
        assert isinstance(artifact, dict)
        relation_summary = artifact.get("relation_summary")
        self.assertIsInstance(relation_summary, dict, msg=artifact)
        assert isinstance(relation_summary, dict)
        incoming_refs = relation_summary.get("incoming_refs")
        self.assertIsInstance(incoming_refs, dict, msg=relation_summary)
        assert isinstance(incoming_refs, dict)

        source_rows = incoming_refs.get("source_ref_by_artifacts")
        self.assertIsInstance(source_rows, list, msg=incoming_refs)
        assert isinstance(source_rows, list)
        source_artifact_ids = {
            str(row.get("artifact_id"))
            for row in source_rows
            if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
        }
        self.assertIn("art-rel-source-visible", source_artifact_ids)
        self.assertNotIn("art-rel-source-private", source_artifact_ids)
        for row in source_rows:
            if isinstance(row, dict):
                self.assertNotIn("body", row, msg=row)

        target_rows = incoming_refs.get("target_ref_by_requests")
        self.assertIsInstance(target_rows, list, msg=incoming_refs)
        assert isinstance(target_rows, list)
        target_request_ids = {
            str(row.get("request_id"))
            for row in target_rows
            if isinstance(row, dict) and isinstance(row.get("request_id"), str)
        }
        self.assertIn(request_target_id, target_request_ids)

        result_rows = incoming_refs.get("result_ref_by_requests")
        self.assertIsInstance(result_rows, list, msg=incoming_refs)
        assert isinstance(result_rows, list)
        result_request_ids = {
            str(row.get("request_id"))
            for row in result_rows
            if isinstance(row, dict) and isinstance(row.get("request_id"), str)
        }
        self.assertIn(request_result_id, result_request_ids)

        update_rows = incoming_refs.get("track_update_refs")
        self.assertIsInstance(update_rows, list, msg=incoming_refs)
        assert isinstance(update_rows, list)
        update_ids = {
            str(row.get("update_id"))
            for row in update_rows
            if isinstance(row, dict) and isinstance(row.get("update_id"), str)
        }
        self.assertIn(update_id, update_ids)

        comment_ids = incoming_refs.get("comment_ids")
        self.assertIsInstance(comment_ids, list, msg=incoming_refs)
        assert isinstance(comment_ids, list)
        self.assertIn(root_comment_id, comment_ids)
        self.assertIn(section_comment_id, comment_ids)
        self.assertTrue(all(isinstance(row, str) for row in comment_ids))


if __name__ == "__main__":
    unittest.main()
