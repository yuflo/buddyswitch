"""Runtime broker lifecycle, health checks, and ensure/stop helpers."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import socket
import subprocess
import time
from typing import Any

from runtime_kernel import process_identity, protocol


@dataclass(frozen=True)
class BrokerPaths:
    socket_path: Path
    pid_file: Path
    marker_file: Path
    log_file: Path


def _append_runtime_broker_event(paths: BrokerPaths, event: str, **fields: Any) -> None:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "service": "runtime_broker",
        "event": event,
    }
    row.update(fields)
    paths.log_file.parent.mkdir(parents=True, exist_ok=True)
    with paths.log_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _runtime_broker_log_metadata(log_path: Path) -> dict[str, Any]:
    try:
        stat = log_path.stat()
    except FileNotFoundError:
        return {
            "path": str(log_path),
            "exists": False,
            "size_bytes": 0,
            "mtime": None,
            "last_event": None,
        }

    last_event: dict[str, Any] | None = None
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("service"), str) and isinstance(payload.get("event"), str):
                last_event = payload
    except OSError:
        last_event = None

    return {
        "path": str(log_path),
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "last_event": last_event,
    }


def resolve_socket_path(actor_id: str, instance_root: Path, marker_file: Path) -> Path:
    if marker_file.exists():
        raw = marker_file.read_text(encoding="utf-8").strip()
        if raw:
            return Path(raw)

    default_socket = instance_root / "runtime" / "runtime-broker.sock"
    if len(str(default_socket)) < 100:
        return default_socket

    socket_identity = f"{actor_id}\0{instance_root.expanduser().resolve(strict=False)}"
    digest = hashlib.sha1(socket_identity.encode("utf-8")).hexdigest()[:12]
    return Path(os.path.realpath("/tmp")) / f"buddyswitch-runtime-{digest}.sock"


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
    expected_actor_id: str,
    expected_active_role: str,
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
    if result.get("actor_id") != expected_actor_id:
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PERMISSION",
                "message": "runtime broker ping actor_id mismatch",
                "retriable": False,
            },
        }
    if result.get("active_role") != expected_active_role:
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_PERMISSION",
                "message": "runtime broker ping active_role mismatch",
                "retriable": False,
            },
        }

    return {
        "ok": True,
        "result": result,
    }


def _path_within_or_equal(candidate: Path, root: Path) -> bool:
    candidate_resolved = candidate.resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    if candidate_resolved == root_resolved:
        return True
    return root_resolved in candidate_resolved.parents


def _terminate_recorded_process(
    recorded: process_identity.RecordedProcess,
    *,
    timeout_seconds: float = 1.0,
) -> bool:
    if not process_identity.is_running(recorded):
        process_identity.reap_if_child(recorded.pid)
        return False
    try:
        if process_identity.matches(recorded):
            os.kill(recorded.pid, 15)
    except OSError:
        pass
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline and process_identity.is_running(recorded):
        time.sleep(0.05)
    if process_identity.is_running(recorded):
        try:
            if process_identity.matches(recorded):
                os.kill(recorded.pid, 9)
        except OSError:
            pass
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline and process_identity.is_running(recorded):
            time.sleep(0.05)
    process_identity.reap_if_child(recorded.pid)
    return True


def _cleanup_failed_startup_artifacts(
    paths: BrokerPaths,
    started_process: process_identity.RecordedProcess | None = None,
) -> None:
    if started_process is not None:
        _terminate_recorded_process(started_process)
    for path in (paths.marker_file, paths.socket_path):
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except OSError:
            pass

    recorded = process_identity.read_record(paths.pid_file)
    if recorded is None or not process_identity.is_running(recorded):
        try:
            if paths.pid_file.exists() or paths.pid_file.is_symlink():
                paths.pid_file.unlink()
            process_identity.identity_file(paths.pid_file).unlink(missing_ok=True)
        except OSError:
            pass


def broker_status(
    paths: BrokerPaths,
    *,
    expected_actor_id: str,
    expected_active_role: str,
    expected_workspace_root: Path | None = None,
) -> dict[str, Any]:
    pid = read_pid(paths.pid_file)
    recorded = process_identity.read_record(paths.pid_file)
    identity_matches = recorded is not None and process_identity.matches(recorded)
    pid_live = recorded is not None and process_identity.is_running(recorded)
    marker_value: str | None = None
    if paths.marker_file.exists():
        marker_value = paths.marker_file.read_text(encoding="utf-8").strip() or None

    status: dict[str, Any] = {
        "ok": True,
        "protocol": protocol.PROTOCOL,
        "pid": pid,
        "pid_live": pid_live,
        "identity_matches": identity_matches,
        "socket_path": str(paths.socket_path),
        "marker_path": str(paths.marker_file),
        "marker_value": marker_value,
        "log_file": str(paths.log_file),
        "log": _runtime_broker_log_metadata(paths.log_file),
        "healthy": False,
        "runtime_root": None,
        "runtime_workspace_root": None,
        "runtime_state_root": None,
        "cwd": None,
        "env_store_root": None,
        "runtime_workspace": None,
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
        expected_actor_id=expected_actor_id,
        expected_active_role=expected_active_role,
    )
    if ping.get("ok") is True:
        result = ping.get("result") if isinstance(ping.get("result"), dict) else {}
        runtime_root = result.get("runtime_root")
        runtime_workspace_root = result.get("runtime_workspace_root")
        runtime_state_root = result.get("runtime_state_root")
        cwd = result.get("cwd")
        env_store_root = result.get("env_store_root")
        runtime_workspace = result.get("runtime_workspace")
        if isinstance(runtime_workspace_root, str) and runtime_workspace_root.strip():
            status["runtime_workspace_root"] = runtime_workspace_root
        else:
            status["runtime_workspace_root"] = runtime_root if isinstance(runtime_root, str) and runtime_root.strip() else None
        status["runtime_root"] = status["runtime_workspace_root"]
        status["runtime_state_root"] = (
            runtime_state_root
            if isinstance(runtime_state_root, str) and runtime_state_root.strip()
            else env_store_root if isinstance(env_store_root, str) and env_store_root.strip() else None
        )
        status["cwd"] = cwd if isinstance(cwd, str) and cwd.strip() else None
        status["env_store_root"] = (
            env_store_root
            if isinstance(env_store_root, str) and env_store_root.strip()
            else status["runtime_state_root"]
        )
        status["runtime_workspace"] = runtime_workspace if isinstance(runtime_workspace, bool) else None

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

        if status["runtime_workspace"] is not True:
            status["error"] = {
                "code": "E_RUNTIME_BROKER_PERMISSION",
                "message": "runtime workspace marker is invalid",
                "retriable": False,
            }
            status["ping"] = result
            return status

        if expected_workspace_root is not None:
            expected_root = expected_workspace_root.resolve(strict=False)
            for fact_name in ("runtime_workspace_root", "cwd"):
                fact_value = status.get(fact_name)
                if not isinstance(fact_value, str) or not fact_value:
                    status["error"] = {
                        "code": "E_RUNTIME_BROKER_STALE_SOCKET",
                        "message": f"runtime root mismatch: missing {fact_name}",
                        "retriable": True,
                    }
                    status["ping"] = result
                    return status
                fact_path = Path(fact_value)
                if not _path_within_or_equal(fact_path, expected_root):
                    status["error"] = {
                        "code": "E_RUNTIME_BROKER_STALE_SOCKET",
                        "message": "runtime root mismatch: "
                        f"{fact_name}={fact_value} expected under {expected_root}",
                        "retriable": True,
                    }
                    status["ping"] = result
                    return status

        status["healthy"] = True
        status["actor_id"] = result.get("actor_id")
        status["active_role"] = result.get("active_role")
        status["socket_path"] = result.get("socket_path") or status["socket_path"]
        status["ping"] = result
        return status

    status["error"] = ping.get("error")
    return status


def cleanup_stale_broker_state(paths: BrokerPaths) -> None:
    for path in (
        paths.pid_file,
        process_identity.identity_file(paths.pid_file),
        paths.marker_file,
        paths.socket_path,
    ):
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
    repo_root_path: Path | None = None,
) -> dict[str, Any]:
    broker_script = Path(__file__).resolve().parent / "broker.py"
    command = [
        os.environ["BUDDYSWITCH_PYTHON"],
        str(broker_script),
        "serve",
        "--socket",
        str(paths.socket_path),
        "--pid-file",
        str(paths.pid_file),
        "--marker-file",
        str(paths.marker_file),
        "--log-file",
        str(paths.log_file),
        "--instance-json",
        str(instance_json_path),
        "--manifest",
        str(manifest_path),
    ]
    if repo_root_path is not None:
        command.extend(["--repo-root", str(repo_root_path)])
    paths.log_file.parent.mkdir(parents=True, exist_ok=True)
    with paths.log_file.open("a", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=log_handle,
            cwd=broker_script.parents[2],
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
    repo_root_path: Path | None = None,
    expected_actor_id: str,
    expected_active_role: str,
    expected_workspace_root: Path | None = None,
    startup_timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    status = broker_status(
        paths,
        expected_actor_id=expected_actor_id,
        expected_active_role=expected_active_role,
        expected_workspace_root=expected_workspace_root,
    )
    if status.get("healthy") is True:
        if not paths.marker_file.parent.exists():
            paths.marker_file.parent.mkdir(parents=True, exist_ok=True)
        paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
        _append_runtime_broker_event(
            paths,
            "runtime_broker_ready",
            actor_id=expected_actor_id,
            pid=status.get("pid"),
            socket_path=str(paths.socket_path),
        )
        return {
            "ok": True,
            "socket_path": str(paths.socket_path),
            "status": status,
        }

    recorded = process_identity.read_record(paths.pid_file)
    if recorded is not None and process_identity.is_running(recorded):
        stop_broker(paths)
    else:
        cleanup_stale_broker_state(paths)
    _append_runtime_broker_event(
        paths,
        "runtime_broker_start_requested",
        actor_id=expected_actor_id,
        socket_path=str(paths.socket_path),
    )

    started = start_broker_process(
        paths,
        instance_json_path=instance_json_path,
        manifest_path=manifest_path,
        repo_root_path=repo_root_path,
    )
    if started.get("ok") is not True:
        cleanup_stale_broker_state(paths)
        return {
            "ok": False,
            "error": {
                "code": "E_RUNTIME_BROKER_UNAVAILABLE",
                "message": "runtime broker failed to start",
                "retriable": True,
                "broker_status": {
                    "log_file": str(paths.log_file),
                    "socket_path": str(paths.socket_path),
                    "pid_file": str(paths.pid_file),
                },
            },
        }

    started_process: process_identity.RecordedProcess | None = None
    started_pid = started.get("pid")
    if isinstance(started_pid, int):
        started_identity = process_identity.start_identity(started_pid)
        if started_identity is not None:
            started_process = process_identity.RecordedProcess(
                started_pid,
                started_identity,
            )

    deadline = time.monotonic() + max(0.05, startup_timeout_seconds)
    latest_status: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        ping = ping_broker(
            paths,
            expected_actor_id=expected_actor_id,
            expected_active_role=expected_active_role,
            timeout_seconds=0.5,
        )
        if ping.get("ok") is True:
            paths.marker_file.parent.mkdir(parents=True, exist_ok=True)
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")

        latest_status = broker_status(
            paths,
            expected_actor_id=expected_actor_id,
            expected_active_role=expected_active_role,
            expected_workspace_root=expected_workspace_root,
        )
        if latest_status.get("healthy") is True:
            paths.marker_file.parent.mkdir(parents=True, exist_ok=True)
            paths.marker_file.write_text(str(paths.socket_path), encoding="utf-8")
            _append_runtime_broker_event(
                paths,
                "runtime_broker_ready",
                actor_id=expected_actor_id,
                pid=latest_status.get("pid"),
                socket_path=str(paths.socket_path),
            )
            return {
                "ok": True,
                "socket_path": str(paths.socket_path),
                "status": latest_status,
            }
        time.sleep(0.1)

    _cleanup_failed_startup_artifacts(paths, started_process)

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
    _append_runtime_broker_event(
        paths,
        "runtime_broker_stop_requested",
        socket_path=str(paths.socket_path),
    )
    pid = read_pid(paths.pid_file)
    recorded = process_identity.read_record(paths.pid_file)
    identity_matches = recorded is not None and process_identity.matches(recorded)
    stopped = False
    if recorded is not None and process_identity.is_running(recorded):
        stopped = _terminate_recorded_process(recorded)
    cleanup_stale_broker_state(paths)
    return {
        "ok": True,
        "stopped": stopped,
        "identity_mismatch": bool(pid is not None and not identity_matches),
        "socket_path": str(paths.socket_path),
    }
