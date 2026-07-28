"""Artifact env.tool integration tests for the single publication path."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.env.repos import artifacts as artifact_repo
from buddyswitch.env.repos import runtime_files
from buddyswitch.env.repos import track_comments as track_comment_repo
from buddyswitch.env.repos import tracks as track_repo
from tests.support import object_builders
from buddyswitch.env.repos import artifacts as artifact_repo  # noqa: E402
import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.integration.env_tool._artifact_env_tool_case import ArtifactEnvToolCase

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class ArtifactAttachmentTests(ArtifactEnvToolCase):
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
        stored = artifact_repo.get_artifact("art-attach-inline-reject")
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
        stored = artifact_repo.get_artifact("art-attach-retired-field")
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
        state_source = self._state_path("buddyswitch/objects/artifacts/not-allowed.txt")
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

        stored = artifact_repo.get_artifact("art-attach-invalid-source")
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
