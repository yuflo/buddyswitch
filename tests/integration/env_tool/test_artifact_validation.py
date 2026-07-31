"""Artifact module validation integration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.env.repos import runtime_files
from buddyswitch.modules.artifact.private.state import artifacts as artifact_repo
from buddyswitch.modules.track.private.state import track_comments as track_comment_repo
from buddyswitch.modules.track.private.state import tracks as track_repo
from tests.support import object_builders
import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.integration.env_tool._artifact_env_tool_case import ArtifactEnvToolCase

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class ArtifactValidationTests(ArtifactEnvToolCase):
    def test_legacy_kind_fixture_is_rejected_without_normalization(self) -> None:
        legacy = {
            "id": "art-legacy-normalize-r1",
            "title": "Legacy normalize",
            "task_id": "task-design-legacy",
            "role": "design",
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
        path = artifact_repo.artifact_file("art-legacy-normalize-r1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(legacy, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "retired"):
            artifact_repo.get_artifact("art-legacy-normalize-r1")

    def test_validate_payload_rejects_retired_fields(self) -> None:
        instance_json = self._instance_json(actor_id="act-pm-art", role="pm")
        for field, value in (
            ("task_id", "task-old"),
            ("kind", "prd"),
            ("content", {"body": "legacy"}),
        ):
            payload = self._dispatch(
                instance_json=instance_json,
                actor_id="act-pm-art",
                role="pm",
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
        normalized = artifact_repo.validate_artifact(
            {
                "id": "art-attachments-normalize-r1",
                "title": "Normalize attachments",
                "summary": "seed",
                "body": "body",
                "template": "brief",
                "revision": 1,
                "is_current": True,
                "supersedes_artifact_id": None,
                "created_by_identity_id": "act-pm-artifact-normalize",
                "author_identity_ids": ["act-pm-artifact-normalize"],
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
            "revision": 1,
            "is_current": True,
            "supersedes_artifact_id": None,
            "created_by_identity_id": "act-pm-artifact-invalid",
            "author_identity_ids": ["act-pm-artifact-invalid"],
            "source_refs": None,
            "created_at": "2026-05-22T10:00:00+08:00",
            "updated_at": "2026-05-22T10:00:00+08:00",
        }
        invalid_rows = (
            {"attachment_id": "att-unsafe", "filename": "../escape.txt", "content_type": "text/plain", "size_bytes": 1, "sha256": "a" * 64, "created_by_identity_id": "act-pm-attachment", "created_at": "2026-05-22T10:00:00+08:00"},
            {"attachment_id": "att-missing-hash", "filename": "safe.txt", "content_type": "text/plain", "size_bytes": 1, "created_by_identity_id": "act-pm-attachment", "created_at": "2026-05-22T10:00:00+08:00"},
            {"attachment_id": "att-bad-route", "filename": "safe.txt", "content_type": "text/plain", "size_bytes": 1, "sha256": "a" * 64, "created_by_identity_id": "", "created_at": "2026-05-22T10:00:00+08:00"},
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    artifact_repo.validate_artifact({**base_artifact, "attachments": [row]})

    def test_create_revision_rejects_direct_publication_without_orphan(self) -> None:
        instance_json = self._instance_json(actor_id="act-pm-art", role="pm")
        created_track = self._create_track(instance_json=instance_json, actor_id="act-pm-art", track_id="track-orphan-guard")
        self.assertTrue(created_track.get("ok"), msg=created_track)

        rejected = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art",
            role="pm",
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

        self.assertFalse(artifact_repo.artifact_file("art-orphan-r1").exists())

        opened = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art",
            role="pm",
            tool="track",
            action="open",
            args={"track_id": "track-orphan-guard"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict, msg=opened)
        assert isinstance(track, dict)
        self.assertEqual(track.get("artifact_relations"), [])
        self.assertNotIn("shared_materials", track)
        self.assertNotIn("close_proof", track)

    def test_create_revision_rejects_status_published_without_mutation(self) -> None:
        instance_json = self._instance_json(actor_id="act-pm-art", role="pm")
        rejected = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art",
            role="pm",
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
        self.assertFalse(artifact_repo.artifact_file("art-reject-status-r1").exists())

    def test_create_revision_creates_private_draft_without_task(self) -> None:
        instance_json = self._instance_json(actor_id="act-pm-art", role="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art",
            role="pm",
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
        self.assertNotIn("status", artifact)
        self.assertNotIn("published_to_track", artifact)
        self.assertEqual(artifact.get("template"), "brief")
        self.assertIn("body", artifact)
        self.assertEqual(artifact.get("currentness"), "draft")
        self.assertNotIn("task_id", artifact)
        self.assertNotIn("kind", artifact)
        self.assertNotIn("content", artifact)
        self.assertNotIn("from_role", artifact)

    def test_create_revision_enforces_role_template_allowlist(self) -> None:
        role_cases = (
            ("pm", ("brief", "decision", "note"), ("design", "proof")),
            ("design", ("design", "brief"), ("decision", "note", "proof")),
            ("dev", ("brief", "note"), ()),
            ("test", ("proof",), ("brief",)),
            ("market", ("brief",), ("design",)),
        )

        for role, allowed_templates, rejected_templates in role_cases:
            for template in allowed_templates:
                artifact_id = f"art-{role}-{template}-allowed"
                actor_id = f"act-{role}-{template}-allowed"
                instance_json = self._instance_json(actor_id=actor_id, role=role)
                created = self._dispatch(
                    instance_json=instance_json,
                    actor_id=actor_id,
                    role=role,
                    tool="artifact",
                    action="create_revision",
                    args={
                        "artifact_id": artifact_id,
                        "title": f"{role} {template} draft",
                        "summary": "allowed template",
                        "template": template,
                        "body": f"{role} can write {template}",
                    },
                )
                with self.subTest(role=role, template=template, expected="allowed"):
                    self.assertTrue(created.get("ok"), msg=created)
                    stored = artifact_repo.get_artifact(artifact_id)
                    self.assertIsInstance(stored, dict, msg=created)
                    assert isinstance(stored, dict)
                    self.assertEqual(stored.get("template"), template)
                    expected_identity_id = self._runtime_actor_id(role=role, label=actor_id)
                    self.assertEqual(stored.get("created_by_identity_id"), expected_identity_id)
                    self.assertEqual(stored.get("author_identity_ids"), [expected_identity_id])
                    self.assertNotIn("created_by_identity", stored)
                    self.assertNotIn("author_identities", stored)
                    self.assertNotIn("created_by", stored)
                    self.assertNotIn("authors", stored)

            for template in rejected_templates:
                artifact_id = f"art-{role}-{template}-denied"
                actor_id = f"act-{role}-{template}-denied"
                instance_json = self._instance_json(actor_id=actor_id, role=role)
                rejected = self._dispatch(
                    instance_json=instance_json,
                    actor_id=actor_id,
                    role=role,
                    tool="artifact",
                    action="create_revision",
                    args={
                        "artifact_id": artifact_id,
                        "title": f"{role} {template} denied",
                        "summary": "rejected template",
                        "template": template,
                        "body": f"{role} should not write {template}",
                    },
                )
                with self.subTest(role=role, template=template, expected="rejected"):
                    self.assertFalse(rejected.get("ok"), msg=rejected)
                    self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_TEMPLATE_PERMISSION")
                    self.assertEqual(rejected.get("permission_boundary"), "artifact.template_permission")
                    self.assertEqual(rejected.get("correctable_fields"), ["template"])
                    self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
                    self.assertEqual(rejected.get("durability"), "none")
                    self.assertFalse(artifact_repo.artifact_file(artifact_id).exists())
