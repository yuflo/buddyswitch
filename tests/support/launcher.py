"""Cross-tier launcher test primitives with no process or system policy."""

from __future__ import annotations

import errno
import json
import os
import subprocess
from pathlib import Path

from tests.support.cli import write_executable
from tests.support.fake_codex import write_fake_codex
from tests.support.paths import REPO_ROOT
from tests.support.processes import ResourceLedger

ROOT = REPO_ROOT
_VERIFIED_RUNTIME_PROJECTIONS = {
    "BUDDYSWITCH_PACKAGE_ROOT",
    "BUDDYSWITCH_PROJECT_SOURCE",
    "BUDDYSWITCH_PYTHON",
    "BUDDYSWITCH_RUNTIME_DIR",
    "BUDDYSWITCH_RUNTIME_IDENTITY",
    "BUDDYSWITCH_SOURCE_ROOT",
}


class LauncherTestSupport:
    _RELATIVE_SENTINELS = (
        "cross-role-sentinel.txt",
        "relative-path-sentinel.txt",
        "shared-product-sentinel.txt",
    )

    def setUp(self) -> None:
        super().setUp()
        self._ledger = ResourceLedger.from_environment()
        self._isolate_parent_buddyswitch_environment()
        self._cleanup_repo_relative_sentinels()
        self.addCleanup(self._cleanup_repo_relative_sentinels)

    def _isolate_parent_buddyswitch_environment(self) -> None:
        saved = {
            key: value
            for key, value in os.environ.items()
            if key.startswith("BUDDYSWITCH_")
            and key not in _VERIFIED_RUNTIME_PROJECTIONS
            and not key.startswith("BUDDYSWITCH_TEST_")
        }
        for key in saved:
            os.environ.pop(key, None)

        def restore() -> None:
            for key in list(os.environ):
                if (
                    key.startswith("BUDDYSWITCH_")
                    and key not in _VERIFIED_RUNTIME_PROJECTIONS
                    and not key.startswith("BUDDYSWITCH_TEST_")
                ):
                    os.environ.pop(key, None)
            os.environ.update(saved)

        self.addCleanup(restore)

    @classmethod
    def _cleanup_repo_relative_sentinels(cls) -> None:
        project_app = ROOT / "projects" / "app"
        for name in cls._RELATIVE_SENTINELS:
            (project_app / name).unlink(missing_ok=True)

    def _write_fake_codex(self, path: Path) -> None:
        write_fake_codex(path)

    def _write_fake_curl(self, path: Path) -> None:
        write_executable(
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
  "${BUDDYSWITCH_PYTHON}" - "${BUDDYSWITCH_TEST_CDP_STATE_FILE}" "${method}" "${url}" "${connect_timeout}" "${max_time}" "${BUDDYSWITCH_TEST_CDP_CALLS_FILE:-}" <<'PY'
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
        write_executable(
            path,
            """#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${BUDDYSWITCH_TEST_CHROME_ARGV_FILE:-}" ]]; then
  "${BUDDYSWITCH_PYTHON}" - "${BUDDYSWITCH_TEST_CHROME_ARGV_FILE}" "$@" <<'PY'
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
  "${BUDDYSWITCH_PYTHON}" - "${BUDDYSWITCH_TEST_CDP_STATE_FILE}" <<'PY'
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
if [[ "${BUDDYSWITCH_TEST_FAKE_CHROME_SERVE_CDP:-0}" == "1" ]]; then
  "${BUDDYSWITCH_PYTHON}" - "$@" <<'PY'
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

port = None
for arg in sys.argv[1:]:
    if arg.startswith("--remote-debugging-port="):
        port = int(arg.split("=", 1)[1])
if port is None:
    raise SystemExit("missing --remote-debugging-port")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_GET(self):
        if self.path == "/json/version":
            payload = {"Browser": "test"}
        elif self.path == "/json/list":
            payload = [{"id": "target-about-blank", "type": "page", "url": "about:blank"}]
        else:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(("127.0.0.1", port), Handler).serve_forever()
PY
fi
exit 0
""",
        )

    def _cli_envelope(self, completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
        self.assertEqual(completed.stdout.count("\n"), 1, msg=completed.stdout)
        self.assertFalse(getattr(completed, "stderr", "").strip(), msg=getattr(completed, "stderr", ""))
        payload = json.loads(completed.stdout)
        self.assertIsInstance(payload, dict)
        return payload

    def _cli_success_data(self, completed: subprocess.CompletedProcess[str], *, kind: str | None = None) -> object:
        payload = self._cli_envelope(completed)
        self.assertEqual(payload.get("ok"), True, msg=payload)
        if kind is not None:
            self.assertEqual(payload.get("kind"), kind, msg=payload)
        self.assertIn("data", payload)
        return payload["data"]

    def _cli_error(self, completed: subprocess.CompletedProcess[str], *, code: str) -> dict[str, object]:
        payload = self._cli_envelope(completed)
        self.assertEqual(payload.get("ok"), False, msg=payload)
        error = payload.get("error")
        self.assertIsInstance(error, dict, msg=payload)
        assert isinstance(error, dict)
        self.assertEqual(error.get("code"), code, msg=payload)
        return error

    def _output_error_text(self, completed: subprocess.CompletedProcess[str]) -> str:
        stdout = getattr(completed, "stdout", "")
        if isinstance(stdout, str) and stdout.count("\n") == 1:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict) and payload.get("ok") is False:
                error = payload.get("error")
                if isinstance(error, dict):
                    return json.dumps(error, ensure_ascii=False)
        stderr = getattr(completed, "stderr", "")
        return stderr if isinstance(stderr, str) else ""

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
        report = self._ledger.cleanup_registered_process(
            pid,
            expected_pgid=self._coerce_pid(pgid_value),
        )
        self.assertEqual(report.identity_mismatches, [])
        self.assertEqual(report.residuals, [])

    def _cleanup_process_descriptor(self, descriptor_id: str) -> None:
        self._ledger.reconcile_descriptors()
        seen: set[tuple[int, str]] = set()
        for record in reversed(self._ledger.records()):
            if (
                record.get("kind") != "process"
                or record.get("descriptor_id") != descriptor_id
            ):
                continue
            key = (int(record["pid"]), str(record["start_identity"]))
            if key in seen:
                continue
            seen.add(key)
            report = self._ledger.cleanup_registered_process(key[0])
            self.assertEqual(report.identity_mismatches, [])
            self.assertEqual(report.residuals, [])
