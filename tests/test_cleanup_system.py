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
permissions = ["artifact.read", "artifact.create", "artifact.update"]

[[buddies]]
id = "pm"
label = "PM"
scope = "PM scope"
skills = ["track-manager"]
permissions = ["track.read", "track.create", "track.update", "artifact.read", "artifact.delete"]
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
            "buddyswitch/objects/artifacts",
            "buddyswitch/content/artifacts",
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
                "artifact_ids": ["art-market", "art-pm"],
                "summary": "Demo track",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-market.json",
            {
                "id": "art-market",
                "title": "Market Artifact",
                "kind": "research",
                "path": "artifacts/art-market--demo.md",
                "content_path": "buddyswitch/content/artifacts/art-market.json",
                "summary_path": "runs/summaries/market/market.md",
                "producer_buddy": "market",
                "source_skill": "research-scan",
                "context_track_id": "track-demo",
                "created_at": "2026-04-11T10:00:00+08:00",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self._write_json(
            "buddyswitch/objects/artifacts/art-pm.json",
            {
                "id": "art-pm",
                "title": "PM Artifact",
                "kind": "spec",
                "path": "artifacts/art-pm--demo.md",
                "content_path": "buddyswitch/content/artifacts/art-pm.json",
                "summary_path": "runs/summaries/pm/pm.md",
                "producer_buddy": "pm",
                "source_skill": "track-manager",
                "context_track_id": "track-demo",
                "created_at": "2026-04-11T10:00:00+08:00",
                "updated_at": "2026-04-11T10:00:00+08:00",
            },
        )
        self._write_text("buddyswitch/objects/artifacts/bad-object.json", "{not-json}\n")

        self._write_json(
            "buddyswitch/content/artifacts/art-market.json",
            {"artifact_id": "art-market", "buddy": "market", "content": {"summary": "market"}},
        )
        self._write_json(
            "buddyswitch/content/artifacts/art-pm.json",
            {"artifact_id": "art-pm", "buddy": "pm", "content": {"summary": "pm"}},
        )
        self._write_json(
            "buddyswitch/content/artifacts/art-market-orphan.json",
            {"artifact_id": "art-market-orphan", "buddy": "market", "content": {"summary": "orphan"}},
        )
        self._write_text("buddyswitch/content/artifacts/bad-content.json", "{not-json}\n")

        self._write_json(
            "buddyswitch/content/runs/run-market.json",
            {
                "switch": {"buddy": "market", "task": "research"},
                "skill_id": "research-scan",
                "artifact_id": "art-market",
                "result": {"execution_summary": "market"},
            },
        )
        self._write_json(
            "buddyswitch/content/runs/run-pm.json",
            {
                "switch": {"buddy": "pm", "task": "manage track"},
                "skill_id": "track-manager",
                "result": {"execution_summary": "pm"},
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

    def test_agent_plan_includes_canonical_content_and_scoped_warnings(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="agent",
            buddy="market",
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )

        self.assertEqual(plan["scope"], "agent")
        self.assertEqual(plan["buddy"], "market")
        self.assertIn("art-market", plan["artifact_object_ids"])
        self.assertIn("run-market", plan["run_ids"])
        self.assertIn("buddyswitch/content/artifacts/art-market-orphan.json", plan["orphan_content_paths"])
        self.assertIn("artifacts/art-market--demo.md", plan["delete_paths"])
        self.assertIn("buddyswitch/content/artifacts/art-market.json", plan["delete_paths"])
        self.assertIn("buddyswitch/content/runs/run-market.json", plan["delete_paths"])
        self.assertNotIn("artifacts/art-pm--demo.md", plan["delete_paths"])
        self.assertNotIn("buddyswitch/content/runs/run-pm.json", plan["delete_paths"])
        self.assertTrue(any("bad-run.json" in warning for warning in plan["warnings"]))
        self.assertTrue(any("bad-content.json" in warning for warning in plan["warnings"]))
        self.assertTrue(any("bad-object.json" in warning for warning in plan["warnings"]))

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
        self.assertFalse(self.fixture.exists("artifacts/art-market--demo.md"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/artifacts/art-market.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/artifacts/art-market-orphan.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/objects/artifacts/art-pm.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/bad-run.json"))
        track = self.fixture.read_json("buddyswitch/objects/tracks/track-demo.json")
        self.assertEqual(track["artifact_ids"], ["art-pm"])
        self.assertTrue(self.fixture.exists("buddyswitch/content/artifacts/.gitkeep"))
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/.gitkeep"))

    def test_all_storage_execute_deletes_all_canonical_content_and_restores_skeleton(self) -> None:
        plan = env_cleanup.build_cleanup_plan(
            scope="all-storage",
            buddy=None,
            repo_root=self.repo_root,
            manifest_path=self.fixture.manifest_path,
        )

        self.assertIn("buddyswitch/content/runs/run-market.json", plan["delete_paths"])
        self.assertIn("buddyswitch/content/artifacts/art-market-orphan.json", plan["delete_paths"])
        self.assertIn("projects/app/.runtime/session.json", plan["delete_paths"])
        result = env_cleanup.execute_cleanup_plan(plan)

        self.assertTrue(result["ok"])
        for relative_path in (
            "buddyswitch/content/runs/run-market.json",
            "buddyswitch/content/runs/run-pm.json",
            "buddyswitch/content/runs/bad-run.json",
            "buddyswitch/content/artifacts/art-market.json",
            "buddyswitch/content/artifacts/art-pm.json",
            "buddyswitch/content/artifacts/art-market-orphan.json",
            "buddyswitch/content/artifacts/bad-content.json",
            "buddyswitch/objects/artifacts/art-market.json",
            "buddyswitch/objects/tracks/track-demo.json",
        ):
            self.assertFalse(self.fixture.exists(relative_path))
        for marker in (
            "artifacts/.gitkeep",
            "runs/raw/.gitkeep",
            "runs/summaries/.gitkeep",
            "projects/app/.runtime/.gitkeep",
            "buddyswitch/objects/tracks/.gitkeep",
            "buddyswitch/objects/artifacts/.gitkeep",
            "buddyswitch/content/artifacts/.gitkeep",
            "buddyswitch/content/runs/.gitkeep",
        ):
            self.assertTrue(self.fixture.exists(marker))


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

    def test_shell_agent_dry_run_reports_canonical_content(self) -> None:
        completed = self.run_cleanup("--agent", "market", "--json")
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertIn("buddyswitch/content/artifacts/art-market-orphan.json", payload["delete_paths"])
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
        self.assertFalse(self.fixture.exists("buddyswitch/content/artifacts/art-market.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/artifacts/art-pm.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/artifacts/art-market-orphan.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/objects/tracks/track-demo.json"))
        self.assertTrue(self.fixture.exists("buddyswitch/content/runs/.gitkeep"))


if __name__ == "__main__":
    unittest.main()
