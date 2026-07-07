#!/usr/bin/env python3
"""Central daemon process entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import central_daemon_core  # noqa: E402
from env.tool_runtime import daemon_client  # noqa: E402


STOP_GRACE_SECONDS = 2.0
POLL_SECONDS = 0.05
PROBE_IDENTITY_ID = "act-central-daemon-probe"
READY_REACHABILITY_STATUSES = {"online", "registered_offline", "never_registered"}


def read_pid(pid_file: Path) -> int | None:
    try:
        raw = pid_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate_pid(pid: int) -> bool:
    if not pid_is_live(pid):
        return True
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + STOP_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not pid_is_live(pid):
            return True
        time.sleep(POLL_SECONDS)
    if pid_is_live(pid):
        os.kill(pid, signal.SIGKILL)
    return True


def cleanup_runtime_files(paths: central_daemon_core.CentralDaemonPaths) -> None:
    for path in (paths.pid_file, paths.socket_path):
        try:
            path.unlink()
        except OSError:
            pass


def register_test_process(paths: central_daemon_core.CentralDaemonPaths, *, pid: int) -> None:
    registry_raw = os.environ.get("BUDDYSWITCH_TEST_PROCESS_REGISTRY")
    if not isinstance(registry_raw, str) or not registry_raw.strip():
        return
    payload: dict[str, Any] = {
        "kind": "central_daemon",
        "pid": pid,
        "shared_root": str(paths.shared_root),
        "pid_file": str(paths.pid_file),
        "socket_path": str(paths.socket_path),
    }
    try:
        payload["pgid"] = os.getpgid(pid)
    except OSError:
        pass
    registry_path = Path(registry_raw).expanduser().resolve(strict=False)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def ping_central_daemon(*, socket_path: Path) -> dict[str, Any]:
    ping = daemon_client.request_central_daemon("daemon.ping", {}, socket_path=socket_path)
    reachability = daemon_client.check_reachability(
        target_identity_id=PROBE_IDENTITY_ID,
        socket_path=socket_path,
    )
    if (
        reachability.get("target_identity_id") != PROBE_IDENTITY_ID
        or reachability.get("reachability_status") not in READY_REACHABILITY_STATUSES
    ):
        raise RuntimeError("central daemon does not support identity reachability protocol")
    ping["identity_reachability_protocol"] = True
    return ping


def start_central_daemon(paths: central_daemon_core.CentralDaemonPaths) -> dict[str, Any]:
    pid = read_pid(paths.pid_file)
    if pid is not None and pid_is_live(pid):
        try:
            ping = ping_central_daemon(socket_path=paths.socket_path)
            return {
                "ok": True,
                "started": False,
                "pid": pid,
                "socket_path": str(paths.socket_path),
                "ping": ping,
            }
        except Exception:
            terminate_pid(pid)
            cleanup_runtime_files(paths)

    paths.run_dir.mkdir(parents=True, exist_ok=True)
    paths.log_file.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "serve",
        "--shared-root",
        str(paths.shared_root),
    ]
    with paths.log_file.open("ab") as log_handle:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(ROOT),
        )
    paths.pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    register_test_process(paths, pid=process.pid)

    deadline = time.monotonic() + 5.0
    ping: dict[str, Any] = {}
    while time.monotonic() < deadline:
        if process.poll() is not None:
            cleanup_runtime_files(paths)
            raise RuntimeError(f"central daemon exited before ready; see {paths.log_file}")
        try:
            ping = ping_central_daemon(socket_path=paths.socket_path)
            break
        except Exception:
            time.sleep(POLL_SECONDS)
    else:
        terminate_pid(process.pid)
        cleanup_runtime_files(paths)
        raise RuntimeError(f"central daemon did not become ready; see {paths.log_file}")

    return {
        "ok": True,
        "started": True,
        "pid": process.pid,
        "socket_path": str(paths.socket_path),
        "ping": ping,
    }


def status_central_daemon(paths: central_daemon_core.CentralDaemonPaths) -> dict[str, Any]:
    pid = read_pid(paths.pid_file)
    pid_live = pid is not None and pid_is_live(pid)
    ping: dict[str, Any] | None = None
    healthy = False
    if pid_live:
        try:
            ping = ping_central_daemon(socket_path=paths.socket_path)
            healthy = True
        except Exception:
            healthy = False
    return {
        "healthy": healthy,
        "pid": pid,
        "pid_live": bool(pid_live),
        "socket_path": str(paths.socket_path),
        "pid_file": str(paths.pid_file),
        "log_file": str(paths.log_file),
        "registry_path": str(paths.registry_path),
        "ping": ping,
    }


def stop_central_daemon(paths: central_daemon_core.CentralDaemonPaths) -> dict[str, Any]:
    pid = read_pid(paths.pid_file)
    terminated = True
    if pid is not None and pid_is_live(pid):
        terminated = terminate_pid(pid)
    cleanup_runtime_files(paths)
    return {
        "ok": True,
        "pid": pid,
        "terminated": bool(terminated),
        "socket_path": str(paths.socket_path),
    }


def stop_if_idle(paths: central_daemon_core.CentralDaemonPaths) -> dict[str, Any]:
    try:
        registry = daemon_client.request_central_daemon("daemon.registry", {}, socket_path=paths.socket_path)
    except Exception:
        return stop_central_daemon(paths)
    actors = registry.get("actors") if isinstance(registry.get("actors"), list) else []
    online = [row for row in actors if isinstance(row, dict) and row.get("status") == "online"]
    if online:
        return {
            "ok": True,
            "stopped": False,
            "online_actor_count": len(online),
            "socket_path": str(paths.socket_path),
        }
    stopped = stop_central_daemon(paths)
    stopped["stopped"] = True
    stopped["online_actor_count"] = 0
    return stopped


def serve(paths: central_daemon_core.CentralDaemonPaths) -> int:
    service = central_daemon_core.CentralDaemonService(paths=paths)
    server = central_daemon_core.CentralDaemonSocketServer(service=service)
    server.serve_forever()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("serve", "start", "status", "stop", "stop-if-idle"):
        item = sub.add_parser(command)
        item.add_argument("--shared-root", required=True, type=Path)
    request = sub.add_parser("request")
    request.add_argument("--shared-root", required=True, type=Path)
    request.add_argument("--method", required=True)
    request.add_argument("--params", default="{}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = central_daemon_core.central_daemon_paths(args.shared_root)
    try:
        if args.command == "serve":
            return serve(paths)
        if args.command == "start":
            payload = start_central_daemon(paths)
        elif args.command == "status":
            payload = status_central_daemon(paths)
        elif args.command == "stop":
            payload = stop_central_daemon(paths)
        elif args.command == "stop-if-idle":
            payload = stop_if_idle(paths)
        elif args.command == "request":
            params = json.loads(args.params)
            if not isinstance(params, dict):
                raise ValueError("--params must decode to an object")
            payload = daemon_client.request_central_daemon(args.method, params, socket_path=paths.socket_path)
        else:
            return 2
        print(json.dumps(payload, ensure_ascii=True))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
