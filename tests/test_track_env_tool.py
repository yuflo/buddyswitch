#!/usr/bin/env python3
"""Functional coverage for broker-routed env.tool track env tool operations."""

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


class TrackManagerEnvToolTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _instance_json(
        self,
        *,
        instance_id: str = "inst-pm-example",
        buddy: str = "pm",
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
        instance_id: str = "inst-pm-example",
        buddy: str = "pm",
    ) -> dict[str, object]:
        request = {
            "protocol": PROTOCOL,
            "instance_id": instance_id,
            "active_buddy": buddy,
            "method": "env.tool",
            "payload": {"tool": "track", "action": action, "args": args},
        }
        return runtime_broker.dispatch_runtime_request(
            request=request,
            instance_json_path=instance_json,
            manifest_path=MANIFEST,
        )

    def _seed_track(
        self,
        *,
        track_id: str,
        title: str,
        status: str = "active",
        current_buddy: str = "pm",
        next_buddy: str | None = None,
        summary: str = "",
    ) -> None:
        env_store.create_track(
            track_id,
            title,
            status=status,
            current_buddy=current_buddy,
            next_buddy=next_buddy,
            summary=summary,
        )

    def _seed_task(
        self,
        *,
        task_id: str,
        buddy: str,
        title: str,
        track_id: str | None = None,
    ) -> None:
        env_store.create_task(
            task_id,
            title,
            buddy=buddy,
            track_id=track_id,
            status="active",
            summary="",
            initial_run_id=None,
        )

    def _tracks_snapshot(self) -> dict[str, dict[str, object]]:
        rows: dict[str, dict[str, object]] = {}
        tracks_dir = self._runtime_path("buddyswitch/objects/tracks")
        if not tracks_dir.exists():
            return rows
        for path in sorted(tracks_dir.glob("*.json")):
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
                    "timestamp": "2026-05-11T00:00:00Z",
                    "handoff": {
                        "next_buddy": next_buddy,
                        "reason": "handoff for discovery ranking",
                        "context": "continue from PM outputs",
                    },
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _assert_lifecycle_rejection(self, response: dict[str, object], *, action: str) -> None:
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "track")
        self.assertEqual(response.get("action"), action)
        self.assertEqual(response.get("active_buddy"), "dev")
        self.assertEqual(response.get("permission_boundary"), "track.lifecycle_authority")
        error = response.get("error")
        self.assertIsInstance(error, dict, msg=response)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), "E_TRACK_LIFECYCLE_AUTHORITY")
        allowed_next_actions = response.get("allowed_next_actions")
        self.assertIsInstance(allowed_next_actions, list, msg=response)
        assert isinstance(allowed_next_actions, list)
        self.assertTrue(allowed_next_actions, msg=response)

    def test_pm_track_lifecycle_operations_use_env_tool_and_persist(self) -> None:
        instance_json = self._instance_json()

        created = self._dispatch(
            action="create",
            args={
                "track_id": "track-env-tool",
                "title": "Env Tool Track",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "market",
                "summary": "Created through the track env tool.",
            },
            instance_json=instance_json,
        )
        self.assertTrue(created.get("ok"), msg=created)
        self.assertEqual(created.get("tool"), "track")
        self.assertEqual(created.get("action"), "track.create")
        self.assertEqual(created.get("active_buddy"), "pm")
        created_track = env_store.get_track("track-env-tool")
        self.assertIsNotNone(created_track)
        assert created_track is not None
        self.assertEqual(created_track["title"], "Env Tool Track")
        self.assertEqual(created_track["current_buddy"], "pm")
        self.assertEqual(created_track["next_buddy"], "market")

        updated = self._dispatch(
            action="update",
            args={
                "track_id": "track-env-tool",
                "title": "Env Tool Track Updated",
                "status": "blocked",
                "summary": "Blocked pending research.",
            },
            instance_json=instance_json,
        )
        self.assertTrue(updated.get("ok"), msg=updated)
        self.assertEqual(updated.get("action"), "track.update")
        updated_track = env_store.get_track("track-env-tool")
        self.assertIsNotNone(updated_track)
        assert updated_track is not None
        self.assertEqual(updated_track["title"], "Env Tool Track Updated")
        self.assertEqual(updated_track["status"], "blocked")
        self.assertEqual(updated_track["summary"], "Blocked pending research.")

        advanced = self._dispatch(
            action="advance",
            args={
                "track_id": "track-env-tool",
                "current_buddy": "market",
                "next_buddy": "design",
                "status": "active",
                "summary": "Market owns the next step.",
            },
            instance_json=instance_json,
        )
        self.assertTrue(advanced.get("ok"), msg=advanced)
        self.assertEqual(advanced.get("action"), "track.advance")
        advanced_track = env_store.get_track("track-env-tool")
        self.assertIsNotNone(advanced_track)
        assert advanced_track is not None
        self.assertEqual(advanced_track["current_buddy"], "market")
        self.assertEqual(advanced_track["next_buddy"], "design")
        self.assertEqual(advanced_track["status"], "active")

        archived = self._dispatch(
            action="archive",
            args={"track_id": "track-env-tool"},
            instance_json=instance_json,
        )
        self.assertTrue(archived.get("ok"), msg=archived)
        self.assertEqual(archived.get("action"), "track.archive")
        archived_track = env_store.get_track("track-env-tool")
        self.assertIsNotNone(archived_track)
        assert archived_track is not None
        self.assertEqual(archived_track["status"], "archived")

    def test_non_pm_can_read_tracks_but_lifecycle_mutations_reject_without_mutation(self) -> None:
        self._seed_track(
            track_id="track-visible",
            title="Visible Track",
            current_buddy="pm",
            next_buddy="market",
            summary="Readable coordination context.",
        )
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev")

        listed = self._dispatch(
            action="list",
            args={},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        track_ids = {row.get("id") for row in listed.get("tracks", []) if isinstance(row, dict)}
        self.assertIn("track-visible", track_ids)

        fetched = self._dispatch(
            action="get",
            args={"track_id": "track-visible"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        self.assertEqual(fetched.get("track_id"), "track-visible")

        before_tracks = copy.deepcopy(self._tracks_snapshot())
        before_tasks = copy.deepcopy(self._tasks_snapshot())
        for action, args in (
            (
                "create",
                {
                    "track_id": "track-spoofed-create",
                    "title": "Spoofed Create",
                    "active_buddy": "pm",
                },
            ),
            (
                "update",
                {
                    "track_id": "track-visible",
                    "summary": "should not persist",
                    "active_buddy": "pm",
                },
            ),
            (
                "advance",
                {
                    "track_id": "track-visible",
                    "current_buddy": "dev",
                    "next_buddy": "test",
                    "active_buddy": "pm",
                },
            ),
            ("archive", {"track_id": "track-visible", "active_buddy": "pm"}),
        ):
            with self.subTest(action=action):
                response = self._dispatch(
                    action=action,
                    args=args,
                    instance_json=instance_json,
                    instance_id="inst-dev-example",
                    buddy="dev",
                )
                self._assert_lifecycle_rejection(response, action=f"track.{action}")
                self.assertEqual(self._tracks_snapshot(), before_tracks)
                self.assertEqual(self._tasks_snapshot(), before_tasks)

    def test_attach_and_detach_task_keep_task_track_backlinks_consistent(self) -> None:
        self._seed_track(track_id="track-link", title="Link Track", current_buddy="pm")
        self._seed_task(task_id="task-dev-owned", buddy="dev", title="Owned Dev Task")
        self._seed_task(task_id="task-pm-foreign", buddy="pm", title="Foreign PM Task")
        instance_json = self._instance_json(instance_id="inst-dev-example", buddy="dev")

        attached = self._dispatch(
            action="attach_task",
            args={"track_id": "track-link", "task_id": "task-dev-owned"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(attached.get("ok"), msg=attached)
        self.assertEqual(attached.get("action"), "track.attach_task")
        linked_task = env_store.get_task("task-dev-owned")
        linked_track = env_store.get_track("track-link")
        self.assertIsNotNone(linked_task)
        self.assertIsNotNone(linked_track)
        assert linked_task is not None
        assert linked_track is not None
        self.assertEqual(linked_task["track_id"], "track-link")
        self.assertIn("task-dev-owned", linked_track["task_ids"])

        detached = self._dispatch(
            action="detach_task",
            args={"track_id": "track-link", "task_id": "task-dev-owned"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertTrue(detached.get("ok"), msg=detached)
        self.assertEqual(detached.get("action"), "track.detach_task")
        detached_task = env_store.get_task("task-dev-owned")
        detached_track = env_store.get_track("track-link")
        self.assertIsNotNone(detached_task)
        self.assertIsNotNone(detached_track)
        assert detached_task is not None
        assert detached_track is not None
        self.assertIsNone(detached_task["track_id"])
        self.assertNotIn("task-dev-owned", detached_track["task_ids"])

        before_tracks = copy.deepcopy(self._tracks_snapshot())
        before_tasks = copy.deepcopy(self._tasks_snapshot())
        foreign = self._dispatch(
            action="attach_task",
            args={"track_id": "track-link", "task_id": "task-pm-foreign"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertFalse(foreign.get("ok"), msg=foreign)
        self.assertEqual(foreign.get("permission_boundary"), "task.buddy_scope")
        self.assertEqual(self._tracks_snapshot(), before_tracks)
        self.assertEqual(self._tasks_snapshot(), before_tasks)

        missing_track = self._dispatch(
            action="attach_task",
            args={"track_id": "track-missing", "task_id": "task-dev-owned"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertFalse(missing_track.get("ok"), msg=missing_track)
        self.assertEqual(missing_track.get("permission_boundary"), "track.lookup")

        missing_task = self._dispatch(
            action="attach_task",
            args={"track_id": "track-link", "task_id": "task-missing"},
            instance_json=instance_json,
            instance_id="inst-dev-example",
            buddy="dev",
        )
        self.assertFalse(missing_task.get("ok"), msg=missing_task)
        self.assertEqual(missing_task.get("permission_boundary"), "task.lookup")

    def test_get_current_reads_active_instance_track_binding(self) -> None:
        self._seed_track(track_id="track-current", title="Current Track", current_buddy="pm")
        instance_json = self._instance_json(current_track_id="track-current")

        current = self._dispatch(action="get_current", args={}, instance_json=instance_json)

        self.assertTrue(current.get("ok"), msg=current)
        self.assertEqual(current.get("action"), "track.get_current")
        self.assertEqual(current.get("track_id"), "track-current")
        binding = current.get("current_binding")
        self.assertIsInstance(binding, dict, msg=current)
        assert isinstance(binding, dict)
        self.assertEqual(binding.get("current_track_id"), "track-current")
        track_payload = current.get("track")
        self.assertIsInstance(track_payload, dict, msg=current)
        assert isinstance(track_payload, dict)
        self.assertEqual(track_payload.get("id"), "track-current")

        unbound_instance_json = self._instance_json(instance_id="inst-pm-unbound")
        unbound = self._dispatch(
            action="get_current",
            args={},
            instance_json=unbound_instance_json,
            instance_id="inst-pm-unbound",
        )
        self.assertTrue(unbound.get("ok"), msg=unbound)
        self.assertIsNone(unbound.get("track"))

    def test_track_list_returns_discovery_summary_with_deterministic_candidate_order(self) -> None:
        self._seed_track(
            track_id="track-handoff-priority",
            title="Handoff Priority",
            current_buddy="pm",
            next_buddy="market",
            summary="recent PM handoff target",
        )
        self._seed_task(
            task_id="task-pm-handoff-priority",
            buddy="pm",
            title="PM Handoff Priority Task",
            track_id="track-handoff-priority",
        )
        self._write_handoff_run(
            run_id="run-handoff-priority-r1",
            task_id="task-pm-handoff-priority",
            track_id="track-handoff-priority",
            buddy_id="pm",
            next_buddy="market",
        )

        self._seed_track(
            track_id="track-next-only",
            title="Next Buddy Only",
            current_buddy="pm",
            next_buddy="market",
            summary="next-buddy match only",
        )
        self._seed_track(
            track_id="track-participant-only",
            title="Participant Only",
            current_buddy="pm",
            next_buddy="design",
            summary="market participates via one task",
        )
        self._seed_task(
            task_id="task-market-participant",
            buddy="market",
            title="Market Participant Task",
            track_id="track-participant-only",
        )
        self._seed_track(
            track_id="track-unrelated",
            title="Unrelated",
            current_buddy="pm",
            next_buddy="design",
            summary="no market relevance",
        )

        instance_json = self._instance_json(instance_id="inst-market-discovery", buddy="market")
        listed = self._dispatch(
            action="list",
            args={},
            instance_json=instance_json,
            instance_id="inst-market-discovery",
            buddy="market",
        )
        self.assertTrue(listed.get("ok"), msg=listed)
        discovery_summary = listed.get("discovery_summary")
        self.assertIsInstance(discovery_summary, dict, msg=listed)
        assert isinstance(discovery_summary, dict)
        candidate_ids = discovery_summary.get("candidate_track_ids")
        self.assertEqual(
            candidate_ids,
            ["track-handoff-priority", "track-next-only", "track-participant-only"],
        )
        rows = listed.get("tracks")
        self.assertIsInstance(rows, list, msg=listed)
        assert isinstance(rows, list)
        first = rows[0]
        self.assertIsInstance(first, dict, msg=listed)
        assert isinstance(first, dict)
        self.assertEqual(first.get("id"), "track-handoff-priority")
        discovery = first.get("discovery")
        self.assertIsInstance(discovery, dict, msg=listed)
        assert isinstance(discovery, dict)
        self.assertEqual(discovery.get("active_buddy_role"), "next_buddy")
        reasons = discovery.get("relevance_reasons")
        self.assertIsInstance(reasons, list, msg=listed)
        assert isinstance(reasons, list)
        self.assertIn("recent_handoff.next_buddy == active_buddy", reasons)
        self.assertIn("track.next_buddy == active_buddy", reasons)

    def test_track_get_returns_track_context_summary_without_foreign_full_artifact_content(self) -> None:
        self._seed_track(
            track_id="track-context-summary",
            title="Context Summary Track",
            current_buddy="pm",
            next_buddy="market",
            summary="context summary smoke",
        )
        self._seed_task(
            task_id="task-pm-context-summary",
            buddy="pm",
            title="PM Context Summary Task",
            track_id="track-context-summary",
        )
        self._seed_task(
            task_id="task-market-context-summary",
            buddy="market",
            title="Market Context Summary Task",
            track_id="track-context-summary",
        )
        env_store.create_artifact(
            artifact_id="art-pm-context-prd-r1",
            title="PM PRD",
            buddy="pm",
            kind="prd",
            task_id="task-pm-context-summary",
            source_run_id="run-pm-context-r1",
            summary="pm summary",
            content={"secret": "full pm content must not leak in track summary"},
        )
        self._write_handoff_run(
            run_id="run-pm-context-handoff-r2",
            task_id="task-pm-context-summary",
            track_id="track-context-summary",
            buddy_id="pm",
            next_buddy="market",
        )

        instance_json = self._instance_json(instance_id="inst-market-track-get", buddy="market")
        fetched = self._dispatch(
            action="get",
            args={"track_id": "track-context-summary"},
            instance_json=instance_json,
            instance_id="inst-market-track-get",
            buddy="market",
        )
        self.assertTrue(fetched.get("ok"), msg=fetched)
        summary = fetched.get("track_context_summary")
        self.assertIsInstance(summary, dict, msg=fetched)
        assert isinstance(summary, dict)
        tasks = summary.get("tasks")
        self.assertIsInstance(tasks, list, msg=fetched)
        assert isinstance(tasks, list)
        pm_row = next(row for row in tasks if isinstance(row, dict) and row.get("id") == "task-pm-context-summary")
        current_artifacts = pm_row.get("current_artifacts")
        self.assertIsInstance(current_artifacts, list, msg=fetched)
        assert isinstance(current_artifacts, list)
        self.assertGreaterEqual(len(current_artifacts), 1)
        art_row = current_artifacts[0]
        self.assertIsInstance(art_row, dict, msg=fetched)
        assert isinstance(art_row, dict)
        for key in ("id", "kind", "title", "summary", "source_buddy", "source_run", "revision", "currentness"):
            self.assertIn(key, art_row)
        self.assertNotIn("content", art_row)

    def test_invalid_buddy_refs_reject_without_partial_mutation(self) -> None:
        self._seed_track(track_id="track-refs", title="Ref Track", current_buddy="pm")
        instance_json = self._instance_json()
        before_tracks = copy.deepcopy(self._tracks_snapshot())

        for action, args in (
            (
                "create",
                {
                    "track_id": "track-invalid-current",
                    "title": "Invalid Current",
                    "current_buddy": "unknown",
                    "next_buddy": "market",
                },
            ),
            (
                "update",
                {
                    "track_id": "track-refs",
                    "current_buddy": "pm",
                    "next_buddy": "unknown",
                },
            ),
            (
                "advance",
                {
                    "track_id": "track-refs",
                    "current_buddy": "unknown",
                    "next_buddy": "design",
                },
            ),
        ):
            with self.subTest(action=action):
                response = self._dispatch(action=action, args=args, instance_json=instance_json)
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("permission_boundary"), "request-payload")
                self.assertEqual(self._tracks_snapshot(), before_tracks)

    def test_cli_prints_structured_json_for_track_commands(self) -> None:
        env = os.environ.copy()
        env.pop("BUDDYSWITCH_RUNTIME_BROKER_SOCKET", None)
        env.pop("BUDDYSWITCH_INSTANCE_ID", None)
        env.pop("BUDDYSWITCH_ACTIVE_BUDDY", None)

        unavailable = subprocess.run(
            ["python3", str(ENV_CLIENT), "track", "list"],
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
            ["python3", str(ENV_CLIENT), "track", "create", "--payload", str(ROOT / "tmp" / "missing-track.json")],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(missing_payload_file.returncode, 2)
        self.assertIn("payload file is not readable", missing_payload_file.stderr.lower())

    def test_live_broker_track_cli_uses_env_tool_and_returns_structured_rejection(self) -> None:
        self._seed_track(track_id="track-live", title="Live Track", current_buddy="pm")
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
                ["python3", str(ENV_CLIENT), "track", "archive", "--track-id", "track-live"],
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
        self.assertEqual(payload.get("tool"), "track")
        self.assertEqual(payload.get("action"), "track.archive")
        self.assertEqual(payload.get("permission_boundary"), "track.lifecycle_authority")
        self.assertEqual(env_store.get_track("track-live")["status"], "active")


if __name__ == "__main__":
    unittest.main()
