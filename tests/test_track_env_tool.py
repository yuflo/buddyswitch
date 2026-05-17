#!/usr/bin/env python3
"""Track env.tool integration tests for track-page collaboration model."""

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
                    "updated_at": "2026-05-17T00:00:00Z",
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

    def _create_track(self, instance_json: Path, track_id: str = "track-main") -> dict[str, object]:
        return self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": track_id,
                "title": "Landing first proof",
                "outcome": "Validate landing message clarity",
                "appetite": "2 days",
                "now": {"next": "Design drafts first screen", "blocker": None},
            },
        )

    def test_pm_creates_human_readable_track_page(self) -> None:
        instance_json = self._pm_instance()
        created = self._create_track(instance_json, "track-human-page")
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
        for forbidden in ("task_ids", "status", "summary"):
            self.assertNotIn(forbidden, track)

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
        self.assertTrue(self._create_track(pm_instance, "track-shared-open").get("ok"))

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
                rows = listed.get("tracks")
                self.assertIsInstance(rows, list)
                assert isinstance(rows, list)
                self.assertIn("track-shared-open", {row.get("id") for row in rows if isinstance(row, dict)})

    def test_track_open_returns_page_without_tasks_or_artifact_bodies(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-safe-open").get("ok"))
        mat = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-safe-open",
                "kind": "prd",
                "label": "PRD",
                "title": "PM PRD",
                "summary": "PRD summary",
                "content": {"body": "SECRET-BODY-SHOULD-NOT-LEAK"},
            },
        )
        self.assertTrue(mat.get("ok"), msg=mat)

        dev_instance = self._instance_json(instance_id="inst-dev-track", buddy="dev")
        opened = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="open",
            args={"track_id": "track-safe-open"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened.get("track")
        self.assertIsInstance(track, dict)
        assert isinstance(track, dict)
        self.assertIn("shared_materials", track)
        self.assertIn("updates", track)
        self.assertIn("close_proof", track)
        encoded = json.dumps(track, ensure_ascii=True)
        for forbidden in ("tasks", "task_ids", "source_" + "task_id", "artifact" + "_slots", "SECRET-BODY-SHOULD-NOT-LEAK"):
            self.assertNotIn(forbidden, encoded)

    def test_all_buddies_can_update_now_state_on_non_archived_track(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-update-now").get("ok"))

        design_instance = self._instance_json(instance_id="inst-design-track", buddy="design")
        updated = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="update_now",
            args={
                "track_id": "track-update-now",
                "now": {"next": "Need positioning decision", "blocker": "One-liner not settled"},
                "state": "blocked",
                "health": "blocked",
            },
        )
        self.assertTrue(updated.get("ok"), msg=updated)

        opened = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="open",
            args={"track_id": "track-update-now"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        track = opened["track"]
        self.assertEqual(track["state"], "blocked")
        self.assertEqual(track["health"], "blocked")
        self.assertEqual(track["now"]["blocker"], "One-liner not settled")
        self.assertGreaterEqual(len(track["updates"]), 1)

    def test_add_material_creates_artifact_and_track_ref(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-material-create").get("ok"))

        material = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-material-create",
                "kind": "prd",
                "label": "PRD",
                "title": "Landing PRD",
                "summary": "scope",
                "content": {"body": "prd"},
            },
        )
        self.assertTrue(material.get("ok"), msg=material)
        self.assertIsInstance(material.get("artifact_id"), str)

        opened = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-material-create"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        refs = opened["track"]["shared_materials"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["kind"], "prd")
        self.assertEqual(refs[0]["label"], "PRD")

    def test_design_publishes_material_without_task_relation(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(pm_instance, "track-cross-publish").get("ok"))
        self.assertTrue(
            self._dispatch(
                instance_json=pm_instance,
                instance_id="inst-pm-track",
                buddy="pm",
                tool="track",
                action="add_material",
                args={
                    "track_id": "track-cross-publish",
                    "kind": "prd",
                    "label": "PRD",
                    "title": "PM PRD",
                    "summary": "summary",
                    "content": {"body": "prd"},
                },
            ).get("ok")
        )

        design_instance = self._instance_json(instance_id="inst-design-track", buddy="design")
        created = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-cross-publish",
                "kind": "design-handoff",
                "label": "Draft",
                "title": "Design Draft",
                "summary": "draft",
                "content": {"body": "design"},
            },
        )
        self.assertTrue(created.get("ok"), msg=created)

        dev_instance = self._instance_json(instance_id="inst-dev-track", buddy="dev")
        opened = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="open",
            args={"track_id": "track-cross-publish"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        refs = opened["track"]["shared_materials"]
        self.assertEqual(len(refs), 2)

    def test_new_material_supersedes_default_current_ref(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-supersede").get("ok"))
        first = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-supersede",
                "kind": "prd",
                "label": "PRD",
                "title": "PRD R1",
                "summary": "r1",
                "content": {"body": "r1"},
            },
        )
        second = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-supersede",
                "kind": "prd",
                "label": "PRD",
                "title": "PRD R2",
                "summary": "r2",
                "content": {"body": "r2"},
            },
        )
        self.assertTrue(first.get("ok"), msg=first)
        self.assertTrue(second.get("ok"), msg=second)

        opened = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-supersede"},
        )
        refs = opened["track"]["shared_materials"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["artifact_id"], second["artifact_id"])

    def test_add_material_rejects_cross_track_republish_without_state_pollution(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-material-a").get("ok"))
        self.assertTrue(self._create_track(instance_json, "track-material-b").get("ok"))

        draft = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-cross-track-material-r1",
                "kind": "prd",
                "title": "Cross track material",
                "summary": "draft",
                "content": {"body": "draft"},
            },
        )
        self.assertTrue(draft.get("ok"), msg=draft)
        artifact_id = draft["artifact_id"]

        first_publish = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-a", "artifact_id": artifact_id, "label": "PRD", "summary": "published-a"},
        )
        self.assertTrue(first_publish.get("ok"), msg=first_publish)

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={"track_id": "track-material-b", "artifact_id": artifact_id, "label": "PRD", "summary": "published-b"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")

        track_b = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-material-b"},
        )
        self.assertTrue(track_b.get("ok"), msg=track_b)
        self.assertEqual(track_b["track"]["shared_materials"], [])

        owner_view = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": artifact_id},
        )
        self.assertTrue(owner_view.get("ok"), msg=owner_view)
        artifact = owner_view.get("artifact")
        self.assertIsInstance(artifact, dict)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("published_to_track"), "track-material-a")
        self.assertEqual(artifact.get("publication_role"), "material")

    def test_add_proof_rejects_cross_track_republish_without_state_pollution(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-proof-a").get("ok"))
        self.assertTrue(self._create_track(instance_json, "track-proof-b").get("ok"))

        draft = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-cross-track-proof-r1",
                "kind": "smoke-test",
                "title": "Cross track proof",
                "summary": "draft",
                "content": {"result": "pass"},
            },
        )
        self.assertTrue(draft.get("ok"), msg=draft)
        artifact_id = draft["artifact_id"]

        first_publish = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_proof",
            args={"track_id": "track-proof-a", "artifact_id": artifact_id, "label": "Smoke", "summary": "published-a"},
        )
        self.assertTrue(first_publish.get("ok"), msg=first_publish)

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_proof",
            args={"track_id": "track-proof-b", "artifact_id": artifact_id, "label": "Smoke", "summary": "published-b"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")

        track_b = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-proof-b"},
        )
        self.assertTrue(track_b.get("ok"), msg=track_b)
        self.assertEqual(track_b["track"]["close_proof"], [])

        owner_view = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="artifact",
            action="get",
            args={"artifact_id": artifact_id},
        )
        self.assertTrue(owner_view.get("ok"), msg=owner_view)
        artifact = owner_view.get("artifact")
        self.assertIsInstance(artifact, dict)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("published_to_track"), "track-proof-a")
        self.assertEqual(artifact.get("publication_role"), "proof")

    def test_add_update_and_add_proof(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(pm_instance, "track-updates").get("ok"))
        material = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-updates",
                "kind": "prd",
                "label": "PRD",
                "title": "PRD",
                "summary": "summary",
                "content": {"body": "prd"},
            },
        )
        self.assertTrue(material.get("ok"), msg=material)

        design_instance = self._instance_json(instance_id="inst-design-track", buddy="design")
        update = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="add_update",
            args={
                "track_id": "track-updates",
                "kind": "blocker",
                "summary": "blocked by copy",
                "refs": [{"type": "artifact", "id": material["artifact_id"]}],
            },
        )
        self.assertTrue(update.get("ok"), msg=update)

        test_instance = self._instance_json(instance_id="inst-test-track", buddy="test")
        proof = self._dispatch(
            instance_json=test_instance,
            instance_id="inst-test-track",
            buddy="test",
            tool="track",
            action="add_proof",
            args={
                "track_id": "track-updates",
                "kind": "smoke-test",
                "label": "Smoke",
                "title": "Smoke proof",
                "summary": "pass",
                "content": {"result": "pass"},
            },
        )
        self.assertTrue(proof.get("ok"), msg=proof)

        opened = self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-updates"},
        )
        track = opened["track"]
        self.assertEqual(len(track["close_proof"]), 1)
        self.assertEqual(track["close_proof"][0]["artifact_id"], proof["artifact_id"])
        self.assertIn("proof", {row.get("kind") for row in track["updates"] if isinstance(row, dict)})

    def test_update_now_rejects_invalid_state_and_health_without_mutation(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-invalid-now").get("ok"))
        before = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-invalid-now"},
        )
        self.assertTrue(before.get("ok"), msg=before)
        before_track = before["track"]

        bad_state = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="update_now",
            args={"track_id": "track-invalid-now", "state": "waiting"},
        )
        self.assertFalse(bad_state.get("ok"), msg=bad_state)
        self.assertEqual((bad_state.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")

        bad_health = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="update_now",
            args={"track_id": "track-invalid-now", "health": "yellow"},
        )
        self.assertFalse(bad_health.get("ok"), msg=bad_health)
        self.assertEqual((bad_health.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")

        after = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-invalid-now"},
        )
        self.assertTrue(after.get("ok"), msg=after)
        self.assertEqual(before_track, after["track"])

    def test_track_payload_rejects_owner_buddy_patch(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-owner-immutable").get("ok"))

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="update_now",
            args={
                "track_id": "track-owner-immutable",
                "owner_buddy": "design",
                "now": {"next": "x", "blocker": None},
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")

        opened = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-owner-immutable"},
        )
        self.assertTrue(opened.get("ok"), msg=opened)
        self.assertEqual(opened["track"]["owner_buddy"], "pm")

    def test_add_update_rejects_invalid_kind(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-invalid-update-kind").get("ok"))
        before = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-invalid-update-kind"},
        )
        self.assertTrue(before.get("ok"), msg=before)

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_update",
            args={"track_id": "track-invalid-update-kind", "kind": "comment", "summary": "bad kind"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")

        after = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-invalid-update-kind"},
        )
        self.assertTrue(after.get("ok"), msg=after)
        self.assertEqual(before["track"]["updates"], after["track"]["updates"])

    def test_add_update_rejects_missing_artifact_ref_without_mutation(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-invalid-update-ref").get("ok"))
        before = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-invalid-update-ref"},
        )
        self.assertTrue(before.get("ok"), msg=before)

        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_update",
            args={
                "track_id": "track-invalid-update-ref",
                "kind": "blocker",
                "summary": "broken ref",
                "refs": [{"type": "artifact", "id": "art-missing"}],
            },
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_UPDATE_REFS")
        self.assertEqual(rejected.get("permission_boundary"), "track.update_refs")

        after = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-invalid-update-ref"},
        )
        self.assertTrue(after.get("ok"), msg=after)
        self.assertEqual(before["track"]["updates"], after["track"]["updates"])

    def test_add_update_refs_enforce_track_readability_and_membership_boundaries(self) -> None:
        instance_json = self._pm_instance()
        self.assertTrue(self._create_track(instance_json, "track-update-main").get("ok"))
        self.assertTrue(self._create_track(instance_json, "track-update-other").get("ok"))
        self.assertTrue(self._create_track(instance_json, "track-update-archived").get("ok"))

        private_draft = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="artifact",
            action="create_revision",
            args={
                "artifact_id": "art-private-draft-r1",
                "kind": "prd",
                "title": "Private draft",
                "summary": "private",
                "content": {"body": "private"},
            },
        )
        self.assertTrue(private_draft.get("ok"), msg=private_draft)

        main_r1 = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-update-main",
                "kind": "prd",
                "label": "PRD",
                "title": "Main R1",
                "summary": "r1",
                "content": {"body": "r1"},
            },
        )
        self.assertTrue(main_r1.get("ok"), msg=main_r1)
        main_r2 = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-update-main",
                "kind": "prd",
                "label": "PRD",
                "title": "Main R2",
                "summary": "r2",
                "content": {"body": "r2"},
            },
        )
        self.assertTrue(main_r2.get("ok"), msg=main_r2)

        cross_track = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-update-other",
                "kind": "design-handoff",
                "label": "Draft",
                "title": "Other track draft",
                "summary": "other",
                "content": {"body": "other"},
            },
        )
        self.assertTrue(cross_track.get("ok"), msg=cross_track)

        archived_artifact = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="add_material",
            args={
                "track_id": "track-update-archived",
                "kind": "implementation-report",
                "label": "Impl",
                "title": "Archived material",
                "summary": "archived",
                "content": {"body": "archived"},
            },
        )
        self.assertTrue(archived_artifact.get("ok"), msg=archived_artifact)
        archived = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-update-archived"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)

        before = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="open",
            args={"track_id": "track-update-main"},
        )
        self.assertTrue(before.get("ok"), msg=before)
        baseline_updates = before["track"]["updates"]

        for label, artifact_id in (
            ("private-draft", private_draft["artifact_id"]),
            ("cross-track-current", cross_track["artifact_id"]),
            ("superseded-material", main_r1["artifact_id"]),
            ("archived-track-material", archived_artifact["artifact_id"]),
        ):
            rejected = self._dispatch(
                instance_json=instance_json,
                instance_id="inst-pm-track",
                buddy="pm",
                tool="track",
                action="add_update",
                args={
                    "track_id": "track-update-main",
                    "kind": "blocker",
                    "summary": f"reject {label}",
                    "refs": [{"type": "artifact", "id": artifact_id}],
                },
            )
            with self.subTest(case=label):
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_UPDATE_REFS")
                self.assertEqual(rejected.get("permission_boundary"), "track.update_refs")
                after = self._dispatch(
                    instance_json=instance_json,
                    instance_id="inst-pm-track",
                    buddy="pm",
                    tool="track",
                    action="open",
                    args={"track_id": "track-update-main"},
                )
                self.assertTrue(after.get("ok"), msg=after)
                self.assertEqual(after["track"]["updates"], baseline_updates)

    def test_archive_boundaries(self) -> None:
        pm_instance = self._pm_instance()
        self.assertTrue(self._create_track(pm_instance, "track-archive").get("ok"))

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

        list_dev = self._dispatch(
            instance_json=design_instance,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="list",
            args={},
        )
        self.assertTrue(list_dev.get("ok"), msg=list_dev)
        ids = {row.get("id") for row in list_dev["tracks"] if isinstance(row, dict)}
        self.assertNotIn("track-archive", ids)

        for action, args in (
            ("open", {"track_id": "track-archive"}),
            ("update_now", {"track_id": "track-archive", "state": "done"}),
            ("add_update", {"track_id": "track-archive", "kind": "progress", "summary": "x"}),
            ("add_material", {"track_id": "track-archive", "kind": "prd", "label": "PRD", "title": "x", "summary": "x", "content": {}}),
            ("add_proof", {"track_id": "track-archive", "kind": "smoke-test", "label": "Smoke", "title": "x", "summary": "x", "content": {}}),
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


if __name__ == "__main__":
    unittest.main()
