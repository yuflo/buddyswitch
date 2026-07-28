"""Process-tier launcher CLI and protocol test support."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tomllib
from pathlib import Path

from buddyswitch.runtime_kernel import process_identity
from tests.support.cli import write_executable
from tests.support.launcher import LauncherTestSupport
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process
from tests.support.python import PYTHON, executable_python_source

ROOT = REPO_ROOT
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


def run_output(command: list[str], *, cwd: Path | None = None, text: bool = False):
    return run_process(
        command,
        cwd=cwd,
        text=text,
        capture_output=True,
        check=True,
    ).stdout


class ProcessLauncherHarness(LauncherTestSupport):
    def _register_browser_process_descriptor(
        self,
        instance_root: Path,
        actor_id: str,
        *,
        profile_dir: Path | None = None,
    ) -> str:
        pid_file = instance_root / "browser" / "chrome.pid"
        return self._ledger.register_process_descriptor(
            pid_file=pid_file,
            cleanup_strategy="browser_stop",
            cleanup_args={
                "instance_root": str(instance_root),
                "actor_id": actor_id,
            },
            command=["browser", "ensure", "--instance", actor_id],
            owned_paths={
                "pid": pid_file,
                "pid_identity": process_identity.identity_file(pid_file),
                "profile": profile_dir or instance_root / "browser" / "profile",
            },
        )

    @staticmethod
    def _tcp_port_is_available(port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        finally:
            sock.close()
        return True

    @classmethod
    def _first_available_browser_port(cls) -> int | None:
        for port in range(9222, 9322):
            if cls._tcp_port_is_available(port):
                return port
        return None

    @staticmethod
    def _legacy_runtime_lock_path(shared_root: Path) -> Path:
        return Path(f"{shared_root}.lock")

    @staticmethod
    def _runtime_lock_path(shared_root: Path) -> Path:
        return shared_root / "run" / "locks" / "runtime.lock"

    @staticmethod
    def _repo_git_common_dir(repo_root: Path = ROOT) -> Path:
        output = run_output(
            ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
            text=True,
        ).strip()
        git_dir = Path(output)
        if not git_dir.is_absolute():
            git_dir = repo_root / git_dir
        return git_dir.resolve(strict=False)

    def _assert_codex_automation_config(self, config_text: str, *, shared_root: Path, repo_root: Path = ROOT) -> None:
        repo_git_common_dir = self._repo_git_common_dir(repo_root)
        repo_root_resolved = str(repo_root.resolve(strict=False))
        top_level_text = config_text.split("[", 1)[0]
        shared_root_resolved = str(shared_root.resolve(strict=False))
        profile_mode = "/instances/" in config_text and shared_root_resolved in config_text

        self.assertIn("approval_policy = { granular = {", top_level_text)
        self.assertIn("sandbox_approval = false", config_text)
        self.assertIn("rules = false", config_text)
        self.assertIn("mcp_elicitations = false", config_text)
        self.assertIn("request_permissions = false", config_text)
        self.assertIn("skill_approval = false", config_text)
        if profile_mode:
            self.assertNotIn('sandbox_mode = "workspace-write"', config_text)
            self.assertNotIn("[sandbox_workspace_write]", config_text)
            self.assertIn('default_permissions = "buddyswitch-runtime"', top_level_text)
            self.assertIn("[permissions.buddyswitch-runtime.filesystem]", config_text)
            parsed = tomllib.loads(config_text)
            filesystem = parsed["permissions"]["buddyswitch-runtime"]["filesystem"]
            self.assertEqual(filesystem["/"], "read")
            self.assertEqual(filesystem[repo_root_resolved], "none")
            workspace_keys = [path for path in filesystem if "/instances/" in path and path.endswith("/workspace")]
            self.assertEqual(len(workspace_keys), 1, msg=workspace_keys)
            self.assertEqual(filesystem[workspace_keys[0]], "read")
            actor_private_keys = [path for path in filesystem if "/instances/" in path and path.endswith("/workspace/private")]
            self.assertEqual(len(actor_private_keys), 1, msg=actor_private_keys)
            self.assertEqual(filesystem[actor_private_keys[0]], "write")
            instance_tmp_keys = [path for path in filesystem if "/instances/" in path and path.endswith("/tmp")]
            self.assertEqual(len(instance_tmp_keys), 1, msg=instance_tmp_keys)
            self.assertEqual(filesystem[instance_tmp_keys[0]], "write")
            project_source_keys = [path for path in filesystem if path.endswith("/project/workspace/projects/app")]
            self.assertEqual(len(project_source_keys), 1, msg=project_source_keys)
            self.assertIn(filesystem[project_source_keys[0]], {"read", "write"})
            project_workspace_keys = [path for path in filesystem if path.endswith("/project/workspace")]
            if project_workspace_keys:
                self.assertEqual(filesystem[project_workspace_keys[0]], "read")
            state_keys = [path for path in filesystem if path.endswith("/state")]
            self.assertEqual(len(state_keys), 1, msg=state_keys)
            self.assertEqual(filesystem[state_keys[0]], "none")
            self.assertNotIn(str(Path("/tmp").resolve(strict=False)), filesystem)
            if os.environ.get("TMPDIR"):
                self.assertNotIn(str(Path(os.environ["TMPDIR"]).resolve(strict=False)), filesystem)
            self.assertNotIn(":project_roots", filesystem)
            for key, value in filesystem.items():
                self.assertIsInstance(key, str)
                self.assertIsInstance(value, str, msg=key)
                self.assertNotIn("*", key)
                if key != "/":
                    self.assertTrue(Path(key).is_absolute(), msg=key)
            scripts_matches = [path for path in filesystem if path.endswith("/workspace/scripts")]
            for scripts_path in scripts_matches:
                self.assertEqual(filesystem[scripts_path], "read")
            if not scripts_matches:
                self.assertEqual(filesystem["/"], "read")
            self.assertIn("[permissions.buddyswitch-runtime.network]", config_text)
            self.assertIn("enabled = true", config_text)
            self.assertIn('mode = "full"', config_text)
            self.assertNotIn(str(repo_git_common_dir), config_text)
        else:
            self.assertEqual(config_text.count('sandbox_mode = "workspace-write"'), 1)
            self.assertEqual(config_text.count("[sandbox_workspace_write]"), 1)
            self.assertIn('sandbox_mode = "workspace-write"', top_level_text)
            self.assertIn("network_access = true", config_text)
            self.assertIn(shared_root_resolved, config_text)
            self.assertIn(str(repo_git_common_dir), config_text)

        masked_config = config_text
        allowed_paths = [
            shared_root_resolved,
            str(repo_git_common_dir),
        ]
        expected_python = os.environ.get("BUDDYSWITCH_PYTHON")
        if expected_python:
            allowed_paths.append(expected_python)
            allowed_paths.append(str(Path(expected_python).resolve(strict=False)))
        if not profile_mode:
            allowed_paths.extend(
                [
                    str(Path("/tmp").resolve(strict=False)),
                    str(Path(os.environ["TMPDIR"]).resolve(strict=False)) if os.environ.get("TMPDIR") else "",
                ]
            )
        if profile_mode:
            allowed_paths.append(repo_root_resolved)
        for allowed_path in allowed_paths:
            if allowed_path:
                masked_config = masked_config.replace(allowed_path, "")
        self.assertNotIn(str(Path.home()), masked_config)
        if profile_mode:
            self.assertNotIn(
                f'{json.dumps(repo_root_resolved)} = "read"',
                config_text,
            )
            self.assertNotIn(
                f'{json.dumps(repo_root_resolved)} = "write"',
                config_text,
            )
        else:
            self.assertNotIn(repo_root_resolved, config_text.replace(str(repo_git_common_dir), ""))

    def _expected_python_for_env(self, env: dict[str, str]) -> str:
        return PYTHON

    def _assert_cockpit_proxy_registration(
        self,
        argv: list[object],
        instance_root: Path,
        *,
        expected_python: str,
        broker_socket: str,
    ) -> None:
        self.assertEqual(argv[:3], ["mcp", "add", "chrome-devtools-cockpit"])
        self.assertIn("--", argv)
        separator_index = argv.index("--")
        self.assertEqual(argv[separator_index + 1], expected_python)
        self.assertEqual(
            argv[separator_index + 2 : separator_index + 4],
            ["-m", "buddyswitch.application.entrypoints.browser_cockpit_proxy"],
        )
        self.assertIn("--upstream-command", argv)
        upstream_index = argv.index("--upstream-command")
        self.assertEqual(argv[upstream_index + 1], "npx chrome-devtools-mcp@1.1.1")
        self.assertIn(f"--instance-root={instance_root}", argv)
        self.assertIn("--broker-socket", argv)
        broker_index = argv.index("--broker-socket")
        self.assertEqual(argv[broker_index + 1], broker_socket)
        self.assertFalse(any(str(item).startswith("--browser-url") for item in argv), msg=argv)
        self.assertNotIn("chrome-devtools-mcp@latest", argv)

    def _assert_env_mcp_registration(
        self,
        argv: list[object],
        *,
        expected_python: str,
        actor_id: str,
        role: str,
        broker_socket: str,
    ) -> None:
        self.assertEqual(argv[:3], ["mcp", "add", "buddyswitch-env"])
        self.assertIn("--", argv)
        separator_index = argv.index("--")
        self.assertEqual(argv[separator_index + 1], expected_python)
        self.assertEqual(
            argv[separator_index + 2 : separator_index + 4],
            ["-m", "buddyswitch.application.entrypoints.env_mcp"],
        )
        self.assertIn("--actor-id", argv)
        self.assertIn(actor_id, argv)
        self.assertIn("--role", argv)
        self.assertIn(role, argv)
        self.assertIn("--broker-socket", argv)
        self.assertIn(broker_socket, argv)

    def _minimal_launcher_path_without_python(self, bin_dir: Path) -> str:
        for tool in ("bash", "dirname"):
            resolved = shutil.which(tool)
            self.assertIsNotNone(resolved, f"{tool} must be available for launcher bootstrap test")
            (bin_dir / tool).symlink_to(str(resolved))
        return str(bin_dir)

    def _write_fake_background_page_tool(self, path: Path) -> None:
        write_executable(
            path,
            executable_python_source(
                """
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
browser_url = None
target_url = None
index = 0
while index < len(args):
    arg = args[index]
    if arg == "--browser-url" and index + 1 < len(args):
        browser_url = args[index + 1]
        index += 2
        continue
    if arg.startswith("--browser-url="):
        browser_url = arg.split("=", 1)[1]
        index += 1
        continue
    if arg == "--url" and index + 1 < len(args):
        target_url = args[index + 1]
        index += 2
        continue
    if arg.startswith("--url="):
        target_url = arg.split("=", 1)[1]
        index += 1
        continue
    index += 1

entry = {
    "method": "CDP",
    "path": "Target.createTarget",
    "browser_url": browser_url,
    "params": {"url": target_url, "background": True},
}
calls_file_raw = os.environ.get("BUDDYSWITCH_TEST_CDP_CALLS_FILE") or os.environ.get("BUDDYSWITCH_TEST_CALLS")
if calls_file_raw:
    calls_file = Path(calls_file_raw)
    calls_file.parent.mkdir(parents=True, exist_ok=True)
    with calls_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\\n")

state_file_raw = os.environ.get("BUDDYSWITCH_TEST_CDP_STATE_FILE")
if not state_file_raw:
    print("missing fake CDP state file", file=sys.stderr)
    raise SystemExit(1)
state_path = Path(state_file_raw)
state = json.loads(state_path.read_text(encoding="utf-8"))
if target_url != "about:blank" or state.get("allow_background_create_about_blank") is not True:
    print("background target creation disabled", file=sys.stderr)
    raise SystemExit(1)

pages = list(state.get("pages", []))
if not any(
    isinstance(page, dict)
    and page.get("type") == "page"
    and isinstance(page.get("url"), str)
    and page.get("url") == "about:blank"
    for page in pages
):
    pages.append({"id": "target-about-blank", "type": "page", "url": "about:blank"})
    state["pages"] = pages
    state_path.write_text(json.dumps(state, ensure_ascii=True, indent=2) + "\\n", encoding="utf-8")

print('{"targetId":"target-about-blank"}')
"""
            ),
        )

    def _spawn_lock_holder(self, lock_path: Path) -> subprocess.Popen[str]:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        holder = self._ledger.start_process(
            [PYTHON, "-c", LOCK_HOLDER_SCRIPT, str(lock_path)],
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
        for stream in (holder.stdin, holder.stdout, holder.stderr):
            if stream is not None and not stream.closed:
                stream.close()

    def _write_instance_record(
        self,
        shared_root: Path,
        actor_id: str,
        *,
        role: str = "pm",
        payload_actor_id: str | None = None,
        workspace_dir: Path | None = None,
        browser_port: int | None = None,
        status: str = "inactive",
        thread_id: str | None = None,
        app_server_pid: int | None = None,
        app_server_socket: str | None = None,
        app_server_log: str | None = None,
    ) -> tuple[Path, Path]:
        instance_root = shared_root / "instances" / actor_id
        instance_root.mkdir(parents=True, exist_ok=True)
        workspace_path = workspace_dir or instance_root / "workspace"
        runtime_executable = write_executable(
            instance_root / "test-codex-runtime",
            "#!/bin/sh\nprintf 'codex-test-runtime\\n'\n",
        )
        (instance_root / "instance.json").write_text(
            json.dumps(
                {
                    "actor_id": payload_actor_id or actor_id,
                    "role": role,
                    "status": status,
                    "current_task_id": "task-existing",
                    "current_track_id": "track-existing",
                    "instance_root": str(instance_root),
                    "workspace_dir": str(workspace_path),
                    "browser_port": browser_port,
                    "thread_id": thread_id,
                    "app_server_pid": app_server_pid,
                    "app_server_socket": app_server_socket,
                    "app_server_log": app_server_log,
                    "codex_runtime": {
                        "executable": str(runtime_executable),
                        "version": "codex-test-runtime",
                    },
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

    def _write_cdp_state(
        self,
        path: Path,
        *,
        version_ok: bool,
        pages: list[dict[str, object]] | None = None,
        allow_put_new_about_blank: bool = False,
        allow_get_new_about_blank: bool = False,
        allow_background_create_about_blank: bool = False,
    ) -> None:
        payload = {
            "version_ok": version_ok,
            "pages": pages or [],
            "allow_put_new_about_blank": allow_put_new_about_blank,
            "allow_get_new_about_blank": allow_get_new_about_blank,
            "allow_background_create_about_blank": allow_background_create_about_blank,
        }
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _write_capability_cli_instance(
        self,
        shared_root: Path,
        *,
        actor_id: str = "act-pm-demo",
        role: str = "pm",
    ) -> Path:
        instance_root = shared_root / "instances" / actor_id
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": "inactive",
                    "instance_root": str(instance_root),
                    "workspace_dir": str(instance_root / "workspace"),
                    "browser_port": None,
                    "updated_at": "2026-07-08T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (instance_root / "capability-config.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "catalog_version": 1,
                    "parent": {"level": "balanced", "model": "gpt-5.6-terra", "effort": "high"},
                    "side": {"level": "fast", "model": "gpt-5.6-luna", "effort": "xhigh"},
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _capability_cli_env(self, temp_root: Path, shared_root: Path) -> dict[str, str]:
        source_home = temp_root / "source-home"
        source_home.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["HOME"] = str(source_home)
        env["BUDDYSWITCH_SOURCE_HOME"] = str(source_home)
        env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
        env.pop("BUDDYSWITCH_STATE_ROOT", None)
        env.pop("CODEX_HOME", None)
        return env

    def _cleanup_popen(self, proc: subprocess.Popen[str]) -> None:
        self._terminate_registered_process(proc.pid)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None and not stream.closed:
                stream.close()

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
