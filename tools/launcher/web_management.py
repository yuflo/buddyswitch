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


def parse_buddies_tsv(stdout: str) -> list[dict[str, str]]:
    buddies: list[dict[str, str]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        buddy_id, label, scope = _split_tsv_line(line, expected_fields=3)
        buddies.append({"id": buddy_id, "label": label, "scope": scope})
    return buddies


def parse_instance_list_tsv(stdout: str) -> list[dict[str, Any]]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines or lines[0] == "No BuddySwitch instances found.":
        return []
    header = lines[0].split("\t")
    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        values = line.split("\t")
        if len(values) < len(header):
            values.extend([""] * (len(header) - len(values)))
        row = dict(zip(header, values, strict=False))
        thread_id = row.get("thread_id") or None
        browser_port_text = row.get("browser_port") or ""
        browser_port = int(browser_port_text) if browser_port_text else None
        rows.append(
            {
                "instance_id": row.get("instance_id", ""),
                "buddy": row.get("buddy", ""),
                "status": row.get("status", ""),
                "app_server_health": row.get("app_server_health", ""),
                "thread_id": thread_id,
                "browser_port": browser_port,
                "updated_at": row.get("updated_at", ""),
                "workspace_dir": row.get("workspace_dir", ""),
            }
        )
    return rows


def parse_started_instance_id(stdout: str) -> str | None:
    match = re.search(r"BuddySwitch instance:\s+(inst-[A-Za-z0-9._-]+)\b", stdout)
    if match is None:
        return None
    return match.group(1)


def parse_turn_action_output(stdout: str) -> dict[str, str] | None:
    match = re.search(r"^(Started|Steered) turn:\s+(\S+)$", stdout, flags=re.MULTILINE)
    if match is None:
        return None
    return {
        "action": "start" if match.group(1) == "Started" else "steer",
        "turn_id": match.group(2),
    }


def parse_interrupt_turn_id(stdout: str) -> str | None:
    match = re.search(r"^Interrupted turn:\s+(\S+)$", stdout, flags=re.MULTILINE)
    if match is None:
        return None
    return match.group(1)


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
        if method == "POST" and action == "input":
            return 200, self._send_input(instance_id, body)
        if method == "POST" and action == "interrupt":
            return 200, self._interrupt(instance_id)
        if method == "POST" and action == "stop":
            return 200, self._stop(instance_id)
        if method == "DELETE" and action == "delete":
            return 200, self._delete(instance_id)
        raise HttpError(status=404, code="NOT_FOUND", message="API route not found.")

    def _parse_instance_action_path(self, path: str) -> tuple[str, str] | None:
        status_prefix = "/api/instances/"
        if path.startswith(status_prefix) and path.endswith("/status"):
            return path[len(status_prefix) : -len("/status")], "status"
        if path.startswith(status_prefix) and path.endswith("/input"):
            return path[len(status_prefix) : -len("/input")], "input"
        if path.startswith(status_prefix) and path.endswith("/interrupt"):
            return path[len(status_prefix) : -len("/interrupt")], "interrupt"
        if path.startswith(status_prefix) and path.endswith("/stop"):
            return path[len(status_prefix) : -len("/stop")], "stop"
        if path.startswith(status_prefix):
            return path[len(status_prefix) :], "delete"
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
        result = self._run_command(["instance", "start", "--buddy", buddy], timeout_seconds=120)
        instance_id = parse_started_instance_id(result.stdout)
        if instance_id is None:
            raise HttpError(status=502, code="COMMAND_FAILED", message="Could not parse created instance id.")
        return {
            "ok": True,
            "instance_id": instance_id,
            "instance": self._get_instance_status(instance_id),
        }

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
        result = self._run_command(
            ["instance", "input", instance_id, "--text", text],
            timeout_seconds=60,
        )
        parsed = parse_turn_action_output(result.stdout)
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(instance_id)}
        if parsed is not None:
            payload.update(parsed)
        return payload

    def _interrupt(self, instance_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._interrupt_under_lock(instance_id),
        )

    def _interrupt_under_lock(self, instance_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "interrupt", instance_id], timeout_seconds=30)
        payload: dict[str, Any] = {"ok": True, "instance": self._get_instance_status(instance_id)}
        turn_id = parse_interrupt_turn_id(result.stdout)
        if turn_id is not None:
            payload["turn_id"] = turn_id
        return payload

    def _stop(self, instance_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._stop_under_lock(instance_id),
        )

    def _stop_under_lock(self, instance_id: str) -> dict[str, Any]:
        self._run_command(["instance", "stop", instance_id], timeout_seconds=60)
        return {"ok": True, "instance": self._get_instance_status(instance_id)}

    def _delete(self, instance_id: str) -> dict[str, Any]:
        return self._run_busy(
            f"instance:{instance_id}",
            lambda: self._delete_under_lock(instance_id),
        )

    def _delete_under_lock(self, instance_id: str) -> dict[str, Any]:
        self._run_command(["instance", "delete", instance_id, "--yes"], timeout_seconds=60)
        return {"ok": True, "instance_id": instance_id}

    def _list_buddies(self) -> list[dict[str, str]]:
        result = self._run_command(["instance", "buddies"], timeout_seconds=10)
        return parse_buddies_tsv(result.stdout)

    def _list_instances(self) -> list[dict[str, Any]]:
        result = self._run_command(["instance", "list"], timeout_seconds=10)
        return parse_instance_list_tsv(result.stdout)

    def _get_instance_status(self, instance_id: str) -> dict[str, Any]:
        result = self._run_command(["instance", "status", instance_id, "--json"], timeout_seconds=10)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise HttpError(
                status=502,
                code="COMMAND_FAILED",
                message=f"Invalid JSON from instance status for {instance_id}.",
            ) from exc
        if not isinstance(payload, dict):
            raise HttpError(
                status=502,
                code="COMMAND_FAILED",
                message=f"Invalid status payload for {instance_id}.",
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


def _split_tsv_line(line: str, *, expected_fields: int) -> list[str]:
    parts = line.split("\t", expected_fields - 1)
    if len(parts) != expected_fields:
        raise ValueError(f"Invalid TSV line: {line!r}")
    return parts


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
