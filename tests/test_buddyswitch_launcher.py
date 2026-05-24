#!/usr/bin/env python3
"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import json
import os
import errno
import shutil
import socket
import stat
import subprocess
import tempfile
import sys
import time
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - python<3.11 fallback
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "buddyswitch-codex"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env_manifest import load_manifest  # noqa: E402

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
    _RELATIVE_SENTINELS = (
        "cross-buddy-sentinel.txt",
        "relative-path-sentinel.txt",
        "shared-product-sentinel.txt",
    )
    _RUNTIME_SPARSE_PATHS = (
        "scripts/env/",
        "scripts/runtime_kernel/",
        "scripts/turn_runtime.py",
        "scripts/env_store.py",
        "scripts/env_legacy_store.py",
        "scripts/env_manifest.py",
        "scripts/env_profiles.py",
        "scripts/browser_evidence.py",
        "buddyswitch/manifest.toml",
        "buddyswitch/env-profiles/",
        "framework/contracts/",
    )
    _PM_PRODUCT_SKILLS = (
        "read-product-context",
        "synthesize-cross-functional-inputs",
        "frame-product-direction",
        "define-scope",
        "write-requirements",
        "write-acceptance-criteria",
        "make-product-decision",
        "decide-from-proof",
        "triage-track",
        "sequence-product-work",
    )

    def setUp(self) -> None:
        super().setUp()
        self._cleanup_repo_relative_sentinels()
        self.addCleanup(self._cleanup_repo_relative_sentinels)

    @classmethod
    def _cleanup_repo_relative_sentinels(cls) -> None:
        project_app = ROOT / "projects" / "app"
        for name in cls._RELATIVE_SENTINELS:
            (project_app / name).unlink(missing_ok=True)

    @staticmethod
    def _legacy_runtime_lock_path(shared_root: Path) -> Path:
        return Path(f"{shared_root}.lock")

    @staticmethod
    def _runtime_lock_path(shared_root: Path) -> Path:
        return shared_root / "run" / "locks" / "runtime.lock"

    @staticmethod
    def _runtime_owner_lock_path(shared_root: Path) -> Path:
        return shared_root / "run" / "locks" / "runtime.owner.lock"

    @staticmethod
    def _repo_git_common_dir(repo_root: Path = ROOT) -> Path:
        output = subprocess.check_output(
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
            buddybox_keys = [path for path in filesystem if "/instances/" in path and path.endswith("/workspace/buddybox")]
            self.assertEqual(len(buddybox_keys), 1, msg=buddybox_keys)
            self.assertEqual(filesystem[buddybox_keys[0]], "write")
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
            self.assertIn(json.dumps(str(Path("/tmp").resolve(strict=False))), config_text)
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

    def _write_exec(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _write_fake_codex(self, path: Path) -> None:
        helper_path = ROOT / "tests" / "helpers" / "fake_codex.py"
        self._write_exec(path, helper_path.read_text(encoding="utf-8"))

    def test_codex_config_patch_removes_prior_misnested_managed_settings_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            config_path = temp_root_path / "config.toml"
            config_path.write_text(
                """[skills.bundled]
enabled = false

[features]
plugins = false
# BuddySwitch managed automation permissions
sandbox_mode = "workspace-write"
approval_policy = { granular = {
  sandbox_approval = false,
  rules = false,
  mcp_elicitations = false,
  request_permissions = false,
  skill_approval = false,
} }

[mcp_servers.chrome-devtools-cockpit]
command = "npx"
args = ["chrome-devtools-mcp@latest", "--browser-url=http://127.0.0.1:9222"]

[mcp_servers.notion]
url = "https://mcp.notion.com/mcp"
default_tools_approval_mode = "ask"

[sandbox_workspace_write] # old managed table with an inline comment
network_access = false
writable_roots = ["/old"]
""",
                encoding="utf-8",
            )

            command = [
                sys.executable,
                str(ROOT / "tools" / "launcher" / "codex_config.py"),
                "--config",
                str(config_path),
                "--shared-root",
                str(shared_root),
                "--repo-root",
                str(ROOT),
                "--temp-root",
                "/tmp",
            ]
            for _ in range(2):
                completed = subprocess.run(
                    command,
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            config_text = config_path.read_text(encoding="utf-8")
            features_section = config_text.split("[features]", 1)[1].split("\n[", 1)[0]
            self._assert_codex_automation_config(config_text, shared_root=shared_root)
            self.assertEqual(config_text.count("# BuddySwitch managed automation permissions"), 1)
            self.assertNotIn("[sandbox_workspace_write] # old", config_text)
            self.assertNotIn("network_access = false", config_text)
            self.assertNotIn('writable_roots = ["/old"]', config_text)
            self.assertNotIn("sandbox_mode", features_section)
            self.assertNotIn("approval_policy", features_section)
            self.assertEqual(config_text.count('default_tools_approval_mode = "approve"'), 2)
            self.assertIn("[mcp_servers.chrome-devtools-cockpit]", config_text)
            self.assertIn("[mcp_servers.notion]", config_text)
            self.assertNotIn('default_tools_approval_mode = "ask"', config_text)
            self.assertNotIn("supports_parallel_tool_calls", config_text)

    def test_codex_config_patch_rejects_shared_root_that_grants_forbidden_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True)
            custom_codex_home = source_home_path / "custom-codex-home"
            custom_codex_home.mkdir()

            safe_shared_root = source_home_path / ".codex-buddyswitch"
            cases = (
                ("source-root", ROOT, []),
                ("source-root-child", ROOT / ".unsafe-buddyswitch-shared-root", []),
                ("source-codex-home", source_codex_home, []),
                ("custom-source-codex-home", custom_codex_home, ["--source-codex-home", str(custom_codex_home)]),
            )
            for label, shared_root, extra_args in cases:
                config_path = temp_root_path / f"{label}-config.toml"
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "tools" / "launcher" / "codex_config.py"),
                        "--config",
                        str(config_path),
                        "--shared-root",
                        str(shared_root),
                        "--repo-root",
                        str(ROOT),
                        "--temp-root",
                        "/tmp",
                        *extra_args,
                    ],
                    cwd=ROOT,
                    env={**os.environ, "HOME": str(source_home_path)},
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(completed.returncode, 2)
                self.assertIn("refusing writable root", completed.stderr)
                self.assertFalse(config_path.exists())

    def test_codex_config_patch_skips_unsafe_temp_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            custom_codex_home = source_home_path / "custom-codex-home"
            custom_codex_home.mkdir()
            config_path = temp_root_path / "config.toml"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "codex_config.py"),
                    "--config",
                    str(config_path),
                    "--shared-root",
                    str(shared_root),
                    "--source-codex-home",
                    str(custom_codex_home),
                    "--repo-root",
                    str(ROOT),
                    "--temp-root",
                    "/tmp",
                    "--temp-root",
                    str(ROOT),
                    "--temp-root",
                    str(custom_codex_home),
                    "--temp-root",
                    str(ROOT / "projects" / "app" / ".runtime"),
                ],
                cwd=ROOT,
                env={**os.environ, "HOME": str(source_home_path)},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            config_text = config_path.read_text(encoding="utf-8")
            self._assert_codex_automation_config(config_text, shared_root=shared_root)
            self.assertNotIn(str(ROOT.resolve(strict=False)), config_text.replace(str(self._repo_git_common_dir()), ""))
            self.assertNotIn(str(custom_codex_home.resolve(strict=False)), config_text)
            self.assertNotIn(str((ROOT / "projects" / "app" / ".runtime").resolve(strict=False)), config_text)

    def _write_fake_curl(self, path: Path) -> None:
        self._write_exec(
            path,
            """#!/usr/bin/env bash
set -euo pipefail

method="GET"
url=""
connect_timeout=""
max_time=""
args=("$@")
index=0
while [[ ${index} -lt ${#args[@]} ]]; do
  arg="${args[${index}]}"
  case "${arg}" in
    --request|-X)
      index=$((index + 1))
      if [[ ${index} -lt ${#args[@]} ]]; then
        method="${args[${index}]}"
      fi
      ;;
    --connect-timeout)
      index=$((index + 1))
      if [[ ${index} -lt ${#args[@]} ]]; then
        connect_timeout="${args[${index}]}"
      fi
      ;;
    --max-time)
      index=$((index + 1))
      if [[ ${index} -lt ${#args[@]} ]]; then
        max_time="${args[${index}]}"
      fi
      ;;
    http://*|https://*)
      url="${arg}"
      ;;
  esac
  index=$((index + 1))
done

if [[ -n "${BUDDYSWITCH_TEST_CDP_STATE_FILE:-}" && -f "${BUDDYSWITCH_TEST_CDP_STATE_FILE}" ]]; then
  python3 - "${BUDDYSWITCH_TEST_CDP_STATE_FILE}" "${method}" "${url}" "${connect_timeout}" "${max_time}" "${BUDDYSWITCH_TEST_CDP_CALLS_FILE:-}" <<'PY'
import json
from pathlib import Path
from urllib.parse import urlparse
import sys

state_path = Path(sys.argv[1])
method = sys.argv[2].upper()
url = sys.argv[3]
connect_timeout = sys.argv[4]
max_time = sys.argv[5]
calls_file = Path(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] else None
state = json.loads(state_path.read_text(encoding="utf-8"))
parsed = urlparse(url)
path = parsed.path
query = parsed.query

if calls_file is not None:
    calls_file.parent.mkdir(parents=True, exist_ok=True)
    with calls_file.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "method": method,
                    "path": path,
                    "query": query,
                    "connect_timeout": connect_timeout,
                    "max_time": max_time,
                },
                ensure_ascii=True,
            )
            + "\\n"
        )

if path == "/json/version":
    if state.get("version_ok") is True:
        print('{"Browser":"test"}')
        raise SystemExit(0)
    raise SystemExit(22)

if path == "/json/list":
    print(json.dumps(state.get("pages", []), ensure_ascii=True))
    raise SystemExit(0)

if path == "/json/new" and query == "about:blank":
    if method == "PUT" and state.get("allow_put_new_about_blank") is True:
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
        print('{"id":"target-about-blank"}')
        raise SystemExit(0)
    if method == "GET" and state.get("allow_get_new_about_blank") is True:
        print('{"id":"target-about-blank"}')
        raise SystemExit(0)
    raise SystemExit(22)

raise SystemExit(22)
PY
  exit $?
fi

if [[ -f "${BUDDYSWITCH_TEST_BROWSER_READY_FILE:-}" ]]; then
  case "${url}" in
    */json/version)
      printf '{"Browser":"test"}\n'
      exit 0
      ;;
    */json/list)
      printf '[{"id":"target-about-blank","type":"page","url":"about:blank"}]\n'
      exit 0
      ;;
    */json/new?about:blank)
      if [[ "${method}" == "PUT" ]]; then
        printf '{"id":"target-about-blank"}\n'
        exit 0
      fi
      exit 22
      ;;
  esac
fi

exit 22
""",
        )

    def _write_fake_chrome(self, path: Path) -> None:
        self._write_exec(
            path,
            """#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${BUDDYSWITCH_TEST_CHROME_ARGV_FILE:-}" ]]; then
  python3 - "${BUDDYSWITCH_TEST_CHROME_ARGV_FILE}" "$@" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
args = sys.argv[2:]
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(args, ensure_ascii=True) + "\\n")
PY
fi

if [[ -n "${BUDDYSWITCH_TEST_CDP_STATE_FILE:-}" && -f "${BUDDYSWITCH_TEST_CDP_STATE_FILE}" ]]; then
  python3 - "${BUDDYSWITCH_TEST_CDP_STATE_FILE}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
state = json.loads(path.read_text(encoding="utf-8"))
state["version_ok"] = True
path.write_text(json.dumps(state, ensure_ascii=True, indent=2) + "\\n", encoding="utf-8")
PY
fi

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
  printf '%s\\n' "$*" >> "${{BUDDYSWITCH_TEST_GIT_CAPTURE}}"
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
        status: str = "inactive",
        thread_id: str | None = None,
        app_server_pid: int | None = None,
        app_server_socket: str | None = None,
        app_server_log: str | None = None,
    ) -> tuple[Path, Path]:
        instance_root = shared_root / "instances" / instance_id
        instance_root.mkdir(parents=True, exist_ok=True)
        workspace_path = workspace_dir or instance_root / "workspace"
        (instance_root / "instance.json").write_text(
            json.dumps(
                {
                    "instance_id": payload_instance_id or instance_id,
                    "buddy": buddy,
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
    ) -> None:
        payload = {
            "version_ok": version_ok,
            "pages": pages or [],
            "allow_put_new_about_blank": allow_put_new_about_blank,
            "allow_get_new_about_blank": allow_get_new_about_blank,
        }
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

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

    def _start_service_instance(
        self,
        temp_root_path: Path,
        source_home_path: Path,
        *,
        buddy: str = "pm",
        state_payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
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
        state_file = temp_root_path / "app-server-state.json"
        if state_payload is not None:
            state_file.write_text(json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        env = os.environ.copy()
        env["HOME"] = str(source_home_path)
        env.pop("CODEX_HOME", None)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
        env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
        env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
        env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
        env["BUDDYSWITCH_TEST_APP_SERVER_STATE_FILE"] = str(state_file)

        completed = subprocess.run(
            [str(LAUNCHER), "instance", "start", "--buddy", buddy],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(capture_path.read_text(encoding="utf-8"))
        shared_root = source_home_path / ".codex-buddyswitch"
        instance_id = payload["instance_id"]
        instance_root = shared_root / "instances" / instance_id
        instance_payload = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
        app_server_pid = instance_payload.get("app_server_pid")
        if isinstance(app_server_pid, int):
            def _cleanup_app_server() -> None:
                try:
                    os.kill(app_server_pid, 15)
                except OSError:
                    return
            self.addCleanup(_cleanup_app_server)

        return {
            "completed": completed,
            "env": env,
            "capture_path": capture_path,
            "calls_path": calls_path,
            "state_file": state_file,
            "payload": payload,
            "shared_root": shared_root,
            "instance_id": instance_id,
            "instance_root": instance_root,
            "instance_payload": instance_payload,
        }

    def _runtime_sparse_list(self, workspace_dir: Path) -> list[str]:
        return subprocess.check_output(
            ["git", "-C", str(workspace_dir), "sparse-checkout", "list"],
            text=True,
        ).splitlines()

    def _assert_runtime_workspace_excludes_source_surfaces(self, workspace_dir: Path) -> None:
        for relative_path in (
            "buddyswitch/skills",
            "tools",
            "tests",
            "docs",
            "README.md",
            "buddyswitch-codex",
        ):
            candidate = workspace_dir / relative_path
            self.assertFalse(
                candidate.exists() or candidate.is_symlink(),
                msg=f"runtime workspace must not expose source surface: {relative_path}",
            )

    def _assert_pm_runtime_shape(self, workspace_dir: Path, shared_root: Path) -> None:
        required_runtime_surface = (
            "scripts/env/client.py",
            "scripts/runtime_kernel/broker.py",
            "scripts/turn_runtime.py",
            "scripts/env_store.py",
            "scripts/env_legacy_store.py",
            "scripts/env_manifest.py",
            "scripts/env_profiles.py",
            "scripts/browser_evidence.py",
            "buddyswitch/manifest.toml",
            "buddyswitch/env-profiles/pm.json",
            "framework/contracts/pm.md",
            "AGENTS.md",
        )
        for relative_path in required_runtime_surface:
            candidate = workspace_dir / relative_path
            self.assertTrue(candidate.exists(), msg=f"runtime workspace missing: {relative_path}")
        self._assert_pm_runtime_skills(workspace_dir)

        self.assertEqual(
            (workspace_dir / "projects" / "app").resolve(strict=True),
            (shared_root / "project" / "workspace" / "projects" / "app").resolve(strict=True),
        )

        self.assertFalse((workspace_dir / "buddyswitch" / "objects").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "objects").is_symlink())
        self.assertTrue((workspace_dir / "buddybox").is_dir())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "buddybox" / "pm").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "buddybox" / "pm").is_symlink())

    def _assert_pm_runtime_skills(self, workspace_dir: Path) -> None:
        runtime_skills = workspace_dir / ".agents" / "skills"
        for skill_id in self._PM_PRODUCT_SKILLS:
            self.assertTrue((runtime_skills / skill_id / "SKILL.md").exists(), msg=skill_id)
        self.assertTrue((runtime_skills / "track-tool" / "SKILL.md").exists())
        self.assertTrue((runtime_skills / "artifact-tool" / "SKILL.md").exists())
        self.assertFalse((runtime_skills / "write-prd").exists())
        self.assertFalse((runtime_skills / "write-prd" / "assets" / "prd-template.md").exists())

    def _cleanup_runtime_broker(self, instance_root: Path) -> None:
        pid_file = instance_root / "runtime" / "runtime-broker.pid"
        try:
            pid_text = pid_file.read_text(encoding="utf-8").strip()
            pid = int(pid_text)
        except (FileNotFoundError, OSError, ValueError):
            pid = 0
        if pid:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
            for _ in range(20):
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
                time.sleep(0.05)
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        for path in (
            pid_file,
            instance_root / "runtime" / "runtime-broker.sock",
            instance_root / "runtime" / "runtime-broker.socket",
        ):
            path.unlink(missing_ok=True)

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

    def _assert_directory_file_bytes_equal(self, *, source: Path, target: Path) -> None:
        source_files = sorted(path for path in source.rglob("*") if path.is_file())
        target_files = sorted(path for path in target.rglob("*") if path.is_file())
        self.assertEqual(
            [path.relative_to(source).as_posix() for path in source_files],
            [path.relative_to(target).as_posix() for path in target_files],
        )
        for source_file in source_files:
            rel_path = source_file.relative_to(source)
            target_file = target / rel_path
            self.assertEqual(
                source_file.read_bytes(),
                target_file.read_bytes(),
                msg=f"mismatch for {rel_path.as_posix()}",
            )

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
        self._assert_unknown_top_level_command(["debug", "prompt-input", "Draft the onboarding PRD"], "debug")

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
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
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
            runtime_skills = workspace_dir / ".agents" / "skills"
            self._assert_pm_runtime_skills(workspace_dir)
            for removed in ("task" + "-manager", "track" + "-manager", "artifact" + "-manager"):
                self.assertFalse((runtime_skills / removed).exists())
            self.assertFalse((runtime_skills / "shape-prototype").exists())

    def test_instance_start_execution_workspace_is_sparse_runtime_surface(self) -> None:
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
            ready_file = temp_root_path / "browser-ready.flag"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "instances" / payload["instance_id"] / "workspace"
            self.assertEqual(payload["cwd"], str(workspace_dir.resolve()))
            self.assertEqual(self._runtime_sparse_list(workspace_dir), list(self._RUNTIME_SPARSE_PATHS))
            self._assert_pm_runtime_shape(workspace_dir, shared_root)
            self._assert_runtime_workspace_excludes_source_surfaces(workspace_dir)

            self._assert_pm_runtime_skills(workspace_dir)
            self.assertFalse((workspace_dir / ".agents" / "skills" / "shape-prototype").exists())
            self.assertFalse(
                (workspace_dir / "buddyswitch" / "skills" / "design" / "shape-prototype" / "SKILL.md").exists()
            )

    def test_instance_start_creates_private_taskbox_for_active_buddy(self) -> None:
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

            capture_path = temp_root_path / "capture-taskbox.json"
            ready_file = temp_root_path / "browser-ready.flag"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "dev"],
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
            runtime_root = shared_root / "state"

            taskbox_root = instance_root / "taskbox" / "dev"
            self.assertTrue((taskbox_root / "tasks").is_dir())
            self.assertTrue((taskbox_root / "history.md").is_file())
            self.assertEqual((taskbox_root / "history.md").read_text(encoding="utf-8"), "")

            self.assertFalse((workspace_dir / "taskbox").exists())
            self.assertFalse((runtime_root / "buddyswitch" / "objects" / "tasks").exists())

    def test_instance_start_design_runtime_skill_exists_without_source_skill_tree(self) -> None:
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

            capture_path = temp_root_path / "capture-design.json"
            ready_file = temp_root_path / "browser-ready.flag"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "design"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            workspace_dir = Path(payload["cwd"])
            self.assertTrue((workspace_dir / ".agents" / "skills" / "shape-prototype" / "SKILL.md").exists())
            self.assertFalse((workspace_dir / "buddyswitch" / "skills" / "design" / "shape-prototype").exists())
            self.assertFalse((workspace_dir / "tools" / "launcher" / "assets" / "buddies" / "design").exists())

    def test_runtime_local_excludes_cover_generated_runtime_paths(self) -> None:
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
            ready_file = temp_root_path / "browser-ready.flag"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            workspace_dir = Path(payload["cwd"])
            exclude_path = subprocess.check_output(
                ["git", "-C", str(workspace_dir), "rev-parse", "--git-path", "info/exclude"],
                text=True,
            ).strip()
            resolved_exclude = Path(exclude_path)
            if not resolved_exclude.is_absolute():
                resolved_exclude = workspace_dir / resolved_exclude
            exclude_lines = {line.strip() for line in resolved_exclude.read_text(encoding="utf-8").splitlines() if line.strip()}
            expected_lines = {
                "AGENTS.md",
                ".agents/skills/**",
                "projects/app",
                ".runtime/**",
                ".codex/config.toml",
            }
            for line in expected_lines:
                self.assertIn(line, exclude_lines)

    def test_runtime_broker_starts_from_sparse_workspace(self) -> None:
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
            ready_file = temp_root_path / "browser-ready.flag"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_BROKER_STATUS"] = "1"

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            status_probe = payload["broker_status_probe"]
            self.assertIsInstance(status_probe, dict)
            assert isinstance(status_probe, dict)
            self.assertEqual(status_probe["returncode"], 0, msg=status_probe)
            status_payload = status_probe["json"]
            self.assertIsInstance(status_payload, dict, msg=status_probe)
            assert isinstance(status_payload, dict)
            self.assertTrue(status_payload.get("healthy"), msg=status_payload)
            self.assertIs(status_payload.get("runtime_workspace"), True)

            workspace_dir = Path(payload["cwd"])
            self.assertTrue((workspace_dir / "scripts" / "runtime_kernel" / "broker.py").exists())
            self.assertTrue((workspace_dir / "buddyswitch" / "manifest.toml").exists())

    def test_local_non_buddy_start_allows_codex_search_args(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            capture_path = temp_root_path / "capture.json"
            home = temp_root_path / "home"
            codex_home = temp_root_path / "codex-home"
            xdg_config_home = temp_root_path / "xdg-config"
            codex_home.mkdir(parents=True)
            (codex_home / "auth.json").write_text("{}\n", encoding="utf-8")
            (codex_home / "config.toml").write_text("", encoding="utf-8")

            command = (
                "source tools/launcher/env.sh\n"
                "BUDDYSWITCH_HOME=\"$1\"\n"
                "BUDDYSWITCH_CODEX_HOME=\"$2\"\n"
                "BUDDYSWITCH_XDG_CONFIG_HOME=\"$3\"\n"
                "buddyswitch_run_codex --search\n"
            )
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env.pop("BUDDYSWITCH_ACTIVE_BUDDY", None)
            env.pop("BUDDYSWITCH_INSTANCE_ID", None)

            completed = subprocess.run(
                ["bash", "-lc", command, "buddyswitch-run-codex-test", str(home), str(codex_home), str(xdg_config_home)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["argv"], ["--search"])
            self.assertIsNone(payload["active_buddy"])
            self.assertIsNone(payload["instance_id"])

    def test_start_execution_worktree_uses_design_buddy_prompt_contract(self) -> None:
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
            capture_path = temp_root_path / "capture-design.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "design"],
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
            agents_md = workspace_dir / "AGENTS.md"
            expected_agents = (ROOT / "tools" / "launcher" / "assets" / "buddies" / "design" / "AGENTS.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(agents_md.read_text(encoding="utf-8"), expected_agents)
            prompt_text = agents_md.read_text(encoding="utf-8")
            self.assertIn("locked to the `design` buddy", prompt_text)
            for token in (
                "## Runtime Boundary",
                "env_tools.search",
                "Native Codex `web_search` is unavailable",
                "scripts/env/client.py search status",
                "## Output Rule",
            ):
                self.assertIn(token, prompt_text)
            self.assertNotIn("project.access=", prompt_text)
            self.assertNotIn("projects/app", prompt_text)
            runtime_skills = workspace_dir / ".agents" / "skills"
            self.assertTrue((runtime_skills / "shape-prototype" / "SKILL.md").exists())
            self.assertFalse((runtime_skills / "write-prd").exists())
            self.assertTrue((runtime_skills / "track-tool" / "SKILL.md").exists())
            for removed in ("task" + "-manager", "track" + "-manager", "artifact" + "-manager"):
                self.assertFalse((runtime_skills / removed).exists())

    def test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy(self) -> None:
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

            manifest_path = ROOT / "buddyswitch" / "manifest.toml"
            manifest = load_manifest(manifest_path)
            buddies = [row for row in manifest.get("buddies", []) if isinstance(row, dict)]
            self.assertTrue(buddies)
            skill_sources = {
                row["id"]: row["path"]
                for row in manifest.get("skills", [])
                if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("path"), str)
            }
            market = next((row for row in buddies if row.get("id") == "market"), None)
            self.assertIsInstance(market, dict)
            assert isinstance(market, dict)
            self.assertGreaterEqual(len([row for row in market.get("skills", []) if isinstance(row, str)]), 6)

            base_env = os.environ.copy()
            base_env["HOME"] = str(source_home_path)
            base_env.pop("CODEX_HOME", None)
            base_env["PATH"] = f"{fake_bin}{os.pathsep}{base_env.get('PATH', '')}"
            base_env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            base_env["BUDDYSWITCH_BROWSER_PORT"] = "1"

            for buddy in buddies:
                buddy_id = buddy.get("id")
                buddy_skills = buddy.get("skills", [])
                if not isinstance(buddy_id, str) or not isinstance(buddy_skills, list):
                    continue

                capture_path = temp_root_path / f"capture-{buddy_id}.json"
                ready_file = temp_root_path / f"browser-ready-{buddy_id}.flag"
                capture_path.unlink(missing_ok=True)
                ready_file.unlink(missing_ok=True)

                env = base_env.copy()
                env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
                env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
                completed = subprocess.run(
                    [
                        str(LAUNCHER),
                        "instance",
                        "start",
                        "--buddy",
                        buddy_id,
                    ],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=f"{buddy_id}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
                payload = json.loads(capture_path.read_text(encoding="utf-8"))
                runtime_skills = Path(payload["cwd"]) / ".agents" / "skills"
                installed_skill_ids = sorted(path.name for path in runtime_skills.iterdir() if path.is_dir())
                expected_skill_ids = sorted(skill_id for skill_id in buddy_skills if isinstance(skill_id, str))
                self.assertEqual(installed_skill_ids, expected_skill_ids, msg=f"buddy={buddy_id}")
                self.assertIn("task-tool", installed_skill_ids, msg=f"buddy={buddy_id}")
                self.assertIn("track-tool", installed_skill_ids, msg=f"buddy={buddy_id}")
                self.assertIn("artifact-tool", installed_skill_ids, msg=f"buddy={buddy_id}")
                self.assertNotIn("buddybox-tool", installed_skill_ids, msg=f"buddy={buddy_id}")
                for removed in ("task" + "-manager", "track" + "-manager", "artifact" + "-manager"):
                    self.assertNotIn(removed, installed_skill_ids, msg=f"buddy={buddy_id}")

                for skill_id in expected_skill_ids:
                    source_dir = ROOT / skill_sources[skill_id]
                    target_dir = runtime_skills / skill_id
                    self._assert_directory_file_bytes_equal(source=source_dir, target=target_dir)

                if buddy_id == "dev":
                    removed_importer = "-".join(("skill", "creator", "importer"))
                    for skill_id in (
                        "enter-dev-workspace",
                        "read-implementation-context",
                        "handle-empty-source-root",
                        "implement-scoped-change",
                        "debug-regression",
                        "select-local-verification",
                        "write-implementation-report",
                        "prepare-review-readiness",
                    ):
                        self.assertTrue((runtime_skills / skill_id / "SKILL.md").exists())
                    self.assertFalse((runtime_skills / "implement-task").exists())
                    self.assertFalse((runtime_skills / removed_importer).exists())

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
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
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
            self.assertIn("Input:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance input {payload['instance_id']} --text", completed.stdout)
            self.assertIn("Attach:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance attach {payload['instance_id']}", completed.stdout)
            self.assertIn("Stop:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance stop {payload['instance_id']}", completed.stdout)
            self.assertIn("Delete instance:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance delete {payload['instance_id']} --yes", completed.stdout)

            self.assertGreaterEqual(len(payload["argv"]), 3, msg=payload["argv"])
            self.assertEqual(payload["argv"][:2], ["app-server", "--listen"])
            self.assertTrue(payload["argv"][2].startswith("unix://"))
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
            self.assertEqual(payload["tmpdir"], str(instance_root / "tmp"))
            self.assertEqual(payload["tmp"], str(instance_root / "tmp"))
            self.assertEqual(payload["temp"], str(instance_root / "tmp"))
            self.assertEqual(payload["instance_tmp"], str(instance_root / "tmp"))
            self.assertEqual(payload["tmpprefix"], str(instance_root / "tmp" / "zsh"))
            self.assertEqual(payload["buddybox_dir"], str(workspace_dir / "buddybox"))
            self.assertTrue((workspace_dir / "buddybox").is_dir())
            self.assertTrue(payload["runtime_broker_socket"], "runtime broker socket must be exported to codex")
            buddy_agents = ROOT / "tools" / "launcher" / "assets" / "buddies" / "pm" / "AGENTS.md"
            self.assertTrue(buddy_agents.exists(), "pm buddy prompt asset must be checked in")
            self.assertEqual((workspace_dir / "AGENTS.md").read_text(encoding="utf-8"), buddy_agents.read_text(encoding="utf-8"))
            self.assertTrue((workspace_dir / "AGENTS.md").read_text(encoding="utf-8").startswith("# BuddySwitch Runtime Workspace\n"))
            copied_agents = (workspace_dir / "AGENTS.md").read_text(encoding="utf-8").lower()
            for token in (
                "guidance only and not the permission source",
                "authoritative runtime tool list",
                "runtime tool examples include",
                "python3 scripts/env/client.py context summarize",
                "## output rule",
            ):
                self.assertIn(token, copied_agents)
            self.assertNotIn("use explicit ids and env tools (`", copied_agents)
            self.assertNotIn("project.access=", copied_agents)
            self.assertNotIn("projects/app", copied_agents)
            self.assertNotIn("state_effects.track", copied_agents)
            self.assertNotIn("skill_id", copied_agents)
            self.assertNotIn("persist-skill-result", copied_agents)
            self.assertNotIn("scripts/result_bridge.py", copied_agents)
            self.assertNotIn("choose exactly one skill_id from prepare_context.skills", copied_agents)
            self.assertNotIn("read and execute the selected buddyswitch skill.md", copied_agents)
            self.assertNotIn("instruction_path", copied_agents)
            runtime_skills = workspace_dir / ".agents" / "skills"
            self.assertTrue((runtime_skills / "task-tool" / "SKILL.md").exists())
            self._assert_pm_runtime_skills(workspace_dir)
            for removed in ("task" + "-manager", "track" + "-manager", "artifact" + "-manager"):
                self.assertFalse((runtime_skills / removed).exists())
            self.assertFalse((runtime_skills / "shape-prototype").exists())
            runtime_turn_runtime = workspace_dir / "scripts" / "turn_runtime.py"
            tracked_turn_runtime = subprocess.check_output(
                ["git", "-C", str(ROOT), "show", "HEAD:scripts/turn_runtime.py"],
                text=True,
            )
            self.assertEqual(
                runtime_turn_runtime.read_text(encoding="utf-8"),
                tracked_turn_runtime,
            )
            runtime_surface_candidates = (
                "scripts/env_legacy_store.py",
                "scripts/env/tool_runtime/definition.py",
                "scripts/env/tool_runtime/context.py",
                "scripts/env/tool_runtime/results.py",
                "scripts/env/tool_runtime/registry.py",
                "scripts/env/services/tasks.py",
                "scripts/env/services/tracks.py",
                "scripts/env/services/artifacts.py",
                "scripts/env/services/context.py",
                "scripts/env/services/buddybox.py",
                "scripts/env/services/evidence.py",
                "scripts/env/tools/task/tool.py",
                "scripts/env/tools/task/_impl.py",
                "scripts/env/tools/track/tool.py",
                "scripts/env/tools/track/_impl.py",
                "scripts/env/tools/artifact/tool.py",
                "scripts/env/tools/artifact/_impl.py",
                "scripts/env/tools/context/tool.py",
                "scripts/env/tools/context/_impl.py",
                "scripts/env/tools/evidence/tool.py",
                "scripts/env/tools/evidence/_impl.py",
                "scripts/env/tools/message/tool.py",
                "scripts/env/tools/message/_impl.py",
                "scripts/env/tools/comment/tool.py",
                "scripts/env/tools/comment/_impl.py",
                "scripts/env/tools/search/tool.py",
                "scripts/env/tools/search/_impl.py",
                "scripts/env/domain/source_refs.py",
                "scripts/env/domain/buddybox_workspace.py",
            )
            for relative in runtime_surface_candidates:
                tracked = subprocess.run(
                    ["git", "-C", str(ROOT), "cat-file", "-e", f"HEAD:{relative}"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if tracked.returncode != 0:
                    continue
                with self.subTest(runtime_surface=relative):
                    self.assertTrue((workspace_dir / relative).exists())
            removed_tool_files = [
                "scripts/env/tools/" + name + "_" + "manager.py"
                for name in ("task", "track", "artifact", "context", "binding", "run", "evidence")
            ]
            for relative in removed_tool_files:
                with self.subTest(removed_runtime_surface=relative):
                    self.assertFalse((workspace_dir / relative).exists())
            exclude_path = subprocess.check_output(
                ["git", "-C", str(workspace_dir), "rev-parse", "--git-path", "info/exclude"],
                text=True,
            ).strip()
            resolved_exclude = Path(exclude_path)
            if not resolved_exclude.is_absolute():
                resolved_exclude = workspace_dir / resolved_exclude
            local_excludes = resolved_exclude.read_text(encoding="utf-8")
            self.assertIn(".agents/skills/**", local_excludes)
            self.assertTrue((instance_root / "browser" / "profile").exists())
            self.assertTrue((instance_root / "browser" / "chrome.pid").exists())
            self.assertTrue((instance_root / "browser" / "chrome.log").exists())
            self.assertTrue((workspace_dir / "buddybox").is_dir())
            self.assertTrue((instance_root / "tmp").is_dir())
            self.assertFalse((shared_root / "chrome" / "shared-browser").exists())
            self.assertFalse((shared_root / "run" / "browser-cockpit.pid").exists())
            workspace_project_config = workspace_dir / ".codex" / "config.toml"
            self.assertFalse(
                workspace_project_config.exists(),
                "product instance workspace must not keep project .codex/config.toml because it can override launcher-managed CODEX_HOME config",
            )
            self.assertTrue((instance_root / "codex-home" / "config.toml").exists())
            config_text = (instance_root / "codex-home" / "config.toml").read_text(encoding="utf-8")
            self._assert_codex_automation_config(config_text, shared_root=shared_root)
            self.assertIn("[mcp_servers.chrome-devtools-cockpit]", config_text)
            self.assertIn('default_tools_approval_mode = "approve"', config_text)
            self.assertIn("unix_sockets = {", config_text)
            resolved_broker_socket = str(Path(payload["runtime_broker_socket"]).resolve(strict=False))
            self.assertIn(" = \"allow\"", config_text)
            self.assertIn(json.dumps(resolved_broker_socket), config_text)
            self.assertNotIn("supports_parallel_tool_calls", config_text)
            instance_auth = instance_root / "codex-home" / "auth.json"
            shared_auth = shared_root / "codex-home" / "auth.json"
            self.assertTrue(shared_auth.exists())
            self.assertTrue(instance_auth.exists())
            self.assertFalse(instance_auth.is_file() and not instance_auth.is_symlink())
            self.assertEqual(instance_auth.resolve(), shared_auth.resolve())
            self.assertEqual(instance_snapshot["instance_id"], payload["instance_id"])
            self.assertEqual(instance_snapshot["buddy"], "pm")
            self.assertNotIn("current_task_id", instance_snapshot)
            self.assertNotIn("current_track_id", instance_snapshot)
            self.assertEqual(instance_snapshot["instance_root"], str(instance_root))
            self.assertEqual(instance_snapshot["workspace_dir"], str(workspace_dir))
            browser_port = instance_snapshot["browser_port"]
            self.assertIsInstance(browser_port, int)
            self.assertTrue(instance_snapshot["updated_at"])

            stored_instance = json.loads(instance_json_path.read_text(encoding="utf-8"))
            self.assertEqual(stored_instance["status"], "active")
            self.assertEqual(stored_instance["instance_id"], payload["instance_id"])
            self.assertEqual(stored_instance["buddy"], "pm")
            self.assertEqual(stored_instance["instance_root"], str(instance_root))
            self.assertEqual(stored_instance["workspace_dir"], str(workspace_dir))
            self.assertNotIn("current_task_id", stored_instance)
            self.assertNotIn("current_track_id", stored_instance)
            self.assertEqual(stored_instance["browser_port"], browser_port)
            self.assertIn("thread_id", stored_instance)
            self.assertIn("app_server_pid", stored_instance)
            self.assertIn("app_server_socket", stored_instance)
            self.assertIn("app_server_log", stored_instance)
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

            for relative_path in (
                "buddyswitch/objects" + "/tasks",
                "buddyswitch/objects/tracks",
                "buddyswitch/objects/artifacts",
            ):
                projected_path = workspace_dir / relative_path
                self.assertFalse(
                    projected_path.exists() or projected_path.is_symlink(),
                    f"runtime workspace must not expose projected state path: {projected_path}",
                )

            buddybox_root = workspace_dir / "buddybox"
            shared_buddybox_root = shared_root / "state" / "buddyswitch" / "local" / "buddybox" / "pm"
            self.assertTrue(buddybox_root.is_dir(), "active buddybox root must exist in the instance workspace")
            self.assertFalse(shared_buddybox_root.exists(), "shared state buddybox remains tool-backed until written")

            self.assertFalse((workspace_dir / "buddyswitch/local/buddybox/dev").exists())
            self.assertFalse((workspace_dir / "buddyswitch/content/" / "buddybox").exists())

            for retired_relative_path in ("runs/raw", "buddyswitch/content/runs"):
                self.assertFalse((workspace_dir / retired_relative_path).exists())

    def test_start_with_buddy_returns_json_metadata_when_requested(self) -> None:
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
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "--json"],
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

            payload = json.loads(completed.stdout)
            capture_payload = json.loads(capture_path.read_text(encoding="utf-8"))
            stored_instance = json.loads(Path(capture_payload["instance_json"]).read_text(encoding="utf-8"))

            self.assertTrue(payload["instance_id"].startswith("inst-pm-"))
            self.assertEqual(payload["buddy"], "pm")
            self.assertEqual(payload["workspace_dir"], stored_instance["workspace_dir"])
            self.assertEqual(payload["project_workspace_dir"], capture_payload["project_workspace_dir"])
            self.assertEqual(payload["instance_record"], capture_payload["instance_json"])
            self.assertNotIn("Input: ./buddyswitch-codex", completed.stdout)
            self.assertEqual(stored_instance["instance_id"], payload["instance_id"])
            self.assertEqual(stored_instance["status"], "active")
            self.assertIn("thread_id", stored_instance)
            self.assertIn("app_server_pid", stored_instance)

    def test_start_with_buddy_starts_app_server_service_and_returns(self) -> None:
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
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
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
            instance_id = payload["instance_id"]
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / instance_id
            instance_json_path = instance_root / "instance.json"
            instance_payload = json.loads(instance_json_path.read_text(encoding="utf-8"))

            self.assertIn(f"./buddyswitch-codex instance input {instance_id} --text", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance attach {instance_id}", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance stop {instance_id}", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance delete {instance_id} --yes", completed.stdout)
            self.assertGreaterEqual(len(payload["argv"]), 3, msg=payload["argv"])
            self.assertEqual(payload["argv"][:2], ["app-server", "--listen"])
            self.assertTrue(payload["argv"][2].startswith("unix://"))
            self.assertEqual(payload["active_buddy"], "pm")
            self.assertEqual(payload["instance_id"], instance_id)
            self.assertEqual(instance_payload["status"], "active")
            self.assertIn("thread_id", instance_payload)
            self.assertIn("app_server_pid", instance_payload)
            self.assertIn("app_server_socket", instance_payload)
            self.assertIn("app_server_log", instance_payload)
            self.assertTrue(payload["runtime_broker_socket"])
            self.assertIn(json.dumps(str(Path(payload["runtime_broker_socket"]).resolve(strict=False))), payload["config_toml"])
            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rpc_rows = [row for row in call_entries if row["argv"][:1] == ["json-rpc"]]
            thread_start = next(row for row in rpc_rows if row["rpc_method"] == "thread/start")
            self.assertEqual(thread_start["params"]["permissions"], "buddyswitch-runtime")
            self.assertIn("runtimeWorkspaceRoots", thread_start["params"])
            self.assertNotIn("sandboxPolicy", thread_start["params"])

    def test_start_rejects_codex_args_passthrough(self) -> None:
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

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "--", "debug", "prompt-input", "x"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, msg=completed.stderr)
            self.assertIn("start no longer accepts Codex args", completed.stderr)
            self.assertFalse((source_home_path / ".codex-buddyswitch" / "instances").exists())

    def test_start_with_buddy_allocates_next_browser_port_when_default_is_busy(self) -> None:
        busy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        owns_busy_socket = False
        try:
            busy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            busy_socket.bind(("127.0.0.1", 9222))
            busy_socket.listen(1)
            owns_busy_socket = True
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                busy_socket.close()
                busy_socket = None
            else:
                busy_socket.close()
                self.skipTest(f"port 9222 is not available for the busy-port precondition: {exc}")
        if owns_busy_socket:
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
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
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

    def test_input_starts_turn_when_thread_idle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            input_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    ctx["instance_id"],
                    "--text",
                    "Draft brief",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rpc_rows = [row for row in calls if row["argv"][:1] == ["json-rpc"]]
            methods = [row["rpc_method"] for row in rpc_rows]
            self.assertIn("thread/read", methods)
            self.assertIn("turn/start", methods)
            self.assertNotIn("turn/steer", methods)
            turn_start = next(row for row in rpc_rows if row["rpc_method"] == "turn/start")
            self.assertEqual(turn_start["params"]["threadId"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(
                turn_start["params"]["input"],
                [{"type": "text", "text": "Draft brief", "text_elements": []}],
            )
            self.assertEqual(turn_start["params"]["permissions"], "buddyswitch-runtime")
            self.assertNotIn("sandboxPolicy", turn_start["params"])
            self.assertIn("turn-test", input_result.stdout)

    def test_input_json_starts_turn_when_thread_idle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            input_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    ctx["instance_id"],
                    "--text",
                    "Draft brief",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)
            payload = json.loads(input_result.stdout)
            self.assertEqual(payload["instance_id"], ctx["instance_id"])
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["action"], "start")
            self.assertTrue(payload["turn_id"])
            self.assertNotIn("Started turn:", input_result.stdout)

    def test_input_steers_in_progress_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_status": {"type": "active", "activeFlags": []},
                    "turns": [
                        {
                            "id": "turn-123",
                            "items": [],
                            "itemsView": "summary",
                            "status": "inProgress",
                            "error": None,
                            "startedAt": 0,
                            "completedAt": None,
                            "durationMs": None,
                        }
                    ],
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            input_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    ctx["instance_id"],
                    "--text",
                    "Steer current turn",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rpc_rows = [row for row in calls if row["argv"][:1] == ["json-rpc"]]
            methods = [row["rpc_method"] for row in rpc_rows]
            self.assertIn("thread/read", methods)
            self.assertIn("thread/turns/list", methods)
            self.assertIn("turn/steer", methods)
            self.assertNotIn("turn/start", methods)
            steer = next(row for row in rpc_rows if row["rpc_method"] == "turn/steer")
            self.assertEqual(steer["params"]["expectedTurnId"], "turn-123")

    def test_input_json_includes_expected_turn_id_when_steering(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_status": {"type": "active", "activeFlags": []},
                    "turns": [
                        {
                            "id": "turn-123",
                            "items": [],
                            "itemsView": "summary",
                            "status": "inProgress",
                            "error": None,
                            "startedAt": 0,
                            "completedAt": None,
                            "durationMs": None,
                        }
                    ],
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            input_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    ctx["instance_id"],
                    "--text",
                    "Steer current turn",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)
            payload = json.loads(input_result.stdout)
            self.assertEqual(payload["instance_id"], ctx["instance_id"])
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["action"], "steer")
            self.assertEqual(payload["turn_id"], "turn-123")
            self.assertEqual(payload["expected_turn_id"], "turn-123")
            self.assertNotIn("Steered turn:", input_result.stdout)

    def test_goal_set_json_calls_thread_goal_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            goal_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "goal",
                    ctx["instance_id"],
                    "set",
                    "--objective",
                    "Ship launcher goal API",
                    "--token-budget",
                    "1234",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(goal_result.returncode, 0, msg=goal_result.stderr)
            payload = json.loads(goal_result.stdout)
            self.assertEqual(payload["instance_id"], ctx["instance_id"])
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["goal"]["objective"], "Ship launcher goal API")
            self.assertEqual(payload["goal"]["tokenBudget"], 1234)
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rpc_rows = [row for row in calls if row["argv"][:1] == ["json-rpc"]]
            goal_set = next(row for row in rpc_rows if row["rpc_method"] == "thread/goal/set")
            self.assertEqual(goal_set["params"]["threadId"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(goal_set["params"]["objective"], "Ship launcher goal API")
            self.assertEqual(goal_set["params"]["tokenBudget"], 1234)

    def test_goal_get_and_clear_json_use_thread_goal_rpc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "goal": {
                        "threadId": "thread-inst-pm-test",
                        "objective": "Existing objective",
                        "status": "active",
                        "tokenBudget": None,
                        "tokensUsed": 0,
                        "timeUsedSeconds": 0,
                        "createdAt": 0,
                        "updatedAt": 0,
                    }
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            get_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "goal",
                    ctx["instance_id"],
                    "get",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(get_result.returncode, 0, msg=get_result.stderr)
            get_payload = json.loads(get_result.stdout)
            self.assertEqual(get_payload["goal"]["objective"], "Existing objective")

            clear_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "goal",
                    ctx["instance_id"],
                    "clear",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(clear_result.returncode, 0, msg=clear_result.stderr)
            clear_payload = json.loads(clear_result.stdout)
            self.assertEqual(clear_payload["instance_id"], ctx["instance_id"])
            self.assertEqual(clear_payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(clear_payload["cleared"], True)
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            methods = [row["rpc_method"] for row in calls if row["argv"][:1] == ["json-rpc"]]
            self.assertIn("thread/goal/get", methods)
            self.assertIn("thread/goal/clear", methods)

    def test_compact_json_calls_thread_compact_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            compact_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "compact",
                    ctx["instance_id"],
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(compact_result.returncode, 0, msg=compact_result.stderr)
            payload = json.loads(compact_result.stdout)
            self.assertEqual(payload["instance_id"], ctx["instance_id"])
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            compact = next(row for row in calls if row.get("rpc_method") == "thread/compact/start")
            self.assertEqual(compact["params"]["threadId"], ctx["instance_payload"]["thread_id"])

    def test_clear_json_starts_clear_thread_and_updates_instance_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={"clear_thread_id": "thread-cleared"},
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            clear_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "clear",
                    ctx["instance_id"],
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(clear_result.returncode, 0, msg=clear_result.stderr)
            payload = json.loads(clear_result.stdout)
            self.assertEqual(payload["instance_id"], ctx["instance_id"])
            self.assertEqual(payload["previous_thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["thread_id"], "thread-cleared")
            instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_payload["thread_id"], "thread-cleared")
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            thread_start = next(row for row in calls if row.get("rpc_method") == "thread/start")
            self.assertEqual(thread_start["params"]["sessionStartSource"], "clear")
            self.assertEqual(thread_start["params"]["permissions"], "buddyswitch-runtime")

    def test_input_reports_non_steerable_active_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_status": {"type": "active", "activeFlags": []},
                    "turns": [
                        {
                            "id": "turn-123",
                            "items": [],
                            "itemsView": "summary",
                            "status": "inProgress",
                            "error": None,
                            "startedAt": 0,
                            "completedAt": None,
                            "durationMs": None,
                        }
                    ],
                    "errors": {
                        "turn/steer": {
                            "code": -32005,
                            "message": "turn not steerable",
                        }
                    },
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            input_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    ctx["instance_id"],
                    "--text",
                    "Steer current turn",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(input_result.returncode, 0)
            self.assertIn("interrupt", input_result.stderr.lower())
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rpc_rows = [row for row in calls if row["argv"][:1] == ["json-rpc"]]
            methods = [row["rpc_method"] for row in rpc_rows]
            self.assertIn("turn/steer", methods)
            self.assertNotIn("turn/start", methods)

    def test_input_rejects_inactive_or_unhealthy_instance(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-unhealthy"
            instance_root, _workspace_dir = self._write_instance_record(
                shared_root,
                instance_id,
                status="active",
                thread_id="thread-test",
                app_server_pid=999999,
                app_server_socket="/tmp/buddyswitch-app-server-missing.sock",
                app_server_log=str(shared_root / "instances" / instance_id / "runtime" / "app-server.log"),
            )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_TEST_CALLS"] = str(instance_root / "calls.jsonl")

            input_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    instance_id,
                    "--text",
                    "Draft brief",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(input_result.returncode, 0)
            self.assertIn("unhealthy", input_result.stderr.lower())
            calls_path = instance_root / "calls.jsonl"
            self.assertFalse(calls_path.exists())

    def test_input_requires_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            input_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    ctx["instance_id"],
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 2)
            self.assertIn("--text", input_result.stderr)
            self.assertEqual(Path(str(ctx["calls_path"])).read_text(encoding="utf-8"), "")

    def test_attach_invokes_remote_tui_without_local_resume_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            attach_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "attach",
                    ctx["instance_id"],
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(attach_result.returncode, 0, msg=attach_result.stderr)
            payload = json.loads(Path(str(ctx["capture_path"])).read_text(encoding="utf-8"))
            instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(
                payload["argv"],
                [
                    "--remote",
                    f"unix://{instance_payload['app_server_socket']}",
                ],
            )
            self.assertEqual(instance_payload["status"], "active")
            self.assertTrue(Path(instance_payload["app_server_socket"]).exists())

    def test_attach_rejects_missing_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            instance_json_path = Path(str(ctx["instance_root"])) / "instance.json"
            instance_payload = json.loads(instance_json_path.read_text(encoding="utf-8"))
            instance_payload["thread_id"] = None
            instance_json_path.write_text(json.dumps(instance_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

            attach_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "attach",
                    ctx["instance_id"],
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(attach_result.returncode, 0)
            self.assertIn("stop/delete", attach_result.stderr.lower())

    def test_attach_rejects_unhealthy_app_server(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-attach-unhealthy"
            self._write_instance_record(
                shared_root,
                instance_id,
                status="active",
                thread_id="thread-test",
                app_server_pid=999999,
                app_server_socket="/tmp/buddyswitch-app-server-missing.sock",
                app_server_log=str(shared_root / "instances" / instance_id / "runtime" / "app-server.log"),
            )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            attach_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "attach",
                    instance_id,
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(attach_result.returncode, 0)
            self.assertIn("unhealthy", attach_result.stderr.lower())

    def test_stop_active_instance_stops_service_broker_browser_and_marks_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            app_server_socket = Path(str(instance_payload["app_server_socket"]))
            app_server_pid_file = Path(str(ctx["instance_root"])) / "runtime" / "app-server.pid"
            app_server_marker = Path(str(ctx["instance_root"])) / "runtime" / "app-server.socket"
            broker_pid = Path(str(ctx["instance_root"])) / "runtime" / "runtime-broker.pid"
            broker_marker = Path(str(ctx["instance_root"])) / "runtime" / "runtime-broker.socket"
            broker_socket = Path(str(ctx["instance_root"])) / "runtime" / "runtime-broker.sock"
            browser_pid = Path(str(ctx["instance_root"])) / "browser" / "chrome.pid"

            stop_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "stop",
                    ctx["instance_id"],
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)

            stored = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "inactive")
            self.assertIsNone(stored["app_server_pid"])
            self.assertIsNone(stored["app_server_socket"])
            self.assertIsNone(stored["app_server_log"])
            self.assertFalse(app_server_socket.exists())
            self.assertFalse(app_server_pid_file.exists())
            self.assertFalse(app_server_marker.exists())
            self.assertFalse(broker_pid.exists())
            self.assertFalse(broker_marker.exists())
            self.assertFalse(broker_socket.exists())
            self.assertFalse(browser_pid.exists())

    def test_stop_json_marks_instance_inactive_after_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            app_server_socket = Path(str(instance_payload["app_server_socket"]))
            app_server_pid_file = Path(str(ctx["instance_root"])) / "runtime" / "app-server.pid"
            app_server_marker = Path(str(ctx["instance_root"])) / "runtime" / "app-server.socket"
            broker_pid = Path(str(ctx["instance_root"])) / "runtime" / "runtime-broker.pid"
            broker_marker = Path(str(ctx["instance_root"])) / "runtime" / "runtime-broker.socket"
            broker_socket = Path(str(ctx["instance_root"])) / "runtime" / "runtime-broker.sock"
            browser_pid = Path(str(ctx["instance_root"])) / "browser" / "chrome.pid"

            stop_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "stop",
                    ctx["instance_id"],
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)
            self.assertEqual(
                json.loads(stop_result.stdout),
                {"instance_id": ctx["instance_id"], "status": "inactive"},
            )

            stored = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "inactive")
            self.assertIsNone(stored["app_server_pid"])
            self.assertIsNone(stored["app_server_socket"])
            self.assertIsNone(stored["app_server_log"])
            self.assertFalse(app_server_socket.exists())
            self.assertFalse(app_server_pid_file.exists())
            self.assertFalse(app_server_marker.exists())
            self.assertFalse(broker_pid.exists())
            self.assertFalse(broker_marker.exists())
            self.assertFalse(broker_socket.exists())
            self.assertFalse(browser_pid.exists())

    def test_stop_is_idempotent_for_stale_service(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-stale-stop"
            instance_root, _workspace_dir = self._write_instance_record(
                shared_root,
                instance_id,
                status="active",
                thread_id="thread-test",
                app_server_pid=999999,
                app_server_socket="/tmp/buddyswitch-app-server-stale.sock",
                app_server_log=str(shared_root / "instances" / instance_id / "runtime" / "app-server.log"),
            )
            runtime_dir = instance_root / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "app-server.pid").write_text("999999\n", encoding="utf-8")
            (runtime_dir / "app-server.socket").write_text("/tmp/buddyswitch-app-server-stale.sock\n", encoding="utf-8")
            (runtime_dir / "runtime-broker.pid").write_text("999999\n", encoding="utf-8")
            (runtime_dir / "runtime-broker.socket").write_text("/tmp/buddyswitch-runtime-stale.sock\n", encoding="utf-8")
            browser_dir = instance_root / "browser"
            browser_dir.mkdir(parents=True, exist_ok=True)
            (browser_dir / "chrome.pid").write_text("999999\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            stop_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "stop",
                    instance_id,
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)
            stored = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "inactive")
            self.assertFalse((runtime_dir / "app-server.pid").exists())
            self.assertFalse((runtime_dir / "app-server.socket").exists())
            self.assertFalse((runtime_dir / "runtime-broker.pid").exists())
            self.assertFalse((runtime_dir / "runtime-broker.socket").exists())
            self.assertFalse((browser_dir / "chrome.pid").exists())

    def test_status_reports_app_server_health_and_thread_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_status": {"type": "idle"},
                    "turns": [],
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            status_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "status",
                    ctx["instance_id"],
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_result.returncode, 0, msg=status_result.stderr)
            payload = json.loads(status_result.stdout)
            self.assertEqual(payload["instance_id"], ctx["instance_id"])
            self.assertEqual(payload["buddy"], "pm")
            self.assertEqual(payload["status"], "active")
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["app_server"]["healthy"], True)
            self.assertEqual(payload["thread"]["status"], "idle")

    def test_list_includes_app_server_health_and_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            list_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "list",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(list_result.returncode, 0, msg=list_result.stderr)
            self.assertIn("instance_id\tbuddy\tstatus\tapp_server_health\tthread_id\tbrowser_port\tupdated_at\tworkspace_dir", list_result.stdout)
            self.assertIn(
                f"{ctx['instance_id']}\tpm\tactive\thealthy\t{ctx['instance_payload']['thread_id']}\t",
                list_result.stdout,
            )

    def test_interrupt_interrupts_active_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_status": {"type": "active", "activeFlags": []},
                    "turns": [
                        {
                            "id": "turn-123",
                            "items": [],
                            "itemsView": "summary",
                            "status": "inProgress",
                            "error": None,
                            "startedAt": 0,
                            "completedAt": None,
                            "durationMs": None,
                        }
                    ],
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            interrupt_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "interrupt",
                    ctx["instance_id"],
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(interrupt_result.returncode, 0, msg=interrupt_result.stderr)
            self.assertIn("turn-123", interrupt_result.stdout)
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rpc_rows = [row for row in calls if row["argv"][:1] == ["json-rpc"]]
            methods = [row["rpc_method"] for row in rpc_rows]
            self.assertIn("thread/turns/list", methods)
            self.assertIn("turn/interrupt", methods)
            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            self.assertEqual(state_payload["thread_status"]["type"], "idle")
            self.assertEqual(state_payload["turns"][0]["status"], "interrupted")

    def test_interrupt_json_returns_interrupted_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_status": {"type": "active", "activeFlags": []},
                    "turns": [
                        {
                            "id": "turn-123",
                            "items": [],
                            "itemsView": "summary",
                            "status": "inProgress",
                            "error": None,
                            "startedAt": 0,
                            "completedAt": None,
                            "durationMs": None,
                        }
                    ],
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            interrupt_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "interrupt",
                    ctx["instance_id"],
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(interrupt_result.returncode, 0, msg=interrupt_result.stderr)
            payload = json.loads(interrupt_result.stdout)
            self.assertEqual(payload["instance_id"], ctx["instance_id"])
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["turn_id"], "turn-123")
            self.assertNotIn("Interrupted turn:", interrupt_result.stdout)

    def test_interrupt_rejects_when_no_active_turn_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_status": {"type": "idle"},
                    "turns": [],
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            interrupt_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "interrupt",
                    ctx["instance_id"],
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(interrupt_result.returncode, 0)
            self.assertIn("no active in-progress turn", interrupt_result.stderr.lower())
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rpc_rows = [row for row in calls if row["argv"][:1] == ["json-rpc"]]
            methods = [row["rpc_method"] for row in rpc_rows]
            self.assertIn("thread/turns/list", methods)
            self.assertNotIn("turn/interrupt", methods)

    def test_instance_open_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            capture_path = temp_root_path / "capture-open-removed.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            result = subprocess.run(
                [str(LAUNCHER), "instance", "open", "inst-pm-example"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Unknown instance command: open", result.stderr)
            self.assertFalse(capture_path.exists(), "removed command must not invoke codex")

    def test_locked_old_open_entrypoint_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            capture_path = temp_root_path / "capture-locked-open-removed.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            removed_locked_command = "__locked-instance-" + "open-bootstrap"
            result = subprocess.run(
                [str(LAUNCHER), removed_locked_command],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Unknown top-level command", result.stderr)
            self.assertFalse(capture_path.exists(), "removed locked open entrypoint must not invoke codex")

    def test_start_with_buddy_creates_shared_project_workspace(self) -> None:
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
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
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
            runtime_workspace_dir = instance_root / "workspace"
            project_workspace_dir = shared_root / "project" / "workspace"

            self.assertEqual(payload["cwd"], str(runtime_workspace_dir.resolve()))
            self.assertNotEqual(payload["cwd"], str(project_workspace_dir.resolve()))
            self.assertEqual(
                payload["project_workspace_dir"],
                str(project_workspace_dir),
            )

            self.assertTrue(project_workspace_dir.is_dir())
            project_app_dir = project_workspace_dir / "projects" / "app"
            placeholder_path = project_app_dir / "README.md"
            self.assertTrue(project_app_dir.is_dir())
            self.assertTrue(placeholder_path.is_file())
            self.assertIn(
                "BuddySwitch runtime mount point",
                placeholder_path.read_text(encoding="utf-8"),
            )
            for sample_file in ("index.html", "main.js", "styles.css"):
                self.assertFalse((project_app_dir / sample_file).exists(), msg=sample_file)

            forbidden_project_workspace_entries = (
                "buddyswitch",
                "tools",
                "scripts",
                "tests",
                "framework",
                "docs",
                "AGENTS.md",
                "README.md",
                "buddyswitch-codex",
            )
            for entry_name in forbidden_project_workspace_entries:
                self.assertFalse(
                    (project_workspace_dir / entry_name).exists(),
                    msg=f"project workspace must not expose framework entry: {entry_name}",
                )

            sparse_list = subprocess.check_output(
                ["git", "-C", str(project_workspace_dir), "sparse-checkout", "list"],
                text=True,
            ).splitlines()
            self.assertEqual(sparse_list, ["projects/app/"])
            projects_app_probe = payload["projects_app_probe"]
            self.assertTrue(projects_app_probe["exists"])
            self.assertEqual(
                projects_app_probe["resolved"],
                str((project_workspace_dir / "projects" / "app").resolve()),
            )
            self.assertFalse((project_workspace_dir / "projects" / "app" / ".runtime").exists())

            source_git_common_dir = self._repo_git_common_dir(ROOT)
            self.assertEqual(self._repo_git_common_dir(project_workspace_dir), source_git_common_dir)

    def test_start_uses_shared_project_workspace_and_instance_workspace(self) -> None:
        self.test_start_with_buddy_creates_shared_project_workspace()

    def test_start_narrows_existing_full_project_worktree(self) -> None:
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

            shared_root = source_home_path / ".codex-buddyswitch"
            project_workspace_dir = shared_root / "project" / "workspace"
            project_workspace_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(project_workspace_dir), "HEAD"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            self.addCleanup(
                subprocess.run,
                ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(project_workspace_dir)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertTrue((project_workspace_dir / "tools").exists())
            product_sentinel = project_workspace_dir / "projects" / "app" / "migration-sentinel.txt"
            product_sentinel.write_text("preserve\n", encoding="utf-8")

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            capture_path = temp_root_path / "capture.json"
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            self.assertFalse((project_workspace_dir / "tools").exists())
            self.assertFalse((project_workspace_dir / "buddyswitch").exists())
            self.assertTrue((project_workspace_dir / "projects" / "app").is_dir())
            self.assertEqual(product_sentinel.read_text(encoding="utf-8"), "preserve\n")
            sparse_list = subprocess.check_output(
                ["git", "-C", str(project_workspace_dir), "sparse-checkout", "list"],
                text=True,
            ).splitlines()
            self.assertEqual(sparse_list, ["projects/app/"])

    def test_start_rejects_dirty_non_project_project_worktree_before_sparse_narrowing(self) -> None:
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

            shared_root = source_home_path / ".codex-buddyswitch"
            project_workspace_dir = shared_root / "project" / "workspace"
            project_workspace_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(project_workspace_dir), "HEAD"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            self.addCleanup(
                subprocess.run,
                ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(project_workspace_dir)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            dirty_file = project_workspace_dir / "tools" / "launcher" / "dirty-non-project-change.txt"
            dirty_file.write_text("do not delete silently\n", encoding="utf-8")

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
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("local changes outside projects/app", completed.stderr)
            self.assertTrue(dirty_file.exists())
            self.assertTrue((project_workspace_dir / "tools").exists())
            self.assertFalse(capture_path.exists())

    def test_start_rejects_dirty_non_project_file_in_existing_sparse_project_worktree(self) -> None:
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
            first_capture_path = temp_root_path / "capture-first.json"
            second_capture_path = temp_root_path / "capture-second.json"

            base_env = os.environ.copy()
            base_env["HOME"] = str(source_home_path)
            base_env.pop("CODEX_HOME", None)
            base_env["PATH"] = f"{fake_bin}{os.pathsep}{base_env.get('PATH', '')}"
            base_env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            base_env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            base_env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)

            first_env = base_env.copy()
            first_env["BUDDYSWITCH_TEST_CAPTURE"] = str(first_capture_path)
            first_start = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=first_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(first_start.returncode, 0, msg=first_start.stderr)
            self.assertTrue(first_capture_path.exists())

            shared_root = source_home_path / ".codex-buddyswitch"
            project_workspace_dir = shared_root / "project" / "workspace"
            sparse_list = subprocess.check_output(
                ["git", "-C", str(project_workspace_dir), "sparse-checkout", "list"],
                text=True,
            ).splitlines()
            self.assertEqual(sparse_list, ["projects/app/"])

            root_stray = project_workspace_dir / "root-stray.txt"
            root_stray.write_text("do not ignore sparse stray\n", encoding="utf-8")

            second_env = base_env.copy()
            second_env["BUDDYSWITCH_TEST_CAPTURE"] = str(second_capture_path)
            second_start = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=second_env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(second_start.returncode, 0)
            self.assertIn("local changes outside projects/app", second_start.stderr)
            self.assertTrue(root_stray.exists())
            self.assertFalse(second_capture_path.exists())
            sparse_list_after_failure = subprocess.check_output(
                ["git", "-C", str(project_workspace_dir), "sparse-checkout", "list"],
                text=True,
            ).splitlines()
            self.assertEqual(sparse_list_after_failure, ["projects/app/"])

    def test_product_mode_projects_app_resolves_to_shared_project_app(self) -> None:
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
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_RELATIVE_WRITE_PATH"] = "relative-path-sentinel.txt"
            env["BUDDYSWITCH_TEST_RELATIVE_WRITE_CONTENT"] = "shared-relative-write"

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            runtime_workspace_dir = shared_root / "instances" / payload["instance_id"] / "workspace"
            shared_project_workspace = shared_root / "project" / "workspace"
            shared_project_app = shared_project_workspace / "projects" / "app"

            self.assertEqual(payload["cwd"], str(runtime_workspace_dir.resolve()))
            self.assertEqual(payload["project_workspace_dir"], str(shared_project_workspace))

            projects_app_probe = payload["projects_app_probe"]
            self.assertTrue(projects_app_probe["exists"])
            self.assertEqual(projects_app_probe["resolved"], str(shared_project_app.resolve()))

            relative_probe = payload["relative_probe"]
            self.assertIsNotNone(relative_probe)
            assert relative_probe is not None
            write_probe = relative_probe["write"]
            self.assertTrue(write_probe["ok"])
            self.assertEqual(
                write_probe["resolved"],
                str((shared_project_app / "relative-path-sentinel.txt").resolve()),
            )
            self.assertEqual(write_probe["content"], "shared-relative-write")
            self.assertTrue((shared_project_app / "relative-path-sentinel.txt").exists())

    def test_cross_buddy_relative_projects_app_is_shared(self) -> None:
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

            pm_capture_path = temp_root_path / "capture-pm.json"
            dev_capture_path = temp_root_path / "capture-dev.json"
            ready_file = temp_root_path / "browser-ready.flag"

            base_env = os.environ.copy()
            base_env["HOME"] = str(source_home_path)
            base_env.pop("CODEX_HOME", None)
            base_env["PATH"] = f"{fake_bin}{os.pathsep}{base_env.get('PATH', '')}"
            base_env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            base_env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            base_env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)

            pm_env = base_env.copy()
            pm_env["BUDDYSWITCH_TEST_CAPTURE"] = str(pm_capture_path)
            pm_env["BUDDYSWITCH_TEST_RELATIVE_WRITE_PATH"] = "cross-buddy-sentinel.txt"
            pm_env["BUDDYSWITCH_TEST_RELATIVE_WRITE_CONTENT"] = "shared-via-relative-path"
            pm_start = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=pm_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(pm_start.returncode, 0, msg=pm_start.stderr)

            dev_env = base_env.copy()
            dev_env["BUDDYSWITCH_TEST_CAPTURE"] = str(dev_capture_path)
            dev_env["BUDDYSWITCH_TEST_RELATIVE_READ_PATH"] = "cross-buddy-sentinel.txt"
            dev_start = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "dev"],
                cwd=ROOT,
                env=dev_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(dev_start.returncode, 0, msg=dev_start.stderr)

            pm_payload = json.loads(pm_capture_path.read_text(encoding="utf-8"))
            dev_payload = json.loads(dev_capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            shared_project_app = shared_root / "project" / "workspace" / "projects" / "app"

            self.assertEqual(
                pm_payload["projects_app_probe"]["resolved"],
                str(shared_project_app.resolve()),
            )
            self.assertEqual(
                dev_payload["projects_app_probe"]["resolved"],
                str(shared_project_app.resolve()),
            )

            pm_relative_probe = pm_payload["relative_probe"]
            dev_relative_probe = dev_payload["relative_probe"]
            self.assertIsNotNone(pm_relative_probe)
            self.assertIsNotNone(dev_relative_probe)
            assert pm_relative_probe is not None
            assert dev_relative_probe is not None
            self.assertEqual(
                pm_relative_probe["write"]["resolved"],
                str((shared_project_app / "cross-buddy-sentinel.txt").resolve()),
            )
            read_probe = dev_relative_probe["read"]
            self.assertTrue(read_probe["exists"])
            self.assertEqual(read_probe["content"], "shared-via-relative-path")

    def test_product_start_does_not_migrate_legacy_shared_workspace_state(self) -> None:
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
            legacy_runtime_marker = shared_root / "workspace" / "projects" / "app" / ".runtime" / "legacy.json"
            legacy_runtime_marker.parent.mkdir(parents=True, exist_ok=True)
            legacy_runtime_marker.write_text("{\"legacy\":true}\n", encoding="utf-8")

            capture_path = temp_root_path / "capture.json"
            ready_file = temp_root_path / "browser-ready.flag"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            project_workspace_dir = shared_root / "project" / "workspace"
            self.assertFalse(
                (project_workspace_dir / "projects" / "app" / ".runtime" / "legacy.json").exists(),
            )

    def test_project_workspace_is_shared_across_buddy_instances(self) -> None:
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

            pm_capture_path = temp_root_path / "capture-pm.json"
            dev_capture_path = temp_root_path / "capture-dev.json"
            ready_file = temp_root_path / "browser-ready.flag"

            base_env = os.environ.copy()
            base_env["HOME"] = str(source_home_path)
            base_env.pop("CODEX_HOME", None)
            base_env["PATH"] = f"{fake_bin}{os.pathsep}{base_env.get('PATH', '')}"
            base_env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            base_env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            base_env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)

            pm_env = base_env.copy()
            pm_env["BUDDYSWITCH_TEST_CAPTURE"] = str(pm_capture_path)
            pm_env["BUDDYSWITCH_TEST_RELATIVE_WRITE_PATH"] = "shared-product-sentinel.txt"
            pm_env["BUDDYSWITCH_TEST_RELATIVE_WRITE_CONTENT"] = "shared-pm-sentinel"
            pm_start = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=pm_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(pm_start.returncode, 0, msg=pm_start.stderr)

            dev_env = base_env.copy()
            dev_env["BUDDYSWITCH_TEST_CAPTURE"] = str(dev_capture_path)
            dev_env["BUDDYSWITCH_TEST_RELATIVE_READ_PATH"] = "shared-product-sentinel.txt"
            dev_start = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "dev"],
                cwd=ROOT,
                env=dev_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(dev_start.returncode, 0, msg=dev_start.stderr)

            pm_payload = json.loads(pm_capture_path.read_text(encoding="utf-8"))
            dev_payload = json.loads(dev_capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            expected_project_workspace = shared_root / "project" / "workspace"

            self.assertEqual(
                pm_payload["project_workspace_dir"],
                str(expected_project_workspace),
            )
            self.assertEqual(
                dev_payload["project_workspace_dir"],
                str(expected_project_workspace),
            )
            self.assertEqual(
                pm_payload["cwd"],
                str((shared_root / "instances" / pm_payload["instance_id"] / "workspace").resolve()),
            )
            self.assertEqual(
                dev_payload["cwd"],
                str((shared_root / "instances" / dev_payload["instance_id"] / "workspace").resolve()),
            )

            shared_project_app = expected_project_workspace / "projects" / "app"
            self.assertEqual(
                pm_payload["projects_app_probe"]["resolved"],
                str(shared_project_app.resolve()),
            )
            self.assertEqual(
                dev_payload["projects_app_probe"]["resolved"],
                str(shared_project_app.resolve()),
            )
            pm_relative_probe = pm_payload["relative_probe"]
            dev_relative_probe = dev_payload["relative_probe"]
            self.assertIsNotNone(pm_relative_probe)
            self.assertIsNotNone(dev_relative_probe)
            assert pm_relative_probe is not None
            assert dev_relative_probe is not None
            self.assertEqual(
                pm_relative_probe["write"]["resolved"],
                str((shared_project_app / "shared-product-sentinel.txt").resolve()),
            )
            self.assertTrue(dev_relative_probe["read"]["exists"])
            self.assertEqual(dev_relative_probe["read"]["content"], "shared-pm-sentinel")
            self.assertTrue((shared_project_app / "shared-product-sentinel.txt").exists())

    def test_start_with_optional_browser_bootstrap_failure_continues_active_instance(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertIn("Chrome binary not found", completed.stderr)
            self.assertIn("continuing without cockpit endpoint", completed.stderr.lower())
            statuses = [
                json.loads(path.read_text(encoding="utf-8")).get("status")
                for path in (source_home_path / ".codex-buddyswitch" / "instances").glob("*/instance.json")
            ]
            self.assertIn("active", statuses)
            self.assertTrue((temp_root_path / "capture.json").exists(), "app-server should still launch for non-required browser buddies")

    def test_start_with_browser_available_buddy_endpoint_only_continues_without_ready_claim(self) -> None:
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

            state_file = temp_root_path / "cdp-state.json"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[],
                allow_put_new_about_blank=False,
                allow_get_new_about_blank=False,
            )

            capture_path = temp_root_path / "capture.json"
            calls_path = temp_root_path / "calls.jsonl"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(capture_path.exists(), "optional-browser buddy should still launch Codex")
            self.assertIn("continuing without cockpit endpoint", completed.stderr.lower())
            self.assertNotIn("Browser cockpit ready:", completed.stdout + completed.stderr)
            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertFalse(
                any(entry.get("argv", [])[:2] == ["mcp", "add"] for entry in call_entries),
                "endpoint-only optional-browser startup must not treat MCP setup as ready",
            )
            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            self.assertNotIn("[mcp_servers.chrome-devtools-cockpit]", payload["config_toml"])

    def test_start_with_required_browser_bootstrap_failure_stops_runtime_broker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            shared_root = source_home_path / ".codex-buddyswitch"
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
                [str(LAUNCHER), "instance", "start", "--buddy", "market"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Chrome binary not found", completed.stderr)
            instance_json_paths = sorted((shared_root / "instances").glob("*/instance.json"))
            self.assertEqual(len(instance_json_paths), 1)
            instance_root = instance_json_paths[0].parent
            self.addCleanup(self._cleanup_runtime_broker, instance_root)
            stored = json.loads(instance_json_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(stored["status"], "inactive")
            self.assertFalse((instance_root / "runtime" / "runtime-broker.pid").exists())
            self.assertFalse((instance_root / "runtime" / "runtime-broker.sock").exists())
            self.assertFalse((instance_root / "runtime" / "runtime-broker.socket").exists())
            self.assertFalse((temp_root_path / "capture.json").exists(), "Codex should not launch after required browser failure")

    def test_start_with_required_buddy_ready_page_launches_codex(self) -> None:
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

            state_file = temp_root_path / "cdp-state.json"
            calls_path = temp_root_path / "calls.jsonl"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
            )

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "market"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(capture_path.exists(), "Codex should launch when a usable page already exists")
            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["active_buddy"], "market")
            instance_payload = payload["instance_json_payload"]
            self.assertIsInstance(instance_payload, dict)
            assert isinstance(instance_payload, dict)
            browser_port = instance_payload.get("browser_port")
            self.assertIsInstance(browser_port, int)
            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            cockpit_add = next(entry for entry in call_entries if entry["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"])
            self.assertIn(f"--browser-url=http://127.0.0.1:{browser_port}", cockpit_add["argv"])
            self.assertIn(f"--browser-url=http://127.0.0.1:{browser_port}", payload["config_toml"])

    def test_start_with_required_buddy_blocks_codex_when_cockpit_mcp_setup_fails(self) -> None:
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

            state_file = temp_root_path / "cdp-state.json"
            calls_path = temp_root_path / "calls.jsonl"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[{"id": "target-about-blank", "type": "page", "url": "about:blank"}],
            )

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_FAIL_MCP_ADD_NAME"] = "chrome-devtools-cockpit"

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "market"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("simulated mcp add failure: chrome-devtools-cockpit", completed.stderr)
            self.assertFalse(capture_path.exists(), "Codex must not launch when required cockpit MCP setup fails")
            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(any(entry["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"] for entry in call_entries))

    def test_start_with_required_buddy_repairs_intro_only_browser_before_codex_launch(self) -> None:
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

            state_file = temp_root_path / "cdp-state.json"
            timeline_path = temp_root_path / "timeline.jsonl"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[{"id": "intro", "type": "page", "url": "chrome://intro/"}],
                allow_put_new_about_blank=True,
                allow_get_new_about_blank=False,
            )

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CDP_CALLS_FILE"] = str(timeline_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(timeline_path)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "market"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(capture_path.exists(), "Codex should launch after intro-only endpoint repair")
            timeline = [
                json.loads(line)
                for line in timeline_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            put_index = next(
                index
                for index, entry in enumerate(timeline)
                if entry.get("method") == "PUT"
                and entry.get("path") == "/json/new"
                and entry.get("query") == "about:blank"
            )
            first_codex_call_index = next(index for index, entry in enumerate(timeline) if isinstance(entry.get("argv"), list))
            self.assertLess(put_index, first_codex_call_index)
            self.assertFalse(
                any(
                    entry.get("method") == "GET"
                    and entry.get("path") == "/json/new"
                    and entry.get("query") == "about:blank"
                    for entry in timeline
                )
            )

    def test_start_with_required_buddy_rejects_endpoint_only_browser_before_codex(self) -> None:
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

            state_file = temp_root_path / "cdp-state.json"
            calls_file = temp_root_path / "cdp-calls.jsonl"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[],
                allow_put_new_about_blank=False,
                allow_get_new_about_blank=False,
            )

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CDP_CALLS_FILE"] = str(calls_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "market"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(capture_path.exists(), "Codex must not launch until a usable browser page exists")
            calls = [
                json.loads(line)
                for line in calls_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(
                any(call["method"] == "PUT" and call["path"] == "/json/new" and call["query"] == "about:blank" for call in calls)
            )

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
                [str(LAUNCHER), "instance", "start", "--buddy", "unknown"],
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

    def test_instance_buddies_json_is_structured_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "buddies", "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(completed.stdout)
            buddy_ids = {row["id"] for row in payload["buddies"]}
            self.assertIn("pm", buddy_ids)
            self.assertIn("dev", buddy_ids)
            self.assertIn("market", buddy_ids)
            for row in payload["buddies"]:
                self.assertIsInstance(row["id"], str)
                self.assertIsInstance(row["label"], str)
                self.assertIsInstance(row["scope"], str)
            self.assertFalse(shared_root.exists(), "instance buddies --json must not create runtime state")

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

    def test_instance_list_json_empty_returns_empty_array(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "list", "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {"instances": []})
            self.assertNotIn("No BuddySwitch instances found.", completed.stdout)

    def test_instance_list_prints_stored_instances_and_filters_by_buddy(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            for instance_id, buddy in (
                ("inst-pm-a", "pm"),
                ("inst-dev-b", "dev"),
            ):
                instance_root = shared_root / "instances" / instance_id
                instance_root.mkdir(parents=True, exist_ok=True)
                (instance_root / "instance.json").write_text(
                    json.dumps(
                        {
                            "instance_id": instance_id,
                            "buddy": buddy,
                            "status": "inactive",
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
            self.assertNotIn("inst-dev-b", completed.stdout)

    def test_instance_list_json_filters_by_buddy(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            for instance_id, buddy in (
                ("inst-pm-a", "pm"),
                ("inst-dev-b", "dev"),
            ):
                instance_root = shared_root / "instances" / instance_id
                instance_root.mkdir(parents=True, exist_ok=True)
                (instance_root / "instance.json").write_text(
                    json.dumps(
                        {
                            "instance_id": instance_id,
                            "buddy": buddy,
                            "status": "inactive",
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
                [str(LAUNCHER), "instance", "list", "--json", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(len(payload["instances"]), 1)
            row = payload["instances"][0]
            self.assertEqual(row["instance_id"], "inst-pm-a")
            self.assertEqual(row["buddy"], "pm")
            self.assertEqual(row["status"], "inactive")
            self.assertEqual(row["app_server_health"], "unhealthy")
            self.assertIsNone(row["thread_id"])
            self.assertIsNone(row["browser_port"])

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

    def test_instance_delete_json_removes_only_target_instance_without_shared_state(self) -> None:
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
                [str(LAUNCHER), "instance", "delete", "inst-pm-delete", "--yes", "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
            self.assertEqual(
                json.loads(delete_result.stdout),
                {"instance_id": "inst-pm-delete", "deleted": True},
            )
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

    def test_instance_delete_keeps_shared_project_workspace(self) -> None:
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
            ready_file = temp_root_path / "browser-ready.flag"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_PRODUCT_WRITE"] = "persist-after-delete"

            start_result = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(start_result.returncode, 0, msg=start_result.stderr)
            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            project_workspace_dir = shared_root / "project" / "workspace"
            sentinel_path = project_workspace_dir / "projects" / "app" / "shared-product-sentinel.txt"
            instance_root = shared_root / "instances" / payload["instance_id"]

            self.assertTrue(project_workspace_dir.exists())
            self.assertTrue(sentinel_path.exists())

            worktree_before = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            self.assertIn(str(project_workspace_dir), worktree_before)

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", payload["instance_id"]],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)
            ready_file.unlink(missing_ok=True)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", payload["instance_id"], "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
            self.assertFalse(instance_root.exists())
            self.assertTrue(project_workspace_dir.exists())
            self.assertTrue(sentinel_path.exists())

            worktree_after = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            self.assertIn(str(project_workspace_dir), worktree_after)

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

    def test_instance_delete_blocks_active_app_server(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            Path(str(ctx["env"]["BUDDYSWITCH_TEST_BROWSER_READY_FILE"])).unlink(missing_ok=True)
            (Path(str(ctx["instance_root"])) / "browser" / "chrome.pid").unlink(missing_ok=True)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", ctx["instance_id"], "--yes"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn(f"Instance delete blocked: {ctx['instance_id']} is active.", delete_result.stderr)
            self.assertTrue(Path(str(ctx["instance_root"])).exists())

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

    def test_instance_delete_ignores_stale_legacy_pid_file_without_active_service(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "inst-pm-stale-legacy-delete")
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / ("launcher" + "-" + "current" + ".pid")).write_text(f"{os.getpid()}\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "inst-pm-stale-legacy-delete", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
            self.assertIn("Instance deleted: inst-pm-stale-legacy-delete", delete_result.stdout)
            self.assertFalse(target_root.exists())

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
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_ACTIVE_BUDDY"] = "leaked-buddy"
            env["BUDDYSWITCH_INSTANCE_ID"] = "leaked-instance-id"
            env["BUDDYSWITCH_INSTANCE_JSON"] = str(temp_root_path / "leaked-instance.json")

            completed = subprocess.run(
                [str(LAUNCHER), "start", "debug", "prompt-input", "Draft the onboarding PRD"],
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

    def test_instance_start_help_has_no_side_effects(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "--help"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertIn("buddyswitch-codex instance start --buddy <buddy>", completed.stdout)
            self.assertFalse(capture_path.exists(), "help path must not launch Codex")
            self.assertFalse(calls_path.exists(), "help path must not call Codex binary")
            self.assertFalse(ready_file.exists(), "help path must not start browser")
            self.assertFalse(shared_root.exists(), "help path must not create shared instance state")

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

    def test_locked_start_bootstrap_requires_buddy_env_before_workspace_setup(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            runtime_lock = ROOT / "tools" / "launcher" / "runtime_lock.py"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env.pop("BUDDYSWITCH_START_BUDDY", None)
            env.pop("BUDDYSWITCH_START_INSTANCE_ID", None)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(runtime_lock),
                    "--shared-root",
                    str(shared_root),
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

            self.assertEqual(completed.returncode, 2)
            self.assertIn("BUDDYSWITCH_START_BUDDY is required", completed.stderr)
            self.assertFalse((shared_root / "workspace").exists(), "missing buddy env must fail before workspace prep")

    def test_locked_start_bootstrap_requires_instance_id_env(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            runtime_lock = ROOT / "tools" / "launcher" / "runtime_lock.py"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_START_BUDDY"] = "pm"
            env.pop("BUDDYSWITCH_START_INSTANCE_ID", None)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(runtime_lock),
                    "--shared-root",
                    str(shared_root),
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

            self.assertEqual(completed.returncode, 2)
            self.assertIn("BUDDYSWITCH_START_INSTANCE_ID is required", completed.stderr)
            self.assertFalse((shared_root / "workspace").exists(), "missing instance id must fail before workspace prep")

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
                msg=f"unknown top-level command should fail closed\nstdout:\n{debug_result.stdout}\nstderr:\n{debug_result.stderr}",
            )
            self.assertIn("Unknown top-level command: debug", debug_result.stderr)
            self.assertFalse(capture_path.exists(), "unknown top-level command must not invoke codex")

    def test_locked_workspace_sync_command_is_not_supported_even_under_runtime_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            runtime_lock = ROOT / "tools" / "launcher" / "runtime_lock.py"
            workspace_dir = shared_root / "workspace"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(runtime_lock),
                    "--shared-root",
                    str(shared_root),
                    "--",
                    str(LAUNCHER),
                    "__locked-workspace-sync",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Unknown top-level command: __locked-workspace-sync", completed.stderr)
            self.assertFalse(workspace_dir.exists(), "retired locked sync command must not create workspace")

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

    def test_data_cleanup_is_blocked_when_active_app_server_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            Path(str(ctx["env"]["BUDDYSWITCH_TEST_BROWSER_READY_FILE"])).unlink(missing_ok=True)
            (Path(str(ctx["instance_root"])) / "browser" / "chrome.pid").unlink(missing_ok=True)

            cleanup_result = subprocess.run(
                [str(LAUNCHER), "data", "cleanup", "--all-data", "--yes", "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(cleanup_result.returncode, 3)
            self.assertIn("active buddyswitch-codex instance", cleanup_result.stderr)
            self.assertTrue(Path(str(ctx["shared_root"])).exists())

    def test_reset_is_blocked_when_active_app_server_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            Path(str(ctx["env"]["BUDDYSWITCH_TEST_BROWSER_READY_FILE"])).unlink(missing_ok=True)
            (Path(str(ctx["instance_root"])) / "browser" / "chrome.pid").unlink(missing_ok=True)

            blocked_reset = subprocess.run(
                [str(LAUNCHER), "env", "reset", "--yes"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(blocked_reset.returncode, 3)
            self.assertIn("active buddyswitch-codex instance", blocked_reset.stderr)
            self.assertTrue(Path(str(ctx["shared_root"])).exists(), "active app-server should block reset")

    def test_reset_ignores_stale_legacy_pid_file_without_active_service(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / ("launcher" + "-" + "current" + ".pid")).write_text(f"{os.getpid()}\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            reset_result = subprocess.run(
                [str(LAUNCHER), "env", "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(reset_result.returncode, 0, msg=reset_result.stderr)
            self.assertFalse(shared_root.exists(), "stale legacy pid file should not block reset")

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

    def test_runtime_lock_helper_writes_locks_under_shared_root_run_locks(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            source_home_path = Path(source_home)
            temp_root_path = Path(temp_root)
            shared_root = source_home_path / ".codex-buddyswitch"
            lock_capture_path = temp_root_path / "lock-capture.json"

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_TEST_LOCK_CAPTURE"] = str(lock_capture_path)

            capture_script = (
                "import json, os\n"
                "from pathlib import Path\n"
                "lock_dir = Path(os.environ['BUDDYSWITCH_SHARED_ROOT']) / 'run' / 'locks'\n"
                "payload = {\n"
                "  'lock_dir': str(lock_dir),\n"
                "  'runtime_lock_exists': (lock_dir / 'runtime.lock').exists(),\n"
                "  'owner_lock_exists': (lock_dir / 'runtime.owner.lock').exists(),\n"
                "}\n"
                "Path(os.environ['BUDDYSWITCH_TEST_LOCK_CAPTURE']).write_text(\n"
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
            self.assertTrue(lock_capture_path.exists(), "locked child must capture lock metadata")

            lock_path = self._legacy_runtime_lock_path(shared_root)
            new_lock_path = self._runtime_lock_path(shared_root)
            owner_lock_path = self._runtime_owner_lock_path(shared_root)
            self.assertFalse(lock_path.exists())
            self.assertTrue(new_lock_path.exists())
            self.assertTrue(owner_lock_path.exists())

            lock_payload = json.loads(lock_capture_path.read_text(encoding="utf-8"))
            self.assertEqual(Path(lock_payload["lock_dir"]), shared_root / "run" / "locks")
            self.assertTrue(lock_payload["runtime_lock_exists"])
            self.assertTrue(lock_payload["owner_lock_exists"])

    def test_runtime_lock_assert_held_accepts_live_locked_descendant(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
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

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

    def test_runtime_lock_assert_held_rejects_without_owner_lock_when_runtime_lock_is_busy(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            lock_path = self._runtime_lock_path(shared_root)

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

            holder = self._spawn_lock_holder(lock_path)
            try:
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
            finally:
                self._stop_lock_holder(holder)

            self.assertEqual(completed.returncode, 2)
            self.assertIn("runtime lock required", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_runtime_lock_assert_held_rejects_non_descendant_when_runtime_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as source_home, tempfile.TemporaryDirectory() as temp_root:
            source_home_path = Path(source_home)
            temp_root_path = Path(temp_root)
            shared_root = source_home_path / ".codex-buddyswitch"
            ready_path = temp_root_path / "holder-ready"

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            holder = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    "--",
                    sys.executable,
                    "-c",
                    "import sys, time; from pathlib import Path; Path(sys.argv[1]).write_text('ready', encoding='utf-8'); time.sleep(30)",
                    str(ready_path),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                deadline = time.time() + 5
                while not ready_path.exists() and time.time() < deadline:
                    time.sleep(0.05)
                if not ready_path.exists():
                    stderr = holder.stderr.read() if holder.stderr is not None else ""
                    self.fail(f"runtime lock holder did not become ready: {stderr}")

                forged_runner = (
                    "import os, subprocess, sys\n"
                    "env = os.environ.copy()\n"
                    "completed = subprocess.run([sys.executable, sys.argv[1], '--assert-held'], env=env, text=True, capture_output=True)\n"
                    "print(completed.returncode)\n"
                    "print(completed.stderr, end='')\n"
                )
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        forged_runner,
                        str(ROOT / "tools" / "launcher" / "runtime_lock.py"),
                    ],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                if holder.poll() is None:
                    holder.terminate()
                    holder.wait(timeout=5)

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            output_lines = completed.stdout.splitlines()
            self.assertTrue(output_lines, msg=completed.stdout)
            self.assertEqual(output_lines[0], "2", msg=completed.stdout)
            self.assertIn("runtime lock required", completed.stdout)
            self.assertNotIn("Traceback", completed.stdout)

    def test_runtime_lock_assert_held_reports_controlled_failure_without_lock_dir(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

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
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            shared_root.mkdir(parents=True)
            (shared_root / "run").write_text("not a directory\n", encoding="utf-8")

            env = os.environ.copy()
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

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
            (run_dir / ("launcher" + "-" + "current" + ".pid")).write_text(f"{os.getpid()}\n", encoding="utf-8")

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

    def test_start_with_buddy_does_not_migrate_legacy_durable_state_to_shared_state(self) -> None:
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
            for path, payload in (
                (legacy_task, {"id": "task-demo", "buddy": "pm"}),
                (legacy_run, {"run_id": "run-demo", "switch": {"buddy": "pm"}}),
                (legacy_reserved, {"run_id": "run-old", "status": "reserved"}),
                (legacy_raw, {"raw": True}),
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
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
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
            self.assertFalse(
                (shared_root / "state" / "buddyswitch" / "objects" / "tasks" / "task-demo.json").exists(),
                "legacy workspace task should not be auto-migrated into shared state",
            )
            self.assertFalse(
                (shared_root / "state" / "buddyswitch" / "content" / "runs" / "run-demo.json").exists(),
                "legacy workspace run should not be auto-migrated into shared state",
            )
            self.assertTrue(legacy_task.exists(), "legacy workspace task should remain untouched")
            self.assertTrue(legacy_run.exists(), "legacy workspace run should remain untouched")
            self.assertTrue(legacy_reserved.exists(), "legacy reservation should remain untouched")
            self.assertTrue(legacy_raw.exists(), "legacy raw runtime scratch must remain untouched")

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
            self.assertIn("Browser cockpit ready: http://127.0.0.1:9333", status_default.stdout)
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
            self.assertIn("Browser cockpit ready: http://127.0.0.1:9444", status_explicit.stdout)
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

    def test_locked_workspace_sync_entrypoint_fails_closed_as_unknown_command(self) -> None:
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
            self.assertIn("Unknown top-level command: __locked-workspace-sync", direct_sync.stderr)
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

    def test_workspace_sync_runtime_surface_advances_execution_worktree_to_repo_head(self) -> None:
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
        repo_head = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
        self.assertNotEqual(stale_head, repo_head, "precondition failed: stale head must differ from repo head")

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
                shell = f"""
set -euo pipefail
source "tools/launcher/workspace.sh"
export BUDDYSWITCH_SHARED_ROOT="{shared_root}"
export BUDDYSWITCH_WORKSPACE_DIR="{workspace_dir}"
buddyswitch_workspace_init_defaults
buddyswitch_workspace_configure_execution_sparse_checkout "{workspace_dir}" existing
echo "before=$(git -C "{workspace_dir}" rev-parse HEAD)"
buddyswitch_workspace_sync_runtime_surface
echo "after=$(git -C "{workspace_dir}" rev-parse HEAD)"
"""
                completed = subprocess.run(
                    ["/bin/bash", "-lc", shell],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=completed.stderr)
                rows = {}
                for line in completed.stdout.splitlines():
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    rows[key.strip()] = value.strip()
                self.assertEqual(rows.get("before"), stale_head)
                self.assertEqual(rows.get("after"), repo_head)
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

    def test_workspace_install_runtime_agents_requires_explicit_template(self) -> None:
        command = r'''
set -euo pipefail
source "tools/launcher/workspace.sh"
tmp_root="$(mktemp -d)"
trap 'rm -rf "${tmp_root}"' EXIT
export BUDDYSWITCH_SHARED_ROOT="${tmp_root}/shared"
export BUDDYSWITCH_WORKSPACE_DIR="${tmp_root}/workspace"
mkdir -p "${BUDDYSWITCH_WORKSPACE_DIR}"
unset BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE || true
set +e
buddyswitch_workspace_install_runtime_agents 1>/dev/null 2>"${tmp_root}/stderr.txt"
exit_code=$?
set -e
if [[ "${exit_code}" -eq 0 ]]; then
  echo "expected failure when template var is unset" >&2
  exit 97
fi
cat "${tmp_root}/stderr.txt"
'''
        completed = subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE is required", completed.stdout + completed.stderr)

    def test_workspace_install_runtime_agents_copies_existing_template_without_content_validation(self) -> None:
        command = r'''
set -euo pipefail
source "tools/launcher/workspace.sh"
tmp_root="$(mktemp -d)"
trap 'rm -rf "${tmp_root}"' EXIT
export BUDDYSWITCH_SHARED_ROOT="${tmp_root}/shared"
export BUDDYSWITCH_WORKSPACE_DIR="${tmp_root}/workspace"
export BUDDYSWITCH_ACTIVE_BUDDY="pm"
export BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE="${tmp_root}/AGENTS.md"
mkdir -p "${BUDDYSWITCH_WORKSPACE_DIR}"
printf '# Custom Runtime AGENTS\n\nFramework-owned prose can iterate freely.\n' >"${BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE}"
buddyswitch_workspace_install_runtime_agents
cmp "${BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE}" "${BUDDYSWITCH_WORKSPACE_DIR}/AGENTS.md"
'''
        completed = subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)

    def test_buddy_agents_template_requirement_checks_presence_only(self) -> None:
        command = r'''
set -euo pipefail
source "tools/launcher/env.sh"
tmp_root="$(mktemp -d)"
trap 'rm -rf "${tmp_root}"' EXIT
export BUDDYSWITCH_REPO_ROOT="${tmp_root}/repo"
mkdir -p "${BUDDYSWITCH_REPO_ROOT}/tools/launcher/assets/buddies/pm"
printf '# Custom Runtime AGENTS\n\nNo required wording.\n' >"${BUDDYSWITCH_REPO_ROOT}/tools/launcher/assets/buddies/pm/AGENTS.md"
buddyswitch_require_buddy_agents_template pm
printf '%s\n' "${BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE}"
'''
        completed = subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertTrue(completed.stdout.strip().endswith("/tools/launcher/assets/buddies/pm/AGENTS.md"))

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
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
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

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", payload["instance_id"]],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)
            ready_file.unlink(missing_ok=True)

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

    def test_reset_removes_shared_project_worktree_registration(self) -> None:
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
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            start_result = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(start_result.returncode, 0, msg=start_result.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / payload["instance_id"]
            project_workspace_dir = shared_root / "project" / "workspace"
            self.assertTrue(project_workspace_dir.exists())

            worktrees_before = subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout
            self.assertIn(str(project_workspace_dir), worktrees_before)

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", payload["instance_id"]],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)
            ready_file.unlink(missing_ok=True)

            try:
                reset_result = subprocess.run(
                    [str(LAUNCHER), "env", "reset", "--yes"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(reset_result.returncode, 0, msg=reset_result.stderr)
                worktrees_after = subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout
                self.assertNotIn(str(project_workspace_dir), worktrees_after)
                prune_dry_run = subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "prune", "--dry-run", "-v"],
                    text=True,
                    capture_output=True,
                    check=True,
                )
                self.assertNotIn(
                    str(project_workspace_dir),
                    prune_dry_run.stdout + prune_dry_run.stderr,
                )
            finally:
                subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(project_workspace_dir)],
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

    def test_start_rejects_project_workspace_dir_existing_worktree_outside_shared_root(self) -> None:
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

            external_project_workspace = temp_root_path / "external-project-workspace"
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(external_project_workspace), "HEAD"],
                text=True,
                capture_output=True,
                check=True,
            )
            sentinel = external_project_workspace / "outside-sentinel.txt"
            sentinel.write_text("do-not-delete\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")
            env["BUDDYSWITCH_PROJECT_WORKSPACE_DIR"] = str(external_project_workspace)

            try:
                completed = subprocess.run(
                    [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("project workspace dir must be under BUDDYSWITCH_SHARED_ROOT", completed.stderr)
                self.assertTrue(sentinel.exists(), "external project workspace sentinel must be preserved")
            finally:
                subprocess.run(
                    ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(external_project_workspace)],
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

    def test_start_preserves_non_empty_invalid_project_workspace(self) -> None:
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
            project_workspace = shared_root / "project" / "workspace"
            sentinel = project_workspace / "projects" / "app" / "product-source-sentinel.txt"
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("do-not-delete\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(temp_root_path / "capture.json")

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("project workspace exists and is not a valid git worktree", completed.stderr)
            self.assertTrue(sentinel.exists(), "invalid project workspace sentinel must be preserved")
            self.assertFalse((project_workspace / ".git").exists(), "invalid project workspace must not be replaced")

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
                [str(LAUNCHER), "start", "debug", "prompt-input", "Draft the onboarding PRD"],
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
                [str(LAUNCHER), "start", "debug", "prompt-input", "Draft the onboarding PRD"],
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
                [str(LAUNCHER), "start", "debug", "prompt-input", "Draft the onboarding PRD"],
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
                        [str(LAUNCHER), "start", "debug", "prompt-input", "Draft the onboarding PRD"],
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
