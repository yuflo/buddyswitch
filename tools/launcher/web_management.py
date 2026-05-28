#!/usr/bin/env python3
"""Local web management UI and API for BuddySwitch instances."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = Path(__file__).resolve().parent / "assets" / "web-management"
VALID_INSTANCE_ID_RE = re.compile(r"^inst-[A-Za-z0-9._-]+$")
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


def validate_instance_id(instance_id: str) -> str:
    if not VALID_INSTANCE_ID_RE.fullmatch(instance_id):
        raise ValueError("Invalid instance id.")
    return instance_id


def load_command_json_object(stdout: str, *, message: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HttpError(status=502, code="COMMAND_FAILED", message=message) from exc
    if not isinstance(payload, dict):
        raise HttpError(status=502, code="COMMAND_FAILED", message=message)
    return payload


def map_command_failure(command_label: str, result: CommandResult) -> HttpError:
    message = _command_error_message(command_label, result)
    if result.timed_out:
        return HttpError(status=504, code="COMMAND_TIMEOUT", message=message)
    if result.returncode == 2:
        return HttpError(status=400, code="INVALID_REQUEST", message=message)
    if result.returncode == 3:
        return HttpError(status=409, code="LIFECYCLE_BLOCKED", message=message)
    if result.returncode == 1 and result.stderr.startswith("Instance input blocked:"):
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
                    self._serve_json(*service.handle_api(self.command, parsed.path, self._read_body()))
                    return
                self._serve_html_404()
            except HttpError as exc:
                self._serve_json(
                    exc.status,
                    {"ok": False, "error": {"code": exc.code, "message": exc.message}},
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


class WebManagementService:
    def __init__(
        self,
        *,
        repo_root: Path,
        command_runner: Callable[[list[str], float], CommandResult] | Callable[..., CommandResult] | None = None,
        busy_guard: BusyGuard | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._runner = command_runner or LauncherCommandRunner(repo_root).run
        self._busy_guard = busy_guard or BusyGuard()

    def handle_api(self, method: str, path: str, body: bytes) -> tuple[int, dict[str, Any]]:
        if method == "GET" and path == "/api/health":
            return 200, {"ok": True}
        if method == "GET" and path == "/api/buddies":
            return 200, {"ok": True, "buddies": self._list_buddies()}
        if method == "GET" and path == "/api/instances":
            return 200, {"ok": True, "instances": self._list_instances()}
        if method == "POST" and path == "/api/instances":
            return 200, self._create_instance(body)

        instance_action = self._parse_instance_action_path(path)
        if instance_action is None:
            raise HttpError(status=404, code="NOT_FOUND", message="API route not found.")
        instance_id, action = instance_action
        try:
            validate_instance_id(instance_id)
        except ValueError as exc:
            raise HttpError(status=400, code="INVALID_REQUEST", message=str(exc)) from exc

        if method == "GET" and action == "status":
            return 200, {"ok": True, "instance": self._get_instance_status(instance_id)}
        if method == "POST" and action == "clear":
            return 200, self._clear(instance_id)
        if method == "POST" and action == "input":
            return 200, self._send_input(instance_id, body)
        if method == "POST" and action == "side":
            return 200, self._side(instance_id, body)
        if method == "POST" and action == "side-close":
            return 200, self._side_close(instance_id, body)
        if method == "POST" and action == "interrupt":
            return 200, self._interrupt(instance_id)
        if method == "POST" and action == "resume":
            return 200, self._resume(instance_id)
        if method == "POST" and action == "stop":
            return 200, self._stop(instance_id)
        if method == "DELETE" and action == "delete":
            return 200, self._delete(instance_id)
        raise HttpError(status=404, code="NOT_FOUND", message="API route not found.")

    def _parse_instance_action_path(self, path: str) -> tuple[str, str] | None:
        status_prefix = "/api/instances/"
        if path.startswith(status_prefix) and path.endswith("/status"):
            return path[len(status_prefix) : -len("/status")], "status"
        if path.startswith(status_prefix) and path.endswith("/clear"):
            return path[len(status_prefix) : -len("/clear")], "clear"
        if path.startswith(status_prefix) and path.endswith("/input"):
            return path[len(status_prefix) : -len("/input")], "input"
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
        if path.startswith(status_prefix):
            instance_id = path[len(status_prefix) :]
            if "/" in instance_id:
                return None
            return instance_id, "delete"
        return None

    def _create_instance(self, body: bytes) -> dict[str, Any]:
        payload = self._parse_json_body(body)
        buddy = payload.get("buddy")
        if not isinstance(buddy, str) or not buddy.strip():
            raise HttpError(status=400, code="INVALID_REQUEST", message="buddy is required.")
        valid_buddy_ids = {row["id"] for row in self._list_buddies()}
        if buddy not in valid_buddy_ids:
            raise HttpError(status=400, code="INVALID_REQUEST", message=f"Unknown buddy: {buddy}")
        return self._run_busy(
            "start",
            lambda: self._create_instance_under_lock(buddy),
        )

    def _create_instance_under_lock(self, buddy: str) -> dict[str, Any]:
        result = self._run_command(["instance", "start", "--buddy", buddy, "--json"], timeout_seconds=120)
        payload = load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance start for buddy {buddy}.",
        )
        instance_id = payload.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise HttpError(status=502, code="COMMAND_FAILED", message=f"Invalid start payload for buddy {buddy}.")
        return {"ok": True, "instance_id": instance_id, "instance": self._get_instance_status(instance_id)}

    def _send_input(self, instance_id: str, body: bytes) -> dict[str, Any]:
        payload = self._parse_json_body(body)
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HttpError(status=400, code="INVALID_REQUEST", message="text must not be empty.")
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._send_input_under_lock(instance_id, text),
        )

    def _send_input_under_lock(self, instance_id: str, text: str) -> dict[str, Any]:
        parsed = self._run_input_command(instance_id, text, timeout_seconds=60)
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(instance_id)}
        action = parsed.get("action")
        turn_id = parsed.get("turn_id")
        expected_turn_id = parsed.get("expected_turn_id")
        if isinstance(action, str):
            payload["action"] = action
        if isinstance(turn_id, str):
            payload["turn_id"] = turn_id
        if isinstance(expected_turn_id, str):
            payload["expected_turn_id"] = expected_turn_id
        return payload

    def _clear(self, instance_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._clear_under_lock(instance_id),
        )

    def _clear_under_lock(self, instance_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "clear", instance_id, "--json"], timeout_seconds=60)
        cleared = load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance clear for {instance_id}.",
        )
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(instance_id)}
        previous_thread_id = cleared.get("previous_thread_id")
        thread_id = cleared.get("thread_id")
        if isinstance(previous_thread_id, str):
            payload["previous_thread_id"] = previous_thread_id
        if isinstance(thread_id, str):
            payload["thread_id"] = thread_id
        return payload

    def _run_input_command(self, instance_id: str, text: str, *, timeout_seconds: float) -> dict[str, Any]:
        result = self._run_command(
            ["instance", "input", instance_id, "--text", text, "--input-wrapper", "task-tui", "--json"],
            timeout_seconds=timeout_seconds,
        )
        return load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance input for {instance_id}.",
        )

    def _run_side_command(
        self,
        instance_id: str,
        *,
        text: str,
        side_thread_id: str | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        args = ["instance", "side", instance_id]
        if side_thread_id is not None:
            args.extend(["--side-thread-id", side_thread_id])
        args.extend(["--text", text, "--json"])
        result = self._run_command(args, timeout_seconds=timeout_seconds)
        return load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance side for {instance_id}.",
        )

    def _run_side_close_command(self, instance_id: str, side_thread_id: str, *, timeout_seconds: float) -> dict[str, Any]:
        result = self._run_command(
            ["instance", "side", "close", instance_id, "--side-thread-id", side_thread_id, "--json"],
            timeout_seconds=timeout_seconds,
        )
        return load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance side close for {instance_id}.",
        )

    def _side(self, instance_id: str, body: bytes) -> dict[str, Any]:
        payload = self._parse_json_body(body)
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HttpError(status=400, code="INVALID_REQUEST", message="text must not be empty.")
        side_thread_id = payload.get("side_thread_id")
        if side_thread_id is not None and (not isinstance(side_thread_id, str) or not side_thread_id.strip()):
            raise HttpError(status=400, code="INVALID_REQUEST", message="side_thread_id must not be empty.")
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._side_under_lock(instance_id, text, side_thread_id if isinstance(side_thread_id, str) else None),
        )

    def _side_under_lock(self, instance_id: str, text: str, side_thread_id: str | None) -> dict[str, Any]:
        parsed = self._run_side_command(
            instance_id,
            text=text,
            side_thread_id=side_thread_id,
            timeout_seconds=60,
        )
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(instance_id)}
        for key in ("action", "thread_action", "parent_thread_id", "side_thread_id", "turn_id", "expected_turn_id"):
            value = parsed.get(key)
            if isinstance(value, str):
                payload[key] = value
        return payload

    def _side_close(self, instance_id: str, body: bytes) -> dict[str, Any]:
        payload = self._parse_json_body(body)
        side_thread_id = payload.get("side_thread_id")
        if not isinstance(side_thread_id, str) or not side_thread_id.strip():
            raise HttpError(status=400, code="INVALID_REQUEST", message="side_thread_id must not be empty.")
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._side_close_under_lock(instance_id, side_thread_id),
        )

    def _side_close_under_lock(self, instance_id: str, side_thread_id: str) -> dict[str, Any]:
        parsed = self._run_side_close_command(instance_id, side_thread_id, timeout_seconds=30)
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(instance_id)}
        for key in ("action", "parent_thread_id", "side_thread_id", "turn_id"):
            value = parsed.get(key)
            if isinstance(value, str):
                payload[key] = value
        startup_interrupt = parsed.get("startup_interrupt")
        if isinstance(startup_interrupt, bool):
            payload["startup_interrupt"] = startup_interrupt
        return payload

    def _interrupt(self, instance_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._interrupt_under_lock(instance_id),
        )

    def _interrupt_under_lock(self, instance_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "interrupt", instance_id, "--json"], timeout_seconds=30)
        parsed = load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance interrupt for {instance_id}.",
        )
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(instance_id)}
        turn_id = parsed.get("turn_id")
        if isinstance(turn_id, str):
            payload["turn_id"] = turn_id
        return payload

    def _stop(self, instance_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._stop_under_lock(instance_id),
        )

    def _stop_under_lock(self, instance_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "stop", instance_id, "--json"], timeout_seconds=60)
        load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance stop for {instance_id}.",
        )
        return {"ok": True, "instance": self._get_instance_status(instance_id)}

    def _resume(self, instance_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._resume_under_lock(instance_id),
        )

    def _resume_under_lock(self, instance_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "resume", instance_id, "--json"], timeout_seconds=60)
        load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance resume for {instance_id}.",
        )
        return {"ok": True, "instance": self._get_instance_status(instance_id)}

    def _delete(self, instance_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._delete_under_lock(instance_id),
        )

    def _delete_under_lock(self, instance_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "delete", instance_id, "--yes", "--json"], timeout_seconds=60)
        load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance delete for {instance_id}.",
        )
        return {"ok": True, "instance_id": instance_id}

    def _list_buddies(self) -> list[dict[str, str]]:
        result = self._run_command(["instance", "buddies", "--json"], timeout_seconds=10)
        payload = load_command_json_object(result.stdout, message="Invalid JSON from instance buddies.")
        buddies = payload.get("buddies")
        if not isinstance(buddies, list):
            raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid buddies payload from launcher.")
        rows: list[dict[str, str]] = []
        for row in buddies:
            if not isinstance(row, dict):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid buddies payload from launcher.")
            buddy_id = row.get("id")
            label = row.get("label")
            scope = row.get("scope")
            if not isinstance(buddy_id, str) or not isinstance(label, str) or not isinstance(scope, str):
                raise HttpError(status=502, code="COMMAND_FAILED", message="Invalid buddies payload from launcher.")
            rows.append({"id": buddy_id, "label": label, "scope": scope})
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
            instance_id = row.get("instance_id")
            buddy = row.get("buddy")
            status = row.get("status")
            app_server_health = row.get("app_server_health")
            thread_id = row.get("thread_id")
            browser_port = row.get("browser_port")
            updated_at = row.get("updated_at")
            workspace_dir = row.get("workspace_dir")
            if not isinstance(instance_id, str) or not isinstance(buddy, str) or not isinstance(status, str):
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
                    "instance_id": instance_id,
                    "buddy": buddy,
                    "status": status,
                    "app_server_health": app_server_health,
                    "thread_id": thread_id,
                    "browser_port": browser_port,
                    "updated_at": updated_at,
                    "workspace_dir": workspace_dir,
                }
            )
        return rows

    def _get_instance_status(self, instance_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "status", instance_id, "--json"], timeout_seconds=10)
        payload = load_command_json_object(
            result.stdout,
            message=f"Invalid JSON from instance status for {instance_id}.",
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
    service = WebManagementService(repo_root=REPO_ROOT)
    server = create_server(args.host, args.port, service)
    print(f"BuddySwitch web management listening on http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
