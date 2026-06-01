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

    def _write_instance_record(self, shared_root: Path, actor_id: str = "act-pm-browser") -> Path:
        instance_root = shared_root / "instances" / actor_id
        instance_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "actor_id": actor_id,
            "role": "pm",
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

    def _assert_cockpit_proxy_registration(self, argv: list[object], browser_url: str) -> None:
        self.assertEqual(argv[:3], ["mcp", "add", "chrome-devtools-cockpit"])
        self.assertIn("--", argv)
        separator_index = argv.index("--")
        self.assertEqual(argv[separator_index + 1], "python3")
        self.assertIn("tools/launcher/chrome_devtools_cockpit_proxy.py", str(argv[separator_index + 2]))
        self.assertIn(f"--browser-url={browser_url}", argv)
        self.assertNotIn("chrome-devtools-mcp@latest", argv)

    def test_browser_ensure_starts_chrome_with_shared_profile_and_bootstraps_mcps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            state_file = temp_root_path / "cdp-state.json"
            self._write_cdp_state(
                state_file,
                version_ok=False,
                pages=[],
                allow_background_create_about_blank=True,
            )
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_background_page_tool(fake_bin / "background-page")

            capture_path = temp_root_path / "calls.jsonl"
            chrome_argv_path = temp_root_path / "chrome-argv.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL"] = str(fake_bin / "background-page")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)
            env["BUDDYSWITCH_TEST_CHROME_ARGV_FILE"] = str(chrome_argv_path)

            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser"
            instance_root = self._write_instance_record(shared_root, actor_id)

            completed = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
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

            self.assertTrue((instance_root / "browser" / "profile").exists())
            self.assertTrue((instance_root / "browser" / "chrome.pid").exists())

            chrome_argv = [
                json.loads(line)
                for line in chrome_argv_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(chrome_argv), 1)
            chrome_args = chrome_argv[0]
            self.assertIn(f"--remote-debugging-port=9222", chrome_args)
            self.assertIn(f"--user-data-dir={instance_root / 'browser' / 'profile'}", chrome_args)
            self.assertIn("--no-first-run", chrome_args)
            self.assertIn("--no-default-browser-check", chrome_args)
            self.assertEqual(chrome_args[-1], "about:blank")

            payloads = [
                json.loads(line)
                for line in capture_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            mcp_add_names = [payload["argv"][2] for payload in payloads if payload["argv"][:2] == ["mcp", "add"]]
            self.assertEqual(mcp_add_names, ["chrome-devtools-cockpit"])
            cockpit_add = next(payload for payload in payloads if payload["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"])
            self._assert_cockpit_proxy_registration(cockpit_add["argv"], "http://127.0.0.1:9222")

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
            actor_id = "act-pm-browser"
            instance_root = self._write_instance_record(shared_root, actor_id)

            completed = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
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

    def test_browser_status_endpoint_only_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            state_file = temp_root_path / "cdp-state.json"
            self._write_cdp_state(state_file, version_ok=True, pages=[])
            self._write_fake_curl(fake_bin / "curl")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)

            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser"
            self._write_instance_record(shared_root, actor_id)

            status = subprocess.run(
                [str(LAUNCHER), "env", "browser", "status", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(status.returncode, 1)
            self.assertIn("not ready", status.stderr.lower())

    def test_browser_status_filters_special_chrome_pages_as_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            state_file = temp_root_path / "cdp-state.json"
            self._write_fake_curl(fake_bin / "curl")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)

            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser"
            self._write_instance_record(shared_root, actor_id)

            for url in (
                "chrome://signin/",
                "chrome-untrusted://blocked",
                "devtools://devtools/bundled/inspector.html",
            ):
                with self.subTest(url=url):
                    self._write_cdp_state(
                        state_file,
                        version_ok=True,
                        pages=[{"id": "only-page", "type": "page", "url": url}],
                    )
                    status = subprocess.run(
                        [str(LAUNCHER), "env", "browser", "status", "--instance", actor_id],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(status.returncode, 1)
                    self.assertIn("not ready", status.stderr.lower())

    def test_browser_status_accepts_http_and_https_pages_as_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            state_file = temp_root_path / "cdp-state.json"
            self._write_fake_curl(fake_bin / "curl")

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)

            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser"
            self._write_instance_record(shared_root, actor_id)

            for url in ("http://example.com/", "https://example.com/"):
                with self.subTest(url=url):
                    self._write_cdp_state(
                        state_file,
                        version_ok=True,
                        pages=[{"id": "normal-page", "type": "page", "url": url}],
                    )
                    status = subprocess.run(
                        [str(LAUNCHER), "env", "browser", "status", "--instance", actor_id],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(status.returncode, 0, msg=status.stderr)
                    self.assertIn("Browser cockpit ready:", status.stdout)

    def test_browser_ensure_rejects_endpoint_only_when_background_ready_page_creation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            state_file = temp_root_path / "cdp-state.json"
            calls_file = temp_root_path / "cdp-calls.jsonl"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[{"id": "intro", "type": "page", "url": "chrome://intro/"}],
                allow_background_create_about_blank=False,
            )
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_background_page_tool(fake_bin / "background-page")

            capture_path = temp_root_path / "calls.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CDP_CALLS_FILE"] = str(calls_file)
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL"] = str(fake_bin / "background-page")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser"
            self._write_instance_record(shared_root, actor_id)

            ensure = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(ensure.returncode, 0)
            self.assertIn("not ready", ensure.stderr.lower())
            self.assertFalse(capture_path.exists(), "MCP setup should not run when ready page cannot be created")
            calls = [
                json.loads(line)
                for line in calls_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(any(call.get("path") == "Target.createTarget" for call in calls))
            self.assertFalse(any(call.get("path") == "/json/new" for call in calls))

    def test_browser_ensure_uses_bounded_timeouts_for_cdp_probes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            state_file = temp_root_path / "cdp-state.json"
            calls_file = temp_root_path / "cdp-calls.jsonl"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[{"id": "intro", "type": "page", "url": "chrome://intro/"}],
                allow_background_create_about_blank=True,
            )
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_background_page_tool(fake_bin / "background-page")

            capture_path = temp_root_path / "calls.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CDP_CALLS_FILE"] = str(calls_file)
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL"] = str(fake_bin / "background-page")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser"
            self._write_instance_record(shared_root, actor_id)

            ensure = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ensure.returncode, 0, msg=ensure.stderr)

            calls = [
                json.loads(line)
                for line in calls_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            for probe_path in ("/json/version", "/json/list"):
                probe_calls = [call for call in calls if call.get("path") == probe_path]
                self.assertTrue(probe_calls, msg=f"Expected at least one call for {probe_path}")
                for call in probe_calls:
                    self.assertNotEqual(call.get("connect_timeout"), "", msg=f"{probe_path} missing --connect-timeout")
                    self.assertNotEqual(call.get("max_time"), "", msg=f"{probe_path} missing --max-time")
            self.assertTrue(any(call.get("path") == "Target.createTarget" for call in calls))
            self.assertFalse(any(call.get("path") == "/json/new" for call in calls))

    def test_browser_ensure_repairs_intro_only_with_background_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            state_file = temp_root_path / "cdp-state.json"
            calls_file = temp_root_path / "cdp-calls.jsonl"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[{"id": "intro", "type": "page", "url": "chrome://intro/"}],
                allow_background_create_about_blank=True,
            )
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_background_page_tool(fake_bin / "background-page")

            capture_path = temp_root_path / "calls.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CDP_CALLS_FILE"] = str(calls_file)
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL"] = str(fake_bin / "background-page")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser"
            self._write_instance_record(shared_root, actor_id)

            ensure = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ensure.returncode, 0, msg=ensure.stderr)
            calls = [
                json.loads(line)
                for line in calls_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            background_calls = [call for call in calls if call.get("path") == "Target.createTarget"]
            self.assertEqual(len(background_calls), 1, msg=calls)
            self.assertEqual(background_calls[0].get("params"), {"url": "about:blank", "background": True})
            self.assertFalse(
                any(call.get("path") == "/json/new" and call.get("query") == "about:blank" for call in calls)
            )

            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertTrue(
                any(
                    isinstance(page, dict)
                    and page.get("type") == "page"
                    and page.get("url") == "about:blank"
                    for page in state["pages"]
                )
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
            self.assertIn("env browser ensure requires --instance <actor-id>", completed.stderr)
            self.assertFalse(shared_root.exists(), "ensure without --instance must fail before creating shared state")

    def test_browser_ensure_repairs_raw_cockpit_mcp_with_matching_browser_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            state_file = temp_root_path / "cdp-state.json"
            self._write_cdp_state(
                state_file,
                version_ok=True,
                pages=[{"id": "ready", "type": "page", "url": "about:blank"}],
            )
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_codex(fake_bin / "codex")

            capture_path = temp_root_path / "calls.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_CDP_STATE_FILE"] = str(state_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            shared_root = source_home_path / ".codex-buddyswitch"
            actor_id = "act-pm-browser-raw-mcp"
            instance_root = self._write_instance_record(shared_root, actor_id)
            instance_codex_home = instance_root / "codex-home"
            instance_codex_home.mkdir(parents=True, exist_ok=True)
            (instance_codex_home / "config.toml").write_text(
                """
[mcp_servers.chrome-devtools-cockpit]
command = "npx"
args = ["chrome-devtools-mcp@latest", "--browser-url=http://127.0.0.1:9222"]
""".lstrip(),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [str(LAUNCHER), "env", "browser", "ensure", "--instance", actor_id],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")

            payloads = [
                json.loads(line)
                for line in capture_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            remove_index = next(
                index
                for index, payload in enumerate(payloads)
                if payload["argv"][:3] == ["mcp", "remove", "chrome-devtools-cockpit"]
            )
            add_index = next(
                index
                for index, payload in enumerate(payloads)
                if payload["argv"][:3] == ["mcp", "add", "chrome-devtools-cockpit"]
            )
            self.assertLess(remove_index, add_index)
            self._assert_cockpit_proxy_registration(payloads[add_index]["argv"], "http://127.0.0.1:9222")

    def test_browser_launcher_source_is_instance_only(self) -> None:
        text = (ROOT / "tools" / "launcher" / "browser_cockpit.sh").read_text(encoding="utf-8")
        self.assertIn("chrome-devtools-cockpit", text)
        self.assertIn("chrome_devtools_cockpit_proxy.py", text)
        self.assertIn("scripts/env/cdp_background_page.py", text)
        self.assertNotIn("tools" + "/launcher/cdp_background_page.py", text)
        self.assertNotIn("/json/new?about:blank", text)
        self.assertNotIn("chrome-devtools-mcp@latest", text)
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
