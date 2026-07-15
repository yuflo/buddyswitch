"""Regression tests for the BuddySwitch root launcher."""

from __future__ import annotations

from contextlib import ExitStack
import json
import os
import errno
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from runtime_kernel import process_identity
from tests.process.launcher._harness import ProcessLauncherHarness
from tests.support.paths import REPO_ROOT
from tests.support.processes import run_process
from tests.support.python import PYTHON
from tests.support.cli import write_executable

ROOT = REPO_ROOT
LAUNCHER = ROOT / "buddyswitch-codex"
LOCK_TIMEOUT_SECONDS = "0.2"


class TestBrowserCommands(ProcessLauncherHarness, unittest.TestCase):
    def test_env_browser_status_instance_defaults_and_explicit_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser-status"
            default_port = self._first_available_browser_port()
            if default_port is None:
                self.skipTest("no browser cockpit port is available in range 9222..9321")
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=default_port)

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            def start_fake_cdp(port: int, profile_dir: Path) -> subprocess.Popen[str]:
                fake_env = os.environ.copy()
                fake_env["BUDDYSWITCH_TEST_FAKE_CHROME_SERVE_CDP"] = "1"
                proc = self._ledger.start_process(
                    [
                        str(fake_bin / "fake-chrome"),
                        f"--remote-debugging-port={port}",
                        f"--user-data-dir={profile_dir}",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "about:blank",
                    ],
                    env=fake_env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.addCleanup(self._cleanup_popen, proc)
                deadline = time.time() + 3.0
                while self._tcp_port_is_available(port) and time.time() < deadline:
                    time.sleep(0.05)
                if self._tcp_port_is_available(port):
                    self.skipTest(f"fake CDP endpoint did not start on {port}")
                return proc

            start_fake_cdp(default_port, instance_root / "browser" / "profile")
            explicit_port = None
            for candidate in range(9222, 9322):
                if candidate != default_port and self._tcp_port_is_available(candidate):
                    explicit_port = candidate
                    break
            if explicit_port is None:
                self.skipTest("no second browser cockpit port is available in range 9222..9321")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            status_default = run_process(
                [str(LAUNCHER), "env", "browser", "status", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_default.returncode, 0, msg=self._output_error_text(status_default))
            status_default_data = self._cli_success_data(status_default, kind="env.browser.status")
            self.assertEqual(status_default_data["browser_url"], f"http://127.0.0.1:{default_port}")  # type: ignore[index]
            self.assertEqual(status_default_data["profile_dir"], str(instance_root / "browser" / "profile"))  # type: ignore[index]
            self.assertEqual(status_default_data["message"], f"Browser cockpit ready: http://127.0.0.1:{default_port}")  # type: ignore[index]

            explicit_profile = temp_root_path / "browser-profile-status"
            start_fake_cdp(explicit_port, explicit_profile)
            status_explicit = run_process(
                [
                    str(LAUNCHER),
                    "env",
                    "browser",
                    "status",
                    "--instance",
                    actor_id,
                    "--port",
                    str(explicit_port),
                    "--profile-dir",
                    str(explicit_profile),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_explicit.returncode, 0, msg=self._output_error_text(status_explicit))
            status_explicit_data = self._cli_success_data(status_explicit, kind="env.browser.status")
            self.assertEqual(status_explicit_data["browser_url"], f"http://127.0.0.1:{explicit_port}")  # type: ignore[index]
            self.assertEqual(status_explicit_data["profile_dir"], str(explicit_profile))  # type: ignore[index]
            self.assertEqual(status_explicit_data["message"], f"Browser cockpit ready: http://127.0.0.1:{explicit_port}")  # type: ignore[index]

            instance_json = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_json["browser_port"], default_port)
    def test_env_browser_status_without_instance_reports_not_ready_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            port = self._first_available_browser_port()
            if port is None:
                self.skipTest("no browser cockpit port is available in range 9222..9321")

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_curl(fake_bin / "curl")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            completed = run_process(
                [str(LAUNCHER), "env", "browser", "status", "--port", str(port)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=self._output_error_text(completed))
            data = self._cli_success_data(completed, kind="env.browser.status")
            self.assertIsInstance(data, dict)
            assert isinstance(data, dict)
            self.assertEqual(data["ok"], True)
            self.assertEqual(data["ready"], False)
            self.assertEqual(data["browser_url"], f"http://127.0.0.1:{port}")
            self.assertEqual(data["browser_port"], port)
            self.assertEqual(data["durability"], "none")
            self.assertEqual(data["state_changed"], False)
    def test_env_browser_status_rejects_invalid_port_before_endpoint_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            write_executable(
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

            status_invalid_port = run_process(
                [str(LAUNCHER), "env", "browser", "status", "--port", "abc"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status_invalid_port.returncode, 2)
            self.assertIn("Invalid value for --port: abc", self._output_error_text(status_invalid_port))
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
            write_executable(
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

            ensure_invalid_port = run_process(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id, "--port", "70000"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ensure_invalid_port.returncode, 2)
            self.assertIn("Invalid value for --port: 70000", self._output_error_text(ensure_invalid_port))
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
            write_executable(
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
                ensure_invalid_port = run_process(
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
            self.assertIn("Invalid value for --port: 70000", self._output_error_text(ensure_invalid_port))
            self.assertNotIn("runtime state busy", self._output_error_text(ensure_invalid_port))
            self.assertFalse(curl_called_path.exists(), "invalid --port must fail before endpoint checks")
            self.assertFalse(
                (instance_root / "browser").exists(),
                "invalid --port must fail before browser profile/bootstrap side effects",
            )
    def test_env_browser_ensure_allocates_when_instance_port_missing_and_default_busy(self) -> None:
        busy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            busy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            busy_socket.bind(("127.0.0.1", 9222))
            busy_socket.listen(1)
            self.addCleanup(busy_socket.close)
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                busy_socket.close()
            else:
                busy_socket.close()
                self.skipTest(f"port 9222 is not available for the busy-port precondition: {exc}")
        expected_port = self._first_available_browser_port()
        if expected_port is None:
            self.skipTest("no browser cockpit port is available in range 9222..9321")

        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser-missing-port"
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=None)

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
            chrome_argv_path = temp_root_path / "chrome-argv.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_CHROME_ARGV_FILE"] = str(chrome_argv_path)
            env["BUDDYSWITCH_TEST_FAKE_CHROME_SERVE_CDP"] = "1"

            descriptor_id = self._register_browser_process_descriptor(instance_root, actor_id)
            cleanup.callback(self._cleanup_process_descriptor, descriptor_id)
            ensure_result = run_process(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ensure_result.returncode, 0, msg=self._output_error_text(ensure_result))

            instance_json = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_json["browser_port"], expected_port)
            self.assertNotEqual(instance_json["browser_port"], 9222)
            chrome_argv = [
                json.loads(line)
                for line in chrome_argv_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(chrome_argv), 1)
            self.assertIn(f"--remote-debugging-port={expected_port}", chrome_argv[0])
            self.assertIn(f"--user-data-dir={instance_root / 'browser' / 'profile'}", chrome_argv[0])
    def test_env_browser_ensure_reallocates_foreign_recorded_port(self) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            foreign_port = self._first_available_browser_port()
            if foreign_port is None:
                self.skipTest("no browser cockpit port is available in range 9222..9321")
            actor_id = "act-pm-foreign-browser-port"
            foreign_actor_id = "act-market-foreign-browser-owner"
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=foreign_port)
            foreign_root, _ = self._write_instance_record(shared_root, foreign_actor_id, role="market", browser_port=foreign_port)
            foreign_browser = foreign_root / "browser"
            foreign_browser.mkdir(parents=True, exist_ok=True)

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
            self._write_fake_chrome(fake_bin / "fake-chrome")
            foreign_env = os.environ.copy()
            foreign_env["BUDDYSWITCH_TEST_FAKE_CHROME_SERVE_CDP"] = "1"
            foreign_proc = self._ledger.start_process(
                [
                    str(fake_bin / "fake-chrome"),
                    f"--remote-debugging-port={foreign_port}",
                    f"--user-data-dir={foreign_root / 'browser' / 'profile'}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "about:blank",
                ],
                env=foreign_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.addCleanup(self._cleanup_popen, foreign_proc)
            (foreign_browser / "chrome.pid").write_text(f"{foreign_proc.pid}\n", encoding="utf-8")
            deadline = time.time() + 3.0
            while self._tcp_port_is_available(foreign_port) and time.time() < deadline:
                time.sleep(0.05)
            if self._tcp_port_is_available(foreign_port):
                self.skipTest(f"foreign browser endpoint did not start on {foreign_port}")

            ready_file = temp_root_path / "browser-ready.flag"
            calls_path = temp_root_path / "calls.jsonl"
            chrome_argv_path = temp_root_path / "chrome-argv.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_CHROME_ARGV_FILE"] = str(chrome_argv_path)
            env["BUDDYSWITCH_TEST_FAKE_CHROME_SERVE_CDP"] = "1"

            descriptor_id = self._register_browser_process_descriptor(instance_root, actor_id)
            cleanup.callback(self._cleanup_process_descriptor, descriptor_id)
            ensure_result = run_process(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ensure_result.returncode, 0, msg=self._output_error_text(ensure_result))

            instance_json = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertIsInstance(instance_json["browser_port"], int)
            self.assertNotEqual(instance_json["browser_port"], foreign_port)
            chrome_argv = [
                json.loads(line)
                for line in chrome_argv_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(chrome_argv), 1)
            self.assertIn(f"--remote-debugging-port={instance_json['browser_port']}", chrome_argv[0])
            self.assertNotIn(f"--remote-debugging-port={foreign_port}", chrome_argv[0])
            self.assertTrue((foreign_browser / "chrome.pid").exists())
    def test_env_browser_release_cleans_owned_runtime_state(self) -> None:
        upstream_proc = self._ledger.start_process(["sleep", "60"])
        upstream_pgid = os.getpgid(upstream_proc.pid)
        self.addCleanup(self._terminate_registered_process, upstream_proc.pid, upstream_pgid)

        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser-release"
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=9333)
            profile_dir = instance_root / "browser" / "profile"
            chrome_proc = self._ledger.start_process(
                [
                    PYTHON,
                    "-c",
                    "import time; time.sleep(60)",
                    "--remote-debugging-port=9333",
                    f"--user-data-dir={profile_dir}",
                ],
            )
            chrome_pgid = os.getpgid(chrome_proc.pid)
            self.addCleanup(self._terminate_registered_process, chrome_proc.pid, chrome_pgid)
            browser_dir = instance_root / "browser"
            runtime_browser_dir = instance_root / "runtime" / "browser"
            browser_dir.mkdir(parents=True, exist_ok=True)
            runtime_browser_dir.mkdir(parents=True, exist_ok=True)
            process_identity.write_record(browser_dir / "chrome.pid", chrome_proc.pid)
            process_identity.write_record(
                runtime_browser_dir / "cockpit-upstream.pid",
                upstream_proc.pid,
            )
            (runtime_browser_dir / "cockpit-upstream.pgid").write_text(f"{upstream_pgid}\n", encoding="utf-8")
            (runtime_browser_dir / "page_idle.json").write_text(
                json.dumps({"targets": {}}, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            (runtime_browser_dir / "page_idle.lock").write_text("", encoding="utf-8")

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            write_executable(
                fake_bin / "curl",
                """#!/usr/bin/env bash
for arg in "$@"; do
  if [[ "${arg}" == "http://127.0.0.1:9333/json/version" ]]; then
    printf '{"Browser":"test"}\n'
    exit 0
  fi
done
exit 22
""",
            )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            release_result = run_process(
                [str(LAUNCHER), "env", "browser", "release", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(release_result.returncode, 0, msg=self._output_error_text(release_result))
            upstream_proc.wait(timeout=2)
            chrome_proc.wait(timeout=2)
            self.assertFalse((runtime_browser_dir / "cockpit-upstream.pid").exists())
            self.assertFalse((runtime_browser_dir / "cockpit-upstream.pgid").exists())
            self.assertFalse((browser_dir / "chrome.pid").exists())
            self.assertFalse((runtime_browser_dir / "page_idle.json").exists())
            self.assertFalse((runtime_browser_dir / "page_idle.lock").exists())
            instance_json = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertIsNone(instance_json["browser_port"])
    def test_env_browser_release_clears_foreign_endpoint_port_without_killing_foreign(self) -> None:
        foreign_proc = self._ledger.start_process(["sleep", "60"])
        foreign_pgid = os.getpgid(foreign_proc.pid)
        self.addCleanup(self._terminate_registered_process, foreign_proc.pid, foreign_pgid)

        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser-release-foreign"
            foreign_actor_id = "act-market-browser-release-owner"
            instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=9333)
            foreign_root, _ = self._write_instance_record(shared_root, foreign_actor_id, role="market", browser_port=9333)
            foreign_browser = foreign_root / "browser"
            foreign_browser.mkdir(parents=True, exist_ok=True)
            (foreign_browser / "chrome.pid").write_text(f"{foreign_proc.pid}\n", encoding="utf-8")

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            write_executable(
                fake_bin / "curl",
                """#!/usr/bin/env bash
for arg in "$@"; do
  if [[ "${arg}" == "http://127.0.0.1:9333/json/version" ]]; then
    printf '{"Browser":"test"}\n'
    exit 0
  fi
done
exit 22
""",
            )
            write_executable(
                fake_bin / "lsof",
                f"""#!/usr/bin/env bash
printf '%s\\n' '{foreign_proc.pid}'
""",
            )
            write_executable(
                fake_bin / "ps",
                f"""#!/usr/bin/env bash
printf '%s\\n' 'Google Chrome --remote-debugging-port=9333 --user-data-dir={foreign_root / "browser" / "profile"}'
""",
            )

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

            release_result = run_process(
                [str(LAUNCHER), "env", "browser", "release", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(release_result.returncode, 0, msg=self._output_error_text(release_result))
            self.assertTrue(self._pid_is_live(foreign_proc.pid))
            self.assertTrue((foreign_browser / "chrome.pid").exists())
            actor_payload = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            foreign_payload = json.loads((foreign_root / "instance.json").read_text(encoding="utf-8"))
            self.assertIsNone(actor_payload["browser_port"])
            self.assertEqual(foreign_payload["browser_port"], 9333)
            self._terminate_registered_process(foreign_proc.pid, foreign_pgid)
            foreign_proc.wait(timeout=2)
    def test_env_browser_ensure_instance_explicit_overrides_profile_and_updates_port(self) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
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
            env["BUDDYSWITCH_TEST_FAKE_CHROME_SERVE_CDP"] = "1"

            descriptor_id = self._register_browser_process_descriptor(
                instance_root,
                actor_id,
                profile_dir=explicit_profile,
            )
            cleanup.callback(self._cleanup_process_descriptor, descriptor_id)
            ensure_result = run_process(
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
            self.assertEqual(ensure_result.returncode, 0, msg=self._output_error_text(ensure_result))
            ensure_data = self._cli_success_data(ensure_result, kind="env.browser.ensure")
            self.assertEqual(ensure_data["browser_url"], "http://127.0.0.1:9444")  # type: ignore[index]
            self.assertEqual(ensure_data["profile_dir"], str(explicit_profile))  # type: ignore[index]
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
            ] if calls_path.exists() else []
            self.assertFalse(
                any(entry["argv"][:2] in (["mcp", "add"], ["mcp", "remove"]) for entry in call_entries),
                msg=call_entries,
            )
    def test_env_browser_ensure_does_not_repair_stale_cockpit_mcp_browser_url(self) -> None:
        with ExitStack() as cleanup:
            temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
            source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
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
command = "/stale/runtime/python"
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
            env["BUDDYSWITCH_TEST_FAKE_CHROME_SERVE_CDP"] = "1"

            descriptor_id = self._register_browser_process_descriptor(instance_root, actor_id)
            cleanup.callback(self._cleanup_process_descriptor, descriptor_id)
            ensure_result = run_process(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id, "--port", "9444"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ensure_result.returncode, 0, msg=self._output_error_text(ensure_result))

            instance_json = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
            self.assertEqual(instance_json["browser_port"], 9444)

            call_entries = (
                [
                    json.loads(line)
                    for line in calls_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                if calls_path.exists()
                else []
            )
            self.assertFalse(
                any(entry["argv"][:2] in (["mcp", "add"], ["mcp", "remove"]) for entry in call_entries),
                msg=call_entries,
            )
            config_text = (instance_codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn("--browser-url=http://127.0.0.1:9333", config_text)
    def test_env_browser_ensure_does_not_repair_cockpit_mcp_missing_or_wrong_instance_root(self) -> None:
        proxy_path = ROOT / "tools" / "launcher" / "chrome_devtools_cockpit_proxy.py"
        cases = {
            "missing": [
                str(proxy_path),
                "--upstream-command",
                "npx chrome-devtools-mcp@1.1.1",
                "--browser-url=http://127.0.0.1:9444",
            ],
            "mismatched": [
                str(proxy_path),
                "--upstream-command",
                "npx chrome-devtools-mcp@1.1.1",
                "--browser-url=http://127.0.0.1:9444",
                "--instance-root=/tmp/buddyswitch-other-instance",
            ],
        }
        for name, existing_args in cases.items():
            with self.subTest(name=name), ExitStack() as cleanup:
                temp_root = cleanup.enter_context(tempfile.TemporaryDirectory())
                source_home = cleanup.enter_context(tempfile.TemporaryDirectory())
                temp_root_path = Path(temp_root)
                source_home_path = Path(source_home)
                shared_root = source_home_path / ".codex-buddyswitch"
                actor_id = f"act-pm-browser-instance-root-{name}"
                instance_root, _ = self._write_instance_record(shared_root, actor_id, browser_port=9444)

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
                    f"""[mcp_servers.chrome-devtools-cockpit]
command = "/stale/runtime/python"
args = {json.dumps(existing_args)}
""",
                    encoding="utf-8",
                )

                fake_bin = temp_root_path / "bin"
                fake_bin.mkdir(parents=True, exist_ok=True)
                self._write_fake_codex(fake_bin / "codex")
                self._write_fake_curl(fake_bin / "curl")
                self._write_fake_chrome(fake_bin / "fake-chrome")

                ready_file = temp_root_path / "browser-ready.flag"
                calls_path = temp_root_path / "calls.jsonl"

                env = os.environ.copy()
                env["HOME"] = str(source_home_path)
                env.pop("CODEX_HOME", None)
                env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
                env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
                env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
                env["BUDDYSWITCH_TEST_CALLS"] = str(calls_path)
                env["BUDDYSWITCH_TEST_FAKE_CHROME_SERVE_CDP"] = "1"

                descriptor_id = self._register_browser_process_descriptor(instance_root, actor_id)
                cleanup.callback(self._cleanup_process_descriptor, descriptor_id)
                ensure_result = run_process(
                    [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id, "--port", "9444"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(ensure_result.returncode, 0, msg=self._output_error_text(ensure_result))

                call_entries = [
                    json.loads(line)
                    for line in calls_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ] if calls_path.exists() else []
                self.assertFalse(
                    any(entry["argv"][:2] in (["mcp", "add"], ["mcp", "remove"]) for entry in call_entries),
                    msg=call_entries,
                )
                config_text = (instance_codex_home / "config.toml").read_text(encoding="utf-8")
                for existing_arg in existing_args:
                    self.assertIn(existing_arg, config_text)
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
                blocked_ensure = run_process(
                    [str(LAUNCHER), "env", "browser", "ensure", "--instance", "act-pm-browser-lock"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                self._stop_lock_holder(holder)

            self.assertEqual(blocked_ensure.returncode, 4)
            self._cli_error(blocked_ensure, code="CONFLICT")
            self.assertIn("runtime state busy", self._output_error_text(blocked_ensure))
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

            direct_ensure = run_process(
                [str(LAUNCHER), "__" + "locked-browser-ensure"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_ensure.returncode, 2)
            self._cli_error(direct_ensure, code="UNKNOWN_COMMAND")
            self.assertIn("Unknown top-level command: __" + "locked-browser-ensure", self._output_error_text(direct_ensure))
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
            ensure_result = run_process(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            after_instance_tree = self._snapshot_tree(instance_root)

            self.assertEqual(ensure_result.returncode, 2)
            self.assertIn("Invalid value for BUDDYSWITCH_BROWSER_PORT: abc", self._output_error_text(ensure_result))
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
    def test_env_browser_missing_instance_emits_not_found_without_helper_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            cases = (
                ["status", "--instance", "act-pm-missing-browser"],
                ["ensure", "--instance", "act-pm-missing-browser"],
                ["release", "--instance", "act-pm-missing-browser"],
            )
            for argv in cases:
                with self.subTest(argv=argv):
                    completed = run_process(
                        [str(LAUNCHER), "env", "browser", *argv],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    self.assertEqual(completed.returncode, 3)
                    error = self._cli_error(completed, code="NOT_FOUND")
                    self.assertIn("act-pm-missing-browser", str(error.get("message")))
                    self.assertNotIn("Traceback", completed.stdout + completed.stderr)
                    self.assertNotIn("EXECUTION_FAILED", completed.stdout)
                    self.assertFalse(shared_root.exists(), "missing actor validation should not create runtime state")
    def test_locked_workspace_sync_entrypoint_fails_closed_as_unknown_command(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace_dir = shared_root / "workspace"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            direct_sync = run_process(
                [str(LAUNCHER), "__" + "locked-workspace-sync"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(direct_sync.returncode, 2)
            self.assertIn("Unknown top-level command: __" + "locked-workspace-sync", self._output_error_text(direct_sync))
            self.assertFalse(workspace_dir.exists(), "direct locked entrypoint must not mutate workspace")
