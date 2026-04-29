#!/usr/bin/env python3
"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import json
import os
import shutil
import socket
import stat
import subprocess
import tempfile
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "buddyswitch-codex"
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


class BuddySwitchLauncherTests(unittest.TestCase):
    @staticmethod
    def _legacy_runtime_lock_path(shared_root: Path) -> Path:
        return Path(f"{shared_root}.lock")

    @staticmethod
    def _runtime_lock_path(shared_root: Path) -> Path:
        return shared_root / "run" / "locks" / "runtime.lock"

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
    "active_buddy": os.environ.get("BUDDYSWITCH_ACTIVE_BUDDY"),
    "instance_id": os.environ.get("BUDDYSWITCH_INSTANCE_ID"),
    "instance_json": os.environ.get("BUDDYSWITCH_INSTANCE_JSON"),
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

instance_payload = None
if entry["instance_json"]:
    instance_payload = json.loads(Path(entry["instance_json"]).read_text(encoding="utf-8"))

payload = {
    **entry,
    "launch_count": launch_count,
    "config_toml": (codex_home / "config.toml").read_text(encoding="utf-8"),
    "auth_json": json.loads((codex_home / "auth.json").read_text(encoding="utf-8")),
    "instance_json_payload": instance_payload,
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
  marker_payload=""
  marker_json="$(ls "${{BUDDYSWITCH_RUN_STATE_DIR}}"/launcher-*.json 2>/dev/null | head -n 1 || true)"
  marker_pid="$(ls "${{BUDDYSWITCH_RUN_STATE_DIR}}"/launcher-*.pid 2>/dev/null | head -n 1 || true)"
  if [[ -n "${{marker_json}}" ]]; then
    marker_state="json"
    marker_payload="$(python3 -c 'import json, sys; print(json.dumps(json.load(open(sys.argv[1], encoding="utf-8")), sort_keys=True))' "${{marker_json}}")"
  elif [[ -n "${{marker_pid}}" ]]; then
    marker_state="pid"
    marker_payload="$(cat "${{marker_pid}}")"
  fi
  printf '%s\\t%s\\t%s\\n' "$*" "$marker_state" "$marker_payload" >> "${{BUDDYSWITCH_TEST_GIT_CAPTURE}}"
fi

if [[ "${{BUDDYSWITCH_FAIL_WORKTREE_ADD:-0}}" == "1" && " $* " == *" worktree add "* ]]; then
  echo "simulated worktree add failure" >&2
  exit 1
fi

if [[ "${{BUDDYSWITCH_FAIL_WORKTREE_REMOVE:-0}}" == "1" && " $* " == *" worktree remove "* ]]; then
  echo "simulated worktree remove failure" >&2
  exit 1
fi

exec "$real_git" "$@"
""",
        )

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

    def _write_instance_record(
        self,
        shared_root: Path,
        instance_id: str,
        *,
        buddy: str = "pm",
        payload_instance_id: str | None = None,
        workspace_dir: Path | None = None,
        browser_port: int | None = None,
    ) -> tuple[Path, Path]:
        instance_root = shared_root / "instances" / instance_id
        instance_root.mkdir(parents=True, exist_ok=True)
        workspace_path = workspace_dir or instance_root / "workspace"
        (instance_root / "instance.json").write_text(
            json.dumps(
                {
                    "instance_id": payload_instance_id or instance_id,
                    "buddy": buddy,
                    "status": "inactive",
                    "current_task_id": "task-existing",
                    "current_track_id": "track-existing",
                    "workspace_dir": str(workspace_path),
                    "browser_port": browser_port,
                    "created_at": "2026-04-26T00:00:00Z",
                    "updated_at": "2026-04-26T00:00:01Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_root, workspace_path

    def _add_test_worktree(self, workspace_dir: Path) -> None:
        add = subprocess.run(
            ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(workspace_dir), "HEAD"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(add.returncode, 0, msg=add.stderr)
        self.addCleanup(
            subprocess.run,
            ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(workspace_dir)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.addCleanup(
            subprocess.run,
            ["git", "-C", str(ROOT), "worktree", "prune"],
            text=True,
            capture_output=True,
            check=False,
        )

    def _snapshot_tree(self, root: Path) -> list[str]:
        entries: list[str] = []
        if not root.exists():
            return entries
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if path.is_dir():
                entries.append(f"d:{rel}")
            elif path.is_symlink():
                entries.append(f"l:{rel}->{os.readlink(path)}")
            else:
                entries.append(f"f:{rel}:{path.read_bytes()!r}")
        return entries

    def _assert_removed_public_command(self, argv: list[str], hint: str) -> None:
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

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            before_home = self._snapshot_tree(source_home_path)
            completed = subprocess.run(
                [str(LAUNCHER), *argv],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            after_home = self._snapshot_tree(source_home_path)

            self.assertEqual(completed.returncode, 2, msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
            self.assertIn(hint, completed.stderr)
            self.assertEqual(before_home, after_home, "removed top-level commands must not mutate HOME state")
            self.assertFalse(capture_path.exists(), "removed top-level commands must not invoke codex")
            self.assertFalse((source_home_path / ".codex-buddyswitch").exists())

    def _assert_unknown_top_level_command(self, argv: list[str], unknown_name: str) -> None:
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

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            before_home = self._snapshot_tree(source_home_path)
            completed = subprocess.run(
                [str(LAUNCHER), *argv],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            after_home = self._snapshot_tree(source_home_path)

            self.assertEqual(completed.returncode, 2, msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
            self.assertIn(f"Unknown top-level command: {unknown_name}", completed.stderr)
            self.assertIn("Run: buddyswitch-codex help", completed.stderr)
            self.assertEqual(after_home, before_home, "unknown commands must not mutate HOME state")
            self.assertFalse(capture_path.exists(), "unknown top-level commands must not invoke codex")
            self.assertFalse((source_home_path / ".codex-buddyswitch").exists())

    def test_bare_codex_args_fail_closed_without_runtime_mutation(self) -> None:
        self.assertTrue(LAUNCHER.exists(), "expected root launcher to exist")
        self._assert_unknown_top_level_command(["debug", "prompt-input", "switch pm: draft prd"], "debug")

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
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "--", "debug", "prompt-input", "switch pm: draft prd"],
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
            workspace_dir = Path(payload["cwd"])
            self.assertEqual(payload["cwd"], str(workspace_dir.resolve()))
            agents_md = workspace_dir / "AGENTS.md"
            self.assertTrue(agents_md.exists(), "runtime workspace should include AGENTS.md")
            expected_agents = (ROOT / "tools" / "launcher" / "assets" / "buddies" / "pm" / "AGENTS.md").read_text(
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
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "switch pm: draft prd"],
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
            json_marker_rows = [line.split("\t", 2) for line in captures if "\tjson\t" in line]
            self.assertTrue(json_marker_rows, "launcher JSON marker should exist before workspace worktree bootstrap")
            payload = json.loads((temp_root_path / "capture.json").read_text(encoding="utf-8"))
            marker = json.loads(json_marker_rows[0][2])
            instance_root = source_home_path / ".codex-buddyswitch" / "instances" / payload["instance_id"]
            self.assertEqual(marker["instance_id"], payload["instance_id"])
            self.assertEqual(marker["buddy"], "pm")
            self.assertEqual(marker["workspace_dir"], str(instance_root / "workspace"))

    def test_start_with_buddy_wires_instance_env_and_lifecycle(self) -> None:
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

            capture_path = temp_root_path / "capture.json"
            calls_path = temp_root_path / "calls.jsonl"
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "switch pm: draft prd"],
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
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_snapshot = payload["instance_json_payload"]

            self.assertIn("BuddySwitch instance:", completed.stdout)
            self.assertIn(payload["instance_id"], completed.stdout)
            self.assertIn("Open existing:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance open {payload['instance_id']}", completed.stdout)
            self.assertIn("Delete instance:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance delete {payload['instance_id']} --yes", completed.stdout)

            self.assertEqual(payload["argv"], ["debug", "prompt-input", "switch pm: draft prd"])
            self.assertEqual(payload["active_buddy"], "pm")
            self.assertIsInstance(payload["instance_id"], str)
            self.assertTrue(payload["instance_id"])
            self.assertIsNotNone(payload["instance_json"])
            self.assertIsInstance(instance_snapshot, dict)

            instance_json_path = Path(payload["instance_json"])
            instance_root = shared_root / "instances" / payload["instance_id"]
            workspace_dir = instance_root / "workspace"
            self.assertTrue(instance_json_path.exists())
            self.assertEqual(payload["cwd"], str(workspace_dir.resolve()))
            self.assertEqual(payload["home"], str(instance_root / "home"))
            self.assertEqual(payload["codex_home"], str(instance_root / "codex-home"))
            self.assertEqual(payload["xdg_config_home"], str(instance_root / "xdg-config"))
            buddy_agents = ROOT / "tools" / "launcher" / "assets" / "buddies" / "pm" / "AGENTS.md"
            self.assertTrue(buddy_agents.exists(), "pm buddy prompt asset must be checked in")
            self.assertEqual((workspace_dir / "AGENTS.md").read_text(encoding="utf-8"), buddy_agents.read_text(encoding="utf-8"))
            self.assertTrue((workspace_dir / "AGENTS.md").read_text(encoding="utf-8").startswith("# BuddySwitch Runtime Workspace\n"))
            copied_agents = (workspace_dir / "AGENTS.md").read_text(encoding="utf-8").lower()
            for token in (
                "selected-skill preflight",
                "host_execution",
                "tool_scope",
                "persist-skill-result",
                "refreshed_context",
                "receipt -> commands -> summary",
            ):
                self.assertIn(token, copied_agents)
            self.assertTrue((instance_root / "browser" / "profile").exists())
            self.assertTrue((instance_root / "browser" / "chrome.pid").exists())
            self.assertTrue((instance_root / "browser" / "chrome.log").exists())
            self.assertFalse((shared_root / "chrome" / "shared-browser").exists())
            self.assertFalse((shared_root / "run" / "browser-cockpit.pid").exists())
            instance_auth = instance_root / "codex-home" / "auth.json"
            shared_auth = shared_root / "codex-home" / "auth.json"
            self.assertTrue(shared_auth.exists())
            self.assertTrue(instance_auth.exists())
            self.assertFalse(instance_auth.is_file() and not instance_auth.is_symlink())
            self.assertEqual(instance_auth.resolve(), shared_auth.resolve())
            self.assertEqual(instance_snapshot["status"], "active")
            self.assertEqual(instance_snapshot["instance_id"], payload["instance_id"])
            self.assertEqual(instance_snapshot["buddy"], "pm")
            self.assertIsNone(instance_snapshot["current_task_id"])
            self.assertIsNone(instance_snapshot["current_track_id"])
            self.assertEqual(instance_snapshot["workspace_dir"], str(workspace_dir))
            browser_port = instance_snapshot["browser_port"]
            self.assertIsInstance(browser_port, int)
            self.assertTrue(instance_snapshot["created_at"])
            self.assertTrue(instance_snapshot["updated_at"])

            stored_instance = json.loads(instance_json_path.read_text(encoding="utf-8"))
            self.assertEqual(stored_instance["status"], "inactive")
            self.assertEqual(stored_instance["instance_id"], payload["instance_id"])
            self.assertEqual(stored_instance["buddy"], "pm")
            self.assertEqual(stored_instance["workspace_dir"], str(workspace_dir))
            self.assertIsNone(stored_instance["current_task_id"])
            self.assertIsNone(stored_instance["current_track_id"])
            self.assertEqual(stored_instance["browser_port"], browser_port)
            self.assertTrue(stored_instance["created_at"])
            self.assertTrue(stored_instance["updated_at"])
            self.assertFalse((shared_root / "workspace").exists(), "buddy-locked start must not use legacy shared workspace")

            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            mcp_add_entries = [entry for entry in call_entries if entry["argv"][:2] == ["mcp", "add"]]
            mcp_add_names = [entry["argv"][2] for entry in mcp_add_entries]
            self.assertIn("chrome-devtools-cockpit", mcp_add_names)
            self.assertNotIn("chrome-devtools", mcp_add_names)
            cockpit_add = next(entry for entry in mcp_add_entries if entry["argv"][2] == "chrome-devtools-cockpit")
            self.assertIn(f"--browser-url=http://127.0.0.1:{browser_port}", cockpit_add["argv"])

            projection_pairs = {
                "buddyswitch/objects/tasks": shared_root / "state" / "buddyswitch" / "objects" / "tasks",
                "buddyswitch/objects/tracks": shared_root / "state" / "buddyswitch" / "objects" / "tracks",
                "buddyswitch/objects/artifacts": shared_root / "state" / "buddyswitch" / "objects" / "artifacts",
                "buddyswitch/content/runs": shared_root / "state" / "buddyswitch" / "content" / "runs",
            }
            for relative_path, state_path in projection_pairs.items():
                projected_path = workspace_dir / relative_path
                self.assertTrue(state_path.is_dir(), f"missing shared state dir: {state_path}")
                self.assertTrue(projected_path.is_symlink(), f"projection should be a symlink: {projected_path}")
                self.assertEqual(projected_path.resolve(), state_path.resolve())

            for relative_path in ("runs/raw", "projects/app/.runtime"):
                local_path = workspace_dir / relative_path
                self.assertTrue(local_path.is_dir(), f"missing instance-local runtime dir: {local_path}")
                self.assertFalse(local_path.is_symlink(), f"instance-local runtime dir must not be projected: {local_path}")

    def test_start_with_buddy_allocates_next_browser_port_when_default_is_busy(self) -> None:
        busy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            busy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            busy_socket.bind(("127.0.0.1", 9222))
            busy_socket.listen(1)
        except OSError as exc:
            busy_socket.close()
            self.skipTest(f"port 9222 is not available for the busy-port precondition: {exc}")
        self.addCleanup(busy_socket.close)

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

            capture_path = temp_root_path / "capture.json"
            calls_path = temp_root_path / "calls.jsonl"
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "switch pm: draft prd"],
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
            instance_json = json.loads(Path(payload["instance_json"]).read_text(encoding="utf-8"))
            self.assertEqual(instance_json["browser_port"], 9223)

            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            cockpit_add = next(entry for entry in call_entries if entry["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"])
            self.assertIn("--browser-url=http://127.0.0.1:9223", cockpit_add["argv"])

    def test_start_with_buddy_bootstrap_failure_does_not_leave_active_instance(self) -> None:
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

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_PORT"] = "65530"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(temp_root_path / "missing-chrome")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Chrome binary not found", completed.stderr)
            statuses = [
                json.loads(path.read_text(encoding="utf-8")).get("status")
                for path in (source_home_path / ".codex-buddyswitch" / "instances").glob("*/instance.json")
            ]
            self.assertNotIn("active", statuses)
            self.assertFalse((temp_root_path / "capture.json").exists(), "Codex should not launch after bootstrap failure")

    def test_start_with_unknown_buddy_fails_before_shared_root_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            capture_path = temp_root_path / "capture.json"

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "unknown", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Unknown buddy 'unknown'", completed.stderr)
            self.assertFalse(capture_path.exists(), "codex should not launch when buddy validation fails")
            self.assertFalse(shared_root.exists(), "invalid buddy must fail before shared root mutation")

    def test_buddy_list_prints_manifest_buddies_without_runtime_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "buddies"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("pm", completed.stdout)
            self.assertIn("dev", completed.stdout)
            self.assertIn("market", completed.stdout)
            self.assertFalse(shared_root.exists(), "instance buddies must not create runtime state")

    def test_instance_list_empty_points_to_start_buddy(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "list"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertIn("No BuddySwitch instances found.", completed.stdout)
            self.assertIn("./buddyswitch-codex instance start --buddy <buddy>", completed.stdout)

    def test_instance_list_prints_stored_instances_and_filters_by_buddy(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            for instance_id, buddy, task_id in (
                ("inst-pm-a", "pm", "task-pm-a"),
                ("inst-dev-b", "dev", "task-dev-b"),
            ):
                instance_root = shared_root / "instances" / instance_id
                instance_root.mkdir(parents=True, exist_ok=True)
                (instance_root / "instance.json").write_text(
                    json.dumps(
                        {
                            "instance_id": instance_id,
                            "buddy": buddy,
                            "status": "inactive",
                            "current_task_id": task_id,
                            "current_track_id": None,
                            "workspace_dir": str(instance_root / "workspace"),
                            "browser_port": None,
                            "created_at": "2026-04-26T00:00:00Z",
                            "updated_at": "2026-04-26T00:00:01Z",
                        },
                        ensure_ascii=True,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "list", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("inst-pm-a", completed.stdout)
            self.assertIn("pm", completed.stdout)
            self.assertIn("task-pm-a", completed.stdout)
            self.assertNotIn("inst-dev-b", completed.stdout)

    def test_instance_open_reuses_existing_instance_environment(self) -> None:
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
            first_capture = temp_root_path / "capture-start.json"
            second_capture = temp_root_path / "capture-open.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)

            start_env = env.copy()
            start_env["BUDDYSWITCH_TEST_CAPTURE"] = str(first_capture)
            start_result = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=start_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(start_result.returncode, 0, msg=start_result.stderr)

            first_payload = json.loads(first_capture.read_text(encoding="utf-8"))
            instance_id = first_payload["instance_id"]
            shared_root = source_home_path / ".codex-buddyswitch"

            open_env = env.copy()
            open_env["BUDDYSWITCH_TEST_CAPTURE"] = str(second_capture)
            open_result = subprocess.run(
                [str(LAUNCHER), "instance", "open", instance_id, "debug", "prompt-input", "continue"],
                cwd=ROOT,
                env=open_env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(open_result.returncode, 0, msg=open_result.stderr)
            second_payload = json.loads(second_capture.read_text(encoding="utf-8"))
            self.assertEqual(second_payload["instance_id"], instance_id)
            self.assertEqual(second_payload["instance_json"], first_payload["instance_json"])
            self.assertEqual(second_payload["cwd"], first_payload["cwd"])
            self.assertEqual(second_payload["home"], first_payload["home"])
            self.assertEqual(second_payload["codex_home"], first_payload["codex_home"])
            self.assertEqual(len(list((shared_root / "instances").glob("inst-*"))), 1)
            stored = json.loads(Path(second_payload["instance_json"]).read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "inactive")

    def test_instance_open_rejects_traversal_instance_id(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "open", "../bad"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Invalid instance id", completed.stderr)

    def test_instance_open_rejects_missing_instance_record(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "open", "inst-pm-missing"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Instance record missing", completed.stderr)

    def test_instance_open_rejects_instance_id_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            self._write_instance_record(shared_root, "inst-pm-record", payload_instance_id="inst-pm-other")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "open", "inst-pm-record"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Instance id mismatch", completed.stderr)

    def test_instance_open_rejects_unknown_buddy(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            self._write_instance_record(shared_root, "inst-unknown-buddy", buddy="unknown")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "open", "inst-unknown-buddy"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Unknown buddy 'unknown'", completed.stderr)

    def test_instance_open_rejects_missing_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            self._write_instance_record(shared_root, "inst-pm-missing-workspace")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "open", "inst-pm-missing-workspace"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 3)
            self.assertIn("Instance open blocked", completed.stderr)
            self.assertIn("delete this instance or start a new one", completed.stderr)

    def test_instance_open_rejects_active_target_instance(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root, workspace_dir = self._write_instance_record(shared_root, "inst-pm-active")
            self._add_test_worktree(workspace_dir)
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / f"launcher-{os.getpid()}.json").write_text(
                json.dumps({"pid": os.getpid(), "instance_id": "inst-pm-active"}, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "open", "inst-pm-active"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 3)
            self.assertIn("Instance open blocked: inst-pm-active is already active.", completed.stderr)
            self.assertTrue(instance_root.exists())

    def test_instance_open_rejects_live_legacy_launcher_marker(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            self._write_instance_record(shared_root, "inst-pm-legacy-live")
            self._add_test_worktree(shared_root / "instances" / "inst-pm-legacy-live" / "workspace")
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "launcher-current.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "open", "inst-pm-legacy-live"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 3)
            self.assertIn("live legacy launcher marker exists", completed.stderr)

    def test_instance_open_bootstrap_failure_leaves_instance_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            _, workspace_dir = self._write_instance_record(shared_root, "inst-pm-open-bootstrap-fail")
            self._add_test_worktree(workspace_dir)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_PORT"] = "65530"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(temp_root_path / "missing-chrome")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "open", "inst-pm-open-bootstrap-fail", "debug", "prompt-input", "continue"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Chrome binary not found", completed.stderr)
            stored = json.loads((shared_root / "instances" / "inst-pm-open-bootstrap-fail" / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "inactive")
            self.assertFalse((temp_root_path / "capture.json").exists(), "Codex should not launch after bootstrap failure")

    def test_locked_instance_open_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_OPEN_INSTANCE_ID"] = "inst-pm-direct"

            completed = subprocess.run(
                [str(LAUNCHER), "__locked-instance-open-bootstrap"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("runtime lock required", completed.stderr)

    def test_instance_delete_removes_only_target_instance_without_shared_state(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, target_workspace = self._write_instance_record(shared_root, "inst-pm-delete")
            other_root, _ = self._write_instance_record(shared_root, "inst-dev-keep", buddy="dev")
            state_task = shared_root / "state" / "buddyswitch" / "objects" / "tasks" / "task-keep.json"
            state_task.parent.mkdir(parents=True, exist_ok=True)
            state_task.write_text('{"id":"task-keep"}\n', encoding="utf-8")
            self._add_test_worktree(target_workspace)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-delete", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
            self.assertIn("Instance deleted: inst-pm-delete", delete_result.stdout)
            self.assertFalse(target_root.exists())
            self.assertTrue(other_root.exists())
            self.assertTrue(state_task.exists())
            worktree_list = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotIn(str(target_workspace), worktree_list.stdout)

    def test_instance_delete_without_yes_previews_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "inst-pm-keep")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-keep"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0)
            self.assertIn("BuddySwitch instance delete preview", delete_result.stdout)
            self.assertIn("Instance root:", delete_result.stdout)
            self.assertIn("Shared state kept:", delete_result.stdout)
            self.assertTrue(target_root.exists())

    def test_instance_delete_rejects_traversal_instance_id(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            outside_path = source_home_path / "bad"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "../bad", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 2)
            self.assertIn("Invalid instance id", delete_result.stderr)
            self.assertFalse(outside_path.exists())

    def test_instance_delete_rejects_missing_target(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-missing", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 2)
            self.assertIn("Instance record missing", delete_result.stderr)

    def test_instance_delete_blocks_active_target_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "inst-pm-live-launcher")
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / f"launcher-{os.getpid()}.json").write_text(
                json.dumps({"pid": os.getpid(), "instance_id": "inst-pm-live-launcher"}, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-live-launcher", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn("Instance delete blocked: inst-pm-live-launcher is active.", delete_result.stderr)
            self.assertTrue(target_root.exists())

    def test_instance_delete_blocks_active_target_browser_pid(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "inst-pm-live-browser-pid")
            browser_dir = target_root / "browser"
            browser_dir.mkdir(parents=True, exist_ok=True)
            (browser_dir / "chrome.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-live-browser-pid", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn("active browser cockpit", delete_result.stderr)
            self.assertTrue(target_root.exists())

    def test_instance_delete_blocks_live_target_browser_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "inst-pm-live-browser-endpoint", browser_port=9333)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_exec(
                fake_bin / "curl",
                """#!/usr/bin/env bash
for arg in "$@"; do
  if [[ "${arg}" == "http://127.0.0.1:9333/json/version" ]]; then
    exit 0
  fi
done
exit 1
""",
            )
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-live-browser-endpoint", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn("active browser cockpit", delete_result.stderr)
            self.assertTrue(target_root.exists())

    def test_instance_delete_blocks_live_legacy_launcher_marker(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "inst-pm-legacy-delete")
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "launcher-current.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-legacy-delete", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn("live legacy launcher marker exists", delete_result.stderr)
            self.assertTrue(target_root.exists())

    def test_instance_delete_blocks_worktree_deregistration_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, target_workspace = self._write_instance_record(shared_root, "inst-pm-remove-fail")
            self._add_test_worktree(target_workspace)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_git(fake_bin / "git")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_FAIL_WORKTREE_REMOVE"] = "1"

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-remove-fail", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(delete_result.returncode, 0)
            self.assertIn("simulated worktree remove failure", delete_result.stderr)
            self.assertTrue(target_root.exists())

    def test_instance_delete_rejects_symlinked_instance_root_without_touching_external_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as external_root:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instances_root = shared_root / "instances"
            instances_root.mkdir(parents=True, exist_ok=True)
            external_instance_root = Path(external_root) / "external-instance"
            external_workspace = external_instance_root / "workspace"
            external_instance_root.mkdir(parents=True, exist_ok=True)
            (external_instance_root / "instance.json").write_text(
                json.dumps(
                    {
                        "instance_id": "inst-pm-symlink",
                        "buddy": "pm",
                        "status": "inactive",
                        "current_task_id": "task-existing",
                        "current_track_id": "track-existing",
                        "workspace_dir": str(external_workspace),
                        "browser_port": None,
                        "created_at": "2026-04-26T00:00:00Z",
                        "updated_at": "2026-04-26T00:00:01Z",
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            sentinel = external_instance_root / "sentinel.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            self._add_test_worktree(external_workspace)
            (instances_root / "inst-pm-symlink").symlink_to(external_instance_root, target_is_directory=True)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-symlink", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn("unsafe instance root", delete_result.stderr)
            self.assertTrue((instances_root / "inst-pm-symlink").is_symlink())
            self.assertTrue(sentinel.exists())
            worktree_list = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertIn(str(external_workspace), worktree_list.stdout)

    def test_instance_delete_rejects_symlinked_shared_root_without_touching_target_instance(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as external_root:
            source_home_path = Path(source_home)
            external_root_path = Path(external_root)
            real_shared_root = external_root_path / ".codex-buddyswitch"
            instance_root, _ = self._write_instance_record(
                real_shared_root,
                "inst-pm-shared-root-symlink",
            )
            sentinel = instance_root / "sentinel.txt"
            sentinel.write_text("keep\n", encoding="utf-8")

            shared_root_link = source_home_path / ".codex-buddyswitch"
            shared_root_link.symlink_to(real_shared_root, target_is_directory=True)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-shared-root-symlink", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn("unsafe shared root", delete_result.stderr)
            self.assertTrue(shared_root_link.is_symlink())
            self.assertTrue(instance_root.exists())
            self.assertTrue(sentinel.exists())

    def test_locked_instance_delete_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_DELETE_INSTANCE_ID"] = "inst-pm-direct"

            completed = subprocess.run(
                [str(LAUNCHER), "__locked-instance-delete"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("runtime lock required", completed.stderr)

    def test_start_without_buddy_does_not_set_instance_env_vars(self) -> None:
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

            capture_path = temp_root_path / "capture.json"
            calls_path = temp_root_path / "calls.jsonl"
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_ACTIVE_BUDDY"] = "leaked-buddy"
            env["BUDDYSWITCH_INSTANCE_ID"] = "leaked-instance-id"
            env["BUDDYSWITCH_INSTANCE_JSON"] = str(temp_root_path / "leaked-instance.json")

            completed = subprocess.run(
                [str(LAUNCHER), "start", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("Top-level command removed: start", completed.stderr)
            self.assertIn("instance start --buddy <buddy>", completed.stderr)
            self.assertFalse(capture_path.exists(), "removed start command must not invoke codex")
            self.assertFalse((source_home_path / ".codex-buddyswitch").exists())

    def test_start_with_buddy_requires_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            capture_path = temp_root_path / "capture.json"

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Missing value for --buddy", completed.stderr)
            self.assertFalse(capture_path.exists(), "codex should not launch when --buddy is malformed")
            self.assertFalse(shared_root.exists(), "malformed --buddy must fail before shared root mutation")

    def test_locked_start_bootstrap_revalidates_buddy_before_instance_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_START_BUDDY"] = "unknown"
            env["BUDDYSWITCH_START_INSTANCE_ID"] = "inst-unknown-demo"

            direct_start = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
                    str(LAUNCHER),
                    "__locked-start-bootstrap",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(direct_start.returncode, 0)
            self.assertIn("Unknown buddy 'unknown'", direct_start.stderr)
            self.assertFalse((shared_root / "instances").exists(), "invalid locked buddy must not create instances")

    def test_locked_instance_inactive_rejects_traversal_instance_id(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            outside_path = source_home_path / "outside.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

            direct_inactive = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
                    str(LAUNCHER),
                    "__locked-instance-set-inactive",
                    "../outside",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_inactive.returncode, 2)
            self.assertIn("Invalid instance id", direct_inactive.stderr)
            self.assertFalse(outside_path.exists(), "traversal instance id must not write outside instances root")

    def test_locked_start_bootstrap_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            direct_start = subprocess.run(
                [str(LAUNCHER), "__locked-start-bootstrap"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_start.returncode, 2)
            self.assertIn("runtime lock required", direct_start.stderr)
            self.assertFalse(shared_root.exists(), "direct locked start bootstrap must not mutate shared root")

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
            self.assertIn("buddyswitch-codex instance buddies", help_result.stdout)
            self.assertIn("buddyswitch-codex instance start --buddy <buddy>", help_result.stdout)
            self.assertIn("buddyswitch-codex data cleanup --buddy <buddy>", help_result.stdout)
            self.assertIn("buddyswitch-codex env status", help_result.stdout)
            self.assertIn("buddyswitch-codex env reset [--yes]", help_result.stdout)
            self.assertIn("buddyswitch-codex help", help_result.stdout)
            self.assertIn("  instance", help_result.stdout)
            self.assertIn("  data", help_result.stdout)
            self.assertIn("  env", help_result.stdout)
            self.assertIn("  help", help_result.stdout)
            self.assertNotIn("buddyswitch-codex [codex args...]", help_result.stdout)
            self.assertNotIn("buddyswitch-codex start", help_result.stdout)
            self.assertNotIn("buddyswitch-codex buddy", help_result.stdout)
            self.assertNotIn("buddyswitch-codex cleanup", help_result.stdout)
            self.assertNotIn("buddyswitch-codex reset", help_result.stdout)
            self.assertNotIn("buddyswitch-codex browser", help_result.stdout)
            self.assertNotIn("buddyswitch-codex workspace", help_result.stdout)

    def test_legacy_public_commands_fail_closed_with_hints(self) -> None:
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

            command_hints = (
                ("start", "instance start --buddy <buddy>"),
                ("buddy", "instance buddies"),
                ("cleanup", "data cleanup"),
                ("reset", "env reset --yes"),
                ("browser", "env browser status"),
                ("workspace", "No public replacement"),
            )
            for command, hint in command_hints:
                with self.subTest(command=command):
                    capture_path.unlink(missing_ok=True)
                    result = subprocess.run(
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
                        msg=f"legacy command should fail closed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                    )
                    self.assertIn(hint, result.stderr)
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

            debug_result = subprocess.run(
                [str(LAUNCHER), "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                debug_result.returncode,
                2,
                msg=f"unknown top-level command should fail closed\nstdout:\n{debug_result.stdout}\nstderr:\n{debug_result.stderr}",
            )
            self.assertIn("Unknown top-level command: debug", debug_result.stderr)
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

            cleanup_result = subprocess.run(
                [str(LAUNCHER), "cleanup", "--all-agents", "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(cleanup_result.returncode, 2)
            self.assertIn("Top-level command removed: cleanup", cleanup_result.stderr)
            self.assertIn("data cleanup", cleanup_result.stderr)
            self.assertFalse(capture_path.exists(), "removed cleanup command must not start Codex")
            self.assertFalse(shared_root.exists(), "removed cleanup command must not create shared state")

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
                [str(LAUNCHER), "env", "reset", "--yes"],
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
                [str(LAUNCHER), "env", "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(blocked_reset.returncode, 3)
            self.assertTrue(shared_root.exists(), "active browser marker should block reset")

    def test_reset_is_blocked_when_active_instance_browser_marker_exists(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-live-browser"
            instance_root = shared_root / "instances" / instance_id
            browser_dir = instance_root / "browser"
            browser_profile_dir = browser_dir / "profile"
            browser_profile_dir.mkdir(parents=True, exist_ok=True)
            (browser_dir / "chrome.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
            (instance_root / "instance.json").write_text(
                json.dumps(
                    {
                        "instance_id": instance_id,
                        "buddy": "pm",
                        "status": "inactive",
                        "workspace_dir": str(instance_root / "workspace"),
                        "browser_port": 9223,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            blocked_reset = subprocess.run(
                [str(LAUNCHER), "env", "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(blocked_reset.returncode, 3)
            self.assertTrue(shared_root.exists(), "active instance browser marker should block reset")
            self.assertTrue(browser_profile_dir.exists(), "blocked reset must not delete active instance profile")

    def test_reset_blocks_live_instance_browser_without_pid_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-live-endpoint"
            instance_root = shared_root / "instances" / instance_id
            instance_root.mkdir(parents=True, exist_ok=True)
            (instance_root / "instance.json").write_text(
                json.dumps(
                    {
                        "instance_id": instance_id,
                        "buddy": "pm",
                        "status": "inactive",
                        "workspace_dir": str(instance_root / "workspace"),
                        "browser_port": 9333,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_exec(
                fake_bin / "curl",
                """#!/usr/bin/env bash
for arg in "$@"; do
  if [[ "${arg}" == "http://127.0.0.1:9333/json/version" ]]; then
    exit 0
  fi
done
exit 1
""",
            )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            blocked_reset = subprocess.run(
                [str(LAUNCHER), "env", "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(blocked_reset.returncode, 3)
            self.assertIn("active browser cockpit", blocked_reset.stderr)
            self.assertTrue(shared_root.exists())

    def test_reset_is_blocked_when_runtime_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            sentinel = shared_root / "sentinel.txt"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("do-not-delete\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"] = LOCK_TIMEOUT_SECONDS

            lock_path = self._runtime_lock_path(shared_root)
            holder = self._spawn_lock_holder(lock_path)
            try:
                blocked_reset = subprocess.run(
                    [str(LAUNCHER), "env", "reset", "--yes"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                self._stop_lock_holder(holder)

            self.assertEqual(blocked_reset.returncode, RUNTIME_LOCK_BUSY_EXIT_CODE)
            self.assertIn("runtime state busy", blocked_reset.stderr)
            self.assertTrue(shared_root.exists(), "reset must not remove shared root while lock is held")
            self.assertTrue(sentinel.exists(), "reset must not mutate locked shared root")

    def test_locked_reset_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            sentinel = shared_root / "sentinel.txt"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("do-not-delete\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            direct_reset = subprocess.run(
                [str(LAUNCHER), "__locked-reset"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_reset.returncode, 2)
            self.assertIn("runtime lock required", direct_reset.stderr)
            self.assertTrue(shared_root.exists(), "direct locked entrypoint must not remove shared root")
            self.assertTrue(sentinel.exists(), "direct locked entrypoint must not mutate shared root")

    def test_lock_helper_wrapped_reset_still_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            sentinel = shared_root / "sentinel.txt"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("do-not-delete\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

            direct_reset = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
                    str(LAUNCHER),
                    "__locked-reset",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_reset.returncode, 1)
            self.assertIn("Reset requires explicit confirmation", direct_reset.stderr)
            self.assertTrue(sentinel.exists(), "helper-wrapped locked reset must not bypass --yes")

    def test_lock_helper_wrapped_reset_still_validates_reset_root(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            unsafe_root = source_home_path / "not-buddyswitch"
            sentinel = unsafe_root / "sentinel.txt"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("do-not-delete\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(unsafe_root)

            direct_reset = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
                    str(LAUNCHER),
                    "__locked-reset",
                    "--yes",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_reset.returncode, 2)
            self.assertIn("Reset blocked", direct_reset.stderr)
            self.assertTrue(sentinel.exists(), "helper-wrapped locked reset must not bypass root validation")

    def test_runtime_lock_helper_writes_lock_and_proof_under_shared_root_run_locks(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            source_home_path = Path(source_home)
            temp_root_path = Path(temp_root)
            shared_root = source_home_path / ".codex-buddyswitch"
            proof_capture_path = temp_root_path / "proof-capture.json"

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_TEST_PROOF_CAPTURE"] = str(proof_capture_path)

            capture_script = (
                "import json, os\n"
                "from pathlib import Path\n"
                "proof_path = Path(os.environ['BUDDYSWITCH_RUNTIME_LOCK_PROOF'])\n"
                "payload = {\n"
                "  'proof_path': str(proof_path),\n"
                "  'proof_parent': str(proof_path.parent),\n"
                "  'proof_exists': proof_path.exists(),\n"
                "}\n"
                "Path(os.environ['BUDDYSWITCH_TEST_PROOF_CAPTURE']).write_text(\n"
                "  json.dumps(payload, ensure_ascii=True),\n"
                "  encoding='utf-8',\n"
                ")\n"
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
                    sys.executable,
                    "-c",
                    capture_script,
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(proof_capture_path.exists(), "locked child must capture inherited proof metadata")

            lock_path = self._legacy_runtime_lock_path(shared_root)
            new_lock_path = self._runtime_lock_path(shared_root)
            self.assertFalse(lock_path.exists())
            self.assertTrue(new_lock_path.exists())

            proof_payload = json.loads(proof_capture_path.read_text(encoding="utf-8"))
            self.assertTrue(proof_payload["proof_exists"])
            self.assertEqual(Path(proof_payload["proof_parent"]), shared_root / "run" / "locks")

    def test_runtime_lock_assert_held_reports_controlled_failure_without_lock_dir(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            source_home_path = Path(source_home)
            temp_root_path = Path(temp_root)
            shared_root = source_home_path / ".codex-buddyswitch"
            proof_path = temp_root_path / "stale-proof"
            proof_path.write_text("stale-token", encoding="utf-8")

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_RUNTIME_LOCK_PROOF"] = str(proof_path)
            env["BUDDYSWITCH_RUNTIME_LOCK_TOKEN"] = "stale-token"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--assert-held",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("runtime lock required", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertFalse(self._legacy_runtime_lock_path(shared_root).exists())

    def test_runtime_lock_assert_held_reports_controlled_failure_when_lock_dir_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            source_home_path = Path(source_home)
            temp_root_path = Path(temp_root)
            shared_root = source_home_path / ".codex-buddyswitch"
            shared_root.mkdir(parents=True)
            (shared_root / "run").write_text("not a directory\n", encoding="utf-8")
            proof_path = temp_root_path / "stale-proof"
            proof_path.write_text("stale-token", encoding="utf-8")

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_RUNTIME_LOCK_PROOF"] = str(proof_path)
            env["BUDDYSWITCH_RUNTIME_LOCK_TOKEN"] = "stale-token"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--assert-held",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("runtime lock required", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertFalse(self._legacy_runtime_lock_path(shared_root).exists())

    def test_runtime_lock_is_not_inherited_by_background_children(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            source_home_path = Path(source_home)
            temp_root_path = Path(temp_root)
            shared_root = source_home_path / ".codex-buddyswitch"
            child_pid_path = temp_root_path / "background-child.pid"

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_TEST_CHILD_PID"] = str(child_pid_path)
            env["BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"] = LOCK_TIMEOUT_SECONDS

            first = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
                    "bash",
                    "-c",
                    'sleep 30 >/dev/null 2>&1 & printf "%s\\n" "$!" > "${BUDDYSWITCH_TEST_CHILD_PID}"',
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            self.assertTrue(child_pid_path.exists(), "precondition: locked command started a background child")

            try:
                second = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                        "--",
                        sys.executable,
                        "-c",
                        "print('lock reacquired')",
                    ],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                child_pid = child_pid_path.read_text(encoding="utf-8").strip()
                subprocess.run(["kill", child_pid], text=True, capture_output=True, check=False)

            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertIn("lock reacquired", second.stdout)

    def test_runtime_lock_terminates_child_before_releasing_lock_on_signal(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            source_home_path = Path(source_home)
            temp_root_path = Path(temp_root)
            shared_root = source_home_path / ".codex-buddyswitch"
            child_pid_path = temp_root_path / "child.pid"
            mutation_path = temp_root_path / "mutated.txt"

            child_script = (
                "import os, sys, time\n"
                "from pathlib import Path\n"
                "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
                "time.sleep(1)\n"
                "Path(sys.argv[2]).write_text('mutated\\n', encoding='utf-8')\n"
                "time.sleep(30)\n"
            )

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

            wrapper = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
                    sys.executable,
                    "-c",
                    child_script,
                    str(child_pid_path),
                    str(mutation_path),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                for _ in range(50):
                    if child_pid_path.exists():
                        break
                    time.sleep(0.05)
                self.assertTrue(child_pid_path.exists(), "precondition: child process started")

                wrapper.terminate()
                wrapper.wait(timeout=5)
                time.sleep(1.2)

                self.assertFalse(mutation_path.exists(), "child must not keep mutating after lock wrapper terminates")
            finally:
                if wrapper.poll() is None:
                    wrapper.kill()
                    wrapper.wait(timeout=5)
                if child_pid_path.exists():
                    child_pid = child_pid_path.read_text(encoding="utf-8").strip()
                    subprocess.run(["kill", child_pid], text=True, capture_output=True, check=False)

    def test_runtime_lock_rejects_non_finite_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"] = "nan"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
                    sys.executable,
                    "-c",
                    "print('should not run')",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("timeout must be finite", completed.stderr)
            self.assertNotIn("should not run", completed.stdout)

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
            self.assertEqual(blocked_sync.returncode, 2)
            self.assertIn("Top-level command removed: workspace", blocked_sync.stderr)
            self.assertIn("No public replacement", blocked_sync.stderr)
            self.assertFalse((shared_root / "workspace").exists(), "blocked sync must not create the workspace")

    def test_workspace_sync_is_blocked_when_runtime_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"] = LOCK_TIMEOUT_SECONDS

            lock_path = self._runtime_lock_path(shared_root)
            holder = self._spawn_lock_holder(lock_path)
            try:
                blocked_sync = subprocess.run(
                    [str(LAUNCHER), "workspace", "sync"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                self._stop_lock_holder(holder)
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

            self.assertEqual(blocked_sync.returncode, 2)
            self.assertIn("Top-level command removed: workspace", blocked_sync.stderr)
            self.assertFalse(workspace_dir.exists(), "blocked sync must not mutate workspace")

    def test_workspace_sync_fails_closed_when_instances_tree_exists(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_json = shared_root / "instances" / "inst-pm-existing" / "instance.json"
            instance_json.parent.mkdir(parents=True, exist_ok=True)
            instance_json.write_text('{"instance_id":"inst-pm-existing","buddy":"pm"}\n', encoding="utf-8")

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

            self.assertEqual(blocked_sync.returncode, 2)
            self.assertIn("Top-level command removed: workspace", blocked_sync.stderr)
            self.assertFalse((shared_root / "workspace").exists(), "blocked sync must not create legacy workspace")

    def test_start_with_buddy_migrates_legacy_durable_state_to_shared_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
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

            legacy_workspace = shared_root / "workspace"
            legacy_task = legacy_workspace / "buddyswitch" / "objects" / "tasks" / "task-demo.json"
            legacy_run = legacy_workspace / "buddyswitch" / "content" / "runs" / "run-demo.json"
            legacy_reserved = legacy_workspace / "buddyswitch" / "content" / "runs" / "reserved" / "run-old.json"
            legacy_raw = legacy_workspace / "runs" / "raw" / "dump.json"
            legacy_runtime = legacy_workspace / "projects" / "app" / ".runtime" / "session.json"
            for path, payload in (
                (legacy_task, {"id": "task-demo", "buddy": "pm"}),
                (legacy_run, {"run_id": "run-demo", "switch": {"buddy": "pm"}}),
                (legacy_reserved, {"run_id": "run-old", "status": "reserved"}),
                (legacy_raw, {"raw": True}),
                (legacy_runtime, {"session": "demo"}),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "switch pm: draft prd"],
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
            self.assertEqual(
                (shared_root / "state" / "buddyswitch" / "objects" / "tasks" / "task-demo.json").read_text(
                    encoding="utf-8"
                ),
                '{"id": "task-demo", "buddy": "pm"}\n',
            )
            self.assertEqual(
                (shared_root / "state" / "buddyswitch" / "content" / "runs" / "run-demo.json").read_text(
                    encoding="utf-8"
                ),
                '{"run_id": "run-demo", "switch": {"buddy": "pm"}}\n',
            )
            self.assertFalse(legacy_task.exists(), "legacy durable task should move into shared state")
            self.assertFalse(legacy_run.exists(), "legacy durable run should move into shared state")
            self.assertFalse(legacy_reserved.exists(), "legacy reservations should be pruned, not migrated")
            self.assertTrue(legacy_raw.exists(), "legacy raw runtime scratch must not migrate into shared state")
            self.assertTrue(legacy_runtime.exists(), "legacy app runtime scratch must not migrate into shared state")

    def test_env_browser_status_instance_defaults_and_explicit_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-browser-status"
            instance_root, _ = self._write_instance_record(shared_root, instance_id, browser_port=9333)

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_curl(fake_bin / "curl")
            ready_file = temp_root_path / "browser-ready.flag"
            ready_file.write_text("ready\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)

            status_default = subprocess.run(
                [str(LAUNCHER), "env", "browser", "status", "--instance", instance_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_default.returncode, 0, msg=status_default.stderr)
            self.assertIn("Browser cockpit reachable: http://127.0.0.1:9333", status_default.stdout)
            self.assertIn(f"Profile: {instance_root / 'browser' / 'profile'}", status_default.stdout)

            explicit_profile = temp_root_path / "browser-profile-status"
            status_explicit = subprocess.run(
                [
                    str(LAUNCHER),
                    "env",
                    "browser",
                    "status",
                    "--instance",
                    instance_id,
                    "--port",
                    "9444",
                    "--profile-dir",
                    str(explicit_profile),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_explicit.returncode, 0, msg=status_explicit.stderr)
            self.assertIn("Browser cockpit reachable: http://127.0.0.1:9444", status_explicit.stdout)
            self.assertIn(f"Profile: {explicit_profile}", status_explicit.stdout)

            instance_json = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_json["browser_port"], 9333)

    def test_env_browser_status_rejects_invalid_port_before_endpoint_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_exec(
                fake_bin / "curl",
                """#!/usr/bin/env bash
if [[ -n "${BUDDYSWITCH_TEST_CURL_CALLED_FILE:-}" ]]; then
  touch "${BUDDYSWITCH_TEST_CURL_CALLED_FILE}"
fi
exit 0
""",
            )
            curl_called_path = temp_root_path / "curl-called.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CURL_CALLED_FILE"] = str(curl_called_path)

            status_invalid_port = subprocess.run(
                [str(LAUNCHER), "env", "browser", "status", "--port", "abc"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_invalid_port.returncode, 2)
            self.assertIn("Invalid value for --port: abc", status_invalid_port.stderr)
            self.assertFalse(curl_called_path.exists(), "invalid --port must fail before endpoint checks")
            self.assertFalse(shared_root.exists(), "invalid status args should stay read-only")

    def test_env_browser_ensure_rejects_invalid_port_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-browser-invalid-port"
            instance_root, _ = self._write_instance_record(shared_root, instance_id, browser_port=9333)

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
            self._write_exec(
                fake_bin / "curl",
                """#!/usr/bin/env bash
if [[ -n "${BUDDYSWITCH_TEST_CURL_CALLED_FILE:-}" ]]; then
  touch "${BUDDYSWITCH_TEST_CURL_CALLED_FILE}"
fi
exit 0
""",
            )
            self._write_fake_chrome(fake_bin / "fake-chrome")

            calls_path = temp_root_path / "calls.jsonl"
            curl_called_path = temp_root_path / "curl-called.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_CURL_CALLED_FILE"] = str(curl_called_path)

            ensure_invalid_port = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", instance_id, "--port", "70000"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ensure_invalid_port.returncode, 2)
            self.assertIn("Invalid value for --port: 70000", ensure_invalid_port.stderr)
            self.assertFalse(curl_called_path.exists(), "invalid --port must fail before endpoint checks")
            self.assertFalse(calls_path.exists(), "invalid --port must fail before MCP updates")
            self.assertFalse(
                (instance_root / "browser").exists(),
                "invalid --port must fail before browser profile/bootstrap side effects",
            )
            instance_json = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_json["browser_port"], 9333)

    def test_env_browser_ensure_rejects_invalid_port_before_runtime_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-lock-invalid-port"
            instance_root, _ = self._write_instance_record(shared_root, instance_id, browser_port=9333)

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_exec(
                fake_bin / "curl",
                """#!/usr/bin/env bash
if [[ -n "${BUDDYSWITCH_TEST_CURL_CALLED_FILE:-}" ]]; then
  touch "${BUDDYSWITCH_TEST_CURL_CALLED_FILE}"
fi
exit 0
""",
            )
            curl_called_path = temp_root_path / "curl-called.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CURL_CALLED_FILE"] = str(curl_called_path)
            env["BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"] = LOCK_TIMEOUT_SECONDS

            lock_path = self._runtime_lock_path(shared_root)
            holder = self._spawn_lock_holder(lock_path)
            try:
                ensure_invalid_port = subprocess.run(
                    [str(LAUNCHER), "env", "browser", "ensure", "--instance", instance_id, "--port", "70000"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                self._stop_lock_holder(holder)

            self.assertEqual(ensure_invalid_port.returncode, 2)
            self.assertIn("Invalid value for --port: 70000", ensure_invalid_port.stderr)
            self.assertNotIn("runtime state busy", ensure_invalid_port.stderr)
            self.assertFalse(curl_called_path.exists(), "invalid --port must fail before endpoint checks")
            self.assertFalse(
                (instance_root / "browser").exists(),
                "invalid --port must fail before browser profile/bootstrap side effects",
            )

    def test_env_browser_ensure_instance_explicit_overrides_profile_and_updates_port(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-browser-ensure"
            instance_root, _ = self._write_instance_record(shared_root, instance_id, browser_port=9333)

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
            explicit_profile = temp_root_path / "explicit-profile-ensure"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)

            ensure_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "env",
                    "browser",
                    "ensure",
                    "--instance",
                    instance_id,
                    "--port",
                    "9444",
                    "--profile-dir",
                    str(explicit_profile),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ensure_result.returncode, 0, msg=ensure_result.stderr)
            self.assertIn("http://127.0.0.1:9444", ensure_result.stdout)
            self.assertIn(f"Profile: {explicit_profile}", ensure_result.stdout)
            self.assertTrue(explicit_profile.is_dir(), "explicit profile dir should be created by ensure")
            self.assertFalse(
                (instance_root / "browser" / "profile").exists(),
                "explicit profile dir should prevent default instance profile directory creation",
            )

            instance_json = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_json["browser_port"], 9444)

            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            cockpit_add = next(entry for entry in call_entries if entry["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"])
            self.assertIn("--browser-url=http://127.0.0.1:9444", cockpit_add["argv"])

    def test_env_browser_ensure_repairs_stale_cockpit_mcp_browser_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-browser-stale-mcp"
            instance_root, _ = self._write_instance_record(shared_root, instance_id, browser_port=9333)

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

            instance_codex_home = instance_root / "codex-home"
            instance_codex_home.mkdir(parents=True, exist_ok=True)
            (instance_codex_home / "config.toml").write_text(
                """[skills.bundled]
enabled = false

[features]
plugins = false

[mcp_servers.chrome-devtools-cockpit]
command = "npx"
args = ["chrome-devtools-mcp@latest", "--browser-url=http://127.0.0.1:9333"]
""",
                encoding="utf-8",
            )

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            ready_file = temp_root_path / "browser-ready.flag"
            capture_path = temp_root_path / "capture.json"
            calls_path = temp_root_path / "calls.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)

            ensure_result = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", instance_id, "--port", "9444"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ensure_result.returncode, 0, msg=ensure_result.stderr)

            instance_json = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_json["browser_port"], 9444)

            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            remove_index = next(
                index
                for index, entry in enumerate(call_entries)
                if entry["argv"][:3] == ["mcp", "remove", "chrome-devtools-cockpit"]
            )
            add_index = next(
                index
                for index, entry in enumerate(call_entries)
                if entry["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"]
            )
            self.assertLess(remove_index, add_index)
            cockpit_add = call_entries[add_index]
            self.assertIn("--browser-url=http://127.0.0.1:9444", cockpit_add["argv"])

    def test_browser_ensure_is_blocked_when_runtime_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            self._write_instance_record(shared_root, "inst-pm-browser-lock")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"] = LOCK_TIMEOUT_SECONDS

            lock_path = self._runtime_lock_path(shared_root)
            holder = self._spawn_lock_holder(lock_path)
            try:
                blocked_ensure = subprocess.run(
                    [str(LAUNCHER), "env", "browser", "ensure", "--instance", "inst-pm-browser-lock"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                self._stop_lock_holder(holder)

            self.assertEqual(blocked_ensure.returncode, RUNTIME_LOCK_BUSY_EXIT_CODE)
            self.assertIn("runtime state busy", blocked_ensure.stderr)
            self.assertFalse(
                (shared_root / "instances" / "inst-pm-browser-lock" / "browser").exists(),
                "blocked browser ensure must not create browser runtime state",
            )

    def test_locked_browser_ensure_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            direct_ensure = subprocess.run(
                [str(LAUNCHER), "__locked-browser-ensure"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_ensure.returncode, 2)
            self.assertIn("runtime lock required", direct_ensure.stderr)
            self.assertFalse(shared_root.exists(), "direct locked browser ensure must not mutate shared root")

    def test_env_browser_ensure_rejects_invalid_env_port_before_lock_and_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-browser-invalid-env-port"
            instance_root, _ = self._write_instance_record(shared_root, instance_id)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_BROWSER_PORT"] = "abc"

            before_instance_tree = self._snapshot_tree(instance_root)
            ensure_result = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", instance_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            after_instance_tree = self._snapshot_tree(instance_root)

            self.assertEqual(ensure_result.returncode, 2)
            self.assertIn("Invalid value for BUDDYSWITCH_BROWSER_PORT: abc", ensure_result.stderr)
            self.assertEqual(
                before_instance_tree,
                after_instance_tree,
                "invalid env browser port must fail before mutating instance state",
            )
            self.assertFalse((instance_root / "browser").exists())
            self.assertFalse((instance_root / "home").exists())
            self.assertFalse((instance_root / "codex-home").exists())
            self.assertFalse((instance_root / "xdg-config").exists())
            self.assertFalse(self._legacy_runtime_lock_path(shared_root).exists())
            self.assertFalse(self._runtime_lock_path(shared_root).exists())

    def test_locked_workspace_sync_entrypoint_rejects_direct_invocation_without_lock(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            direct_sync = subprocess.run(
                [str(LAUNCHER), "__locked-workspace-sync"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_sync.returncode, 2)
            self.assertIn("runtime lock required", direct_sync.stderr)
            self.assertFalse(workspace_dir.exists(), "direct locked entrypoint must not mutate workspace")

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
            self.assertIn("Top-level command removed: workspace", missing_subcommand.stderr)
            self.assertIn("No public replacement", missing_subcommand.stderr)
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
                self.assertEqual(sync_result.returncode, 2)
                self.assertIn("Top-level command removed: workspace", sync_result.stderr)

                after_sync = subprocess.run(
                    ["git", "-C", str(workspace_dir), "rev-parse", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(after_sync.returncode, 0, msg=after_sync.stderr)
                self.assertEqual(after_sync.stdout.strip(), stale_head)
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
                self.assertEqual(launch_result.returncode, 2)
                self.assertIn("Top-level command removed: start", launch_result.stderr)

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
            self.assertEqual(sync_result.returncode, 2)
            self.assertIn("Top-level command removed: workspace", sync_result.stderr)
            self.assertEqual((workspace_dir / "AGENTS.md").read_text(encoding="utf-8"), "# Wrong Header\n")
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
            self.assertIn("Top-level command removed: workspace", sync_result.stderr)
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
                [str(LAUNCHER), "env", "reset", "--yes"],
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

            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            self.assertTrue(workspace_dir.exists(), "precondition: shared root contains runtime state")

            ready_file.unlink(missing_ok=True)

            reset_result = subprocess.run(
                [str(LAUNCHER), "env", "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(reset_result.returncode, 0)
            self.assertFalse(workspace_dir.exists(), "reset should remove the execution worktree")

    def test_reset_removes_registered_instance_worktrees(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / payload["instance_id"]
            workspace_dir = instance_root / "workspace"
            self.assertTrue(workspace_dir.exists())

            ready_file.unlink(missing_ok=True)
            (instance_root / "browser" / "chrome.pid").unlink(missing_ok=True)

            try:
                reset_with_yes = subprocess.run(
                    [str(LAUNCHER), "env", "reset", "--yes"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(reset_with_yes.returncode, 0, msg=reset_with_yes.stderr)
                worktrees = subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout
                self.assertNotIn(str(workspace_dir), worktrees)
            finally:
                subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(workspace_dir)],
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

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Top-level command removed: start", completed.stderr)
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

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Top-level command removed: start", completed.stderr)
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

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Top-level command removed: start", completed.stderr)
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

                    self.assertEqual(completed.returncode, 2)
                    self.assertIn("Top-level command removed: start", completed.stderr)
                    self.assertTrue(sentinel.exists(), f"reserved workspace sentinel must be preserved for {relative}")
                    self.assertFalse((reserved_workspace / ".git").exists(), f"reserved workspace must not become a worktree for {relative}")


if __name__ == "__main__":
    unittest.main()
