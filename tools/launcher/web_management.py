#!/usr/bin/env python3
"""Local web management UI and API for BuddySwitch instances."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

HELPER_DIR = Path(__file__).resolve().parent
SCRIPTS = HELPER_DIR.parents[1] / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import web_im_identity
import im_http_router
import imessage_channel
from env.domain import task_sys, track_read
from env.repos import runtime_files
from env.tool_runtime import daemon_client
import external_im_session


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = HELPER_DIR / "assets" / "web-management"
VALID_INSTANCE_ID_RE = re.compile(r"^act-[A-Za-z0-9._-]+$")
LOCAL_BIND_HOSTS = {"127.0.0.1", "localhost"}


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


@dataclass(frozen=True)
class HttpError(Exception):
    status: int
    code: str
    message: str
    details: dict[str, Any] | None = None


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


class LauncherCommandRunner:
    def __init__(self, repo_root: Path) -> None:
        self._launcher = repo_root / "buddyswitch-codex"
        self._repo_root = repo_root

    def run(self, args: list[str], *, timeout_seconds: float) -> CommandResult:
        command = [str(self._launcher), *args]
        try:
            completed = subprocess.run(
                command,
                cwd=self._repo_root,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                returncode=1,
                stdout=_coerce_process_text(exc.stdout),
                stderr=_coerce_process_text(exc.stderr),
                timed_out=True,
            )
        return CommandResult(
            returncode=int(completed.returncode),
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )


def _coerce_process_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def validate_bind_host(host: str) -> str:
    if host not in LOCAL_BIND_HOSTS:
        raise ValueError("BuddySwitch web host must stay local to 127.0.0.1 or localhost.")
    return host


def validate_actor_id(actor_id: str) -> str:
    if not VALID_INSTANCE_ID_RE.fullmatch(actor_id):
        raise ValueError("Invalid actor id.")
    return actor_id


def load_command_json_object(stdout: str, *, message: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HttpError(status=502, code="COMMAND_FAILED", message=message) from exc
    if not isinstance(payload, dict):
        raise HttpError(status=502, code="COMMAND_FAILED", message=message)
    return payload


def bind_web_runtime_state() -> None:
    raw_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
    if isinstance(raw_shared_root, str) and raw_shared_root.strip():
        shared_root = Path(raw_shared_root.strip()).expanduser()
        os.environ["BUDDYSWITCH_STATE_ROOT"] = str(shared_root / "state")
    runtime_files.refresh_runtime_roots_from_env()


def map_command_failure(command_label: str, result: CommandResult) -> HttpError:
    message = _command_error_message(command_label, result)
    if result.timed_out:
        return HttpError(status=504, code="COMMAND_TIMEOUT", message=message)
    if result.returncode == 2:
        return HttpError(status=400, code="INVALID_REQUEST", message=message)
    if result.returncode == 3:
        return HttpError(status=409, code="LIFECYCLE_BLOCKED", message=message)
    return HttpError(status=502, code="COMMAND_FAILED", message=message)


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
                if parsed.path == "/static/styles.css":
                    self._serve_static(STATIC_ROOT / "styles.css", "text/css; charset=utf-8")
                    return
                if parsed.path == "/static/app.js":
                    self._serve_static(STATIC_ROOT / "app.js", "application/javascript; charset=utf-8")
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
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

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
        command_runner: Callable[[list[str], float], CommandResult] | Callable[..., CommandResult] | None = None,
        terminal_opener: Callable[[str], None] | None = None,
        web_im_identity_provider: web_im_identity.WebImIdentityProvider | None = None,
        im_session: external_im_session.ExternalImSession | None = None,
        platform_name: str | None = None,
        busy_guard: BusyGuard | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._runner = command_runner or LauncherCommandRunner(repo_root).run
        self._terminal_opener = terminal_opener or open_macos_terminal_app
        self._platform_name = platform_name or sys.platform
        self._busy_guard = busy_guard or BusyGuard()
        self._im_session = im_session or external_im_session.ExternalImSession(
            actor_lister=self._external_im_actor_rows,
            actor_delivery_handler=self._wake_im_actor,
        )
        self._web_im_identity = web_im_identity_provider or web_im_identity.WebImIdentityProvider(
            im_session=self._im_session
        )
        self._im_router = im_http_router.ImHttpRouter(
            actor_lister=self._external_im_actor_rows,
            actor_delivery_handler=self._wake_im_actor,
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
            return 200, {"ok": True, "roles": self._list_buddies()}
        if method == "GET" and path == "/api/instances":
            return 200, {"ok": True, "instances": self._list_instances()}
        if method == "POST" and path == "/api/instances":
            return 200, self._create_instance(body)
        if method == "GET" and route == "/api/actors":
            return 200, {"ok": True, "actors": self._list_actor_rows()}
        actor_console_id = self._parse_actor_console_path(route)
        if method == "GET" and actor_console_id is not None:
            try:
                validate_actor_id(actor_console_id)
            except ValueError as exc:
                raise HttpError(status=400, code="INVALID_REQUEST", message=str(exc)) from exc
            return 200, {"ok": True, "console": self._actor_console(actor_console_id)}
        if method == "GET" and route == "/api/tracks":
            return 200, {"ok": True, "tracks": track_read.list_track_summaries()}
        track_id = self._parse_track_detail_path(route)
        if method == "GET" and track_id is not None:
            try:
                detail = track_read.get_track_detail(track_id)
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
        try:
            validate_actor_id(actor_id)
        except ValueError as exc:
            raise HttpError(status=400, code="INVALID_REQUEST", message=str(exc)) from exc

        if method == "GET" and action == "status":
            return 200, {"ok": True, "instance": self._get_instance_status(actor_id)}
        if method == "POST" and action == "clear":
            return 200, self._clear(actor_id)
        if method == "POST" and action == "side":
            return 200, self._side(actor_id, body)
        if method == "POST" and action == "side-close":
            return 200, self._side_cleanup(actor_id, body)
        if method == "POST" and action == "interrupt":
            return 200, self._interrupt(actor_id)
        if method == "POST" and action == "resume":
            return 200, self._resume(actor_id)
        if method == "POST" and action == "stop":
            return 200, self._stop(actor_id)
        if method == "POST" and action == "open-tui":
            return 200, self._open_tui(actor_id, body, headers)
        if method == "DELETE" and action == "delete":
            return 200, self._delete(actor_id)
        raise HttpError(status=404, code="NOT_FOUND", message="API route not found.")

    def _parse_instance_action_path(self, path: str) -> tuple[str, str] | None:
        status_prefix = "/api/instances/"
        if path.startswith(status_prefix) and path.endswith("/status"):
            return path[len(status_prefix) : -len("/status")], "status"
        if path.startswith(status_prefix) and path.endswith("/clear"):
            return path[len(status_prefix) : -len("/clear")], "clear"
        if path.startswith(status_prefix) and path.endswith("/side/close"):
            return path[len(status_prefix) : -len("/side/close")], "side-close"
        if path.startswith(status_prefix) and path.endswith("/side"):
            return path[len(status_prefix) : -len("/side")], "side"
        if path.startswith(status_prefix) and path.endswith("/interrupt"):
            return path[len(status_prefix) : -len("/interrupt")], "interrupt"
        if path.startswith(status_prefix) and path.endswith("/resume"):
            return path[len(status_prefix) : -len("/resume")], "resume"
        if path.startswith(status_prefix) and path.endswith("/stop"):
            return path[len(status_prefix) : -len("/stop")], "stop"
        if path.startswith(status_prefix) and path.endswith("/open-tui"):
            return path[len(status_prefix) : -len("/open-tui")], "open-tui"
        if path.startswith(status_prefix):
            actor_id = path[len(status_prefix) :]
            if "/" in actor_id:
                return None
            return actor_id, "delete"
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
        valid_role_ids = {row["id"] for row in self._list_buddies()}
        if role not in valid_role_ids:
            raise HttpError(status=400, code="INVALID_REQUEST", message=f"Unknown role: {role}")
        return self._run_busy(
            "start",
            lambda: self._create_instance_under_lock(role),
        )

    def _create_instance_under_lock(self, role: str) -> dict[str, Any]:
        result = self._run_command(["instance", "start", "--role", role, "--json"], timeout_seconds=120)
        payload = load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance start for role {role}.",
        )
        actor_id = payload.get("actor_id")
        if not isinstance(actor_id, str) or not actor_id:
            raise HttpError(status=502, code="COMMAND_FAILED", message=f"Invalid start payload for role {role}.")
        return {"ok": True, "actor_id": actor_id, "instance": self._get_instance_status(actor_id)}

    def _clear(self, actor_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{actor_id}",
            lambda: self._clear_under_lock(actor_id),
        )

    def _clear_under_lock(self, actor_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "clear", actor_id, "--json"], timeout_seconds=60)
        cleared = load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance clear for {actor_id}.",
        )
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(actor_id)}
        previous_thread_id = cleared.get("previous_thread_id")
        thread_id = cleared.get("thread_id")
        if isinstance(previous_thread_id, str):
            payload["previous_thread_id"] = previous_thread_id
        if isinstance(thread_id, str):
            payload["thread_id"] = thread_id
        return payload

    def _run_side_command(
        self,
        actor_id: str,
        *,
        text: str,
        side_thread_id: str | None,
        model: str | None,
        effort: str | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        args = ["instance", "side", actor_id]
        if side_thread_id is not None:
            args.extend(["--side-thread-id", side_thread_id])
        args.extend(["--text", text])
        if side_thread_id is None:
            if model:
                args.extend(["--model", model])
            if effort:
                args.extend(["--effort", effort])
        args.append("--json")
        result = self._run_command(args, timeout_seconds=timeout_seconds)
        return load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance side for {actor_id}.",
        )

    def _run_side_cleanup_command(self, actor_id: str, side_thread_id: str, *, timeout_seconds: float) -> dict[str, Any]:
        result = self._run_command(
            ["instance", "side", "close", actor_id, "--side-thread-id", side_thread_id, "--json"],
            timeout_seconds=timeout_seconds,
        )
        return load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance side close for {actor_id}.",
        )

    def _side(self, actor_id: str, body: bytes) -> dict[str, Any]:
        payload = self._parse_json_body(body)
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HttpError(status=400, code="INVALID_REQUEST", message="text must not be empty.")
        side_thread_id = payload.get("side_thread_id")
        if side_thread_id is not None and (not isinstance(side_thread_id, str) or not side_thread_id.strip()):
            raise HttpError(status=400, code="INVALID_REQUEST", message="side_thread_id must not be empty.")
        model = payload.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise HttpError(status=400, code="INVALID_REQUEST", message="model must not be empty.")
        effort = payload.get("effort")
        if effort is not None and (not isinstance(effort, str) or not effort.strip()):
            raise HttpError(status=400, code="INVALID_REQUEST", message="effort must not be empty.")
        normalized_model = model.strip() if isinstance(model, str) else None
        normalized_effort = effort.strip() if isinstance(effort, str) else None
        if side_thread_id is not None and (normalized_model is not None or normalized_effort is not None):
            raise HttpError(
                status=400,
                code="INVALID_REQUEST",
                message="model and effort only applies when starting a new side thread.",
            )
        return self._run_busy(
            f"instance:{actor_id}",
            lambda: self._side_under_lock(
                actor_id,
                text,
                side_thread_id if isinstance(side_thread_id, str) else None,
                normalized_model,
                normalized_effort,
            ),
        )

    def _side_under_lock(
        self,
        actor_id: str,
        text: str,
        side_thread_id: str | None,
        model: str | None,
        effort: str | None,
    ) -> dict[str, Any]:
        parsed = self._run_side_command(
            actor_id,
            text=text,
            side_thread_id=side_thread_id,
            model=model,
            effort=effort,
            timeout_seconds=60,
        )
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(actor_id)}
        for key in (
            "action",
            "thread_action",
            "parent_thread_id",
            "side_thread_id",
            "turn_id",
            "expected_turn_id",
            "model",
            "model_reasoning_effort",
            "model_source",
            "model_reasoning_effort_source",
            "model_config_durability",
        ):
            value = parsed.get(key)
            if isinstance(value, str):
                payload[key] = value
        return payload

    def _side_cleanup(self, actor_id: str, body: bytes) -> dict[str, Any]:
        payload = self._parse_json_body(body)
        side_thread_id = payload.get("side_thread_id")
        if not isinstance(side_thread_id, str) or not side_thread_id.strip():
            raise HttpError(status=400, code="INVALID_REQUEST", message="side_thread_id must not be empty.")
        return self._run_busy(
            f"instance:{actor_id}",
            lambda: self._side_cleanup_under_lock(actor_id, side_thread_id),
        )

    def _side_cleanup_under_lock(self, actor_id: str, side_thread_id: str) -> dict[str, Any]:
        parsed = self._run_side_cleanup_command(actor_id, side_thread_id, timeout_seconds=30)
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(actor_id)}
        for key in ("action", "parent_thread_id", "side_thread_id", "turn_id"):
            value = parsed.get(key)
            if isinstance(value, str):
                payload[key] = value
        for key in ("turn_interrupt_attempted", "turn_interrupt_ok", "lease_unregistered"):
            value = parsed.get(key)
            if isinstance(value, bool):
                payload[key] = value
        for key in ("turn_interrupt_error", "lease_unregister_error"):
            value = parsed.get(key)
            if isinstance(value, str):
                payload[key] = value
        return payload

    def _interrupt(self, actor_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{actor_id}",
            lambda: self._interrupt_under_lock(actor_id),
        )

    def _interrupt_under_lock(self, actor_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "interrupt", actor_id, "--json"], timeout_seconds=30)
        parsed = load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance interrupt for {actor_id}.",
        )
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(actor_id)}
        turn_id = parsed.get("turn_id")
        if isinstance(turn_id, str):
            payload["turn_id"] = turn_id
        return payload

    def _stop(self, actor_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{actor_id}",
            lambda: self._stop_under_lock(actor_id),
        )

    def _stop_under_lock(self, actor_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "stop", actor_id, "--json"], timeout_seconds=60)
        load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance stop for {actor_id}.",
        )
        return {"ok": True, "instance": self._get_instance_status(actor_id)}

    def _resume(self, actor_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{actor_id}",
            lambda: self._resume_under_lock(actor_id),
        )

    def _resume_under_lock(self, actor_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "resume", actor_id, "--json"], timeout_seconds=60)
        load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance resume for {actor_id}.",
        )
        return {"ok": True, "instance": self._get_instance_status(actor_id)}

    def _delete(self, actor_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{actor_id}",
            lambda: self._delete_under_lock(actor_id),
        )

    def _delete_under_lock(self, actor_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "delete", actor_id, "--yes", "--json"], timeout_seconds=60)
        load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance delete for {actor_id}.",
        )
        return {"ok": True, "actor_id": actor_id}

    def _open_tui(
        self,
        actor_id: str,
        body: bytes,
        headers: Mapping[str, str] | None,
    ) -> dict[str, Any]:
        self._validate_open_tui_request(headers, body)
        instance = self._get_instance_status(actor_id)
        self._validate_open_tui_instance(instance)
        command = build_open_tui_attach_command(self._repo_root, actor_id)
        if self._platform_name != "darwin":
            raise HttpError(
                status=400,
                code="UNSUPPORTED_PLATFORM",
                message="Could not open Terminal.",
                details={"command": command},
            )
        try:
            self._terminal_opener(command)
        except TerminalOpenError as exc:
            raise HttpError(
                status=502,
                code="TERMINAL_OPEN_FAILED",
                message="Could not open Terminal.",
                details={"command": command},
            ) from exc
        except Exception as exc:
            raise HttpError(
                status=502,
                code="TERMINAL_OPEN_FAILED",
                message="Could not open Terminal.",
                details={"command": command},
            ) from exc
        return {
            "ok": True,
            "actor_id": actor_id,
            "command": command,
            "terminal": "Terminal.app",
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

    def _validate_open_tui_instance(self, instance: dict[str, Any]) -> None:
        if instance.get("status") != "active":
            raise HttpError(status=409, code="OPEN_TUI_BLOCKED", message="Resume this instance first.")
        app_server = instance.get("app_server")
        app_server_healthy = isinstance(app_server, dict) and bool(app_server.get("healthy"))
        if not app_server_healthy:
            raise HttpError(status=409, code="OPEN_TUI_BLOCKED", message="Instance is unhealthy.")
        thread_id = instance.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise HttpError(status=409, code="OPEN_TUI_BLOCKED", message="No thread to attach.")

    def _list_buddies(self) -> list[dict[str, str]]:
        result = self._run_command(["instance", "roles", "--json"], timeout_seconds=10)
        payload = load_command_json_object(result.stdout, message="Invalid JSON from instance roles.")
        roles = payload.get("roles")
        if not isinstance(roles, list):
            raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid roles payload from launcher.")
        rows: list[dict[str, str]] = []
        for row in roles:
            if not isinstance(row, dict):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid roles payload from launcher.")
            role_id = row.get("id")
            label = row.get("label")
            scope = row.get("scope")
            if not isinstance(role_id, str) or not isinstance(label, str) or not isinstance(scope, str):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid roles payload from launcher.")
            rows.append({"id": role_id, "label": label, "scope": scope})
        return rows

    def _list_instances(self) -> list[dict[str, Any]]:
        result = self._run_command(["instance", "list", "--json"], timeout_seconds=10)
        payload = load_command_json_object(result.stdout, message="Invalid JSON from instance list.")
        instances = payload.get("instances")
        if not isinstance(instances, list):
            raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid instance list payload from launcher.")
        rows: list[dict[str, Any]] = []
        for row in instances:
            if not isinstance(row, dict):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid instance list payload from launcher.")
            actor_id = row.get("actor_id")
            role = row.get("role")
            status = row.get("status")
            app_server_health = row.get("app_server_health")
            thread_id = row.get("thread_id")
            browser_port = row.get("browser_port")
            updated_at = row.get("updated_at")
            workspace_dir = row.get("workspace_dir")
            if not isinstance(actor_id, str) or not isinstance(role, str) or not isinstance(status, str):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid instance list payload from launcher.")
            if not isinstance(app_server_health, str):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid instance list payload from launcher.")
            if thread_id is not None and not isinstance(thread_id, str):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid instance list payload from launcher.")
            if browser_port is not None and not isinstance(browser_port, int):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid instance list payload from launcher.")
            if not isinstance(updated_at, str) or not isinstance(workspace_dir, str):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid instance list payload from launcher.")
            rows.append(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": status,
                    "app_server_health": app_server_health,
                    "thread_id": thread_id,
                    "browser_port": browser_port,
                    "updated_at": updated_at,
                    "workspace_dir": workspace_dir,
                }
            )
        return rows

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
            try:
                identity_id = validate_actor_id(row.get("actor_id"))
                normalized_role = runtime_files.require_id(row.get("role"), "role_id")
            except ValueError:
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
        actor_target = {"actor_id": actor_id, "role_id": role}
        instance_payload = dict(instance)
        workspace_dir = instance_payload.get("workspace_dir")
        if "instance_root" not in instance_payload and isinstance(workspace_dir, str) and workspace_dir.strip():
            instance_payload["instance_root"] = str(Path(workspace_dir).expanduser().resolve(strict=False).parent)
        del instance_payload
        task_sys_tasks = task_sys.active_tasks_for_actor(actor_target)
        recoverable_task_sys_tasks = task_sys.recoverable_tasks_for_actor(actor_target)
        return {
            "actor": {"actor_id": actor_id, "role": role},
            "runtime": self._runtime_row(instance),
            "task_sys": {
                "active_count": len(task_sys_tasks),
                "recoverable_count": len(recoverable_task_sys_tasks),
                "active_tasks": [
                    {
                        "task_id": row.get("id"),
                        "source_type": row.get("source_type"),
                        "status": row.get("status"),
                        "active_processor": row.get("active_processor"),
                        "updated_at": row.get("updated_at"),
                    }
                    for row in task_sys_tasks[:10]
                ],
                "recoverable_tasks": [
                    {
                        "task_id": row.get("id"),
                        "source_type": row.get("source_type"),
                        "status": row.get("status"),
                        "active_processor": row.get("active_processor"),
                        "failure_result": dict(row.get("failure_result")) if isinstance(row.get("failure_result"), dict) else {},
                        "updated_at": row.get("updated_at"),
                    }
                    for row in recoverable_task_sys_tasks[:10]
                ],
            },
            "tracks": {
                "items": track_read.list_track_summaries(owner_identity=current_identity),
                "source": "web-track-summary",
            },
            "im": {
                "target": {
                    "identity": {"id": actor_id, "type": "actor"},
                    "identity_id": actor_id,
                    "role_id": role,
                }
            },
        }

    def _wake_im_actor(self, payload: dict[str, Any]) -> dict[str, Any]:
        return daemon_client.wake_im_actor(payload)

    def _get_instance_status(self, actor_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "status", actor_id, "--json"], timeout_seconds=10)
        payload = load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance status for {actor_id}.",
        )
        return payload

    def _run_command(self, args: list[str], *, timeout_seconds: float) -> CommandResult:
        result = self._runner(args, timeout_seconds=timeout_seconds)
        if result.returncode != 0 or result.timed_out:
            raise map_command_failure(" ".join(args), result)
        return result

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


def _command_error_message(command_label: str, result: CommandResult) -> str:
    if result.timed_out:
        return f"Command timed out: {command_label}"
    message = _first_nonempty_line(result.stderr) or _first_nonempty_line(result.stdout)
    if message:
        return message
    return f"Command failed: {command_label}"


def _first_nonempty_line(text: str) -> str | None:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return None


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


def build_open_tui_attach_command(repo_root: Path, actor_id: str) -> str:
    validate_actor_id(actor_id)
    return (
        f"cd {shlex.quote(str(repo_root))} "
        f"&& ./buddyswitch-codex instance attach {shlex.quote(actor_id)}"
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
    print(f"BuddySwitch web management listening on http://{args.host}:{server.server_port}", flush=True)
    worker = create_imessage_channel_worker(f"http://{args.host}:{server.server_port}")
    serve_with_imessage_worker(server, worker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
