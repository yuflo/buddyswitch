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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_store  # noqa: E402
import runtime_kernel.broker as runtime_broker  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402

MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v1"
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

    def _dispatch(
        self,
        *,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        instance_id: str = "inst-dev-example",
        buddy: str = "dev",
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "instance_id": instance_id,
            "active_buddy": buddy,
            "method": "env.tool",
            "payload": {"tool": "artifact", "action": action, "args": args},
        }
        return runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

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
        self._seed_task(task_id="task-dev-current", buddy="dev", title="Dev Current")
        self._seed_task(task_id="task-dev-other", buddy="dev", title="Dev Other")
        self._seed_task(task_id="task-pm-foreign", buddy="pm", title="PM Foreign")
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

        listed = self._dispatch(action="list", args={}, instance_json=instance_json)
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(listed.get("tool"), "artifact")
        self.assertEqual(listed.get("action"), "artifact.list")
        artifacts = listed.get("artifacts")
        self.assertIsInstance(artifacts, list, msg=listed)
        assert isinstance(artifacts, list)
        self.assertEqual([row.get("id") for row in artifacts if isinstance(row, dict)], ["art-dev-current-report-r1"])

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

    def test_artifact_list_get_and_get_current_include_decision_metadata_fields(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-metadata")
        self._seed_task(task_id="task-dev-metadata", buddy="dev", title="Dev Metadata Task")
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

        listed = self._dispatch(action="list", args={}, instance_json=instance_json)
        self.assertTrue(listed.get("ok"), msg=listed)
        listed_rows = listed.get("artifacts")
        self.assertIsInstance(listed_rows, list, msg=listed)
        assert isinstance(listed_rows, list)
        self.assertGreaterEqual(len(listed_rows), 2)
        first_row = listed_rows[0]
        self.assertIsInstance(first_row, dict, msg=listed)
        assert isinstance(first_row, dict)
        for key in ("source_buddy", "source_run", "revision", "is_current", "currentness"):
            self.assertIn(key, first_row)
        self.assertEqual(first_row.get("source_buddy"), "dev")
        self.assertIn(first_row.get("currentness"), {"current", "superseded"})

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

    def test_foreign_task_and_artifact_reject_without_content_leak_or_mutation(self) -> None:
        instance_json = self._instance_json(current_task_id="task-dev-current")
        self._seed_task(task_id="task-dev-current", buddy="dev", title="Dev Current")
        self._seed_task(task_id="task-pm-secret", buddy="pm", title="PM Secret")
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
        self.assertEqual(fetched.get("permission_boundary"), "artifact.buddy_scope")
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
            ["python3", str(ENV_CLIENT), "artifact", "list"],
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
        self.assertEqual(payload.get("permission_boundary"), "artifact.buddy_scope")
        self.assertNotIn("broker must not leak this", completed.stdout)


if __name__ == "__main__":
    unittest.main()
