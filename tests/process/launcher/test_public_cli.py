"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.process.launcher._harness import ProcessLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process
from tests.support.python import PYTHON

ROOT = REPO_ROOT
LAUNCHER = ROOT / "buddyswitch-codex"


class TestLauncherPublicCli(ProcessLauncherHarness, unittest.TestCase):
    def test_env_reset_rejects_symlinked_shared_root_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_parent, tempfile.TemporaryDirectory() as external:
            temp_parent_path = Path(temp_parent)
            external_path = Path(external)
            shared_root = temp_parent_path / ".codex-buddyswitch"
            sentinel = external_path / "sentinel.txt"
            sentinel.write_text("preserve\n", encoding="utf-8")
            shared_root.symlink_to(external_path, target_is_directory=True)

            env = os.environ.copy()
            env["HOME"] = str(temp_parent_path)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

            completed = run_process(
                [str(LAUNCHER), "env", "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self._cli_error(completed, code="INVALID_ARGUMENT")
            self.assertIn("Reset blocked:", self._output_error_text(completed))
            self.assertTrue(shared_root.is_symlink())
            self.assertEqual(sorted(path.name for path in external_path.iterdir()), ["sentinel.txt"])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")

    def test_reset_owner_removes_owned_filesystem_without_workspace_or_git_path(self) -> None:
        source = (ROOT / "tools" / "launcher" / "cli.py").read_text(encoding="utf-8")
        helper_block = source.split("def _source_helpers_script(", 1)[1].split(
            "def _reset_locked_script()",
            1,
        )[0]
        reset_block = source.split("def _reset_locked_script()", 1)[1].split(
            "def _cleanup_locked_script()",
            1,
        )[0]

        self.assertNotIn("workspace.sh", helper_block)
        self.assertNotIn("buddyswitch_workspace_", reset_block)
        self.assertNotIn("git worktree", reset_block)
        self.assertIn("buddyswitch_remove_owned_path", reset_block)

    def test_launcher_help_and_reset_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True, exist_ok=True)
            (source_codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "apikey",
                        "openai_api_key": "test-key",
                        "tokens": None,
                        "last_refresh": None,
                        "agent_identity": None,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            ready_file = temp_root_path / "browser-ready.flag"
            calls_path = temp_root_path / "calls.jsonl"
            capture_path = temp_root_path / "capture.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_FAKE_CHROME_SERVE_CDP"] = "1"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            help_result = run_process(
                [str(LAUNCHER), "help"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(help_result.returncode, 0)
            self.assertIn("Usage:", help_result.stdout)
            self.assertIn("buddyswitch-codex instance roles", help_result.stdout)
            self.assertIn("buddyswitch-codex instance start --role <role>", help_result.stdout)
            self.assertIn("buddyswitch-codex data cleanup (--role <role>|--all-data) --yes", help_result.stdout)
            self.assertIn("buddyswitch-codex env status", help_result.stdout)
            self.assertIn("buddyswitch-codex env reset --yes", help_result.stdout)
            self.assertIn("buddyswitch-codex help", help_result.stdout)
            self.assertIn("buddyswitch-codex web", help_result.stdout)
            self.assertIn("  instance", help_result.stdout)
            self.assertIn("  web", help_result.stdout)
            self.assertIn("  data", help_result.stdout)
            self.assertIn("  env", help_result.stdout)
            self.assertIn("  help", help_result.stdout)
            self.assertNotIn("buddyswitch-codex [codex args...]", help_result.stdout)
            self.assertNotIn("buddyswitch-codex start", help_result.stdout)
            self.assertNotIn("buddyswitch-codex role", help_result.stdout)
            self.assertNotIn("buddyswitch-codex cleanup", help_result.stdout)
            self.assertNotIn("buddyswitch-codex reset", help_result.stdout)
            self.assertNotIn("buddyswitch-codex browser", help_result.stdout)
            self.assertNotIn("buddyswitch-codex workspace", help_result.stdout)
            self.assertNotIn("imessage " + "bridge", help_result.stdout)
            self.assertNotIn("target" + "-identity-id", help_result.stdout)
            self.assertNotIn("allow" + "-sender", help_result.stdout)
            self.assertNotIn("  imessage", help_result.stdout)
    def test_public_cli_successes_emit_single_cli_contract_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            roles_result = run_process(
                [str(LAUNCHER), "instance", "roles"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            list_result = run_process(
                [str(LAUNCHER), "instance", "list"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            env_status_result = run_process(
                [str(LAUNCHER), "env", "status"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(roles_result.returncode, 0)
            roles_data = self._cli_success_data(roles_result, kind="instance.roles")
            self.assertIsInstance(roles_data, dict)
            assert isinstance(roles_data, dict)
            role_ids = {row["id"] for row in roles_data["roles"] if isinstance(row, dict)}
            self.assertIn("pm", role_ids)
            self.assertIn("dev", role_ids)

            self.assertEqual(list_result.returncode, 0)
            self.assertEqual(self._cli_success_data(list_result, kind="instance.list"), {"instances": []})

            self.assertEqual(env_status_result.returncode, 0)
            env_data = self._cli_success_data(env_status_result, kind="env.status")
            self.assertIsInstance(env_data, dict)
            assert isinstance(env_data, dict)
            self.assertEqual(env_data["shared_root"], str(shared_root))
            self.assertEqual(env_data["instance_count"], 0)
            self.assertEqual(env_data["browser_state"], "inactive")
            self.assertFalse(shared_root.exists(), "read-only public status commands must not create runtime state")
    def test_env_manifest_commands_emit_one_canonical_json_line(self) -> None:
        cases = (
            ["print"],
            ["list-roles"],
            ["show-role", "pm"],
        )
        for argv in cases:
            with self.subTest(argv=argv):
                completed = run_process(
                    [PYTHON, "scripts/env_manifest.py", *argv],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(completed.returncode, 0, msg=completed.stderr)
                self.assertEqual(completed.stderr, "")
                self.assertEqual(completed.stdout.count("\n"), 1, msg=completed.stdout)
                payload = json.loads(completed.stdout)
                self.assertEqual(completed.stdout, json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
                self.assertIsInstance(payload, dict)
        role_ids = {row["id"] for row in json.loads(
            run_process(
                [PYTHON, "scripts/env_manifest.py", "list-roles"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout
        )["roles"]}
        self.assertIn("pm", role_ids)
        self.assertIn("dev", role_ids)
    def test_env_manifest_list_roles_rejects_removed_json_flag(self) -> None:
        removed = run_process(
            [PYTHON, "scripts/env_manifest.py", "list-roles", "--" + "json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(removed.returncode, 2, msg=removed.stdout + removed.stderr)
        self.assertEqual(removed.stdout, "")
    def test_env_cleanup_helper_is_json_only_without_json_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            repo_root = Path(temp_root) / "state"
            repo_root.mkdir(parents=True)

            preview = run_process(
                [
                    PYTHON,
                    "scripts/env_cleanup.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(ROOT / "buddyswitch" / "manifest.toml"),
                    "--role",
                    "pm",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(preview.returncode, 0, msg=preview.stderr)
            self.assertEqual(preview.stderr, "")
            self.assertEqual(preview.stdout.count("\n"), 1, msg=preview.stdout)
            payload = json.loads(preview.stdout)
            self.assertEqual(payload["scope"], "role")
            self.assertEqual(payload["role"], "pm")

            removed = run_process(
                [
                    PYTHON,
                    "scripts/env_cleanup.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(ROOT / "buddyswitch" / "manifest.toml"),
                    "--role",
                    "pm",
                    "--" + "json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(removed.returncode, 2, msg=removed.stdout + removed.stderr)
            self.assertEqual(removed.stdout, "")
    def test_cleanup_helper_retired_options_are_generic_unknown_options(self) -> None:
        retired_options = (
            "--app-runtime",
            "--agent",
            "--all-agents",
            "--project",
            "--all-storage",
            "--execute",
            "--force",
        )
        for option in retired_options:
            with self.subTest(option=option):
                completed = run_process(
                    [
                        "/bin/bash",
                        "-c",
                        'source tools/launcher/cleanup.sh; buddyswitch_cleanup_parse_args "$@"',
                        "cleanup-parse-test",
                        option,
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(completed.returncode, 2)
                self.assertIn(f"Unknown data cleanup option: {option}", completed.stderr)
                self.assertNotIn("Removed data cleanup option", completed.stderr)
                self.assertEqual(completed.stdout, "")
    def test_public_data_cleanup_bridge_consumes_owner_json_without_output_flag(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = run_process(
                [str(LAUNCHER), "data", "cleanup", "--all-data", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            data = self._cli_success_data(completed, kind="data.cleanup")
            self.assertIsInstance(data, dict)
            assert isinstance(data, dict)
            self.assertIn("plan", data)
            self.assertIn("result", data)
            self.assertNotIn("stdout", data)
            self.assertNotIn("stderr", data)
            self.assertEqual(data["result"]["scope"], "all-data")  # type: ignore[index]
    def test_public_cli_rejects_unknown_commands_and_arguments_without_historical_hints(self) -> None:
        cases = (
            (["start"], "UNKNOWN_COMMAND", "Unknown top-level command: start"),
            (["workspace"], "UNKNOWN_COMMAND", "Unknown top-level command: workspace"),
            (["__" + "locked-reset"], "UNKNOWN_COMMAND", "Unknown top-level command: __" + "locked-reset"),
            (
                ["__" + "locked-browser-ensure"],
                "UNKNOWN_COMMAND",
                "Unknown top-level command: __" + "locked-browser-ensure",
            ),
            (
                ["instance", "side", "act-pm-demo", "--text", "Explore"],
                "UNKNOWN_COMMAND",
                "Unknown instance command: side",
            ),
            (
                ["instance", "goal", "act-pm-demo", "get"],
                "UNKNOWN_COMMAND",
                "Unknown instance command: goal",
            ),
            (["instance", "roles", "--" + "json"], "INVALID_ARGUMENT", "instance roles does not accept: --json"),
            (
                ["instance", "list", "--output", "text"],
                "INVALID_ARGUMENT",
                "instance list does not accept: --output",
            ),
        )
        for argv, code, message in cases:
            with self.subTest(argv=argv):
                completed = run_process(
                    [str(LAUNCHER), *argv],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(completed.returncode, 2)
                error = self._cli_error(completed, code=code)
                self.assertEqual(error.get("message"), message)
                error_text = json.dumps(error, ensure_ascii=False).lower()
                for forbidden_hint in ("migrat", "replacement", "not supported", "command removed"):
                    self.assertNotIn(forbidden_hint, error_text)
    def test_public_cli_destructive_commands_require_yes_with_confirmation_error(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "act-pm-keep")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            cases = (
                ["instance", "delete", "act-pm-keep"],
                ["env", "reset"],
                ["data", "cleanup", "--all-data"],
            )
            for argv in cases:
                with self.subTest(argv=argv):
                    completed = run_process(
                        [str(LAUNCHER), *argv],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertEqual(completed.returncode, 4)
                    error = self._cli_error(completed, code="CONFIRMATION_REQUIRED")
                    self.assertIn("--yes", str(error.get("message")))
                    self.assertTrue(target_root.exists())
    def test_public_cli_task_and_track_commands_read_external_projections(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            state_root = shared_root / "state"
            task_dir = state_root / "buddyswitch" / "objects" / "task-sys" / "tasks"
            track_dir = state_root / "buddyswitch" / "objects" / "tracks"
            task_dir.mkdir(parents=True, exist_ok=True)
            track_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "task-alpha.json").write_text(
                json.dumps(
                    {
                        "id": "task-alpha",
                        "source_type": "message",
                        "actor_target": {"actor_id": "act-pm-demo", "role_id": "pm"},
                        "status": "in_progress.side_processing",
                        "execution": {"processor": "side", "handoff": None, "result": None},
                        "updated_at": "2026-07-13T00:00:00Z",
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (track_dir / "track-alpha.json").write_text(
                json.dumps(
                    {
                        "id": "track-alpha",
                        "title": "Launch web control",
                        "outcome": "External control works",
                        "owner_identity_id": "act-pm-demo",
                        "state": "active",
                        "now": {"next": "Validate CLI", "blocker": None},
                        "acceptance_criteria": ["CLI emits envelopes"],
                        "non_goals": [],
                        "artifact_relations": [],
                        "updates": [],
                        "created_at": "2026-07-13T00:00:00Z",
                        "updated_at": "2026-07-13T00:00:01Z",
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_STATE_ROOT"] = str(state_root)
            env.pop("CODEX_HOME", None)

            task_list = run_process(
                [str(LAUNCHER), "task", "list", "--actor", "act-pm-demo"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            task_get = run_process(
                [str(LAUNCHER), "task", "get", "task-alpha"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            track_list = run_process(
                [str(LAUNCHER), "track", "list", "--owner", "act-pm-demo"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            track_get = run_process(
                [str(LAUNCHER), "track", "get", "track-alpha"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(task_list.returncode, 0)
            task_list_data = self._cli_success_data(task_list, kind="task.list")
            self.assertEqual(task_list_data["tasks"][0]["task_id"], "task-alpha")
            self.assertEqual(task_list_data["tasks"][0]["actor"]["actor_id"], "act-pm-demo")

            self.assertEqual(task_get.returncode, 0)
            self.assertEqual(self._cli_success_data(task_get, kind="task.get")["task"]["task_id"], "task-alpha")

            self.assertEqual(track_list.returncode, 0)
            self.assertEqual(self._cli_success_data(track_list, kind="track.list")["tracks"][0]["id"], "track-alpha")

            self.assertEqual(track_get.returncode, 0)
            self.assertEqual(self._cli_success_data(track_get, kind="track.get")["track"]["id"], "track-alpha")
    def test_public_cli_task_and_track_malformed_arguments_emit_canonical_errors(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            state_root = shared_root / "state"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_STATE_ROOT"] = str(state_root)
            env.pop("CODEX_HOME", None)

            cases = (
                ["track", "get", "../bad"],
                ["task", "list", "--actor", "act-PM-demo"],
            )
            for argv in cases:
                with self.subTest(argv=argv):
                    completed = run_process(
                        [str(LAUNCHER), *argv],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertEqual(completed.returncode, 2)
                    self._cli_error(completed, code="INVALID_ARGUMENT")
                    self.assertNotIn("Traceback", completed.stdout + completed.stderr)
                    self.assertNotIn("INTERNAL_ERROR", completed.stdout)
    def test_legacy_public_commands_fail_closed_as_unknown_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True, exist_ok=True)
            (source_codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "apikey",
                        "openai_api_key": "test-key",
                        "tokens": None,
                        "last_refresh": None,
                        "agent_identity": None,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            ready_file = temp_root_path / "browser-ready.flag"
            capture_path = temp_root_path / "capture.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            commands = ("start", "role", "cleanup", "reset", "browser", "workspace")
            for command in commands:
                with self.subTest(command=command):
                    capture_path.unlink(missing_ok=True)
                    result = run_process(
                        [str(LAUNCHER), command],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(
                        result.returncode,
                        2,
                        msg=f"legacy command should fail closed\nstdout:\n{result.stdout}\nstderr:\n{self._output_error_text(result)}",
                    )
                    self._cli_error(result, code="UNKNOWN_COMMAND")
                    self.assertIn(f"Unknown top-level command: {command}", self._output_error_text(result))
                    self.assertNotIn("replacement", self._output_error_text(result).lower())
                    self.assertNotIn("migrat", self._output_error_text(result).lower())
                    self.assertFalse(capture_path.exists(), "legacy command must not invoke codex")
    def test_unknown_top_level_command_fails_closed_without_invoking_codex(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True, exist_ok=True)
            (source_codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "apikey",
                        "openai_api_key": "test-key",
                        "tokens": None,
                        "last_refresh": None,
                        "agent_identity": None,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            ready_file = temp_root_path / "browser-ready.flag"
            capture_path = temp_root_path / "capture.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            debug_result = run_process(
                [str(LAUNCHER), "debug", "prompt-input", "Draft the onboarding PRD"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                debug_result.returncode,
                2,
                msg=f"unknown top-level command should fail closed\nstdout:\n{debug_result.stdout}\nstderr:\n{self._output_error_text(debug_result)}",
            )
            self._cli_error(debug_result, code="UNKNOWN_COMMAND")
            self.assertIn("Unknown top-level command: debug", self._output_error_text(debug_result))
            self.assertFalse(capture_path.exists(), "unknown top-level command must not invoke codex")
    def test_removed_cleanup_command_fails_closed_without_launching_codex(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = temp_root_path / "shared-root"
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            capture_path = temp_root_path / "capture.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            cleanup_result = run_process(
                [str(LAUNCHER), "cleanup", "--all-agents"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(cleanup_result.returncode, 2)
            self._cli_error(cleanup_result, code="UNKNOWN_COMMAND")
            self.assertIn("Unknown top-level command: cleanup", self._output_error_text(cleanup_result))
            self.assertFalse(capture_path.exists(), "removed cleanup command must not start Codex")
            self.assertFalse(shared_root.exists(), "removed cleanup command must not create shared state")
