"""Real Codex App Server harness for native Goal contract tests."""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable, Iterable

import zstandard

from tests.support.paths import REPO_ROOT
from tests.support.processes import CleanupReport, ResourceLedger
import app_server
import codex_runtime


DEFAULT_TIMEOUT_SECONDS = 20.0


def _event_stream(events: Iterable[dict[str, Any]]) -> bytes:
    chunks: list[str] = []
    for event in events:
        event_type = str(event["type"])
        chunks.append(f"event: {event_type}\ndata: {json.dumps(event, separators=(',', ':'))}\n\n")
    return "".join(chunks).encode("utf-8")


def response_created(response_id: str) -> dict[str, Any]:
    return {
        "type": "response.created",
        "response": {"id": response_id},
    }


def response_completed(response_id: str, *, total_tokens: int = 0) -> dict[str, Any]:
    return {
        "type": "response.completed",
        "response": {
            "id": response_id,
            "usage": {
                "input_tokens": total_tokens,
                "input_tokens_details": None,
                "output_tokens": 0,
                "output_tokens_details": None,
                "total_tokens": total_tokens,
            },
        },
    }


def assistant_message(message_id: str, text: str) -> dict[str, Any]:
    return {
        "type": "response.output_item.done",
        "item": {
            "type": "message",
            "role": "assistant",
            "id": message_id,
            "content": [{"type": "output_text", "text": text}],
        },
    }


def function_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "response.output_item.done",
        "item": {
            "type": "function_call",
            "call_id": call_id,
            "name": name,
            "arguments": json.dumps(arguments, separators=(",", ":")),
        },
    }


@dataclass(frozen=True)
class ResponseSpec:
    status: int
    content_type: str
    body: bytes

    @classmethod
    def sse(cls, *events: dict[str, Any]) -> "ResponseSpec":
        return cls(status=200, content_type="text/event-stream", body=_event_stream(events))

    @classmethod
    def server_error(cls, message: str) -> "ResponseSpec":
        return cls(
            status=500,
            content_type="application/json",
            body=json.dumps({"error": {"message": message}}, separators=(",", ":")).encode("utf-8"),
        )


ResponseProvider = ResponseSpec | Callable[[dict[str, Any], int], ResponseSpec]


class SequencedResponsesServer:
    """Loopback Responses API server with deterministic, captured requests."""

    def __init__(self, responses: list[ResponseProvider]) -> None:
        self._responses = list(responses)
        self._requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                if "zstd" in self.headers.get("Content-Encoding", "").lower():
                    body = zstandard.ZstdDecompressor().decompress(body)
                try:
                    payload: Any = json.loads(body)
                except json.JSONDecodeError:
                    payload = {"_invalid_json": body.decode("utf-8", errors="replace")}
                with owner._condition:
                    request_index = len(owner._requests)
                    request_record = {
                        "path": self.path,
                        "headers": {key.lower(): value for key, value in self.headers.items()},
                        "body": payload,
                    }
                    owner._requests.append(request_record)
                    provider = (
                        owner._responses[request_index]
                        if request_index < len(owner._responses)
                        else ResponseSpec.server_error(
                            f"unexpected Responses request {request_index + 1}"
                        )
                    )
                    owner._condition.notify_all()
                spec = (
                    provider(request_record, request_index)
                    if callable(provider)
                    else provider
                )
                self.send_response(spec.status)
                self.send_header("Content-Type", spec.content_type)
                self.send_header("Content-Length", str(len(spec.body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(spec.body)
                self.wfile.flush()

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="buddyswitch-goal-responses",
            daemon=True,
        )

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address
        return f"http://{host}:{port}"

    @property
    def requests(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(request) for request in self._requests]

    def start(self) -> None:
        self._thread.start()

    def wait_for_request_count(
        self,
        count: int,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout_seconds
        with self._condition:
            while len(self._requests) < count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(
                        f"expected {count} Responses requests, observed {len(self._requests)}"
                    )
                self._condition.wait(timeout=remaining)
            return [dict(request) for request in self._requests]

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=2.0)
        if self._thread.is_alive():
            raise AssertionError("Responses server thread did not stop")


class RealCodexGoalHarness:
    """Start the installed Codex App Server against a deterministic model endpoint."""

    def __init__(self, responses: list[ResponseProvider]) -> None:
        self.ledger = ResourceLedger.from_environment()
        self.runtime = codex_runtime.resolve_codex_runtime()
        self.root = Path(tempfile.mkdtemp(prefix="buddyswitch-goal-")).resolve()
        self.ledger.register_path(self.root, path_type="native_goal_root")
        self.codex_home = self.root / "codex-home"
        self.workspace = self.root / "workspace"
        self.runtime_dir = self.root / "runtime"
        self.codex_home.mkdir()
        self.workspace.mkdir()
        self.runtime_dir.mkdir()
        self.socket_path = self.runtime_dir / "app-server.sock"
        self.log_path = self.runtime_dir / "app-server.log"
        self.responses = SequencedResponsesServer(responses)
        self.responses.start()
        self.thread_start_result: dict[str, Any] | None = None
        self.materialize_completion: dict[str, Any] | None = None
        self.log_text = ""
        self._write_config()
        environment = dict(os.environ)
        environment.update(
            {
                "CODEX_HOME": str(self.codex_home),
                "OPENAI_API_KEY": "buddyswitch-goal-test",
                "NO_PROXY": "127.0.0.1,localhost",
                "RUST_LOG": "warn",
                "no_proxy": "127.0.0.1,localhost",
            }
        )
        with self.log_path.open("w", encoding="utf-8") as log_handle:
            self.process = self.ledger.start_process(
                [
                    str(self.runtime.executable),
                    "app-server",
                    "--listen",
                    f"unix://{self.socket_path}",
                ],
                cwd=self.workspace,
                env=environment,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )
        self.process_group = os.getpgid(self.process.pid)
        self.cleanup_report: CleanupReport | None = None
        self._closed = False
        self._wait_until_ready()

    def _write_config(self) -> None:
        (self.codex_home / "config.toml").write_text(
            "\n".join(
                (
                    'model = "mock-model"',
                    'model_provider = "mock_provider"',
                    'approval_policy = "never"',
                    'sandbox_mode = "read-only"',
                    "",
                    "[features]",
                    "goals = true",
                    "",
                    "[model_providers.mock_provider]",
                    'name = "BuddySwitch native Goal test"',
                    f'base_url = "{self.responses.base_url}/v1"',
                    'wire_api = "responses"',
                    "request_max_retries = 0",
                    "stream_max_retries = 0",
                    "supports_websockets = false",
                    "",
                )
            ),
            encoding="utf-8",
        )

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + DEFAULT_TIMEOUT_SECONDS
        last_error: BaseException | None = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise AssertionError(
                    f"Codex app-server exited early ({self.process.returncode}):\n"
                    f"{self.log_path.read_text(encoding='utf-8', errors='replace')}"
                )
            if self.socket_path.exists():
                try:
                    with app_server.AppServerClient(
                        self.socket_path,
                        timeout_seconds=2.0,
                    ) as client:
                        client.request("thread/loaded/list", {"cursor": None, "limit": 1})
                    return
                except BaseException as exc:
                    last_error = exc
            time.sleep(0.05)
        raise AssertionError(
            f"Codex app-server did not become ready: {last_error}\n"
            f"{self.log_path.read_text(encoding='utf-8', errors='replace')}"
        )

    def client(self) -> app_server.AppServerClient:
        client = app_server.AppServerClient(
            self.socket_path,
            timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        )
        client.connect()
        client.initialize()
        return client

    def materialize_thread(self, client: app_server.AppServerClient) -> str:
        started = client.request(
            "thread/start",
            {
                "cwd": str(self.workspace),
                "runtimeWorkspaceRoots": [str(self.workspace)],
                "model": "mock-model",
                "ephemeral": False,
            },
        )
        self.thread_start_result = dict(started)
        thread = started.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise AssertionError(f"thread/start returned no thread id: {started!r}")
        thread_id = str(thread["id"])
        client.request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [
                    {
                        "type": "text",
                        "text": "Materialize this persistent Goal contract thread.",
                        "text_elements": [],
                    }
                ],
            },
        )
        self.materialize_completion = self.wait_for_notification(
            client,
            "turn/completed",
            thread_id=thread_id,
        )
        return thread_id

    @staticmethod
    def wait_for_notification(
        client: app_server.AppServerClient,
        method: str,
        *,
        thread_id: str | None = None,
        goal_status: str | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + DEFAULT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            notification = client.read_notification()
            if notification.get("method") != method:
                continue
            params = notification.get("params")
            if not isinstance(params, dict):
                continue
            if thread_id is not None and params.get("threadId") != thread_id:
                continue
            goal = params.get("goal")
            if goal_status is not None and (
                not isinstance(goal, dict) or goal.get("status") != goal_status
            ):
                continue
            return dict(params)
        raise AssertionError(
            f"did not observe notification {method} for thread={thread_id!r} "
            f"goal_status={goal_status!r}"
        )

    def wait_for_goal_status(
        self,
        thread_id: str,
        status: str,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        observed: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            result = app_server.goal_get(self.socket_path, thread_id)
            goal = result.get("goal")
            if isinstance(goal, dict):
                observed = dict(goal)
                if goal.get("status") == status:
                    return observed
            time.sleep(0.05)
        raise AssertionError(f"Goal did not reach {status!r}; last observed={observed!r}")

    def feature_output(self) -> str:
        completed = subprocess.run(
            [str(self.runtime.executable), "features", "list"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
            env={**os.environ, "CODEX_HOME": str(self.codex_home)},
        )
        if completed.returncode != 0:
            raise AssertionError(f"codex features list failed: {completed.stderr}")
        return completed.stdout

    def close(self) -> CleanupReport:
        if self._closed:
            assert self.cleanup_report is not None
            return self.cleanup_report
        self._closed = True
        self.responses.close()
        self.cleanup_report = self.ledger.cleanup_registered_process(
            self.process.pid,
            expected_pgid=self.process_group,
        )
        kill_error: PermissionError | None = None
        if not self._wait_for_process_group_exit(timeout_seconds=2.0):
            try:
                os.killpg(self.process_group, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError as exc:
                kill_error = exc
        if not self._wait_for_process_group_exit(timeout_seconds=2.0):
            detail = (
                f"; signal denied: {kill_error}"
                if kill_error is not None
                else ""
            )
            self.cleanup_report.residuals.append(
                "Codex app-server process group remains: "
                f"pgid={self.process_group}{detail}"
            )
        self.log_text = self.log_path.read_text(encoding="utf-8", errors="replace")
        self.socket_path.unlink(missing_ok=True)
        if not self.cleanup_report.residuals:
            shutil.rmtree(self.root, ignore_errors=False)
        return self.cleanup_report

    def _wait_for_process_group_exit(self, *, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not self._live_process_group_members():
                return True
            time.sleep(0.02)
        return not self._live_process_group_members()

    def _live_process_group_members(self) -> list[int]:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,pgid=,stat="],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "cannot inspect Codex app-server process group: "
                f"{completed.stderr.strip()}"
            )
        members: list[int] = []
        for line in completed.stdout.splitlines():
            fields = line.split()
            if len(fields) < 3:
                continue
            try:
                pid = int(fields[0])
                pgid = int(fields[1])
            except ValueError:
                continue
            if pgid == self.process_group and not fields[2].startswith("Z"):
                members.append(pid)
        return members


def completed_response(response_id: str, text: str) -> ResponseSpec:
    return ResponseSpec.sse(
        response_created(response_id),
        assistant_message(f"msg-{response_id}", text),
        response_completed(response_id),
    )


def update_goal_response(response_id: str, status: str) -> ResponseSpec:
    return ResponseSpec.sse(
        response_created(response_id),
        function_call(
            f"call-{response_id}",
            "update_goal",
            {"status": status},
        ),
        response_completed(response_id),
    )


def request_has_tool(request: dict[str, Any], tool_name: str) -> bool:
    body = request.get("body")
    if not isinstance(body, dict):
        return False
    tools = body.get("tools")
    if not isinstance(tools, list):
        return False
    return any(
        isinstance(tool, dict) and tool.get("name") == tool_name
        for tool in tools
    )


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "REPO_ROOT",
    "RealCodexGoalHarness",
    "ResponseSpec",
    "completed_response",
    "request_has_tool",
    "update_goal_response",
]
