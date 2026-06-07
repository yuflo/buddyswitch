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
    def _instance_json(self, *, actor_id: str, role: str, status: str = "active") -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_root = self._runtime_path(f"instances/{actor_id}")
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        path = instance_root / "instance.json"
        path.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
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
        self._seed_active_task_for_instance(
            instance_json=path,
            role=role,
            actor_id=actor_id,
            task_slug=f"{role}-artifact-env",
        )
        return path

    def _dispatch(
        self,
        *,
        instance_json: Path,
        actor_id: str,
        role: str,
        tool: str,
        action: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-art-{uuid.uuid4().hex}",
            "method": "env.tool",
            "params": {
                "actor_id": actor_id,
                "active_role": role,
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

    def _create_track(self, *, instance_json: Path, actor_id: str, track_id: str) -> dict[str, object]:
        return self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="pm",
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
        path = env_store.artifact_file("art-legacy-normalize-r1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(legacy, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "retired"):
            env_store.get_artifact("art-legacy-normalize-r1")

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
                "created_by_actor": {"actor_id": "act-pm-artifact-normalize", "role_id": "pm"},
                "author_actors": [{"actor_id": "act-pm-artifact-normalize", "role_id": "pm"}],
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
            "created_by_actor": {"actor_id": "act-pm-artifact-invalid", "role_id": "pm"},
            "author_actors": [{"actor_id": "act-pm-artifact-invalid", "role_id": "pm"}],
            "source_refs": None,
            "created_at": "2026-05-22T10:00:00+08:00",
            "updated_at": "2026-05-22T10:00:00+08:00",
        }
        invalid_rows = (
            {"attachment_id": "att-unsafe", "filename": "../escape.txt", "content_type": "text/plain", "size_bytes": 1, "sha256": "a" * 64, "created_by_actor": {"actor_id": "act-pm-attachment", "role_id": "pm"}, "created_at": "2026-05-22T10:00:00+08:00"},
            {"attachment_id": "att-missing-hash", "filename": "safe.txt", "content_type": "text/plain", "size_bytes": 1, "created_by_actor": {"actor_id": "act-pm-attachment", "role_id": "pm"}, "created_at": "2026-05-22T10:00:00+08:00"},
            {"attachment_id": "att-bad-role", "filename": "safe.txt", "content_type": "text/plain", "size_bytes": 1, "sha256": "a" * 64, "created_by_actor": {"actor_id": "act-unknown-attachment", "role_id": "unknown"}, "created_at": "2026-05-22T10:00:00+08:00"},
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    env_store.validate_artifact({**base_artifact, "attachments": [row]})

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

        self.assertFalse(env_store.artifact_file("art-orphan-r1").exists())

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
        self.assertEqual(track.get("shared_materials"), [])
        self.assertEqual(track.get("close_proof"), [])

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
        self.assertFalse(env_store.artifact_file("art-reject-status-r1").exists())

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
        self.assertEqual(artifact.get("status"), "draft")
        self.assertIsNone(artifact.get("published_to_track"))
        self.assertEqual(artifact.get("template"), "brief")
        self.assertIn("body", artifact)
        self.assertEqual(artifact.get("currentness"), "draft")
        self.assertNotIn("task_id", artifact)
        self.assertNotIn("kind", artifact)
        self.assertNotIn("content", artifact)

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
                    stored = env_store.get_artifact(artifact_id)
                    self.assertIsInstance(stored, dict, msg=created)
                    assert isinstance(stored, dict)
                    self.assertEqual(stored.get("template"), template)
                    self.assertEqual(
                        stored.get("created_by_actor"),
                        {"actor_id": self._runtime_actor_id(role=role, label=actor_id), "role_id": role},
                    )
                    self.assertEqual(
                        stored.get("author_actors"),
                        [{"actor_id": self._runtime_actor_id(role=role, label=actor_id), "role_id": role}],
                    )
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
                    self.assertFalse(env_store.artifact_file(artifact_id).exists())

    def test_update_metadata_rejects_template_not_declared_for_active_role_without_mutation(self) -> None:
        instance_json = self._instance_json(actor_id="act-pm-template-update", role="pm")
        created = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-template-update",
            role="pm",
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
            actor_id="act-pm-template-update",
            role="pm",
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
        instance_pm = self._instance_json(actor_id="act-pm-art", role="pm")
        self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-draft-private-r1"},
        )
        self.assertTrue(owner_read.get("ok"), msg=owner_read)

        instance_dev = self._instance_json(actor_id="act-dev-art", role="dev")
        non_owner = self._dispatch(
            instance_json=instance_dev,
            actor_id="act-dev-art",
            role="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-draft-private-r1"},
        )
        self.assertFalse(non_owner.get("ok"), msg=non_owner)
        self.assertEqual((non_owner.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")
        self.assertEqual(non_owner.get("permission_boundary"), "artifact.status")

    def test_same_role_different_actor_cannot_access_private_draft_surfaces(self) -> None:
        owner_actor = "act-pm-draft-owner"
        other_actor = "act-pm-draft-other"
        owner_instance = self._instance_json(actor_id=owner_actor, role="pm")
        other_instance = self._instance_json(actor_id=other_actor, role="pm")

        created = self._dispatch(
            instance_json=owner_instance,
            actor_id=owner_actor,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-same-role-owner-draft",
                "title": "Owner private draft",
                "summary": "same-role isolation",
                "template": "brief",
                "body": "private draft body",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        source = owner_instance.parent / "workspace" / "private" / "screens" / "draft.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("attachment body", encoding="utf-8")
        attached = self._dispatch(
            instance_json=owner_instance,
            actor_id=owner_actor,
            role="pm",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-same-role-owner-draft",
                "filename": "draft.txt",
                "source_path": str(source),
                "content_type": "text/plain",
            },
        )
        self.assertTrue(attached.get("ok"), msg=attached)
        attachment_id = str((attached.get("attachment") or {}).get("attachment_id"))
        self.assertTrue(attachment_id, msg=attached)

        owner_list = self._dispatch(
            instance_json=owner_instance,
            actor_id=owner_actor,
            role="pm",
            tool="artifact",
            action="list",
            args={"status": "draft"},
        )
        self.assertTrue(owner_list.get("ok"), msg=owner_list)
        owner_ids = {
            row.get("artifact_id")
            for row in owner_list.get("artifacts", [])
            if isinstance(row, dict)
        }
        self.assertIn("art-same-role-owner-draft", owner_ids)

        owner_attachment = self._dispatch(
            instance_json=owner_instance,
            actor_id=owner_actor,
            role="pm",
            tool="artifact",
            action="get_attachment",
            args={"artifact_id": "art-same-role-owner-draft", "attachment_id": attachment_id},
        )
        self.assertTrue(owner_attachment.get("ok"), msg=owner_attachment)

        other_get = self._dispatch(
            instance_json=other_instance,
            actor_id=other_actor,
            role="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-same-role-owner-draft"},
        )
        self.assertFalse(other_get.get("ok"), msg=other_get)
        self.assertEqual((other_get.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")

        other_list = self._dispatch(
            instance_json=other_instance,
            actor_id=other_actor,
            role="pm",
            tool="artifact",
            action="list",
            args={"status": "draft"},
        )
        self.assertTrue(other_list.get("ok"), msg=other_list)
        other_ids = {
            row.get("artifact_id")
            for row in other_list.get("artifacts", [])
            if isinstance(row, dict)
        }
        self.assertNotIn("art-same-role-owner-draft", other_ids)

        other_list_attachments = self._dispatch(
            instance_json=other_instance,
            actor_id=other_actor,
            role="pm",
            tool="artifact",
            action="list_attachments",
            args={"artifact_id": "art-same-role-owner-draft"},
        )
        self.assertFalse(other_list_attachments.get("ok"), msg=other_list_attachments)
        self.assertEqual((other_list_attachments.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")

        other_get_attachment = self._dispatch(
            instance_json=other_instance,
            actor_id=other_actor,
            role="pm",
            tool="artifact",
            action="get_attachment",
            args={"artifact_id": "art-same-role-owner-draft", "attachment_id": attachment_id},
        )
        self.assertFalse(other_get_attachment.get("ok"), msg=other_get_attachment)
        self.assertEqual((other_get_attachment.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")

        other_source_ref = self._dispatch(
            instance_json=other_instance,
            actor_id=other_actor,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-same-role-source-claim",
                "title": "Invalid source claim",
                "summary": "claim",
                "template": "brief",
                "body": "claim body",
                "source_refs": [{"type": "artifact", "id": "art-same-role-owner-draft"}],
                "read_claim": "summarized-full-content",
            },
        )
        self.assertFalse(other_source_ref.get("ok"), msg=other_source_ref)
        self.assertEqual(other_source_ref.get("permission_boundary"), "source_refs.read_scope")

        other_supersede = self._dispatch(
            instance_json=other_instance,
            actor_id=other_actor,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-same-role-other-supersede",
                "title": "Invalid supersede",
                "summary": "supersede",
                "template": "brief",
                "body": "replacement",
                "supersedes_artifact_id": "art-same-role-owner-draft",
            },
        )
        self.assertFalse(other_supersede.get("ok"), msg=other_supersede)
        self.assertEqual(other_supersede.get("permission_boundary"), "artifact.revision_scope")

        owner_supersede = self._dispatch(
            instance_json=owner_instance,
            actor_id=owner_actor,
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-same-role-owner-draft-r2",
                "title": "Owner draft r2",
                "summary": "own supersede",
                "template": "brief",
                "body": "replacement",
                "supersedes_artifact_id": "art-same-role-owner-draft",
            },
        )
        self.assertTrue(owner_supersede.get("ok"), msg=owner_supersede)

    def test_draft_revision_does_not_replace_current_shared_material(self) -> None:
        instance_pm = self._instance_json(actor_id="act-pm-art", role="pm")
        self.assertTrue(
            self._create_track(instance_json=instance_pm, actor_id="act-pm-art", track_id="track-revision-draft").get("ok")
        )
        r1 = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
            tool="track",
            action="open",
            args={"track_id": "track-revision-draft"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict, msg=opened)
        assert isinstance(track, dict)
        self.assertEqual([row.get("artifact_id") for row in track.get("shared_materials", [])], ["art-revision-r1"])

        instance_dev = self._instance_json(actor_id="act-dev-art", role="dev")
        denied = self._dispatch(
            instance_json=instance_dev,
            actor_id="act-dev-art",
            role="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-revision-r2"},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual((denied.get("error") or {}).get("code"), "E_ARTIFACT_READ_SCOPE")

    def test_publish_exposes_current_artifact_to_all_buddies(self) -> None:
        instance_pm = self._instance_json(actor_id="act-pm-art", role="pm")
        self.assertTrue(self._create_track(instance_json=instance_pm, actor_id="act-pm-art", track_id="track-art-pub").get("ok"))
        created = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
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

        instance_dev = self._instance_json(actor_id="act-dev-art", role="dev")
        readable = self._dispatch(
            instance_json=instance_dev,
            actor_id="act-dev-art",
            role="dev",
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
        instance_json = self._instance_json(actor_id="act-pm-art-source-invalid", role="pm")
        rejected = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art-source-invalid",
            role="pm",
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

    def test_source_ref_rejects_private_actor_private_logical_name_refs_without_mutation(self) -> None:
        instance_json = self._instance_json(actor_id="act-pm-art-source-actor-private", role="pm")
        rejected_create = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art-source-actor-private",
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-source-actor-private-r1",
                "title": "Invalid source ref type",
                "summary": "",
                "template": "note",
                "body": "invalid source refs",
                "source_refs": [{"type": "actor_private", "logical_name": "prototype/index.html"}],
            },
        )
        self.assertFalse(rejected_create.get("ok"), msg=rejected_create)
        self.assertEqual((rejected_create.get("error") or {}).get("code"), "E_SOURCE_REFS")
        self.assertEqual(rejected_create.get("permission_boundary"), "source_refs.required_fields")
        self.assertFalse(env_store.artifact_file("art-source-actor-private-r1").exists())

        created = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art-source-actor-private",
            role="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-source-update-target",
                "title": "Valid source ref target",
                "summary": "seed",
                "template": "note",
                "body": "seed",
                "source_refs": [{"type": "note", "label": "seed"}],
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        rejected_update = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art-source-actor-private",
            role="pm",
            tool="artifact",
            action="update_metadata",
            args={
                "artifact_id": "art-source-update-target",
                "source_refs": [{"type": "actor_private", "logical_name": "prototype/index.html"}],
            },
        )
        self.assertFalse(rejected_update.get("ok"), msg=rejected_update)
        self.assertEqual((rejected_update.get("error") or {}).get("code"), "E_SOURCE_REFS")
        self.assertEqual(rejected_update.get("permission_boundary"), "source_refs.required_fields")

        stored = env_store.get_artifact("art-source-update-target")
        self.assertIsInstance(stored, dict, msg=rejected_update)
        assert isinstance(stored, dict)
        self.assertEqual(stored.get("source_refs"), [{"type": "note", "label": "seed"}])

    def test_source_ref_full_read_claim_accepts_readable_published_artifact(self) -> None:
        instance_pm = self._instance_json(actor_id="act-pm-art-source-read", role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id="act-pm-art-source-read",
                track_id="track-source-ref-readable",
            ).get("ok")
        )

        created = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-source-read",
            role="pm",
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
            actor_id="act-pm-art-source-read",
            role="pm",
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

        instance_dev = self._instance_json(actor_id="act-dev-art-source-read", role="dev")
        derived = self._dispatch(
            instance_json=instance_dev,
            actor_id="act-dev-art-source-read",
            role="dev",
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
        instance_pm = self._instance_json(actor_id="act-pm-art-source-private", role="pm")
        created = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-source-private",
            role="pm",
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

        instance_dev = self._instance_json(actor_id="act-dev-art-source-private", role="dev")
        rejected = self._dispatch(
            instance_json=instance_dev,
            actor_id="act-dev-art-source-private",
            role="dev",
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
        instance_pm = self._instance_json(actor_id="act-pm-art", role="pm")
        self.assertTrue(self._create_track(instance_json=instance_pm, actor_id="act-pm-art", track_id="track-revision-trace").get("ok"))

        created_r1 = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-revision-trace", "artifact_id": "art-trace-r1", "label": "Brief", "summary": "v1"},
        )
        self.assertTrue(publish_r1.get("ok"), msg=publish_r1)

        created_r2 = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
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

        instance_dev = self._instance_json(actor_id="act-dev-art", role="dev")
        r1_read = self._dispatch(
            instance_json=instance_dev,
            actor_id="act-dev-art",
            role="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-trace-r1"},
        )
        self.assertTrue(r1_read.get("ok"), msg=r1_read)
        self.assertEqual((r1_read.get("artifact") or {}).get("body"), "v1")
        self.assertEqual((r1_read.get("artifact") or {}).get("currentness"), "superseded")

        r2_read = self._dispatch(
            instance_json=instance_dev,
            actor_id="act-dev-art",
            role="dev",
            tool="artifact",
            action="get",
            args={"artifact_id": "art-trace-r2"},
        )
        self.assertTrue(r2_read.get("ok"), msg=r2_read)
        self.assertEqual((r2_read.get("artifact") or {}).get("body"), "v2")
        self.assertEqual((r2_read.get("artifact") or {}).get("currentness"), "current")

    def test_create_revision_from_archived_published_artifact_rejects_without_new_artifact(self) -> None:
        track = env_store.create_track("track-art-revision-archived", "Archived Revision", owner_role="pm")
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
            from_role="pm",
            summary="source",
        )
        env_store.update_track(str(track["id"]), {"archived_at": "2026-05-19T00:00:00Z"})
        before_artifacts = {row["id"] for row in env_store.list_artifacts()}
        instance_json = self._instance_json(actor_id="act-pm-art-archived-revision", role="pm")

        rejected = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-art-archived-revision",
            role="pm",
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
        instance_pm = self._instance_json(actor_id="act-pm-art", role="pm")
        self.assertTrue(self._create_track(instance_json=instance_pm, actor_id="act-pm-art", track_id="track-art-archive").get("ok"))

        created = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
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
            actor_id="act-pm-art",
            role="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-art-archive"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)

        track_open = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art",
            role="pm",
            tool="track",
            action="open",
            args={"track_id": "track-art-archive"},
        )
        self.assertFalse(track_open.get("ok"), msg=track_open)
        self.assertEqual(track_open.get("permission_boundary"), "track.lifecycle_status")

        for role, actor_id in (("pm", "act-pm-art"), ("dev", "act-dev-art")):
            instance_json = instance_pm if role == "pm" else self._instance_json(actor_id=actor_id, role=role)
            denied = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_id,
                role=role,
                tool="artifact",
                action="get",
                args={"artifact_id": "art-pm-archive-r1"},
            )
            with self.subTest(role=role):
                self.assertFalse(denied.get("ok"), msg=denied)
                self.assertEqual(denied.get("permission_boundary"), "track.lifecycle_status")

    def test_list_returns_owner_draft_summaries_without_body(self) -> None:
        shared_actor_id = "act-art-list-owner"
        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        created_pm_brief = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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

        instance_dev = self._instance_json(actor_id=shared_actor_id, role="dev")
        created_dev_private = self._dispatch(
            instance_json=instance_dev,
            actor_id=shared_actor_id,
            role="dev",
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

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        listed = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
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
        instance_pm = self._instance_json(actor_id="act-pm-art-list-published", role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id="act-pm-art-list-published",
                track_id="track-art-list-published",
            ).get("ok")
        )

        created_r1 = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-published",
            role="pm",
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
            actor_id="act-pm-art-list-published",
            role="pm",
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

        instance_test = self._instance_json(actor_id="act-pm-art-list-published", role="test")
        created_proof = self._dispatch(
            instance_json=instance_test,
            actor_id="act-pm-art-list-published",
            role="test",
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
            actor_id="act-pm-art-list-published",
            role="test",
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

        instance_pm = self._instance_json(actor_id="act-pm-art-list-published", role="pm")
        created_r2 = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-published",
            role="pm",
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
            actor_id="act-pm-art-list-published",
            role="pm",
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
            actor_id="act-pm-art-list-published",
            role="pm",
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
        shared_actor_id = "act-art-list-filter"
        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                track_id="track-art-list-filter",
            ).get("ok")
        )

        created_pm_brief = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
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
                actor_id=shared_actor_id,
                role="pm",
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

        instance_design = self._instance_json(actor_id=shared_actor_id, role="design")
        created_design = self._dispatch(
            instance_json=instance_design,
            actor_id=shared_actor_id,
            role="design",
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
                actor_id=shared_actor_id,
                role="design",
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

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        instance_test = self._instance_json(actor_id=shared_actor_id, role="test")
        created_body_only = self._dispatch(
            instance_json=instance_test,
            actor_id=shared_actor_id,
            role="test",
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
                actor_id=shared_actor_id,
                role="test",
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

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        created_draft = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
            tool="artifact",
            action="list",
            args={"created_by_role": "design"},
        )
        self.assertTrue(created_by_design.get("ok"), msg=created_by_design)
        for row in created_by_design.get("artifacts", []):
            if isinstance(row, dict):
                self.assertEqual((row.get("created_by_actor") or {}).get("role_id"), "design", msg=row)

        template_brief = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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
        instance_pm = self._instance_json(actor_id="act-pm-art-list-invalid", role="pm")
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
                actor_id="act-pm-art-list-invalid",
                role="pm",
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
        instance_pm = self._instance_json(actor_id="act-pm-art-list-archived", role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id="act-pm-art-list-archived",
                track_id="track-art-list-archived",
            ).get("ok")
        )
        created = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-archived",
            role="pm",
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
                actor_id="act-pm-art-list-archived",
                role="pm",
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
                actor_id="act-pm-art-list-archived",
                role="pm",
                tool="track",
                action="archive",
                args={"track_id": "track-art-list-archived"},
            ).get("ok")
        )

        listed = self._dispatch(
            instance_json=instance_pm,
            actor_id="act-pm-art-list-archived",
            role="pm",
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
            actor_id="act-pm-art-list-archived",
            role="pm",
            tool="artifact",
            action="list",
            args={"track_id": "track-art-list-archived"},
        )
        self.assertFalse(track_filtered.get("ok"), msg=track_filtered)
        self.assertEqual(track_filtered.get("state_changed"), False, msg=track_filtered)
        self.assertEqual(track_filtered.get("durability"), "none", msg=track_filtered)

    def test_attach_file_creates_artifact_owned_attachment_summary_without_body_blob(self) -> None:
        actor_id = "act-design-attach"
        instance_json = self._instance_json(actor_id=actor_id, role="design")
        normalized_actor_id = self._runtime_actor_id(role="design", label=actor_id)
        source = self._runtime_path(f"instances/{normalized_actor_id}/workspace/private/screenshots/desktop.png")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"\x89PNG\r\n\x1a\n")

        created = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="design",
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
            actor_id=actor_id,
            role="design",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-design-attach-r1",
                "filename": "desktop.png",
                "content_type": "image/png",
                "source_path": str(source),
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
        self.assertNotIn("source_path", attachment)
        self.assertNotIn("path", attachment)
        self.assertNotIn(str(source), json.dumps(attached, ensure_ascii=True))

        attachment_id = str(attachment.get("attachment_id"))
        self.assertTrue(artifact_repo.attachment_file("art-design-attach-r1", attachment_id).exists())

        read = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="design",
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
        self.assertNotIn("source_path", attachments[0])
        self.assertNotIn("path", attachments[0])

    def test_list_attachments_returns_empty_list_for_readable_artifact_without_attachments(self) -> None:
        instance_json = self._instance_json(actor_id="act-pm-empty-attachments", role="pm")
        created = self._dispatch(
            instance_json=instance_json,
            actor_id="act-pm-empty-attachments",
            role="pm",
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
            actor_id="act-pm-empty-attachments",
            role="pm",
            tool="artifact",
            action="list_attachments",
            args={"artifact_id": "art-pm-empty-attachments"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(listed.get("attachments"), [])

    def test_published_attachment_is_readable_by_other_role_through_artifact_visibility(self) -> None:
        actor_id = "act-attach-published"
        instance_pm = self._instance_json(actor_id=actor_id, role="pm")
        normalized_actor_id = self._runtime_actor_id(role="pm", label=actor_id)
        created_track = self._create_track(instance_json=instance_pm, actor_id=actor_id, track_id="track-attach-published")
        self.assertTrue(created_track.get("ok"), msg=created_track)
        created = self._dispatch(
            instance_json=instance_pm,
            actor_id=actor_id,
            role="pm",
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
        source = self._runtime_path(f"instances/{normalized_actor_id}/workspace/private/evidence/evidence.txt")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("hello from PM", encoding="utf-8")
        attached = self._dispatch(
            instance_json=instance_pm,
            actor_id=actor_id,
            role="pm",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-pm-attach-published",
                "filename": "evidence.txt",
                "source_path": str(source),
                "content_type": "text/plain",
            },
        )
        self.assertTrue(attached.get("ok"), msg=attached)
        attachment_id = attached["attachment"]["attachment_id"]
        published = self._dispatch(
            instance_json=instance_pm,
            actor_id=actor_id,
            role="pm",
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

        instance_dev = self._instance_json(actor_id=actor_id, role="dev")
        listed = self._dispatch(
            instance_json=instance_dev,
            actor_id=actor_id,
            role="dev",
            tool="artifact",
            action="list_attachments",
            args={"artifact_id": "art-pm-attach-published"},
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual([row["attachment_id"] for row in listed["attachments"]], [attachment_id])

        fetched = self._dispatch(
            instance_json=instance_dev,
            actor_id=actor_id,
            role="dev",
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
        instance_json = self._instance_json(actor_id="act-attach-inline-reject", role="design")
        source = self._runtime_path("instances/act-attach-inline-reject/workspace/private/screenshots/desktop.png")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"\x89PNG\r\n")
        created = self._dispatch(
            instance_json=instance_json,
            actor_id="act-attach-inline-reject",
            role="design",
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
            actor_id="act-attach-inline-reject",
            role="design",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-attach-inline-reject",
                "filename": "desktop.png",
                "source_path": str(source),
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

    def test_attach_file_rejects_retired_actor_private_source_field_without_mutation(self) -> None:
        instance_json = self._instance_json(actor_id="act-attach-retired-field", role="design")
        created = self._dispatch(
            instance_json=instance_json,
            actor_id="act-attach-retired-field",
            role="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-attach-retired-field",
                "title": "Design handoff",
                "summary": "seed",
                "template": "design",
                "body": "# Handoff",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        retired_field = "_".join(["source", "actor_private", "logical", "name"])
        rejected = self._dispatch(
            instance_json=instance_json,
            actor_id="act-attach-retired-field",
            role="design",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-attach-retired-field",
                "filename": "desktop.png",
                retired_field: "screenshots/desktop.png",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("state_changed"), False, msg=rejected)
        self.assertEqual(rejected.get("durability"), "none", msg=rejected)
        self.assertIn(retired_field, json.dumps(rejected, ensure_ascii=True))
        stored = env_store.get_artifact("art-attach-retired-field")
        self.assertIsInstance(stored, dict, msg=rejected)
        assert isinstance(stored, dict)
        self.assertEqual(stored.get("attachments"), [])

    def test_attach_file_rejects_invalid_source_paths_without_mutation(self) -> None:
        actor_id = "act-attach-invalid-source"
        instance_json = self._instance_json(actor_id=actor_id, role="design")
        created = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_id,
            role="design",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-attach-invalid-source",
                "title": "Design handoff",
                "summary": "seed",
                "template": "design",
                "body": "# Handoff",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        actor_private_root = self._runtime_path(f"instances/{actor_id}/workspace/private")
        actor_private_root.mkdir(parents=True, exist_ok=True)
        directory_source = actor_private_root / "dir-source"
        directory_source.mkdir(parents=True, exist_ok=True)
        empty_source = actor_private_root / "empty.txt"
        empty_source.write_bytes(b"")
        missing_source = actor_private_root / "missing.txt"
        outside_runtime_source = self._runtime_path("external/outside.txt")
        outside_runtime_source.parent.mkdir(parents=True, exist_ok=True)
        outside_runtime_source.write_text("outside\n", encoding="utf-8")
        state_source = self._runtime_path("buddyswitch/objects/artifacts/not-allowed.txt")
        state_source.parent.mkdir(parents=True, exist_ok=True)
        state_source.write_text("state\n", encoding="utf-8")
        global_tmp_source = Path("/tmp") / f"buddyswitch-attach-{actor_id}.txt"
        global_tmp_source.write_text("tmp\n", encoding="utf-8")
        source_root = ROOT / "README.md"
        escape_target = self._runtime_path("escape/secret.txt")
        escape_target.parent.mkdir(parents=True, exist_ok=True)
        escape_target.write_text("secret\n", encoding="utf-8")
        symlink_source = actor_private_root / "links" / "escape.txt"
        symlink_source.parent.mkdir(parents=True, exist_ok=True)
        symlink_source.symlink_to(escape_target)
        self.addCleanup(global_tmp_source.unlink, missing_ok=True)

        cases = {
            "missing": missing_source,
            "directory": directory_source,
            "empty": empty_source,
            "runtime_state": state_source,
            "source_checkout": source_root,
            "global_tmp": global_tmp_source,
            "outside_instance": outside_runtime_source,
            "symlink_escape": symlink_source,
        }

        for name, path in cases.items():
            rejected = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_id,
                role="design",
                tool="artifact",
                action="attach_file",
                args={
                    "artifact_id": "art-attach-invalid-source",
                    "filename": "evidence.txt",
                    "source_path": str(path),
                },
            )
            with self.subTest(case=name):
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual(rejected.get("state_changed"), False, msg=rejected)
                self.assertEqual(rejected.get("durability"), "none", msg=rejected)
                self.assertIn("source_path", rejected.get("correctable_fields", []), msg=rejected)

        stored = env_store.get_artifact("art-attach-invalid-source")
        self.assertIsInstance(stored, dict)
        assert isinstance(stored, dict)
        self.assertEqual(stored.get("attachments"), [])

    def test_get_attachment_rejects_unknown_attachment_id_without_mutation(self) -> None:
        instance_json = self._instance_json(actor_id="act-unknown-attachment", role="pm")
        created = self._dispatch(
            instance_json=instance_json,
            actor_id="act-unknown-attachment",
            role="pm",
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
            actor_id="act-unknown-attachment",
            role="pm",
            tool="artifact",
            action="get_attachment",
            args={"artifact_id": "art-unknown-attachment", "attachment_id": "att-missing"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("state_changed"), False, msg=rejected)
        self.assertEqual(rejected.get("durability"), "none")

    def test_get_relation_summary_includes_publication_and_lineage(self) -> None:
        shared_actor_id = "act-art-rel-lineage"
        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                track_id="track-art-rel-lineage",
            ).get("ok")
        )
        created_r1 = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
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
                actor_id=shared_actor_id,
                role="pm",
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

        instance_dev = self._instance_json(actor_id=shared_actor_id, role="dev")
        created_dev_private = self._dispatch(
            instance_json=instance_dev,
            actor_id=shared_actor_id,
            role="dev",
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

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        created_r2 = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
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
                actor_id=shared_actor_id,
                role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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
        shared_actor_id = "act-art-rel-incoming"
        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        self.assertTrue(
            self._create_track(
                instance_json=instance_pm,
                actor_id=shared_actor_id,
                track_id="track-art-rel-incoming",
            ).get("ok")
        )
        created_target = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
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
                actor_id=shared_actor_id,
                role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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

        instance_dev = self._instance_json(actor_id=shared_actor_id, role="dev")
        private_source = self._dispatch(
            instance_json=instance_dev,
            actor_id=shared_actor_id,
            role="dev",
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

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        request_target = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
            tool="request",
            action="create",
            args={
                "track_id": "track-art-rel-incoming",
                "to_role": "dev",
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
            actor_id=shared_actor_id,
            role="pm",
            tool="request",
            action="create",
            args={
                "track_id": "track-art-rel-incoming",
                "to_role": "dev",
                "title": "Produce result",
                "summary": "Result ref request",
                "target_refs": [{"type": "track", "id": "track-art-rel-incoming"}],
            },
        )
        self.assertTrue(request_result.get("ok"), msg=request_result)
        request_result_id = str(request_result.get("request_id") or "")
        self.assertTrue(request_result_id)
        instance_dev = self._instance_json(actor_id=shared_actor_id, role="dev")
        accepted = self._dispatch(
            instance_json=instance_dev,
            actor_id=shared_actor_id,
            role="dev",
            tool="request",
            action="accept",
            args={"request_id": request_result_id},
        )
        self.assertTrue(accepted.get("ok"), msg=accepted)
        completed = self._dispatch(
            instance_json=instance_dev,
            actor_id=shared_actor_id,
            role="dev",
            tool="request",
            action="complete",
            args={
                "request_id": request_result_id,
                "result_refs": [{"type": "artifact", "id": "art-rel-target"}],
            },
        )
        self.assertTrue(completed.get("ok"), msg=completed)

        instance_pm = self._instance_json(actor_id=shared_actor_id, role="pm")
        added_update = self._dispatch(
            instance_json=instance_pm,
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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
            actor_id=shared_actor_id,
            role="pm",
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
