#!/usr/bin/env python3
"""Tests for browser cockpit subcommands on the BuddySwitch launcher."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "buddyswitch-codex"


class BrowserCockpitLauncherTests(unittest.TestCase):
    def _write_exec(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _write_instance_record(self, shared_root: Path, instance_id: str = "inst-pm-browser") -> Path:
        instance_root = shared_root / "instances" / instance_id
        instance_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "instance_id": instance_id,
            "buddy": "pm",
            "status": "inactive",
            "current_task_id": None,
            "current_track_id": None,
            "workspace_dir": str(instance_root / "workspace"),
            "browser_port": None,
            "created_at": "2026-05-02T00:00:00Z",
            "updated_at": "2026-05-02T00:00:00Z",
        }
        record_path = instance_root / "instance.json"
        record_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return instance_root

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

    def _write_fake_codex(self, path: Path) -> None:
        self._write_exec(
            path,
            """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

payload = {
    "argv": sys.argv[1:],
    "home": os.environ.get("HOME"),
    "codex_home": os.environ.get("CODEX_HOME"),
    "xdg_config_home": os.environ.get("XDG_CONFIG_HOME"),
}
with Path(os.environ["BUDDYSWITCH_TEST_CAPTURE"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(payload, ensure_ascii=True) + "\\n")
""",
        )

    def test_browser_ensure_starts_chrome_with_shared_profile_and_bootstraps_mcps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            ready_file = temp_root_path / "browser-ready.flag"
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")
            self._write_fake_codex(fake_bin / "codex")

            capture_path = temp_root_path / "calls.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-browser"
            instance_root = self._write_instance_record(shared_root, instance_id)

            completed = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", instance_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                msg=f"browser ensure failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            )
            self.assertTrue(ready_file.exists(), "browser ensure should make endpoint reachable")

            self.assertTrue((instance_root / "browser" / "profile").exists())
            self.assertTrue((instance_root / "browser" / "chrome.pid").exists())

            payloads = [
                json.loads(line)
                for line in capture_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            mcp_add_names = [payload["argv"][2] for payload in payloads if payload["argv"][:2] == ["mcp", "add"]]
            self.assertEqual(mcp_add_names, ["chrome-devtools-cockpit"])

            expected_home = instance_root / "home"
            expected_codex_home = instance_root / "codex-home"
            for payload in payloads:
                self.assertEqual(payload["home"], str(expected_home))
                self.assertEqual(payload["codex_home"], str(expected_codex_home))
                self.assertEqual(payload["xdg_config_home"], str(instance_root / "xdg-config"))

    def test_browser_ensure_does_not_create_runtime_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            ready_file = temp_root_path / "browser-ready.flag"
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")
            self._write_fake_codex(fake_bin / "codex")

            capture_path = temp_root_path / "calls.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            shared_root = source_home_path / ".codex-buddyswitch"
            instance_id = "inst-pm-browser"
            instance_root = self._write_instance_record(shared_root, instance_id)

            completed = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", instance_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                msg=f"browser ensure failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            )
            shared_workspace_dir = shared_root / "workspace"
            instance_workspace_dir = instance_root / "workspace"
            self.assertFalse(shared_workspace_dir.exists(), "browser ensure should not create the legacy runtime workspace")
            self.assertFalse(instance_workspace_dir.exists(), "browser ensure should not create the instance runtime workspace")
            payloads = [
                json.loads(line)
                for line in capture_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(
                payloads[0]["home"],
                str(instance_root / "home"),
                "browser ensure should bootstrap from instance-scoped runtime state, not main-checkout skeletons",
            )

    def test_browser_ensure_requires_instance_flag(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("env browser ensure requires --instance <instance-id>", completed.stderr)
            self.assertFalse(shared_root.exists(), "ensure without --instance must fail before creating shared state")

    def test_browser_launcher_source_is_instance_only(self) -> None:
        text = (ROOT / "tools" / "launcher" / "browser_cockpit.sh").read_text(encoding="utf-8")
        self.assertIn("chrome-devtools-cockpit", text)
        self.assertNotIn("chrome/shared-browser", text)
        self.assertNotIn("buddyswitch_browser_ensure_general_mcp", text)
        self.assertNotIn("mcp add \"chrome-devtools\"", text)

    def test_browser_status_does_not_create_shared_root(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "env", "browser", "status", "--port", "65530"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertFalse(
                shared_root.exists(),
                "browser status should be read-only and must not create shared launcher directories",
            )

    def test_browser_status_rejects_missing_port_value(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "env", "browser", "status", "--port"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Missing value for --port", completed.stderr)
            self.assertFalse(shared_root.exists(), "invalid browser status args should stay read-only")


if __name__ == "__main__":
    unittest.main()
