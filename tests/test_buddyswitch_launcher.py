#!/usr/bin/env python3
"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "buddyswitch-codex"


class BuddySwitchLauncherTests(unittest.TestCase):
    def _write_exec(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _write_fake_codex(self, path: Path) -> None:
        self._write_exec(
            path,
            """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

codex_home = Path(os.environ["CODEX_HOME"])
entry = {
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "home": os.environ.get("HOME"),
    "codex_home": os.environ.get("CODEX_HOME"),
    "xdg_config_home": os.environ.get("XDG_CONFIG_HOME"),
}
calls_path = os.environ.get("BUDDYSWITCH_TEST_CALLS")
if calls_path:
    with Path(calls_path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\\n")

if sys.argv[1:3] == ["mcp", "add"]:
    raise SystemExit(0)

counter_path = codex_home / "launch-count.txt"
launch_count = int(counter_path.read_text(encoding="utf-8")) if counter_path.exists() else 0
launch_count += 1
counter_path.write_text(f"{launch_count}\\n", encoding="utf-8")

payload = {
    **entry,
    "launch_count": launch_count,
    "config_toml": (codex_home / "config.toml").read_text(encoding="utf-8"),
    "auth_json": json.loads((codex_home / "auth.json").read_text(encoding="utf-8")),
}
Path(os.environ["BUDDYSWITCH_TEST_CAPTURE"]).write_text(
    json.dumps(payload, ensure_ascii=True, indent=2) + "\\n",
    encoding="utf-8",
)
""",
        )

    def _write_fake_curl(self, path: Path) -> None:
        self._write_exec(
            path,
            """#!/usr/bin/env bash
if [[ -f "${BUDDYSWITCH_TEST_BROWSER_READY_FILE:-}" ]]; then
  exit 0
fi
exit 1
""",
        )

    def _write_fake_chrome(self, path: Path) -> None:
        self._write_exec(
            path,
            """#!/usr/bin/env bash
if [[ -n "${BUDDYSWITCH_TEST_BROWSER_READY_FILE:-}" ]]; then
  touch "${BUDDYSWITCH_TEST_BROWSER_READY_FILE}"
fi
exit 0
""",
        )

    def _write_fake_git(self, path: Path) -> None:
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git, "git must be available for launcher tests")
        self._write_exec(
            path,
            f"""#!/usr/bin/env bash
set -euo pipefail
real_git={real_git!r}

if [[ -n "${{BUDDYSWITCH_TEST_GIT_CAPTURE:-}}" && " $* " == *" worktree add "* ]]; then
  marker_state="absent"
  if ls "${{BUDDYSWITCH_RUN_STATE_DIR}}"/launcher-*.pid >/dev/null 2>&1; then
    marker_state="present"
  fi
  printf '%s\\t%s\\n' "$*" "$marker_state" >> "${{BUDDYSWITCH_TEST_GIT_CAPTURE}}"
fi

if [[ "${{BUDDYSWITCH_FAIL_WORKTREE_ADD:-0}}" == "1" && " $* " == *" worktree add "* ]]; then
  echo "simulated worktree add failure" >&2
  exit 1
fi

exec "$real_git" "$@"
""",
        )

    def test_start_bootstraps_browser_stack_and_reuses_state(self) -> None:
        self.assertTrue(LAUNCHER.exists(), "expected root launcher to exist")

        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True, exist_ok=True)

            auth_payload = {
                "auth_mode": "apikey",
                "openai_api_key": "test-key",
                "tokens": None,
                "last_refresh": None,
                "agent_identity": None,
            }
            (source_codex_home / "auth.json").write_text(
                json.dumps(auth_payload, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            calls_path = temp_root_path / "calls.jsonl"
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)

            capture_paths = [temp_root_path / "capture-1.json", temp_root_path / "capture-2.json"]
            payloads: list[dict[str, object]] = []

            for capture_path in capture_paths:
                run_env = env.copy()
                run_env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
                completed = subprocess.run(
                    [str(LAUNCHER), "debug", "prompt-input", "switch pm: draft prd"],
                    cwd=ROOT,
                    env=run_env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    msg=f"launcher failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
                )
                payloads.append(json.loads(capture_path.read_text(encoding="utf-8")))

            expected_home = source_home_path / ".codex-buddyswitch" / "home"
            expected_codex_home = source_home_path / ".codex-buddyswitch" / "codex-home"
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"

            for payload in payloads:
                self.assertEqual(payload["argv"], ["debug", "prompt-input", "switch pm: draft prd"])
                self.assertEqual(payload["cwd"], str(workspace_dir.resolve()))
                self.assertEqual(payload["auth_json"], auth_payload)
                self.assertIn("[skills.bundled]", payload["config_toml"])
                self.assertIn("enabled = false", payload["config_toml"])
                self.assertIn("[features]", payload["config_toml"])
                self.assertIn("plugins = false", payload["config_toml"])
                self.assertEqual(payload["home"], str(expected_home))
                self.assertEqual(payload["codex_home"], str(expected_codex_home))

            self.assertEqual(payloads[0]["launch_count"], 1)
            self.assertEqual(payloads[1]["launch_count"], 2)
            self.assertTrue(ready_file.exists(), "start should ensure the shared browser endpoint")
            self.assertTrue((shared_root / "chrome" / "shared-browser").exists())

            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            mcp_add_names = [entry["argv"][2] for entry in call_entries if entry["argv"][:2] == ["mcp", "add"]]
            self.assertIn("chrome-devtools", mcp_add_names)
            self.assertIn("chrome-devtools-cockpit", mcp_add_names)

    def test_start_execution_worktree_uses_runtime_workspace_agents_header(self) -> None:
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

            completed = subprocess.run(
                [str(LAUNCHER), "start", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"launcher failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            )

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            workspace_dir = source_home_path / ".codex-buddyswitch" / "workspace"
            self.assertEqual(payload["cwd"], str(workspace_dir.resolve()))
            agents_md = workspace_dir / "AGENTS.md"
            self.assertTrue(agents_md.exists(), "runtime workspace should include AGENTS.md")
            expected_agents = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(agents_md.read_text(encoding="utf-8"), expected_agents)

    def test_start_writes_launcher_marker_before_workspace_bootstrap(self) -> None:
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
            self._write_fake_git(fake_bin / "git")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")
            env["BUDDYSWITCH_TEST_GIT_CAPTURE"] = str(temp_root_path / "git-calls.log")

            completed = subprocess.run(
                [str(LAUNCHER), "start"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"launcher failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            )

            captures = (temp_root_path / "git-calls.log").read_text(encoding="utf-8").splitlines()
            self.assertTrue(captures, "expected worktree add to be recorded")
            self.assertTrue(
                any(line.endswith("\tpresent") for line in captures),
                "launcher marker should exist before workspace worktree bootstrap",
            )

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
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            help_result = subprocess.run(
                [str(LAUNCHER), "help"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(help_result.returncode, 0)
            self.assertIn("Usage:", help_result.stdout)
            self.assertIn("reset --yes", help_result.stdout)
            self.assertIn("browser status", help_result.stdout)
            self.assertIn("browser ensure", help_result.stdout)
            self.assertIn("workspace sync", help_result.stdout)
            self.assertNotIn("workspace ensure", help_result.stdout)
            self.assertNotIn("install-mcp", help_result.stdout)

            launch_result = subprocess.run(
                [str(LAUNCHER), "start"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(launch_result.returncode, 0)

            shared_root = source_home_path / ".codex-buddyswitch"
            self.assertTrue(shared_root.exists(), "start should create shared launcher root")

            reset_without_yes = subprocess.run(
                [str(LAUNCHER), "reset"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(reset_without_yes.returncode, 1)
            self.assertTrue(shared_root.exists(), "reset without --yes must not remove shared root")

            ready_file.unlink(missing_ok=True)
            (shared_root / "run" / "browser-cockpit.pid").unlink(missing_ok=True)

            reset_with_yes = subprocess.run(
                [str(LAUNCHER), "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(reset_with_yes.returncode, 0)
            self.assertFalse(shared_root.exists(), "reset --yes should remove shared root")

    def test_reset_is_blocked_when_active_launcher_marker_exists(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "launcher-current.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            blocked_reset = subprocess.run(
                [str(LAUNCHER), "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(blocked_reset.returncode, 3)
            self.assertTrue(shared_root.exists(), "active marker should block reset")

    def test_reset_is_blocked_when_active_browser_marker_exists(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "browser-cockpit.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            blocked_reset = subprocess.run(
                [str(LAUNCHER), "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(blocked_reset.returncode, 3)
            self.assertTrue(shared_root.exists(), "active browser marker should block reset")

    def test_workspace_sync_is_blocked_when_active_launcher_marker_exists(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "launcher-current.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            blocked_sync = subprocess.run(
                [str(LAUNCHER), "workspace", "sync"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(blocked_sync.returncode, 3)
            self.assertIn("active buddyswitch-codex instance", blocked_sync.stderr)
            self.assertFalse((shared_root / "workspace").exists(), "blocked sync must not create the workspace")

    def test_workspace_command_requires_explicit_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            missing_subcommand = subprocess.run(
                [str(LAUNCHER), "workspace"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(missing_subcommand.returncode, 2)
            self.assertIn("workspace command is required", missing_subcommand.stderr)
            self.assertIn("workspace sync", missing_subcommand.stderr)
            self.assertFalse(workspace_dir.exists(), "workspace command without subcommand must not run sync")

    def test_workspace_sync_rebuilds_valid_stale_worktree_to_repo_head(self) -> None:
        parent_head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD~1"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if parent_head.returncode != 0:
            self.skipTest("repository does not have HEAD~1 available for stale-worktree test")
        stale_head = parent_head.stdout.strip()
        repo_head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(repo_head.returncode, 0, msg=repo_head.stderr)
        current_head = repo_head.stdout.strip()
        self.assertNotEqual(stale_head, current_head)

        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"
            shared_root.mkdir(parents=True, exist_ok=True)

            add_worktree = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(workspace_dir), stale_head],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(add_worktree.returncode, 0, msg=add_worktree.stderr)

            try:
                before_sync = subprocess.run(
                    ["git", "-C", str(workspace_dir), "rev-parse", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(before_sync.returncode, 0, msg=before_sync.stderr)
                self.assertEqual(before_sync.stdout.strip(), stale_head)

                env = os.environ.copy()
                env["HOME"] = str(source_home_path)
                env.pop("CODEX_HOME", None)

                sync_result = subprocess.run(
                    [str(LAUNCHER), "workspace", "sync"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    sync_result.returncode,
                    0,
                    msg=f"workspace sync failed\nstdout:\n{sync_result.stdout}\nstderr:\n{sync_result.stderr}",
                )

                after_sync = subprocess.run(
                    ["git", "-C", str(workspace_dir), "rev-parse", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(after_sync.returncode, 0, msg=after_sync.stderr)
                self.assertEqual(after_sync.stdout.strip(), current_head)
            finally:
                subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(workspace_dir)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "prune"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

    def test_start_leaves_valid_stale_worktree_untouched(self) -> None:
        parent_head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD~1"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if parent_head.returncode != 0:
            self.skipTest("repository does not have HEAD~1 available for stale-worktree test")
        stale_head = parent_head.stdout.strip()

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

            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"
            shared_root.mkdir(parents=True, exist_ok=True)

            add_worktree = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(workspace_dir), stale_head],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(add_worktree.returncode, 0, msg=add_worktree.stderr)

            try:
                before_start = subprocess.run(
                    ["git", "-C", str(workspace_dir), "rev-parse", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(before_start.returncode, 0, msg=before_start.stderr)
                self.assertEqual(before_start.stdout.strip(), stale_head)

                env = os.environ.copy()
                env["HOME"] = str(source_home_path)
                env.pop("CODEX_HOME", None)
                env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
                env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
                env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
                env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")

                launch_result = subprocess.run(
                    [str(LAUNCHER), "start"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    launch_result.returncode,
                    0,
                    msg=f"launcher failed\nstdout:\n{launch_result.stdout}\nstderr:\n{launch_result.stderr}",
                )

                after_start = subprocess.run(
                    ["git", "-C", str(workspace_dir), "rev-parse", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(after_start.returncode, 0, msg=after_start.stderr)
                self.assertEqual(after_start.stdout.strip(), stale_head)
            finally:
                subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(workspace_dir)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "prune"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )

    def test_workspace_sync_restores_runtime_agents_and_preserves_runtime_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"
            runtime_artifact = workspace_dir / "buddyswitch" / "objects" / "artifacts" / "artifact-demo.json"
            runtime_run = workspace_dir / "buddyswitch" / "content" / "runs" / "run-demo.json"
            raw_dump = workspace_dir / "runs" / "raw" / "dump.json"
            runtime_session = workspace_dir / "projects" / "app" / ".runtime" / "session.json"

            (workspace_dir / ".git").mkdir(parents=True, exist_ok=True)
            runtime_artifact.parent.mkdir(parents=True, exist_ok=True)
            runtime_run.parent.mkdir(parents=True, exist_ok=True)
            raw_dump.parent.mkdir(parents=True, exist_ok=True)
            runtime_session.parent.mkdir(parents=True, exist_ok=True)
            runtime_artifact.write_text('{"artifact_id":"artifact-demo"}\n', encoding="utf-8")
            runtime_run.write_text('{"run_id":"run-demo"}\n', encoding="utf-8")
            raw_dump.write_text('{"raw":true}\n', encoding="utf-8")
            runtime_session.write_text('{"session":"demo"}\n', encoding="utf-8")
            (workspace_dir / "AGENTS.md").write_text("# Wrong Header\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            sync_result = subprocess.run(
                [str(LAUNCHER), "workspace", "sync"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                sync_result.returncode,
                0,
                msg=f"workspace sync failed\nstdout:\n{sync_result.stdout}\nstderr:\n{sync_result.stderr}",
            )
            self.assertIn("Workspace synced:", sync_result.stdout)
            self.assertTrue((workspace_dir / ".git").exists(), "workspace sync should leave a git worktree behind")
            expected_agents = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual((workspace_dir / "AGENTS.md").read_text(encoding="utf-8"), expected_agents)
            self.assertEqual(runtime_artifact.read_text(encoding="utf-8"), '{"artifact_id":"artifact-demo"}\n')
            self.assertEqual(runtime_run.read_text(encoding="utf-8"), '{"run_id":"run-demo"}\n')
            self.assertEqual(raw_dump.read_text(encoding="utf-8"), '{"raw":true}\n')
            self.assertEqual(runtime_session.read_text(encoding="utf-8"), '{"session":"demo"}\n')

    def test_workspace_sync_restores_runtime_outputs_when_worktree_rebuild_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"
            runtime_artifact = workspace_dir / "buddyswitch" / "objects" / "artifacts" / "artifact-demo.json"
            runtime_run = workspace_dir / "buddyswitch" / "content" / "runs" / "run-demo.json"
            raw_dump = workspace_dir / "runs" / "raw" / "dump.json"
            runtime_session = workspace_dir / "projects" / "app" / ".runtime" / "session.json"

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_git(fake_bin / "git")

            (workspace_dir / ".git").mkdir(parents=True, exist_ok=True)
            runtime_artifact.parent.mkdir(parents=True, exist_ok=True)
            runtime_run.parent.mkdir(parents=True, exist_ok=True)
            raw_dump.parent.mkdir(parents=True, exist_ok=True)
            runtime_session.parent.mkdir(parents=True, exist_ok=True)
            runtime_artifact.write_text('{"artifact_id":"artifact-demo"}\n', encoding="utf-8")
            runtime_run.write_text('{"run_id":"run-demo"}\n', encoding="utf-8")
            raw_dump.write_text('{"raw":true}\n', encoding="utf-8")
            runtime_session.write_text('{"session":"demo"}\n', encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_FAIL_WORKTREE_ADD"] = "1"

            sync_result = subprocess.run(
                [str(LAUNCHER), "workspace", "sync"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(sync_result.returncode, 0)
            self.assertIn("simulated worktree add failure", sync_result.stderr)
            self.assertEqual(runtime_artifact.read_text(encoding="utf-8"), '{"artifact_id":"artifact-demo"}\n')
            self.assertEqual(runtime_run.read_text(encoding="utf-8"), '{"run_id":"run-demo"}\n')
            self.assertEqual(raw_dump.read_text(encoding="utf-8"), '{"raw":true}\n')
            self.assertEqual(runtime_session.read_text(encoding="utf-8"), '{"session":"demo"}\n')
            self.assertEqual(
                list(shared_root.glob("workspace-outputs.*")),
                [],
                "staged runtime outputs should not be left behind after a failed rebuild",
            )

    def test_reset_rejects_unsafe_shared_root(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as unsafe_root:
            source_home_path = Path(source_home)
            unsafe_root_path = Path(unsafe_root)
            (unsafe_root_path / "sentinel").mkdir(parents=True, exist_ok=True)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(unsafe_root_path)

            blocked_reset = subprocess.run(
                [str(LAUNCHER), "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(blocked_reset.returncode, 2)
            self.assertTrue((unsafe_root_path / "sentinel").exists(), "unsafe root must not be deleted")

    def test_reset_removes_execution_worktree_with_shared_root(self) -> None:
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
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")

            launch_result = subprocess.run(
                [str(LAUNCHER), "start"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(launch_result.returncode, 0)

            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"
            self.assertTrue(workspace_dir.exists(), "start should create execution worktree")

            ready_file.unlink(missing_ok=True)
            (shared_root / "run" / "browser-cockpit.pid").unlink(missing_ok=True)

            reset_result = subprocess.run(
                [str(LAUNCHER), "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(reset_result.returncode, 0)
            self.assertFalse(workspace_dir.exists(), "reset should remove the execution worktree")
            self.assertFalse(shared_root.exists(), "reset should remove the shared launcher root")

    def test_start_rejects_workspace_dir_outside_shared_root(self) -> None:
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

            external_workspace = temp_root_path / "external-workspace"
            external_workspace.mkdir(parents=True, exist_ok=True)
            sentinel = external_workspace / "sentinel.txt"
            sentinel.write_text("do-not-delete\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")
            env["BUDDYSWITCH_WORKSPACE_DIR"] = str(external_workspace)

            completed = subprocess.run(
                [str(LAUNCHER), "start", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("workspace dir must be under BUDDYSWITCH_SHARED_ROOT", completed.stderr)
            self.assertTrue(sentinel.exists(), "external workspace sentinel must be preserved")

    def test_start_rejects_workspace_dir_with_parent_traversal_outside_shared_root(self) -> None:
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

            escaped_workspace = source_home_path / "escaped-workspace"
            escaped_workspace.mkdir(parents=True, exist_ok=True)
            sentinel = escaped_workspace / "sentinel.txt"
            sentinel.write_text("do-not-delete\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")
            env["BUDDYSWITCH_WORKSPACE_DIR"] = str(
                source_home_path / ".codex-buddyswitch" / ".." / "escaped-workspace"
            )

            completed = subprocess.run(
                [str(LAUNCHER), "start", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("workspace dir must be under BUDDYSWITCH_SHARED_ROOT", completed.stderr)
            self.assertTrue(sentinel.exists(), "traversal workspace sentinel must be preserved")

    def test_start_rejects_workspace_dir_equal_to_shared_root(self) -> None:
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

            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")
            env["BUDDYSWITCH_WORKSPACE_DIR"] = str(shared_root)

            completed = subprocess.run(
                [str(LAUNCHER), "start", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("workspace dir must be under BUDDYSWITCH_SHARED_ROOT", completed.stderr)
            self.assertFalse((shared_root / "workspace").exists(), "shared root itself must not become the workspace")

    def test_start_rejects_workspace_dir_inside_reserved_launcher_state(self) -> None:
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

            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")

            for relative in (
                "home/workspace",
                "codex-home/session",
                "run/workspace",
                "chrome/workspace",
            ):
                with self.subTest(relative=relative):
                    reserved_workspace = shared_root / relative
                    reserved_workspace.mkdir(parents=True, exist_ok=True)
                    sentinel = reserved_workspace / "sentinel.txt"
                    sentinel.write_text("do-not-delete\n", encoding="utf-8")

                    run_env = env.copy()
                    run_env["BUDDYSWITCH_TEST_CAPTURE"] = str(
                        temp_root_path / f"capture-{relative.replace('/', '-')}.json"
                    )
                    run_env["BUDDYSWITCH_WORKSPACE_DIR"] = str(reserved_workspace)

                    completed = subprocess.run(
                        [str(LAUNCHER), "start", "debug", "prompt-input", "switch pm: draft prd"],
                        cwd=ROOT,
                        env=run_env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("workspace dir must be under BUDDYSWITCH_SHARED_ROOT", completed.stderr)
                    self.assertTrue(sentinel.exists(), f"reserved workspace sentinel must be preserved for {relative}")
                    self.assertFalse((reserved_workspace / ".git").exists(), f"reserved workspace must not become a worktree for {relative}")


if __name__ == "__main__":
    unittest.main()
