#!/usr/bin/env python3
"""Tests for launcher-owned browser runtime manager."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.launcher import browser_runtime_manager as manager  # noqa: E402


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def wait_until(predicate: object, *, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():  # type: ignore[operator]
            return True
        time.sleep(0.05)
    return bool(predicate())  # type: ignore[operator]


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def port_accepts(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.2)
        sock.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


class BrowserRuntimeManagerTests(unittest.TestCase):
    def _write_instance(self, instance_root: Path, actor_id: str = "act-dev-browser", *, browser_port: int | None = None) -> Path:
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": "dev",
                    "status": "active",
                    "instance_root": str(instance_root),
                    "workspace_dir": str(instance_root / "workspace"),
                    "thread_id": "thr-main",
                    "browser_port": browser_port,
                    "created_at": "2026-07-02T00:00:00Z",
                    "updated_at": "2026-07-02T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _write_fake_chrome(self, path: Path, argv_path: Path) -> None:
        path.write_text(
            textwrap.dedent(
                f"""\
                #!/usr/bin/env python3
                from http.server import BaseHTTPRequestHandler, HTTPServer
                import json
                import sys

                argv_path = {str(argv_path)!r}
                port = None
                for arg in sys.argv[1:]:
                    if arg.startswith("--remote-debugging-port="):
                        port = int(arg.split("=", 1)[1])
                if port is None:
                    raise SystemExit("missing remote debugging port")
                with open(argv_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(sys.argv[1:], ensure_ascii=True) + "\\n")

                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *_args):
                        return

                    def do_GET(self):
                        if self.path == "/json/version":
                            payload = {{
                                "Browser": "fake",
                                "webSocketDebuggerUrl": f"ws://127.0.0.1:{{port}}/devtools/browser/fake",
                            }}
                        elif self.path == "/json/list":
                            payload = [{{"id": "ready", "type": "page", "url": "about:blank"}}]
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

                server = HTTPServer(("127.0.0.1", port), Handler)
                server.serve_forever()
                """
            ),
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | 0o700)

    def _terminate_process(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        if not wait_until(lambda: not pid_alive(pid), timeout=2.0):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                return

    def _start_fake_chrome(self, chrome_bin: Path, *, port: int, profile_dir: Path, log_file: Path) -> subprocess.Popen[str]:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(
            [
                str(chrome_bin),
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "about:blank",
            ],
            stdout=log_file.open("a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        self.addCleanup(self._terminate_process, proc.pid)
        self.assertTrue(wait_until(lambda: port_accepts(port)), "fake Chrome endpoint did not become ready")
        return proc

    def test_acquire_starts_chrome_records_port_and_pid_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            instance_json = self._write_instance(instance_root)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            port = free_port()

            result = manager.acquire(
                instance_root=instance_root,
                actor_id="act-dev-browser",
                requested_port=port,
                chrome_bin=chrome_bin,
            )

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("browser_port"), port)
            self.assertEqual(result.get("browser_url"), f"http://127.0.0.1:{port}")
            self.assertEqual(result.get("state_changed"), True)
            self.assertEqual(result.get("durability"), "runtime")
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertEqual(instance_payload["browser_port"], port)
            pid_file = instance_root / "browser" / "chrome.pid"
            self.assertTrue(pid_file.exists())
            browser_pid = int(pid_file.read_text(encoding="utf-8").strip())
            self.assertTrue(pid_alive(browser_pid))
            argv = [json.loads(line) for line in chrome_argv.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(argv), 1)
            self.assertIn(f"--remote-debugging-port={port}", argv[0])
            self.assertIn(f"--user-data-dir={instance_root / 'browser' / 'profile'}", argv[0])

            release = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="test_cleanup")
            self.assertTrue(release.get("ok"), msg=release)
            self.assertTrue(wait_until(lambda: not pid_alive(browser_pid)), "release must stop fake Chrome")

    def test_acquire_reuses_owned_recorded_ready_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            self._write_instance(instance_root, browser_port=port)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=instance_root / "browser" / "profile",
                log_file=instance_root / "browser" / "chrome.log",
            )
            (instance_root / "browser").mkdir(parents=True, exist_ok=True)
            (instance_root / "browser" / "chrome.pid").write_text(f"{proc.pid}\n", encoding="utf-8")

            result = manager.acquire(instance_root=instance_root, actor_id="act-dev-browser")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("browser_port"), port)
            self.assertEqual(result.get("state_changed"), False)
            argv = [json.loads(line) for line in chrome_argv.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(argv), 1, "acquire should not start another Chrome when owned endpoint is ready")

    def test_release_cleans_owned_runtime_state(self) -> None:
        upstream_proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
        upstream_pgid = os.getpgid(upstream_proc.pid)
        self.addCleanup(self._terminate_process, upstream_proc.pid)

        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            instance_json = self._write_instance(instance_root, browser_port=port)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            chrome_proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=instance_root / "browser" / "profile",
                log_file=instance_root / "browser" / "chrome.log",
            )
            browser_dir = instance_root / "browser"
            runtime_browser_dir = instance_root / "runtime" / "browser"
            browser_dir.mkdir(parents=True, exist_ok=True)
            runtime_browser_dir.mkdir(parents=True, exist_ok=True)
            (browser_dir / "chrome.pid").write_text(f"{chrome_proc.pid}\n", encoding="utf-8")
            (runtime_browser_dir / "cockpit-upstream.pid").write_text(f"{upstream_proc.pid}\n", encoding="utf-8")
            (runtime_browser_dir / "cockpit-upstream.pgid").write_text(f"{upstream_pgid}\n", encoding="utf-8")
            (runtime_browser_dir / "page_idle.json").write_text("{}", encoding="utf-8")
            (runtime_browser_dir / "page_idle.lock").write_text("", encoding="utf-8")

            result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="page_idle_empty")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("handled"), True)
            self.assertEqual(result.get("state_changed"), True)
            self.assertTrue(wait_until(lambda: not pid_alive(chrome_proc.pid)), "release must stop Chrome pid")
            self.assertTrue(wait_until(lambda: not pid_alive(upstream_proc.pid)), "release must stop upstream pid")
            self.assertFalse((browser_dir / "chrome.pid").exists())
            self.assertFalse((runtime_browser_dir / "cockpit-upstream.pid").exists())
            self.assertFalse((runtime_browser_dir / "cockpit-upstream.pgid").exists())
            self.assertFalse((runtime_browser_dir / "page_idle.json").exists())
            self.assertFalse((runtime_browser_dir / "page_idle.lock").exists())
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertIsNone(instance_payload["browser_port"])

    def test_release_clears_foreign_endpoint_without_killing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            instance_root = temp_root_path / "instances" / "act-dev-browser"
            port = free_port()
            instance_json = self._write_instance(instance_root, browser_port=port)
            chrome_bin = temp_root_path / "fake-chrome.py"
            chrome_argv = temp_root_path / "chrome-argv.jsonl"
            self._write_fake_chrome(chrome_bin, chrome_argv)
            foreign_proc = self._start_fake_chrome(
                chrome_bin,
                port=port,
                profile_dir=temp_root_path / "foreign-profile",
                log_file=temp_root_path / "foreign.log",
            )

            result = manager.release(instance_root=instance_root, actor_id="act-dev-browser", reason="page_idle_empty")

            self.assertTrue(result.get("ok"), msg=result)
            self.assertEqual(result.get("handled"), True)
            self.assertIn(result.get("ownership"), {"foreign", "unknown"})
            self.assertTrue(pid_alive(foreign_proc.pid), "foreign endpoint process must not be killed")
            instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
            self.assertIsNone(instance_payload["browser_port"])


if __name__ == "__main__":
    unittest.main()
