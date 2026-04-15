#!/usr/bin/env python3
"""Cleanup backend and shell wrapper regression tests."""

from __future__ import annotations

import json
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
            "runs/raw/market",
            "runs/raw/pm",
            "runs/summaries/market",
            "runs/summaries/pm",
            "projects/app/.runtime",
            "buddyswitch/objects/tracks",
            "buddyswitch/objects/tasks",
            "buddyswitch/objects/artifacts",
            "buddyswitch/content/runs",
        ):
            self._write_text(f"{relative_dir}/.gitkeep", "")

        self._write_text("artifacts/art-market--demo.md", "# Market artifact\n")
        self._write_text("artifacts/art-pm--demo.md", "# PM artifact\n")
        self._write_text("runs/raw/market/market.log", "market raw\n")
        self._write_text("runs/raw/pm/pm.log", "pm raw\n")
        self._write_text("runs/summaries/market/market.md", "market summary\n")
        self._write_text("runs/summaries/pm/pm.md", "pm summary\n")
        self._write_text("projects/app/.runtime/session.json", "{\"ok\":true}\n")

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
                "skill_id": "research-scan",
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
                "skill_id": "track-manager",
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
                "switch": {
                    "buddy": "market",
                    "demand": "research",
                    "task_id": "task-market",
                    "track_id": "track-demo",
                },
                "resolved_task_id": "task-market",
                "effective_track_id": "track-demo",
                "skill_id": "research-scan",
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
                "switch": {
                    "buddy": "pm",
                    "demand": "manage track",
                    "task_id": "task-pm",
                    "track_id": "track-demo",
                },
                "skill_id": "track-manager",
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

    def test_agent_plan_includes_run_content_and_scoped_warnings(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="agent",
            buddy="market",
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )

        self.assertEqual(plan["scope"], "agent")
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

    def test_agent_execute_detaches_track_and_preserves_other_buddy_files(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="agent",
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
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/.gitkeep"))

    def test_all_storage_execute_deletes_all_generated_state_and_restores_skeleton(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="all-storage",
            buddy=None,
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )

        self.assertIn("buddyswitch/content/runs/run-market.json", plan["delete_paths"])
        self.assertIn("projects/app/.runtime/session.json", plan["delete_paths"])
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
            "projects/app/.runtime/.gitkeep",
            "buddyswitch/objects/tracks/.gitkeep",
            "buddyswitch/objects/tasks/.gitkeep",
            "buddyswitch/objects/artifacts/.gitkeep",
            "buddyswitch/content/runs/.gitkeep",
        ):
            self.assertTrue(self.fixture.exists(marker))

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
                "skill_id": "write-prd",
                "slot": "prd",
                "revision": 1,
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
                "skill_id": "write-prd",
                "slot": "prd",
                "revision": 2,
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


class CleanupShellIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp_dir.cleanup)
        self.repo_root = Path(self.temp_dir.name)
        self.fixture = CleanupFixture(self.repo_root)
        scripts_dir = self.repo_root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for name in ("cleanup_buddyswitch.sh", "env_cleanup.py"):
            shutil.copy2(ROOT / "scripts" / name, scripts_dir / name)

    def run_cleanup(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "scripts/cleanup_buddyswitch.sh", *args],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_shell_agent_dry_run_reports_run_content(self) -> None:
        completed = self.run_cleanup("--agent", "market", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertIn("buddyswitch/content/runs/run-market.json", payload["delete_paths"])
        self.assertNotIn("buddyswitch/content/runs/run-pm.json", payload["delete_paths"])

    def test_shell_project_cleanup_only_touches_runtime(self) -> None:
        completed = self.run_cleanup("--project", "app", "--execute", "--force", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["result"]["scope"], "project")
        self.assertIn("projects/app/.runtime/session.json", payload["result"]["deleted_paths"])
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertFalse(self.fixture.exists("projects/app/.runtime/session.json"))
        self.assertTrue(self.fixture.exists("projects/app/.runtime/.gitkeep"))

    def test_shell_all_agents_cleanup_clears_buddy_state(self) -> None:
        completed = self.run_cleanup("--all-agents", "--execute", "--force", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["result"]["scope"], "all-agents")
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/bad-run.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/objects/tracks/track-demo.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/.gitkeep"))


if __name__ == "__main__":
    unittest.main()
