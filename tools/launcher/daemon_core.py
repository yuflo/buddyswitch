#!/usr/bin/env python3
"""BuddySwitch daemon core."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import app_server  # noqa: E402


MAX_DAEMON_ORIGIN_TURN_IDS = 50
DAEMON_CLIENT_NAME = "buddyswitch_daemon"
DAEMON_CLIENT_TITLE = "BuddySwitch Daemon"
DAEMON_PERMISSIONS = "buddyswitch-runtime"
DAEMON_STOP_GRACE_SECONDS = 2.0
DAEMON_POLL_SECONDS = 0.05
DAEMON_READY_TIMEOUT_SECONDS = 5.0
DAEMON_READY_POLL_SECONDS = 0.05
LEGACY_STATE_FIELDS = (
    "last_origin_turn_id",
    "last_" + "stop" + "_" + "tui" + "_turn_id",
)
INSTANCE_DAEMON_ENTRYPOINT = HELPER_DIR / "instance_daemon.py"


def daemon_runtime_dir(instance_root: Path) -> Path:
    return instance_root / "runtime" / "daemon"


def daemon_pid_file(instance_root: Path) -> Path:
    return daemon_runtime_dir(instance_root) / "daemon.pid"


def daemon_log_file(instance_root: Path) -> Path:
    return daemon_runtime_dir(instance_root) / "daemon.log"


def daemon_state_file(instance_root: Path) -> Path:
    return daemon_runtime_dir(instance_root) / "state.json"


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_text_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")


def _read_pid(path: Path) -> int | None:
    raw = _read_text_file(path)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _remove_path(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _terminate_pid(pid: int) -> bool:
    if not _pid_is_live(pid):
        return True
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + DAEMON_STOP_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not _pid_is_live(pid):
            return True
        time.sleep(DAEMON_POLL_SECONDS)
    if _pid_is_live(pid):
        os.kill(pid, signal.SIGKILL)
    return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _state_payload(instance_id: str, main_thread_id: str) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "main_thread_id": main_thread_id,
        "daemon_origin_turn_ids": [],
        "ready": None,
        "last_error": None,
        "handlers": {},
    }


def _string_field(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _notification_turn_id(notification: dict[str, Any]) -> str | None:
    params = notification.get("params")
    if not isinstance(params, dict):
        return None
    turn = params.get("turn")
    if not isinstance(turn, dict):
        return None
    turn_id = _string_field(turn, "id")
    return turn_id or None


class DaemonState:
    def __init__(self, *, path: Path, payload: dict[str, Any]) -> None:
        self.path = path
        self.payload = payload

    @classmethod
    def load(cls, *, instance_root: Path, instance_id: str, main_thread_id: str) -> DaemonState:
        path = daemon_state_file(instance_root)
        payload = _state_payload(instance_id, main_thread_id)
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls(path=path, payload=payload)
        if isinstance(loaded, dict):
            payload.update(loaded)
        payload["instance_id"] = instance_id
        payload["main_thread_id"] = main_thread_id
        for field in LEGACY_STATE_FIELDS:
            payload.pop(field, None)
        if not isinstance(payload.get("daemon_origin_turn_ids"), list):
            payload["daemon_origin_turn_ids"] = []
        payload["daemon_origin_turn_ids"] = [
            item for item in payload["daemon_origin_turn_ids"] if isinstance(item, str) and item
        ][-MAX_DAEMON_ORIGIN_TURN_IDS:]
        if not isinstance(payload.get("ready"), dict):
            payload["ready"] = None
        if "last_error" not in payload:
            payload["last_error"] = None
        if not isinstance(payload.get("handlers"), dict):
            payload["handlers"] = {}
        return cls(path=path, payload=payload)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temp_path.write_text(json.dumps(self.payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.path)

    def is_daemon_origin_turn(self, turn_id: str) -> bool:
        return turn_id in self.payload.get("daemon_origin_turn_ids", [])

    def record_daemon_origin_turn(self, turn_id: str) -> None:
        turn_ids = [item for item in self.payload.get("daemon_origin_turn_ids", []) if isinstance(item, str) and item]
        turn_ids = [item for item in turn_ids if item != turn_id]
        turn_ids.append(turn_id)
        self.payload["daemon_origin_turn_ids"] = turn_ids[-MAX_DAEMON_ORIGIN_TURN_IDS:]
        self.save()

    def record_error(self, *, origin_turn_id: str | None, message: str, handler: str | None = None) -> None:
        payload = {
            "origin_turn_id": origin_turn_id,
            "message": message,
            "at": _utc_now(),
        }
        if handler:
            payload["handler"] = handler
        self.payload["last_error"] = payload
        self.save()

    def record_ready(self, *, pid: int, main_thread_id: str) -> None:
        self.payload["ready"] = {
            "pid": pid,
            "main_thread_id": main_thread_id,
            "at": _utc_now(),
        }
        self.save()

    def ready_for(self, pid: int, main_thread_id: str) -> bool:
        ready = self.payload.get("ready")
        if not isinstance(ready, dict):
            return False
        ready_pid = ready.get("pid")
        ready_thread_id = ready.get("main_thread_id")
        return ready_pid == pid and ready_thread_id == main_thread_id

    def handler_state(self, handler_name: str) -> dict[str, Any]:
        handlers = self.payload.setdefault("handlers", {})
        if not isinstance(handlers, dict):
            handlers = {}
            self.payload["handlers"] = handlers
        state = handlers.setdefault(handler_name, {})
        if not isinstance(state, dict):
            state = {}
            handlers[handler_name] = state
        return state

    def update_handler_state(self, handler_name: str, values: dict[str, Any]) -> None:
        state = self.handler_state(handler_name)
        state.update(values)
        self.save()

    def record_handler_error(self, handler_name: str, *, origin_turn_id: str | None, message: str) -> None:
        self.update_handler_state(
            handler_name,
            {
                "last_error": {
                    "origin_turn_id": origin_turn_id,
                    "message": message,
                    "at": _utc_now(),
                }
            },
        )


class DaemonContext:
    def __init__(
        self,
        *,
        instance_json: Path,
        instance_payload: dict[str, Any],
        instance_id: str,
        instance_root: Path,
        main_thread_id: str,
        buddy: str,
        workspace_dir: Path,
        project_workspace_dir: Path,
        socket_path: Path,
        permissions: str = DAEMON_PERMISSIONS,
    ) -> None:
        self.instance_json = instance_json
        self.instance_payload = instance_payload
        self.instance_id = instance_id
        self.instance_root = instance_root
        self.main_thread_id = main_thread_id
        self.buddy = buddy
        self.workspace_dir = workspace_dir
        self.project_workspace_dir = project_workspace_dir
        self.socket_path = socket_path
        self.permissions = permissions


def load_daemon_context(instance_json: Path) -> DaemonContext:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"instance JSON must contain an object: {instance_json}")
    instance_id = _string_field(payload, "instance_id")
    buddy = _string_field(payload, "buddy")
    main_thread_id = _string_field(payload, "thread_id")
    instance_root_text = _string_field(payload, "instance_root")
    workspace_dir_text = _string_field(payload, "workspace_dir")
    if not instance_id or not buddy or not main_thread_id or not instance_root_text or not workspace_dir_text:
        raise ValueError(f"instance JSON is missing daemon fields: {instance_json}")
    instance_root = Path(instance_root_text)
    workspace_dir = Path(workspace_dir_text)
    project_workspace_dir = instance_root.parent.parent / "project" / "workspace"
    socket_text = _string_field(payload, "app_server_socket")
    socket_path = (
        Path(socket_text)
        if socket_text
        else app_server.effective_socket_path(instance_id, instance_root, app_server.marker_file(instance_root))
    )
    return DaemonContext(
        instance_json=instance_json,
        instance_payload=payload,
        instance_id=instance_id,
        instance_root=instance_root,
        main_thread_id=main_thread_id,
        buddy=buddy,
        workspace_dir=workspace_dir,
        project_workspace_dir=project_workspace_dir,
        socket_path=socket_path,
    )


def bind_main_thread(context: DaemonContext, client: Any) -> None:
    result = client.request(
        "thread/resume",
        {
            "threadId": context.main_thread_id,
            "cwd": str(context.workspace_dir),
            "runtimeWorkspaceRoots": [
                str(context.workspace_dir),
                str(context.project_workspace_dir),
            ],
            "permissions": context.permissions,
            "excludeTurns": True,
        },
    )
    thread = result.get("thread")
    if not isinstance(thread, dict) or _string_field(thread, "id") != context.main_thread_id:
        raise app_server.AppServerProtocolError(
            f"thread/resume returned unexpected thread id for {context.instance_id}"
        )


def dispatch_notification(
    context: DaemonContext,
    state: DaemonState,
    client: Any,
    notification: dict[str, Any],
    handlers: list[Any] | tuple[Any, ...],
) -> bool:
    handled = False
    origin_turn_id = _notification_turn_id(notification)
    for handler in handlers:
        try:
            handled = bool(handler.handle_notification(context, state, client, notification)) or handled
        except Exception as exc:
            handler_name = getattr(handler, "name", type(handler).__name__)
            state.record_error(origin_turn_id=origin_turn_id, message=str(exc), handler=handler_name)
            continue
    return handled


def daemon_status(instance_json: Path) -> dict[str, Any]:
    context = load_daemon_context(instance_json)
    runtime = daemon_runtime_dir(context.instance_root)
    pid_path = daemon_pid_file(context.instance_root)
    log_path = daemon_log_file(context.instance_root)
    state_path = daemon_state_file(context.instance_root)
    pid = _read_pid(pid_path)
    pid_live = pid is not None and _pid_is_live(pid)
    if pid is not None and not pid_live:
        _remove_path(pid_path)
        pid = None
    state = DaemonState.load(
        instance_root=context.instance_root,
        instance_id=context.instance_id,
        main_thread_id=context.main_thread_id,
    )
    ready = bool(pid is not None and pid_live and state.ready_for(pid, context.main_thread_id))
    ready_payload = state.payload.get("ready")
    ready_main_thread_id = ready_payload.get("main_thread_id") if isinstance(ready_payload, dict) else None
    return {
        "live": bool(pid_live),
        "pid": pid,
        "pid_live": bool(pid_live),
        "ready": ready,
        "ready_main_thread_id": ready_main_thread_id,
        "runtime_dir": str(runtime),
        "pid_file": str(pid_path),
        "log_path": str(log_path),
        "state_path": str(state_path),
        "last_error": state.payload.get("last_error"),
    }


def start_daemon(instance_json: Path) -> dict[str, Any]:
    context = load_daemon_context(instance_json)
    runtime = daemon_runtime_dir(context.instance_root)
    pid_path = daemon_pid_file(context.instance_root)
    log_path = daemon_log_file(context.instance_root)
    runtime.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)
    state = DaemonState.load(
        instance_root=context.instance_root,
        instance_id=context.instance_id,
        main_thread_id=context.main_thread_id,
    )
    state.save()

    pid = _read_pid(pid_path)
    if pid is not None and _pid_is_live(pid):
        if state.ready_for(pid, context.main_thread_id):
            status = daemon_status(instance_json)
            status["started"] = False
            return status
        _terminate_pid(pid)
        _remove_path(pid_path)
    if pid is not None:
        _remove_path(pid_path)
    state.payload["ready"] = None
    state.save()

    command = [
        sys.executable,
        str(INSTANCE_DAEMON_ENTRYPOINT.resolve()),
        "run",
        "--instance-json",
        str(instance_json),
    ]
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(context.instance_root),
        )
    _write_text_file(pid_path, str(process.pid))
    deadline = time.monotonic() + DAEMON_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        wait_state = DaemonState.load(
            instance_root=context.instance_root,
            instance_id=context.instance_id,
            main_thread_id=context.main_thread_id,
        )
        if wait_state.ready_for(process.pid, context.main_thread_id):
            status = daemon_status(instance_json)
            status["started"] = True
            status["pid"] = process.pid
            status["pid_live"] = _pid_is_live(process.pid)
            status["live"] = bool(status["pid_live"])
            return status
        if process.poll() is not None:
            _remove_path(pid_path)
            raise RuntimeError(f"daemon exited before ready for {context.instance_id}; see {log_path}")
        time.sleep(DAEMON_READY_POLL_SECONDS)
    _terminate_pid(process.pid)
    _remove_path(pid_path)
    raise RuntimeError(f"daemon did not become ready for {context.instance_id}; see {log_path}")


def stop_daemon(instance_json: Path) -> dict[str, Any]:
    context = load_daemon_context(instance_json)
    pid_path = daemon_pid_file(context.instance_root)
    pid = _read_pid(pid_path)
    terminated = True
    if pid is not None and _pid_is_live(pid):
        terminated = _terminate_pid(pid)
    _remove_path(pid_path)
    return {
        "ok": True,
        "pid": pid,
        "terminated": bool(terminated),
        "pid_file": str(pid_path),
    }


def run_daemon(instance_json: Path, *, handlers: list[Any] | None = None) -> int:
    context = load_daemon_context(instance_json)
    state = DaemonState.load(
        instance_root=context.instance_root,
        instance_id=context.instance_id,
        main_thread_id=context.main_thread_id,
    )
    state.save()
    notification_handlers = list(handlers or [])
    try:
        with app_server.AppServerClient(
            context.socket_path,
            timeout_seconds=app_server.DEFAULT_RPC_TIMEOUT_SECONDS,
            client_name=DAEMON_CLIENT_NAME,
            client_title=DAEMON_CLIENT_TITLE,
        ) as client:
            bind_main_thread(context, client)
            state.record_ready(pid=os.getpid(), main_thread_id=context.main_thread_id)
            while True:
                try:
                    notification = client.read_notification()
                except app_server.AppServerTimeoutError:
                    continue
                except app_server.AppServerError as exc:
                    state.record_error(origin_turn_id=None, message=str(exc))
                    return 1
                dispatch_notification(context, state, client, notification, notification_handlers)
    except app_server.AppServerError as exc:
        state.record_error(origin_turn_id=None, message=str(exc))
        return 1
    return 0
