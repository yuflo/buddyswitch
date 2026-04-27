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
            "projects/app/.runtime",
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
                    "buddy_id": "market",
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
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/.gitkeep"))

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
        self.assertTrue(self.fixture.exists("projects/app/.runtime/.gitkeep"))
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
        self.shared_root = self.repo_root / ".codex-buddyswitch"
        self.workspace_dir = self.shared_root / "workspace"
        self.workspace_fixture = CleanupFixture(self.workspace_dir)
        shutil.copy2(ROOT / "buddyswitch-codex", self.repo_root / "buddyswitch-codex")
        scripts_dir = self.repo_root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        for name in ("cleanup_buddyswitch.sh", "env_cleanup.py"):
            shutil.copy2(ROOT / "scripts" / name, scripts_dir / name)
        launcher_dir = self.repo_root / "tools" / "launcher"
        launcher_dir.mkdir(parents=True, exist_ok=True)
        for name in ("env.sh", "workspace.sh", "runtime_lock.py", "browser_cockpit.sh", "instance.sh", "cleanup.sh"):
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
            ["bash", "./buddyswitch-codex", "cleanup", *args],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            env=env,
            text=True,
        )

    def run_cleanup_shim(
        self,
        *args: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["BUDDYSWITCH_SHARED_ROOT"] = str(self.shared_root)
        env["BUDDYSWITCH_REPO_ROOT"] = str(self.repo_root)
        env["BUDDYSWITCH_BROWSER_PORT"] = "1"
        env["REPO_ROOT"] = str(self.repo_root)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", "scripts/cleanup_buddyswitch.sh", *args],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            env=env,
            text=True,
        )

    def _spawn_lock_holder(self, lock_path: Path) -> subprocess.Popen[str]:
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
        completed = self.run_cleanup("--agent", "market", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertIn("buddyswitch/content/runs/run-market.json", payload["delete_paths"])
        self.assertNotIn("buddyswitch/content/runs/run-pm.json", payload["delete_paths"])
        self.assertEqual(payload["repo_root"], str(self.workspace_dir))

    def test_shell_agent_dry_run_without_common_args_prints_human_plan(self) -> None:
        completed = self.run_cleanup("--agent", "market")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("BuddySwitch cleanup plan", completed.stdout)
        self.assertIn("buddyswitch/content/runs/run-market.json", completed.stdout)

    def test_shell_cleanup_legacy_script_forwards_to_launcher_cleanup(self) -> None:
        completed = self.run_cleanup_shim("--agent", "market", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertIn("buddyswitch/content/runs/run-market.json", payload["delete_paths"])
        self.assertEqual(payload["repo_root"], str(self.workspace_dir))

    def test_shell_cleanup_uses_source_manifest_when_targeting_shared_state(self) -> None:
        state_root = self.shared_root / "state"
        state_fixture = CleanupFixture(state_root)
        (state_root / "buddyswitch" / "manifest.toml").unlink()

        completed = self.run_cleanup("--agent", "market", "--json")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["repo_root"], str(state_root))
        self.assertIn("buddyswitch/content/runs/run-market.json", payload["delete_paths"])
        self.assertTrue(state_fixture.exists("buddyswitch/content/runs/run-market.json"))

    def test_shell_project_cleanup_only_touches_runtime(self) -> None:
        completed = self.run_cleanup("--project", "app", "--execute", "--force", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["result"]["scope"], "project")
        self.assertIn("projects/app/.runtime/session.json", payload["result"]["deleted_paths"])
        self.assertTrue(self.workspace_fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertFalse(self.workspace_fixture.exists("projects/app/.runtime/session.json"))
        self.assertTrue((self.workspace_dir / "projects" / "app" / ".runtime").is_dir())
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/run-market.json"))

    def test_shell_all_agents_cleanup_clears_buddy_state(self) -> None:
        completed = self.run_cleanup("--all-agents", "--execute", "--force", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["result"]["scope"], "all-agents")
        self.assertFalse(self.workspace_fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertFalse(self.workspace_fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertFalse(self.workspace_fixture.exists("buddyswitch/content/runs/bad-run.json"))
        self.assertFalse(self.workspace_fixture.exists("buddyswitch/objects/tracks/track-demo.json"))
        self.assertTrue((self.workspace_dir / "buddyswitch" / "content" / "runs").is_dir())
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/run-market.json"))

    def test_shell_agent_cleanup_targets_launcher_workspace_not_source_checkout(self) -> None:
        completed = self.run_cleanup(
            "--agent",
            "market",
            "--execute",
            "--force",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["plan"]["repo_root"], str(self.workspace_dir))
        self.assertFalse(self.workspace_fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertTrue(self.workspace_fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/run-market.json"))

    def test_shell_all_storage_cleanup_migrates_source_checkout_legacy_state_and_excludes(self) -> None:
        exclude_path = self.repo_root / ".git" / "info" / "exclude"
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        exclude_path.write_text(
            "# BuddySwitch runtime-only excludes\n"
            "buddyswitch/content/runs/**\n"
            "buddyswitch/objects/tracks/**\n"
            "buddyswitch/objects/tasks/**\n"
            "buddyswitch/objects/artifacts/**\n"
            "runs/raw/**\n"
            "projects/app/.runtime/**\n",
            encoding="utf-8",
        )

        completed = self.run_cleanup(
            "--all-storage",
            "--execute",
            "--force",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertFalse(self.workspace_fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/objects/tracks/track-demo.json"))
        self.assertNotIn("BuddySwitch runtime-only excludes", exclude_path.read_text(encoding="utf-8"))

    def test_shell_all_storage_dry_run_does_not_mutate_source_checkout_or_excludes(self) -> None:
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
            "projects/app/.runtime/**\n",
            encoding="utf-8",
        )
        before_exclude_bytes = exclude_path.read_bytes()

        source_run_path = self.repo_root / "buddyswitch" / "content" / "runs" / "source-dry-run.json"
        source_run_path.parent.mkdir(parents=True, exist_ok=True)
        source_run_path.write_text(
            json.dumps(
                {
                    "run_id": "source-dry-run",
                    "switch": {"buddy_id": "market", "task_id": "task-market"},
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
            "--all-storage",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertTrue(source_run_path.exists())
        self.assertTrue(source_runtime_path.exists())
        self.assertEqual(before_exclude_bytes, exclude_path.read_bytes())

    def test_shell_cleanup_is_blocked_when_runtime_lock_is_held(self) -> None:
        lock_path = Path(f"{self.shared_root}.lock")
        workspace_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.workspace_fixture.exists(workspace_run_path), "precondition: workspace run fixture exists")

        holder = self._spawn_lock_holder(lock_path)
        try:
            completed = self.run_cleanup(
                "--all-agents",
                "--execute",
                "--force",
                "--json",
                extra_env={"BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS": LOCK_TIMEOUT_SECONDS},
            )
        finally:
            self._stop_lock_holder(holder)

        self.assertEqual(completed.returncode, RUNTIME_LOCK_BUSY_EXIT_CODE)
        self.assertIn("runtime state busy", completed.stderr)
        self.assertTrue(
            self.workspace_fixture.exists(workspace_run_path),
            "cleanup must not mutate runtime state while lock is held",
        )

    def test_shell_cleanup_is_blocked_when_active_launcher_marker_exists(self) -> None:
        run_dir = self.shared_root / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "launcher-current.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
        workspace_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.workspace_fixture.exists(workspace_run_path), "precondition: workspace run fixture exists")

        completed = self.run_cleanup(
            "--all-agents",
            "--execute",
            "--force",
            "--json",
        )

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active buddyswitch-codex instance", completed.stderr)
        self.assertTrue(
            self.workspace_fixture.exists(workspace_run_path),
            "cleanup must not mutate runtime state while a launcher is active",
        )

    def test_shell_cleanup_is_blocked_when_active_browser_marker_exists(self) -> None:
        browser_marker = self.shared_root / "instances" / "inst-market-active" / "browser" / "chrome.pid"
        browser_marker.parent.mkdir(parents=True, exist_ok=True)
        browser_marker.write_text(f"{os.getpid()}\n", encoding="utf-8")
        workspace_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.workspace_fixture.exists(workspace_run_path), "precondition: workspace run fixture exists")

        completed = self.run_cleanup(
            "--all-agents",
            "--execute",
            "--force",
            "--json",
        )

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active browser", completed.stderr)
        self.assertTrue(
            self.workspace_fixture.exists(workspace_run_path),
            "cleanup must not mutate runtime state while a browser is active",
        )

    def test_shell_cleanup_is_blocked_when_shared_browser_endpoint_is_active_without_marker(self) -> None:
        fake_bin = self.repo_root / "bin"
        fake_bin.mkdir(parents=True, exist_ok=True)
        fake_curl = fake_bin / "curl"
        fake_curl.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        fake_curl.chmod(0o755)

        workspace_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.workspace_fixture.exists(workspace_run_path), "precondition: workspace run fixture exists")

        completed = self.run_cleanup(
            "--all-agents",
            "--execute",
            "--force",
            "--json",
            extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
        )

        self.assertEqual(completed.returncode, 3)
        self.assertIn("active browser", completed.stderr)
        self.assertTrue(
            self.workspace_fixture.exists(workspace_run_path),
            "cleanup must not mutate runtime state while a browser endpoint is active",
        )

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
            "--all-agents",
            "--execute",
            "--force",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertFalse(browser_marker.exists(), "stale pid marker should be ignored and removed")

    def test_shell_all_storage_cleanup_handles_state_and_instances_without_legacy_workspace(self) -> None:
        shutil.rmtree(self.workspace_dir)

        state_root = self.shared_root / "state"
        state_fixture = CleanupFixture(state_root)
        instance_root = self.shared_root / "instances" / "inst-market-a"
        instance_workspace = instance_root / "workspace"
        instance_root.mkdir(parents=True, exist_ok=True)
        (instance_root / "instance.json").write_text(
            json.dumps(
                {
                    "instance_id": "inst-market-a",
                    "buddy": "market",
                    "status": "inactive",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(instance_workspace),
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
        worktree_registered = False
        try:
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(instance_workspace), "HEAD"],
                text=True,
                capture_output=True,
                check=True,
            )
            worktree_registered = True
        except subprocess.CalledProcessError:
            pass
        (instance_workspace / "runs" / "raw" / "market").mkdir(parents=True, exist_ok=True)
        (instance_workspace / "runs" / "raw" / "market" / "market.log").write_text(
            "instance raw\n",
            encoding="utf-8",
        )
        (instance_workspace / "projects" / "app" / ".runtime").mkdir(parents=True, exist_ok=True)
        (instance_workspace / "projects" / "app" / ".runtime" / "session.json").write_text(
            "{\"ok\":true}\n",
            encoding="utf-8",
        )

        try:
            completed = self.run_cleanup(
                "--all-storage",
                "--execute",
                "--force",
                "--json",
                extra_env={"REPO_ROOT": str(ROOT), "BUDDYSWITCH_REPO_ROOT": str(ROOT)},
            )
        finally:
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(instance_workspace)],
                text=True,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "prune"],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["plan"]["repo_root"], str(state_root))
        self.assertFalse(state_fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertFalse(state_fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertFalse((instance_workspace / "runs" / "raw" / "market" / "market.log").exists())
        self.assertFalse((instance_workspace / "projects" / "app" / ".runtime" / "session.json").exists())
        if worktree_registered:
            worktrees = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            self.assertNotIn(str(instance_workspace), worktrees)

    def test_shell_locked_cleanup_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        workspace_run_path = "buddyswitch/content/runs/run-market.json"
        self.assertTrue(self.workspace_fixture.exists(workspace_run_path), "precondition: workspace run fixture exists")

        env = os.environ.copy()
        env["BUDDYSWITCH_SHARED_ROOT"] = str(self.shared_root)
        env["BUDDYSWITCH_REPO_ROOT"] = str(self.repo_root)
        env["BUDDYSWITCH_BROWSER_PORT"] = "1"
        env["REPO_ROOT"] = str(self.repo_root)
        completed = subprocess.run(
            ["bash", "./buddyswitch-codex", "__locked-cleanup", "--all-agents", "--execute", "--force", "--json"],
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            env=env,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("runtime lock required", completed.stderr)
        self.assertTrue(
            self.workspace_fixture.exists(workspace_run_path),
            "direct locked cleanup entrypoint must not mutate runtime state",
        )


if __name__ == "__main__":
    unittest.main()
