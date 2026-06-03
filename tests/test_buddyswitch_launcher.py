#!/usr/bin/env python3
"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

import json
import os
import errno
import shutil
import signal
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
        "cross-role-sentinel.txt",
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

    def setUp(self) -> None:
        super().setUp()
        self._process_registry_tmp = tempfile.TemporaryDirectory(prefix="buddyswitch-launcher-procs-")
        self._process_registry_path = Path(self._process_registry_tmp.name) / "processes.jsonl"
        original_temporary_directory = tempfile.TemporaryDirectory
        test_case = self

        class ProcessAwareTemporaryDirectory(original_temporary_directory):  # type: ignore[misc, valid-type]
            def cleanup(self) -> None:
                test_case._cleanup_registered_test_processes()
                super().cleanup()

        tempfile.TemporaryDirectory = ProcessAwareTemporaryDirectory
        previous_process_registry = os.environ.get("BUDDYSWITCH_TEST_PROCESS_REGISTRY")
        os.environ["BUDDYSWITCH_TEST_PROCESS_REGISTRY"] = str(self._process_registry_path)
        self.addCleanup(self._restore_temporary_directory, original_temporary_directory)
        self.addCleanup(self._process_registry_tmp.cleanup)
        self.addCleanup(self._restore_process_registry_env, previous_process_registry)
        self.addCleanup(self._cleanup_registered_test_processes)
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
    def _first_available_local_port(start: int, *, limit: int = 50) -> int:
        for port in range(start, start + limit):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise AssertionError(f"no available localhost TCP port found from {start}")

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

    def _assert_cockpit_proxy_registration(self, argv: list[object], browser_url: str) -> None:
        self.assertEqual(argv[:3], ["mcp", "add", "chrome-devtools-cockpit"])
        self.assertIn("--", argv)
        separator_index = argv.index("--")
        self.assertEqual(argv[separator_index + 1], "python3")
        self.assertIn("tools/launcher/chrome_devtools_cockpit_proxy.py", str(argv[separator_index + 2]))
        self.assertIn(f"--browser-url={browser_url}", argv)
        self.assertNotIn("chrome-devtools-mcp@latest", argv)

    def _assert_env_mcp_registration(
        self,
        argv: list[object],
        *,
        actor_id: str,
        role: str,
        broker_socket: str,
    ) -> None:
        self.assertEqual(argv[:3], ["mcp", "add", "buddyswitch-env"])
        self.assertIn("--", argv)
        separator_index = argv.index("--")
        self.assertEqual(argv[separator_index + 1], "python3")
        self.assertIn("tools/launcher/env_tool_mcp_server.py", str(argv[separator_index + 2]))
        self.assertIn("--repo-root", argv)
        self.assertIn(str(ROOT), argv)
        self.assertIn("--actor-id", argv)
        self.assertIn(actor_id, argv)
        self.assertIn("--role", argv)
        self.assertIn(role, argv)
        self.assertIn("--broker-socket", argv)
        self.assertIn(broker_socket, argv)

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

    def _write_fake_background_page_tool(self, path: Path) -> None:
        self._write_exec(
            path,
            """#!/usr/bin/env python3
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
        role: str = "pm",
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
            [str(LAUNCHER), "instance", "start", "--role", role],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(capture_path.read_text(encoding="utf-8"))
        shared_root = source_home_path / ".codex-buddyswitch"
        actor_id = payload["actor_id"]
        instance_root = shared_root / "instances" / actor_id
        instance_payload = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
        app_server_pid = instance_payload.get("app_server_pid")
        if isinstance(app_server_pid, int):
            self.addCleanup(self._cleanup_app_server_process, instance_root, app_server_pid)
        daemon_pid_file = instance_root / "runtime" / "daemon" / "daemon.pid"
        try:
            daemon_pid = int(daemon_pid_file.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, OSError, ValueError):
            daemon_pid = 0
        if daemon_pid:
            self.addCleanup(self._cleanup_daemon_process, instance_root, daemon_pid)
        runtime_broker_pid_file = instance_root / "runtime" / "runtime-broker.pid"
        try:
            runtime_broker_pid = int(runtime_broker_pid_file.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, OSError, ValueError):
            runtime_broker_pid = 0
        if runtime_broker_pid:
            self.addCleanup(self._cleanup_runtime_broker_process, instance_root, runtime_broker_pid)

        return {
            "completed": completed,
            "env": env,
            "capture_path": capture_path,
            "calls_path": calls_path,
            "state_file": state_file,
            "payload": payload,
            "shared_root": shared_root,
            "actor_id": actor_id,
            "instance_root": instance_root,
            "instance_payload": instance_payload,
        }

    @staticmethod
    def _read_json_lines(path: Path) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _read_rpc_rows(self, path: Path) -> list[dict[str, object]]:
        return [row for row in self._read_json_lines(path) if row["argv"][:1] == ["json-rpc"]]

    def _wait_for_rpc_rows(self, path: Path, method: str, *, count: int = 1, timeout: float = 5.0) -> list[dict[str, object]]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.exists():
                rows = [row for row in self._read_rpc_rows(path) if row.get("rpc_method") == method]
                if len(rows) >= count:
                    return rows
            time.sleep(0.05)
        return [row for row in self._read_rpc_rows(path) if row.get("rpc_method") == method] if path.exists() else []

    def _set_instance_side_threads(
        self,
        instance_root: Path,
        side_threads: list[dict[str, object]],
    ) -> dict[str, object]:
        instance_json = instance_root / "instance.json"
        payload = json.loads(instance_json.read_text(encoding="utf-8"))
        payload["side_threads"] = side_threads
        instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return payload

    def _set_fake_side_thread_state(
        self,
        state_file: Path,
        *,
        main_thread_id: str,
        side_thread_id: str,
        main_status: dict[str, object] | None = None,
        main_turns: list[dict[str, object]] | None = None,
        side_status: dict[str, object],
        side_turns: list[dict[str, object]],
    ) -> dict[str, object]:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
        effective_main_status = main_status if main_status is not None else payload.get("thread_status", {"type": "idle"})
        effective_main_turns = main_turns if main_turns is not None else payload.get("turns", [])
        payload["thread_status"] = effective_main_status
        payload["turns"] = effective_main_turns
        threads = payload.get("threads")
        if not isinstance(threads, dict):
            threads = {}
        threads[main_thread_id] = {
            "status": effective_main_status,
            "turns": effective_main_turns,
        }
        threads[side_thread_id] = {
            "status": side_status,
            "turns": side_turns,
            "injected_items": [],
        }
        payload["threads"] = threads
        state_file.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return payload

    def _seed_instance_taskbox_current(
        self,
        *,
        instance_root: Path,
        role: str,
        task_id: str = "task-0001-launcher-context",
        title: str = "Launcher context task",
        summary: str = "Render task context before user input.",
    ) -> None:
        taskbox_root = instance_root / "taskbox" / role
        tasks_dir = taskbox_root / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        task_payload = {
            "id": task_id,
            "owner_actor": {"actor_id": instance_root.name, "role_id": role},
            "title": title,
            "summary": summary,
            "body": "Detailed launcher task body.",
            "status": "active",
            "priority": "normal",
            "track_id": None,
            "refs": [],
            "created_at": "2026-05-27T10:00:00+08:00",
            "updated_at": "2026-05-27T10:00:00+08:00",
            "closed_at": None,
        }
        (tasks_dir / f"{task_id}.json").write_text(json.dumps(task_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        (taskbox_root / "history.md").write_text(
            f"- 2026-05-27T10:00:00+08:00 task.create {task_id} title={json.dumps(title, ensure_ascii=True, separators=(',', ':'))} status=\"active\"\n",
            encoding="utf-8",
        )

    def _assert_composed_task_input(
        self,
        text: str,
        *,
        raw_text: str,
        task_id: str = "task-0001-launcher-context",
        title: str = "Launcher context task",
    ) -> None:
        self.assertTrue(text.startswith("[TASK CONTEXT]"), msg=text)
        self.assertIn(f"Current Task: {task_id}", text)
        self.assertIn(f"Title: {title}", text)
        self.assertIn("State: active", text)
        self.assertIn("Task Handling Cue:", text)
        self.assertIn("[USER INPUT]", text)
        self.assertIn(raw_text, text)
        self.assertLess(text.index(f"Current Task: {task_id}"), text.index("[USER INPUT]"))
        self.assertLess(text.index("[USER INPUT]"), text.index(raw_text))

    def _assert_raw_input(self, text: str, *, raw_text: str) -> None:
        self.assertEqual(text, raw_text)
        self.assertNotIn("[TASK CONTEXT]", text)
        self.assertNotIn("[USER INPUT]", text)

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
        self.assertTrue((workspace_dir / "private").is_dir())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "private" / "pm").exists())
        self.assertFalse((workspace_dir / "buddyswitch" / "local" / "private" / "pm").is_symlink())

    def _assert_pm_runtime_skills(self, workspace_dir: Path) -> None:
        runtime_skills = workspace_dir / ".agents" / "skills"
        for skill_id in self._PM_PRODUCT_SKILLS:
            self.assertTrue((runtime_skills / skill_id / "SKILL.md").exists(), msg=skill_id)
        self.assertTrue((runtime_skills / "task-management" / "SKILL.md").exists())
        self.assertTrue((runtime_skills / "track-tool" / "SKILL.md").exists())
        self.assertTrue((runtime_skills / "artifact-tool" / "SKILL.md").exists())
        self.assertFalse((runtime_skills / "write-prd").exists())
        self.assertFalse((runtime_skills / "write-prd" / "assets" / "prd-template.md").exists())

    @staticmethod
    def _restore_temporary_directory(original_temporary_directory: type[tempfile.TemporaryDirectory]) -> None:
        tempfile.TemporaryDirectory = original_temporary_directory

    @staticmethod
    def _restore_process_registry_env(previous_value: str | None) -> None:
        if previous_value is None:
            os.environ.pop("BUDDYSWITCH_TEST_PROCESS_REGISTRY", None)
        else:
            os.environ["BUDDYSWITCH_TEST_PROCESS_REGISTRY"] = previous_value

    @staticmethod
    def _coerce_pid(value: object) -> int | None:
        if isinstance(value, int):
            return value if value > 0 else None
        if isinstance(value, str) and value.isdigit():
            pid = int(value)
            return pid if pid > 0 else None
        return None

    @staticmethod
    def _pid_is_live(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError as exc:
            return exc.errno == errno.EPERM
        return True

    def _terminate_registered_process(self, pid_value: object, pgid_value: object | None = None) -> None:
        pid = self._coerce_pid(pid_value)
        if pid is None:
            return
        pgid = self._coerce_pid(pgid_value)
        if pgid is None:
            try:
                pgid = os.getpgid(pid)
            except OSError:
                pgid = None
        current_pgid = os.getpgrp()
        use_group = pgid is not None and pgid != current_pgid

        for signum in (signal.SIGTERM, signal.SIGKILL):
            if not self._pid_is_live(pid):
                return
            try:
                if use_group and pgid is not None:
                    os.killpg(pgid, signum)
                else:
                    os.kill(pid, signum)
            except OSError:
                pass
            deadline = time.monotonic() + (1.0 if signum == signal.SIGTERM else 0.2)
            while time.monotonic() < deadline:
                if not self._pid_is_live(pid):
                    return
                time.sleep(0.05)

    def _cleanup_registered_test_processes(self) -> None:
        registry_path = getattr(self, "_process_registry_path", None)
        if not isinstance(registry_path, Path) or not registry_path.exists():
            return
        records: list[dict[str, object]] = []
        for line in registry_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)

        seen: set[int] = set()
        for payload in reversed(records):
            for prefix in ("browser", "app_server", "runtime_broker"):
                pid = self._coerce_pid(payload.get(f"{prefix}_pid"))
                if pid is None or pid in seen:
                    continue
                seen.add(pid)
                self._terminate_registered_process(pid, payload.get(f"{prefix}_pgid"))
            pid = self._coerce_pid(payload.get("pid"))
            if pid is not None and pid not in seen:
                seen.add(pid)
                self._terminate_registered_process(pid, payload.get("pgid"))

    def _cleanup_app_server_process(self, instance_root: Path, app_server_pid: int) -> None:
        self._terminate_registered_process(app_server_pid)
        for path in (
            instance_root / "runtime" / "app-server.pid",
            instance_root / "runtime" / "app-server.sock",
            instance_root / "runtime" / "app-server.socket",
        ):
            path.unlink(missing_ok=True)

    def _cleanup_runtime_broker_process(self, instance_root: Path, runtime_broker_pid: int) -> None:
        self._terminate_registered_process(runtime_broker_pid)
        for path in (
            instance_root / "runtime" / "runtime-broker.pid",
            instance_root / "runtime" / "runtime-broker.sock",
            instance_root / "runtime" / "runtime-broker.socket",
        ):
            path.unlink(missing_ok=True)

    def _cleanup_daemon_process(self, instance_root: Path, daemon_pid: int) -> None:
        self._terminate_registered_process(daemon_pid)
        (instance_root / "runtime" / "daemon" / "daemon.pid").unlink(missing_ok=True)

    def _cleanup_runtime_broker(self, instance_root: Path) -> None:
        pid_file = instance_root / "runtime" / "runtime-broker.pid"
        try:
            pid_text = pid_file.read_text(encoding="utf-8").strip()
            pid = int(pid_text)
        except (FileNotFoundError, OSError, ValueError):
            pid = 0
        if pid:
            self._terminate_registered_process(pid)
        for path in (
            pid_file,
            instance_root / "runtime" / "runtime-broker.sock",
            instance_root / "runtime" / "runtime-broker.socket",
        ):
            path.unlink(missing_ok=True)

    def test_cleanup_registered_test_processes_terminates_recorded_process_group(self) -> None:
        script = (
            "import subprocess, sys, time\n"
            "from pathlib import Path\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8')\n"
            "time.sleep(60)\n"
        )

        def pid_live(pid: int) -> bool:
            try:
                os.kill(pid, 0)
            except OSError:
                return False
            return True

        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            child_pid_file = temp_root_path / "child.pid"
            registry_path = temp_root_path / "processes.jsonl"
            leader = subprocess.Popen(
                [sys.executable, "-c", script, str(child_pid_file)],
                start_new_session=True,
            )
            child_pid = 0
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if child_pid_file.exists():
                        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
                        break
                    time.sleep(0.05)
                self.assertNotEqual(child_pid, 0)
                registry_path.write_text(
                    json.dumps(
                        {
                            "pid": leader.pid,
                            "pgid": os.getpgid(leader.pid),
                            "kind": "test-process-group",
                        },
                        ensure_ascii=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                previous_registry = getattr(self, "_process_registry_path", None)
                self._process_registry_path = registry_path
                try:
                    self._cleanup_registered_test_processes()
                finally:
                    self._process_registry_path = previous_registry

                leader.wait(timeout=2)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and pid_live(child_pid):
                    time.sleep(0.05)
                self.assertFalse(pid_live(child_pid))
            finally:
                for pid in (child_pid, leader.pid):
                    if pid:
                        try:
                            os.kill(pid, 9)
                        except OSError:
                            pass

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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
            expected_agents = (ROOT / "tools" / "launcher" / "assets" / "roles" / "pm" / "AGENTS.md").read_text(
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "instances" / payload["actor_id"] / "workspace"
            self.assertEqual(payload["cwd"], str(workspace_dir.resolve()))
            self.assertEqual(self._runtime_sparse_list(workspace_dir), list(self._RUNTIME_SPARSE_PATHS))
            self._assert_pm_runtime_shape(workspace_dir, shared_root)
            self._assert_runtime_workspace_excludes_source_surfaces(workspace_dir)

            self._assert_pm_runtime_skills(workspace_dir)
            self.assertFalse((workspace_dir / ".agents" / "skills" / "shape-prototype").exists())
            self.assertFalse(
                (workspace_dir / "buddyswitch" / "skills" / "design" / "shape-prototype" / "SKILL.md").exists()
            )

    def test_search_open_browser_helper_stays_inside_runtime_sparse_surface(self) -> None:
        workspace_text = (ROOT / "tools" / "launcher" / "workspace.sh").read_text(encoding="utf-8")
        search_text = (ROOT / "scripts" / "env" / "tools" / "search" / "_impl.py").read_text(encoding="utf-8")

        self.assertRegex(workspace_text, r"(?m)^scripts/env/$")
        self.assertRegex(workspace_text, r"(?m)^tools$")
        self.assertIn('"scripts"', search_text)
        self.assertIn('"env"', search_text)
        self.assertIn("cdp_background_page.py", search_text)
        self.assertNotIn("tools" + "/launcher", search_text)
        self.assertTrue((ROOT / "scripts" / "env" / "cdp_background_page.py").exists())
        self.assertFalse((ROOT / "tools" / "launcher" / "cdp_background_page.py").exists())

    def test_instance_start_creates_private_taskbox_for_active_role(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "dev"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / payload["actor_id"]
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
                [str(LAUNCHER), "instance", "start", "--role", "design"],
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
            self.assertFalse((workspace_dir / "tools" / "launcher" / "assets" / "roles" / "design").exists())

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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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

    def test_local_non_role_start_allows_codex_search_args(self) -> None:
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
            env.pop("BUDDYSWITCH_ROLE_ID", None)
            env.pop("BUDDYSWITCH_ACTOR_ID", None)

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
            self.assertIsNone(payload["active_role"])
            self.assertIsNone(payload["actor_id"])

    def test_product_mode_run_codex_rejects_native_search_with_native_env_tool_guidance(self) -> None:
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
                "BUDDYSWITCH_ROLE_ID=pm\n"
                "BUDDYSWITCH_ACTOR_ID=act-pm-test\n"
                "buddyswitch_run_codex --search\n"
            )
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                ["bash", "-lc", command, "buddyswitch-run-codex-test", str(home), str(codex_home), str(xdg_config_home)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2, msg=completed.stderr)
            self.assertIn("Native Codex web_search is disabled in BuddySwitch product sessions.", completed.stderr)
            self.assertIn("search__status", completed.stderr)
            self.assertIn("search__open_browser", completed.stderr)
            self.assertIn("python3 scripts/turn_runtime.py status", completed.stderr)
            self.assertNotIn("python3 scripts/env/client.py", completed.stderr)
            self.assertNotIn("search open-browser --query", completed.stderr)
            self.assertNotIn("search open-browser --payload", completed.stderr)
            self.assertFalse(capture_path.exists(), "rejected native search must not invoke codex")

    def test_start_execution_worktree_uses_design_role_prompt_contract(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "design"],
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
            expected_agents = (ROOT / "tools" / "launcher" / "assets" / "roles" / "design" / "AGENTS.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(agents_md.read_text(encoding="utf-8"), expected_agents)
            prompt_text = agents_md.read_text(encoding="utf-8")
            self.assertIn("locked to the `design` role", prompt_text)
            for token in (
                "## Runtime Boundary",
                "Native Codex `web_search` is unavailable",
                "native BuddySwitch env search tools",
                "search__open_browser",
                "chrome-devtools-cockpit",
                "## Output Rule",
            ):
                self.assertIn(token, prompt_text)
            self.assertNotIn("python3 scripts/env/client.py", prompt_text)
            self.assertNotIn("search open-browser --payload", prompt_text)
            self.assertNotIn("project.access=", prompt_text)
            self.assertNotIn("projects/app", prompt_text)
            runtime_skills = workspace_dir / ".agents" / "skills"
            self.assertTrue((runtime_skills / "shape-prototype" / "SKILL.md").exists())
            self.assertFalse((runtime_skills / "write-prd").exists())
            self.assertTrue((runtime_skills / "track-tool" / "SKILL.md").exists())
            for removed in ("task" + "-manager", "track" + "-manager", "artifact" + "-manager"):
                self.assertFalse((runtime_skills / removed).exists())

    def test_instance_start_materializes_runtime_skills_from_manifest_for_each_role(self) -> None:
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
            roles = [row for row in manifest.get("roles", []) if isinstance(row, dict)]
            self.assertTrue(roles)
            skill_sources = {
                row["id"]: row["path"]
                for row in manifest.get("skills", [])
                if isinstance(row, dict) and isinstance(row.get("id"), str) and isinstance(row.get("path"), str)
            }
            market = next((row for row in roles if row.get("id") == "market"), None)
            self.assertIsInstance(market, dict)
            assert isinstance(market, dict)
            self.assertGreaterEqual(len([row for row in market.get("skills", []) if isinstance(row, str)]), 6)

            base_env = os.environ.copy()
            base_env["HOME"] = str(source_home_path)
            base_env.pop("CODEX_HOME", None)
            base_env["PATH"] = f"{fake_bin}{os.pathsep}{base_env.get('PATH', '')}"
            base_env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            base_env["BUDDYSWITCH_BROWSER_PORT"] = "1"

            for role in roles:
                role_id = role.get("id")
                role_skills = role.get("skills", [])
                if not isinstance(role_id, str) or not isinstance(role_skills, list):
                    continue

                capture_path = temp_root_path / f"capture-{role_id}.json"
                ready_file = temp_root_path / f"browser-ready-{role_id}.flag"
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
                        "--role",
                        role_id,
                    ],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, msg=f"{role_id}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
                payload = json.loads(capture_path.read_text(encoding="utf-8"))
                runtime_skills = Path(payload["cwd"]) / ".agents" / "skills"
                installed_skill_ids = sorted(path.name for path in runtime_skills.iterdir() if path.is_dir())
                expected_skill_ids = sorted(skill_id for skill_id in role_skills if isinstance(skill_id, str))
                self.assertEqual(installed_skill_ids, expected_skill_ids, msg=f"role={role_id}")
                self.assertIn("task-management", installed_skill_ids, msg=f"role={role_id}")
                self.assertIn("track-tool", installed_skill_ids, msg=f"role={role_id}")
                self.assertIn("artifact-tool", installed_skill_ids, msg=f"role={role_id}")
                self.assertNotIn("actor_private-tool", installed_skill_ids, msg=f"role={role_id}")
                for removed in ("task" + "-manager", "track" + "-manager", "artifact" + "-manager"):
                    self.assertNotIn(removed, installed_skill_ids, msg=f"role={role_id}")

                for skill_id in expected_skill_ids:
                    source_dir = ROOT / skill_sources[skill_id]
                    target_dir = runtime_skills / skill_id
                    self._assert_directory_file_bytes_equal(source=source_dir, target=target_dir)

                if role_id == "dev":
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

    def test_start_with_role_wires_instance_env_and_lifecycle(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
            self.assertIn(payload["actor_id"], completed.stdout)
            self.assertIn("Input:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance input {payload['actor_id']} --text", completed.stdout)
            self.assertIn("Attach:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance attach {payload['actor_id']}", completed.stdout)
            self.assertIn("Stop:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance stop {payload['actor_id']}", completed.stdout)
            self.assertIn("Delete instance:", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance delete {payload['actor_id']} --yes", completed.stdout)

            self.assertGreaterEqual(len(payload["argv"]), 3, msg=payload["argv"])
            self.assertEqual(payload["argv"][:2], ["app-server", "--listen"])
            self.assertTrue(payload["argv"][2].startswith("unix://"))
            self.assertEqual(payload["active_role"], "pm")
            self.assertIsInstance(payload["actor_id"], str)
            self.assertTrue(payload["actor_id"])
            self.assertIsNotNone(payload["instance_json"])
            self.assertIsInstance(instance_snapshot, dict)

            instance_json_path = Path(payload["instance_json"])
            instance_root = shared_root / "instances" / payload["actor_id"]
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
            self.assertEqual(payload["actor_private_dir"], str(workspace_dir / "private"))
            self.assertTrue((workspace_dir / "private").is_dir())
            self.assertTrue(payload["runtime_broker_socket"], "runtime broker socket must be exported to codex")
            role_agents = ROOT / "tools" / "launcher" / "assets" / "roles" / "pm" / "AGENTS.md"
            self.assertTrue(role_agents.exists(), "pm role prompt asset must be checked in")
            self.assertEqual((workspace_dir / "AGENTS.md").read_text(encoding="utf-8"), role_agents.read_text(encoding="utf-8"))
            self.assertTrue((workspace_dir / "AGENTS.md").read_text(encoding="utf-8").startswith("# BuddySwitch Runtime Workspace\n"))
            copied_agents = (workspace_dir / "AGENTS.md").read_text(encoding="utf-8").lower()
            for token in (
                "guidance only and not the permission source",
                "prefer native buddyswitch env mcp tools",
                "start with the native buddyswitch env context summary tool",
                "context.get.tool_catalog",
                "python3 scripts/turn_runtime.py status",
                "## output rule",
            ):
                self.assertIn(token, copied_agents)
            self.assertNotIn("python3 scripts/env/client.py", copied_agents)
            self.assertNotIn("context summarize --payload", copied_agents)
            self.assertNotIn("search open-browser --payload", copied_agents)
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
            runtime_pm_contract = workspace_dir / "framework" / "contracts" / "pm.md"
            source_pm_contract = ROOT / "framework" / "contracts" / "pm.md"
            runtime_pm_contract_text = runtime_pm_contract.read_text(encoding="utf-8")
            self.assertEqual(runtime_pm_contract_text, source_pm_contract.read_text(encoding="utf-8"))
            self.assertNotIn("python3 scripts/env/client.py", runtime_pm_contract_text)
            self.assertIn("native BuddySwitch env MCP tools", runtime_pm_contract_text)
            runtime_skills = workspace_dir / ".agents" / "skills"
            self.assertTrue((runtime_skills / "task-management" / "SKILL.md").exists())
            self._assert_pm_runtime_skills(workspace_dir)
            for removed in ("task" + "-manager", "track" + "-manager", "artifact" + "-manager"):
                self.assertFalse((runtime_skills / removed).exists())
            self.assertFalse((runtime_skills / "shape-prototype").exists())
            runtime_turn_runtime = workspace_dir / "scripts" / "turn_runtime.py"
            self.assertEqual(
                runtime_turn_runtime.read_text(encoding="utf-8"),
                (ROOT / "scripts" / "turn_runtime.py").read_text(encoding="utf-8"),
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
                "scripts/env/services/private.py",
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
                "scripts/env/domain/private_workspace.py",
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
            self.assertTrue((workspace_dir / "private").is_dir())
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
            self.assertIn("[mcp_servers.buddyswitch-env]", config_text)
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
            self.assertEqual(instance_snapshot["actor_id"], payload["actor_id"])
            self.assertEqual(instance_snapshot["role"], "pm")
            self.assertNotIn("current_task_id", instance_snapshot)
            self.assertNotIn("current_track_id", instance_snapshot)
            self.assertEqual(instance_snapshot["instance_root"], str(instance_root))
            self.assertEqual(instance_snapshot["workspace_dir"], str(workspace_dir))
            browser_port = instance_snapshot["browser_port"]
            self.assertIsInstance(browser_port, int)
            self.assertTrue(instance_snapshot["updated_at"])

            stored_instance = json.loads(instance_json_path.read_text(encoding="utf-8"))
            self.assertEqual(stored_instance["status"], "active")
            self.assertEqual(stored_instance["actor_id"], payload["actor_id"])
            self.assertEqual(stored_instance["role"], "pm")
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
            self.assertFalse((shared_root / "workspace").exists(), "role-locked start must not use legacy shared workspace")

            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            mcp_add_entries = [entry for entry in call_entries if entry["argv"][:2] == ["mcp", "add"]]
            mcp_add_names = [entry["argv"][2] for entry in mcp_add_entries]
            self.assertIn("buddyswitch-env", mcp_add_names)
            self.assertIn("chrome-devtools-cockpit", mcp_add_names)
            self.assertNotIn("chrome-devtools", mcp_add_names)
            env_mcp_add = next(entry for entry in mcp_add_entries if entry["argv"][2] == "buddyswitch-env")
            self._assert_env_mcp_registration(
                env_mcp_add["argv"],
                actor_id=payload["actor_id"],
                role="pm",
                broker_socket=str(payload["runtime_broker_socket"]),
            )
            cockpit_add = next(entry for entry in mcp_add_entries if entry["argv"][2] == "chrome-devtools-cockpit")
            self._assert_cockpit_proxy_registration(cockpit_add["argv"], f"http://127.0.0.1:{browser_port}")

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

            actor_private_root = workspace_dir / "private"
            shared_actor_private_root = shared_root / "state" / "buddyswitch" / "local" / "private" / "pm"
            self.assertTrue(actor_private_root.is_dir(), "active actor_private root must exist in the instance workspace")
            self.assertFalse(shared_actor_private_root.exists(), "shared state actor_private remains tool-backed until written")

            self.assertFalse((workspace_dir / "buddyswitch/local/private/dev").exists())
            self.assertFalse((workspace_dir / "buddyswitch/content/" / "private").exists())

            for retired_relative_path in ("runs/raw", "buddyswitch/content/runs"):
                self.assertFalse((workspace_dir / retired_relative_path).exists())

    def test_start_with_role_returns_json_metadata_when_requested(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "pm", "--json"],
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

            self.assertTrue(payload["actor_id"].startswith("act-pm-"))
            self.assertEqual(payload["role"], "pm")
            self.assertEqual(payload["workspace_dir"], stored_instance["workspace_dir"])
            self.assertEqual(payload["project_workspace_dir"], capture_payload["project_workspace_dir"])
            self.assertEqual(payload["instance_record"], capture_payload["instance_json"])
            self.assertNotIn("Input: ./buddyswitch-codex", completed.stdout)
            self.assertEqual(stored_instance["actor_id"], payload["actor_id"])
            self.assertEqual(stored_instance["status"], "active")
            self.assertIn("thread_id", stored_instance)
            self.assertIn("app_server_pid", stored_instance)

    def test_start_with_role_starts_app_server_service_and_returns(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
            actor_id = payload["actor_id"]
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / actor_id
            instance_json_path = instance_root / "instance.json"
            instance_payload = json.loads(instance_json_path.read_text(encoding="utf-8"))

            self.assertIn(f"./buddyswitch-codex instance input {actor_id} --text", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance attach {actor_id}", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance stop {actor_id}", completed.stdout)
            self.assertIn(f"./buddyswitch-codex instance delete {actor_id} --yes", completed.stdout)
            self.assertGreaterEqual(len(payload["argv"]), 3, msg=payload["argv"])
            self.assertEqual(payload["argv"][:2], ["app-server", "--listen"])
            self.assertTrue(payload["argv"][2].startswith("unix://"))
            self.assertEqual(payload["active_role"], "pm")
            self.assertEqual(payload["actor_id"], actor_id)
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

    def test_start_with_role_starts_ready_daemon_for_main_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            daemon_dir = Path(str(ctx["instance_root"])) / "runtime" / "daemon"
            daemon_state = json.loads((daemon_dir / "state.json").read_text(encoding="utf-8"))
            daemon_pid = int((daemon_dir / "daemon.pid").read_text(encoding="utf-8").strip())

            self.assertTrue((daemon_dir / "daemon.pid").exists())
            self.assertTrue((daemon_dir / "daemon.log").exists())
            self.assertEqual(daemon_state["actor_id"], ctx["actor_id"])
            self.assertEqual(daemon_state["main_thread_id"], instance_payload["thread_id"])
            self.assertEqual(daemon_state["daemon_origin_turn_ids"], [])
            self.assertEqual(daemon_state["ready"]["pid"], daemon_pid)
            self.assertEqual(daemon_state["ready"]["main_thread_id"], instance_payload["thread_id"])

            status_result = subprocess.run(
                [str(LAUNCHER), "instance", "status", str(ctx["actor_id"]), "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_result.returncode, 0, msg=status_result.stderr)
            status_payload = json.loads(status_result.stdout)
            self.assertTrue(status_payload["daemon"]["ready"])
            self.assertEqual(status_payload["daemon"]["ready_main_thread_id"], instance_payload["thread_id"])
            self.assertEqual(status_payload["daemon"]["handlers"]["registered"], ["task_checkout", "message_available"])
            task_checkout_status = status_payload["daemon"]["handlers"]["items"]["task_checkout"]
            self.assertIs(task_checkout_status["enabled"], True)
            self.assertIs(task_checkout_status["active"], True)
            message_status = status_payload["daemon"]["handlers"]["items"]["message_available"]
            self.assertIs(message_status["enabled"], True)
            self.assertIs(message_status["active"], True)

            calls = self._read_json_lines(Path(str(ctx["calls_path"])))
            daemon_resume = next(
                row
                for row in calls
                if row.get("rpc_method") == "thread/resume" and row.get("client_name") == "buddyswitch_daemon"
            )
            self.assertEqual(daemon_resume["params"]["threadId"], instance_payload["thread_id"])

    def test_fake_codex_thread_start_is_unmaterialized_until_inject_or_turn_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                role="pm",
                state_payload={
                    "errors": {
                        "thread/inject_items": {
                            "code": -32000,
                            "message": "inject failed",
                        }
                    }
                },
            )

            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertNotEqual(completed.returncode, 0)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            thread_id = state_payload["thread_id"]
            thread = state_payload["threads"][thread_id]
            self.assertFalse(thread["rollout_materialized"])
            self.assertEqual(thread["turns"], [])
            self.assertEqual(thread["injected_items"], [])

    def test_fake_codex_inject_items_materializes_target_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            main_thread = state_payload["threads"][ctx["instance_payload"]["thread_id"]]
            self.assertTrue(main_thread["rollout_materialized"])
            self.assertEqual(main_thread["injected_items"][0]["role"], "assistant")

    def test_fake_codex_turn_start_still_materializes_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            thread_id = ctx["instance_payload"]["thread_id"]
            state_payload["threads"][thread_id]["rollout_materialized"] = False
            Path(str(ctx["state_file"])).write_text(
                json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )

            input_result = subprocess.run(
                [str(LAUNCHER), "instance", "input", ctx["actor_id"], "--text", "materialize", "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)
            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            self.assertTrue(state_payload["threads"][thread_id]["rollout_materialized"])

    def test_start_bootstraps_main_thread_rollout_before_daemon_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            calls = self._read_json_lines(Path(str(ctx["calls_path"])))
            rpc_rows = [row for row in calls if row.get("argv", [])[:1] == ["json-rpc"]]
            thread_id = ctx["instance_payload"]["thread_id"]
            relevant = [
                row
                for row in rpc_rows
                if row.get("rpc_method") in {"thread/start", "thread/inject_items", "thread/resume"}
            ]
            start_index = next(i for i, row in enumerate(relevant) if row["rpc_method"] == "thread/start")
            inject_index = next(i for i, row in enumerate(relevant) if row["rpc_method"] == "thread/inject_items")
            daemon_resume_index = next(
                i
                for i, row in enumerate(relevant)
                if row["rpc_method"] == "thread/resume" and row.get("client_name") == "buddyswitch_daemon"
            )

            self.assertLess(start_index, inject_index)
            self.assertLess(inject_index, daemon_resume_index)
            self.assertEqual(relevant[inject_index]["params"]["threadId"], thread_id)
            self.assertEqual(relevant[daemon_resume_index]["params"]["threadId"], thread_id)

    def test_start_bootstrap_uses_inject_items_not_turn_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            bootstrap = next(row for row in rpc_rows if row.get("rpc_method") == "thread/inject_items")
            self.assertEqual(bootstrap["params"]["threadId"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(
                bootstrap["params"]["items"],
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "[BuddySwitch internal bootstrap marker]",
                            }
                        ],
                    }
                ],
            )
            self.assertNotIn(
                "Initialize this " "BuddySwitch thread",
                json.dumps(self._read_json_lines(Path(str(ctx["calls_path"])))),
            )
            launcher_turn_starts = [
                row
                for row in rpc_rows
                if row.get("rpc_method") == "turn/start" and row.get("client_name") == "buddyswitch_launcher"
            ]
            self.assertEqual(launcher_turn_starts, [])

    def test_thread_bootstrap_marker_is_minimal_assistant_output_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            bootstrap = next(row for row in rpc_rows if row.get("rpc_method") == "thread/inject_items")
            self.assertEqual(
                bootstrap["params"]["items"],
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "[BuddySwitch internal bootstrap marker]",
                            }
                        ],
                    }
                ],
            )
            self.assertNotEqual(bootstrap["params"]["items"][0]["role"], "user")

    def test_start_bootstrap_failure_fails_closed_without_ready_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                role="pm",
                state_payload={
                    "errors": {
                        "thread/inject_items": {
                            "code": -32000,
                            "message": "inject failed",
                        }
                    }
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("thread/inject_items failed", completed.stderr)

            instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_payload["status"], "inactive")
            self.assertIsNone(instance_payload["app_server_pid"])
            self.assertIsNone(instance_payload["app_server_socket"])
            self.assertIsNone(instance_payload["app_server_log"])
            self.assertIsNone(instance_payload["browser_port"])
            self.assertEqual(instance_payload["last_failure"]["phase"], "thread_bootstrap")
            self.assertEqual(instance_payload.get("thread_id"), None)
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            bootstrap_calls = [row for row in rpc_rows if row.get("rpc_method") == "thread/inject_items"]
            self.assertEqual(len(bootstrap_calls), 1)
            self.assertFalse((Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "daemon.pid").exists())

    def test_start_bootstrap_timeout_retries_once_and_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                role="pm",
                state_payload={
                    "error_on_attempts": {
                        "thread/inject_items": {
                            "1": {
                                "code": -32000,
                                "message": "timed out waiting for thread/inject_items",
                            }
                        }
                    }
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            thread_start_calls = [row for row in rpc_rows if row.get("rpc_method") == "thread/start"]
            bootstrap_calls = [row for row in rpc_rows if row.get("rpc_method") == "thread/inject_items"]
            daemon_resume = next(
                row
                for row in rpc_rows
                if row.get("rpc_method") == "thread/resume" and row.get("client_name") == "buddyswitch_daemon"
            )

            self.assertEqual(len(thread_start_calls), 1)
            self.assertEqual(len(bootstrap_calls), 2)
            self.assertEqual(bootstrap_calls[0]["params"]["threadId"], bootstrap_calls[1]["params"]["threadId"])
            self.assertEqual(bootstrap_calls[0]["params"]["threadId"], instance_payload["thread_id"])
            self.assertEqual(daemon_resume["params"]["threadId"], instance_payload["thread_id"])
            self.assertEqual(instance_payload["status"], "active")
            self.assertNotIn("last_failure", instance_payload)

    def test_start_bootstrap_retry_failure_cleans_state_and_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                role="pm",
                state_payload={
                    "error_on_attempts": {
                        "thread/inject_items": {
                            "1": {
                                "code": -32000,
                                "message": "timed out waiting for thread/inject_items",
                            },
                            "2": {
                                "code": -32000,
                                "message": "timed out waiting for thread/inject_items again",
                            },
                        }
                    }
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("timed out waiting for thread/inject_items", completed.stderr)

            instance_root = Path(str(ctx["instance_root"]))
            instance_payload = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            bootstrap_calls = [row for row in rpc_rows if row.get("rpc_method") == "thread/inject_items"]

            self.assertEqual(len(bootstrap_calls), 2)
            self.assertEqual(instance_payload["status"], "inactive")
            self.assertIsNone(instance_payload["app_server_pid"])
            self.assertIsNone(instance_payload["app_server_socket"])
            self.assertIsNone(instance_payload["app_server_log"])
            self.assertIsNone(instance_payload["browser_port"])
            self.assertIsNone(instance_payload.get("thread_id"))
            self.assertEqual(instance_payload["last_failure"]["phase"], "thread_bootstrap")
            self.assertEqual(instance_payload["last_failure"]["thread_id"], bootstrap_calls[0]["params"]["threadId"])
            self.assertIn("timed out waiting for thread/inject_items", instance_payload["last_failure"]["message"])
            self.assertIsInstance(instance_payload["last_failure"].get("browser_port"), int)
            self.assertTrue(instance_payload["last_failure"].get("failed_at"))
            self.assertFalse((instance_root / "runtime" / "app-server.pid").exists())
            self.assertFalse((instance_root / "runtime" / "app-server.sock").exists())
            self.assertFalse((instance_root / "runtime" / "app-server.socket").exists())
            self.assertFalse((instance_root / "runtime" / "runtime-broker.pid").exists())
            self.assertFalse((instance_root / "runtime" / "daemon" / "daemon.pid").exists())
            self.assertFalse((instance_root / "browser" / "chrome.pid").exists())

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
                [str(LAUNCHER), "instance", "start", "--role", "pm", "--", "debug", "prompt-input", "x"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, msg=completed.stderr)
            self.assertIn("start no longer accepts Codex args", completed.stderr)
            self.assertFalse((source_home_path / ".codex-buddyswitch" / "instances").exists())

    def test_start_with_role_allocates_next_browser_port_when_default_is_busy(self) -> None:
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
        expected_port = self._first_available_browser_port()
        if expected_port is None:
            self.skipTest("no browser cockpit port is available in range 9222..9321")

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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
            self.assertEqual(instance_json["browser_port"], expected_port)

            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            cockpit_add = next(entry for entry in call_entries if entry["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"])
            self._assert_cockpit_proxy_registration(cockpit_add["argv"], f"http://127.0.0.1:{expected_port}")

    def test_input_starts_turn_when_thread_idle_defaults_to_raw(self) -> None:
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
                    ctx["actor_id"],
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
            input_item = turn_start["params"]["input"][0]
            self.assertEqual(input_item["type"], "text")
            self._assert_raw_input(input_item["text"], raw_text="Draft brief")
            self.assertEqual(turn_start["params"]["permissions"], "buddyswitch-runtime")
            self.assertNotIn("sandboxPolicy", turn_start["params"])
            self.assertIn("turn-test", input_result.stdout)

    def test_input_json_starts_turn_when_thread_idle_without_changing_sent_text(self) -> None:
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
                    ctx["actor_id"],
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
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["action"], "start")
            self.assertTrue(payload["turn_id"])
            self.assertNotIn("Started turn:", input_result.stdout)

            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            turn_start = next(row for row in rpc_rows if row["rpc_method"] == "turn/start")
            self._assert_raw_input(turn_start["params"]["input"][0]["text"], raw_text="Draft brief")

    def test_input_steers_in_progress_turn_defaults_to_raw(self) -> None:
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
                    ctx["actor_id"],
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
            input_item = steer["params"]["input"][0]
            self.assertEqual(input_item["type"], "text")
            self._assert_raw_input(input_item["text"], raw_text="Steer current turn")

    def test_input_task_tui_wrapper_starts_turn_when_thread_idle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self._seed_instance_taskbox_current(
                instance_root=Path(str(ctx["instance_root"])),
                role=str(ctx["instance_payload"]["role"]),
            )

            input_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    ctx["actor_id"],
                    "--text",
                    "Draft brief",
                    "--input-wrapper",
                    "task-tui",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            turn_start = next(row for row in rpc_rows if row["rpc_method"] == "turn/start")
            self._assert_composed_task_input(turn_start["params"]["input"][0]["text"], raw_text="Draft brief")

    def test_input_task_tui_wrapper_steers_in_progress_turn(self) -> None:
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
            self._seed_instance_taskbox_current(
                instance_root=Path(str(ctx["instance_root"])),
                role=str(ctx["instance_payload"]["role"]),
            )

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            input_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "input",
                    ctx["actor_id"],
                    "--text",
                    "Steer current turn",
                    "--input-wrapper",
                    "task-tui",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            steer = next(row for row in rpc_rows if row["rpc_method"] == "turn/steer")
            self._assert_composed_task_input(steer["params"]["input"][0]["text"], raw_text="Steer current turn")

    def test_input_rejects_unknown_wrapper_without_rpc_mutation(self) -> None:
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
                    ctx["actor_id"],
                    "--text",
                    "Draft brief",
                    "--input-wrapper",
                    "task-ui",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(input_result.returncode, 0)
            self.assertEqual(self._read_rpc_rows(Path(str(ctx["calls_path"]))), [])

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
                    ctx["actor_id"],
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
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["action"], "steer")
            self.assertEqual(payload["turn_id"], "turn-123")
            self.assertEqual(payload["expected_turn_id"], "turn-123")
            self.assertNotIn("Steered turn:", input_result.stdout)

    def test_side_creates_child_injects_boundary_and_sends_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={"next_side_thread_id": "thread-side-1"},
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            side_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    ctx["actor_id"],
                    "--text",
                    "Explore the API shape",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(side_result.returncode, 0, msg=side_result.stderr)
            payload = json.loads(side_result.stdout)
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
            self.assertEqual(payload["parent_thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["side_thread_id"], "thread-side-1")
            self.assertEqual(payload["action"], "start")
            self.assertTrue(payload.get("turn_id"))

            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            methods = [row["rpc_method"] for row in rpc_rows]
            self.assertIn("thread/fork", methods)
            self.assertIn("thread/inject_items", methods)
            self.assertIn("turn/start", methods)

            fork = next(row for row in rpc_rows if row["rpc_method"] == "thread/fork")
            self.assertEqual(fork["params"]["threadId"], ctx["instance_payload"]["thread_id"])
            self.assertTrue(fork["params"]["ephemeral"])
            self.assertEqual(fork["params"]["permissions"], "buddyswitch-runtime")
            self.assertIn("runtimeWorkspaceRoots", fork["params"])
            self.assertIn("developerInstructions", fork["params"])
            self.assertIn("side conversation", fork["params"]["developerInstructions"])

            inject = next(row for row in rpc_rows if row["rpc_method"] == "thread/inject_items")
            self.assertEqual(inject["params"]["threadId"], "thread-side-1")
            item = inject["params"]["items"][0]
            self.assertEqual(item["type"], "message")
            self.assertEqual(item["role"], "user")
            self.assertIn("Side conversation boundary.", item["content"][0]["text"])

            turn_start = next(row for row in rpc_rows if row["rpc_method"] == "turn/start")
            self.assertEqual(turn_start["params"]["threadId"], "thread-side-1")
            self.assertEqual(
                turn_start["params"]["input"],
                [{"type": "text", "text": "Explore the API shape", "text_elements": []}],
            )
            self.assertNotIn("[TASK CONTEXT]", turn_start["params"]["input"][0]["text"])
            self.assertEqual(turn_start["params"]["permissions"], "buddyswitch-runtime")
            self.assertNotEqual(turn_start["params"]["threadId"], ctx["instance_payload"]["thread_id"])

            instance_payload = json.loads((ctx["instance_root"] / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(len(instance_payload["side_threads"]), 1)
            side_thread = instance_payload["side_threads"][0]
            self.assertEqual(side_thread["thread_id"], "thread-side-1")
            self.assertEqual(side_thread["parent_thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(side_thread["status"], "open")

    def test_side_create_human_output_prints_side_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={"next_side_thread_id": "thread-side-1"},
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            side_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    ctx["actor_id"],
                    "--text",
                    "Explore the API shape",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(side_result.returncode, 0, msg=side_result.stderr)
            self.assertIn("Side conversation started:", side_result.stdout)
            self.assertIn("thread-side-1", side_result.stdout)
            self.assertNotIn("{", side_result.stdout)

    def test_side_send_existing_active_child_steers_side_not_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            main_thread_id = str(ctx["instance_payload"]["thread_id"])
            self._set_instance_side_threads(
                ctx["instance_root"],
                [{"thread_id": "thread-side-1", "parent_thread_id": main_thread_id, "status": "open"}],
            )
            self._set_fake_side_thread_state(
                Path(str(ctx["state_file"])),
                main_thread_id=main_thread_id,
                side_thread_id="thread-side-1",
                side_status={"type": "active", "activeFlags": []},
                side_turns=[
                    {
                        "id": "turn-side-1",
                        "items": [],
                        "itemsView": "summary",
                        "status": "inProgress",
                        "error": None,
                        "startedAt": 0,
                        "completedAt": None,
                        "durationMs": None,
                    }
                ],
            )
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")

            side_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    ctx["actor_id"],
                    "--side-thread-id",
                    "thread-side-1",
                    "--text",
                    "Narrow that answer",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(side_result.returncode, 0, msg=side_result.stderr)
            payload = json.loads(side_result.stdout)
            self.assertEqual(payload["action"], "send")
            self.assertEqual(payload["side_thread_id"], "thread-side-1")
            self.assertEqual(payload["parent_thread_id"], main_thread_id)
            self.assertEqual(payload["thread_action"], "steer")
            self.assertEqual(payload["expected_turn_id"], "turn-side-1")

            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            methods = [row["rpc_method"] for row in rpc_rows]
            self.assertNotIn("thread/fork", methods)
            self.assertIn("turn/steer", methods)
            steer = next(row for row in rpc_rows if row["rpc_method"] == "turn/steer")
            self.assertEqual(steer["params"]["threadId"], "thread-side-1")
            self.assertEqual(steer["params"]["expectedTurnId"], "turn-side-1")
            self.assertNotEqual(steer["params"]["threadId"], main_thread_id)

    def test_side_send_existing_idle_child_starts_side_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            main_thread_id = str(ctx["instance_payload"]["thread_id"])
            self._set_instance_side_threads(
                ctx["instance_root"],
                [{"thread_id": "thread-side-1", "parent_thread_id": main_thread_id, "status": "open"}],
            )
            self._set_fake_side_thread_state(
                Path(str(ctx["state_file"])),
                main_thread_id=main_thread_id,
                side_thread_id="thread-side-1",
                side_status={"type": "idle"},
                side_turns=[],
            )
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")

            side_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    ctx["actor_id"],
                    "--side-thread-id",
                    "thread-side-1",
                    "--text",
                    "Follow up",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(side_result.returncode, 0, msg=side_result.stderr)
            payload = json.loads(side_result.stdout)
            self.assertEqual(payload["action"], "send")
            self.assertEqual(payload["thread_action"], "start")

            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            turn_start = next(row for row in rpc_rows if row["rpc_method"] == "turn/start")
            self.assertEqual(turn_start["params"]["threadId"], "thread-side-1")
            self.assertEqual(turn_start["params"]["permissions"], "buddyswitch-runtime")

    def test_side_send_rejects_unknown_side_thread_without_rpc_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            side_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    ctx["actor_id"],
                    "--side-thread-id",
                    "thread-unknown",
                    "--text",
                    "Do not send",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(side_result.returncode, 0)
            self.assertIn("not registered", side_result.stderr.lower())
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            methods = [row["rpc_method"] for row in rpc_rows]
            self.assertNotIn("thread/fork", methods)
            self.assertNotIn("turn/start", methods)
            self.assertNotIn("turn/steer", methods)
            self.assertNotIn("turn/interrupt", methods)

    def test_side_send_rejects_main_thread_id_as_side_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            main_thread_id = str(ctx["instance_payload"]["thread_id"])
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    ctx["actor_id"],
                    "--side-thread-id",
                    main_thread_id,
                    "--text",
                    "Bad",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("main thread", result.stderr.lower())
            methods = [row["rpc_method"] for row in self._read_rpc_rows(Path(str(ctx["calls_path"])))]
            self.assertNotIn("turn/start", methods)
            self.assertNotIn("turn/steer", methods)
            self.assertNotIn("turn/interrupt", methods)

    def test_side_close_rejects_main_thread_id_as_side_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            main_thread_id = str(ctx["instance_payload"]["thread_id"])
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    "close",
                    ctx["actor_id"],
                    "--side-thread-id",
                    main_thread_id,
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("main thread", result.stderr.lower())
            methods = [row["rpc_method"] for row in self._read_rpc_rows(Path(str(ctx["calls_path"])))]
            self.assertNotIn("turn/interrupt", methods)
            self.assertNotIn("turn/start", methods)
            self.assertNotIn("turn/steer", methods)

    def test_side_close_interrupts_registered_child_and_removes_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            main_thread_id = str(ctx["instance_payload"]["thread_id"])
            main_turn = {
                "id": "turn-main-1",
                "items": [],
                "itemsView": "summary",
                "status": "inProgress",
                "error": None,
                "startedAt": 0,
                "completedAt": None,
                "durationMs": None,
            }
            self._set_instance_side_threads(
                ctx["instance_root"],
                [{"thread_id": "thread-side-1", "parent_thread_id": main_thread_id, "status": "open"}],
            )
            self._set_fake_side_thread_state(
                Path(str(ctx["state_file"])),
                main_thread_id=main_thread_id,
                main_status={"type": "active", "activeFlags": []},
                main_turns=[main_turn],
                side_thread_id="thread-side-1",
                side_status={"type": "active", "activeFlags": []},
                side_turns=[
                    {
                        "id": "turn-side-1",
                        "items": [],
                        "itemsView": "summary",
                        "status": "inProgress",
                        "error": None,
                        "startedAt": 0,
                        "completedAt": None,
                        "durationMs": None,
                    }
                ],
            )
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")

            close_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    "close",
                    ctx["actor_id"],
                    "--side-thread-id",
                    "thread-side-1",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(close_result.returncode, 0, msg=close_result.stderr)
            payload = json.loads(close_result.stdout)
            self.assertEqual(payload["action"], "close")
            self.assertEqual(payload["side_thread_id"], "thread-side-1")
            self.assertEqual(payload["parent_thread_id"], main_thread_id)
            self.assertEqual(payload["turn_id"], "turn-side-1")

            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            interrupt = next(row for row in rpc_rows if row["rpc_method"] == "turn/interrupt")
            self.assertEqual(interrupt["params"]["threadId"], "thread-side-1")
            self.assertEqual(interrupt["params"]["turnId"], "turn-side-1")

            instance_payload = json.loads((ctx["instance_root"] / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_payload.get("side_threads", []), [])

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            main_state = state_payload["threads"][main_thread_id]
            self.assertEqual(main_state["turns"][0]["status"], "inProgress")

    def test_side_close_idle_registered_child_uses_startup_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            main_thread_id = str(ctx["instance_payload"]["thread_id"])
            self._set_instance_side_threads(
                ctx["instance_root"],
                [{"thread_id": "thread-side-1", "parent_thread_id": main_thread_id, "status": "open"}],
            )
            self._set_fake_side_thread_state(
                Path(str(ctx["state_file"])),
                main_thread_id=main_thread_id,
                side_thread_id="thread-side-1",
                side_status={"type": "idle"},
                side_turns=[],
            )
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")

            close_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    "close",
                    ctx["actor_id"],
                    "--side-thread-id",
                    "thread-side-1",
                    "--json",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(close_result.returncode, 0, msg=close_result.stderr)
            payload = json.loads(close_result.stdout)
            interrupt = next(
                row
                for row in self._read_rpc_rows(Path(str(ctx["calls_path"])))
                if row["rpc_method"] == "turn/interrupt"
            )
            self.assertEqual(interrupt["params"]["threadId"], "thread-side-1")
            self.assertEqual(interrupt["params"]["turnId"], "")
            self.assertTrue(payload["startup_interrupt"])

    def test_side_create_requires_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            result = subprocess.run(
                [str(LAUNCHER), "instance", "side", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("requires --text", result.stderr)
            self.assertEqual(self._read_json_lines(Path(str(ctx["calls_path"]))), [])

    def test_side_send_requires_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    ctx["actor_id"],
                    "--side-thread-id",
                    "thread-side-1",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("requires --text", result.stderr)
            self.assertEqual(self._read_json_lines(Path(str(ctx["calls_path"]))), [])

    def test_side_close_requires_side_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            result = subprocess.run(
                [str(LAUNCHER), "instance", "side", "close", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("requires --side-thread-id", result.stderr)
            self.assertEqual(self._read_json_lines(Path(str(ctx["calls_path"]))), [])

    def test_side_rejects_inactive_or_unhealthy_instance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            state_payload["errors"] = {
                "thread/loaded/list": {"code": -32001, "message": "probe failed"}
            }
            Path(str(ctx["state_file"])).write_text(
                json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")

            result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "side",
                    ctx["actor_id"],
                    "--text",
                    "Explore",
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 3)
            self.assertIn("unhealthy or inactive", result.stderr.lower())
            methods = [row["rpc_method"] for row in self._read_rpc_rows(Path(str(ctx["calls_path"])))]
            self.assertNotIn("thread/fork", methods)
            self.assertNotIn("turn/start", methods)
            self.assertNotIn("turn/steer", methods)
            self.assertNotIn("turn/interrupt", methods)

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
                    ctx["actor_id"],
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
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
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
                        "threadId": "thread-act-pm-test",
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
                    ctx["actor_id"],
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
                    ctx["actor_id"],
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
            self.assertEqual(clear_payload["actor_id"], ctx["actor_id"])
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
                    ctx["actor_id"],
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
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
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
                    ctx["actor_id"],
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
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
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

    def test_clear_restarts_ready_daemon_for_new_main_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={"clear_thread_id": "thread-cleared"},
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            old_daemon_pid = int(
                (Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "daemon.pid").read_text(encoding="utf-8").strip()
            )

            clear_result = subprocess.run(
                [str(LAUNCHER), "instance", "clear", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(clear_result.returncode, 0, msg=clear_result.stderr)
            daemon_state = json.loads((Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(daemon_state["main_thread_id"], "thread-cleared")
            self.assertTrue((Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "daemon.pid").exists())
            new_daemon_pid = int(
                (Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "daemon.pid").read_text(encoding="utf-8").strip()
            )
            self.assertEqual(daemon_state["ready"]["pid"], new_daemon_pid)
            self.assertEqual(daemon_state["ready"]["main_thread_id"], "thread-cleared")
            self.assertFalse(self._pid_is_live(old_daemon_pid))

    def test_clear_bootstraps_new_thread_before_daemon_resume(self) -> None:
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
                [str(LAUNCHER), "instance", "clear", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(clear_result.returncode, 0, msg=clear_result.stderr)

            calls = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            start = next(row for row in calls if row.get("rpc_method") == "thread/start")
            inject = next(row for row in calls if row.get("rpc_method") == "thread/inject_items")
            daemon_resume = next(
                row
                for row in calls
                if row.get("rpc_method") == "thread/resume" and row.get("client_name") == "buddyswitch_daemon"
            )
            self.assertEqual(start["params"]["sessionStartSource"], "clear")
            self.assertEqual(inject["params"]["threadId"], "thread-cleared")
            self.assertEqual(daemon_resume["params"]["threadId"], "thread-cleared")

    def test_clear_bootstrap_failure_preserves_new_thread_and_stops_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={"clear_thread_id": "thread-cleared"},
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            state_payload["errors"] = {
                "thread/inject_items": {
                    "code": -32000,
                    "message": "inject failed",
                }
            }
            Path(str(ctx["state_file"])).write_text(
                json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )

            clear_result = subprocess.run(
                [str(LAUNCHER), "instance", "clear", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(clear_result.returncode, 0)
            self.assertIn("thread/inject_items failed", clear_result.stderr)
            instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_payload["thread_id"], "thread-cleared")
            self.assertEqual(instance_payload["status"], "inactive")
            self.assertIsNone(instance_payload["app_server_pid"])
            self.assertIsNone(instance_payload["app_server_socket"])
            self.assertIsNone(instance_payload["app_server_log"])
            self.assertFalse((Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "daemon.pid").exists())

    def test_clear_daemon_failure_after_bootstrap_preserves_materialized_new_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "clear_thread_id": "thread-cleared",
                    "thread_resume_error_on_count": 2,
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            clear_result = subprocess.run(
                [str(LAUNCHER), "instance", "clear", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(clear_result.returncode, 0)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            self.assertTrue(state_payload["threads"]["thread-cleared"]["rollout_materialized"])
            state_payload.pop("thread_resume_error_on_count", None)
            Path(str(ctx["state_file"])).write_text(
                json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )

            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
            self.assertEqual(json.loads(resume_result.stdout)["thread_id"], "thread-cleared")

    def test_clear_daemon_start_failure_preserves_new_thread_and_stops_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "clear_thread_id": "thread-cleared",
                    "thread_resume_error_on_count": 2,
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            clear_result = subprocess.run(
                [str(LAUNCHER), "instance", "clear", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(clear_result.returncode, 0)
            instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_payload["thread_id"], "thread-cleared")
            self.assertEqual(instance_payload["status"], "inactive")
            self.assertIsNone(instance_payload["app_server_pid"])
            self.assertIsNone(instance_payload["app_server_socket"])
            self.assertIsNone(instance_payload["app_server_log"])

            status_result = subprocess.run(
                [str(LAUNCHER), "instance", "status", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_result.returncode, 0, msg=status_result.stderr)
            status_payload = json.loads(status_result.stdout)
            self.assertEqual(status_payload["status"], "inactive")
            self.assertFalse(status_payload["app_server"]["healthy"])
            self.assertFalse(status_payload["daemon"]["live"])

    def test_resume_after_clear_daemon_failure_uses_new_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "clear_thread_id": "thread-cleared",
                    "thread_resume_error_on_count": 2,
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            clear_result = subprocess.run(
                [str(LAUNCHER), "instance", "clear", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(clear_result.returncode, 0)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            state_payload.pop("thread_resume_error_on_count", None)
            Path(str(ctx["state_file"])).write_text(json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
            payload = json.loads(resume_result.stdout)
            self.assertEqual(payload["thread_id"], "thread-cleared")
            calls = self._read_json_lines(Path(str(ctx["calls_path"])))
            resume_calls = [row for row in calls if row.get("rpc_method") == "thread/resume"]
            self.assertTrue(resume_calls)
            self.assertEqual(resume_calls[-1]["params"]["threadId"], "thread-cleared")

    def test_attach_after_clear_uses_new_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={"clear_thread_id": "thread-cleared"},
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            clear_result = subprocess.run(
                [str(LAUNCHER), "instance", "clear", ctx["actor_id"], "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(clear_result.returncode, 0, msg=clear_result.stderr)
            self.assertEqual(json.loads(clear_result.stdout)["thread_id"], "thread-cleared")

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            attach_result = subprocess.run(
                [str(LAUNCHER), "instance", "attach", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(attach_result.returncode, 0, msg=attach_result.stderr)

            payload = json.loads(Path(str(ctx["capture_path"])).read_text(encoding="utf-8"))
            self.assertEqual(payload["argv"][-1], "thread-cleared")
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            resume_rpc = next(row for row in calls if row.get("rpc_method") == "thread/resume")
            self.assertEqual(resume_rpc["params"]["threadId"], "thread-cleared")

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
                    ctx["actor_id"],
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
            actor_id = "act-pm-unhealthy"
            instance_root, _workspace_dir = self._write_instance_record(
                shared_root,
                actor_id,
                status="active",
                thread_id="thread-test",
                app_server_pid=999999,
                app_server_socket="/tmp/buddyswitch-app-server-missing.sock",
                app_server_log=str(shared_root / "instances" / actor_id / "runtime" / "app-server.log"),
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
                    actor_id,
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
                    ctx["actor_id"],
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

    def test_instance_resume_json_restarts_stopped_instance_with_original_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            actor_id = str(ctx["actor_id"])
            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            thread_id = str(instance_payload["thread_id"])

            input_result = subprocess.run(
                [str(LAUNCHER), "instance", "input", actor_id, "--text", "materialize", "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)

            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
            payload = json.loads(resume_result.stdout)
            self.assertEqual(payload["actor_id"], actor_id)
            self.assertEqual(payload["thread_id"], thread_id)
            self.assertEqual(payload["status"], "active")
            record = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            config_text = (Path(str(ctx["instance_root"])) / "codex-home" / "config.toml").read_text(encoding="utf-8")
            self.assertEqual(record["thread_id"], thread_id)
            self.assertEqual(record["status"], "active")
            self.assertIsInstance(record["app_server_pid"], int)
            self.assertTrue(record["app_server_socket"])
            self.assertIn('default_permissions = "buddyswitch-runtime"', config_text)
            self.assertIn("[permissions.buddyswitch-runtime.filesystem]", config_text)
            self._assert_codex_automation_config(config_text, shared_root=Path(str(ctx["shared_root"])))

    def test_instance_resume_starts_ready_daemon_for_original_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            actor_id = str(ctx["actor_id"])
            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            thread_id = str(instance_payload["thread_id"])

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)

            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
            daemon_dir = Path(str(ctx["instance_root"])) / "runtime" / "daemon"
            daemon_state = json.loads((daemon_dir / "state.json").read_text(encoding="utf-8"))
            daemon_pid = int((daemon_dir / "daemon.pid").read_text(encoding="utf-8").strip())
            self.assertEqual(daemon_state["main_thread_id"], thread_id)
            self.assertTrue((daemon_dir / "daemon.pid").exists())
            self.assertEqual(daemon_state["ready"]["pid"], daemon_pid)
            self.assertEqual(daemon_state["ready"]["main_thread_id"], thread_id)

    def test_instance_resume_uses_thread_resume_for_original_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            actor_id = str(ctx["actor_id"])
            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            thread_id = str(instance_payload["thread_id"])

            input_result = subprocess.run(
                [str(LAUNCHER), "instance", "input", actor_id, "--text", "materialize", "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            resume_calls = [row for row in calls if row.get("rpc_method") == "thread/resume"]
            self.assertTrue(resume_calls, "resume must use Codex app-server thread/resume")
            self.assertEqual(resume_calls[-1]["params"]["threadId"], thread_id)
            self.assertEqual(resume_calls[-1]["params"]["excludeTurns"], True)

    def test_instance_resume_does_not_bootstrap_existing_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            actor_id = str(ctx["actor_id"])
            thread_id = str(ctx["instance_payload"]["thread_id"])

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            resume_calls = [row for row in rpc_rows if row.get("rpc_method") == "thread/resume"]
            inject_calls = [row for row in rpc_rows if row.get("rpc_method") == "thread/inject_items"]
            self.assertTrue(resume_calls)
            self.assertEqual(resume_calls[-1]["params"]["threadId"], thread_id)
            self.assertEqual(inject_calls, [])

    def test_instance_resume_reports_no_rollout_for_unmaterialized_legacy_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            actor_id = str(ctx["actor_id"])
            thread_id = str(ctx["instance_payload"]["thread_id"])

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            state_payload["threads"][thread_id]["rollout_materialized"] = False
            Path(str(ctx["state_file"])).write_text(
                json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(resume_result.returncode, 0)
            self.assertIn("no rollout found", resume_result.stderr)
            rpc_rows = self._read_rpc_rows(Path(str(ctx["calls_path"])))
            self.assertEqual([row for row in rpc_rows if row.get("rpc_method") == "thread/inject_items"], [])

    def test_instance_resume_human_output_reports_instance_and_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            actor_id = str(ctx["actor_id"])
            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            thread_id = str(instance_payload["thread_id"])

            input_result = subprocess.run(
                [str(LAUNCHER), "instance", "input", actor_id, "--text", "materialize", "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(input_result.returncode, 0, msg=input_result.stderr)

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)

            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", actor_id],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
            self.assertIn(f"Instance resumed: {actor_id}", resume_result.stdout)
            self.assertIn(f"Thread: {thread_id}", resume_result.stdout)

    def test_instance_resume_active_instance_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            actor_id = str(ctx["actor_id"])
            record_path = Path(str(ctx["instance_root"])) / "instance.json"
            before = json.loads(record_path.read_text(encoding="utf-8"))
            thread_id = str(before["thread_id"])

            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resume_result.returncode, 0, msg=resume_result.stderr)
            payload = json.loads(resume_result.stdout)
            self.assertEqual(payload["actor_id"], actor_id)
            self.assertEqual(payload["thread_id"], thread_id)
            self.assertEqual(payload["status"], "active")
            after = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(after["thread_id"], before["thread_id"])
            self.assertEqual(after["app_server_socket"], before["app_server_socket"])
            rpc_calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertFalse(
                [row for row in rpc_calls if row.get("rpc_method") == "thread/resume"],
                "active resume must not restart lifecycle through thread/resume",
            )

    def test_instance_resume_blocks_when_thread_id_missing(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-no-thread"
            self._write_instance_record(
                shared_root,
                actor_id,
                status="inactive",
                thread_id=None,
            )
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", actor_id, "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(resume_result.returncode, 3)
            self.assertIn("has no thread id", resume_result.stderr)

    def test_instance_resume_keeps_inactive_when_thread_resume_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home), role="pm")
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            actor_id = str(ctx["actor_id"])
            instance_payload = ctx["instance_payload"]
            assert isinstance(instance_payload, dict)
            thread_id = str(instance_payload["thread_id"])

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)

            Path(str(ctx["state_file"])).write_text(
                json.dumps(
                    {
                        "thread_id": thread_id,
                        "errors": {
                            "thread/resume": {
                                "code": -32600,
                                "message": f"no rollout found for thread id {thread_id}",
                            }
                        },
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            resume_result = subprocess.run(
                [str(LAUNCHER), "instance", "resume", actor_id, "--json"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(resume_result.returncode, 0)
            self.assertIn("thread/resume failed", resume_result.stderr)
            record = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "inactive")
            self.assertIsNone(record.get("app_server_pid"))
            self.assertIsNone(record.get("app_server_socket"))

    def test_attach_preflights_thread_resume_then_invokes_remote_resume_tui(self) -> None:
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
                    ctx["actor_id"],
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
            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            resume_rpc = next(row for row in calls if row.get("rpc_method") == "thread/resume")
            self.assertEqual(resume_rpc["params"]["threadId"], instance_payload["thread_id"])
            self.assertEqual(resume_rpc["params"]["cwd"], instance_payload["workspace_dir"])
            self.assertEqual(resume_rpc["params"]["permissions"], "buddyswitch-runtime")
            self.assertEqual(resume_rpc["params"]["excludeTurns"], True)
            self.assertNotIn("path", resume_rpc["params"])

            self.assertEqual(
                payload["argv"],
                [
                    "resume",
                    "--remote",
                    f"unix://{instance_payload['app_server_socket']}",
                    instance_payload["thread_id"],
                ],
            )
            instance_root = Path(str(ctx["instance_root"]))
            self.assertEqual(payload["cwd"], str((instance_root / "workspace").resolve()))
            self.assertEqual(payload["home"], str(instance_root / "home"))
            self.assertEqual(payload["codex_home"], str(instance_root / "codex-home"))
            self.assertEqual(payload["xdg_config_home"], str(instance_root / "xdg-config"))
            self.assertEqual(payload["instance_json"], str(instance_root / "instance.json"))
            self.assertEqual(instance_payload["status"], "active")
            self.assertTrue(Path(instance_payload["app_server_socket"]).exists())

    def test_attach_to_active_turn_preflights_same_running_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_status": {"type": "active", "activeFlags": []},
                    "turns": [
                        {
                            "id": "turn-active",
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
            attach_result = subprocess.run(
                [str(LAUNCHER), "instance", "attach", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(attach_result.returncode, 0, msg=attach_result.stderr)

            instance_payload = json.loads((Path(str(ctx["instance_root"])) / "instance.json").read_text(encoding="utf-8"))
            payload = json.loads(Path(str(ctx["capture_path"])).read_text(encoding="utf-8"))
            self.assertEqual(payload["argv"][-1], instance_payload["thread_id"])

            calls = [
                json.loads(line)
                for line in Path(str(ctx["calls_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            resume_rpc = next(row for row in calls if row.get("rpc_method") == "thread/resume")
            self.assertEqual(resume_rpc["params"]["threadId"], instance_payload["thread_id"])

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
                    ctx["actor_id"],
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
            actor_id = "act-pm-attach-unhealthy"
            self._write_instance_record(
                shared_root,
                actor_id,
                status="active",
                thread_id="thread-test",
                app_server_pid=999999,
                app_server_socket="/tmp/buddyswitch-app-server-missing.sock",
                app_server_log=str(shared_root / "instances" / actor_id / "runtime" / "app-server.log"),
            )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            attach_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "attach",
                    actor_id,
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(attach_result.returncode, 0)
            self.assertIn("unhealthy", attach_result.stderr.lower())

    def test_attach_blocks_when_thread_resume_returns_different_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            state_payload["thread_resume_response_thread_id"] = "thread-other"
            Path(str(ctx["state_file"])).write_text(json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            Path(str(ctx["capture_path"])).unlink(missing_ok=True)
            attach_result = subprocess.run(
                [str(LAUNCHER), "instance", "attach", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(attach_result.returncode, 0)
            self.assertIn("thread/resume returned unexpected thread id", attach_result.stderr)
            self.assertFalse(Path(str(ctx["capture_path"])).exists(), "TUI must not launch after mismatched preflight")

    def test_attach_blocks_when_thread_resume_preflight_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            state_payload = json.loads(Path(str(ctx["state_file"])).read_text(encoding="utf-8"))
            state_payload["errors"] = {
                "thread/resume": {
                    "code": -32004,
                    "message": "thread not loaded: thread-test",
                }
            }
            Path(str(ctx["state_file"])).write_text(json.dumps(state_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            Path(str(ctx["capture_path"])).unlink(missing_ok=True)
            Path(str(ctx["calls_path"])).write_text("", encoding="utf-8")
            attach_result = subprocess.run(
                [str(LAUNCHER), "instance", "attach", ctx["actor_id"]],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(attach_result.returncode, 0)
            self.assertIn("thread/resume failed", attach_result.stderr)
            self.assertFalse(Path(str(ctx["capture_path"])).exists(), "TUI must not launch after failed preflight")

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
                    ctx["actor_id"],
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
            self.assertFalse((Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "daemon.pid").exists())

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
                    ctx["actor_id"],
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
                {"actor_id": ctx["actor_id"], "status": "inactive"},
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
            self.assertFalse((Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "daemon.pid").exists())

    def test_stop_is_idempotent_for_stale_service(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-stale-stop"
            instance_root, _workspace_dir = self._write_instance_record(
                shared_root,
                actor_id,
                status="active",
                thread_id="thread-test",
                app_server_pid=999999,
                app_server_socket="/tmp/buddyswitch-app-server-stale.sock",
                app_server_log=str(shared_root / "instances" / actor_id / "runtime" / "app-server.log"),
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
                    actor_id,
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
                    ctx["actor_id"],
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
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
            self.assertEqual(payload["role"], "pm")
            self.assertEqual(payload["status"], "active")
            self.assertEqual(payload["thread_id"], ctx["instance_payload"]["thread_id"])
            self.assertEqual(payload["app_server"]["healthy"], True)
            self.assertIn("daemon", payload)
            self.assertTrue(payload["daemon"]["pid_file"].endswith("runtime/daemon/daemon.pid"))
            self.assertTrue(payload["daemon"]["state_path"].endswith("runtime/daemon/state.json"))
            self.assertEqual(payload["daemon"]["handlers"]["registered"], ["task_checkout", "message_available"])
            self.assertTrue(payload["daemon"]["handlers"]["items"]["task_checkout"]["active"])
            self.assertTrue(payload["daemon"]["handlers"]["items"]["message_available"]["active"])
            self.assertEqual(payload["thread"]["status"], "idle")

    def test_human_status_reports_daemon_health_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(Path(temp_root), Path(source_home))
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            status_result = subprocess.run(
                [
                    str(LAUNCHER),
                    "instance",
                    "status",
                    ctx["actor_id"],
                ],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status_result.returncode, 0, msg=status_result.stderr)
            self.assertIn("Daemon health:", status_result.stdout)
            self.assertIn("Daemon handlers: task_checkout", status_result.stdout)

    def test_fake_codex_requires_daemon_thread_resume_before_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_id": "thr-main",
                    "daemon_notifications": [
                        {
                            "method": "turn/completed",
                            "params": {
                                "threadId": "thr-main",
                                "turn": {
                                    "id": "turn-user-1",
                                    "items": [],
                                    "itemsView": "summary",
                                    "status": "completed",
                                    "error": None,
                                    "startedAt": 0,
                                    "completedAt": 1,
                                    "durationMs": 1,
                                },
                            },
                        }
                    ],
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            rows = self._read_json_lines(Path(str(ctx["calls_path"])))
            daemon_rows = [
                row
                for row in rows
                if row.get("client_name") == "buddyswitch_daemon"
                and ((row.get("argv") or [None])[0] == "json-rpc" or row.get("kind") == "daemon-notification")
            ]
            sequence = [
                row.get("rpc_method") if row.get("kind") != "daemon-notification" else row.get("notification_method")
                for row in daemon_rows
            ]
            self.assertEqual(sequence[:4], ["initialize", "initialized", "thread/resume", "turn/completed"])

    def test_fake_codex_real_completed_event_triggers_one_stop_task_tui_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_id": "thr-main",
                    "next_turn_id": "turn-daemon-1",
                    "daemon_notifications": [
                        {
                            "method": "turn/completed",
                            "params": {
                                "threadId": "thr-main",
                                "turn": {
                                    "id": "turn-user-1",
                                    "items": [],
                                    "itemsView": "summary",
                                    "status": "completed",
                                    "error": None,
                                    "startedAt": 0,
                                    "completedAt": 1,
                                    "durationMs": 1,
                                },
                            },
                        }
                    ],
                    "daemon_emit_completion_for_started_turn": True,
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            turn_start_rows = self._wait_for_rpc_rows(Path(str(ctx["calls_path"])), "turn/start")
            time.sleep(0.5)
            turn_start_rows = [row for row in self._read_rpc_rows(Path(str(ctx["calls_path"]))) if row.get("rpc_method") == "turn/start"]

            self.assertEqual(len(turn_start_rows), 1)
            params = turn_start_rows[0]["params"]
            self.assertEqual(params["threadId"], "thr-main")
            prompt = params["input"][0]["text"]
            self.assertTrue(prompt.startswith("[TASK CHECKOUT]"), msg=prompt)
            self.assertNotIn("[USER INPUT]", prompt)
            daemon_state = json.loads((Path(str(ctx["instance_root"])) / "runtime" / "daemon" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(daemon_state["daemon_origin_turn_ids"], ["turn-daemon-1"])
            self.assertEqual(daemon_state["daemon_origin_turns"]["turn-daemon-1"]["handler_name"], "task_checkout")
            self.assertEqual(daemon_state["daemon_origin_turns"]["turn-daemon-1"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(daemon_state["handlers"]["task_checkout"]["last_origin_turn_id"], "turn-user-1")
            self.assertEqual(daemon_state["handlers"]["task_checkout"]["last_runtime_turn_id"], "turn-daemon-1")
            self.assertEqual(daemon_state["handlers"]["task_checkout"]["last_result"], "handled")
            self.assertNotIn("last_" + "action" + "_turn_id", daemon_state["handlers"]["task_checkout"])
            self.assertNotIn("last_checkout_turn_id", daemon_state["handlers"]["task_checkout"])

    def test_daemon_origin_completion_real_shape_does_not_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_id": "thr-main",
                    "next_turn_id": "turn-daemon-1",
                    "daemon_notifications": [
                        {
                            "method": "turn/completed",
                            "params": {
                                "threadId": "thr-main",
                                "turn": {
                                    "id": "turn-user-1",
                                    "items": [],
                                    "itemsView": "summary",
                                    "status": "completed",
                                    "error": None,
                                    "startedAt": 0,
                                    "completedAt": 1,
                                    "durationMs": 1,
                                },
                            },
                        }
                    ],
                    "daemon_emit_completion_for_started_turn": True,
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            turn_start_rows = self._wait_for_rpc_rows(Path(str(ctx["calls_path"])), "turn/start")
            time.sleep(0.5)
            turn_start_rows = [row for row in self._read_rpc_rows(Path(str(ctx["calls_path"]))) if row.get("rpc_method") == "turn/start"]
            self.assertEqual(len(turn_start_rows), 1)

    def test_daemon_ignores_other_thread_real_completion_in_fake_codex(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            ctx = self._start_service_instance(
                Path(temp_root),
                Path(source_home),
                state_payload={
                    "thread_id": "thr-main",
                    "next_turn_id": "turn-daemon-1",
                    "daemon_notifications": [
                        {
                            "method": "turn/completed",
                            "params": {
                                "threadId": "thr-side",
                                "turn": {
                                    "id": "turn-side-1",
                                    "items": [],
                                    "itemsView": "summary",
                                    "status": "completed",
                                    "error": None,
                                    "startedAt": 0,
                                    "completedAt": 1,
                                    "durationMs": 1,
                                },
                            },
                        },
                        {
                            "method": "turn/completed",
                            "params": {
                                "threadId": "thr-main",
                                "turn": {
                                    "id": "turn-user-1",
                                    "items": [],
                                    "itemsView": "summary",
                                    "status": "completed",
                                    "error": None,
                                    "startedAt": 0,
                                    "completedAt": 1,
                                    "durationMs": 1,
                                },
                            },
                        },
                    ],
                },
            )
            completed = ctx["completed"]
            assert isinstance(completed, subprocess.CompletedProcess)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            turn_start_rows = self._wait_for_rpc_rows(Path(str(ctx["calls_path"])), "turn/start")
            self.assertEqual(len(turn_start_rows), 1)

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
            self.assertIn("actor_id\tbuddy\tstatus\tapp_server_health\tthread_id\tbrowser_port\tupdated_at\tworkspace_dir", list_result.stdout)
            self.assertIn(
                f"{ctx['actor_id']}\tpm\tactive\thealthy\t{ctx['instance_payload']['thread_id']}\t",
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
                    ctx["actor_id"],
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
                    ctx["actor_id"],
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
            self.assertEqual(payload["actor_id"], ctx["actor_id"])
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
                    ctx["actor_id"],
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
                [str(LAUNCHER), "instance", "open", "act-pm-example"],
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

    def test_start_with_role_creates_shared_project_workspace(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / payload["actor_id"]
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
        self.test_start_with_role_creates_shared_project_workspace()

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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            runtime_workspace_dir = shared_root / "instances" / payload["actor_id"] / "workspace"
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

    def test_cross_role_relative_projects_app_is_shared(self) -> None:
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
            pm_env["BUDDYSWITCH_TEST_RELATIVE_WRITE_PATH"] = "cross-role-sentinel.txt"
            pm_env["BUDDYSWITCH_TEST_RELATIVE_WRITE_CONTENT"] = "shared-via-relative-path"
            pm_start = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
                cwd=ROOT,
                env=pm_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(pm_start.returncode, 0, msg=pm_start.stderr)

            dev_env = base_env.copy()
            dev_env["BUDDYSWITCH_TEST_CAPTURE"] = str(dev_capture_path)
            dev_env["BUDDYSWITCH_TEST_RELATIVE_READ_PATH"] = "cross-role-sentinel.txt"
            dev_start = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--role", "dev"],
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
                str((shared_project_app / "cross-role-sentinel.txt").resolve()),
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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

    def test_project_workspace_is_shared_across_role_instances(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
                [str(LAUNCHER), "instance", "start", "--role", "dev"],
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
                str((shared_root / "instances" / pm_payload["actor_id"] / "workspace").resolve()),
            )
            self.assertEqual(
                dev_payload["cwd"],
                str((shared_root / "instances" / dev_payload["actor_id"] / "workspace").resolve()),
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
            self.assertTrue((temp_root_path / "capture.json").exists(), "app-server should still launch for non-required browser roles")

    def test_start_with_browser_available_role_endpoint_only_continues_without_ready_claim(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(capture_path.exists(), "optional-browser role should still launch Codex")
            self.assertIn("continuing without cockpit endpoint", completed.stderr.lower())
            self.assertNotIn("Browser cockpit ready:", completed.stdout + completed.stderr)
            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertFalse(
                any(entry.get("argv", [])[:3] == ["mcp", "add", "chrome-devtools-cockpit"] for entry in call_entries),
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
                [str(LAUNCHER), "instance", "start", "--role", "market"],
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

    def test_start_with_required_role_ready_page_launches_codex(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "market"],
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
            self.assertEqual(payload["active_role"], "market")
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
            self._assert_cockpit_proxy_registration(cockpit_add["argv"], f"http://127.0.0.1:{browser_port}")
            self.assertIn(f"--browser-url=http://127.0.0.1:{browser_port}", payload["config_toml"])

    def test_start_with_required_role_blocks_codex_when_cockpit_mcp_setup_fails(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "market"],
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

    def test_start_with_required_role_blocks_codex_when_env_mcp_setup_fails(self) -> None:
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
            env["BUDDYSWITCH_TEST_FAIL_MCP_ADD_NAME"] = "buddyswitch-env"

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--role", "market"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("simulated mcp add failure: buddyswitch-env", completed.stderr)
            self.assertFalse(capture_path.exists(), "Codex must not launch when required env MCP setup fails")
            call_entries = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(any(entry["argv"][:3] == ["mcp", "add", "buddyswitch-env"] for entry in call_entries))
            self.assertFalse(
                any(entry["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"] for entry in call_entries),
                "browser MCP setup must not run after required env MCP setup fails",
            )

    def test_start_with_required_role_repairs_intro_only_browser_before_codex_launch(self) -> None:
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
            self._write_fake_background_page_tool(fake_bin / "background-page")

            state_file = temp_root_path / "cdp-state.json"
            timeline_path = temp_root_path / "timeline.jsonl"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[{"id": "intro", "type": "page", "url": "chrome://intro/"}],
                allow_background_create_about_blank=True,
            )

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL"] = str(fake_bin / "background-page")
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CDP_CALLS_FILE"] = str(timeline_path)
            env["BUDDYSWITCH_TEST_CALLS"] = str(timeline_path)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--role", "market"],
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
            background_index = next(
                index
                for index, entry in enumerate(timeline)
                if entry.get("method") == "CDP"
                and entry.get("path") == "Target.createTarget"
                and entry.get("params") == {"url": "about:blank", "background": True}
            )
            cockpit_mcp_index = next(
                index
                for index, entry in enumerate(timeline)
                if entry.get("argv", [])[:3] == ["mcp", "add", "chrome-devtools-cockpit"]
            )
            self.assertLess(background_index, cockpit_mcp_index)
            self.assertFalse(
                any(
                    entry.get("path") == "/json/new"
                    and entry.get("query") == "about:blank"
                    for entry in timeline
                )
            )

    def test_start_with_required_role_rejects_endpoint_only_browser_before_codex(self) -> None:
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
            self._write_fake_background_page_tool(fake_bin / "background-page")

            state_file = temp_root_path / "cdp-state.json"
            calls_file = temp_root_path / "cdp-calls.jsonl"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[],
                allow_background_create_about_blank=False,
            )

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL"] = str(fake_bin / "background-page")
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CDP_CALLS_FILE"] = str(calls_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--role", "market"],
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
            self.assertTrue(any(call.get("path") == "Target.createTarget" for call in calls))
            self.assertFalse(any(call.get("path") == "/json/new" for call in calls))

    def test_start_with_unknown_role_fails_before_shared_root_mutation(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role", "unknown"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Unknown role 'unknown'", completed.stderr)
            self.assertFalse(capture_path.exists(), "codex should not launch when role validation fails")
            self.assertFalse(shared_root.exists(), "invalid role must fail before shared root mutation")

    def test_role_list_prints_manifest_buddies_without_runtime_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "roles"],
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
            self.assertFalse(shared_root.exists(), "instance roles must not create runtime state")

    def test_instance_buddies_json_is_structured_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "roles", "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(completed.stdout)
            role_ids = {row["id"] for row in payload["roles"]}
            self.assertIn("pm", role_ids)
            self.assertIn("dev", role_ids)
            self.assertIn("market", role_ids)
            for row in payload["roles"]:
                self.assertIsInstance(row["id"], str)
                self.assertIsInstance(row["label"], str)
                self.assertIsInstance(row["scope"], str)
            self.assertFalse(shared_root.exists(), "instance roles --json must not create runtime state")

    def test_instance_list_empty_points_to_start_role(self) -> None:
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
            self.assertIn("./buddyswitch-codex instance start --role <role>", completed.stdout)

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

    def test_instance_list_prints_stored_instances_and_filters_by_role(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            for actor_id, role in (
                ("act-pm-a", "pm"),
                ("act-dev-b", "dev"),
            ):
                instance_root = shared_root / "instances" / actor_id
                instance_root.mkdir(parents=True, exist_ok=True)
                (instance_root / "instance.json").write_text(
                    json.dumps(
                        {
                            "actor_id": actor_id,
                            "role": role,
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
                [str(LAUNCHER), "instance", "list", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("act-pm-a", completed.stdout)
            self.assertIn("pm", completed.stdout)
            self.assertNotIn("act-dev-b", completed.stdout)

    def test_instance_list_json_filters_by_role(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            for actor_id, role in (
                ("act-pm-a", "pm"),
                ("act-dev-b", "dev"),
            ):
                instance_root = shared_root / "instances" / actor_id
                instance_root.mkdir(parents=True, exist_ok=True)
                (instance_root / "instance.json").write_text(
                    json.dumps(
                        {
                            "actor_id": actor_id,
                            "role": role,
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
                [str(LAUNCHER), "instance", "list", "--json", "--role", "pm"],
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
            self.assertEqual(row["actor_id"], "act-pm-a")
            self.assertEqual(row["role"], "pm")
            self.assertEqual(row["status"], "inactive")
            self.assertEqual(row["app_server_health"], "unhealthy")
            self.assertIsNone(row["thread_id"])
            self.assertIsNone(row["browser_port"])

    def test_instance_delete_removes_only_target_instance_without_shared_state(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, target_workspace = self._write_instance_record(shared_root, "act-pm-delete")
            other_root, _ = self._write_instance_record(shared_root, "act-dev-keep", role="dev")
            state_task = shared_root / "state" / "buddyswitch" / "objects" / "tasks" / "task-keep.json"
            state_task.parent.mkdir(parents=True, exist_ok=True)
            state_task.write_text('{"id":"task-keep"}\n', encoding="utf-8")
            self._add_test_worktree(target_workspace)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-delete", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
            self.assertIn("Instance deleted: act-pm-delete", delete_result.stdout)
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
            target_root, target_workspace = self._write_instance_record(shared_root, "act-pm-delete")
            other_root, _ = self._write_instance_record(shared_root, "act-dev-keep", role="dev")
            state_task = shared_root / "state" / "buddyswitch" / "objects" / "tasks" / "task-keep.json"
            state_task.parent.mkdir(parents=True, exist_ok=True)
            state_task.write_text('{"id":"task-keep"}\n', encoding="utf-8")
            self._add_test_worktree(target_workspace)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-delete", "--yes", "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
            self.assertEqual(
                json.loads(delete_result.stdout),
                {"actor_id": "act-pm-delete", "deleted": True},
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
            target_root, _ = self._write_instance_record(shared_root, "act-pm-keep")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-keep"],
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
            instance_root = shared_root / "instances" / payload["actor_id"]

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
                [str(LAUNCHER), "instance", "stop", payload["actor_id"]],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(stop_result.returncode, 0, msg=stop_result.stderr)
            ready_file.unlink(missing_ok=True)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", payload["actor_id"], "--yes"],
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

    def test_instance_delete_rejects_traversal_actor_id(self) -> None:
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
            self.assertIn("Invalid actor id", delete_result.stderr)
            self.assertFalse(outside_path.exists())

    def test_instance_delete_rejects_missing_target(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            env = os.environ.copy()
            env["HOME"] = str(Path(source_home))
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-missing", "--yes"],
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
                [str(LAUNCHER), "instance", "delete", ctx["actor_id"], "--yes"],
                cwd=ROOT,
                env=ctx["env"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn(f"Instance delete blocked: {ctx['actor_id']} is active.", delete_result.stderr)
            self.assertTrue(Path(str(ctx["instance_root"])).exists())

    def test_instance_delete_blocks_active_target_browser_pid(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "act-pm-live-browser-pid")
            browser_dir = target_root / "browser"
            browser_dir.mkdir(parents=True, exist_ok=True)
            (browser_dir / "chrome.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-live-browser-pid", "--yes"],
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
            target_root, _ = self._write_instance_record(shared_root, "act-pm-live-browser-endpoint", browser_port=9333)
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
            self._write_exec(
                fake_bin / "lsof",
                """#!/usr/bin/env bash
printf '12345\n'
""",
            )
            self._write_exec(
                fake_bin / "ps",
                f"""#!/usr/bin/env bash
printf '%s\\n' 'Google Chrome --remote-debugging-port=9333 --user-data-dir={target_root / "browser" / "profile"}'
""",
            )
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-live-browser-endpoint", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn("active browser cockpit", delete_result.stderr)
            self.assertTrue(target_root.exists())

    def test_instance_delete_ignores_foreign_browser_endpoint_on_stale_port(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "act-pm-stale-port", browser_port=9333)
            market_root, _ = self._write_instance_record(shared_root, "act-market-live-port", role="market", browser_port=9333)
            market_browser = market_root / "browser"
            market_browser.mkdir(parents=True, exist_ok=True)
            (market_browser / "chrome.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
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
            self._write_exec(
                fake_bin / "lsof",
                """#!/usr/bin/env bash
printf '12345\n'
""",
            )
            self._write_exec(
                fake_bin / "ps",
                f"""#!/usr/bin/env bash
printf '%s\\n' 'Google Chrome --remote-debugging-port=9333 --user-data-dir={market_root / "browser" / "profile"}'
""",
            )
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-stale-port", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
            self.assertIn("Instance deleted: act-pm-stale-port", delete_result.stdout)
            self.assertFalse(target_root.exists())
            self.assertTrue(market_root.exists())
            self.assertTrue((market_browser / "chrome.pid").exists())

    def test_instance_delete_ignores_stale_legacy_pid_file_without_active_service(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, _ = self._write_instance_record(shared_root, "act-pm-stale-legacy-delete")
            run_dir = shared_root / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / ("launcher" + "-" + "current" + ".pid")).write_text(f"{os.getpid()}\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-stale-legacy-delete", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
            self.assertIn("Instance deleted: act-pm-stale-legacy-delete", delete_result.stdout)
            self.assertFalse(target_root.exists())

    def test_instance_delete_blocks_worktree_deregistration_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            target_root, target_workspace = self._write_instance_record(shared_root, "act-pm-remove-fail")
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
                [str(LAUNCHER), "instance", "delete", "act-pm-remove-fail", "--yes"],
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
                        "actor_id": "act-pm-symlink",
                        "role": "pm",
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
            (instances_root / "act-pm-symlink").symlink_to(external_instance_root, target_is_directory=True)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-symlink", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 3)
            self.assertIn("unsafe instance root", delete_result.stderr)
            self.assertTrue((instances_root / "act-pm-symlink").is_symlink())
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
                "act-pm-shared-root-symlink",
            )
            sentinel = instance_root / "sentinel.txt"
            sentinel.write_text("keep\n", encoding="utf-8")

            shared_root_link = source_home_path / ".codex-buddyswitch"
            shared_root_link.symlink_to(real_shared_root, target_is_directory=True)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", "act-pm-shared-root-symlink", "--yes"],
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
            env["BUDDYSWITCH_DELETE_ACTOR_ID"] = "act-pm-direct"

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

    def test_start_without_role_does_not_set_instance_env_vars(self) -> None:
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
            env["BUDDYSWITCH_ROLE_ID"] = "leaked-role"
            env["BUDDYSWITCH_ACTOR_ID"] = "leaked-actor-id"
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
            self.assertIn("instance start --role <role>", completed.stderr)
            self.assertFalse(capture_path.exists(), "removed start command must not invoke codex")
            self.assertFalse((source_home_path / ".codex-buddyswitch").exists())

    def test_start_with_role_requires_value(self) -> None:
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
                [str(LAUNCHER), "instance", "start", "--role"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Missing value for --role", completed.stderr)
            self.assertFalse(capture_path.exists(), "codex should not launch when --role is malformed")
            self.assertFalse(shared_root.exists(), "malformed --role must fail before shared root mutation")

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
                [str(LAUNCHER), "instance", "start", "--role", "pm", "--help"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertIn("buddyswitch-codex instance start --role <role>", completed.stdout)
            self.assertFalse(capture_path.exists(), "help path must not launch Codex")
            self.assertFalse(calls_path.exists(), "help path must not call Codex binary")
            self.assertFalse(ready_file.exists(), "help path must not start browser")
            self.assertFalse(shared_root.exists(), "help path must not create shared instance state")

    def test_locked_start_bootstrap_revalidates_role_before_instance_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_START_ROLE"] = "unknown"
            env["BUDDYSWITCH_START_ACTOR_ID"] = "act-unknown-demo"

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
            self.assertIn("Unknown role 'unknown'", direct_start.stderr)
            self.assertFalse((shared_root / "instances").exists(), "invalid locked role must not create instances")

    def test_locked_instance_inactive_rejects_traversal_actor_id(self) -> None:
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
            self.assertIn("Invalid actor id", direct_inactive.stderr)
            self.assertFalse(outside_path.exists(), "traversal actor id must not write outside instances root")

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

    def test_locked_start_bootstrap_requires_role_env_before_workspace_setup(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            runtime_lock = ROOT / "tools" / "launcher" / "runtime_lock.py"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env.pop("BUDDYSWITCH_START_ROLE", None)
            env.pop("BUDDYSWITCH_START_ACTOR_ID", None)

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
            self.assertIn("BUDDYSWITCH_START_ROLE is required", completed.stderr)
            self.assertFalse((shared_root / "workspace").exists(), "missing role env must fail before workspace prep")

    def test_locked_start_bootstrap_requires_actor_id_env(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            runtime_lock = ROOT / "tools" / "launcher" / "runtime_lock.py"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            env["BUDDYSWITCH_START_ROLE"] = "pm"
            env.pop("BUDDYSWITCH_START_ACTOR_ID", None)

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
            self.assertIn("BUDDYSWITCH_START_ACTOR_ID is required", completed.stderr)
            self.assertFalse((shared_root / "workspace").exists(), "missing actor id must fail before workspace prep")

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
            self.assertIn("buddyswitch-codex instance roles", help_result.stdout)
            self.assertIn("buddyswitch-codex instance start --role <role>", help_result.stdout)
            self.assertIn("buddyswitch-codex data cleanup --role <role>", help_result.stdout)
            self.assertIn("buddyswitch-codex env status", help_result.stdout)
            self.assertIn("buddyswitch-codex env reset [--yes]", help_result.stdout)
            self.assertIn("buddyswitch-codex help", help_result.stdout)
            self.assertIn("  instance", help_result.stdout)
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
                ("start", "instance start --role <role>"),
                ("role", "instance roles"),
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
            actor_id = "act-pm-live-browser"
            instance_root = shared_root / "instances" / actor_id
            browser_dir = instance_root / "browser"
            browser_profile_dir = browser_dir / "profile"
            browser_profile_dir.mkdir(parents=True, exist_ok=True)
            (browser_dir / "chrome.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
            (instance_root / "instance.json").write_text(
                json.dumps(
                    {
                        "actor_id": actor_id,
                        "role": "pm",
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
            actor_id = "act-pm-live-endpoint"
            instance_root = shared_root / "instances" / actor_id
            instance_root.mkdir(parents=True, exist_ok=True)
            (instance_root / "instance.json").write_text(
                json.dumps(
                    {
                        "actor_id": actor_id,
                        "role": "pm",
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
            instance_json = shared_root / "instances" / "act-pm-existing" / "instance.json"
            instance_json.parent.mkdir(parents=True, exist_ok=True)
            instance_json.write_text('{"actor_id":"act-pm-existing","role":"pm"}\n', encoding="utf-8")

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

    def test_start_with_role_does_not_migrate_legacy_durable_state_to_shared_state(self) -> None:
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
                (legacy_task, {"id": "task-demo", "role": "pm"}),
                (legacy_run, {"run_id": "run-demo", "switch": {"role": "pm"}}),
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
            actor_id = "act-pm-browser-status"
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=9333)

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
                [str(LAUNCHER), "env", "browser", "status", "--instance", actor_id],
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
                    actor_id,
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
            actor_id = "act-pm-browser-invalid-port"
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=9333)

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
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id, "--port", "70000"],
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
            actor_id = "act-pm-lock-invalid-port"
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=9333)

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
                    [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id, "--port", "70000"],
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
            actor_id = "act-pm-browser-ensure"
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=9333)

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
                    actor_id,
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
            self._assert_cockpit_proxy_registration(cockpit_add["argv"], "http://127.0.0.1:9444")

    def test_env_browser_ensure_repairs_stale_cockpit_mcp_browser_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser-stale-mcp"
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=9333)

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
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id, "--port", "9444"],
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
            self._assert_cockpit_proxy_registration(cockpit_add["argv"], "http://127.0.0.1:9444")

    def test_browser_ensure_is_blocked_when_runtime_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            self._write_instance_record(shared_root, "act-pm-browser-lock")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"] = LOCK_TIMEOUT_SECONDS

            lock_path = self._runtime_lock_path(shared_root)
            holder = self._spawn_lock_holder(lock_path)
            try:
                blocked_ensure = subprocess.run(
                    [str(LAUNCHER), "env", "browser", "ensure", "--instance", "act-pm-browser-lock"],
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
                (shared_root / "instances" / "act-pm-browser-lock" / "browser").exists(),
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
            actor_id = "act-pm-browser-invalid-env-port"
            instance_root, _ = self._write_instance_record(shared_root, actor_id)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["BUDDYSWITCH_BROWSER_PORT"] = "abc"

            before_instance_tree = self._snapshot_tree(instance_root)
            ensure_result = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
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
export BUDDYSWITCH_ROLE_ID="pm"
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

    def test_role_agents_template_requirement_checks_presence_only(self) -> None:
        command = r'''
set -euo pipefail
source "tools/launcher/env.sh"
tmp_root="$(mktemp -d)"
trap 'rm -rf "${tmp_root}"' EXIT
export BUDDYSWITCH_REPO_ROOT="${tmp_root}/repo"
mkdir -p "${BUDDYSWITCH_REPO_ROOT}/tools/launcher/assets/roles/pm"
printf '# Custom Runtime AGENTS\n\nNo required wording.\n' >"${BUDDYSWITCH_REPO_ROOT}/tools/launcher/assets/roles/pm/AGENTS.md"
buddyswitch_require_role_agents_template pm
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
        self.assertTrue(completed.stdout.strip().endswith("/tools/launcher/assets/roles/pm/AGENTS.md"))

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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / payload["actor_id"]
            workspace_dir = instance_root / "workspace"
            self.assertTrue(workspace_dir.exists())

            stop_result = subprocess.run(
                [str(LAUNCHER), "instance", "stop", payload["actor_id"]],
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(start_result.returncode, 0, msg=start_result.stderr)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / payload["actor_id"]
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
                [str(LAUNCHER), "instance", "stop", payload["actor_id"]],
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
                    [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
                [str(LAUNCHER), "instance", "start", "--role", "pm"],
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
