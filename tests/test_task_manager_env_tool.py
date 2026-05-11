#!/usr/bin/env python3
"""Functional coverage for broker-routed env.tool task-manager operations."""

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


class TaskManagerEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
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
                    "created_at": "2026-05-10T00:00:00Z",
                    "updated_at": "2026-05-10T00:00:00Z",
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
        payload: dict[str, object] = {"tool": "task", "action": action, "args": args}
        request = {
            "protocol": PROTOCOL,
            "instance_id": instance_id,
            "active_buddy": buddy,
            "method": "env.tool",
            "payload": payload,
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
        summary: str = "",
        status: str = "active",
        track_id: str | None = None,
    ) -> None:
        env_store.create_task(
            task_id,
            title,
            buddy=buddy,
            track_id=track_id,
            status=status,
            summary=summary,
            initial_run_id=None,
        )

    def _load_instance(self, instance_json: Path) -> dict[str, object]:
        return json.loads(instance_json.read_text(encoding="utf-8"))

    def _tasks_snapshot(self) -> dict[str, dict[str, object]]:
        rows: dict[str, dict[str, object]] = {}
        tasks_dir = self._runtime_path("buddyswitch/objects/tasks")
        if not tasks_dir.exists():
            return rows
        for path in sorted(tasks_dir.glob("*.json")):
            rows[path.name] = json.loads(path.read_text(encoding="utf-8"))
        return rows

    def _assert_scope_rejection(self, response: dict[str, object], *, action: str, task_id: str) -> None:
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("action"), action)
        error = response.get("error")
        self.assertIsInstance(error, dict, msg=response)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_TASK_BUDDY_SCOPE")
        self.assertEqual(response.get("permission_boundary"), "task.buddy_scope")
        self.assertEqual(response.get("active_buddy"), "dev")
        self.assertEqual(response.get("task_id"), task_id)
        allowed_next_actions = response.get("allowed_next_actions")
        self.assertIsInstance(allowed_next_actions, list, msg=response)
        assert isinstance(allowed_next_actions, list)
        self.assertTrue(allowed_next_actions, msg=response)

    def test_task_create_list_get_update_archive_for_active_buddy(self) -> None:
        instance_json = self._instance_json()
        self._seed_task(task_id="task-dev-existing", buddy="dev", title="Dev Existing")
        self._seed_task(task_id="task-pm-foreign", buddy="pm", title="PM Foreign")

        created = self._dispatch(
            action="create",
            args={
                "title": "Dev Created",
                "summary": "created through env tool",
                "buddy": "pm",
                "active_buddy": "pm",
            },
            instance_json=instance_json,
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertEqual(created.get("action"), "task.create")
        self.assertEqual(created.get("active_buddy"), "dev")
        created_task_id = created.get("task_id")
        self.assertIsInstance(created_task_id, str)
        assert isinstance(created_task_id, str)
        created_task = env_store.get_task(created_task_id)
        self.assertIsNotNone(created_task)
        assert created_task is not None
        self.assertEqual(created_task["buddy"], "dev")

        listed = self._dispatch(action="list", args={}, instance_json=instance_json)
        self.assertTrue(listed.get("ok"), msg=listed)
        self.assertEqual(listed.get("action"), "task.list")
        tasks = listed.get("tasks")
        self.assertIsInstance(tasks, list, msg=listed)
        assert isinstance(tasks, list)
        task_ids = {row.get("id") for row in tasks if isinstance(row, dict)}
        self.assertIn("task-dev-existing", task_ids)
        self.assertIn(created_task_id, task_ids)
        self.assertNotIn("task-pm-foreign", task_ids)

        fetched = self._dispatch(action="get", args={"task_id": created_task_id}, instance_json=instance_json)
        self.assertTrue(fetched.get("ok"), msg=fetched)
        self.assertEqual(fetched.get("action"), "task.get")
        self.assertEqual(fetched.get("task_id"), created_task_id)

        summary_updated = self._dispatch(
            action="update",
            args={"task_id": created_task_id, "summary": "summary-only update"},
            instance_json=instance_json,
        )
        self.assertTrue(summary_updated.get("ok"), msg=summary_updated)
        summary_task = env_store.get_task(created_task_id)
        self.assertIsNotNone(summary_task)
        assert summary_task is not None
        self.assertEqual(summary_task["summary"], "summary-only update")

        updated = self._dispatch(
            action="update",
            args={"task_id": created_task_id, "title": "Dev Created Updated", "status": "blocked"},
            instance_json=instance_json,
        )
        self.assertTrue(updated.get("ok"), msg=updated)
        self.assertEqual(updated.get("action"), "task.update")
        self.assertEqual(updated.get("task_id"), created_task_id)
        updated_task = env_store.get_task(created_task_id)
        self.assertIsNotNone(updated_task)
        assert updated_task is not None
        self.assertEqual(updated_task["title"], "Dev Created Updated")
        self.assertEqual(updated_task["status"], "blocked")

        archived = self._dispatch(
            action="archive",
            args={"task_id": created_task_id},
            instance_json=instance_json,
        )
        self.assertTrue(archived.get("ok"), msg=archived)
        self.assertEqual(archived.get("action"), "task.archive")
        archived_task = env_store.get_task(created_task_id)
        self.assertIsNotNone(archived_task)
        assert archived_task is not None
        self.assertEqual(archived_task["status"], "archived")

        archived_fetch = self._dispatch(action="get", args={"task_id": created_task_id}, instance_json=instance_json)
        self.assertTrue(archived_fetch.get("ok"), msg=archived_fetch)
        archived_task_payload = archived_fetch.get("task")
        self.assertIsInstance(archived_task_payload, dict, msg=archived_fetch)
        assert isinstance(archived_task_payload, dict)
        self.assertEqual(archived_task_payload.get("status"), "archived")

        pm_instance_json = self._instance_json(instance_id="inst-pm-example", buddy="pm")
        pm_listed = self._dispatch(
            action="list",
            args={},
            instance_json=pm_instance_json,
            instance_id="inst-pm-example",
            buddy="pm",
        )
        self.assertTrue(pm_listed.get("ok"), msg=pm_listed)
        pm_tasks = pm_listed.get("tasks")
        self.assertIsInstance(pm_tasks, list, msg=pm_listed)
        assert isinstance(pm_tasks, list)
        pm_task_ids = {row.get("id") for row in pm_tasks if isinstance(row, dict)}
        self.assertIn("task-pm-foreign", pm_task_ids)
        self.assertNotIn("task-dev-existing", pm_task_ids)
        self.assertNotIn(created_task_id, pm_task_ids)

    def test_unsupported_update_fields_reject_without_partial_mutation(self) -> None:
        instance_json = self._instance_json()
        self._seed_task(task_id="task-dev-owned", buddy="dev", title="Dev Owned", summary="original")
        before_task = copy.deepcopy(env_store.get_task("task-dev-owned"))
        before_instance = self._load_instance(instance_json)

        response = self._dispatch(
            action="update",
            args={
                "task_id": "task-dev-owned",
                "summary": "should not persist",
                "track_id": "track-dev-example",
                "artifact_ids": ["artifact-dev-example"],
                "run_ids": ["run-dev-example"],
            },
            instance_json=instance_json,
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("permission_boundary"), "request-payload")
        self.assertEqual(env_store.get_task("task-dev-owned"), before_task)
        self.assertEqual(self._load_instance(instance_json), before_instance)

    def test_cross_buddy_named_task_operations_reject_without_mutation(self) -> None:
        instance_json = self._instance_json()
        self._seed_task(task_id="task-dev-owned", buddy="dev", title="Dev Owned")
        self._seed_task(task_id="task-pm-foreign", buddy="pm", title="PM Foreign", summary="do not mutate")
        before_task = copy.deepcopy(env_store.get_task("task-pm-foreign"))
        before_instance = self._load_instance(instance_json)

        for action, args in (
            ("get", {"task_id": "task-pm-foreign"}),
            ("update", {"task_id": "task-pm-foreign", "summary": "should fail"}),
            ("archive", {"task_id": "task-pm-foreign"}),
            ("set_current", {"task_id": "task-pm-foreign"}),
        ):
            with self.subTest(action=action):
                response = self._dispatch(action=action, args=args, instance_json=instance_json)
                self._assert_scope_rejection(response, action=f"task.{action}", task_id="task-pm-foreign")
                self.assertEqual(env_store.get_task("task-pm-foreign"), before_task)
                self.assertEqual(self._load_instance(instance_json), before_instance)

    def test_set_current_and_get_current_sync_instance_binding(self) -> None:
        instance_json = self._instance_json()
        env_store.create_track(
            "track-dev-example",
            "Dev Track",
            status="active",
            current_buddy="dev",
            next_buddy=None,
            summary="",
        )
        self._seed_task(task_id="task-dev-untracked", buddy="dev", title="Untracked Dev Task")
        self._seed_task(
            task_id="task-dev-tracked",
            buddy="dev",
            title="Tracked Dev Task",
            track_id="track-dev-example",
        )

        untracked_set = self._dispatch(
            action="set_current",
            args={"task_id": "task-dev-untracked"},
            instance_json=instance_json,
        )
        self.assertTrue(untracked_set.get("ok"), msg=untracked_set)
        self.assertEqual(untracked_set.get("action"), "task.set_current")
        instance_after_untracked = self._load_instance(instance_json)
        self.assertEqual(instance_after_untracked["current_task_id"], "task-dev-untracked")
        self.assertIsNone(instance_after_untracked["current_track_id"])

        current_untracked = self._dispatch(action="get_current", args={}, instance_json=instance_json)
        self.assertTrue(current_untracked.get("ok"), msg=current_untracked)
        self.assertEqual(current_untracked.get("action"), "task.get_current")
        task_payload = current_untracked.get("task")
        self.assertIsInstance(task_payload, dict, msg=current_untracked)
        assert isinstance(task_payload, dict)
        self.assertEqual(task_payload.get("id"), "task-dev-untracked")

        tracked_set = self._dispatch(
            action="set_current",
            args={"task_id": "task-dev-tracked"},
            instance_json=instance_json,
        )
        self.assertTrue(tracked_set.get("ok"), msg=tracked_set)
        instance_after_tracked = self._load_instance(instance_json)
        self.assertEqual(instance_after_tracked["current_task_id"], "task-dev-tracked")
        self.assertEqual(instance_after_tracked["current_track_id"], "track-dev-example")

        current_tracked = self._dispatch(action="get_current", args={}, instance_json=instance_json)
        self.assertTrue(current_tracked.get("ok"), msg=current_tracked)
        current_binding = current_tracked.get("current_binding")
        self.assertIsInstance(current_binding, dict, msg=current_tracked)
        assert isinstance(current_binding, dict)
        self.assertEqual(current_binding.get("current_task_id"), "task-dev-tracked")
        self.assertEqual(current_binding.get("current_track_id"), "track-dev-example")
        tracked_payload = current_tracked.get("task")
        self.assertIsInstance(tracked_payload, dict, msg=current_tracked)
        assert isinstance(tracked_payload, dict)
        self.assertEqual(tracked_payload.get("id"), "task-dev-tracked")

        missing_set = self._dispatch(
            action="set_current",
            args={"task_id": "task-dev-missing"},
            instance_json=instance_json,
        )
        self.assertFalse(missing_set.get("ok"), msg=missing_set)
        self.assertEqual(missing_set.get("permission_boundary"), "task.lookup")
        instance_after_missing = self._load_instance(instance_json)
        self.assertEqual(instance_after_missing["current_task_id"], "task-dev-tracked")
        self.assertEqual(instance_after_missing["current_track_id"], "track-dev-example")

    def test_get_current_without_binding_returns_structured_success(self) -> None:
        instance_json = self._instance_json()
        response = self._dispatch(action="get_current", args={}, instance_json=instance_json)
        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("action"), "task.get_current")
        self.assertEqual(response.get("active_buddy"), "dev")
        self.assertIsNone(response.get("task"))
        current_binding = response.get("current_binding")
        self.assertIsInstance(current_binding, dict, msg=response)
        assert isinstance(current_binding, dict)
        self.assertIsNone(current_binding.get("current_task_id"))
        self.assertIsNone(current_binding.get("current_track_id"))
        allowed_next_actions = response.get("allowed_next_actions")
        self.assertIsInstance(allowed_next_actions, list, msg=response)
        assert isinstance(allowed_next_actions, list)
        self.assertTrue(allowed_next_actions, msg=response)

    def test_malformed_or_missing_payload_rejects_without_mutation(self) -> None:
        instance_json = self._instance_json()
        self._seed_task(task_id="task-dev-owned", buddy="dev", title="Dev Owned")
        before_tasks = self._tasks_snapshot()
        before_instance = self._load_instance(instance_json)

        bad_payload_request = {
            "protocol": PROTOCOL,
            "instance_id": "inst-dev-example",
            "active_buddy": "dev",
            "method": "env.tool",
            "payload": {"tool": "task", "action": "update", "args": "bad"},
        }
        bad_payload = runtime_broker.dispatch_runtime_request(
            request=bad_payload_request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )
        self.assertFalse(bad_payload.get("ok"), msg=bad_payload)
        self.assertEqual(bad_payload.get("permission_boundary"), "request-payload")
        self.assertEqual(self._tasks_snapshot(), before_tasks)
        self.assertEqual(self._load_instance(instance_json), before_instance)

        missing_payload = self._dispatch(action="update", args={}, instance_json=instance_json)
        self.assertFalse(missing_payload.get("ok"), msg=missing_payload)
        self.assertEqual(missing_payload.get("permission_boundary"), "request-payload")
        self.assertEqual(self._tasks_snapshot(), before_tasks)
        self.assertEqual(self._load_instance(instance_json), before_instance)

    def test_cli_prints_structured_json_and_exit_codes(self) -> None:
        env = os.environ.copy()
        env.pop("BUDDYSWITCH_RUNTIME_BROKER_SOCKET", None)
        env.pop("BUDDYSWITCH_INSTANCE_ID", None)
        env.pop("BUDDYSWITCH_ACTIVE_BUDDY", None)

        unavailable = subprocess.run(
            ["python3", str(ENV_CLIENT), "task", "list"],
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
            ["python3", str(ENV_CLIENT), "task", "create", "--payload", str(ROOT / "tmp" / "missing-task.json")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(missing_payload_file.returncode, 2)
        self.assertIn("payload file is not readable", missing_payload_file.stderr.lower())

    def test_cli_prints_structured_ok_false_from_live_broker_and_exits_zero(self) -> None:
        instance_json = self._instance_json()
        self._seed_task(task_id="task-pm-foreign", buddy="pm", title="PM Foreign")

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
                ["python3", str(ENV_CLIENT), "task", "get", "--task-id", "task-pm-foreign"],
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
        self.assertEqual(payload.get("action"), "task.get")
        self.assertEqual(payload.get("permission_boundary"), "task.buddy_scope")
        self.assertEqual(payload.get("error", {}).get("code"), "E_TASK_BUDDY_SCOPE")


if __name__ == "__main__":
    unittest.main()
