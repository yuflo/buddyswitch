#!/usr/bin/env python3
"""Functional coverage for broker-routed env.tool artifact env tool operations."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
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
ENV_CLIENT = ROOT / "scripts" / "env" / "client.py"


class ArtifactManagerEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
        status: str = "active",
        current_task_id: str | None = None,
        current_track_id: str | None = None,
    ) -> Path:
        instance_json = self._runtime_path("instance.json")
        instance_json.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "current_task_id": current_task_id,
                    "current_track_id": current_track_id,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": None,
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _dispatch_request(
        self,
        *,
        method: str,
        payload: dict[str, object],
        instance_json: Path,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "request_id": f"req-artifact-env-{uuid.uuid4().hex}",
            "method": method,
            "params": {
                "instance_id": instance_id,
                "active_buddy": buddy,
                **payload,
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
        error = envelope.get("error")
        self.assertIsInstance(error, dict, msg=envelope)
        assert isinstance(error, dict)
        response: dict[str, object] = {
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
            response[key] = value
        return response

    def _dispatch_tool(
        self,
        *,
        tool: str,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
    ) -> dict[str, object]:
        return self._dispatch_request(
            method="env.tool",
            payload={"tool": tool, "action": action, "args": args},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )

    def _dispatch(
        self,
        *,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
    ) -> dict[str, object]:
        return self._dispatch_tool(
            tool="artifact",
            action=action,
            args=args,
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )

    def _prepare(
        self,
        *,
        text: str,
        instance_json: Path,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
    ) -> dict[str, object]:
        response = self._dispatch_request(
            method="prepare",
            payload={"text": text},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy=buddy,
        )
        self.assertTrue(response.get("ok"), msg=response)
        prepared = response.get("payload") if isinstance(response.get("payload"), dict) else response
        self.assertIsInstance(prepared, dict, msg=response)
        assert isinstance(prepared, dict)
        return prepared

    def _seed_task(
        self,
        *,
        task_id: str,
        buddy: str,
        title: str,
        track_id: str | None = None,
        initial_run_id: str | None = None,
    ) -> None:
        env_store.create_task(
            task_id,
            title,
            buddy=buddy,
            track_id=track_id,
            status="active",
            summary="",
            initial_run_id=initial_run_id,
        )

    def _seed_artifact(
        self,
        *,
        artifact_id: str,
        task_id: str,
        buddy: str,
        kind: str,
        title: str,
        source_run_id: str,
        content: dict[str, object] | None = None,
        summary: str = "",
    ) -> dict[str, object]:
        return env_store.create_artifact(
            artifact_id=artifact_id,
            title=title,
            buddy=buddy,
            kind=kind,
            task_id=task_id,
            source_run_id=source_run_id,
            summary=summary,
            content=content or {"body": title},
        )

    def _seed_run_reservation(
        self,
        *,
        run_id: str,
        task_id: str,
        buddy: str = "dev",
        instance_id: str = "inst-dev-example",
    ) -> None:
        path = self._runtime_path(f"buddyswitch/content/runs/reserved/{run_id}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": "reserved",
                    "context_revision": f"ctx-{task_id}-1",
                    "sequence": 1,
                    "task_id": task_id,
                    "instance_id": instance_id,
                    "turn_identity": {
                        "instance_id": instance_id,
                        "active_buddy": buddy,
                        "task_id": task_id,
                        "track_id": None,
                        "context_revision": f"ctx-{task_id}-1",
                        "sequence": 1,
                        "run_id": run_id,
                    },
                    "reserved_at": "2026-05-11T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_handoff_run(
        self,
        *,
        run_id: str,
        task_id: str,
        track_id: str,
        buddy_id: str,
        next_buddy: str,
    ) -> None:
        run_path = self._runtime_path(f"buddyswitch/content/runs/{run_id}.json")
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "track_id": track_id,
                    "buddy_id": buddy_id,
                    "timestamp": "2026-05-14T00:00:00Z",
                    "handoff": {
                        "next_buddy": next_buddy,
                        "reason": "handoff",
                        "context": "continue",
                    },
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _seed_track_with_pm_and_design_current_artifacts(self) -> tuple[str, str, str, str]:
        track_id = "track-artifact-source-intake"
        pm_task_id = "task-pm-source-intake"
        design_task_id = "task-design-source-intake"
        self._seed_task(task_id=pm_task_id, buddy="pm", title="PM Source Intake Task")
        self._seed_task(task_id=design_task_id, buddy="design", title="Design Source Intake Task")
        self._seed_task(task_id="task-pm-unrelated", buddy="pm", title="PM Unrelated Task")
        env_store.create_track(
            track_id,
            "Artifact Source Intake",
            status="active",
            current_buddy="pm",
            next_buddy="dev",
            summary="Cross-buddy source intake baseline",
        )
        env_store.register_task_to_track(track_id, pm_task_id)
        env_store.register_task_to_track(track_id, design_task_id)
        pm_artifact = self._seed_artifact(
            artifact_id="art-pm-source-intake-prd-r1",
            task_id=pm_task_id,
            buddy="pm",
            kind="prd",
            title="PM PRD",
            source_run_id="run-pm-source-intake-r1",
            content={"pm_secret": "pm full body"},
            summary="PM source summary",
        )
        design_artifact = self._seed_artifact(
            artifact_id="art-design-source-intake-handoff-r1",
            task_id=design_task_id,
            buddy="design",
            kind="design-handoff",
            title="Design Handoff",
            source_run_id="run-design-source-intake-r1",
            content={"design_secret": "design full body"},
            summary="Design source summary",
        )
        unrelated_artifact = self._seed_artifact(
            artifact_id="art-pm-unrelated-prd-r1",
            task_id="task-pm-unrelated",
            buddy="pm",
            kind="prd",
            title="PM Unrelated PRD",
            source_run_id="run-pm-unrelated-r1",
            content={"unrelated_secret": "do-not-leak-cross-buddy-body"},
            summary="Unrelated source summary",
        )
        return track_id, str(pm_artifact["id"]), str(design_artifact["id"]), str(unrelated_artifact["id"])

    def _artifacts_snapshot(self) -> dict[str, dict[str, object]]:
        rows: dict[str, dict[str, object]] = {}
        artifacts_dir = self._runtime_path("buddyswitch/objects/artifacts")
        if not artifacts_dir.exists():
            return rows
        for path in sorted(artifacts_dir.glob("*.json")):
            rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
        return rows

    def _tasks_snapshot(self) -> dict[str, dict[str, object]]:
        rows: dict[str, dict[str, object]] = {}
        tasks_dir = self._runtime_path("buddyswitch/objects/tasks")
        if not tasks_dir.exists():
            return rows
        for path in sorted(tasks_dir.glob("*.json")):
            rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
        return rows

    def test_list_get_and_get_current_are_scoped_to_active_current_task(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-current")
        env_store.create_track(
            "track-artifact-list-scope",
            "Artifact List Scope",
            status="active",
            current_buddy="pm",
            next_buddy="dev",
            summary="artifact list by track",
        )
        self._seed_task(task_id="task-dev-current", buddy="dev", title="Dev Current", track_id="track-artifact-list-scope")
        self._seed_task(task_id="task-dev-other", buddy="dev", title="Dev Other", track_id="track-artifact-list-scope")
        self._seed_task(task_id="task-pm-foreign", buddy="pm", title="PM Foreign", track_id="track-artifact-list-scope")
        current_artifact = self._seed_artifact(
            artifact_id="art-dev-current-report-r1",
            task_id="task-dev-current",
            buddy="dev",
            kind="implementation-report",
            title="Current Report",
            source_run_id="run-dev-current-r1",
            content={"result": "current content"},
        )
        self._seed_artifact(
            artifact_id="art-dev-other-report-r1",
            task_id="task-dev-other",
            buddy="dev",
            kind="implementation-report",
            title="Other Report",
            source_run_id="run-dev-other-r1",
        )
        self._seed_artifact(
            artifact_id="art-pm-secret-prd-r1",
            task_id="task-pm-foreign",
            buddy="pm",
            kind="prd",
            title="Secret PRD",
            source_run_id="run-pm-secret-r1",
            content={"secret": "do not leak"},
        )

        listed = self._dispatch(
            action="list",
            args={"track_id": "track-artifact-list-scope"},
            instance_json=instance_json,
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(listed.get("tool"), "artifact")
        self.assertEqual(listed.get("action"), "artifact.list")
        artifacts = listed.get("artifacts")
        self.assertIsInstance(artifacts, list, msg=listed)
        assert isinstance(artifacts, list)
        listed_ids = {row.get("artifact_id") for row in artifacts if isinstance(row, dict)}
        self.assertEqual(
            listed_ids,
            {"art-dev-current-report-r1", "art-dev-other-report-r1", "art-pm-secret-prd-r1"},
        )

        current = self._dispatch(action="get_current", args={}, instance_json=instance_json)
        self.assertTrue(current.get("ok"), msg=current)
        current_rows = current.get("artifacts")
        self.assertIsInstance(current_rows, list, msg=current)
        assert isinstance(current_rows, list)
        self.assertEqual([row.get("id") for row in current_rows if isinstance(row, dict)], ["art-dev-current-report-r1"])

        fetched = self._dispatch(
            action="get",
            args={"artifact_id": current_artifact["id"]},
            instance_json=instance_json,
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        artifact = fetched.get("artifact")
        self.assertIsInstance(artifact, dict, msg=fetched)
        assert isinstance(artifact, dict)
        self.assertEqual(artifact.get("content"), {"result": "current content"})

    def test_artifact_get_rejects_unrelated_foreign_artifact_with_no_content_leak_contract(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-no-leak", buddy="dev")
        _, _, _, unrelated_artifact_id = self._seed_track_with_pm_and_design_current_artifacts()
        rejected = self._dispatch(
            action="get",
            args={"artifact_id": unrelated_artifact_id},
            instance_json=instance_json,
            instance_id="inst-dev-no-leak",
            buddy="dev",
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("tool"), "artifact")
        self.assertEqual(rejected.get("action"), "artifact.get")
        self.assertEqual(rejected.get("active_buddy"), "dev")
        self.assertEqual(rejected.get("artifact_id"), unrelated_artifact_id)
        self.assertTrue(rejected.get("no_content_leak"), msg=rejected)
        for key in (
            "why",
            "permission_boundary",
            "relation",
            "missing_preconditions",
            "next_actions",
            "command_hint",
        ):
            self.assertIn(key, rejected)
        serialized = json.dumps(rejected, ensure_ascii=True, sort_keys=True)
        self.assertNotIn("do-not-leak-cross-buddy-body", serialized)
        self.assertNotIn('"content":', serialized)
        self.assertNotIn("preview", serialized)
        self.assertNotIn("partial", serialized)
        self.assertNotIn("buddyswitch/objects", serialized)

    def test_artifact_get_lookup_and_payload_errors_keep_body_no_leak_contract(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-artifact-errors", buddy="dev")

        missing = self._dispatch(
            action="get",
            args={"artifact_id": "missing-artifact"},
            instance_json=instance_json,
            instance_id="inst-dev-artifact-errors",
            buddy="dev",
        )
        self.assertFalse(missing.get("ok"), msg=missing)
        self.assertEqual(missing.get("permission_boundary"), "artifact.lookup")
        self.assertTrue(missing.get("no_content_leak"), msg=missing)

        malformed = self._dispatch(
            action="get",
            args={"artifact_id": "../bad"},
            instance_json=instance_json,
            instance_id="inst-dev-artifact-errors",
            buddy="dev",
        )
        self.assertFalse(malformed.get("ok"), msg=malformed)
        self.assertEqual(malformed.get("permission_boundary"), "request-payload")
        self.assertTrue(malformed.get("no_content_leak"), msg=malformed)

        for response in (missing, malformed):
            serialized = json.dumps(response, ensure_ascii=True, sort_keys=True)
            self.assertNotIn('"content":', serialized)
            self.assertNotIn("preview", serialized)
            self.assertNotIn("buddyswitch/objects", serialized)
            self.assertNotIn("buddyswitch/content/runs", serialized)
            self.assertNotIn("runs/raw", serialized)

    def test_artifact_get_rejects_missing_task_or_track_association_without_content(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-association", buddy="dev")

        env_store.create_track(
            "track-association-missing-task",
            "Association Missing Task",
            status="active",
            current_buddy="pm",
            next_buddy="dev",
            summary="missing task association",
        )
        self._seed_task(
            task_id="task-pm-association-missing-task",
            buddy="pm",
            title="PM Missing Task Source",
            track_id="track-association-missing-task",
        )
        self._seed_artifact(
            artifact_id="art-pm-missing-task-r1",
            task_id="task-pm-association-missing-task",
            buddy="pm",
            kind="prd",
            title="PM Missing Task Artifact",
            source_run_id="run-pm-missing-task-r1",
            content={"body": "must-not-leak-missing-task"},
        )
        missing_task_artifact = env_store.get_artifact("art-pm-missing-task-r1")
        self.assertIsNotNone(missing_task_artifact)
        assert missing_task_artifact is not None
        missing_task_artifact["task_id"] = "task-does-not-exist"
        env_store.save_artifact(missing_task_artifact)

        missing_task_response = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-missing-task-r1"},
            instance_json=instance_json,
            instance_id="inst-dev-association",
            buddy="dev",
        )
        self.assertFalse(missing_task_response.get("ok"), msg=missing_task_response)
        self.assertEqual(missing_task_response.get("permission_boundary"), "artifact.track_association")
        self.assertTrue(missing_task_response.get("no_content_leak"), msg=missing_task_response)

        env_store.create_track(
            "track-association-detached",
            "Association Detached",
            status="active",
            current_buddy="pm",
            next_buddy="dev",
            summary="detached task association",
        )
        self._seed_task(
            task_id="task-pm-association-detached",
            buddy="pm",
            title="PM Detached Source",
            track_id="track-association-detached",
        )
        self._seed_artifact(
            artifact_id="art-pm-detached-r1",
            task_id="task-pm-association-detached",
            buddy="pm",
            kind="prd",
            title="PM Detached Artifact",
            source_run_id="run-pm-detached-r1",
            content={"body": "must-not-leak-detached-task"},
        )
        detached_track = env_store.get_track("track-association-detached")
        self.assertIsNotNone(detached_track)
        assert detached_track is not None
        detached_track["task_ids"] = []
        env_store.save_track(detached_track)

        detached_response = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-detached-r1"},
            instance_json=instance_json,
            instance_id="inst-dev-association",
            buddy="dev",
        )
        self.assertFalse(detached_response.get("ok"), msg=detached_response)
        self.assertEqual(detached_response.get("permission_boundary"), "artifact.track_association")
        self.assertTrue(detached_response.get("no_content_leak"), msg=detached_response)

        for response in (missing_task_response, detached_response):
            serialized = json.dumps(response, ensure_ascii=True, sort_keys=True)
            self.assertNotIn("must-not-leak", serialized)
            self.assertNotIn('"content":', serialized)

    def test_artifact_list_requires_existing_track_id(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-list-requires-track", buddy="dev")
        before_artifacts = copy.deepcopy(self._artifacts_snapshot())
        before_tasks = copy.deepcopy(self._tasks_snapshot())
        before_tracks = {row["id"]: row for row in env_store.list_tracks()}

        missing = self._dispatch(
            action="list",
            args={},
            instance_json=instance_json,
            instance_id="inst-dev-list-requires-track",
            buddy="dev",
        )
        self.assertFalse(missing.get("ok"), msg=missing)
        self.assertEqual(missing.get("permission_boundary"), "request-payload")

        malformed = self._dispatch(
            action="list",
            args={"track_id": "../bad"},
            instance_json=instance_json,
            instance_id="inst-dev-list-requires-track",
            buddy="dev",
        )
        self.assertFalse(malformed.get("ok"), msg=malformed)
        self.assertEqual(malformed.get("permission_boundary"), "request-payload")

        unknown = self._dispatch(
            action="list",
            args={"track_id": "track-missing"},
            instance_json=instance_json,
            instance_id="inst-dev-list-requires-track",
            buddy="dev",
        )
        self.assertFalse(unknown.get("ok"), msg=unknown)
        self.assertEqual(unknown.get("permission_boundary"), "track.lookup")
        self.assertEqual(unknown.get("track_id"), "track-missing")
        self.assertTrue(unknown.get("no_content_leak"), msg=unknown)
        hint = unknown.get("command_hint")
        self.assertIsInstance(hint, str, msg=unknown)
        assert isinstance(hint, str)
        self.assertIn("track list", hint)

        self.assertEqual(self._artifacts_snapshot(), before_artifacts)
        self.assertEqual(self._tasks_snapshot(), before_tasks)
        self.assertEqual({row["id"]: row for row in env_store.list_tracks()}, before_tracks)

    def test_track_and_task_summary_surfaces_do_not_include_foreign_artifact_body(self) -> None:
        track_id = "track-summary-no-leak"
        env_store.create_track(
            track_id,
            "Summary No Leak Track",
            status="active",
            current_buddy="pm",
            next_buddy="dev",
            summary="summary no leak",
        )
        self._seed_task(task_id="task-pm-summary-no-leak", buddy="pm", title="PM Summary Source", track_id=track_id)
        self._seed_task(task_id="task-dev-summary-no-leak", buddy="dev", title="Dev Participant", track_id=track_id)
        self._seed_artifact(
            artifact_id="art-pm-summary-no-leak-r1",
            task_id="task-pm-summary-no-leak",
            buddy="pm",
            kind="prd",
            title="PM Summary No Leak Artifact",
            source_run_id="run-pm-summary-no-leak-r1",
            content={"body": "pm-foreign-body-should-not-appear-in-summary"},
        )

        instance_json = self._instance_json(instance_id="inst-dev-summary-no-leak", buddy="dev")
        track_response = self._dispatch_tool(
            tool="track",
            action="get",
            args={"track_id": track_id},
            instance_json=instance_json,
            instance_id="inst-dev-summary-no-leak",
            buddy="dev",
        )
        self.assertTrue(track_response.get("ok"), msg=track_response)
        task_response = self._dispatch_tool(
            tool="task",
            action="get",
            args={"task_id": "task-pm-summary-no-leak"},
            instance_json=instance_json,
            instance_id="inst-dev-summary-no-leak",
            buddy="dev",
        )
        self.assertTrue(task_response.get("ok"), msg=task_response)

        serialized = json.dumps({"track": track_response, "task": task_response}, ensure_ascii=True, sort_keys=True)
        self.assertNotIn("pm-foreign-body-should-not-appear-in-summary", serialized)
        self.assertNotIn('"content":', serialized)

    def test_artifact_list_by_track_returns_summary_rows_without_content(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-art-list", buddy="dev")
        track_id, pm_artifact_id, design_artifact_id, _ = self._seed_track_with_pm_and_design_current_artifacts()
        env_store.create_task(
            "task-dev-track-participant",
            "Dev Participant",
            buddy="dev",
            track_id=track_id,
            status="active",
            summary="join-like participant",
            initial_run_id=None,
        )
        listed = self._dispatch(
            action="list",
            args={"track_id": track_id},
            instance_json=instance_json,
            instance_id="inst-dev-art-list",
            buddy="dev",
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(listed.get("track_id"), track_id)
        rows = listed.get("artifacts")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        artifact_ids = {row.get("artifact_id") for row in rows if isinstance(row, dict)}
        self.assertEqual(artifact_ids, {pm_artifact_id, design_artifact_id})
        serialized = json.dumps(rows, ensure_ascii=True, sort_keys=True)
        self.assertNotIn('"content":', serialized)
        for row in rows:
            self.assertIsInstance(row, dict, msg=listed)
            assert isinstance(row, dict)
            self.assertIn("readable_by_current_buddy", row)

    def test_artifact_get_allows_owned_artifacts_including_historical_revision(self) -> None:
        instance_json = self._instance_json(instance_id="inst-dev-owned", buddy="dev", current_task_id="task-dev-owned")
        self._seed_task(task_id="task-dev-owned", buddy="dev", title="Dev Owned")
        self._seed_run_reservation(
            run_id="run-dev-owned-r1",
            task_id="task-dev-owned",
            instance_id="inst-dev-owned",
        )
        self._seed_run_reservation(
            run_id="run-dev-owned-r2",
            task_id="task-dev-owned",
            instance_id="inst-dev-owned",
        )
        first = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-owned-r1",
                "task_id": "task-dev-owned",
                "kind": "implementation-report",
                "title": "Owned R1",
                "summary": "r1",
                "content": {"body": "owned-r1"},
                "source_run_id": "run-dev-owned-r1",
            },
            instance_json=instance_json,
            instance_id="inst-dev-owned",
            buddy="dev",
        )
        self.assertTrue(first.get("ok"), msg=first)
        second = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-owned-r2",
                "task_id": "task-dev-owned",
                "kind": "implementation-report",
                "title": "Owned R2",
                "summary": "r2",
                "content": {"body": "owned-r2"},
                "source_run_id": "run-dev-owned-r2",
            },
            instance_json=instance_json,
            instance_id="inst-dev-owned",
            buddy="dev",
        )
        self.assertTrue(second.get("ok"), msg=second)
        for artifact_id in ("art-dev-owned-r1", "art-dev-owned-r2"):
            fetched = self._dispatch(
                action="get",
                args={"artifact_id": artifact_id},
                instance_json=instance_json,
                instance_id="inst-dev-owned",
                buddy="dev",
            )
            self.assertTrue(fetched.get("ok"), msg=fetched)
            self.assertEqual(fetched.get("relation"), "owner")
            self.assertIn("content", fetched.get("artifact", {}))

    def test_artifact_get_allows_current_track_artifact_for_each_reasonable_relation(self) -> None:
        # pm_lifecycle_owner
        env_store.create_track(
            "track-pm-relation",
            "PM Relation",
            status="active",
            current_buddy="dev",
            next_buddy=None,
            summary="pm relation",
        )
        self._seed_task(task_id="task-design-pm-relation", buddy="design", title="Design Src", track_id="track-pm-relation")
        self._seed_artifact(
            artifact_id="art-design-pm-relation-r1",
            task_id="task-design-pm-relation",
            buddy="design",
            kind="design-handoff",
            title="Design Src",
            source_run_id="run-design-pm-relation-r1",
            content={"body": "pm relation body"},
        )
        pm_instance = self._instance_json(instance_id="inst-pm-relation", buddy="pm")
        pm_read = self._dispatch(
            action="get",
            args={"artifact_id": "art-design-pm-relation-r1"},
            instance_json=pm_instance,
            instance_id="inst-pm-relation",
            buddy="pm",
        )
        self.assertTrue(pm_read.get("ok"), msg=pm_read)
        self.assertEqual(pm_read.get("relation"), "pm_lifecycle_owner")

        # participant
        env_store.create_track(
            "track-participant-relation",
            "Participant Relation",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="participant relation",
        )
        self._seed_task(task_id="task-pm-participant-src", buddy="pm", title="PM Src", track_id="track-participant-relation")
        self._seed_task(task_id="task-dev-participant", buddy="dev", title="Dev Participant", track_id="track-participant-relation")
        self._seed_artifact(
            artifact_id="art-pm-participant-src-r1",
            task_id="task-pm-participant-src",
            buddy="pm",
            kind="prd",
            title="PM Participant Source",
            source_run_id="run-pm-participant-src-r1",
            content={"body": "participant body"},
        )
        dev_instance = self._instance_json(instance_id="inst-dev-participant", buddy="dev")
        dev_read = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-participant-src-r1"},
            instance_json=dev_instance,
            instance_id="inst-dev-participant",
            buddy="dev",
        )
        self.assertTrue(dev_read.get("ok"), msg=dev_read)
        self.assertEqual(dev_read.get("relation"), "participant")

        # current_buddy
        env_store.create_track(
            "track-current-relation",
            "Current Relation",
            status="active",
            current_buddy="design",
            next_buddy=None,
            summary="current relation",
        )
        self._seed_task(task_id="task-pm-current-src", buddy="pm", title="PM Current Src", track_id="track-current-relation")
        self._seed_artifact(
            artifact_id="art-pm-current-src-r1",
            task_id="task-pm-current-src",
            buddy="pm",
            kind="prd",
            title="PM Current Source",
            source_run_id="run-pm-current-src-r1",
            content={"body": "current body"},
        )
        design_instance = self._instance_json(instance_id="inst-design-current", buddy="design")
        design_read = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-current-src-r1"},
            instance_json=design_instance,
            instance_id="inst-design-current",
            buddy="design",
        )
        self.assertTrue(design_read.get("ok"), msg=design_read)
        self.assertEqual(design_read.get("relation"), "current_buddy")

        # next_buddy
        env_store.create_track(
            "track-next-relation",
            "Next Relation",
            status="active",
            current_buddy="pm",
            next_buddy="test",
            summary="next relation",
        )
        self._seed_task(task_id="task-pm-next-src", buddy="pm", title="PM Next Src", track_id="track-next-relation")
        self._seed_artifact(
            artifact_id="art-pm-next-src-r1",
            task_id="task-pm-next-src",
            buddy="pm",
            kind="prd",
            title="PM Next Source",
            source_run_id="run-pm-next-src-r1",
            content={"body": "next body"},
        )
        test_instance = self._instance_json(instance_id="inst-test-next", buddy="test")
        test_read = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-next-src-r1"},
            instance_json=test_instance,
            instance_id="inst-test-next",
            buddy="test",
        )
        self.assertTrue(test_read.get("ok"), msg=test_read)
        self.assertEqual(test_read.get("relation"), "next_buddy")

        # handoff_recipient
        env_store.create_track(
            "track-handoff-recipient",
            "Handoff Recipient",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="handoff recipient relation",
        )
        self._seed_task(task_id="task-pm-handoff-src", buddy="pm", title="PM Handoff Src", track_id="track-handoff-recipient")
        self._seed_artifact(
            artifact_id="art-pm-handoff-src-r1",
            task_id="task-pm-handoff-src",
            buddy="pm",
            kind="prd",
            title="PM Handoff Source",
            source_run_id="run-pm-handoff-src-r1",
            content={"body": "handoff body"},
        )
        env_store.create_handoff(
            handoff_id="handoff-pm-to-dev-relation-r1",
            track_id="track-handoff-recipient",
            source_buddy="pm",
            target_buddy="dev",
            source_task_id="task-pm-handoff-src",
            source_run_id="run-pm-handoff-src-r1",
            artifact_ids=["art-pm-handoff-src-r1"],
            historical_artifact_ids=[],
            reason="Dev should continue from PM source artifact.",
            context="Use explicit handoff record context.",
            status="active",
        )
        handoff_instance = self._instance_json(instance_id="inst-dev-handoff", buddy="dev")
        handoff_read = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-handoff-src-r1"},
            instance_json=handoff_instance,
            instance_id="inst-dev-handoff",
            buddy="dev",
        )
        self.assertTrue(handoff_read.get("ok"), msg=handoff_read)
        self.assertEqual(handoff_read.get("relation"), "handoff_recipient")

    def test_run_audit_only_handoff_does_not_authorize_handoff_recipient(self) -> None:
        env_store.create_track(
            "track-handoff-run-audit-only",
            "Handoff Run Audit Only",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="run audit alone must not grant handoff_recipient relation",
        )
        self._seed_task(task_id="task-pm-handoff-run-audit-only", buddy="pm", title="PM Source", track_id="track-handoff-run-audit-only")
        self._seed_artifact(
            artifact_id="art-pm-handoff-run-audit-only-r1",
            task_id="task-pm-handoff-run-audit-only",
            buddy="pm",
            kind="prd",
            title="PM Handoff Run Audit Only Source",
            source_run_id="run-pm-handoff-run-audit-only-r1",
            content={"body": "run-audit-only"},
        )
        self._write_handoff_run(
            run_id="run-pm-to-dev-handoff-run-audit-only",
            task_id="task-pm-handoff-run-audit-only",
            track_id="track-handoff-run-audit-only",
            buddy_id="pm",
            next_buddy="dev",
        )
        handoff_instance = self._instance_json(instance_id="inst-dev-handoff-run-audit-only", buddy="dev")
        rejected = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-handoff-run-audit-only-r1"},
            instance_json=handoff_instance,
            instance_id="inst-dev-handoff-run-audit-only",
            buddy="dev",
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "artifact.track_relation")
        self.assertEqual(rejected.get("relation"), "none")
        self.assertTrue(rejected.get("no_content_leak"), msg=rejected)

    def test_artifact_get_foreign_relation_success_does_not_suggest_write_actions(self) -> None:
        # participant relation
        env_store.create_track(
            "track-participant-no-write",
            "Participant No Write",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="participant no-write guidance",
        )
        self._seed_task(task_id="task-pm-participant-no-write", buddy="pm", title="PM Src", track_id="track-participant-no-write")
        self._seed_task(task_id="task-dev-participant-no-write", buddy="dev", title="Dev Participant", track_id="track-participant-no-write")
        self._seed_artifact(
            artifact_id="art-pm-participant-no-write-r1",
            task_id="task-pm-participant-no-write",
            buddy="pm",
            kind="prd",
            title="Participant No Write Source",
            source_run_id="run-pm-participant-no-write-r1",
            content={"body": "participant no-write body"},
        )

        # current_buddy relation
        env_store.create_track(
            "track-current-no-write",
            "Current No Write",
            status="active",
            current_buddy="design",
            next_buddy=None,
            summary="current no-write guidance",
        )
        self._seed_task(task_id="task-pm-current-no-write", buddy="pm", title="PM Src", track_id="track-current-no-write")
        self._seed_artifact(
            artifact_id="art-pm-current-no-write-r1",
            task_id="task-pm-current-no-write",
            buddy="pm",
            kind="prd",
            title="Current No Write Source",
            source_run_id="run-pm-current-no-write-r1",
            content={"body": "current no-write body"},
        )

        # next_buddy relation
        env_store.create_track(
            "track-next-no-write",
            "Next No Write",
            status="active",
            current_buddy="pm",
            next_buddy="test",
            summary="next no-write guidance",
        )
        self._seed_task(task_id="task-pm-next-no-write", buddy="pm", title="PM Src", track_id="track-next-no-write")
        self._seed_artifact(
            artifact_id="art-pm-next-no-write-r1",
            task_id="task-pm-next-no-write",
            buddy="pm",
            kind="prd",
            title="Next No Write Source",
            source_run_id="run-pm-next-no-write-r1",
            content={"body": "next no-write body"},
        )

        # handoff_recipient relation via explicit active handoff record
        env_store.create_track(
            "track-handoff-no-write",
            "Handoff No Write",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="handoff no-write guidance",
        )
        self._seed_task(task_id="task-pm-handoff-no-write", buddy="pm", title="PM Src", track_id="track-handoff-no-write")
        self._seed_artifact(
            artifact_id="art-pm-handoff-no-write-r1",
            task_id="task-pm-handoff-no-write",
            buddy="pm",
            kind="prd",
            title="Handoff No Write Source",
            source_run_id="run-pm-handoff-no-write-r1",
            content={"body": "handoff no-write body"},
        )
        env_store.create_handoff(
            handoff_id="handoff-pm-to-dev-no-write-r1",
            track_id="track-handoff-no-write",
            source_buddy="pm",
            target_buddy="dev",
            source_task_id="task-pm-handoff-no-write",
            source_run_id="run-pm-handoff-no-write-r1",
            artifact_ids=["art-pm-handoff-no-write-r1"],
            historical_artifact_ids=[],
            reason="Dev should continue from PM source artifact.",
            context="Use handoff explicit context.",
            status="active",
        )

        scenarios = (
            (
                "participant",
                "inst-dev-participant-no-write",
                "dev",
                "art-pm-participant-no-write-r1",
            ),
            (
                "current_buddy",
                "inst-design-current-no-write",
                "design",
                "art-pm-current-no-write-r1",
            ),
            (
                "next_buddy",
                "inst-test-next-no-write",
                "test",
                "art-pm-next-no-write-r1",
            ),
            (
                "handoff_recipient",
                "inst-dev-handoff-no-write",
                "dev",
                "art-pm-handoff-no-write-r1",
            ),
        )
        for relation, instance_id, buddy, artifact_id in scenarios:
            with self.subTest(relation=relation):
                instance_json = self._instance_json(instance_id=instance_id, buddy=buddy)
                response = self._dispatch(
                    action="get",
                    args={"artifact_id": artifact_id},
                    instance_json=instance_json,
                    instance_id=instance_id,
                    buddy=buddy,
                )
                self.assertTrue(response.get("ok"), msg=response)
                self.assertEqual(response.get("relation"), relation)
                artifact = response.get("artifact")
                self.assertIsInstance(artifact, dict, msg=response)
                assert isinstance(artifact, dict)
                self.assertIn("content", artifact)

                next_actions = response.get("next_actions")
                self.assertIsInstance(next_actions, list, msg=response)
                assert isinstance(next_actions, list)
                forbidden_write_actions = {
                    ("artifact", "create_revision"),
                    ("artifact", "update_metadata"),
                }
                observed_actions = {
                    (str(row.get("tool") or ""), str(row.get("action") or ""))
                    for row in next_actions
                    if isinstance(row, dict)
                }
                self.assertTrue(observed_actions, msg=response)
                self.assertFalse(observed_actions & forbidden_write_actions, msg=response)

                hints = "\n".join(str(item) for item in response.get("allowed_next_actions", []))
                self.assertNotIn("artifact.create_revision", hints)
                self.assertNotIn("artifact.update_metadata", hints)

    def test_archived_or_superseded_handoff_record_does_not_authorize_handoff_recipient(self) -> None:
        env_store.create_track(
            "track-handoff-status-boundary",
            "Handoff Status Boundary",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="archived/superseded handoff must not grant read relation",
        )
        self._seed_task(
            task_id="task-pm-handoff-status-boundary",
            buddy="pm",
            title="PM Source",
            track_id="track-handoff-status-boundary",
        )
        self._seed_artifact(
            artifact_id="art-pm-handoff-status-boundary-r1",
            task_id="task-pm-handoff-status-boundary",
            buddy="pm",
            kind="prd",
            title="PM Handoff Status Boundary Source",
            source_run_id="run-pm-handoff-status-boundary-r1",
            content={"body": "handoff status boundary"},
        )
        dev_instance = self._instance_json(instance_id="inst-dev-handoff-status-boundary", buddy="dev")

        for status in ("archived", "superseded"):
            with self.subTest(status=status):
                env_store.create_handoff(
                    handoff_id=f"handoff-pm-dev-{status}-r1",
                    track_id="track-handoff-status-boundary",
                    source_buddy="pm",
                    target_buddy="dev",
                    source_task_id="task-pm-handoff-status-boundary",
                    source_run_id=f"run-pm-handoff-status-{status}-r1",
                    artifact_ids=["art-pm-handoff-status-boundary-r1"],
                    historical_artifact_ids=[],
                    reason=f"{status} handoff should not authorize read relation",
                    context="status boundary",
                    status=status,
                )
                response = self._dispatch(
                    action="get",
                    args={"artifact_id": "art-pm-handoff-status-boundary-r1"},
                    instance_json=dev_instance,
                    instance_id="inst-dev-handoff-status-boundary",
                    buddy="dev",
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("permission_boundary"), "artifact.track_relation")
                self.assertEqual(response.get("relation"), "none")
                self.assertTrue(response.get("no_content_leak"), msg=response)

    def test_artifact_get_rejects_stale_foreign_artifact_even_when_participant(self) -> None:
        env_store.create_track(
            "track-stale-foreign",
            "Stale Foreign",
            status="active",
            current_buddy="pm",
            next_buddy=None,
            summary="stale foreign",
        )
        self._seed_task(task_id="task-pm-stale", buddy="pm", title="PM Stale", track_id="track-stale-foreign")
        self._seed_task(task_id="task-dev-stale", buddy="dev", title="Dev Participant", track_id="track-stale-foreign")
        self._seed_artifact(
            artifact_id="art-pm-stale-r1",
            task_id="task-pm-stale",
            buddy="pm",
            kind="prd",
            title="PM Stale R1",
            source_run_id="run-pm-stale-r1",
            content={"body": "stale-r1"},
        )
        self._seed_artifact(
            artifact_id="art-pm-stale-r2",
            task_id="task-pm-stale",
            buddy="pm",
            kind="prd",
            title="PM Stale R2",
            source_run_id="run-pm-stale-r2",
            content={"body": "stale-r2"},
        )
        dev_instance = self._instance_json(instance_id="inst-dev-stale", buddy="dev")
        rejected = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-stale-r1"},
            instance_json=dev_instance,
            instance_id="inst-dev-stale",
            buddy="dev",
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "artifact.currentness")
        self.assertTrue(rejected.get("no_content_leak"), msg=rejected)

    def test_artifact_get_rejects_archived_track_relation_without_content(self) -> None:
        env_store.create_track(
            "track-archived-foreign",
            "Archived Foreign",
            status="archived",
            current_buddy="pm",
            next_buddy=None,
            summary="archived",
        )
        self._seed_task(task_id="task-pm-archived", buddy="pm", title="PM Archived", track_id="track-archived-foreign")
        self._seed_task(task_id="task-dev-archived", buddy="dev", title="Dev Archived", track_id="track-archived-foreign")
        self._seed_artifact(
            artifact_id="art-pm-archived-r1",
            task_id="task-pm-archived",
            buddy="pm",
            kind="prd",
            title="PM Archived Source",
            source_run_id="run-pm-archived-r1",
            content={"body": "archived body"},
        )
        dev_instance = self._instance_json(instance_id="inst-dev-archived", buddy="dev")
        rejected = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-archived-r1"},
            instance_json=dev_instance,
            instance_id="inst-dev-archived",
            buddy="dev",
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "track.lifecycle_status")
        self.assertTrue(rejected.get("no_content_leak"), msg=rejected)

    def test_artifact_list_get_and_get_current_include_decision_metadata_fields(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-metadata")
        env_store.create_track(
            "track-dev-metadata",
            "Dev Metadata Track",
            status="active",
            current_buddy="dev",
            next_buddy=None,
            summary="metadata",
        )
        self._seed_task(task_id="task-dev-metadata", buddy="dev", title="Dev Metadata Task", track_id="track-dev-metadata")
        self._seed_run_reservation(run_id="run-dev-metadata-r1", task_id="task-dev-metadata")
        self._seed_run_reservation(run_id="run-dev-metadata-r2", task_id="task-dev-metadata")

        first = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-metadata-report-r1",
                "task_id": "task-dev-metadata",
                "kind": "implementation-report",
                "title": "Metadata Report R1",
                "summary": "r1",
                "content": {"body": "r1"},
                "source_run_id": "run-dev-metadata-r1",
            },
            instance_json=instance_json,
        )
        self.assertTrue(first.get("ok"), msg=first)
        second = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-metadata-report-r2",
                "task_id": "task-dev-metadata",
                "kind": "implementation-report",
                "title": "Metadata Report R2",
                "summary": "r2",
                "content": {"body": "r2"},
                "source_run_id": "run-dev-metadata-r2",
            },
            instance_json=instance_json,
        )
        self.assertTrue(second.get("ok"), msg=second)

        listed = self._dispatch(
            action="list",
            args={"track_id": "track-dev-metadata"},
            instance_json=instance_json,
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        listed_rows = listed.get("artifacts")
        self.assertIsInstance(listed_rows, list, msg=listed)
        assert isinstance(listed_rows, list)
        self.assertGreaterEqual(len(listed_rows), 1)
        first_row = listed_rows[0]
        self.assertIsInstance(first_row, dict, msg=listed)
        assert isinstance(first_row, dict)
        for key in ("source_buddy", "source_run", "source_run_id", "revision", "currentness"):
            self.assertIn(key, first_row)
        self.assertIn(first_row.get("source_buddy"), {"dev"})
        self.assertIn(first_row.get("currentness"), {"current"})

        fetched = self._dispatch(
            action="get",
            args={"artifact_id": "art-dev-metadata-report-r2"},
            instance_json=instance_json,
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        artifact = fetched.get("artifact")
        self.assertIsInstance(artifact, dict, msg=fetched)
        assert isinstance(artifact, dict)
        for key in ("source_buddy", "source_run", "revision", "is_current", "currentness"):
            self.assertIn(key, artifact)
        self.assertEqual(artifact.get("source_run"), "run-dev-metadata-r2")
        self.assertEqual(artifact.get("currentness"), "current")

        current = self._dispatch(action="get_current", args={}, instance_json=instance_json)
        self.assertTrue(current.get("ok"), msg=current)
        current_rows = current.get("artifacts")
        self.assertIsInstance(current_rows, list, msg=current)
        assert isinstance(current_rows, list)
        self.assertEqual([row.get("id") for row in current_rows if isinstance(row, dict)], ["art-dev-metadata-report-r2"])
        current_row = current_rows[0]
        self.assertIsInstance(current_row, dict, msg=current)
        assert isinstance(current_row, dict)
        self.assertEqual(current_row.get("source_run"), "run-dev-metadata-r2")
        self.assertEqual(current_row.get("currentness"), "current")

    def test_create_revision_promotes_current_artifact_and_updates_task_slots(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-revision")
        self._seed_task(task_id="task-dev-revision", buddy="dev", title="Dev Revision")
        self._seed_run_reservation(run_id="run-dev-revision-r1", task_id="task-dev-revision")
        self._seed_run_reservation(run_id="run-dev-revision-r2", task_id="task-dev-revision")

        first = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-revision-report-r1",
                "task_id": "task-dev-revision",
                "kind": "implementation-report",
                "title": "Revision Report",
                "summary": "first",
                "content": {"body": "first"},
                "source_run_id": "run-dev-revision-r1",
            },
            instance_json=instance_json,
        )
        self.assertTrue(first.get("ok"), msg=first)
        self.assertEqual(first.get("action"), "artifact.create_revision")
        self.assertEqual(first.get("artifact_id"), "art-dev-revision-report-r1")
        first_artifact = env_store.get_artifact("art-dev-revision-report-r1")
        self.assertIsNotNone(first_artifact)
        assert first_artifact is not None
        self.assertTrue(first_artifact["is_current"])
        self.assertEqual(first_artifact["revision"], 1)

        second = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-revision-report-r2",
                "task_id": "task-dev-revision",
                "kind": "implementation-report",
                "title": "Revision Report",
                "summary": "second",
                "content": {"body": "second"},
                "source_run_id": "run-dev-revision-r2",
            },
            instance_json=instance_json,
        )
        self.assertTrue(second.get("ok"), msg=second)
        second_artifact = env_store.get_artifact("art-dev-revision-report-r2")
        previous_artifact = env_store.get_artifact("art-dev-revision-report-r1")
        task = env_store.get_task("task-dev-revision")
        self.assertIsNotNone(second_artifact)
        self.assertIsNotNone(previous_artifact)
        self.assertIsNotNone(task)
        assert second_artifact is not None
        assert previous_artifact is not None
        assert task is not None
        self.assertEqual(second_artifact["revision"], 2)
        self.assertEqual(second_artifact["supersedes_artifact_id"], "art-dev-revision-report-r1")
        self.assertTrue(second_artifact["is_current"])
        self.assertFalse(previous_artifact["is_current"])
        self.assertEqual(task["artifact_ids"], ["art-dev-revision-report-r1", "art-dev-revision-report-r2"])
        self.assertEqual(
            task["artifact_slots"]["implementation-report"],
            {
                "current_artifact_id": "art-dev-revision-report-r2",
                "revision_count": 2,
            },
        )

    def test_create_revision_allows_taskless_prepare_source_run_after_explicit_task_selection(self) -> None:
        instance_id = "inst-dev-taskless-source"
        instance_json = self._instance_json(
            instance_id=instance_id,
            buddy="dev",
            current_task_id=None,
        )
        prepared = self._prepare(
            text="先调研再决定任务",
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="dev",
        )
        self.assertIsNone(prepared.get("current_task_id"))
        run_envelope = prepared.get("run_envelope")
        self.assertIsInstance(run_envelope, dict, msg=prepared)
        assert isinstance(run_envelope, dict)
        source_run_id = run_envelope.get("run_id")
        self.assertIsInstance(source_run_id, str, msg=prepared)
        assert isinstance(source_run_id, str)

        task_id = "task-dev-selected-after-taskless-prepare"
        created_task = self._dispatch_tool(
            tool="task",
            action="create",
            args={"task_id": task_id, "title": "Selected after taskless prepare", "summary": "artifact target task"},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="dev",
        )
        self.assertTrue(created_task.get("ok"), msg=created_task)
        selected_task = self._dispatch_tool(
            tool="task",
            action="set_current",
            args={"task_id": task_id},
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="dev",
        )
        self.assertTrue(selected_task.get("ok"), msg=selected_task)

        created = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-taskless-source-r1",
                "task_id": task_id,
                "kind": "implementation-report",
                "title": "Taskless Source Run Artifact",
                "summary": "created after explicit task selection",
                "content": {"body": "artifact created from taskless reservation"},
                "source_run_id": source_run_id,
            },
            instance_json=instance_json,
            instance_id=instance_id,
            buddy="dev",
        )
        self.assertTrue(created.get("ok"), msg=created)
        artifact = env_store.get_artifact("art-dev-taskless-source-r1")
        self.assertIsNotNone(artifact)
        assert artifact is not None
        self.assertEqual(artifact["task_id"], task_id)
        self.assertEqual(artifact["source_run_id"], source_run_id)

    def test_create_revision_rejects_mismatched_bound_reservation_task(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-bound-a")
        self._seed_task(task_id="task-dev-bound-a", buddy="dev", title="Bound Task A")
        self._seed_task(task_id="task-dev-bound-b", buddy="dev", title="Bound Task B")
        self._seed_run_reservation(run_id="run-dev-bound-a-r1", task_id="task-dev-bound-a")
        before_artifacts = copy.deepcopy(self._artifacts_snapshot())

        rejected = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-bound-mismatch-r1",
                "task_id": "task-dev-bound-b",
                "kind": "implementation-report",
                "title": "Bound Reservation Mismatch",
                "summary": "must reject task mismatch",
                "content": {"body": "should not write"},
                "source_run_id": "run-dev-bound-a-r1",
            },
            instance_json=instance_json,
        )
        self.assertFalse(rejected.get("ok"), msg=rejected)
        self.assertEqual(rejected.get("permission_boundary"), "artifact.source_run")
        error = rejected.get("error")
        self.assertIsInstance(error, dict, msg=rejected)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_ARTIFACT_SOURCE_RUN")
        self.assertIn("run reservation task mismatch", str(error.get("message")))
        self.assertEqual(self._artifacts_snapshot(), before_artifacts)
        self.assertIsNone(env_store.get_artifact("art-dev-bound-mismatch-r1"))

    def test_foreign_task_and_artifact_reject_without_content_leak_or_mutation(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-current")
        self._seed_task(task_id="task-dev-current", buddy="dev", title="Dev Current")
        env_store.create_track(
            "track-pm-secret",
            "PM Secret Track",
            status="active",
            current_buddy="pm",
            next_buddy="design",
            summary="pm secret",
        )
        self._seed_task(task_id="task-pm-secret", buddy="pm", title="PM Secret", track_id="track-pm-secret")
        self._seed_artifact(
            artifact_id="art-pm-secret-prd-r1",
            task_id="task-pm-secret",
            buddy="pm",
            kind="prd",
            title="Secret PRD",
            source_run_id="run-pm-secret-r1",
            content={"secret": "full foreign content"},
        )
        before_artifacts = copy.deepcopy(self._artifacts_snapshot())
        before_tasks = copy.deepcopy(self._tasks_snapshot())

        fetched = self._dispatch(
            action="get",
            args={"artifact_id": "art-pm-secret-prd-r1"},
            instance_json=instance_json,
        )
        self.assertFalse(fetched.get("ok"), msg=fetched)
        self.assertIn(
            fetched.get("permission_boundary"),
            {"artifact.track_relation", "artifact.currentness", "track.lifecycle_status"},
        )
        self.assertTrue(fetched.get("no_content_leak"), msg=fetched)
        self.assertNotIn("full foreign content", json.dumps(fetched, sort_keys=True))

        created = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-bad-r1",
                "task_id": "task-pm-secret",
                "kind": "implementation-report",
                "title": "Bad Cross Buddy",
                "content": {"body": "bad"},
                "source_run_id": "run-dev-bad-r1",
            },
            instance_json=instance_json,
        )
        self.assertFalse(created.get("ok"), msg=created)
        self.assertEqual(created.get("permission_boundary"), "task.buddy_scope")

        metadata = self._dispatch(
            action="update_metadata",
            args={
                "artifact_id": "art-pm-secret-prd-r1",
                "summary": "dev must not mutate pm metadata",
            },
            instance_json=instance_json,
        )
        self.assertFalse(metadata.get("ok"), msg=metadata)
        self.assertEqual(metadata.get("permission_boundary"), "artifact.buddy_scope")
        self.assertEqual(self._artifacts_snapshot(), before_artifacts)
        self.assertEqual(self._tasks_snapshot(), before_tasks)

    def test_kind_content_source_run_and_update_metadata_boundaries_do_not_mutate(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-current")
        self._seed_task(task_id="task-dev-current", buddy="dev", title="Dev Current")
        self._seed_artifact(
            artifact_id="art-dev-report-r1",
            task_id="task-dev-current",
            buddy="dev",
            kind="implementation-report",
            title="Existing Report",
            source_run_id="run-dev-existing-r1",
        )
        before_artifacts = copy.deepcopy(self._artifacts_snapshot())
        before_tasks = copy.deepcopy(self._tasks_snapshot())

        bad_kind = self._dispatch(
            action="create_revision",
            args={
                "task_id": "task-dev-current",
                "kind": "prd",
                "title": "Wrong Kind",
                "content": {"body": "wrong"},
                "source_run_id": "run-dev-current-r2",
            },
            instance_json=instance_json,
        )
        self.assertFalse(bad_kind.get("ok"), msg=bad_kind)
        self.assertEqual(bad_kind.get("permission_boundary"), "manifest.artifact_kinds")

        bad_content = self._dispatch(
            action="create_revision",
            args={
                "task_id": "task-dev-current",
                "kind": "implementation-report",
                "title": "Bad Content",
                "content": ["not", "an", "object"],
                "source_run_id": "run-dev-current-r2",
            },
            instance_json=instance_json,
        )
        self.assertFalse(bad_content.get("ok"), msg=bad_content)
        self.assertEqual(bad_content.get("permission_boundary"), "request-payload")

        bad_run = self._dispatch(
            action="create_revision",
            args={
                "task_id": "task-dev-current",
                "kind": "implementation-report",
                "title": "No Reservation",
                "content": {"body": "missing source"},
                "source_run_id": "run-dev-not-reserved",
            },
            instance_json=instance_json,
        )
        self.assertFalse(bad_run.get("ok"), msg=bad_run)
        self.assertEqual(bad_run.get("permission_boundary"), "artifact.source_run")

        content_overwrite = self._dispatch(
            action="update_metadata",
            args={
                "artifact_id": "art-dev-report-r1",
                "content": {"body": "overwrite"},
            },
            instance_json=instance_json,
        )
        self.assertFalse(content_overwrite.get("ok"), msg=content_overwrite)
        self.assertEqual(content_overwrite.get("permission_boundary"), "request-payload")
        self.assertEqual(self._artifacts_snapshot(), before_artifacts)
        self.assertEqual(self._tasks_snapshot(), before_tasks)

    def test_update_metadata_changes_only_metadata_with_reserved_source_run(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-current")
        self._seed_task(task_id="task-dev-current", buddy="dev", title="Dev Current")
        self._seed_artifact(
            artifact_id="art-dev-report-r1",
            task_id="task-dev-current",
            buddy="dev",
            kind="implementation-report",
            title="Existing Report",
            summary="old summary",
            source_run_id="run-dev-existing-r1",
            content={"body": "unchanged"},
        )
        self._seed_run_reservation(run_id="run-dev-current-r2", task_id="task-dev-current")

        updated = self._dispatch(
            action="update_metadata",
            args={
                "artifact_id": "art-dev-report-r1",
                "title": "Updated Report",
                "summary": "new summary",
                "source_run_id": "run-dev-current-r2",
            },
            instance_json=instance_json,
        )

        self.assertTrue(updated.get("ok"), msg=updated)
        self.assertEqual(updated.get("action"), "artifact.update_metadata")
        artifact = env_store.get_artifact("art-dev-report-r1")
        task = env_store.get_task("task-dev-current")
        self.assertIsNotNone(artifact)
        self.assertIsNotNone(task)
        assert artifact is not None
        assert task is not None
        self.assertEqual(artifact["title"], "Updated Report")
        self.assertEqual(artifact["summary"], "new summary")
        self.assertEqual(artifact["source_run_id"], "run-dev-current-r2")
        self.assertEqual(artifact["content"], {"body": "unchanged"})
        self.assertEqual(
            task["artifact_slots"]["implementation-report"],
            {
                "current_artifact_id": "art-dev-report-r1",
                "revision_count": 1,
            },
        )

    def test_validate_payload_does_not_mutate_and_payload_authored_identity_is_ignored(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-current")
        self._seed_task(task_id="task-dev-current", buddy="dev", title="Dev Current")
        self._seed_run_reservation(run_id="run-dev-current-r1", task_id="task-dev-current")
        before_artifacts = copy.deepcopy(self._artifacts_snapshot())
        before_tasks = copy.deepcopy(self._tasks_snapshot())

        validated = self._dispatch(
            action="validate_payload",
            args={
                "task_id": "task-dev-current",
                "buddy": "pm",
                "active_buddy": "pm",
                "kind": "implementation-report",
                "title": "Validated Report",
                "summary": "valid",
                "content": {"body": "valid"},
                "source_run_id": "run-dev-current-r1",
            },
            instance_json=instance_json,
        )
        self.assertTrue(validated.get("ok"), msg=validated)
        self.assertEqual(validated.get("active_buddy"), "dev")
        normalized = validated.get("normalized")
        self.assertIsInstance(normalized, dict, msg=validated)
        assert isinstance(normalized, dict)
        self.assertEqual(normalized.get("buddy"), "dev")
        self.assertEqual(self._artifacts_snapshot(), before_artifacts)
        self.assertEqual(self._tasks_snapshot(), before_tasks)

        created = self._dispatch(
            action="create_revision",
            args={
                "artifact_id": "art-dev-identity-r1",
                "task_id": "task-dev-current",
                "buddy": "pm",
                "active_buddy": "pm",
                "kind": "implementation-report",
                "title": "Identity Ignored",
                "summary": "created",
                "content": {"body": "created"},
                "source_run_id": "run-dev-current-r1",
            },
            instance_json=instance_json,
        )
        self.assertTrue(created.get("ok"), msg=created)
        artifact = env_store.get_artifact("art-dev-identity-r1")
        self.assertIsNotNone(artifact)
        assert artifact is not None
        self.assertEqual(artifact["buddy"], "dev")

    def test_cli_prints_structured_json_for_artifact_commands(self) -> None:
        env = os.environ.copy()
        env.pop("BUDDYSWITCH_RUNTIME_BROKER_SOCKET", None)
        env.pop("BUDDYSWITCH_INSTANCE_ID", None)
        env.pop("BUDDYSWITCH_ACTIVE_BUDDY", None)

        unavailable = subprocess.run(
            ["python3", str(ENV_CLIENT), "artifact", "list", "--track-id", "track-any"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(unavailable.returncode, 0, msg=unavailable.stderr)
        unavailable_payload = json.loads(unavailable.stdout)
        self.assertFalse(unavailable_payload.get("ok"), msg=unavailable_payload)
        self.assertEqual(unavailable_payload.get("error", {}).get("code"), "E_RUNTIME_BROKER_UNAVAILABLE")

        missing_payload_file = subprocess.run(
            [
                "python3",
                str(ENV_CLIENT),
                "artifact",
                "create-revision",
                "--payload",
                str(ROOT / "tmp" / "missing-artifact.json"),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(missing_payload_file.returncode, 2)
        self.assertIn("payload file is not readable", missing_payload_file.stderr.lower())

    def test_artifact_cli_requires_track_id_for_list(self) -> None:
        env = os.environ.copy()
        env.pop("BUDDYSWITCH_RUNTIME_BROKER_SOCKET", None)
        env.pop("BUDDYSWITCH_INSTANCE_ID", None)
        env.pop("BUDDYSWITCH_ACTIVE_BUDDY", None)

        missing_track_id = subprocess.run(
            ["python3", str(ENV_CLIENT), "artifact", "list"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(missing_track_id.returncode, 2, msg=missing_track_id.stderr)
        self.assertIn("--track-id", missing_track_id.stderr)

    def test_live_broker_artifact_cli_uses_env_tool_and_returns_structured_rejection(self) -> None:
        self._seed_task(task_id="task-pm-secret", buddy="pm", title="PM Secret")
        self._seed_artifact(
            artifact_id="art-pm-secret-prd-r1",
            task_id="task-pm-secret",
            buddy="pm",
            kind="prd",
            title="Secret PRD",
            source_run_id="run-pm-secret-r1",
            content={"secret": "broker must not leak this"},
        )
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev")

        socket_path = self._runtime_path("runtime/runtime-broker.socket")
        pid_path = self._runtime_path("runtime/runtime-broker.pid")
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        broker_env = os.environ.copy()
        broker_env.update(
            {
                "BUDDYSWITCH_SHARED_ROOT": str(self.runtime_root),
                "BUDDYSWITCH_STATE_ROOT": str(self.runtime_root),
            }
        )
        broker = subprocess.Popen(
            [
                "python3",
                str(ROOT / "scripts" / "runtime_kernel" / "broker.py"),
                "serve",
                "--socket",
                str(socket_path),
                "--pid-file",
                str(pid_path),
                "--instance-json",
                str(instance_json),
                "--manifest",
                str(MANIFEST),
            ],
            cwd=ROOT,
            env=broker_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if socket_path.exists():
                    break
                if broker.poll() is not None:
                    break
                time.sleep(0.05)
            if broker.poll() is not None:
                stderr = broker.stderr.read() if broker.stderr else "broker exited"
                self.fail(stderr)
            self.assertTrue(socket_path.exists(), "broker socket was not created")

            client_env = os.environ.copy()
            client_env.update(
                {
                    "BUDDYSWITCH_RUNTIME_BROKER_SOCKET": str(socket_path),
                    "BUDDYSWITCH_INSTANCE_ID": "inst-dev-example",
                    "BUDDYSWITCH_ACTIVE_BUDDY": "dev",
                }
            )
            completed = subprocess.run(
                ["python3", str(ENV_CLIENT), "artifact", "get", "--artifact-id", "art-pm-secret-prd-r1"],
                cwd=ROOT,
                env=client_env,
                text=True,
                capture_output=True,
                check=False,
                timeout=5,
            )
        finally:
            broker.terminate()
            try:
                broker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                broker.kill()
                broker.wait(timeout=5)

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload.get("ok"), msg=payload)
        self.assertEqual(payload.get("tool"), "artifact")
        self.assertEqual(payload.get("action"), "artifact.get")
        self.assertIn(
            payload.get("permission_boundary"),
            {"artifact.track_association", "artifact.track_relation", "artifact.currentness", "track.lifecycle_status"},
        )
        self.assertNotIn("broker must not leak this", completed.stdout)


if __name__ == "__main__":
    unittest.main()
