#!/usr/bin/env python3
"""Clean runtime environment host-visible regression tests."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_HELPER = ROOT / "tools" / "launcher" / "workspace.sh"
CODEX_CONFIG = ROOT / "tools" / "launcher" / "codex_config.py"
PERMISSION_PROFILE = "buddyswitch-runtime"


class CleanRuntimeEnvironmentTests(unittest.TestCase):
    def _new_temp_root(self) -> Path:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        return Path(holder.name)

    def _git_remove_worktree(self, path: Path) -> None:
        subprocess.run(
            ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(path)],
            text=True,
            capture_output=True,
            check=False,
        )

    def _git_prune_worktrees(self) -> None:
        subprocess.run(
            ["git", "-C", str(ROOT), "worktree", "prune"],
            text=True,
            capture_output=True,
            check=False,
        )

    def _runtime_env(self, *, shared_root: Path, workspace_dir: Path, project_workspace_dir: Path, buddy: str) -> dict[str, str]:
        env = dict()
        env.update(
            {
                "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
                "BUDDYSWITCH_WORKSPACE_DIR": str(workspace_dir),
                "BUDDYSWITCH_PROJECT_WORKSPACE_DIR": str(project_workspace_dir),
                "BUDDYSWITCH_INSTANCE_ID": "inst-clean-runtime",
                "BUDDYSWITCH_ACTIVE_BUDDY": buddy,
                "BUDDYSWITCH_START_BUDDY": buddy,
                "BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE": str(
                    ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy / "AGENTS.md"
                ),
                "BUDDYSWITCH_REPO_ROOT": str(ROOT),
            }
        )
        return env

    def _prepare_runtime_workspace(self, *, buddy: str = "pm") -> tuple[Path, Path, Path]:
        temp_root = self._new_temp_root()
        shared_root = temp_root / "shared"
        workspace_dir = shared_root / "instances" / "inst-clean-runtime" / "workspace"
        project_workspace_dir = shared_root / "project" / "workspace"
        env = self._runtime_env(
            shared_root=shared_root,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
            buddy=buddy,
        )
        cmd = """
set -euo pipefail
source tools/launcher/workspace.sh
buddyswitch_workspace_ensure_project_worktree
buddyswitch_workspace_prepare_execution_worktree
buddyswitch_workspace_repair_runtime_projects_app_projection
"""
        completed = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, **env},
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.addCleanup(self._git_prune_worktrees)
        self.addCleanup(self._git_remove_worktree, workspace_dir)
        self.addCleanup(self._git_remove_worktree, project_workspace_dir)
        return shared_root, workspace_dir, project_workspace_dir

    def _run_cleanup(self, *, shared_root: Path, workspace_dir: Path, project_workspace_dir: Path, buddy: str) -> subprocess.CompletedProcess[str]:
        env = self._runtime_env(
            shared_root=shared_root,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
            buddy=buddy,
        )
        cmd = """
set -euo pipefail
source tools/launcher/workspace.sh
buddyswitch_workspace_cleanup_stale_state_projections
"""
        return subprocess.run(
            ["bash", "-lc", cmd],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, **env},
        )

    def test_fresh_runtime_workspace_is_clean_and_host_visible(self) -> None:
        shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(buddy="pm")

        self.assertFalse((workspace_dir / "buddyswitch" / "objects").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "objects").is_symlink())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "buddybox" / "pm").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "buddybox" / "pm").is_symlink())

        required = (
            "scripts/env/client.py",
            "scripts/runtime_kernel/broker.py",
            "scripts/turn_runtime.py",
            "buddyswitch/manifest.toml",
            "framework/contracts/pm.md",
        )
        for relative in required:
            self.assertTrue((workspace_dir / relative).exists(), msg=relative)

        self.assertEqual(
            (workspace_dir / "projects" / "app").resolve(strict=True),
            (project_workspace_dir / "projects" / "app").resolve(strict=True),
        )

    def test_host_exploration_commands_are_quiet_in_runtime_workspace(self) -> None:
        _, workspace_dir, _ = self._prepare_runtime_workspace(buddy="pm")
        checks = (
            ["rg", "--files"],
            ["rg", "-n", "context|buddybox|track", "."],
            ["git", "status", "--short", "--untracked-files=all", "--", "."],
        )
        for command in checks:
            with self.subTest(command=command):
                completed = subprocess.run(
                    command,
                    cwd=workspace_dir,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if command[:2] == ["rg", "-n"]:
                    self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
                else:
                    self.assertEqual(completed.returncode, 0, msg=completed.stderr)
                stderr_lower = completed.stderr.lower()
                self.assertNotIn("operation not permitted", stderr_lower)
                self.assertNotIn("permission denied", stderr_lower)
                self.assertNotIn("retry without sandbox", stderr_lower)

    def test_stale_projection_cleanup_is_data_safe(self) -> None:
        shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(buddy="pm")

        state_track = shared_root / "state" / "buddyswitch" / "objects" / "tracks" / "track-old.json"
        state_track.parent.mkdir(parents=True, exist_ok=True)
        state_track.write_text('{"id":"track-old","ok":true}\n', encoding="utf-8")

        stale_objects = workspace_dir / "buddyswitch" / "objects"
        stale_objects.parent.mkdir(parents=True, exist_ok=True)
        stale_objects.symlink_to(shared_root / "state" / "buddyswitch" / "objects", target_is_directory=True)

        cleanup = self._run_cleanup(
            shared_root=shared_root,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
            buddy="pm",
        )
        self.assertEqual(cleanup.returncode, 0, msg=cleanup.stderr)
        self.assertFalse(stale_objects.exists())
        self.assertTrue(state_track.exists())
        self.assertEqual(state_track.read_text(encoding="utf-8"), '{"id":"track-old","ok":true}\n')

    def test_stale_local_runtime_data_is_migrated_to_state_root(self) -> None:
        shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(buddy="pm")

        local_track = workspace_dir / "buddyswitch" / "objects" / "tracks" / "track-local.json"
        local_track.parent.mkdir(parents=True, exist_ok=True)
        local_track.write_text('{"id":"track-local","from":"workspace"}\n', encoding="utf-8")

        local_box = workspace_dir / "buddyswitch" / "local" / "buddybox" / "pm" / "coordination" / "a-log.md"
        local_box.parent.mkdir(parents=True, exist_ok=True)
        local_box.write_text("hello\n", encoding="utf-8")

        cleanup = self._run_cleanup(
            shared_root=shared_root,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
            buddy="pm",
        )
        self.assertEqual(cleanup.returncode, 0, msg=cleanup.stderr)

        migrated_track = shared_root / "state" / "buddyswitch" / "objects" / "tracks" / "track-local.json"
        migrated_box = shared_root / "state" / "buddyswitch" / "local" / "buddybox" / "pm" / "coordination" / "a-log.md"
        self.assertTrue(migrated_track.exists())
        self.assertEqual(migrated_track.read_text(encoding="utf-8"), '{"id":"track-local","from":"workspace"}\n')
        self.assertTrue(migrated_box.exists())
        self.assertEqual(migrated_box.read_text(encoding="utf-8"), "hello\n")

        self.assertFalse((workspace_dir / "buddyswitch" / "objects").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "buddybox" / "pm").exists())

    def test_no_prompt_side_command_blacklist_workaround_text(self) -> None:
        completed = subprocess.run(
            [
                "rg",
                "-n",
                "do not run rg|exclude buddyswitch/objects|retry without sandbox|always use rg --glob|command blacklist|phrase-to-tool",
                "tools/launcher/assets/buddies",
                "buddyswitch/skills",
                "scripts",
                "-g",
                "!tests/**",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "", msg=completed.stdout)

    def test_codex_sandbox_smoke_for_runtime_workspace(self) -> None:
        if platform.system() != "Darwin":
            self.skipTest("codex macos sandbox smoke only runs on macOS")
        if shutil.which("codex") is None:
            self.skipTest("codex CLI not available")

        shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(buddy="pm")
        instance_root = shared_root / "instances" / "inst-clean-runtime"
        codex_home = instance_root / "codex-home"
        config_path = codex_home / "config.toml"
        patch = subprocess.run(
            [
                "python3",
                str(CODEX_CONFIG),
                "--config",
                str(config_path),
                "--repo-root",
                str(ROOT),
                "--shared-root",
                str(shared_root),
                "--source-codex-home",
                str(shared_root / "source-codex-home"),
                "--buddy",
                "pm",
                "--instance-root",
                str(instance_root),
                "--workspace-dir",
                str(workspace_dir),
                "--project-workspace-dir",
                str(project_workspace_dir),
                "--home",
                str(instance_root / "home"),
                "--codex-home",
                str(codex_home),
                "--xdg-config-home",
                str(instance_root / "xdg-config"),
                "--temp-root",
                "/tmp",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(patch.returncode, 0, msg=patch.stderr)

        sandbox_env = dict(os.environ)
        sandbox_env["CODEX_HOME"] = str(codex_home)
        sandboxed = subprocess.run(
            [
                "codex",
                "sandbox",
                "macos",
                "--permissions-profile",
                PERMISSION_PROFILE,
                "-C",
                str(workspace_dir),
                "/bin/zsh",
                "-lc",
                "rg --files >/tmp/buddyswitch-rg-files.txt && git status --short --untracked-files=all -- . >/tmp/buddyswitch-git-status.txt",
            ],
            text=True,
            capture_output=True,
            check=False,
            env=sandbox_env,
        )
        self.assertEqual(sandboxed.returncode, 0, msg=sandboxed.stderr)
        stderr_lower = sandboxed.stderr.lower()
        self.assertNotIn("operation not permitted", stderr_lower)
        self.assertNotIn("retry without sandbox", stderr_lower)


if __name__ == "__main__":
    unittest.main()
