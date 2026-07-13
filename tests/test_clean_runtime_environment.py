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

from tests.python_runtime import PYTHON

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

    def _runtime_env(self, *, shared_root: Path, workspace_dir: Path, project_workspace_dir: Path, role: str) -> dict[str, str]:
        env = dict()
        env.update(
            {
                "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
                "BUDDYSWITCH_WORKSPACE_DIR": str(workspace_dir),
                "BUDDYSWITCH_PROJECT_WORKSPACE_DIR": str(project_workspace_dir),
                "BUDDYSWITCH_ACTOR_ID": "act-clean-runtime",
                "BUDDYSWITCH_ROLE_ID": role,
                "BUDDYSWITCH_START_ROLE": role,
                "BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE": str(
                    ROOT / "tools" / "launcher" / "assets" / "roles" / role / "AGENTS.md"
                ),
                "BUDDYSWITCH_REPO_ROOT": str(ROOT),
            }
        )
        return env

    def _prepare_runtime_workspace(self, *, role: str = "pm") -> tuple[Path, Path, Path]:
        temp_root = self._new_temp_root()
        shared_root = temp_root / "shared"
        workspace_dir = shared_root / "instances" / "act-clean-runtime" / "workspace"
        project_workspace_dir = shared_root / "project" / "workspace"
        env = self._runtime_env(
            shared_root=shared_root,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
            role=role,
        )
        cmd = """
set -euo pipefail
source tools/launcher/env.sh
buddyswitch_env_init
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

    def _run_cleanup(self, *, shared_root: Path, workspace_dir: Path, project_workspace_dir: Path, role: str) -> subprocess.CompletedProcess[str]:
        env = self._runtime_env(
            shared_root=shared_root,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
            role=role,
        )
        cmd = """
set -euo pipefail
source tools/launcher/env.sh
buddyswitch_env_init
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
        shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(role="pm")

        self.assertFalse((workspace_dir / "buddyswitch" / "objects").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "objects").is_symlink())
        self.assertTrue((workspace_dir / "private").is_dir())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "private" / "pm").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "private" / "pm").is_symlink())

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
        _, workspace_dir, _ = self._prepare_runtime_workspace(role="pm")
        checks = (
            ["rg", "--files"],
            ["rg", "-n", "context|actor_private|track", "."],
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
        shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(role="pm")

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
            role="pm",
        )
        self.assertEqual(cleanup.returncode, 0, msg=cleanup.stderr)
        self.assertFalse(stale_objects.exists())
        self.assertTrue(state_track.exists())
        self.assertEqual(state_track.read_text(encoding="utf-8"), '{"id":"track-old","ok":true}\n')

    def test_stale_object_projection_is_migrated_to_state_root(self) -> None:
        shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(role="pm")

        local_track = workspace_dir / "buddyswitch" / "objects" / "tracks" / "track-local.json"
        local_track.parent.mkdir(parents=True, exist_ok=True)
        local_track.write_text('{"id":"track-local","from":"workspace"}\n', encoding="utf-8")

        cleanup = self._run_cleanup(
            shared_root=shared_root,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
            role="pm",
        )
        self.assertEqual(cleanup.returncode, 0, msg=cleanup.stderr)

        migrated_track = shared_root / "state" / "buddyswitch" / "objects" / "tracks" / "track-local.json"
        self.assertTrue(migrated_track.exists())
        self.assertEqual(migrated_track.read_text(encoding="utf-8"), '{"id":"track-local","from":"workspace"}\n')

        self.assertFalse((workspace_dir / "buddyswitch" / "objects").exists())

    def test_stale_actor_private_projection_is_removed_without_migration(self) -> None:
        shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(role="pm")

        local_box = workspace_dir / "buddyswitch" / "local" / "private" / "pm" / "coordination" / "a-log.md"
        local_box.parent.mkdir(parents=True, exist_ok=True)
        local_box.write_text("hello\n", encoding="utf-8")

        cleanup = self._run_cleanup(
            shared_root=shared_root,
            workspace_dir=workspace_dir,
            project_workspace_dir=project_workspace_dir,
            role="pm",
        )
        self.assertEqual(cleanup.returncode, 0, msg=cleanup.stderr)
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "private").exists())
        self.assertFalse((shared_root / "state" / "buddyswitch" / "local" / "private" / "pm" / "coordination" / "a-log.md").exists())
        self.assertFalse((workspace_dir / "private" / "coordination" / "a-log.md").exists())

    def test_no_prompt_side_command_blacklist_workaround_text(self) -> None:
        completed = subprocess.run(
            [
                "rg",
                "-n",
                "do not run rg|exclude buddyswitch/objects|retry without sandbox|always use rg --glob|command blacklist|phrase-to-tool",
                "tools/launcher/assets/roles",
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

        shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(role="pm")
        instance_root = shared_root / "instances" / "act-clean-runtime"
        codex_home = instance_root / "codex-home"
        config_path = codex_home / "config.toml"
        patch = subprocess.run(
            [
                PYTHON,
                str(CODEX_CONFIG),
                "--config",
                str(config_path),
                "--repo-root",
                str(ROOT),
                "--shared-root",
                str(shared_root),
                "--source-codex-home",
                str(shared_root / "source-codex-home"),
                "--role",
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
                str(instance_root / "tmp"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(patch.returncode, 0, msg=patch.stderr)

        sandbox_env = dict(os.environ)
        sandbox_env["HOME"] = str(instance_root / "home")
        sandbox_env["CODEX_HOME"] = str(codex_home)
        sandbox_env["XDG_CONFIG_HOME"] = str(instance_root / "xdg-config")
        sandbox_env["TMPDIR"] = str(instance_root / "tmp")
        sandbox_env["TMP"] = str(instance_root / "tmp")
        sandbox_env["TEMP"] = str(instance_root / "tmp")
        sandbox_env["TMPPREFIX"] = str(instance_root / "tmp" / "zsh")
        sandbox_env["BUDDYSWITCH_ACTOR_PRIVATE_DIR"] = str(workspace_dir / "private")
        sandbox_env["BUDDYSWITCH_STATE_ROOT"] = str(shared_root / "state")
        sandboxed = subprocess.run(
            [
                "codex",
                "sandbox",
                "--permissions-profile",
                PERMISSION_PROFILE,
                "-C",
                str(workspace_dir),
                "/bin/zsh",
                "-lc",
                "set +e\n"
                "mkdir -p \"$HOME/.cache\" && echo home > \"$HOME/.cache/probe.txt\"; home=$?\n"
                "mkdir -p \"$CODEX_HOME/sessions\" && echo codex > \"$CODEX_HOME/sessions/probe.jsonl\"; codex=$?\n"
                "mkdir -p \"$XDG_CONFIG_HOME/test\" && echo xdg > \"$XDG_CONFIG_HOME/test/probe.txt\"; xdg=$?\n"
                "mkdir -p \"$TMPDIR\" && echo tmp > \"$TMPDIR/probe.txt\"; inst_tmp=$?\n"
                "mkdir -p \"$BUDDYSWITCH_ACTOR_PRIVATE_DIR/prototypes\" && echo actor_private > \"$BUDDYSWITCH_ACTOR_PRIVATE_DIR/prototypes/probe.txt\"; actor_private=$?\n"
                "cat > \"$BUDDYSWITCH_ACTOR_PRIVATE_DIR/heredoc.txt\" <<'EOF'\n"
                "ok\n"
                "EOF\n"
                "heredoc=$?\n"
                "test \"$(cat \"$BUDDYSWITCH_ACTOR_PRIVATE_DIR/heredoc.txt\")\" = ok; heredoc_read=$?\n"
                "echo root > workspace-root-probe.txt; workspace_root=$?\n"
                "echo global > /tmp/buddyswitch-global-probe.txt; global_tmp=$?\n"
                "mkdir -p \"$BUDDYSWITCH_STATE_ROOT/buddyswitch/objects\" && echo state > \"$BUDDYSWITCH_STATE_ROOT/buddyswitch/objects/probe.txt\"; state=$?\n"
                "echo \"home=$home codex=$codex xdg=$xdg inst_tmp=$inst_tmp actor_private=$actor_private heredoc=$heredoc heredoc_read=$heredoc_read workspace_root=$workspace_root global_tmp=$global_tmp state=$state\"\n"
                "test \"$home\" = 0\n"
                "test \"$codex\" = 0\n"
                "test \"$xdg\" = 0\n"
                "test \"$inst_tmp\" = 0\n"
                "test \"$actor_private\" = 0\n"
                "test \"$heredoc\" = 0\n"
                "test \"$heredoc_read\" = 0\n"
                "test \"$workspace_root\" != 0\n"
                "test \"$global_tmp\" != 0\n"
                "test \"$state\" != 0\n",
            ],
            text=True,
            capture_output=True,
            check=False,
            env=sandbox_env,
        )
        self.assertEqual(sandboxed.returncode, 0, msg=sandboxed.stderr)
        self.assertIn("home=0", sandboxed.stdout)
        self.assertIn("xdg=0", sandboxed.stdout)
        self.assertIn("inst_tmp=0", sandboxed.stdout)
        self.assertIn("actor_private=0", sandboxed.stdout)
        self.assertIn("heredoc=0", sandboxed.stdout)
        self.assertIn("heredoc_read=0", sandboxed.stdout)
        self.assertIn("workspace_root=1", sandboxed.stdout)
        self.assertIn("global_tmp=1", sandboxed.stdout)
        self.assertIn("state=1", sandboxed.stdout)
        stderr_lower = sandboxed.stderr.lower()
        self.assertNotIn("retry without sandbox", stderr_lower)


if __name__ == "__main__":
    unittest.main()
