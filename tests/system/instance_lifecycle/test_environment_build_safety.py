"""System proof for the Git-free Actor environment build and owned cleanup."""

from __future__ import annotations

from contextlib import ExitStack
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.system.support.launcher import SystemLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process
from buddyswitch.roles.secondary_market_investor.role import (
    ROLE as SECONDARY_MARKET_INVESTOR_ROLE,
)


LAUNCHER = REPO_ROOT / "buddyswitch-codex"


def _activated_runtime_identity() -> dict[str, object]:
    configured = os.environ.get("BUDDYSWITCH_RUNTIME_DIR")
    runtime_dir = (
        Path(configured)
        if configured is not None
        else REPO_ROOT / ".buddyswitch-runtime"
    )
    payload = json.loads(
        (runtime_dir / "activation.json").read_text(encoding="utf-8")
    )
    assert isinstance(payload, dict)
    return payload


class TestEnvironmentBuildSafety(SystemLauncherHarness, unittest.TestCase):
    def test_directory_only_investor_role_starts_with_only_selected_bootstrap(self) -> None:
        with ExitStack() as cleanup:
            temp_root = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            source_home = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            ctx = self._start_service_instance(
                temp_root,
                source_home,
                cleanup_stack=cleanup,
                role="secondary-market-investor",
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(
                completed.returncode,
                0,
                msg=self._output_error_text(completed),
            )

            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            self.assertEqual(
                instance_payload["role"],
                "secondary-market-investor",
            )
            workspace = Path(str(ctx["instance_root"])) / "workspace"
            self.assertEqual(
                (workspace / "AGENTS.md").read_text(encoding="utf-8"),
                (
                    REPO_ROOT
                    / "src"
                    / "buddyswitch"
                    / "roles"
                    / "secondary_market_investor"
                    / "AGENTS.md"
                ).read_text(encoding="utf-8"),
            )
            self.assertEqual(
                {
                    path.name
                    for path in (workspace / ".agents" / "skills").iterdir()
                },
                set(SECONDARY_MARKET_INVESTOR_ROLE.skills),
            )
            self._assert_runtime_workspace_excludes_source_surfaces(workspace)
            self._stop_service_instance(ctx)

    def test_started_actor_is_code_free_and_runtime_attributable(self) -> None:
        with ExitStack() as cleanup:
            temp_root = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            source_home = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            ctx = self._start_service_instance(
                temp_root,
                source_home,
                cleanup_stack=cleanup,
                role="pm",
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(
                completed.returncode,
                0,
                msg=self._output_error_text(completed),
            )

            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            instance_root = Path(str(ctx["instance_root"]))
            workspace = instance_root / "workspace"
            copied_implementation = [
                relative
                for relative in (
                    "scripts",
                    "tools",
                    "framework",
                    "src",
                    "tests",
                    "docs",
                    "buddyswitch/manifest.toml",
                )
                if (workspace / relative).exists()
            ]

            self.assertEqual(
                (
                    instance_payload.get("runtime_identity"),
                    copied_implementation,
                ),
                (
                    _activated_runtime_identity(),
                    [],
                ),
            )
            self._stop_service_instance(ctx)

    def test_two_actor_starts_share_one_preserved_git_free_project_environment(self) -> None:
        with ExitStack() as cleanup:
            first_temp = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            second_temp = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            source_home = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            first = self._start_service_instance(
                first_temp,
                source_home,
                cleanup_stack=cleanup,
                role="pm",
            )
            first_completed = first["completed"]
            assert isinstance(first_completed, subprocess.CompletedProcess)
            self.assertEqual(first_completed.returncode, 0, msg=self._output_error_text(first_completed))
            first_root = Path(str(first["instance_root"]))
            shared_root = Path(str(first["shared_root"]))
            project_workspace = shared_root / "project" / "workspace"
            sentinel = project_workspace / "projects" / "app" / "seed-once-sentinel.txt"
            sentinel.write_text("preserve\n", encoding="utf-8")
            self.assertEqual(list(first_root.rglob(".git")), [])
            self.assertEqual(list(project_workspace.rglob(".git")), [])
            worktree_output = run_process(
                ["git", "-C", str(REPO_ROOT), "worktree", "list", "--porcelain"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            self.assertNotIn(str(first_root), worktree_output)
            self.assertNotIn(str(project_workspace), worktree_output)
            self._stop_service_instance(first)

            second = self._start_service_instance(
                second_temp,
                source_home,
                cleanup_stack=cleanup,
                role="pm",
            )
            second_completed = second["completed"]
            assert isinstance(second_completed, subprocess.CompletedProcess)
            self.assertEqual(second_completed.returncode, 0, msg=self._output_error_text(second_completed))
            second_root = Path(str(second["instance_root"]))
            second_project_link = second_root / "workspace" / "projects" / "app"
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
            self.assertTrue(second_project_link.is_symlink())
            self.assertEqual(
                second_project_link.resolve(),
                (project_workspace / "projects" / "app").resolve(),
            )
            self.assertEqual(list(second_root.rglob(".git")), [])
            second_worktree_output = run_process(
                ["git", "-C", str(REPO_ROOT), "worktree", "list", "--porcelain"],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            self.assertNotIn(str(second_root), second_worktree_output)
            self.assertNotIn(str(project_workspace), second_worktree_output)
            self._stop_service_instance(second)

    def test_reset_removes_stopped_actor_and_shared_project_as_owned_filesystem(self) -> None:
        with ExitStack() as cleanup:
            temp_root = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            source_home = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            ctx = self._start_service_instance(
                temp_root,
                source_home,
                cleanup_stack=cleanup,
                role="pm",
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            shared_root = Path(str(ctx["shared_root"]))
            self._stop_service_instance(ctx)

            self._reset_service_environment(ctx)

            self.assertFalse(shared_root.exists())

    def test_inactive_resume_ignores_retired_source_locator(self) -> None:
        with ExitStack() as cleanup:
            temp_root = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            source_home = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            ctx = self._start_service_instance(
                temp_root,
                source_home,
                cleanup_stack=cleanup,
                role="pm",
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            self._stop_service_instance(ctx)
            detached_repo = temp_root / "detached-runtime-carrier"
            detached_repo.mkdir()
            resume_env = dict(ctx["env"])
            resume_env["BUDDYSWITCH_REPO_ROOT"] = str(detached_repo)

            resumed = run_process(
                [str(LAUNCHER), "instance", "resume", str(ctx["actor_id"])],
                cwd=REPO_ROOT,
                env=resume_env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resumed.returncode, 0, msg=self._output_error_text(resumed))
            payload = self._cli_success_data(resumed, kind="instance.resume")
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["status"], "active")

    def test_active_resume_ignores_runtime_owned_codex_symlinks(self) -> None:
        with ExitStack() as cleanup:
            temp_root = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            source_home = Path(cleanup.enter_context(tempfile.TemporaryDirectory()))
            ctx = self._start_service_instance(
                temp_root,
                source_home,
                cleanup_stack=cleanup,
                role="pm",
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            instance_root = Path(str(ctx["instance_root"]))
            runtime_target = temp_root / "codex-runtime-wrapper"
            runtime_target.write_text("runtime\n", encoding="utf-8")
            runtime_link = instance_root / "codex-home" / "tmp" / "arg0" / "codex-test" / "apply_patch"
            runtime_link.parent.mkdir(parents=True)
            runtime_link.symlink_to(runtime_target)

            resumed = run_process(
                [str(LAUNCHER), "instance", "resume", str(ctx["actor_id"])],
                cwd=REPO_ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resumed.returncode, 0, msg=self._output_error_text(resumed))
            payload = self._cli_success_data(resumed, kind="instance.resume")
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["status"], "active")
            self.assertTrue(runtime_link.is_symlink())


if __name__ == "__main__":
    unittest.main()
