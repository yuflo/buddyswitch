#!/usr/bin/env python3
"""Cleanup backend and shell wrapper regression tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_cleanup  # noqa: E402

RUNTIME_LOCK_BUSY_EXIT_CODE = 4
LOCK_TIMEOUT_SECONDS = "0.2"
LOCK_HOLDER_SCRIPT = """\
import fcntl
import os
import signal
import sys
import time

lock_path = sys.argv[1]
fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
print("locked", flush=True)

def _exit(*_args):
    raise SystemExit(0)

signal.signal(signal.SIGTERM, _exit)
signal.signal(signal.SIGINT, _exit)

while True:
    time.sleep(1)
"""


class CleanupFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest_path = self.root / "buddyswitch" / "manifest.toml"
        self._seed()

    def _write_text(self, relative_path: str, content: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_json(self, relative_path: str, payload: dict) -> None:
        self._write_text(relative_path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")

    def _seed(self) -> None:
        self._write_text(
            "buddyswitch/manifest.toml",
            """
schema_version = 1

[env]
id = "test"
label = "Test Env"

[[buddies]]
id = "market"
label = "Market"
scope = "Market scope"
skills = ["research-scan"]
permissions = ["task.read", "task.create", "task.update", "artifact.read", "artifact.create", "artifact.update"]

[[buddies]]
id = "pm"
label = "PM"
scope = "PM scope"
skills = ["track-manager"]
permissions = ["track.read", "track.create", "track.update", "task.read", "task.create", "task.update", "artifact.read", "artifact.delete"]
""".strip()
            + "\n",
        )

        for relative_dir in (
            "artifacts",
            "runs/summaries/market",
            "runs/summaries/pm",
        ):
            self._write_text(f"{relative_dir}/.gitkeep", "")

        self._write_text("artifacts/art-market--demo.md", "# Market artifact\n")
        self._write_text("artifacts/art-pm--demo.md", "# PM artifact\n")
        self._write_text("runs/raw/market/market.log", "market raw\n")
        self._write_text("runs/raw/pm/pm.log", "pm raw\n")
        self._write_text("runs/summaries/market/market.md", "market summary\n")
        self._write_text("runs/summaries/pm/pm.md", "pm summary\n")

        self._write_json(
            "buddyswitch/objects/tracks/track-demo.json",
            {
                "id": "track-demo",
                "title": "Demo Track",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": None,
                "task_ids": ["task-market", "task-pm"],
                "summary": "Demo track",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/tasks/task-market.json",
            {
                "id": "task-market",
                "title": "Market Task",
                "buddy": "market",
                "status": "active",
                "track_id": "track-demo",
                "run_ids": ["run-market"],
                "artifact_ids": ["art-market"],
                "artifact_slots": {
                    "market-scan": {
                        "current_artifact_id": "art-market",
                        "revision_count": 1,
                    }
                },
                "summary": "Market task",
                "created_at": "2026-04-11T10:00:00+08:00",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/tasks/task-pm.json",
            {
                "id": "task-pm",
                "title": "PM Task",
                "buddy": "pm",
                "status": "active",
                "track_id": "track-demo",
                "run_ids": ["run-pm"],
                "artifact_ids": ["art-pm"],
                "artifact_slots": {
                    "track-update": {
                        "current_artifact_id": "art-pm",
                        "revision_count": 1,
                    }
                },
                "summary": "PM task",
                "created_at": "2026-04-11T10:00:00+08:00",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-market.json",
            {
                "id": "art-market",
                "title": "Market Artifact",
                "task_id": "task-market",
                "source_run_id": "run-market",
                "buddy": "market",
                "kind": "market-scan",
                "revision": 1,
                "supersedes_artifact_id": None,
                "is_current": True,
                "summary": "Market summary",
                "content": {"summary": "market"},
                "created_at": "2026-04-11T10:00:00+08:00",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-pm.json",
            {
                "id": "art-pm",
                "title": "PM Artifact",
                "task_id": "task-pm",
                "source_run_id": "run-pm",
                "buddy": "pm",
                "kind": "track-update",
                "revision": 1,
                "supersedes_artifact_id": None,
                "is_current": True,
                "summary": "PM summary",
                "content": {"summary": "pm"},
                "created_at": "2026-04-11T10:00:00+08:00",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self._write_text("buddyswitch/objects/artifacts/bad-object.json", "{not-json}\n")
        self._write_text("buddyswitch/objects/tasks/bad-task.json", "{not-json}\n")

        self._write_json(
            "buddyswitch/content/runs/run-market.json",
            {
                "run_id": "run-market",
                "timestamp": "2026-04-11T10:00:00+08:00",
                "request_text": "research",
                "active_buddy": "market",
                "current_task_id": "task-market",
                "current_track_id": "track-demo",
                "resolved_task_id": "task-market",
                "effective_track_id": "track-demo",
                "artifact_ids": ["art-market"],
                "track_id": "track-demo",
                "paths": {
                    "artifacts": ["buddyswitch/objects/artifacts/art-market.json"],
                    "task": "buddyswitch/objects/tasks/task-market.json",
                    "track": "buddyswitch/objects/tracks/track-demo.json",
                    "run": "buddyswitch/content/runs/run-market.json",
                },
                "writes": [
                    "buddyswitch/objects/artifacts/art-market.json",
                    "buddyswitch/objects/tasks/task-market.json",
                    "buddyswitch/objects/tracks/track-demo.json",
                    "buddyswitch/content/runs/run-market.json",
                ],
                "execution_summary": "market",
            },
        )
        self._write_json(
            "buddyswitch/content/runs/run-pm.json",
            {
                "run_id": "run-pm",
                "timestamp": "2026-04-11T10:00:00+08:00",
                "request_text": "manage track",
                "active_buddy": "pm",
                "current_task_id": "task-pm",
                "current_track_id": "track-demo",
                "resolved_task_id": "task-pm",
                "effective_track_id": "track-demo",
                "artifact_ids": ["art-pm"],
                "track_action": "update",
                "track_id": "track-demo",
                "paths": {
                    "artifacts": ["buddyswitch/objects/artifacts/art-pm.json"],
                    "task": "buddyswitch/objects/tasks/task-pm.json",
                    "track": "buddyswitch/objects/tracks/track-demo.json",
                    "run": "buddyswitch/content/runs/run-pm.json",
                },
                "writes": [
                    "buddyswitch/objects/tasks/task-pm.json",
                    "buddyswitch/objects/tracks/track-demo.json",
                    "buddyswitch/content/runs/run-pm.json",
                ],
                "execution_summary": "pm",
            },
        )
        self._write_text("buddyswitch/content/runs/bad-run.json", "{not-json}\n")

    def read_json(self, relative_path: str) -> dict:
        return json.loads((self.root / relative_path).read_text(encoding="utf-8"))

    def exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).exists()


class CleanupBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp_dir.cleanup)
        self.repo_root = Path(self.temp_dir.name)
        self.fixture = CleanupFixture(self.repo_root)

    def test_backend_rejects_retired_scope_names(self) -> None:
        for scope, buddy in (("agent", "market"), ("all-agents", None), ("all-storage", None)):
            with self.subTest(scope=scope):
                with self.assertRaisesRegex(ValueError, "Unsupported cleanup scope"):
                    env_cleanup.build_cleanup_plan(
                        scope=scope,
                        buddy=buddy,
                        repo_root=self.repo_root,
                        manifest_path=self.fixture.manifest_path,
                    )

    def test_buddy_plan_includes_run_content_and_scoped_warnings(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="buddy",
            buddy="market",
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )

        self.assertEqual(plan["scope"], "buddy")
        self.assertEqual(plan["buddy"], "market")
        self.assertIn("art-market", plan["artifact_object_ids"])
        self.assertIn("task-market", plan["task_object_ids"])
        self.assertIn("run-market", plan["run_ids"])
        self.assertIn("buddyswitch/objects/artifacts/art-market.json", plan["delete_paths"])
        self.assertIn("buddyswitch/objects/tasks/task-market.json", plan["delete_paths"])
        self.assertIn("buddyswitch/content/runs/run-market.json", plan["delete_paths"])
        self.assertNotIn("artifacts/art-market--demo.md", plan["delete_paths"])
        self.assertNotIn("artifacts/art-pm--demo.md", plan["delete_paths"])
        self.assertNotIn("buddyswitch/objects/tasks/task-pm.json", plan["delete_paths"])
        self.assertNotIn("buddyswitch/content/runs/run-pm.json", plan["delete_paths"])
        self.assertTrue(any("bad-run.json" in warning for warning in plan["warnings"]))
        self.assertTrue(any("bad-object.json" in warning for warning in plan["warnings"]))
        self.assertTrue(any("bad-task.json" in warning for warning in plan["warnings"]))

    def test_buddy_execute_detaches_track_and_preserves_other_buddy_files(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="buddy",
            buddy="market",
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )
        result = env_cleanup.execute_cleanup_plan(plan)

        self.assertTrue(result["ok"])
        self.assertFalse(self.fixture.exists("buddyswitch/objects/artifacts/art-market.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/objects/tasks/task-market.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertTrue(self.fixture.exists("artifacts/art-market--demo.md"))
        self.assertTrue(self.fixture.exists("buddyswitch/objects/artifacts/art-pm.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/objects/tasks/task-pm.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/bad-run.json"))
        track = self.fixture.read_json("buddyswitch/objects/tracks/track-demo.json")
        self.assertEqual(track["task_ids"], ["task-pm"])
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/.gitkeep"))

    def test_all_data_execute_deletes_all_generated_state_and_restores_skeleton(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            buddy=None,
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )

        self.assertIn("buddyswitch/content/runs/run-market.json", plan["delete_paths"])
        self.assertIn("buddyswitch/objects/tasks/task-market.json", plan["delete_paths"])
        self.assertNotIn("artifacts/art-market--demo.md", plan["delete_paths"])
        self.assertNotIn("runs/summaries/market/market.md", plan["delete_paths"])
        result = env_cleanup.execute_cleanup_plan(plan)

        self.assertTrue(result["ok"])
        for relative_path in (
            "buddyswitch/content/runs/run-market.json",
            "buddyswitch/content/runs/run-pm.json",
            "buddyswitch/content/runs/bad-run.json",
            "buddyswitch/objects/artifacts/art-market.json",
            "buddyswitch/objects/tasks/task-market.json",
            "buddyswitch/objects/tracks/track-demo.json",
        ):
            self.assertFalse(self.fixture.exists(relative_path))
        self.assertTrue(self.fixture.exists("artifacts/art-market--demo.md"))
        self.assertTrue(self.fixture.exists("runs/summaries/market/market.md"))
        for marker in (
            "runs/raw/.gitkeep",
            "buddyswitch/objects/tracks/.gitkeep",
            "buddyswitch/objects/tasks/.gitkeep",
            "buddyswitch/objects/artifacts/.gitkeep",
            "buddyswitch/content/runs/.gitkeep",
        ):
            self.assertFalse(self.fixture.exists(marker))

    def test_detach_artifact_from_task_updates_artifact_slots_from_remaining_revisions(self) -> None:
        self.fixture._write_json(
            "buddyswitch/objects/tasks/task-keep.json",
            {
                "id": "task-keep",
                "title": "Keep Task",
                "buddy": "pm",
                "status": "active",
                "track_id": "track-demo",
                "run_ids": ["run-keep"],
                "artifact_ids": ["art-keep-r1", "art-keep-r2"],
                "artifact_slots": {
                    "prd": {
                        "current_artifact_id": "art-keep-r2",
                        "revision_count": 2,
                    }
                },
                "summary": "Task with retained history",
                "created_at": "2026-04-11T10:00:00+08:00",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self.fixture._write_json(
            "buddyswitch/objects/artifacts/art-keep-r1.json",
            {
                "id": "art-keep-r1",
                "title": "Keep Artifact r1",
                "task_id": "task-keep",
                "source_run_id": "run-keep-r1",
                "buddy": "pm",
                "kind": "prd",
                "revision": 1,
                "supersedes_artifact_id": None,
                "is_current": False,
                "summary": "Older PRD",
                "content": {"summary": "old"},
                "created_at": "2026-04-11T10:00:00+08:00",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self.fixture._write_json(
            "buddyswitch/objects/artifacts/art-keep-r2.json",
            {
                "id": "art-keep-r2",
                "title": "Keep Artifact r2",
                "task_id": "task-keep",
                "source_run_id": "run-keep-r2",
                "buddy": "pm",
                "kind": "prd",
                "revision": 2,
                "supersedes_artifact_id": "art-keep-r1",
                "is_current": True,
                "summary": "Current PRD",
                "content": {"summary": "new"},
                "created_at": "2026-04-11T10:00:00+08:00",
                "updated_at": "2026-04-11T11:00:00+08:00",
            },
        )

        env_cleanup.detach_artifact_from_task(self.repo_root, "task-keep", "art-keep-r2")

        task = self.fixture.read_json("buddyswitch/objects/tasks/task-keep.json")
        artifact = self.fixture.read_json("buddyswitch/objects/artifacts/art-keep-r1.json")

        self.assertEqual(task["artifact_ids"], ["art-keep-r1"])
        self.assertEqual(
            task["artifact_slots"]["prd"],
            {
                "current_artifact_id": "art-keep-r1",
                "revision_count": 2,
            },
        )
        self.assertTrue(artifact["is_current"])

    def test_buddy_cleanup_skips_symlinked_index_roots(self) -> None:
        outside_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(outside_dir.cleanup)
        outside_root = Path(outside_dir.name)

        outside_tasks = outside_root / "tasks"
        outside_artifacts = outside_root / "artifacts"
        outside_runs = outside_root / "runs"
        outside_tasks.mkdir(parents=True, exist_ok=True)
        outside_artifacts.mkdir(parents=True, exist_ok=True)
        outside_runs.mkdir(parents=True, exist_ok=True)

        outside_task_path = outside_tasks / "task-market.json"
        outside_task_path.write_text(
            json.dumps(
                {
                    "id": "task-market",
                    "buddy": "market",
                    "track_id": "track-demo",
                    "artifact_ids": ["art-market"],
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        outside_artifact_path = outside_artifacts / "art-market.json"
        outside_artifact_path.write_text(
            json.dumps(
                {
                    "id": "art-market",
                    "buddy": "market",
                    "task_id": "task-market",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        outside_run_path = outside_runs / "run-market.json"
        outside_run_path.write_text(
            json.dumps(
                {
                    "run_id": "run-market",
                    "active_buddy": "market",
                    "current_task_id": "task-market",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        for relative_path, external_dir in (
            ("buddyswitch/objects/tasks", outside_tasks),
            ("buddyswitch/objects/artifacts", outside_artifacts),
            ("buddyswitch/content/runs", outside_runs),
        ):
            internal_dir = self.repo_root / relative_path
            shutil.rmtree(internal_dir)
            internal_dir.symlink_to(external_dir, target_is_directory=True)

        plan = env_cleanup.build_cleanup_plan(
            scope="buddy",
            buddy="market",
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )

        self.assertNotIn("buddyswitch/objects/tasks/task-market.json", plan["delete_paths"])
        self.assertNotIn("buddyswitch/objects/artifacts/art-market.json", plan["delete_paths"])
        self.assertNotIn("buddyswitch/content/runs/run-market.json", plan["delete_paths"])

        result = env_cleanup.execute_cleanup_plan(plan)

        self.assertTrue(
            outside_task_path.exists(),
            "cleanup must not delete task objects through symlinked indexed roots",
        )
        self.assertTrue(
            outside_artifact_path.exists(),
            "cleanup must not delete artifact objects through symlinked indexed roots",
        )
        self.assertTrue(
            outside_run_path.exists(),
            "cleanup must not delete run content through symlinked indexed roots",
        )
        self.assertNotIn("buddyswitch/objects/tasks/task-market.json", result["deleted_paths"])
        self.assertNotIn("buddyswitch/objects/artifacts/art-market.json", result["deleted_paths"])
        self.assertNotIn("buddyswitch/content/runs/run-market.json", result["deleted_paths"])

    def test_buddy_cleanup_skips_unsafe_detach_when_tasks_root_is_symlinked(self) -> None:
        outside_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(outside_dir.cleanup)
        outside_root = Path(outside_dir.name)

        outside_tasks = outside_root / "tasks"
        outside_tasks.mkdir(parents=True, exist_ok=True)
        outside_task_path = outside_tasks / "task-market.json"
        outside_task_payload = {
            "id": "task-market",
            "title": "External Market Task",
            "buddy": "market",
            "track_id": "track-demo",
            "artifact_ids": ["art-market"],
            "artifact_slots": {
                "market-scan": {
                    "current_artifact_id": "art-market",
                    "revision_count": 1,
                }
            },
        }
        outside_task_path.write_text(
            json.dumps(outside_task_payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

        internal_tasks_dir = self.repo_root / "buddyswitch" / "objects" / "tasks"
        shutil.rmtree(internal_tasks_dir)
        internal_tasks_dir.symlink_to(outside_tasks, target_is_directory=True)

        plan = env_cleanup.build_cleanup_plan(
            scope="buddy",
            buddy="market",
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )
        self.assertIn("buddyswitch/objects/artifacts/art-market.json", plan["delete_paths"])
        self.assertNotIn("buddyswitch/objects/tasks/task-market.json", plan["delete_paths"])

        original_task_json = outside_task_path.read_text(encoding="utf-8")
        env_cleanup.execute_cleanup_plan(plan)

        self.assertEqual(
            outside_task_path.read_text(encoding="utf-8"),
            original_task_json,
            "cleanup must not detach artifacts by mutating task JSON through a symlinked tasks root",
        )

    def test_buddy_cleanup_skips_unsafe_detach_when_tracks_root_is_symlinked(self) -> None:
        outside_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(outside_dir.cleanup)
        outside_root = Path(outside_dir.name)

        outside_tracks = outside_root / "tracks"
        outside_tracks.mkdir(parents=True, exist_ok=True)
        outside_track_path = outside_tracks / "track-demo.json"
        outside_track_payload = {
            "id": "track-demo",
            "title": "External Track",
            "status": "active",
            "task_ids": ["task-market", "task-pm"],
        }
        outside_track_path.write_text(
            json.dumps(outside_track_payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

        internal_tracks_dir = self.repo_root / "buddyswitch" / "objects" / "tracks"
        shutil.rmtree(internal_tracks_dir)
        internal_tracks_dir.symlink_to(outside_tracks, target_is_directory=True)

        plan = env_cleanup.build_cleanup_plan(
            scope="buddy",
            buddy="market",
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )
        self.assertIn("buddyswitch/objects/tasks/task-market.json", plan["delete_paths"])

        original_track_json = outside_track_path.read_text(encoding="utf-8")
        env_cleanup.execute_cleanup_plan(plan)

        self.assertEqual(
            outside_track_path.read_text(encoding="utf-8"),
            original_track_json,
            "cleanup must not detach tasks by mutating track JSON through a symlinked tracks root",
        )

    def test_all_data_cleanup_does_not_recreate_skeleton_through_symlinked_parents(self) -> None:
        outside_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(outside_dir.cleanup)
        outside_root = Path(outside_dir.name)

        outside_runs_parent = outside_root / "outside-runs"
        outside_objects_parent = outside_root / "outside-objects"
        outside_runs_parent.mkdir(parents=True, exist_ok=True)
        outside_objects_parent.mkdir(parents=True, exist_ok=True)

        internal_runs_parent = self.repo_root / "runs"
        shutil.rmtree(internal_runs_parent)
        internal_runs_parent.symlink_to(outside_runs_parent, target_is_directory=True)

        internal_objects_parent = self.repo_root / "buddyswitch" / "objects"
        shutil.rmtree(internal_objects_parent)
        internal_objects_parent.symlink_to(outside_objects_parent, target_is_directory=True)

        plan = env_cleanup.build_cleanup_plan(
            scope="all-data",
            buddy=None,
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )
        env_cleanup.execute_cleanup_plan(plan)

        self.assertFalse(
            (outside_runs_parent / "raw").exists(),
            "cleanup must not recreate runs/raw through a symlinked runs parent",
        )
        self.assertFalse(
            (outside_objects_parent / "tracks").exists(),
            "cleanup must not recreate tracks skeleton through a symlinked objects parent",
        )
        self.assertFalse(
            (outside_objects_parent / "tasks").exists(),
            "cleanup must not recreate tasks skeleton through a symlinked objects parent",
        )
        self.assertFalse(
            (outside_objects_parent / "artifacts").exists(),
            "cleanup must not recreate artifacts skeleton through a symlinked objects parent",
        )

    def test_cli_rejects_symlinked_repo_root_for_shared_state_cleanup(self) -> None:
        shared_root = self.repo_root / ".codex-buddyswitch"
        shared_root.mkdir(parents=True, exist_ok=True)
        outside_state_root = self.repo_root / "outside-state"
        CleanupFixture(outside_state_root)
        outside_raw_log = outside_state_root / "runs" / "raw" / "market" / "market.log"

        state_link = shared_root / "state"
        state_link.symlink_to(outside_state_root, target_is_directory=True)

        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "env_cleanup.py"),
                "--repo-root",
                str(state_link),
                "--shared-root",
                str(shared_root),
                "--manifest",
                str(self.fixture.manifest_path),
                "--all-data",
                "--yes",
                "--json",
            ],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(
            "repo root" in completed.stderr.lower() and "symlink" in completed.stderr.lower(),
            "symlinked --repo-root must be rejected before cleanup planning",
        )
        self.assertTrue(outside_raw_log.exists(), "cleanup must not delete data through symlinked state roots")


class CleanupShellIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp_dir.cleanup)
        self.repo_root = Path(self.temp_dir.name)
        self.fixture = CleanupFixture(self.repo_root)
        self.shared_root = self.repo_root / ".codex-buddyswitch"
        self.state_root = self.shared_root / "state"
        self.state_fixture = CleanupFixture(self.state_root)
        self.workspace_dir = self.shared_root / "workspace"
        self.workspace_fixture = CleanupFixture(self.workspace_dir)
        shutil.copy2(ROOT / "buddyswitch-codex", self.repo_root / "buddyswitch-codex")
        scripts_dir = self.repo_root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for name in ("env_cleanup.py",):
            shutil.copy2(ROOT / "scripts" / name, scripts_dir / name)
        launcher_dir = self.repo_root / "tools" / "launcher"
        launcher_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "env.sh",
            "workspace.sh",
            "runtime_lock.py",
            "browser_cockpit.sh",
            "instance.sh",
            "cleanup.sh",
            "runtime_broker.sh",
        ):
            shutil.copy2(ROOT / "tools" / "launcher" / name, launcher_dir / name)

    def run_cleanup(self, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["BUDDYSWITCH_SHARED_ROOT"] = str(self.shared_root)
        env["BUDDYSWITCH_REPO_ROOT"] = str(self.repo_root)
        env["BUDDYSWITCH_BROWSER_PORT"] = "1"
        env["REPO_ROOT"] = str(self.repo_root)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", "./buddyswitch-codex", "data", "cleanup", *args],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            env=env,
            text=True,
        )

    def _create_instance_workspace(self, instance_id: str, buddy: str) -> tuple[Path, Path]:
        instance_root = self.shared_root / "instances" / instance_id
        workspace_dir = instance_root / "workspace"
        instance_root.mkdir(parents=True, exist_ok=True)
        (workspace_dir / "runs" / "raw" / buddy).mkdir(parents=True, exist_ok=True)
        (workspace_dir / "runs" / "raw" / buddy / f"{buddy}.log").write_text("instance raw\n", encoding="utf-8")
        (instance_root / "instance.json").write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": "inactive",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(workspace_dir),
                    "browser_port": None,
                    "created_at": "2026-04-24T00:00:00Z",
                    "updated_at": "2026-04-24T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_root, workspace_dir

    def _spawn_lock_holder(self, lock_path: Path) -> subprocess.Popen[str]:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        holder = subprocess.Popen(
            [sys.executable, "-c", LOCK_HOLDER_SCRIPT, str(lock_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertIsNotNone(holder.stdout, "expected lock holder stdout pipe")
        ready = holder.stdout.readline().strip()
        if ready != "locked":
            stderr = holder.stderr.read() if holder.stderr is not None else ""
            holder.kill()
            holder.wait(timeout=5)
            self.fail(f"failed to acquire test runtime lock\nstdout:\n{ready}\nstderr:\n{stderr}")
        return holder

    def _stop_lock_holder(self, holder: subprocess.Popen[str]) -> None:
        if holder.poll() is None:
            holder.terminate()
            try:
                holder.wait(timeout=5)
            except subprocess.TimeoutExpired:
                holder.kill()
                holder.wait(timeout=5)

    def test_shell_agent_dry_run_reports_run_content(self) -> None:
        self._create_instance_workspace("inst-market-a", "market")
        self._create_instance_workspace("inst-pm-a", "pm")

        completed = self.run_cleanup("--buddy", "market", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertIn("buddyswitch/content/runs/run-market.json", payload["delete_paths"])
        self.assertNotIn("buddyswitch/content/runs/run-pm.json", payload["delete_paths"])
        self.assertIn("instances/inst-market-a/workspace/runs/raw/market/market.log", payload["delete_paths"])
        self.assertNotIn("instances/inst-pm-a/workspace/runs/raw/pm/pm.log", payload["delete_paths"])
        self.assertEqual(payload["repo_root"], str(self.state_root))

    def test_shell_agent_dry_run_without_common_args_prints_human_plan(self) -> None:
        completed = self.run_cleanup("--buddy", "market")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("BuddySwitch cleanup plan", completed.stdout)
        self.assertIn(f"Repo root: {self.state_root}", completed.stdout)
        self.assertIn("buddyswitch/content/runs/run-market.json", completed.stdout)

    def test_legacy_cleanup_script_is_removed(self) -> None:
        self.assertFalse((self.repo_root / "scripts" / "cleanup_buddyswitch.sh").exists())

    def test_shell_cleanup_rejects_removed_public_options(self) -> None:
        for option in ("--execute", "--force", "--agent", "--all-agents", "--project", "--all-storage"):
            with self.subTest(option=option):
                completed = self.run_cleanup(option)
                self.assertEqual(completed.returncode, 2)
                self.assertIn("Removed data cleanup option", completed.stderr)

    def test_shell_cleanup_rejects_removed_app_runtime_target(self) -> None:
        completed = self.run_cleanup("--app-runtime")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("Removed data cleanup option", completed.stderr)
        self.assertIn("--app-runtime", completed.stderr)
        self.assertIn("--buddy <buddy>", completed.stderr)
        self.assertIn("--all-data", completed.stderr)

    def test_shell_cleanup_uses_source_manifest_when_targeting_shared_state(self) -> None:
        (self.state_root / "buddyswitch" / "manifest.toml").unlink()

        completed = self.run_cleanup("--buddy", "market", "--json")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["repo_root"], str(self.state_root))
        self.assertIn("buddyswitch/content/runs/run-market.json", payload["delete_paths"])
        self.assertTrue(self.state_fixture.exists("buddyswitch/content/runs/run-market.json"))

    def test_shell_all_data_cleanup_clears_shared_and_instance_local_state(self) -> None:
        _, market_workspace = self._create_instance_workspace("inst-market-all", "market")
        _, pm_workspace = self._create_instance_workspace("inst-pm-all", "pm")

        completed = self.run_cleanup("--all-data", "--yes", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["result"]["scope"], "all-data")
        self.assertFalse(self.state_fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertFalse(self.state_fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertFalse(self.state_fixture.exists("buddyswitch/content/runs/bad-run.json"))
        self.assertFalse(self.state_fixture.exists("buddyswitch/objects/tracks/track-demo.json"))
        self.assertFalse((market_workspace / "runs" / "raw" / "market" / "market.log").exists())
        self.assertFalse((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())
        self.assertTrue((self.state_root / "buddyswitch" / "content" / "runs").is_dir())
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/run-market.json"))

    def test_shell_all_data_cleanup_keeps_shared_project_workspace(self) -> None:
        sentinel_path = self.shared_root / "project" / "workspace" / "projects" / "app" / "product-source-sentinel.txt"
        sentinel_path.parent.mkdir(parents=True, exist_ok=True)
        sentinel_path.write_text("keep\n", encoding="utf-8")
        framework_residue_path = self.shared_root / "project" / "workspace" / "tools" / "launcher" / "should-not-exist.txt"
        self.assertFalse(framework_residue_path.exists())

        completed = self.run_cleanup("--all-data", "--yes", "--json")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(sentinel_path.exists())
        self.assertNotIn(
            "project/workspace/projects/app/product-source-sentinel.txt",
            payload["result"]["deleted_paths"],
        )
        self.assertFalse(
            any(path.startswith("project/workspace/projects/app/") for path in payload["result"]["deleted_paths"]),
            "all-data cleanup must not delete shared project source paths",
        )

    def test_shell_agent_cleanup_targets_shared_state_not_legacy_workspace_or_source_checkout(self) -> None:
        completed = self.run_cleanup(
            "--buddy",
            "market",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["plan"]["repo_root"], str(self.state_root))
        self.assertFalse(self.state_fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertTrue(self.workspace_fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/run-market.json"))

    def test_shell_all_data_keeps_shared_root_and_instance_roots(self) -> None:
        market_root, market_workspace = self._create_instance_workspace("inst-market-keep", "market")
        pm_root, pm_workspace = self._create_instance_workspace("inst-pm-keep", "pm")

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertTrue(self.shared_root.exists())
        self.assertTrue((self.shared_root / "instances").is_dir())
        self.assertTrue(market_root.is_dir())
        self.assertTrue(pm_root.is_dir())
        self.assertTrue((market_root / "instance.json").is_file())
        self.assertTrue((pm_root / "instance.json").is_file())
        self.assertFalse((market_workspace / "runs" / "raw" / "market" / "market.log").exists())
        self.assertFalse((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_all_data_dry_run_does_not_mutate_source_checkout_or_excludes(self) -> None:
        exclude_path = self.repo_root / ".git" / "info" / "exclude"
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        exclude_path.write_text(
            "keep-this-line\n"
            "# BuddySwitch runtime-only excludes\n"
            "buddyswitch/content/runs/**\n"
            "buddyswitch/objects/tracks/**\n"
            "buddyswitch/objects/tasks/**\n"
            "buddyswitch/objects/artifacts/**\n"
            "runs/raw/**\n"
            "legacy/runtime/path/**\n",
            encoding="utf-8",
        )
        before_exclude_bytes = exclude_path.read_bytes()

        source_run_path = self.repo_root / "buddyswitch" / "content" / "runs" / "source-dry-run.json"
        source_run_path.parent.mkdir(parents=True, exist_ok=True)
        source_run_path.write_text(
            json.dumps(
                {
                    "run_id": "source-dry-run",
                    "active_buddy": "market",
                    "current_task_id": "task-market",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        source_runtime_path = self.repo_root / "projects" / "app" / ".runtime" / "source-dry-run-session.json"
        source_runtime_path.parent.mkdir(parents=True, exist_ok=True)
        source_runtime_path.write_text("{\"ok\":true}\n", encoding="utf-8")
        self.assertTrue(source_run_path.exists(), "precondition: source run fixture exists")
        self.assertTrue(source_runtime_path.exists(), "precondition: source runtime fixture exists")

        completed = self.run_cleanup(
            "--all-data",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertTrue(source_run_path.exists())
        self.assertTrue(source_runtime_path.exists())
        self.assertEqual(before_exclude_bytes, exclude_path.read_bytes())

    def test_shell_cleanup_is_blocked_when_runtime_lock_is_held(self) -> None:
        lock_path = self.shared_root / "run" / "locks" / "runtime.lock"
        state_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        holder = self._spawn_lock_holder(lock_path)
        try:
            completed = self.run_cleanup(
                "--all-data",
                "--yes",
                "--json",
                extra_env={"BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS": LOCK_TIMEOUT_SECONDS},
            )
        finally:
            self._stop_lock_holder(holder)

        self.assertEqual(completed.returncode, RUNTIME_LOCK_BUSY_EXIT_CODE)
        self.assertIn("runtime state busy", completed.stderr)
        self.assertTrue(
            self.state_fixture.exists(state_run_path),
            "cleanup must not mutate runtime state while lock is held",
        )

    def test_shell_cleanup_is_blocked_when_active_launcher_marker_exists(self) -> None:
        run_dir = self.shared_root / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "launcher-current.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
        state_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active buddyswitch-codex instance", completed.stderr)
        self.assertTrue(
            self.state_fixture.exists(state_run_path),
            "cleanup must not mutate runtime state while a launcher is active",
        )

    def test_shell_buddy_cleanup_blocks_unattributed_active_launcher_marker(self) -> None:
        _, pm_workspace = self._create_instance_workspace("inst-pm-legacy-active-cleanup", "pm")
        run_dir = self.shared_root / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "launcher-current.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
        state_run_path = "buddyswitch/content/runs/run-pm.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active buddyswitch-codex instance", completed.stderr)
        self.assertTrue(self.state_fixture.exists(state_run_path))
        self.assertTrue((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_buddy_cleanup_allows_other_buddy_active_launcher(self) -> None:
        _, pm_workspace = self._create_instance_workspace("inst-pm-cleanup", "pm")
        run_dir = self.shared_root / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "launcher-market.json").write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "instance_id": "inst-market-active",
                    "buddy": "market",
                    "workspace_dir": str(self.shared_root / "instances" / "inst-market-active" / "workspace"),
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["result"]["scope"], "buddy")
        self.assertIn(
            "instances/inst-pm-cleanup/workspace/runs/raw/pm/pm.log",
            payload["result"]["deleted_paths"],
        )
        self.assertFalse(self.state_fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertFalse((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_buddy_cleanup_blocks_same_buddy_active_launcher(self) -> None:
        _, pm_workspace = self._create_instance_workspace("inst-pm-active-cleanup", "pm")
        run_dir = self.shared_root / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "launcher-pm.json").write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "instance_id": "inst-pm-active-cleanup",
                    "buddy": "pm",
                    "workspace_dir": str(pm_workspace),
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        state_run_path = "buddyswitch/content/runs/run-pm.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active buddyswitch-codex instance", completed.stderr)
        self.assertTrue(self.state_fixture.exists(state_run_path))
        self.assertTrue((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_cleanup_is_blocked_when_active_browser_marker_exists(self) -> None:
        browser_marker = self.shared_root / "instances" / "inst-market-active" / "browser" / "chrome.pid"
        browser_marker.parent.mkdir(parents=True, exist_ok=True)
        browser_marker.write_text(f"{os.getpid()}\n", encoding="utf-8")
        state_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active browser", completed.stderr)
        self.assertTrue(
            self.state_fixture.exists(state_run_path),
            "cleanup must not mutate runtime state while a browser is active",
        )

    def test_shell_buddy_cleanup_blocks_shared_browser_marker(self) -> None:
        _, pm_workspace = self._create_instance_workspace("inst-pm-shared-browser-cleanup", "pm")
        browser_marker = self.shared_root / "run" / "browser-cockpit.pid"
        browser_marker.parent.mkdir(parents=True, exist_ok=True)
        browser_marker.write_text(f"{os.getpid()}\n", encoding="utf-8")
        state_run_path = "buddyswitch/content/runs/run-pm.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active browser", completed.stderr)
        self.assertTrue(self.state_fixture.exists(state_run_path))
        self.assertTrue((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_buddy_cleanup_allows_other_buddy_active_browser_marker(self) -> None:
        _, pm_workspace = self._create_instance_workspace("inst-pm-browser-cleanup", "pm")
        market_root, _ = self._create_instance_workspace("inst-market-browser-active", "market")
        browser_marker = market_root / "browser" / "chrome.pid"
        browser_marker.parent.mkdir(parents=True, exist_ok=True)
        browser_marker.write_text(f"{os.getpid()}\n", encoding="utf-8")

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["result"]["scope"], "buddy")
        self.assertIn(
            "instances/inst-pm-browser-cleanup/workspace/runs/raw/pm/pm.log",
            payload["result"]["deleted_paths"],
        )
        self.assertFalse(self.state_fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertFalse((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_buddy_cleanup_blocks_same_buddy_active_browser_marker(self) -> None:
        pm_root, pm_workspace = self._create_instance_workspace("inst-pm-browser-active", "pm")
        browser_marker = pm_root / "browser" / "chrome.pid"
        browser_marker.parent.mkdir(parents=True, exist_ok=True)
        browser_marker.write_text(f"{os.getpid()}\n", encoding="utf-8")
        state_run_path = "buddyswitch/content/runs/run-pm.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup("--buddy", "pm", "--yes", "--json")

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active browser", completed.stderr)
        self.assertTrue(self.state_fixture.exists(state_run_path))
        self.assertTrue((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_cleanup_is_blocked_when_shared_browser_endpoint_is_active_without_marker(self) -> None:
        fake_bin = self.repo_root / "bin"
        fake_bin.mkdir(parents=True, exist_ok=True)
        fake_curl = fake_bin / "curl"
        fake_curl.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        fake_curl.chmod(0o755)

        state_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
            extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
        )

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active browser", completed.stderr)
        self.assertTrue(
            self.state_fixture.exists(state_run_path),
            "cleanup must not mutate runtime state while a browser endpoint is active",
        )

    def test_shell_buddy_cleanup_blocks_shared_browser_endpoint_without_marker(self) -> None:
        fake_bin = self.repo_root / "bin"
        fake_bin.mkdir(parents=True, exist_ok=True)
        fake_curl = fake_bin / "curl"
        fake_curl.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        fake_curl.chmod(0o755)
        _, pm_workspace = self._create_instance_workspace("inst-pm-shared-browser-endpoint-cleanup", "pm")
        state_run_path = "buddyswitch/content/runs/run-pm.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        completed = self.run_cleanup(
            "--buddy",
            "pm",
            "--yes",
            "--json",
            extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
        )

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active browser", completed.stderr)
        self.assertTrue(self.state_fixture.exists(state_run_path))
        self.assertTrue((pm_workspace / "runs" / "raw" / "pm" / "pm.log").exists())

    def test_shell_cleanup_ignores_stale_instance_browser_pid_without_endpoint(self) -> None:
        instance_id = "inst-market-stale"
        browser_marker = self.shared_root / "instances" / instance_id / "browser" / "chrome.pid"
        browser_marker.parent.mkdir(parents=True, exist_ok=True)
        browser_marker.write_text("999999\n", encoding="utf-8")
        (self.shared_root / "instances" / instance_id / "instance.json").write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": "market",
                    "status": "inactive",
                    "workspace_dir": str(self.shared_root / "instances" / instance_id / "workspace"),
                    "browser_port": 9333,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertFalse(browser_marker.exists(), "stale pid marker should be ignored and removed")

    def test_shell_all_data_cleanup_skips_unsafe_symlinked_instance_workspace(self) -> None:
        instance_id = "inst-market-unsafe"
        instance_root = self.shared_root / "instances" / instance_id
        unsafe_workspace = self.repo_root / "outside-instance-workspace"
        (unsafe_workspace / "runs" / "raw" / "market").mkdir(parents=True, exist_ok=True)
        (unsafe_workspace / "runs" / "raw" / "market" / "market.log").write_text("unsafe raw\n", encoding="utf-8")
        (unsafe_workspace / "projects" / "app" / ".runtime").mkdir(parents=True, exist_ok=True)
        (unsafe_workspace / "projects" / "app" / ".runtime" / "session.json").write_text(
            "{\"ok\":true}\n",
            encoding="utf-8",
        )

        instance_root.mkdir(parents=True, exist_ok=True)
        (instance_root / "workspace").symlink_to(unsafe_workspace, target_is_directory=True)
        (instance_root / "instance.json").write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "buddy": "market",
                    "status": "inactive",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(instance_root / "workspace"),
                    "browser_port": None,
                    "created_at": "2026-04-24T00:00:00Z",
                    "updated_at": "2026-04-24T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(
            any("symlink" in warning.lower() for warning in payload["result"]["warnings"]),
            "unsafe symlinked instance workspace should produce a warning",
        )
        self.assertTrue((unsafe_workspace / "runs" / "raw" / "market" / "market.log").exists())

    def test_shell_all_data_cleanup_skips_symlinked_instance_runs_raw_target_dir(self) -> None:
        instance_id = "inst-market-raw-symlink"
        _, workspace_dir = self._create_instance_workspace(instance_id, "market")
        unsafe_raw_root = self.repo_root / "outside-instance-runs-raw-target"
        (unsafe_raw_root / "market").mkdir(parents=True, exist_ok=True)
        unsafe_raw_file = unsafe_raw_root / "market" / "market.log"
        unsafe_raw_file.write_text("unsafe raw\n", encoding="utf-8")
        shutil.rmtree(workspace_dir / "runs" / "raw")
        (workspace_dir / "runs" / "raw").symlink_to(unsafe_raw_root, target_is_directory=True)

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(
            any("symlink" in warning.lower() for warning in payload["result"]["warnings"]),
            "symlinked instance runs/raw path should produce a warning",
        )
        self.assertTrue(unsafe_raw_file.exists(), "cleanup must not delete files through symlinked runs/raw targets")
        self.assertNotIn(
            f"instances/{instance_id}/workspace/runs/raw/market/market.log",
            payload["result"]["deleted_paths"],
        )

    def test_shell_all_data_cleanup_skips_symlinked_shared_state_runs_raw_target_dir(self) -> None:
        unsafe_raw_root = self.repo_root / "outside-shared-state-runs-raw-target"
        (unsafe_raw_root / "market").mkdir(parents=True, exist_ok=True)
        unsafe_raw_file = unsafe_raw_root / "market" / "market.log"
        unsafe_raw_file.write_text("unsafe shared raw\n", encoding="utf-8")
        shutil.rmtree(self.state_root / "runs" / "raw")
        (self.state_root / "runs" / "raw").symlink_to(unsafe_raw_root, target_is_directory=True)

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(
            any("symlink" in warning.lower() for warning in payload["result"]["warnings"]),
            "symlinked shared-state runs/raw path should produce a warning",
        )
        self.assertTrue(
            unsafe_raw_file.exists(),
            "cleanup must not delete files through symlinked shared-state runs/raw targets",
        )
        self.assertNotIn(
            "runs/raw/market/market.log",
            payload["result"]["deleted_paths"],
        )

    def test_shell_all_data_cleanup_rejects_symlinked_shared_root_arg(self) -> None:
        instance_id = "inst-market-shared-root-link"
        _, workspace_dir = self._create_instance_workspace(instance_id, "market")
        shared_root_link = self.repo_root / ".codex-buddyswitch-link"
        shared_root_link.symlink_to(self.shared_root, target_is_directory=True)
        stale_launcher_marker = self.shared_root / "run" / "launcher-999999.pid"
        stale_launcher_marker.parent.mkdir(parents=True, exist_ok=True)
        stale_launcher_marker.write_text("999999\n", encoding="utf-8")
        stale_browser_marker = self.shared_root / "instances" / "inst-stale-marker" / "browser" / "chrome.pid"
        stale_browser_marker.parent.mkdir(parents=True, exist_ok=True)
        stale_browser_marker.write_text("999999\n", encoding="utf-8")

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
            extra_env={"BUDDYSWITCH_SHARED_ROOT": str(shared_root_link)},
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(
            "shared root" in completed.stderr.lower() and "symlink" in completed.stderr.lower(),
            "symlinked --shared-root must be rejected before cleanup planning",
        )
        self.assertTrue(
            stale_launcher_marker.exists(),
            "cleanup must reject symlinked shared root before pruning stale launcher markers",
        )
        self.assertTrue(
            stale_browser_marker.exists(),
            "cleanup must reject symlinked shared root before pruning stale browser markers",
        )
        self.assertTrue(self.state_fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertTrue((workspace_dir / "runs" / "raw" / "market" / "market.log").exists())
        self.assertTrue((workspace_dir / "runs" / "raw").is_dir())

    def test_shell_all_data_cleanup_rejects_symlinked_state_root(self) -> None:
        outside_state_root = self.repo_root / "outside-state"
        CleanupFixture(outside_state_root)
        outside_raw_log = outside_state_root / "runs" / "raw" / "market" / "market.log"

        shutil.rmtree(self.state_root)
        self.state_root.symlink_to(outside_state_root, target_is_directory=True)

        completed = self.run_cleanup(
            "--all-data",
            "--yes",
            "--json",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(
            "repo root" in completed.stderr.lower() and "symlink" in completed.stderr.lower(),
            "symlinked shared-state root must be rejected before cleanup planning",
        )
        self.assertTrue(outside_raw_log.exists(), "cleanup must not delete files through symlinked state roots")

    def test_shell_locked_cleanup_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        state_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.state_fixture.exists(state_run_path), "precondition: shared-state run fixture exists")

        env = os.environ.copy()
        env["BUDDYSWITCH_SHARED_ROOT"] = str(self.shared_root)
        env["BUDDYSWITCH_REPO_ROOT"] = str(self.repo_root)
        env["BUDDYSWITCH_BROWSER_PORT"] = "1"
        env["REPO_ROOT"] = str(self.repo_root)
        completed = subprocess.run(
            ["bash", "./buddyswitch-codex", "__locked-cleanup", "--all-data", "--yes", "--json"],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            env=env,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("runtime lock required", completed.stderr)
        self.assertTrue(
            self.state_fixture.exists(state_run_path),
            "direct locked cleanup entrypoint must not mutate runtime state",
        )


if __name__ == "__main__":
    unittest.main()
