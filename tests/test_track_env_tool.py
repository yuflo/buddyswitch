#!/usr/bin/env python3
"""Track env.tool integration tests."""

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


class TrackEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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

    def _seed_pm_track_with_current_artifact(self, *, track_id: str) -> str:
        env_store.create_track(track_id, "Source Intake Track", owner_buddy="pm", summary="track with PM source")
        env_store.create_task(f"task-pm-{track_id}", "PM Source Task", buddy="pm", track_id=track_id, summary="PM produced source material")
        artifact = env_store.create_artifact(
            artifact_id=f"art-pm-{track_id}",
            title="PM PRD",
            buddy="pm",
            kind="prd",
            task_id=f"task-pm-{track_id}",
            summary="PM PRD summary",
            content={"body": "Full PM PRD body must not appear in track.get."},
            created_by="pm",
            source_refs=[{"type": "note", "label": "seed"}],
        )
        return str(artifact["id"])

    def test_track_create_records_owner_buddy_without_next_buddy(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-track", buddy="pm")
        created = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-owner", "title": "Owner Track"},
        )
        self.assertTrue(created.get("ok"), msg=created)
        track = created.get("track")
        self.assertIsInstance(track, dict, msg=created)
        assert isinstance(track, dict)
        self.assertEqual(track.get("owner_buddy"), "pm")
        self.assertNotIn("current_buddy", track)
        self.assertNotIn("next_buddy", track)

        stored = env_store.get_track("track-owner")
        self.assertIsInstance(stored, dict)
        assert isinstance(stored, dict)
        self.assertEqual(stored.get("owner_buddy"), "pm")

    def test_track_payload_rejects_current_and_next_buddy(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-track", buddy="pm")
        for args in (
            {"track_id": "track-bad-1", "title": "Bad", "current_buddy": "pm"},
            {"track_id": "track-bad-2", "title": "Bad", "next_buddy": "dev"},
        ):
            payload = self._dispatch(
                instance_json=instance_json,
                instance_id="inst-pm-track",
                buddy="pm",
                tool="track",
                action="create",
                args=args,
            )
            with self.subTest(args=args):
                self.assertFalse(payload.get("ok"), msg=payload)
                self.assertEqual((payload.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")

    def test_track_update_rejects_owner_buddy_patch(self) -> None:
        env_store.create_track("track-owner-patch", "Patch", owner_buddy="pm")
        instance_json = self._instance_json(instance_id="inst-pm-track", buddy="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="update",
            args={"track_id": "track-owner-patch", "owner_buddy": "design"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_TRACK_PAYLOAD")
        self.assertEqual(env_store.get_track("track-owner-patch").get("owner_buddy"), "pm")

    def test_track_advance_action_is_unsupported(self) -> None:
        env_store.create_track("track-no-advance", "No Advance", owner_buddy="pm")
        instance_json = self._instance_json(instance_id="inst-pm-track", buddy="pm")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="advance",
            args={"track_id": "track-no-advance"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_ENV_TOOL")

    def test_track_get_rejects_archived_track(self) -> None:
        env_store.create_track("track-archived", "Archived", owner_buddy="pm", status="archived")
        instance_json = self._instance_json(instance_id="inst-dev-track", buddy="dev")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="get",
            args={"track_id": "track-archived"},
        )
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual((payload.get("error") or {}).get("code"), "E_TRACK_ARCHIVED")
        self.assertEqual(payload.get("permission_boundary"), "track.lifecycle_status")

    def test_track_list_default_omits_archived_tracks(self) -> None:
        env_store.create_track("track-active", "Active", owner_buddy="pm", status="active")
        env_store.create_track("track-archived", "Archived", owner_buddy="pm", status="archived")
        instance_json = self._instance_json(instance_id="inst-dev-track", buddy="dev")
        payload = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="list",
            args={},
        )
        self.assertTrue(payload.get("ok"), msg=payload)
        rows = payload.get("tracks")
        self.assertIsInstance(rows, list, msg=payload)
        assert isinstance(rows, list)
        ids = {row.get("id") for row in rows if isinstance(row, dict)}
        self.assertIn("track-active", ids)
        self.assertNotIn("track-archived", ids)

    def test_track_get_artifact_rows_match_artifact_list_current_rows(self) -> None:
        instance_json = self._instance_json(instance_id="inst-design-track", buddy="design")
        artifact_id = self._seed_pm_track_with_current_artifact(track_id="track-consistency")

        join = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="join",
            args={"track_id": "track-consistency", "title": "Design Join Task"},
        )
        self.assertTrue(join.get("ok"), msg=join)

        track_response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track",
            buddy="design",
            tool="track",
            action="get",
            args={"track_id": "track-consistency"},
        )
        list_response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track",
            buddy="design",
            tool="artifact",
            action="list",
            args={"track_id": "track-consistency"},
        )

        self.assertTrue(track_response.get("ok"), msg=track_response)
        self.assertTrue(list_response.get("ok"), msg=list_response)
        track_summary = track_response.get("track_context_summary")
        self.assertIsInstance(track_summary, dict, msg=track_response)
        assert isinstance(track_summary, dict)
        track_rows = track_summary.get("artifacts")
        list_rows = list_response.get("artifacts")
        self.assertIsInstance(track_rows, list, msg=track_response)
        self.assertIsInstance(list_rows, list, msg=list_response)
        assert isinstance(track_rows, list)
        assert isinstance(list_rows, list)

        slim_track = [
            {
                "artifact_id": row.get("artifact_id"),
                "source_buddy": row.get("source_buddy"),
                "source_task_id": row.get("source_task_id"),
                "kind": row.get("kind"),
                "revision": row.get("revision"),
                "currentness": row.get("currentness"),
                "readable_by_active_buddy": row.get("readable_by_active_buddy"),
                "relation": row.get("relation"),
            }
            for row in track_rows
            if isinstance(row, dict)
        ]
        slim_list = [
            {
                "artifact_id": row.get("artifact_id"),
                "source_buddy": row.get("source_buddy"),
                "source_task_id": row.get("source_task_id"),
                "kind": row.get("kind"),
                "revision": row.get("revision"),
                "currentness": row.get("currentness"),
                "readable_by_active_buddy": row.get("readable_by_active_buddy"),
                "relation": row.get("relation"),
            }
            for row in list_rows
            if isinstance(row, dict)
        ]
        self.assertEqual(slim_track, slim_list)
        self.assertEqual(slim_track[0].get("artifact_id"), artifact_id)


if __name__ == "__main__":
    unittest.main()
