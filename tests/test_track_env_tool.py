#!/usr/bin/env python3
"""Track env.tool integration tests for artifact-id publication path."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_legacy_store as env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"
ALL_BUDDIES = ("pm", "design", "dev", "market", "test")


class TrackEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, instance_id: str, buddy: str, status: str = "active") -> Path:
        instance_root = self._instance_root(instance_id)
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
            "request_id": f"req-track-{uuid.uuid4().hex}",
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

    def _pm_instance(self) -> Path:
        return self._instance_json(instance_id="inst-pm-track", buddy="pm")

    def _create_track(self, *, instance_json: Path, track_id: str) -> dict[str, object]:
        return self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
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

    def _create_draft(
        self,
        *,
        instance_json: Path,
        instance_id: str,
        buddy: str,
        artifact_id: str,
        template: str,
        body: str,
        title: str | None = None,
        supersedes_artifact_id: str | None = None,
    ) -> dict[str, object]:
        args: dict[str, object] = {
            "artifact_id": artifact_id,
            "title": title or artifact_id,
            "summary": body,
            "template": template,
            "body": body,
        }
        if supersedes_artifact_id:
            args["supersedes_artifact_id"] = supersedes_artifact_id
        return self._dispatch(
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
            tool="artifact",
            action="create_revision",
            args=args,
        )

    def test_pm_creates_human_readable_track_page(self) -> None:
        instance_json = self._pm_instance()
        created = self._create_track(instance_json=instance_json, track_id="track-human-page")
        self.assertTrue(created.get("ok"), msg=created)
        track = created.get("track")
        self.assertIsInstance(track, dict, msg=created)
        assert isinstance(track, dict)
        self.assertEqual(track.get("owner_buddy"), "pm")
        self.assertEqual(track.get("state"), "active")
        self.assertEqual(track.get("health"), "ok")
        self.assertEqual(track.get("shared_materials"), [])
        self.assertEqual(track.get("updates"), [])
        self.assertEqual(track.get("close_proof"), [])

    def test_non_pm_cannot_create_track(self) -> None:
        instance_json = self._instance_json(instance_id="inst-design-track", buddy="design")
        denied = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="create",
            args={
                "track_id": "track-denied",
                "title": "Denied",
                "outcome": "Denied",
                "appetite": "1 day",
                "now": {"next": "x", "blocker": None},
            },
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual((denied.get("error") or {}).get("code"), "E_TRACK_AUTHORITY")
        self.assertEqual(denied.get("permission_boundary"), "track.lifecycle_authority")

    def test_update_now_rejects_owner_buddy_without_state_mutation(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-owner-buddy-now").get("ok"))
        before = env_store.track_file("track-owner-buddy-now").read_text(encoding="utf-8")

        design_instance = self._instance_json(instance_id="inst-design-owner-now", buddy="design")
        rejected = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-owner-now",
            buddy="design",
            tool="track",
            action="update_now",
            args={
                "track_id": "track-owner-buddy-now",
                "now": {"next": "x", "blocker": None},
                "owner_buddy": "design",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")
        self.assertEqual(rejected.get("permission_boundary"), "request-payload")
        self.assertIs(rejected.get("state_changed"), False)
        self.assertIn("unsupported payload fields: owner_buddy", str(rejected.get("why_blocked")))
        self.assertEqual(env_store.track_file("track-owner-buddy-now").read_text(encoding="utf-8"), before)

    def test_add_update_rejects_owner_buddy_without_state_mutation(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-owner-buddy-update").get("ok"))
        before = env_store.track_file("track-owner-buddy-update").read_text(encoding="utf-8")

        design_instance = self._instance_json(instance_id="inst-design-owner-update", buddy="design")
        rejected = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-owner-update",
            buddy="design",
            tool="track",
            action="add_update",
            args={
                "track_id": "track-owner-buddy-update",
                "summary": "x",
                "owner_buddy": "design",
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")
        self.assertEqual(rejected.get("permission_boundary"), "request-payload")
        self.assertIs(rejected.get("state_changed"), False)
        self.assertIn("unsupported payload fields: owner_buddy", str(rejected.get("why_blocked")))
        self.assertEqual(env_store.track_file("track-owner-buddy-update").read_text(encoding="utf-8"), before)

    def test_add_update_defaults_kind_to_progress_when_omitted(self) -> None:
        pm_instance = self._pm_instance()
        created = self._create_track(instance_json=pm_instance, track_id="track-update-default-kind")
        self.assertTrue(created.get("ok"), msg=created)

        updated = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_update",
            args={
                "track_id": "track-update-default-kind",
                "summary": "default-kind update",
            },
        )
        self.assertTrue(updated.get("ok"), msg=updated)
        self.assertTrue(bool(updated.get("state_changed")), msg=updated)

        track = env_store.get_track("track-update-default-kind")
        self.assertIsInstance(track, dict)
        assert isinstance(track, dict)
        updates = [row for row in track.get("updates", []) if isinstance(row, dict)]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].get("kind"), "progress")

    def test_all_buddies_can_list_and_open_non_archived_tracks(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-shared-open").get("ok"))
        for buddy in ALL_BUDDIES:
            instance_id = f"inst-{buddy}-track"
            instance_json = self._instance_json(instance_id=instance_id, buddy=buddy)
            listed = self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy=buddy,
                tool="track",
                action="list",
                args={},
            )
            opened = self._dispatch(
                instance_json=instance_json,
                instance_id=instance_id,
                buddy=buddy,
                tool="track",
                action="open",
                args={"track_id": "track-shared-open"},
            )
            with self.subTest(buddy=buddy):
                self.assertTrue(listed.get("ok"), msg=listed)
                self.assertTrue(opened.get("ok"), msg=opened)

    def test_track_publish_rejects_legacy_inline_payload_without_mutation(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=instance_json, track_id="track-legacy-inline").get("ok"))

        before = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-legacy-inline"},
        )
        self.assertTrue(before.get("ok"), msg=before)
        baseline = before.get("track")
        self.assertIsInstance(baseline, dict, msg=before)
        assert isinstance(baseline, dict)
        baseline_copy = deepcopy(baseline)

        for action, payload in (
            (
                "add_material",
                {
                    "track_id": "track-legacy-inline",
                    "kind": "prd",
                    "label": "PRD",
                    "title": "Legacy",
                    "summary": "legacy",
                    "content": {"body": "legacy"},
                },
            ),
            (
                "add_proof",
                {
                    "track_id": "track-legacy-inline",
                    "kind": "proof",
                    "label": "Smoke",
                    "title": "Legacy",
                    "summary": "legacy",
                    "content": {"body": "legacy"},
                },
            ),
        ):
            rejected = self._dispatch(
                instance_json=instance_json,
                instance_id="inst-pm-track",
                buddy="pm",
                tool="track",
                action=action,
                args=payload,
            )
            with self.subTest(action=action):
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")
                self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
                self.assertEqual(rejected.get("durability"), "none")

                after = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-pm-track",
                    buddy="pm",
                    tool="track",
                    action="open",
                    args={"track_id": "track-legacy-inline"},
                )
                self.assertTrue(after.get("ok"), msg=after)
                self.assertEqual(after.get("track"), baseline_copy)

    def test_add_material_publishes_existing_draft_and_track_ref(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=instance_json, track_id="track-material-publish").get("ok"))
        draft = self._create_draft(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            artifact_id="art-material-r1",
            template="brief",
            body="material body",
        )
        self.assertTrue(draft.get("ok"), msg=draft)

        published = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-material-publish",
                "artifact_id": "art-material-r1",
                "label": "Brief",
                "summary": "Published PM brief",
            },
        )
        self.assertTrue(published.get("ok"), msg=published)
        self.assertTrue(bool(published.get("state_changed")), msg=published)
        self.assertEqual(published.get("durability"), "durable")
        state_changes = published.get("state_changes")
        self.assertIsInstance(state_changes, list, msg=published)
        assert isinstance(state_changes, list)
        changes = {row.get("change") for row in state_changes if isinstance(row, dict)}
        self.assertIn("published_material", changes)
        self.assertIn("material_added", changes)

        artifact = env_store.get_artifact("art-material-r1")
        self.assertIsInstance(artifact, dict)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("status"), "published")
        self.assertEqual(artifact.get("published_to_track"), "track-material-publish")
        self.assertEqual(artifact.get("template"), "brief")
        self.assertEqual(artifact.get("body"), "material body")
        self.assertTrue(bool(artifact.get("is_current")), msg=artifact)

        track_store = env_store.get_track("track-material-publish")
        self.assertIsInstance(track_store, dict)
        assert isinstance(track_store, dict)
        refs = [row for row in track_store.get("shared_materials", []) if isinstance(row, dict)]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].get("artifact_id"), "art-material-r1")
        self.assertEqual(refs[0].get("kind"), "brief")
        self.assertEqual(refs[0].get("label"), "Brief")
        self.assertEqual(refs[0].get("from_buddy"), "pm")
        self.assertEqual(refs[0].get("summary"), "Published PM brief")
        self.assertTrue(bool(refs[0].get("current")), msg=refs[0])
        self.assertEqual(track_store.get("close_proof"), [])

    def test_add_material_replaces_current_only_after_successful_publish(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=instance_json, track_id="track-material-main").get("ok"))
        self.assertTrue(self._create_track(instance_json=instance_json, track_id="track-material-other").get("ok"))
        self.assertTrue(self._create_track(instance_json=instance_json, track_id="track-material-archived").get("ok"))

        r1 = self._create_draft(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            artifact_id="art-replace-r1",
            template="brief",
            body="r1",
        )
        self.assertTrue(r1.get("ok"), msg=r1)
        pub_r1 = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-main", "artifact_id": "art-replace-r1", "label": "Brief", "summary": "r1"},
        )
        self.assertTrue(pub_r1.get("ok"), msg=pub_r1)

        r2 = self._create_draft(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            artifact_id="art-replace-r2",
            template="brief",
            body="r2",
            supersedes_artifact_id="art-replace-r1",
        )
        self.assertTrue(r2.get("ok"), msg=r2)

        archived = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-material-archived"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)

        baseline_track = env_store.get_track("track-material-main")
        baseline_r1 = env_store.get_artifact("art-replace-r1")
        baseline_r2 = env_store.get_artifact("art-replace-r2")
        self.assertIsInstance(baseline_track, dict)
        self.assertIsInstance(baseline_r1, dict)
        self.assertIsInstance(baseline_r2, dict)
        assert isinstance(baseline_track, dict)
        assert isinstance(baseline_r1, dict)
        assert isinstance(baseline_r2, dict)
        baseline_track = deepcopy(baseline_track)
        baseline_r1 = deepcopy(baseline_r1)
        baseline_r2 = deepcopy(baseline_r2)

        cross_track = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-other", "artifact_id": "art-replace-r2", "label": "Brief", "summary": "r2"},
        )
        self.assertFalse(cross_track.get("ok"), msg=cross_track)
        self.assertFalse(bool(cross_track.get("state_changed")), msg=cross_track)
        self.assertEqual(cross_track.get("durability"), "none")
        self.assertEqual(env_store.get_track("track-material-main"), baseline_track)
        self.assertEqual(env_store.get_artifact("art-replace-r1"), baseline_r1)
        self.assertEqual(env_store.get_artifact("art-replace-r2"), baseline_r2)

        archived_reject = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-archived", "artifact_id": "art-replace-r2", "label": "Brief", "summary": "r2"},
        )
        self.assertFalse(archived_reject.get("ok"), msg=archived_reject)
        self.assertEqual(archived_reject.get("permission_boundary"), "track.lifecycle_status")
        self.assertFalse(bool(archived_reject.get("state_changed")), msg=archived_reject)
        self.assertEqual(env_store.get_track("track-material-main"), baseline_track)
        self.assertEqual(env_store.get_artifact("art-replace-r1"), baseline_r1)
        self.assertEqual(env_store.get_artifact("art-replace-r2"), baseline_r2)

        pub_r2 = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-main", "artifact_id": "art-replace-r2", "label": "Brief", "summary": "r2"},
        )
        self.assertTrue(pub_r2.get("ok"), msg=pub_r2)

        track = env_store.get_track("track-material-main")
        r1_store = env_store.get_artifact("art-replace-r1")
        r2_store = env_store.get_artifact("art-replace-r2")
        self.assertIsInstance(track, dict)
        self.assertIsInstance(r1_store, dict)
        self.assertIsInstance(r2_store, dict)
        assert isinstance(track, dict)
        assert isinstance(r1_store, dict)
        assert isinstance(r2_store, dict)
        refs = [row for row in track.get("shared_materials", []) if isinstance(row, dict)]
        self.assertEqual(len(refs), 2)
        by_id = {str(row.get("artifact_id")): bool(row.get("current")) for row in refs}
        self.assertFalse(by_id["art-replace-r1"])
        self.assertTrue(by_id["art-replace-r2"])
        self.assertFalse(bool(r1_store.get("is_current")), msg=r1_store)
        self.assertTrue(bool(r2_store.get("is_current")), msg=r2_store)
        self.assertEqual(r2_store.get("published_to_track"), "track-material-main")

    def test_track_open_exposes_attachment_summaries_for_readable_material_and_proof(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-open-attachments").get("ok"))

        pm_source = self._instance_root("inst-pm-track") / "tmp" / "pm" / "brief-attachment.txt"
        pm_source.parent.mkdir(parents=True, exist_ok=True)
        pm_source.write_text("pm attachment", encoding="utf-8")
        imported_pm = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="buddybox",
            action="import_file",
            args={
                "logical_name": "evidence/brief-attachment.txt",
                "source_path": str(pm_source),
                "content_type": "text/plain",
            },
        )
        self.assertTrue(imported_pm.get("ok"), msg=imported_pm)

        pm_draft = self._create_draft(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            artifact_id="art-track-open-brief-r1",
            template="brief",
            body="# Brief",
        )
        self.assertTrue(pm_draft.get("ok"), msg=pm_draft)
        attached_pm = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-track-open-brief-r1",
                "filename": "brief-attachment.txt",
                "source_buddybox_logical_name": "evidence/brief-attachment.txt",
                "content_type": "text/plain",
            },
        )
        self.assertTrue(attached_pm.get("ok"), msg=attached_pm)
        material_attachment_id = str((attached_pm.get("attachment") or {}).get("attachment_id"))

        published_material = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-open-attachments",
                "artifact_id": "art-track-open-brief-r1",
                "label": "Brief",
                "summary": "brief publish",
            },
        )
        self.assertTrue(published_material.get("ok"), msg=published_material)

        test_instance = self._instance_json(instance_id="inst-test-track-open", buddy="test")
        test_source = self._instance_root("inst-test-track-open") / "tmp" / "test" / "proof-attachment.txt"
        test_source.parent.mkdir(parents=True, exist_ok=True)
        test_source.write_text("proof attachment", encoding="utf-8")
        imported_test = self._dispatch(
            instance_json=test_instance,
            instance_id="inst-test-track-open",
            buddy="test",
            tool="buddybox",
            action="import_file",
            args={
                "logical_name": "evidence/proof-attachment.txt",
                "source_path": str(test_source),
                "content_type": "text/plain",
            },
        )
        self.assertTrue(imported_test.get("ok"), msg=imported_test)

        test_draft = self._create_draft(
            instance_json=test_instance,
            instance_id="inst-test-track-open",
            buddy="test",
            artifact_id="art-track-open-proof-r1",
            template="proof",
            body="# Proof",
        )
        self.assertTrue(test_draft.get("ok"), msg=test_draft)
        attached_test = self._dispatch(
            instance_json=test_instance,
            instance_id="inst-test-track-open",
            buddy="test",
            tool="artifact",
            action="attach_file",
            args={
                "artifact_id": "art-track-open-proof-r1",
                "filename": "proof-attachment.txt",
                "source_buddybox_logical_name": "evidence/proof-attachment.txt",
                "content_type": "text/plain",
            },
        )
        self.assertTrue(attached_test.get("ok"), msg=attached_test)
        proof_attachment_id = str((attached_test.get("attachment") or {}).get("attachment_id"))

        published_proof = self._dispatch(
            instance_json=test_instance,
            instance_id="inst-test-track-open",
            buddy="test",
            tool="track",
            action="add_proof",
            args={
                "track_id": "track-open-attachments",
                "artifact_id": "art-track-open-proof-r1",
                "label": "Proof",
                "summary": "proof publish",
            },
        )
        self.assertTrue(published_proof.get("ok"), msg=published_proof)

        dev_instance = self._instance_json(instance_id="inst-dev-track-open", buddy="dev")
        opened = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-track-open",
            buddy="dev",
            tool="track",
            action="open",
            args={"track_id": "track-open-attachments"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict, msg=opened)
        assert isinstance(track, dict)

        shared_materials = track.get("shared_materials")
        self.assertIsInstance(shared_materials, list, msg=track)
        assert isinstance(shared_materials, list)
        self.assertEqual(len(shared_materials), 1)
        material_ref = shared_materials[0]
        self.assertEqual(material_ref.get("attachment_count"), 1)
        material_attachments = material_ref.get("attachments")
        self.assertIsInstance(material_attachments, list, msg=material_ref)
        assert isinstance(material_attachments, list)
        self.assertEqual([row.get("attachment_id") for row in material_attachments], [material_attachment_id])
        self.assertNotIn("content_base64", material_attachments[0])
        self.assertNotIn("path", material_attachments[0])

        close_proof = track.get("close_proof")
        self.assertIsInstance(close_proof, list, msg=track)
        assert isinstance(close_proof, list)
        self.assertEqual(len(close_proof), 1)
        proof_ref = close_proof[0]
        self.assertEqual(proof_ref.get("attachment_count"), 1)
        proof_attachments = proof_ref.get("attachments")
        self.assertIsInstance(proof_attachments, list, msg=proof_ref)
        assert isinstance(proof_attachments, list)
        self.assertEqual([row.get("attachment_id") for row in proof_attachments], [proof_attachment_id])
        self.assertNotIn("content_base64", proof_attachments[0])
        self.assertNotIn("path", proof_attachments[0])

    def test_add_material_rejects_duplicate_already_bound_and_cross_track_without_state_pollution(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-material-a").get("ok"))
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-material-b").get("ok"))

        draft = self._create_draft(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            artifact_id="art-cross-track-material-r1",
            template="brief",
            body="draft",
        )
        self.assertTrue(draft.get("ok"), msg=draft)
        first_publish = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-a", "artifact_id": "art-cross-track-material-r1", "label": "PRD", "summary": "published-a"},
        )
        self.assertTrue(first_publish.get("ok"), msg=first_publish)

        before_track_a = deepcopy(env_store.get_track("track-material-a"))
        before_track_b = deepcopy(env_store.get_track("track-material-b"))
        before_artifact = deepcopy(env_store.get_artifact("art-cross-track-material-r1"))

        duplicate = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-a", "artifact_id": "art-cross-track-material-r1", "label": "PRD", "summary": "dup"},
        )
        self.assertFalse(duplicate.get("ok"), msg=duplicate)
        self.assertFalse(bool(duplicate.get("state_changed")), msg=duplicate)
        self.assertEqual(duplicate.get("durability"), "none")

        cross_track = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-b", "artifact_id": "art-cross-track-material-r1", "label": "PRD", "summary": "published-b"},
        )
        self.assertFalse(cross_track.get("ok"), msg=cross_track)
        self.assertFalse(bool(cross_track.get("state_changed")), msg=cross_track)
        self.assertEqual(cross_track.get("durability"), "none")

        design_instance = self._instance_json(instance_id="inst-design-track", buddy="design")
        wrong_owner = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-a", "artifact_id": "art-cross-track-material-r1", "label": "PRD", "summary": "wrong-owner"},
        )
        self.assertFalse(wrong_owner.get("ok"), msg=wrong_owner)
        self.assertEqual((wrong_owner.get("error") or {}).get("code"), "E_TRACK_ARTIFACT_SCOPE")
        self.assertFalse(bool(wrong_owner.get("state_changed")), msg=wrong_owner)

        self.assertEqual(env_store.get_track("track-material-a"), before_track_a)
        self.assertEqual(env_store.get_track("track-material-b"), before_track_b)
        self.assertEqual(env_store.get_artifact("art-cross-track-material-r1"), before_artifact)

    def test_add_material_write_failure_rejects_without_track_or_artifact_mutation(self) -> None:
        pm_instance = self._pm_instance()
        track_id = "track-atomic-material"
        artifact_id = "art-atomic-material-r1"
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id=track_id).get("ok"))
        draft = self._create_draft(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            artifact_id=artifact_id,
            template="brief",
            body="atomic body",
        )
        self.assertTrue(draft.get("ok"), msg=draft)

        before_track = deepcopy(env_store.get_track(track_id))
        before_artifact = deepcopy(env_store.get_artifact(artifact_id))
        self.assertIsInstance(before_track, dict)
        self.assertIsInstance(before_artifact, dict)
        assert isinstance(before_track, dict)
        assert isinstance(before_artifact, dict)

        original_save_track = env_store.save_track
        call_count = {"count": 0}

        def _fail_first_track_save(track: dict[str, object]) -> dict[str, object]:
            if track.get("id") == track_id:
                call_count["count"] += 1
                if call_count["count"] == 1:
                    raise ValueError("simulated track save failure")
            return original_save_track(track)

        with mock.patch("env_legacy_store.save_track", side_effect=_fail_first_track_save):
            rejected = self._dispatch(
                instance_json=pm_instance,
                instance_id="inst-pm-track",
                buddy="pm",
                tool="track",
                action="add_material",
                args={"track_id": track_id, "artifact_id": artifact_id, "label": "Brief", "summary": "publish"},
            )

        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
        self.assertEqual(rejected.get("durability"), "none")
        self.assertEqual(env_store.get_track(track_id), before_track)
        self.assertEqual(env_store.get_artifact(artifact_id), before_artifact)

    def test_add_proof_publishes_existing_draft_updates_close_proof_and_update(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-proof-publish").get("ok"))

        test_instance = self._instance_json(instance_id="inst-test-track", buddy="test")
        draft = self._create_draft(
            instance_json=test_instance,
            instance_id="inst-test-track",
            buddy="test",
            artifact_id="art-proof-r1",
            template="proof",
            body="pass",
        )
        self.assertTrue(draft.get("ok"), msg=draft)

        proof = self._dispatch(
            instance_json=test_instance,
            instance_id="inst-test-track",
            buddy="test",
            tool="track",
            action="add_proof",
            args={"track_id": "track-proof-publish", "artifact_id": "art-proof-r1", "label": "Smoke", "summary": "Pass"},
        )
        self.assertTrue(proof.get("ok"), msg=proof)
        self.assertTrue(bool(proof.get("state_changed")), msg=proof)
        self.assertEqual(proof.get("durability"), "durable")
        changes = {row.get("change") for row in proof.get("state_changes", []) if isinstance(row, dict)}
        self.assertIn("published_proof", changes)
        self.assertIn("proof_added", changes)
        self.assertIn("update_added", changes)

        artifact = env_store.get_artifact("art-proof-r1")
        self.assertIsInstance(artifact, dict)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("status"), "published")
        self.assertEqual(artifact.get("published_to_track"), "track-proof-publish")
        self.assertEqual(artifact.get("template"), "proof")
        self.assertTrue(bool(artifact.get("is_current")), msg=artifact)

        track = env_store.get_track("track-proof-publish")
        self.assertIsInstance(track, dict)
        assert isinstance(track, dict)
        close = [row for row in track.get("close_proof", []) if isinstance(row, dict)]
        self.assertEqual(len(close), 1)
        self.assertEqual(close[0].get("artifact_id"), "art-proof-r1")
        self.assertTrue(bool(close[0].get("current")), msg=close[0])
        updates = [row for row in track.get("updates", []) if isinstance(row, dict)]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].get("kind"), "proof")
        refs = updates[0].get("refs")
        self.assertIsInstance(refs, list)
        assert isinstance(refs, list)
        self.assertEqual(refs[0].get("id"), "art-proof-r1")

    def test_add_proof_replaces_current_proof_only_after_successful_publish(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-proof-main").get("ok"))
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-proof-archived").get("ok"))
        archived = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-proof-archived"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)

        test_instance = self._instance_json(instance_id="inst-test-track", buddy="test")
        r1 = self._create_draft(
            instance_json=test_instance,
            instance_id="inst-test-track",
            buddy="test",
            artifact_id="art-proof-replace-r1",
            template="proof",
            body="r1",
        )
        self.assertTrue(r1.get("ok"), msg=r1)
        pub_r1 = self._dispatch(
            instance_json=test_instance,
            instance_id="inst-test-track",
            buddy="test",
            tool="track",
            action="add_proof",
            args={"track_id": "track-proof-main", "artifact_id": "art-proof-replace-r1", "label": "Smoke", "summary": "r1"},
        )
        self.assertTrue(pub_r1.get("ok"), msg=pub_r1)

        r2 = self._create_draft(
            instance_json=test_instance,
            instance_id="inst-test-track",
            buddy="test",
            artifact_id="art-proof-replace-r2",
            template="proof",
            body="r2",
            supersedes_artifact_id="art-proof-replace-r1",
        )
        self.assertTrue(r2.get("ok"), msg=r2)

        baseline_track = deepcopy(env_store.get_track("track-proof-main"))
        baseline_r1 = deepcopy(env_store.get_artifact("art-proof-replace-r1"))
        baseline_r2 = deepcopy(env_store.get_artifact("art-proof-replace-r2"))

        rejected = self._dispatch(
            instance_json=test_instance,
            instance_id="inst-test-track",
            buddy="test",
            tool="track",
            action="add_proof",
            args={"track_id": "track-proof-archived", "artifact_id": "art-proof-replace-r2", "label": "Smoke", "summary": "r2"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "track.lifecycle_status")
        self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
        self.assertEqual(env_store.get_track("track-proof-main"), baseline_track)
        self.assertEqual(env_store.get_artifact("art-proof-replace-r1"), baseline_r1)
        self.assertEqual(env_store.get_artifact("art-proof-replace-r2"), baseline_r2)

        published = self._dispatch(
            instance_json=test_instance,
            instance_id="inst-test-track",
            buddy="test",
            tool="track",
            action="add_proof",
            args={"track_id": "track-proof-main", "artifact_id": "art-proof-replace-r2", "label": "Smoke", "summary": "r2"},
        )
        self.assertTrue(published.get("ok"), msg=published)
        track = env_store.get_track("track-proof-main")
        self.assertIsInstance(track, dict)
        assert isinstance(track, dict)
        close = [row for row in track.get("close_proof", []) if isinstance(row, dict)]
        self.assertEqual(len(close), 2)
        by_id = {str(row.get("artifact_id")): bool(row.get("current")) for row in close}
        self.assertFalse(by_id["art-proof-replace-r1"])
        self.assertTrue(by_id["art-proof-replace-r2"])

        r1_store = env_store.get_artifact("art-proof-replace-r1")
        r2_store = env_store.get_artifact("art-proof-replace-r2")
        self.assertIsInstance(r1_store, dict)
        self.assertIsInstance(r2_store, dict)
        assert isinstance(r1_store, dict)
        assert isinstance(r2_store, dict)
        self.assertFalse(bool(r1_store.get("is_current")), msg=r1_store)
        self.assertTrue(bool(r2_store.get("is_current")), msg=r2_store)

    def test_archive_boundaries(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(instance_json=pm_instance, track_id="track-archive").get("ok"))

        design_instance = self._instance_json(instance_id="inst-design-track", buddy="design")
        denied = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="archive",
            args={"track_id": "track-archive"},
        )
        self.assertFalse(denied.get("ok"), msg=denied)
        self.assertEqual((denied.get("error") or {}).get("code"), "E_TRACK_AUTHORITY")

        archived = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-archive"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)

        draft = self._create_draft(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            artifact_id="art-archive-r1",
            template="brief",
            body="x",
        )
        self.assertTrue(draft.get("ok"), msg=draft)

        for action, args in (
            ("open", {"track_id": "track-archive"}),
            ("update_now", {"track_id": "track-archive", "state": "done"}),
            ("add_update", {"track_id": "track-archive", "kind": "progress", "summary": "x"}),
            ("add_material", {"track_id": "track-archive", "artifact_id": "art-archive-r1", "label": "Brief", "summary": "x"}),
            ("add_proof", {"track_id": "track-archive", "artifact_id": "art-archive-r1", "label": "Smoke", "summary": "x"}),
        ):
            rejected = self._dispatch(
                instance_json=design_instance,
                instance_id="inst-design-track",
                buddy="design",
                tool="track",
                action=action,
                args=args,
            )
            with self.subTest(action=action):
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_ARCHIVED")
                self.assertEqual(rejected.get("permission_boundary"), "track.lifecycle_status")
                self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)


if __name__ == "__main__":
    unittest.main()
