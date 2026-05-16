#!/usr/bin/env python3
"""Runless track env.tool integration tests."""

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

    def _seed_pm_track_with_current_artifact(
        self,
        *,
        track_id: str,
        current_buddy: str = "pm",
        next_buddy: str | None = None,
    ) -> str:
        env_store.create_track(
            track_id,
            "Source Intake Track",
            current_buddy=current_buddy,
            next_buddy=next_buddy,
            summary="track with PM source",
        )
        env_store.create_task(
            f"task-pm-{track_id}",
            "PM Source Task",
            buddy="pm",
            track_id=track_id,
            summary="PM produced source material",
        )
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

    def test_track_get_returns_artifact_summaries_for_track_with_pm_artifact(self) -> None:
        instance_json = self._instance_json(instance_id="inst-design-track-artifacts", buddy="design")
        artifact_id = self._seed_pm_track_with_current_artifact(
            track_id="track-get-artifact-summary",
            current_buddy="pm",
            next_buddy="design",
        )

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track-artifacts",
            buddy="design",
            tool="track",
            action="get",
            args={"track_id": "track-get-artifact-summary"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        summary = response.get("track_context_summary")
        self.assertIsInstance(summary, dict, msg=response)
        assert isinstance(summary, dict)
        artifacts = summary.get("artifacts")
        self.assertIsInstance(artifacts, list, msg=response)
        assert isinstance(artifacts, list)
        self.assertEqual(len(artifacts), 1, msg=response)
        row = artifacts[0]
        self.assertEqual(row.get("artifact_id"), artifact_id)
        self.assertEqual(row.get("id"), artifact_id)
        self.assertEqual(row.get("track_id"), "track-get-artifact-summary")
        self.assertEqual(row.get("kind"), "prd")
        self.assertEqual(row.get("title"), "PM PRD")
        self.assertEqual(row.get("summary"), "PM PRD summary")
        self.assertEqual(row.get("source_buddy"), "pm")
        self.assertEqual(row.get("source_task_id"), "task-pm-track-get-artifact-summary")
        self.assertEqual(row.get("currentness"), "current")
        self.assertEqual(row.get("relation"), "next_buddy")
        self.assertTrue(row.get("readable_by_current_buddy"), msg=row)
        self.assertNotIn("content", row)
        self.assertNotIn("Full PM PRD body", json.dumps(response, ensure_ascii=False))

    def test_track_get_marks_unrelated_foreign_artifact_unreadable_without_content(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-track-artifacts", buddy="dev")
        artifact_id = self._seed_pm_track_with_current_artifact(
            track_id="track-get-unreadable-artifact-summary",
            current_buddy="pm",
            next_buddy="design",
        )

        response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-track-artifacts",
            buddy="dev",
            tool="track",
            action="get",
            args={"track_id": "track-get-unreadable-artifact-summary"},
        )

        self.assertTrue(response.get("ok"), msg=response)
        summary = response.get("track_context_summary")
        self.assertIsInstance(summary, dict, msg=response)
        assert isinstance(summary, dict)
        artifacts = summary.get("artifacts")
        self.assertIsInstance(artifacts, list, msg=response)
        assert isinstance(artifacts, list)
        self.assertEqual(len(artifacts), 1, msg=response)
        row = artifacts[0]
        self.assertEqual(row.get("artifact_id"), artifact_id)
        self.assertEqual(row.get("relation"), "observer")
        self.assertFalse(row.get("readable_by_current_buddy"), msg=row)
        self.assertNotIn("content", row)
        self.assertNotIn("Full PM PRD body", json.dumps(response, ensure_ascii=False))

    def test_track_get_artifact_rows_match_artifact_list_for_same_track(self) -> None:
        instance_json = self._instance_json(instance_id="inst-design-track-artifact-list", buddy="design")
        artifact_id = self._seed_pm_track_with_current_artifact(
            track_id="track-get-list-consistency",
            current_buddy="pm",
            next_buddy="design",
        )

        track_response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track-artifact-list",
            buddy="design",
            tool="track",
            action="get",
            args={"track_id": "track-get-list-consistency"},
        )
        list_response = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-design-track-artifact-list",
            buddy="design",
            tool="artifact",
            action="list",
            args={"track_id": "track-get-list-consistency"},
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

        self.assertEqual(
            [
                {
                    "artifact_id": row.get("artifact_id"),
                    "source_buddy": row.get("source_buddy"),
                    "source_task_id": row.get("source_task_id"),
                    "currentness": row.get("currentness"),
                    "readable_by_current_buddy": row.get("readable_by_current_buddy"),
                }
                for row in track_rows
            ],
            [
                {
                    "artifact_id": row.get("artifact_id"),
                    "source_buddy": row.get("source_buddy"),
                    "source_task_id": row.get("source_task_id"),
                    "currentness": row.get("currentness"),
                    "readable_by_current_buddy": row.get("readable_by_current_buddy"),
                }
                for row in list_rows
            ],
        )
        self.assertEqual(track_rows[0].get("artifact_id"), artifact_id)

    def test_pm_track_lifecycle_mutations(self) -> None:
        instance_json = self._instance_json(instance_id="inst-pm-track", buddy="pm")

        created = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="create",
            args={
                "track_id": "track-runless-pm",
                "title": "Runless Track",
                "current_buddy": "pm",
                "next_buddy": "design",
                "summary": "seed",
            },
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertEqual((created.get("track") or {}).get("id"), "track-runless-pm")

        advanced = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="advance",
            args={"track_id": "track-runless-pm", "current_buddy": "design", "next_buddy": "dev", "status": "active"},
        )
        self.assertTrue(advanced.get("ok"), msg=advanced)
        self.assertEqual((advanced.get("track") or {}).get("current_buddy"), "design")

        archived = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="archive",
            args={"track_id": "track-runless-pm"},
        )
        self.assertTrue(archived.get("ok"), msg=archived)
        self.assertEqual((archived.get("track") or {}).get("status"), "archived")

    def test_non_pm_cannot_create_track(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-track", buddy="dev")
        rejected = self._dispatch(
            instance_json=instance_json,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="create",
            args={"track_id": "track-nope", "title": "Nope"},
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual((rejected.get("error") or {}).get("code"), "E_TRACK_AUTHORITY")

    def test_join_track_creates_or_reuses_active_buddy_task_without_binding_mutation(self) -> None:
        pm_instance = self._instance_json(instance_id="inst-pm-track", buddy="pm")
        self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-join-runless", "title": "Join Flow", "current_buddy": "pm"},
        )

        dev_instance = self._instance_json(instance_id="inst-dev-track", buddy="dev")
        joined = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="join",
            args={"track_id": "track-join-runless", "title": "Dev Join Task", "summary": "join"},
        )
        self.assertTrue(joined.get("ok"), msg=joined)
        self.assertNotIn("binding_changed", joined)
        task_id = (joined.get("task") or {}).get("id")
        self.assertIsInstance(task_id, str, msg=joined)
        assert isinstance(task_id, str)
        stored_task = env_store.get_task(task_id)
        self.assertIsInstance(stored_task, dict)
        assert isinstance(stored_task, dict)
        self.assertEqual(stored_task.get("track_id"), "track-join-runless")

    def test_attach_and_detach_task(self) -> None:
        pm_instance = self._instance_json(instance_id="inst-pm-track", buddy="pm")
        self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track",
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-attach-runless", "title": "Attach Flow", "current_buddy": "pm"},
        )

        env_store.create_task("task-dev-detach", "Detach Task", buddy="dev", summary="seed")
        dev_instance = self._instance_json(instance_id="inst-dev-track", buddy="dev")

        attached = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="attach_task",
            args={"track_id": "track-attach-runless", "task_id": "task-dev-detach"},
        )
        self.assertTrue(attached.get("ok"), msg=attached)
        self.assertEqual((attached.get("task") or {}).get("track_id"), "track-attach-runless")

        detached = self._dispatch(
            instance_json=dev_instance,
            instance_id="inst-dev-track",
            buddy="dev",
            tool="track",
            action="detach_task",
            args={"track_id": "track-attach-runless", "task_id": "task-dev-detach"},
        )
        self.assertTrue(detached.get("ok"), msg=detached)
        self.assertIsNone((detached.get("task") or {}).get("track_id"))

    def test_join_attach_detach_reject_foreign_task_with_scope_feedback(self) -> None:
        pm_instance = self._instance_json(instance_id="inst-pm-track-foreign", buddy="pm")
        self._dispatch(
            instance_json=pm_instance,
            instance_id="inst-pm-track-foreign",
            buddy="pm",
            tool="track",
            action="create",
            args={"track_id": "track-foreign-task-scope", "title": "Scope Flow", "current_buddy": "pm"},
        )
        env_store.create_task("task-pm-foreign-scope", "PM owned task", buddy="pm", track_id=None, summary="pm only")

        dev_instance = self._instance_json(instance_id="inst-dev-track-foreign", buddy="dev")
        for action in ("join", "attach_task", "detach_task"):
            args = {"track_id": "track-foreign-task-scope", "task_id": "task-pm-foreign-scope"}
            rejected = self._dispatch(
                instance_json=dev_instance,
                instance_id="inst-dev-track-foreign",
                buddy="dev",
                tool="track",
                action=action,
                args=args,
            )
            with self.subTest(action=action):
                self.assertFalse(rejected.get("ok"), msg=rejected)
                self.assertEqual(rejected.get("permission_boundary"), "task.buddy_scope", msg=rejected)
                self.assertFalse(rejected.get("state_changed"), msg=rejected)
                self.assertIn("ownership", str(rejected.get("retry_guidance", "")).lower(), msg=rejected)
                self.assertIn("task_id", rejected.get("correctable_fields", []), msg=rejected)
                alternatives = rejected.get("alternative_capabilities")
                self.assertIsInstance(alternatives, list, msg=rejected)
                assert isinstance(alternatives, list)
                alt_pairs = {
                    (row.get("tool"), row.get("action"))
                    for row in alternatives
                    if isinstance(row, dict)
                }
                self.assertIn(("task", "list"), alt_pairs)
                self.assertIn(("track", "get"), alt_pairs)
                self.assertIn(("track", "join"), alt_pairs)


if __name__ == "__main__":
    unittest.main()
