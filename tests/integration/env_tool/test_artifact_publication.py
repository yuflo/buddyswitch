"""Artifact module publication integration tests."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.modules.artifact.private.state import artifacts as artifact_repo
from buddyswitch.modules.track.private.state import track_comments as track_comment_repo
from buddyswitch.modules.track.private.state import tracks as track_repo
from tests.support import object_builders
import buddyswitch.foundation.runtime_broker.broker as runtime_broker  # noqa: E402
from tests.integration.env_tool._artifact_env_tool_case import ArtifactEnvToolCase

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class ArtifactPublicationTests(ArtifactEnvToolCase):
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

        stored = artifact_repo.get_artifact("art-pm-template-update")
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
        self.assertEqual(non_owner.get("permission_boundary"), "artifact.relation_scope")

    def test_same_role_different_actor_cannot_access_private_draft_surfaces(self) -> None:
        owner_identity = "act-pm-draft-owner"
        other_actor = "act-pm-draft-other"
        owner_instance = self._instance_json(actor_id=owner_identity, role="pm")
        other_instance = self._instance_json(actor_id=other_actor, role="pm")

        created = self._dispatch(
            instance_json=owner_instance,
            actor_id=owner_identity,
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
            actor_id=owner_identity,
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
            actor_id=owner_identity,
            role="pm",
            tool="artifact",
            action="list",
            args={},
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
            actor_id=owner_identity,
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
            args={},
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
            actor_id=owner_identity,
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
        self.assertNotIn("status", r2_artifact)
        self.assertNotIn("published_to_track", r2_artifact)
        self.assertEqual(r2_artifact.get("supersedes_artifact_id"), "art-revision-r1")
        self.assertEqual(r2_artifact.get("currentness"), "draft")

        r1_store = artifact_repo.get_artifact("art-revision-r1")
        self.assertIsInstance(r1_store, dict)
        assert isinstance(r1_store, dict)
        self.assertNotIn("status", r1_store)
        self.assertNotIn("published_to_track", r1_store)
        self.assertFalse(bool(r1_store.get("is_current")), msg=r1_store)

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
        self.assertEqual([row.get("artifact_id") for row in track.get("artifact_relations", [])], ["art-revision-r1"])

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
        self.assertNotIn("status", artifact)
        self.assertNotIn("published_to_track", artifact)
        self.assertEqual(artifact.get("track_id"), "track-art-pub")
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
        self.assertFalse(artifact_repo.artifact_file("art-source-invalid-r1").exists())

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
        self.assertFalse(artifact_repo.artifact_file("art-source-actor-private-r1").exists())

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

        stored = artifact_repo.get_artifact("art-source-update-target")
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
        self.assertNotIn("status", artifact)
        self.assertIn({"type": "artifact", "id": "art-source-readable-r1"}, artifact.get("source_refs") or [])

        persisted = artifact_repo.get_artifact("art-source-derived-r1")
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
        self.assertFalse(artifact_repo.artifact_file("art-source-private-denied-r1").exists())

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
        self.assertIn("material_relation_superseded", changes)

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
        current_materials = [
            row
            for row in track.get("artifact_relations", [])
            if isinstance(row, dict) and row.get("role") == "material" and bool(row.get("current"))
        ]
        self.assertEqual([row.get("artifact_id") for row in current_materials], ["art-trace-r2"])

        track_store = track_repo.get_track("track-revision-trace")
        self.assertIsInstance(track_store, dict)
        assert isinstance(track_store, dict)
        refs = [row for row in track_store.get("artifact_relations", []) if isinstance(row, dict) and row.get("role") == "material"]
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
