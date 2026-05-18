#!/usr/bin/env python3
"""Track env.tool integration tests for artifact-id publication path."""

from __future__ import annotations

import json
import sys
import unittest
import uuid
from copy import deepcopy
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
ALL_BUDDIES = ("pm", "design", "dev", "market", "test")


class TrackEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(self, *, instance_id: str, buddy: str, status: str = "active") -> Path:
        path = self._runtime_path(f"instance-{instance_id}.json")
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
