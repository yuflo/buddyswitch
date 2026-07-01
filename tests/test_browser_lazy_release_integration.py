#!/usr/bin/env python3
"""End-to-end smoke for lazy browser runtime release and restart."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from itertools import count
from typing import Any
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import env_manifest  # noqa: E402
import env.tools.search._impl as search_impl  # noqa: E402
from env.domain import task_sys  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.tool_runtime.registry import dispatch_env_tool_request  # noqa: E402


LAUNCHER = ROOT / "buddyswitch-codex"
MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
PROXY = ROOT / "tools" / "launcher" / "chrome_devtools_cockpit_proxy.py"
PAGE_EXPIRED_HANDLER = ROOT / "tools" / "launcher" / "browser_page_expired_handler.py"
RELEASE_HANDLER = ROOT / "tools" / "launcher" / "browser_release_handler.py"
TRIGGERS = ROOT / "tools" / "launcher" / "daemon_triggers.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    module_name = f"buddyswitch_{path.stem}_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def wait_until(predicate: Any, *, timeout: float = 5.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def port_accepts(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class FakeRuntime:
    def parent_activity(self) -> dict[str, object]:
        return {"status": "idle"}


class BrowserLazyReleaseIntegrationTests(unittest.TestCase):
    maxDiff = None

    def _write_exec(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _write_fake_chrome_server(self, path: Path) -> None:
        self._write_exec(
            path,
            r'''#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse


STATE_FILE = Path(os.environ["BUDDYSWITCH_TEST_FAKE_CHROME_STATE"])
PORT = int(os.environ["BUDDYSWITCH_TEST_FAKE_CHROME_PORT"])
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def websocket_accept_value(key: str) -> str:
    digest = hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def read_exact(stream: object, length: int) -> bytes:
    chunks = b""
    while len(chunks) < length:
        chunk = stream.read(length - len(chunks))
        if not chunk:
            raise EOFError("websocket stream closed")
        chunks += chunk
    return chunks


def read_client_text_frame(stream: object) -> str:
    first, second = read_exact(stream, 2)
    opcode = first & 0x0F
    if opcode != 0x1:
        raise ValueError(f"expected text frame, got opcode {opcode}")
    length = second & 0x7F
    if length == 126:
        length = int.from_bytes(read_exact(stream, 2), "big")
    elif length == 127:
        length = int.from_bytes(read_exact(stream, 8), "big")
    mask = read_exact(stream, 4) if second & 0x80 else b""
    payload = read_exact(stream, length)
    if mask:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return payload.decode("utf-8")


def write_server_text_frame(stream: object, text: str) -> None:
    payload = text.encode("utf-8")
    first = 0x80 | 0x1
    length = len(payload)
    if length < 126:
        header = bytes([first, length])
    elif length < (1 << 16):
        header = bytes([first, 126]) + length.to_bytes(2, "big")
    else:
        header = bytes([first, 127]) + length.to_bytes(8, "big")
    stream.write(header + payload)
    stream.flush()


def read_state() -> dict[str, object]:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {"targets": []}
    if not isinstance(payload, dict):
        payload = {"targets": []}
    targets = payload.get("targets")
    if not isinstance(targets, list):
        payload["targets"] = []
    return payload


def write_state(payload: dict[str, object]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/json/version":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {
                "Browser": "fake-chrome",
                "webSocketDebuggerUrl": f"ws://127.0.0.1:{PORT}/devtools/browser/test",
            }
            self.wfile.write(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
            return
        if parsed.path == "/json/list":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(read_state().get("targets", []), ensure_ascii=True).encode("utf-8"))
            return
        if parsed.path == "/devtools/browser/test":
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:
                self.send_response(400)
                self.end_headers()
                return
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", websocket_accept_value(key))
            self.end_headers()
            raw_message = read_client_text_frame(self.rfile)
            message = json.loads(raw_message)
            state = read_state()
            targets = state.setdefault("targets", [])
            if not isinstance(targets, list):
                targets = []
                state["targets"] = targets
            method = message.get("method")
            if method == "Target.closeTarget":
                params = message.get("params") if isinstance(message.get("params"), dict) else {}
                target_id = params.get("targetId")
                state["targets"] = [
                    target
                    for target in targets
                    if not (isinstance(target, dict) and target.get("id") == target_id)
                ]
                write_state(state)
                response = {"id": message.get("id"), "result": {"success": True}}
            elif method == "Target.createTarget":
                params = message.get("params") if isinstance(message.get("params"), dict) else {}
                target_id = f"target-{len(targets) + 1}"
                targets.append(
                    {
                        "id": target_id,
                        "type": "page",
                        "url": params.get("url") if isinstance(params.get("url"), str) else "",
                    }
                )
                write_state(state)
                response = {"id": message.get("id"), "result": {"targetId": target_id}}
            else:
                response = {"id": message.get("id"), "result": {"success": True}}
            write_server_text_frame(self.wfile, json.dumps(response, ensure_ascii=True))
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


write_state(read_state())
HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
''',
        )

    def _write_fake_upstream(self, path: Path) -> None:
        self._write_exec(
            path,
            r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


argv_path = Path(os.environ["BUDDYSWITCH_TEST_UPSTREAM_ARGV"])
calls_path = Path(os.environ["BUDDYSWITCH_TEST_UPSTREAM_CALLS"])
argv_path.parent.mkdir(parents=True, exist_ok=True)
with argv_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:], ensure_ascii=True) + "\n")


for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
        continue
    message = json.loads(line)
    with calls_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(message, ensure_ascii=True) + "\n")
    request_id = message.get("id")
    method = message.get("method")
    if request_id is None:
        continue
    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-chrome-devtools-mcp", "version": "test"},
            },
        }
    elif method == "tools/call":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": "fake upstream tool response"}]},
        }
    else:
        response = {"jsonrpc": "2.0", "id": request_id, "result": {}}
    sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
    sys.stdout.flush()
''',
        )

    def _write_ensure_script(self, path: Path) -> None:
        self._write_exec(
            path,
            r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def endpoint_ready(port: int) -> bool:
    request = Request(f"http://127.0.0.1:{port}/json/version", method="GET")
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=0.2) as response:
            response.read()
    except (OSError, URLError):
        return False
    return True


instance_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ["BUDDYSWITCH_TEST_INSTANCE_ROOT"])
instance_json = Path(os.environ.get("BUDDYSWITCH_TEST_INSTANCE_JSON", str(instance_root / "instance.json")))
port = int(os.environ["BUDDYSWITCH_TEST_FAKE_CHROME_PORT"])
state_file = Path(os.environ["BUDDYSWITCH_TEST_FAKE_CHROME_STATE"])
server_script = Path(os.environ["BUDDYSWITCH_TEST_FAKE_CHROME_SERVER"])
calls_path = Path(os.environ["BUDDYSWITCH_TEST_BROWSER_ENSURE_CALLS"])
marker = instance_root / "browser" / "chrome.pid"

existing_pid = None
try:
    existing_pid = int(marker.read_text(encoding="ascii").strip())
except (FileNotFoundError, ValueError):
    existing_pid = None

started = False
pid = existing_pid
if pid is None or not pid_alive(pid) or not endpoint_ready(port):
    if pid is not None and pid_alive(pid):
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    marker.parent.mkdir(parents=True, exist_ok=True)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    if not state_file.exists():
        state_file.write_text(json.dumps({"targets": []}, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    child_env = os.environ.copy()
    child_env["BUDDYSWITCH_TEST_FAKE_CHROME_PORT"] = str(port)
    child_env["BUDDYSWITCH_TEST_FAKE_CHROME_STATE"] = str(state_file)
    devnull_in = open(os.devnull, "rb")
    devnull_out = open(os.devnull, "ab")
    proc = subprocess.Popen(
        [sys.executable, str(server_script)],
        stdin=devnull_in,
        stdout=devnull_out,
        stderr=devnull_out,
        env=child_env,
        start_new_session=True,
        close_fds=True,
    )
    pid = proc.pid
    marker.write_text(f"{pid}\n", encoding="ascii")
    started = True
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if endpoint_ready(port):
            break
        if proc.poll() is not None:
            raise SystemExit(f"fake chrome server exited with {proc.returncode}")
        time.sleep(0.05)
    if not endpoint_ready(port):
        raise SystemExit("fake chrome endpoint did not become ready")

payload = json.loads(instance_json.read_text(encoding="utf-8"))
payload["browser_port"] = port
instance_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

calls_path.parent.mkdir(parents=True, exist_ok=True)
with calls_path.open("a", encoding="utf-8") as handle:
    handle.write(
        json.dumps(
            {
                "instance_root": str(instance_root),
                "started": started,
                "pid": pid,
                "port": port,
            },
            ensure_ascii=True,
        )
        + "\n"
    )
''',
        )

    def _instance_record(self, instance_root: Path, actor_id: str, role: str) -> Path:
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(instance_root / "workspace"),
                    "browser_port": None,
                    "created_at": "2026-06-30T00:00:00Z",
                    "updated_at": "2026-06-30T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _start_proxy(self, *, instance_root: Path, upstream: Path, env: dict[str, str]) -> subprocess.Popen[str]:
        proc = subprocess.Popen(
            [
                sys.executable,
                str(PROXY),
                "--upstream-command",
                f"{sys.executable} {upstream}",
                f"--instance-root={instance_root}",
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        self.addCleanup(self._stop_proxy, proc)
        return proc

    def _stop_proxy(self, proc: subprocess.Popen[str]) -> None:
        try:
            if proc.poll() is None:
                if proc.stdin is not None and not proc.stdin.closed:
                    proc.stdin.close()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)
        finally:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None and not stream.closed:
                    stream.close()

    def _send_proxy_tool_call(
        self,
        proc: subprocess.Popen[str],
        *,
        request_id: int,
        tool_name: str,
        arguments: dict[str, object],
    ) -> dict[str, Any]:
        assert proc.stdin is not None
        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        proc.stdin.write(json.dumps(message, ensure_ascii=True) + "\n")
        proc.stdin.flush()
        return self._read_proxy_response(proc)

    def _read_proxy_response(self, proc: subprocess.Popen[str]) -> dict[str, Any]:
        assert proc.stdout is not None
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            remaining = max(0.01, deadline - time.monotonic())
            readable, _, _ = select.select([proc.stdout], [], [], remaining)
            if not readable:
                continue
            line = proc.stdout.readline()
            if not line:
                stderr = proc.stderr.read() if proc.stderr is not None else ""
                self.fail(f"proxy exited before response with code {proc.poll()}; stderr:\n{stderr}")
            return json.loads(line)
        stderr = ""
        if proc.poll() is not None and proc.stderr is not None:
            stderr = proc.stderr.read()
        self.fail(f"timed out waiting for proxy response; code={proc.poll()}; stderr:\n{stderr}")

    def _dispatch_search_open_browser(self, *, instance_json: Path, actor_id: str, role: str) -> dict[str, Any]:
        manifest = env_manifest.load_manifest(MANIFEST)
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        return dispatch_env_tool_request(
            payload={
                "tool": "search",
                "action": "open_browser",
                "args": {"query": "lazy release smoke", "engine": "google"},
            },
            active_role=role,
            actor_id=actor_id,
            instance_json=instance_json,
            instance_payload=instance_payload,
            manifest=manifest,
            manifest_path=MANIFEST,
        )

    def _seed_active_task(self, *, actor_id: str, role: str) -> None:
        task_sys.ingest(
            {
                "source": {"type": "test.browser_lazy_release", "ref": {"slug": "lazy-release-smoke"}},
                "actor_target": {"actor_id": actor_id, "role_id": role},
                "context": {"fixture": "browser lazy release integration"},
            }
        )

    def _page_trigger(self, triggers: Any, *, actor_id: str, role: str, target_id: str) -> Any:
        return triggers.DaemonTrigger(
            source="scheduled_trigger",
            type="browser.page.expired",
            target_actor_address={"role_id": role, "actor_id": actor_id},
            origin_id="schedule-page",
            correlation_id=None,
            payload={"target_id": target_id},
            source_context={"schedule_id": "schedule-page"},
        )

    def _release_trigger(self, triggers: Any, *, actor_id: str, role: str) -> Any:
        return triggers.DaemonTrigger(
            source="scheduled_trigger",
            type="browser.cockpit.release",
            target_actor_address={"role_id": role, "actor_id": actor_id},
            origin_id="schedule-release",
            correlation_id=None,
            payload={"reason": "page_idle_empty"},
            source_context={"schedule_id": "schedule-release", "owner": "browser"},
        )

    def _handler_context(self, *, instance_root: Path, instance_json: Path, actor_id: str, role: str) -> Any:
        class Context:
            pass

        context = Context()
        context.actor_address = {"role_id": role, "actor_id": actor_id}
        context.actor_id = actor_id
        context.role = role
        context.instance_root = instance_root
        context.instance_json = instance_json
        context.instance_payload = {"browser_port": None}
        return context

    def _launcher_release(self, *, actor_id: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(LAUNCHER), "env", "browser", "release", "--instance", actor_id],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def _cleanup_fake_chrome_pids(self, ensure_calls: Path) -> None:
        for entry in read_jsonl(ensure_calls):
            pid = entry.get("pid")
            if isinstance(pid, int) and pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass

    def test_lazy_runtime_releases_after_idle_and_restarts_on_next_browser_call(self) -> None:
        actor_id = "act-dev-browser"
        role = "dev"
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            runtime_state_root = temp_root_path / "runtime-state"
            runtime_state_root.mkdir(parents=True, exist_ok=True)
            runtime_files.set_runtime_root_override(runtime_state_root)
            self.addCleanup(runtime_files.reset_runtime_root_override)
            source_home = temp_root_path / "home"
            shared_root = source_home / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / actor_id
            instance_json = self._instance_record(instance_root, actor_id, role)
            self._seed_active_task(actor_id=actor_id, role=role)

            fake_chrome = temp_root_path / "fake_chrome_server.py"
            fake_upstream = temp_root_path / "fake_upstream.py"
            ensure_script = temp_root_path / "fake_browser_ensure.py"
            fake_chrome_state = temp_root_path / "fake_chrome_state.json"
            ensure_calls = temp_root_path / "ensure_calls.jsonl"
            upstream_argv = temp_root_path / "upstream_argv.jsonl"
            upstream_calls = temp_root_path / "upstream_calls.jsonl"
            search_schedules: list[dict[str, object]] = []
            release_schedules: list[dict[str, object]] = []
            fake_port = free_port()

            self._write_fake_chrome_server(fake_chrome)
            self._write_fake_upstream(fake_upstream)
            self._write_ensure_script(ensure_script)
            self.addCleanup(self._cleanup_fake_chrome_pids, ensure_calls)
            original_search_schedule = search_impl.browser_lifecycle.daemon_client.schedule_trigger

            def fake_search_schedule_trigger(**kwargs: object) -> dict[str, object]:
                search_schedules.append(dict(kwargs))
                return {"schedule": {"schedule_id": "schedule-page"}}

            search_impl.browser_lifecycle.daemon_client.schedule_trigger = fake_search_schedule_trigger
            self.addCleanup(
                setattr,
                search_impl.browser_lifecycle.daemon_client,
                "schedule_trigger",
                original_search_schedule,
            )

            base_env = os.environ.copy()
            base_env.update(
                {
                    "HOME": str(source_home),
                    "CODEX_HOME": str(source_home / ".codex"),
                    "BUDDYSWITCH_SOURCE_HOME": str(source_home),
                    "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
                    "BUDDYSWITCH_REPO_ROOT": str(ROOT),
                    "BUDDYSWITCH_TEST_INSTANCE_ROOT": str(instance_root),
                    "BUDDYSWITCH_TEST_INSTANCE_JSON": str(instance_json),
                    "BUDDYSWITCH_TEST_FAKE_CHROME_PORT": str(fake_port),
                    "BUDDYSWITCH_TEST_FAKE_CHROME_STATE": str(fake_chrome_state),
                    "BUDDYSWITCH_TEST_FAKE_CHROME_SERVER": str(fake_chrome),
                    "BUDDYSWITCH_TEST_BROWSER_ENSURE_CALLS": str(ensure_calls),
                    "BUDDYSWITCH_BROWSER_COCKPIT_ENSURE_COMMAND": f"{sys.executable} {ensure_script}",
                    "BUDDYSWITCH_SEARCH_BROWSER_ENSURE_COMMAND": f"{sys.executable} {ensure_script}",
                    "BUDDYSWITCH_TEST_UPSTREAM_ARGV": str(upstream_argv),
                    "BUDDYSWITCH_TEST_UPSTREAM_CALLS": str(upstream_calls),
                    "NO_PROXY": "127.0.0.1,localhost",
                    "no_proxy": "127.0.0.1,localhost",
                }
            )

            with patch.dict(os.environ, base_env, clear=False):
                proxy = self._start_proxy(instance_root=instance_root, upstream=fake_upstream, env=base_env)

                first_proxy_response = self._send_proxy_tool_call(
                    proxy,
                    request_id=1,
                    tool_name="list_pages",
                    arguments={},
                )
                self.assertFalse(first_proxy_response.get("result", {}).get("isError"), msg=first_proxy_response)
                self.assertTrue((instance_root / "runtime" / "browser" / "cockpit-upstream.pid").exists())
                self.assertTrue((instance_root / "runtime" / "browser" / "cockpit-upstream.pgid").exists())
                self.assertTrue(port_accepts(fake_port))
                self.assertTrue(read_jsonl(upstream_argv), "first browser call must start upstream MCP")
                self.assertTrue(read_jsonl(ensure_calls)[0]["started"], "first browser call must launch fake runtime")

                search_response = self._dispatch_search_open_browser(instance_json=instance_json, actor_id=actor_id, role=role)
                self.assertTrue(search_response.get("ok"), msg=search_response)
                self.assertEqual(search_response.get("page_opened"), True, msg=search_response)
                self.assertEqual(search_schedules[-1]["trigger_type"], "browser.page.expired")
                self.assertEqual(search_schedules[-1]["schedule_key"], "browser.page.idle:target-1")
                page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
                targets = page_idle.get("targets")
                self.assertIsInstance(targets, dict, msg=page_idle)
                assert isinstance(targets, dict)
                self.assertEqual(list(targets), ["target-1"])

                page_handler = load_module(PAGE_EXPIRED_HANDLER)
                release_handler = load_module(RELEASE_HANDLER)
                triggers = load_module(TRIGGERS)

                def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
                    release_schedules.append(dict(kwargs))
                    return {"schedule": {"schedule_id": "schedule-release"}}

                page_handler.browser_lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger
                context = self._handler_context(instance_root=instance_root, instance_json=instance_json, actor_id=actor_id, role=role)
                page_result = page_handler.BrowserPageExpiredHandler().handle(
                    context,
                    state=object(),
                    runtime=FakeRuntime(),
                    trigger=self._page_trigger(triggers, actor_id=actor_id, role=role, target_id="target-1"),
                )
                self.assertEqual(page_result.status, "handled", msg=getattr(page_result, "message", None))
                self.assertEqual(release_schedules[-1]["trigger_type"], "browser.cockpit.release")
                self.assertEqual(release_schedules[-1]["schedule_key"], "browser.cockpit.release")
                page_idle_after_close = json.loads(
                    (instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8")
                )
                self.assertEqual(page_idle_after_close["targets"], {})
                self.assertEqual(json.loads(fake_chrome_state.read_text(encoding="utf-8"))["targets"], [])

                release_result = release_handler.BrowserReleaseHandler().handle(
                    context,
                    state=object(),
                    runtime=FakeRuntime(),
                    trigger=self._release_trigger(triggers, actor_id=actor_id, role=role),
                )
                self.assertEqual(release_result.status, "handled", msg=getattr(release_result, "message", None))
                self.assertIsNone(json.loads(instance_json.read_text(encoding="utf-8")).get("browser_port"))
                self.assertFalse((instance_root / "runtime" / "browser" / "cockpit-upstream.pid").exists())
                self.assertFalse((instance_root / "runtime" / "browser" / "cockpit-upstream.pgid").exists())
                self.assertFalse((instance_root / "runtime" / "browser" / "page_idle.json").exists())
                self.assertFalse((instance_root / "runtime" / "browser" / "page_idle.lock").exists())
                self.assertFalse((instance_root / "browser" / "chrome.pid").exists())
                self.assertTrue(wait_until(lambda: not port_accepts(fake_port)), "release must stop fake Chrome endpoint")

                second_proxy_response = self._send_proxy_tool_call(
                    proxy,
                    request_id=2,
                    tool_name="list_pages",
                    arguments={},
                )
                self.assertFalse(second_proxy_response.get("result", {}).get("isError"), msg=second_proxy_response)
                self.assertTrue(port_accepts(fake_port))
                self.assertEqual(len(read_jsonl(upstream_argv)), 2, "next browser call must restart upstream MCP")
                start_events = [entry for entry in read_jsonl(ensure_calls) if entry.get("started") is True]
                self.assertGreaterEqual(len(start_events), 2, "next browser call must relaunch fake runtime")

                final_release = self._launcher_release(actor_id=actor_id, env=base_env)
                self.assertEqual(final_release.returncode, 0, msg=f"stdout:\n{final_release.stdout}\nstderr:\n{final_release.stderr}")
                self.assertTrue(wait_until(lambda: not port_accepts(fake_port)), "cleanup release must stop fake Chrome endpoint")


if __name__ == "__main__":
    unittest.main()
