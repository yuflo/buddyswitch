#!/usr/bin/env python3
"""Runtime broker lifecycle, health checks, and ensure/stop helpers."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import socket
import subprocess
import time
from typing import Any

from runtime_kernel import protocol


@dataclass(frozen=True)
class BrokerPaths:
    socket_path: Path
    pid_file: Path
    marker_file: Path
    log_file: Path


def resolve_socket_path(instance_id: str, instance_root: Path, marker_file: Path) -> Path:
    if marker_file.exists():
        raw = marker_file.read_text(encoding="utf-8").strip()
        if raw:
            return Path(raw)

    default_socket = instance_root / "runtime" / "runtime-broker.sock"
    if len(str(default_socket)) < 100:
        return default_socket

    digest = hashlib.sha1(instance_id.encode("utf-8")).hexdigest()[:12]
    return Path(f"/tmp/buddyswitch-runtime-{digest}.sock")


def read_pid(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    raw = pid_file.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    if not raw.isdigit():
        return None
    return int(raw)


def pid_is_live(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _socket_is_unix(path: Path) -> bool:
    return path.exists() and path.is_socket()


def ping_broker(
    paths: BrokerPaths,
    *,
    expected_instance_id: str,
    expected_active_buddy: str,
    timeout_seconds: float = 0.75,
) -> dict[str, Any]:
    request_id = f"req-ping-{int(time.time() * 1000)}"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_seconds)
            sock.connect(str(paths.socket_path))
            protocol.write_message(
                sock,
                protocol.make_request(
                    request_id=request_id,
                    method="ping",
                    params={},
                    deadline_ms=1500,
                ),
            )
            response = protocol.read_message(sock)
    except OSError as exc:
        err = getattr(exc, "errno", None)
        if err in {errno.ECONNRESET, errno.EPIPE}:
            return {
                "ok": False,
                "error": {
                    "code": "E_RUNTIME_BROKER_CLIENT_DISCONNECTED",
                    "message": f"runtime broker ping disconnected: {exc}",
                    "retriable": True,
                },
            }
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_UNAVAILABLE",
                "message": f"runtime broker ping unavailable: {exc}",
                "retriable": True,
            },
        }
    except protocol.BrokerProtocolError as exc:
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PROTOCOL",
                "message": exc.message,
                "retriable": False,
            },
        }

    if not isinstance(response, dict):
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PROTOCOL",
                "message": "runtime broker ping response must be an object",
                "retriable": False,
            },
        }

    if response.get("protocol") != protocol.PROTOCOL:
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PROTOCOL",
                "message": "runtime broker ping response protocol mismatch",
                "retriable": False,
            },
        }

    if response.get("request_id") != request_id:
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PROTOCOL",
                "message": "runtime broker ping response request_id mismatch",
                "retriable": False,
            },
        }

    if response.get("ok") is not True:
        error = response.get("error") if isinstance(response.get("error"), dict) else {}
        return {
            "ok": False,
            "error": {
                "code": error.get("code", "E_RUNTIME_BROKER_UNAVAILABLE"),
                "message": error.get("message", "runtime broker ping failed"),
                "retriable": bool(error.get("retriable", True)),
            },
        }

    result = response.get("result")
    if not isinstance(result, dict):
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PROTOCOL",
                "message": "runtime broker ping result must be an object",
                "retriable": False,
            },
        }
    if result.get("protocol") != protocol.PROTOCOL:
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PROTOCOL",
                "message": "runtime broker ping result protocol mismatch",
                "retriable": False,
            },
        }
    if result.get("instance_id") != expected_instance_id:
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PERMISSION",
                "message": "runtime broker ping instance_id mismatch",
                "retriable": False,
            },
        }
    if result.get("active_buddy") != expected_active_buddy:
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PERMISSION",
                "message": "runtime broker ping active_buddy mismatch",
                "retriable": False,
            },
        }

    return {
        "ok": True,
        "result": result,
    }


def broker_status(
    paths: BrokerPaths,
    *,
    expected_instance_id: str,
    expected_active_buddy: str,
) -> dict[str, Any]:
    pid = read_pid(paths.pid_file)
    pid_live = pid_is_live(pid)
    marker_value: str | None = None
    if paths.marker_file.exists():
        marker_value = paths.marker_file.read_text(encoding="utf-8").strip() or None

    status: dict[str, Any] = {
        "ok": True,
        "protocol": protocol.PROTOCOL,
        "pid": pid,
        "pid_live": pid_live,
        "socket_path": str(paths.socket_path),
        "marker_path": str(paths.marker_file),
        "marker_value": marker_value,
        "log_file": str(paths.log_file),
        "healthy": False,
    }

    if marker_value and marker_value != str(paths.socket_path):
        status["error"] = {
            "code": "E_RUNTIME_BROKER_STALE_SOCKET",
            "message": "runtime broker marker/socket mismatch",
            "retriable": True,
        }
        return status

    if not pid_live and not _socket_is_unix(paths.socket_path):
        status["error"] = {
            "code": "E_RUNTIME_BROKER_UNAVAILABLE",
            "message": "runtime broker is not running",
            "retriable": True,
        }
        return status

    if pid_live and not _socket_is_unix(paths.socket_path):
        status["error"] = {
            "code": "E_RUNTIME_BROKER_STALE_SOCKET",
            "message": "runtime broker pid is live but socket is missing or invalid",
            "retriable": True,
        }
        return status

    if not marker_value:
        status["error"] = {
            "code": "E_RUNTIME_BROKER_STALE_SOCKET",
            "message": "runtime broker marker file is missing or empty",
            "retriable": True,
        }
        return status

    if not pid_live:
        status["error"] = {
            "code": "E_RUNTIME_BROKER_STALE_SOCKET",
            "message": "runtime broker pid is stale while socket marker is present",
            "retriable": True,
        }
        return status

    ping = ping_broker(
        paths,
        expected_instance_id=expected_instance_id,
        expected_active_buddy=expected_active_buddy,
    )
    if ping.get("ok") is True:
        result = ping.get("result") if isinstance(ping.get("result"), dict) else {}
        ping_pid = result.get("pid")
        if not isinstance(ping_pid, int):
            status["error"] = {
                "code": "E_RUNTIME_BROKER_STALE_SOCKET",
                "message": "runtime broker ping result missing pid",
                "retriable": True,
            }
            status["ping"] = result
            return status
        if pid is not None and ping_pid != pid:
            status["error"] = {
                "code": "E_RUNTIME_BROKER_STALE_SOCKET",
                "message": "runtime broker pid file and ping pid mismatch",
                "retriable": True,
            }
            status["ping"] = result
            return status
        ping_socket = result.get("socket_path")
        if not isinstance(ping_socket, str) or not ping_socket:
            status["error"] = {
                "code": "E_RUNTIME_BROKER_STALE_SOCKET",
                "message": "runtime broker ping result missing socket_path",
                "retriable": True,
            }
            status["ping"] = result
            return status
        if ping_socket != str(paths.socket_path):
            status["error"] = {
                "code": "E_RUNTIME_BROKER_STALE_SOCKET",
                "message": "runtime broker ping socket path mismatch",
                "retriable": True,
            }
            status["ping"] = result
            return status

        status["healthy"] = True
        status["instance_id"] = result.get("instance_id")
        status["active_buddy"] = result.get("active_buddy")
        status["socket_path"] = result.get("socket_path") or status["socket_path"]
        status["ping"] = result
        return status

    status["error"] = ping.get("error")
    return status

    return status


def cleanup_stale_broker_state(paths: BrokerPaths) -> None:
    for path in (paths.pid_file, paths.marker_file, paths.socket_path):
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except OSError:
            pass


def start_broker_process(
    paths: BrokerPaths,
    *,
    instance_json_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    broker_script = Path(__file__).resolve().parent / "broker.py"
    command = [
        "python3",
        str(broker_script),
        "serve",
        "--socket",
        str(paths.socket_path),
        "--pid-file",
        str(paths.pid_file),
        "--instance-json",
        str(instance_json_path),
        "--manifest",
        str(manifest_path),
    ]
    paths.log_file.parent.mkdir(parents=True, exist_ok=True)
    with paths.log_file.open("a", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=log_handle,
            cwd=Path(__file__).resolve().parents[2],
        )
    return {
        "ok": True,
        "pid": int(process.pid),
    }


def ensure_broker(
    paths: BrokerPaths,
    *,
    instance_json_path: Path,
    manifest_path: Path,
    expected_instance_id: str,
    expected_active_buddy: str,
    startup_timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    status = broker_status(
        paths,
        expected_instance_id=expected_instance_id,
        expected_active_buddy=expected_active_buddy,
    )
    if status.get("healthy") is True:
        if not paths.marker_file.parent.exists():
            paths.marker_file.parent.mkdir(parents=True, exist_ok=True)
        paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
        return {
            "ok": True,
            "socket_path": str(paths.socket_path),
            "status": status,
        }

    cleanup_stale_broker_state(paths)

    started = start_broker_process(
        paths,
        instance_json_path=instance_json_path,
        manifest_path=manifest_path,
    )
    if started.get("ok") is not True:
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_UNAVAILABLE",
                "message": "runtime broker failed to start",
                "retriable": True,
                "broker_status": {
                    "log_file": str(paths.log_file),
                    "socket_path": str(paths.socket_path),
                },
            },
        }

    deadline = time.monotonic() + max(0.05, startup_timeout_seconds)
    latest_status: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        ping = ping_broker(
            paths,
            expected_instance_id=expected_instance_id,
            expected_active_buddy=expected_active_buddy,
            timeout_seconds=0.5,
        )
        if ping.get("ok") is True:
            paths.marker_file.parent.mkdir(parents=True, exist_ok=True)
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            latest_status = broker_status(
                paths,
                expected_instance_id=expected_instance_id,
                expected_active_buddy=expected_active_buddy,
            )
            if latest_status.get("healthy") is True:
                return {
                    "ok": True,
                    "socket_path": str(paths.socket_path),
                    "status": latest_status,
                }
        time.sleep(0.1)

    broker_status_payload: dict[str, Any] = {
        "log_file": str(paths.log_file),
        "socket_path": str(paths.socket_path),
        "pid_file": str(paths.pid_file),
    }
    if latest_status is not None:
        broker_status_payload["latest_status"] = latest_status

    return {
        "ok": False,
        "error": {
            "code": "E_RUNTIME_BROKER_UNAVAILABLE",
            "message": "runtime broker failed to become healthy before timeout",
            "retriable": True,
            "broker_status": broker_status_payload,
        },
    }


def stop_broker(paths: BrokerPaths) -> dict[str, Any]:
    pid = read_pid(paths.pid_file)
    stopped = False
    if pid is not None and pid > 0 and pid_is_live(pid):
        try:
            os.kill(pid, 15)
        except OSError:
            pass
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and pid_is_live(pid):
            time.sleep(0.05)
        if pid_is_live(pid):
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        stopped = True
    cleanup_stale_broker_state(paths)
    return {
        "ok": True,
        "stopped": stopped,
        "socket_path": str(paths.socket_path),
    }
