"""Local web management UI and API for BuddySwitch instances."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit
from uuid import uuid4

HELPER_DIR = Path(__file__).resolve().parent
SCRIPTS = HELPER_DIR.parents[1] / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import web_im_identity
import im_http_router
import imessage_channel
import host_control as host_control_module
import actor_session
import cli_contract
import codex_runtime
from env.domain import task_read, track_read
from env.domain.identity import ActorIdentityProfile, IdentityRef
from env.repos import runtime_files
from env.tool_runtime import daemon_client
from env.tool_runtime import im_actor_delivery
import external_im_session


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = HELPER_DIR / "assets" / "web-management"
STATIC_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}
LOCAL_BIND_HOSTS = {"127.0.0.1", "localhost"}


@dataclass(frozen=True)
class HttpError(Exception):
    status: int
    code: str
    message: str
    details: dict[str, Any] | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _lifecycle_action_label(action: str) -> str:
    if action == "start":
        return "Start"
    if action == "stop":
        return "Stop"
    if action == "resume":
        return "Resume"
    if action == "clear":
        return "Clear"
    if action == "delete":
        return "Delete"
    return "Lifecycle action"


@dataclass
class WebLifecycleOperation:
    id: str
    action: str
    status: str
    label: str
    detail: str
    target: dict[str, str]
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    started_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "status": self.status,
            "label": self.label,
            "detail": self.detail,
            "target": dict(self.target),
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
        }


class TerminalOpenError(Exception):
    """Raised when the host cannot ask Terminal.app to open the attach command."""


class BusyGuard:
    def __init__(self) -> None:
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def acquire(self, key: str) -> bool:
        with self._lock:
            if key in self._active:
                return False
            self._active.add(key)
            return True

    def release(self, key: str) -> None:
        with self._lock:
            self._active.discard(key)


def validate_bind_host(host: str) -> str:
    if host not in LOCAL_BIND_HOSTS:
        raise ValueError("BuddySwitch web host must stay local to 127.0.0.1 or localhost.")
    return host


def bind_web_runtime_state() -> None:
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(raw_shared_root, str) and raw_shared_root.strip():
        shared_root = Path(raw_shared_root.strip()).expanduser()
        os.environ["BUDDYSWITCH_STATE_ROOT"] = str(shared_root / "state")
    runtime_files.refresh_runtime_roots_from_env()


def map_host_control_failure(error: host_control_module.HostControlError) -> HttpError:
    if error.timed_out or error.code == "COMMAND_TIMEOUT":
        return HttpError(status=504, code="COMMAND_TIMEOUT", message=error.message)
    if error.code == "CAPABILITY_CONFIG_INVALID":
        return HttpError(status=409, code="CAPABILITY_CONFIG_INVALID", message=error.message)
    if error.code == "CAPABILITY_CONFIG_WRITE_FAILED":
        return HttpError(status=502, code="CAPABILITY_CONFIG_WRITE_FAILED", message=error.message)
    if error.code in {"INVALID_REQUEST"} or error.returncode == 2:
        return HttpError(status=400, code="INVALID_REQUEST", message=error.message)
    if error.code == "NOT_FOUND":
        return HttpError(status=404, code="NOT_FOUND", message=error.message)
    if error.code == "RUNTIME_MISMATCH":
        return HttpError(status=409, code="RUNTIME_MISMATCH", message=error.message)
    if error.code == "RUNTIME_UNAVAILABLE":
        return HttpError(status=503, code="RUNTIME_UNAVAILABLE", message=error.message)
    if error.code in {"LIFECYCLE_BLOCKED", "LOCK_BUSY"} or error.returncode in {3, 4}:
        return HttpError(status=409, code="LIFECYCLE_BLOCKED", message=error.message)
    return HttpError(status=502, code="COMMAND_FAILED", message=error.message)


def map_actor_session_failure(error: actor_session.ActorSessionError) -> HttpError:
    message = str(error)
    if message == "invalid actor id":
        return HttpError(status=400, code="INVALID_REQUEST", message="Invalid actor id.")
    if message.startswith("actor not found:"):
        actor_id = message.split(":", 1)[1].strip()
        return HttpError(status=404, code="NOT_FOUND", message=f"actor instance not found: {actor_id}")
    if message.startswith("actor has no thread id"):
        return HttpError(status=409, code="OPEN_TUI_BLOCKED", message="No thread to attach.")
    if message.startswith("actor app server unhealthy"):
        return HttpError(status=409, code="OPEN_TUI_BLOCKED", message="Instance is unhealthy.")
    return HttpError(status=502, code="COMMAND_FAILED", message=message)


def map_codex_runtime_failure(error: codex_runtime.CodexRuntimeError) -> HttpError:
    return HttpError(status=409, code="RUNTIME_MISMATCH", message=str(error))


def create_server(host: str, port: int, service: "WebManagementService") -> ThreadingHTTPServer:
    validate_bind_host(host)

    class WebManagementServer(ThreadingHTTPServer):
        daemon_threads = True

    class Handler(BaseHTTPRequestHandler):
        server_version = "BuddySwitchWeb/1.0"

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch()

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch()

        def do_PATCH(self) -> None:  # noqa: N802
            self._dispatch()

        def do_PUT(self) -> None:  # noqa: N802
            self._dispatch()

        def do_DELETE(self) -> None:  # noqa: N802
            self._dispatch()

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _dispatch(self) -> None:
            try:
                parsed = urlsplit(self.path)
                if parsed.path == "/":
                    self._serve_static(STATIC_ROOT / "index.html", "text/html; charset=utf-8")
                    return
                if parsed.path.startswith("/static/"):
                    self._serve_static_request(parsed.path)
                    return
                if parsed.path.startswith("/api/"):
                    api_path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
                    self._serve_json(*service.handle_api(self.command, api_path, self._read_body(), self.headers))
                    return
                self._serve_html_404()
            except HttpError as exc:
                error_payload: dict[str, Any] = {"code": exc.code, "message": exc.message}
                if exc.details:
                    error_payload.update(exc.details)
                self._serve_json(
                    exc.status,
                    {"ok": False, "error": error_payload},
                )

        def _read_body(self) -> bytes:
            length = self.headers.get("Content-Length")
            if not length:
                return b""
            return self.rfile.read(int(length))

        def _serve_static(self, path: Path, content_type: str) -> None:
            if not path.is_file():
                self._serve_html_404()
                return
            payload = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _serve_static_request(self, request_path: str) -> None:
            relative_path = request_path[len("/static/") :]
            if not relative_path or "\x00" in relative_path:
                self._serve_html_404()
                return
            static_root = STATIC_ROOT.resolve()
            candidate = (STATIC_ROOT / relative_path).resolve()
            if candidate != static_root and static_root not in candidate.parents:
                self._serve_html_404()
                return
            content_type = STATIC_CONTENT_TYPES.get(candidate.suffix)
            if content_type is None:
                self._serve_html_404()
                return
            self._serve_static(candidate, content_type)

        def _serve_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_html_404(self) -> None:
            body = b"<!doctype html><html><body><h1>Not Found</h1></body></html>"
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return WebManagementServer((host, port), Handler)


def create_imessage_channel_worker(server_url: str) -> imessage_channel.ImessageChannelWorker:
    config = imessage_channel.ChannelConfig(server=server_url)
    controller = imessage_channel.ImessageChannelController(config=config)
    return imessage_channel.ImessageChannelWorker(controller)


def serve_with_imessage_worker(server: Any, worker: Any) -> None:
    worker_started = False
    try:
        try:
            worker.start()
            worker_started = True
        except Exception as exc:
            sys.stderr.write(f"iMessage channel worker disabled: {exc}\n")
            sys.stderr.flush()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    finally:
        if worker_started:
            worker.stop()
        server.server_close()


class WebManagementService:
    def __init__(
        self,
        *,
        repo_root: Path,
        host_control: host_control_module.HostControl | None = None,
        terminal_opener: Callable[[str], None] | None = None,
        web_im_identity_provider: web_im_identity.WebImIdentityProvider | None = None,
        im_session: external_im_session.ExternalImSession | None = None,
        platform_name: str | None = None,
        busy_guard: BusyGuard | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._host_control = host_control or host_control_module.HostControl(repo_root=repo_root)
        self._terminal_opener = terminal_opener or open_macos_terminal_app
        self._platform_name = platform_name or sys.platform
        self._busy_guard = busy_guard or BusyGuard()
        self._operation_lock = threading.Lock()
        self._operations: dict[str, WebLifecycleOperation] = {}
        self._operation_commands: dict[str, Callable[[], dict[str, Any]]] = {}
        self._lifecycle_queue: list[str] = []
        self._lifecycle_running_operation_id: str | None = None
        self._im_session = im_session or external_im_session.ExternalImSession(
            actor_lister=self._external_im_actor_rows,
            actor_reachability_checker=self._check_im_actor_reachability,
            actor_delivery_handler=self._deliver_im_actor,
        )
        self._web_im_identity = web_im_identity_provider or web_im_identity.WebImIdentityProvider(
            im_session=self._im_session
        )
        self._im_router = im_http_router.ImHttpRouter(
            actor_lister=self._external_im_actor_rows,
            actor_reachability_checker=self._check_im_actor_reachability,
            actor_delivery_handler=self._deliver_im_actor,
            im_session=self._im_session,
            web_external_session_provider=self.ensure_web_im_identity,
        )

    def handle_api(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        parsed = urlsplit(path)
        route = parsed.path
        if method == "GET" and path == "/api/health":
            return 200, {"ok": True}
        if method == "GET" and path == "/api/roles":
            return 200, {"ok": True, "roles": self._list_roles()}
        if method == "GET" and path == "/api/instances":
            return 200, {"ok": True, "instances": self._list_instances()}
        if method == "POST" and path == "/api/instances":
            return 202, self._create_instance(body)
        if method == "GET" and route == "/api/actors":
            return 200, {"ok": True, "actors": self._list_actor_rows()}
        operation_id = self._parse_operation_path(route)
        if method == "GET" and operation_id is not None:
            return 200, self._get_operation(operation_id)
        actor_capability_id = self._parse_actor_capability_path(route)
        if actor_capability_id is not None:
            if method == "GET":
                return 200, self._read_actor_capabilities(actor_capability_id)
            if method == "PUT":
                return 200, self._replace_actor_capabilities(actor_capability_id, body)
            raise HttpError(status=404, code="NOT_FOUND", message="API route not found.")
        actor_console_id = self._parse_actor_console_path(route)
        if method == "GET" and actor_console_id is not None:
            return 200, {"ok": True, "console": self._actor_console(actor_console_id)}
        if method == "GET" and route == "/api/tracks":
            return 200, {"ok": True, "tracks": track_read.list_external_tracks()}
        track_id = self._parse_track_detail_path(route)
        if method == "GET" and track_id is not None:
            try:
                detail = track_read.get_external_track(track_id)
            except ValueError as exc:
                raise HttpError(status=400, code="INVALID_REQUEST", message=str(exc)) from exc
            if detail is None:
                raise HttpError(status=404, code="NOT_FOUND", message=f"track not found: {track_id}")
            return 200, {"ok": True, "track": detail}
        if route.startswith("/api/im/"):
            return self._im_router.handle(method, path, body, headers)

        instance_action = self._parse_instance_action_path(path)
        if instance_action is None:
            raise HttpError(status=404, code="NOT_FOUND", message="API route not found.")
        actor_id, action = instance_action
        if method == "GET" and action == "status":
            return 200, {"ok": True, "instance": self._get_instance_status(actor_id)}
        if method == "GET" and action == "attach-command":
            return 200, self._attach_command(actor_id)
        if method == "POST" and action == "clear":
            return 202, self._clear(actor_id)
        if method == "POST" and action == "interrupt":
            return 200, self._interrupt(actor_id)
        if method == "POST" and action == "resume":
            return 202, self._resume(actor_id)
        if method == "POST" and action == "stop":
            return 202, self._stop(actor_id)
        if method == "POST" and action == "open-tui":
            return 200, self._open_tui(actor_id, body, headers)
        if method == "DELETE" and action == "delete":
            return 202, self._delete(actor_id)
        raise HttpError(status=404, code="NOT_FOUND", message="API route not found.")

    def _parse_operation_path(self, path: str) -> str | None:
        prefix = "/api/operations/"
        if not path.startswith(prefix):
            return None
        operation_id = path[len(prefix):]
        if not operation_id or "/" in operation_id:
            return None
        return operation_id

    def _get_operation(self, operation_id: str) -> dict[str, Any]:
        with self._operation_lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                raise HttpError(status=404, code="NOT_FOUND", message="Operation not found.")
            return {"ok": True, "operation": operation.to_payload()}

    def _parse_instance_action_path(self, path: str) -> tuple[str, str] | None:
        status_prefix = "/api/instances/"
        if path.startswith(status_prefix) and path.endswith("/status"):
            return path[len(status_prefix) : -len("/status")], "status"
        if path.startswith(status_prefix) and path.endswith("/clear"):
            return path[len(status_prefix) : -len("/clear")], "clear"
        if path.startswith(status_prefix) and path.endswith("/interrupt"):
            return path[len(status_prefix) : -len("/interrupt")], "interrupt"
        if path.startswith(status_prefix) and path.endswith("/resume"):
            return path[len(status_prefix) : -len("/resume")], "resume"
        if path.startswith(status_prefix) and path.endswith("/stop"):
            return path[len(status_prefix) : -len("/stop")], "stop"
        if path.startswith(status_prefix) and path.endswith("/open-tui"):
            return path[len(status_prefix) : -len("/open-tui")], "open-tui"
        if path.startswith(status_prefix) and path.endswith("/attach-command"):
            return path[len(status_prefix) : -len("/attach-command")], "attach-command"
        if path.startswith(status_prefix):
            actor_id = path[len(status_prefix) :]
            if "/" in actor_id:
                return None
            return actor_id, "delete"
        return None

    def _parse_actor_capability_path(self, path: str) -> str | None:
        prefix = "/api/actors/"
        suffix = "/capabilities"
        if path.startswith(prefix) and path.endswith(suffix):
            actor_id = path[len(prefix) : -len(suffix)]
            if "/" not in actor_id:
                return actor_id
        return None

    def _parse_actor_console_path(self, path: str) -> str | None:
        prefix = "/api/actors/"
        suffix = "/console"
        if path.startswith(prefix) and path.endswith(suffix):
            return path[len(prefix) : -len(suffix)]
        return None

    def _parse_track_detail_path(self, path: str) -> str | None:
        prefix = "/api/tracks/"
        if path.startswith(prefix):
            track_id = path[len(prefix) :]
            if "/" not in track_id:
                return track_id
        return None

    def ensure_web_im_identity(self) -> dict[str, Any]:
        try:
            return self._web_im_identity.ensure()
        except web_im_identity.WebImIdentityError as exc:
            raise HttpError(status=502, code="IM_IDENTITY_FAILED", message=str(exc)) from exc
        except ValueError as exc:
            raise HttpError(status=409, code="IM_IDENTITY_BLOCKED", message=str(exc)) from exc

    def _create_instance(self, body: bytes) -> dict[str, Any]:
        payload = self._parse_json_body(body)
        role = payload.get("role")
        if not isinstance(role, str) or not role.strip():
            raise HttpError(status=400, code="INVALID_REQUEST", message="role is required.")
        role_id = role.strip()
        roles_by_id = {row["id"]: row for row in self._list_roles()}
        role_row = roles_by_id.get(role_id)
        if role_row is None:
            raise HttpError(status=400, code="INVALID_REQUEST", message=f"Unknown role: {role_id}")
        role_label = str(role_row.get("label") or role_id)
        return self._start_lifecycle_operation(
            key="start",
            action="start",
            label=f"Starting {role_label}",
            detail="Launcher start command is queued.",
            target={"actor_id": "", "role": role_id},
            command=lambda: self._create_instance_under_lock(role_id),
        )

    def _create_instance_under_lock(self, role: str) -> dict[str, Any]:
        payload = self._call_host_control(lambda: self._host_control.start(role))
        actor_id = payload.get("actor_id")
        if not isinstance(actor_id, str) or not actor_id:
            raise HttpError(status=502, code="COMMAND_FAILED", message=f"Invalid start payload for role {role}.")
        return {"ok": True, "actor_id": actor_id, "instance": self._get_instance_status(actor_id)}

    def _clear(self, actor_id: str) -> dict[str, Any]:
        return self._start_lifecycle_operation(
            key=f"instance:{actor_id}",
            action="clear",
            label=f"Clearing thread for {actor_id}",
            detail="Launcher clear command is queued.",
            target={"actor_id": actor_id, "role": ""},
            command=lambda: self._clear_under_lock(actor_id),
        )

    def _clear_under_lock(self, actor_id: str) -> dict[str, Any]:
        cleared = self._call_host_control(lambda: self._host_control.clear(actor_id))
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(actor_id)}
        previous_thread_id = cleared.get("previous_thread_id")
        thread_id = cleared.get("thread_id")
        if isinstance(previous_thread_id, str):
            payload["previous_thread_id"] = previous_thread_id
        if isinstance(thread_id, str):
            payload["thread_id"] = thread_id
        return payload

    def _interrupt(self, actor_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{actor_id}",
            lambda: self._interrupt_under_lock(actor_id),
        )

    def _interrupt_under_lock(self, actor_id: str) -> dict[str, Any]:
        parsed = self._call_host_control(lambda: self._host_control.interrupt(actor_id))
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(actor_id)}
        turn_id = parsed.get("turn_id")
        if isinstance(turn_id, str):
            payload["turn_id"] = turn_id
        return payload

    def _stop(self, actor_id: str) -> dict[str, Any]:
        return self._start_lifecycle_operation(
            key=f"instance:{actor_id}",
            action="stop",
            label=f"Stopping {actor_id}",
            detail="Launcher stop command is queued.",
            target={"actor_id": actor_id, "role": ""},
            command=lambda: self._stop_under_lock(actor_id),
        )

    def _stop_under_lock(self, actor_id: str) -> dict[str, Any]:
        self._call_host_control(lambda: self._host_control.stop(actor_id))
        return {"ok": True, "instance": self._get_instance_status(actor_id)}

    def _resume(self, actor_id: str) -> dict[str, Any]:
        return self._start_lifecycle_operation(
            key=f"instance:{actor_id}",
            action="resume",
            label=f"Resuming {actor_id}",
            detail="Launcher resume command is queued.",
            target={"actor_id": actor_id, "role": ""},
            command=lambda: self._resume_under_lock(actor_id),
        )

    def _resume_under_lock(self, actor_id: str) -> dict[str, Any]:
        self._call_host_control(lambda: self._host_control.resume(actor_id))
        return {"ok": True, "instance": self._get_instance_status(actor_id)}

    def _delete(self, actor_id: str) -> dict[str, Any]:
        return self._start_lifecycle_operation(
            key=f"instance:{actor_id}",
            action="delete",
            label=f"Deleting {actor_id}",
            detail="Launcher delete command is queued.",
            target={"actor_id": actor_id, "role": ""},
            command=lambda: self._delete_under_lock(actor_id),
        )

    def _delete_under_lock(self, actor_id: str) -> dict[str, Any]:
        self._call_host_control(lambda: self._host_control.delete(actor_id))
        return {"ok": True, "actor_id": actor_id}

    def _open_tui(
        self,
        actor_id: str,
        body: bytes,
        headers: Mapping[str, str] | None,
    ) -> dict[str, Any]:
        self._validate_open_tui_request(headers, body)
        try:
            descriptor = actor_session.ActorSession(
                shared_root=self._shared_root(),
                repo_root=self._repo_root,
            ).resolve_attach(actor_id)
        except actor_session.ActorSessionError as exc:
            raise map_actor_session_failure(exc) from exc
        except codex_runtime.CodexRuntimeError as exc:
            raise map_codex_runtime_failure(exc) from exc
        command = build_terminal_attach_command(descriptor)
        if self._platform_name != "darwin":
            raise HttpError(
                status=400,
                code="UNSUPPORTED_PLATFORM",
                message="Could not open Terminal.",
            )
        try:
            self._terminal_opener(command)
        except TerminalOpenError as exc:
            raise HttpError(
                status=502,
                code="TERMINAL_OPEN_FAILED",
                message="Could not open Terminal.",
            ) from exc
        except Exception as exc:
            raise HttpError(
                status=502,
                code="TERMINAL_OPEN_FAILED",
                message="Could not open Terminal.",
            ) from exc
        return {
            "ok": True,
            "actor_id": actor_id,
            "terminal": "Terminal.app",
        }

    def _attach_command(self, actor_id: str) -> dict[str, Any]:
        try:
            normalized_actor_id = host_control_module.validate_actor_id(actor_id)
        except host_control_module.HostControlError as exc:
            raise map_host_control_failure(exc) from exc
        return {
            "ok": True,
            "actor_id": normalized_actor_id,
            "command": build_copy_attach_command(self._repo_root, normalized_actor_id),
        }

    def _validate_open_tui_request(self, headers: Mapping[str, str] | None, body: bytes) -> None:
        content_type = _header_value(headers, "Content-Type")
        if content_type is None or content_type.split(";", 1)[0].strip().lower() != "application/json":
            raise HttpError(
                status=400,
                code="INVALID_REQUEST",
                message="Content-Type must be application/json.",
            )
        web_header = _header_value(headers, "X-BuddySwitch-Web")
        if web_header != "1":
            raise HttpError(
                status=400,
                code="INVALID_REQUEST",
                message="X-BuddySwitch-Web header is required.",
            )
        host_header = _header_value(headers, "Host")
        host = _hostname_from_host_header(host_header)
        if host is not None and host not in LOCAL_BIND_HOSTS:
            raise HttpError(status=403, code="FORBIDDEN", message="Open TUI requires a local Host header.")
        origin_value = _header_value(headers, "Origin")
        if origin_value:
            parsed_origin = urlsplit(origin_value)
            origin_host = parsed_origin.hostname.lower() if parsed_origin.hostname else None
            if origin_host not in LOCAL_BIND_HOSTS:
                raise HttpError(status=403, code="FORBIDDEN", message="Open TUI requires a local Origin header.")
            if host is not None and origin_host != host:
                raise HttpError(status=403, code="FORBIDDEN", message="Open TUI requires same-origin headers.")
            host_netloc = _normalized_host_netloc(host_header)
            origin_netloc = parsed_origin.netloc.lower()
            if host_netloc is not None and origin_netloc != host_netloc:
                raise HttpError(status=403, code="FORBIDDEN", message="Open TUI requires same-origin headers.")
        payload = self._parse_json_body(body)
        if payload:
            raise HttpError(status=400, code="INVALID_REQUEST", message="open-tui does not accept request fields.")

    def _list_roles(self) -> list[dict[str, str]]:
        return self._call_host_control(self._host_control.roles)

    def _list_instances(self) -> list[dict[str, Any]]:
        return self._call_host_control(lambda: self._host_control.list_instances())

    def _runtime_row(self, instance: Mapping[str, Any]) -> dict[str, Any]:
        thread = instance.get("thread")
        thread_status = thread.get("status") if isinstance(thread, Mapping) else None
        app_server_health = instance.get("app_server_health")
        if not isinstance(app_server_health, str):
            app_server = instance.get("app_server")
            if isinstance(app_server, Mapping) and isinstance(app_server.get("healthy"), bool):
                app_server_health = "healthy" if app_server.get("healthy") else "unhealthy"
            else:
                app_server_health = ""
        return {
            "status": instance.get("status"),
            "app_server_health": app_server_health,
            "thread_id": instance.get("thread_id"),
            "thread_status": thread_status or "",
            "browser_port": instance.get("browser_port"),
            "updated_at": instance.get("updated_at"),
            "workspace_dir": instance.get("workspace_dir"),
        }

    def _actor_row_from_instance(self, instance: Mapping[str, Any]) -> dict[str, Any]:
        row = {
            "actor_id": instance.get("actor_id"),
            "role": instance.get("role"),
            "status": instance.get("status"),
            "app_server_health": instance.get("app_server_health"),
            "thread_id": instance.get("thread_id"),
            "browser_port": instance.get("browser_port"),
            "updated_at": instance.get("updated_at"),
            "workspace_dir": instance.get("workspace_dir"),
        }
        row["runtime"] = self._runtime_row(instance)
        return row

    def _list_actor_rows(self) -> list[dict[str, Any]]:
        return [self._actor_row_from_instance(instance) for instance in self._list_instances()]

    def _external_im_actor_rows(self, role_id: str | None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in self._list_actor_rows():
            if role_id is not None and row.get("role") != role_id:
                continue
            identity_id = row.get("actor_id")
            normalized_role = row.get("role")
            if not isinstance(identity_id, str) or not isinstance(normalized_role, str):
                continue
            rows.append(
                {
                    "identity_id": identity_id,
                    "identity": {"id": identity_id, "type": "actor"},
                    "role_id": normalized_role,
                    "status": row.get("status") if isinstance(row.get("status"), str) else "online",
                }
            )
        return rows

    def _actor_console(self, actor_id: str) -> dict[str, Any]:
        instance = self._get_instance_status(actor_id)
        role = instance.get("role")
        if not isinstance(role, str) or not role:
            raise HttpError(status=502, code="COMMAND_FAILED", message=f"Invalid instance status payload for {actor_id}.")
        current_identity = {"id": actor_id, "type": "actor"}
        task_projection = task_read.actor_external_task_projection(
            actor_profile=ActorIdentityProfile(
                identity=IdentityRef(id=actor_id, type="actor"),
                role_id=role,
            )
        )

        return {
            "actor": {"actor_id": actor_id, "role": role},
            "runtime": self._runtime_row(instance),
            "task_sys": {
                "active_count": task_projection["active_count"],
                "recoverable_count": task_projection["recoverable_count"],
                "active_tasks": task_projection["active_tasks"][:10],
                "recoverable_tasks": task_projection["recoverable_tasks"][:10],
            },
            "tracks": {
                "items": track_read.list_external_tracks(owner_identity=current_identity),
                "source": "web-track-summary",
            },
            "im": {
                "target": {
                    "identity": {"id": actor_id, "type": "actor"},
                    "identity_id": actor_id,
                    "role_id": role,
                }
            },
            "capabilities": self._read_actor_capabilities(actor_id)["capabilities"],
        }

    def _shared_root(self) -> Path:
        raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
        if isinstance(raw_shared_root, str) and raw_shared_root.strip():
            return Path(raw_shared_root.strip()).expanduser().resolve(strict=False)
        source_home = os.environ.get("BUDDYSWITCH_SOURCE_HOME") or os.environ.get("HOME")
        if isinstance(source_home, str) and source_home.strip():
            return (Path(source_home.strip()).expanduser() / ".codex-buddyswitch").resolve(strict=False)
        return (Path.home() / ".codex-buddyswitch").resolve(strict=False)

    def _read_actor_capabilities(self, actor_id: str) -> dict[str, Any]:
        return self._call_host_control(lambda: self._host_control.capabilities_get(actor_id))

    def _replace_actor_capabilities(self, actor_id: str, body: bytes) -> dict[str, Any]:
        payload = self._parse_json_body(body)
        if set(payload) != {"parent", "side"}:
            raise HttpError(
                status=400,
                code="INVALID_REQUEST",
                message="capability request must contain exactly parent and side.",
            )
        parent = payload["parent"]
        side = payload["side"]
        if not isinstance(parent, str) or not isinstance(side, str):
            raise HttpError(status=400, code="INVALID_REQUEST", message="capability levels must be strings.")
        return self._call_host_control(lambda: self._host_control.capabilities_set(actor_id, parent, side))

    def _deliver_im_actor(self, payload: dict[str, Any]) -> dict[str, Any]:
        return im_actor_delivery.deliver(payload)

    def _check_im_actor_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
        return daemon_client.check_reachability(target_identity_id=target_identity_id)

    def _get_instance_status(self, actor_id: str) -> dict[str, Any]:
        return self._call_host_control(lambda: self._host_control.status(actor_id))

    def _call_host_control(self, action: Callable[[], Any]) -> Any:
        try:
            return action()
        except host_control_module.HostControlError as exc:
            raise map_host_control_failure(exc) from exc

    def _start_lifecycle_operation(
        self,
        *,
        key: str,
        action: str,
        label: str,
        detail: str,
        target: dict[str, str],
        command: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        operation = WebLifecycleOperation(
            id=f"op-{uuid4().hex[:16]}",
            action=action,
            status="queued",
            label=label,
            detail=detail,
            target=target,
        )
        next_thread: threading.Thread | None = None
        with self._operation_lock:
            conflict = self._active_lifecycle_conflict_locked(target)
            if conflict is not None:
                raise HttpError(
                    status=409,
                    code="BUSY",
                    message=self._protective_lifecycle_message(action, conflict),
                )
            self._operations[operation.id] = operation
            self._operation_commands[operation.id] = command
            self._lifecycle_queue.append(operation.id)
            next_thread = self._dispatch_next_lifecycle_operation_locked()
        if next_thread is not None:
            next_thread.start()
        return {"ok": True, "operation": operation.to_payload()}

    def _active_lifecycle_conflict_locked(self, target: dict[str, str]) -> WebLifecycleOperation | None:
        actor_id = target.get("actor_id")
        if not isinstance(actor_id, str) or not actor_id:
            return None
        for operation in self._operations.values():
            operation_target = operation.target if isinstance(operation.target, dict) else {}
            if (
                operation.status in {"queued", "running"}
                and operation_target.get("actor_id") == actor_id
            ):
                return operation
        return None

    def _protective_lifecycle_message(self, action: str, conflict: WebLifecycleOperation) -> str:
        requested = _lifecycle_action_label(action)
        active = _lifecycle_action_label(conflict.action)
        actor_id = conflict.target.get("actor_id", "")
        if action == conflict.action:
            suffix = f" for {actor_id}" if actor_id else ""
            return f"{requested} is already in progress{suffix}."
        return f"{requested} available after {active} completes."

    def _dispatch_next_lifecycle_operation_locked(self) -> threading.Thread | None:
        if self._lifecycle_running_operation_id is not None:
            return None
        while self._lifecycle_queue:
            operation_id = self._lifecycle_queue.pop(0)
            operation = self._operations.get(operation_id)
            command = self._operation_commands.get(operation_id)
            if operation is None or command is None or operation.status != "queued":
                continue
            self._lifecycle_running_operation_id = operation_id
            operation.status = "running"
            operation.detail = "Launcher command is running."
            operation.updated_at = utc_now_iso()
            return threading.Thread(
                target=self._run_lifecycle_operation_worker,
                args=(operation_id, command),
                daemon=True,
            )
        return None

    def _run_lifecycle_operation_worker(
        self,
        operation_id: str,
        command: Callable[[], dict[str, Any]],
    ) -> None:
        status = "succeeded"
        detail = "Launcher command completed."
        result: dict[str, Any] | None = None
        error: dict[str, str] | None = None
        target_patch: dict[str, str] = {}
        try:
            result = command()
        except HttpError as exc:
            status = "failed"
            detail = exc.message
            error = {"code": exc.code, "message": exc.message}
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            status = "failed"
            detail = str(exc)
            error = {"code": "COMMAND_FAILED", "message": str(exc)}
        else:
            actor_id = result.get("actor_id")
            if isinstance(actor_id, str):
                target_patch["actor_id"] = actor_id
        finally:
            next_thread = self._complete_lifecycle_operation(
                operation_id,
                status=status,
                detail=detail,
                result=result,
                error=error,
                target_patch=target_patch,
            )
            if next_thread is not None:
                next_thread.start()

    def _complete_lifecycle_operation(
        self,
        operation_id: str,
        *,
        status: str,
        detail: str,
        result: dict[str, Any] | None,
        error: dict[str, str] | None,
        target_patch: dict[str, str],
    ) -> threading.Thread | None:
        with self._operation_lock:
            operation = self._operations.get(operation_id)
            if operation is not None:
                operation.status = status
                operation.detail = detail
                operation.result = result
                operation.error = error
                if target_patch:
                    operation.target.update(target_patch)
                operation.updated_at = utc_now_iso()
            self._operation_commands.pop(operation_id, None)
            if self._lifecycle_running_operation_id == operation_id:
                self._lifecycle_running_operation_id = None
            return self._dispatch_next_lifecycle_operation_locked()

    def _parse_json_body(self, body: bytes) -> dict[str, Any]:
        if not body:
            return {}
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HttpError(status=400, code="INVALID_REQUEST", message="Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise HttpError(status=400, code="INVALID_REQUEST", message="JSON body must be an object.")
        return payload

    def _run_busy(self, key: str, action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        if not self._busy_guard.acquire(key):
            raise HttpError(status=409, code="BUSY", message="Another action is already running for this target.")
        try:
            return action()
        finally:
            self._busy_guard.release(key)


def _header_value(headers: Mapping[str, str] | None, name: str) -> str | None:
    if headers is None:
        return None
    value = headers.get(name)
    if value is not None:
        return str(value)
    lower_name = name.lower()
    for key, candidate in headers.items():
        if key.lower() == lower_name:
            return str(candidate)
    return None


def _hostname_from_host_header(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip().lower()
    if cleaned.startswith("["):
        end = cleaned.find("]")
        if end > 1:
            return cleaned[1:end]
    return cleaned.rsplit(":", 1)[0]


def _normalized_host_netloc(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip().lower()


def _first_nonempty_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return None


def build_terminal_attach_command(descriptor: actor_session.AttachDescriptor) -> str:
    return actor_session.terminal_command_from_descriptor(descriptor)


def build_copy_attach_command(repo_root: Path, actor_id: str) -> str:
    return (
        f"cd {shlex.quote(str(repo_root))} && "
        f"./buddyswitch-codex instance attach {shlex.quote(actor_id)}"
    )


def _quote_applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def open_macos_terminal_app(command: str) -> None:
    script = "\n".join(
        [
            'tell application "Terminal"',
            "  activate",
            f"  do script {_quote_applescript_string(command)}",
            "end tell",
        ]
    )
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        raise TerminalOpenError("Terminal open timed out.") from exc
    if completed.returncode != 0:
        message = _first_nonempty_line(completed.stderr) or _first_nonempty_line(completed.stdout)
        raise TerminalOpenError(message or "Terminal open failed.")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the BuddySwitch local web management server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (local only).")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        validate_bind_host(args.host)
    except ValueError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 2
    bind_web_runtime_state()
    service = WebManagementService(repo_root=REPO_ROOT)
    try:
        service.ensure_web_im_identity()
    except HttpError as exc:
        print(exc.message, file=sys.stderr, flush=True)
        return 1
    server = create_server(args.host, args.port, service)
    url = f"http://{args.host}:{server.server_port}"
    cli_contract.emit(
        cli_contract.success(
            "web.ready",
            {"url": url},
        ),
        sys.stdout,
    )
    sys.stdout.flush()
    print(f"BuddySwitch web management listening on {url}", file=sys.stderr, flush=True)
    worker = create_imessage_channel_worker(f"http://{args.host}:{server.server_port}")
    serve_with_imessage_worker(server, worker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
