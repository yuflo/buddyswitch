#!/usr/bin/env python3
"""Launcher-owned browser runtime lifecycle manager."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ENV = ROOT / "scripts" / "env"
LAUNCHER_DIR = ROOT / "tools" / "launcher"
if str(SCRIPTS_ENV) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ENV))
if str(LAUNCHER_DIR) not in sys.path:
    sys.path.insert(0, str(LAUNCHER_DIR))

import cdp_browser_lifecycle as browser_lifecycle  # noqa: E402
import cdp_background_page  # noqa: E402
import daemon_core  # noqa: E402


PORT_START = 9222
PORT_END = 9321
DEFAULT_READY_ATTEMPTS = 50
DEFAULT_READY_DELAY_SECONDS = 0.1


class BrowserRuntimeManagerError(RuntimeError):
    pass


class ProcessInfo:
    __slots__ = ("pid", "pgid", "command_line")

    def __init__(self, *, pid: int, pgid: int | None, command_line: str) -> None:
        self.pid = pid
        self.pgid = pgid
        self.command_line = command_line


class BrowserResourceSnapshot:
    __slots__ = (
        "instance_root",
        "profile_dir",
        "recorded_port",
        "marker_pid",
        "marker_pgid",
        "upstream_pid",
        "upstream_pgid",
        "port_listener_pids",
        "profile_owned_processes",
        "page_idle_page_count",
        "ownership",
    )

    def __init__(
        self,
        *,
        instance_root: Path,
        profile_dir: Path,
        recorded_port: int | None,
        marker_pid: int | None,
        marker_pgid: int | None,
        upstream_pid: int | None,
        upstream_pgid: int | None,
        port_listener_pids: tuple[int, ...],
        profile_owned_processes: tuple[ProcessInfo, ...],
        page_idle_page_count: int,
        ownership: str,
    ) -> None:
        self.instance_root = instance_root
        self.profile_dir = profile_dir
        self.recorded_port = recorded_port
        self.marker_pid = marker_pid
        self.marker_pgid = marker_pgid
        self.upstream_pid = upstream_pid
        self.upstream_pgid = upstream_pgid
        self.port_listener_pids = port_listener_pids
        self.profile_owned_processes = profile_owned_processes
        self.page_idle_page_count = page_idle_page_count
        self.ownership = ownership


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _instance_json(instance_root: Path) -> Path:
    return Path(instance_root) / "instance.json"


def _browser_dir(instance_root: Path) -> Path:
    return Path(instance_root) / "browser"


def _runtime_browser_dir(instance_root: Path) -> Path:
    return Path(instance_root) / "runtime" / "browser"


def _default_profile_dir(instance_root: Path) -> Path:
    return _browser_dir(instance_root) / "profile"


def _default_log_file(instance_root: Path) -> Path:
    return _browser_dir(instance_root) / "chrome.log"


def _pid_file(instance_root: Path) -> Path:
    return _browser_dir(instance_root) / "chrome.pid"


def _browser_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def _validate_port(port: object) -> int:
    if isinstance(port, bool) or not isinstance(port, int):
        raise BrowserRuntimeManagerError(f"invalid browser port: {port}")
    if port < 1 or port > 65535:
        raise BrowserRuntimeManagerError(f"invalid browser port: {port}")
    return port


def _read_instance_payload(instance_root: Path, actor_id: str) -> dict[str, Any]:
    path = _instance_json(instance_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserRuntimeManagerError(f"failed to read instance record: {exc}") from exc
    if not isinstance(payload, dict):
        raise BrowserRuntimeManagerError("instance record must be a JSON object")
    if payload.get("actor_id") != actor_id:
        raise BrowserRuntimeManagerError(f"actor id mismatch in {path}")
    return payload


def _write_instance_payload(instance_root: Path, payload: dict[str, Any]) -> None:
    path = _instance_json(instance_root)
    payload["updated_at"] = _utc_now()
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _set_browser_port(instance_root: Path, actor_id: str, port: int) -> bool:
    payload = _read_instance_payload(instance_root, actor_id)
    if payload.get("browser_port") == port:
        return False
    payload["browser_port"] = port
    _write_instance_payload(instance_root, payload)
    return True


def _clear_browser_port(instance_root: Path, actor_id: str) -> bool:
    payload = _read_instance_payload(instance_root, actor_id)
    if payload.get("browser_port") is None:
        return False
    payload["browser_port"] = None
    _write_instance_payload(instance_root, payload)
    return True


def _recorded_port(instance_root: Path, actor_id: str) -> int | None:
    payload = _read_instance_payload(instance_root, actor_id)
    port = payload.get("browser_port")
    if isinstance(port, bool) or not isinstance(port, int):
        return None
    if port < 1 or port > 65535:
        return None
    return port


def _port_available(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def _allocate_port() -> int:
    for port in range(PORT_START, PORT_END + 1):
        if _port_available(port):
            return port
    raise BrowserRuntimeManagerError(f"no free browser cockpit port found in range {PORT_START}..{PORT_END}")


def _http_json(url: str, timeout_seconds: float = 1.5) -> Any:
    request = Request(url, method="GET")
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise BrowserRuntimeManagerError(str(exc)) from exc


def _endpoint_ready(port: int) -> bool:
    try:
        payload = _http_json(f"{_browser_url(port)}/json/version", timeout_seconds=0.5)
    except BrowserRuntimeManagerError:
        return False
    return isinstance(payload, dict)


def _page_targets(port: int) -> list[dict[str, Any]]:
    payload = _http_json(f"{_browser_url(port)}/json/list", timeout_seconds=1.5)
    if not isinstance(payload, list):
        raise BrowserRuntimeManagerError("Chrome DevTools /json/list did not return a list")
    return [target for target in payload if isinstance(target, dict) and target.get("type") == "page"]


def _has_usable_page(port: int) -> bool:
    try:
        page_targets = _page_targets(port)
    except BrowserRuntimeManagerError:
        return False
    for target in page_targets:
        url = target.get("url")
        if not isinstance(url, str):
            continue
        normalized = url.strip().lower()
        if not normalized:
            continue
        if normalized == "about:blank":
            return True
        if normalized.startswith(("chrome://", "chrome-untrusted://", "devtools://")):
            continue
        return True
    return False


def _ensure_usable_page(port: int) -> None:
    if _has_usable_page(port):
        return
    cdp_background_page.create_background_target(_browser_url(port), "about:blank", timeout_seconds=5.0)
    if not _has_usable_page(port):
        raise BrowserRuntimeManagerError("browser endpoint reachable but no usable page target")


def _read_numeric_file(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text.isdigit():
        return None
    value = int(text)
    return value if value > 0 else None


def _pid_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    if _reap_child_pid(pid):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return not _pid_is_zombie(pid)


def _reap_child_pid(pid: int) -> bool:
    try:
        waited_pid, _status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return False
    return waited_pid == pid


def _pid_is_zombie(pid: int) -> bool:
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "stat="],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return False
    stat = completed.stdout.strip()
    return stat.startswith("Z")


def _wait_pid_gone(pid: int, timeout_seconds: float = 1.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _reap_child_pid(pid):
            return True
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_alive(pid)


def _pgid_alive(pgid: int | None) -> bool:
    if pgid is None:
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return _pgid_has_live_process(pgid)


def _pgid_has_live_process(pgid: int) -> bool:
    completed = subprocess.run(
        ["ps", "-axo", "pgid=,stat="],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return True
    for raw_line in completed.stdout.splitlines():
        parts = raw_line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].lstrip("-").isdigit():
            continue
        if int(parts[0]) == pgid and not parts[1].startswith("Z"):
            return True
    return False


def _wait_pgid_gone(pgid: int, timeout_seconds: float = 1.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _pgid_alive(pgid):
            return True
        time.sleep(0.05)
    return not _pgid_alive(pgid)


def _terminate_pid(pid: int | None) -> None:
    if not _pid_alive(pid):
        return
    assert pid is not None
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    if not _wait_pid_gone(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        _wait_pid_gone(pid)


def _terminate_pgid(pgid: int | None) -> bool:
    if pgid is None:
        return False
    try:
        current_pgid = os.getpgid(os.getpid())
    except OSError:
        current_pgid = None
    if current_pgid == pgid:
        return False
    if not _pgid_alive(pgid):
        return True
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    if not _wait_pgid_gone(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        _wait_pgid_gone(pgid)
    return True


def _process_command_line(pid: int) -> str:
    completed = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "command="],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _process_pgid(pid: int | None) -> int | None:
    if pid is None:
        return None
    if not _pid_alive(pid):
        return None
    try:
        return os.getpgid(pid)
    except ProcessLookupError:
        return None
    except PermissionError:
        return None


def _all_processes() -> list[ProcessInfo]:
    completed = subprocess.run(
        ["ps", "-axo", "pid=,pgid=,command="],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    processes: list[ProcessInfo] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].lstrip("-").isdigit():
            continue
        command_line = parts[2] if len(parts) > 2 else ""
        processes.append(ProcessInfo(pid=int(parts[0]), pgid=int(parts[1]), command_line=command_line))
    return processes


def _user_data_dir_arg(profile_dir: Path) -> str:
    return f"--user-data-dir={profile_dir}"


def _has_user_data_dir(command_line: str) -> bool:
    return "--user-data-dir=" in command_line


def _canonical_path_text(path: Path | str) -> str:
    return str(Path(path).expanduser().resolve(strict=False))


def _user_data_dir_values(command_line: str) -> list[str]:
    values: list[str] = []
    for match in re.finditer(r"--user-data-dir=(\"[^\"]+\"|'[^']+'|\S+)", command_line):
        value = match.group(1).strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        if value:
            values.append(value)
    return values


def _is_profile_owned_process(command_line: str, profile_dir: Path) -> bool:
    expected = str(profile_dir)
    expected_canonical = _canonical_path_text(profile_dir)
    for value in _user_data_dir_values(command_line):
        if value == expected or _canonical_path_text(value) == expected_canonical:
            return True
    return False



def _profile_owned_processes(profile_dir: Path) -> list[ProcessInfo]:
    return [
        process
        for process in _all_processes()
        if process.pid != os.getpid() and _pid_alive(process.pid) and _is_profile_owned_process(process.command_line, profile_dir)
    ]


def _port_listener_pids(port: int) -> list[int]:
    completed = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    pids: list[int] = []
    for line in completed.stdout.splitlines():
        text = line.strip()
        if text.isdigit():
            pids.append(int(text))
    return pids


def _page_idle_page_count(instance_root: Path) -> int:
    state = browser_lifecycle._read_page_idle_state(instance_root)
    pages = state.get("pages")
    return len(pages) if isinstance(pages, dict) else 0


def _classify_snapshot(
    *,
    recorded_port: int | None,
    marker_pid: int | None,
    marker_pgid: int | None,
    port_listener_pids: list[int],
    profile_owned_processes: list[ProcessInfo],
    profile_dir: Path,
) -> str:
    del marker_pgid
    endpoint_ready = recorded_port is not None and _endpoint_ready(recorded_port)
    if profile_owned_processes:
        return "owned" if endpoint_ready else "orphaned_owned"
    if endpoint_ready:
        found_foreign = False
        for pid in port_listener_pids:
            command_line = _process_command_line(pid)
            if _is_profile_owned_process(command_line, profile_dir):
                return "owned"
            if _has_user_data_dir(command_line):
                found_foreign = True
        if found_foreign:
            return "foreign"
        return "unknown"
    if recorded_port is not None or marker_pid is not None:
        return "stale_state"
    return "inactive"


def _discover_resources(
    *,
    instance_root: Path,
    actor_id: str,
    profile_dir: Path | None = None,
) -> BrowserResourceSnapshot:
    _read_instance_payload(instance_root, actor_id)
    effective_profile_dir = profile_dir if profile_dir is not None else _default_profile_dir(instance_root)
    recorded_port = _recorded_port(instance_root, actor_id)
    marker_pid = _read_numeric_file(_pid_file(instance_root))
    marker_pgid = _process_pgid(marker_pid)
    runtime_dir = _runtime_browser_dir(instance_root)
    upstream_pid = _read_numeric_file(runtime_dir / "cockpit-upstream.pid")
    upstream_pgid = _read_numeric_file(runtime_dir / "cockpit-upstream.pgid")
    port_listener_pids = _port_listener_pids(recorded_port) if recorded_port is not None else []
    profile_processes = _profile_owned_processes(effective_profile_dir)
    ownership = _classify_snapshot(
        recorded_port=recorded_port,
        marker_pid=marker_pid,
        marker_pgid=marker_pgid,
        port_listener_pids=port_listener_pids,
        profile_owned_processes=profile_processes,
        profile_dir=effective_profile_dir,
    )
    return BrowserResourceSnapshot(
        instance_root=instance_root,
        profile_dir=effective_profile_dir,
        recorded_port=recorded_port,
        marker_pid=marker_pid,
        marker_pgid=marker_pgid,
        upstream_pid=upstream_pid,
        upstream_pgid=upstream_pgid,
        port_listener_pids=tuple(port_listener_pids),
        profile_owned_processes=tuple(profile_processes),
        page_idle_page_count=_page_idle_page_count(instance_root),
        ownership=ownership,
    )


def ownership_state(instance_root: Path, actor_id: str) -> str:
    return _discover_resources(instance_root=Path(instance_root), actor_id=actor_id).ownership


def _find_chrome_bin(chrome_bin: Path | str | None) -> Path:
    if chrome_bin is not None:
        path = Path(chrome_bin)
        if path.exists() and os.access(path, os.X_OK):
            return path
        raise BrowserRuntimeManagerError(f"Chrome binary not found: {path}")
    env_bin = os.environ.get("BUDDYSWITCH_BROWSER_CHROME_BIN")
    if env_bin:
        return _find_chrome_bin(Path(env_bin))
    for candidate in (
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    raise BrowserRuntimeManagerError("Chrome binary not found. Set BUDDYSWITCH_BROWSER_CHROME_BIN or install Chrome.")


def _choose_port(instance_root: Path, actor_id: str, requested_port: int | None) -> int:
    if requested_port is not None:
        return _validate_port(requested_port)
    recorded = _recorded_port(instance_root, actor_id)
    if recorded is not None:
        state = ownership_state(instance_root, actor_id)
        if state == "owned":
            return recorded
        if state in {"inactive", "stale_state"} and _port_available(recorded):
            return recorded
    return _allocate_port()


def _success(**fields: object) -> dict[str, object]:
    return {"ok": True, **fields}


def _failure(exc: Exception) -> dict[str, object]:
    return {
        "ok": False,
        "error": {
            "code": "E_BROWSER_RUNTIME_MANAGER",
            "message": str(exc),
        },
        "state_changed": False,
        "durability": "none",
    }


def acquire(
    *,
    instance_root: Path | str,
    actor_id: str,
    requested_port: int | None = None,
    profile_dir: Path | str | None = None,
    log_file: Path | str | None = None,
    chrome_bin: Path | str | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    del reason
    root = Path(instance_root)
    try:
        _read_instance_payload(root, actor_id)
        port = _choose_port(root, actor_id, requested_port)
        browser_url = _browser_url(port)
        effective_profile_dir = Path(profile_dir) if profile_dir is not None else _default_profile_dir(root)
        effective_log_file = Path(log_file) if log_file is not None else _default_log_file(root)

        if _endpoint_ready(port):
            _ensure_usable_page(port)
            changed = _set_browser_port(root, actor_id, port)
            return _success(
                browser_url=browser_url,
                browser_port=port,
                profile_dir=str(effective_profile_dir),
                log_file=str(effective_log_file),
                ready=True,
                ownership=ownership_state(root, actor_id),
                state_changed=changed,
                durability="runtime",
                message=f"Browser cockpit ready: {browser_url}",
            )

        chrome_path = _find_chrome_bin(chrome_bin)
        effective_profile_dir.mkdir(parents=True, exist_ok=True)
        effective_log_file.parent.mkdir(parents=True, exist_ok=True)
        _browser_dir(root).mkdir(parents=True, exist_ok=True)

        log_handle = effective_log_file.open("a", encoding="utf-8")
        proc: subprocess.Popen[str] | None = None
        marker_file = _pid_file(root)
        try:
            proc = subprocess.Popen(
                [
                    str(chrome_path),
                    f"--remote-debugging-port={port}",
                    f"--user-data-dir={effective_profile_dir}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "about:blank",
                ],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            marker_file.write_text(f"{proc.pid}\n", encoding="utf-8")
        finally:
            log_handle.close()

        for _attempt in range(DEFAULT_READY_ATTEMPTS):
            if _endpoint_ready(port):
                try:
                    _ensure_usable_page(port)
                except Exception:
                    break
                _set_browser_port(root, actor_id, port)
                return _success(
                    browser_url=browser_url,
                    browser_port=port,
                    profile_dir=str(effective_profile_dir),
                    log_file=str(effective_log_file),
                    ready=True,
                    ownership="owned",
                    state_changed=True,
                    durability="runtime",
                    message=f"Browser cockpit ready: {browser_url}",
                )
            time.sleep(DEFAULT_READY_DELAY_SECONDS)

        if proc is not None:
            _terminate_pid(proc.pid)
        marker_file.unlink(missing_ok=True)
        raise BrowserRuntimeManagerError(f"Browser cockpit not ready: {browser_url}")
    except Exception as exc:
        return _failure(exc)


def status(
    *,
    instance_root: Path | str,
    actor_id: str,
    requested_port: int | None = None,
    profile_dir: Path | str | None = None,
) -> dict[str, object]:
    root = Path(instance_root)
    try:
        effective_profile_dir = Path(profile_dir) if profile_dir is not None else _default_profile_dir(root)
        snapshot = _discover_resources(instance_root=root, actor_id=actor_id, profile_dir=effective_profile_dir)
        port = _validate_port(requested_port) if requested_port is not None else snapshot.recorded_port
        if port is None:
            return _success(
                ready=False,
                browser_port=None,
                browser_url=None,
                profile_dir=str(effective_profile_dir),
                ownership=snapshot.ownership,
                profile_owned_pids=[process.pid for process in snapshot.profile_owned_processes],
                page_idle_page_count=snapshot.page_idle_page_count,
                state_changed=False,
                durability="none",
                message="Browser cockpit not ready: no browser port recorded",
            )
        ready = _endpoint_ready(port) and _has_usable_page(port)
        return _success(
            ready=ready,
            browser_port=port,
            browser_url=_browser_url(port),
            profile_dir=str(effective_profile_dir),
            ownership=snapshot.ownership,
            profile_owned_pids=[process.pid for process in snapshot.profile_owned_processes],
            port_listener_pids=list(snapshot.port_listener_pids),
            page_idle_page_count=snapshot.page_idle_page_count,
            state_changed=False,
            durability="runtime" if ready else "none",
            message=(
                f"Browser cockpit ready: {_browser_url(port)}"
                if ready
                else f"Browser cockpit not ready: {_browser_url(port)}"
            ),
        )
    except Exception as exc:
        return _failure(exc)


def _release_mode(reason: str | None, *, force: bool = False) -> str:
    if force:
        return "explicit_cleanup"
    normalized = reason.strip() if isinstance(reason, str) else ""
    if normalized in {"page_idle_empty", "browser.cockpit.release"}:
        return "automatic_idle"
    if normalized == "orphan_repair":
        return "orphan_repair"
    return "explicit_cleanup"


def _stop_upstream_processes(snapshot: BrowserResourceSnapshot) -> list[int]:
    terminated: list[int] = []
    if snapshot.upstream_pgid is not None:
        _terminate_pgid(snapshot.upstream_pgid)
    if snapshot.upstream_pid is not None:
        _terminate_pid(snapshot.upstream_pid)
        terminated.append(snapshot.upstream_pid)
    return terminated


def _marker_matches_profile(snapshot: BrowserResourceSnapshot) -> bool:
    if snapshot.marker_pid is None or not _pid_alive(snapshot.marker_pid):
        return False
    command_line = _process_command_line(snapshot.marker_pid)
    return _is_profile_owned_process(command_line, snapshot.profile_dir)


def _stop_owned_chrome_processes(snapshot: BrowserResourceSnapshot) -> list[int]:
    terminated: list[int] = []
    attempted_pids: set[int] = set()
    if _marker_matches_profile(snapshot):
        if snapshot.marker_pgid is not None:
            _terminate_pgid(snapshot.marker_pgid)
        assert snapshot.marker_pid is not None
        _terminate_pid(snapshot.marker_pid)
        attempted_pids.add(snapshot.marker_pid)
        terminated.append(snapshot.marker_pid)
    attempted_pgids: set[int] = {snapshot.marker_pgid} if snapshot.marker_pgid is not None else set()
    for process in snapshot.profile_owned_processes:
        if process.pid in attempted_pids:
            continue
        if process.pgid is not None and process.pgid not in attempted_pgids:
            _terminate_pgid(process.pgid)
            attempted_pgids.add(process.pgid)
        if _pid_alive(process.pid):
            _terminate_pid(process.pid)
        attempted_pids.add(process.pid)
        terminated.append(process.pid)
    return terminated


def _owned_listener_pids(port: int | None, profile_dir: Path) -> list[int]:
    if port is None:
        return []
    owned: list[int] = []
    for pid in _port_listener_pids(port):
        if _is_profile_owned_process(_process_command_line(pid), profile_dir):
            owned.append(pid)
    return owned


def _verify_owned_chrome_gone(snapshot: BrowserResourceSnapshot) -> tuple[bool, list[int]]:
    owned_processes = _profile_owned_processes(snapshot.profile_dir)
    owned_listener_pids = _owned_listener_pids(snapshot.recorded_port, snapshot.profile_dir)
    remaining = sorted({process.pid for process in owned_processes}.union(owned_listener_pids))
    return not remaining, remaining


def _verify_upstream_gone(snapshot: BrowserResourceSnapshot) -> tuple[bool, list[int]]:
    remaining: list[int] = []
    if snapshot.upstream_pid is not None and _pid_alive(snapshot.upstream_pid):
        remaining.append(snapshot.upstream_pid)
    return not remaining, remaining


def _clear_release_state(instance_root: Path, actor_id: str) -> bool:
    runtime_dir = _runtime_browser_dir(instance_root)
    changed = False
    for path in (
        _pid_file(instance_root),
        runtime_dir / "cockpit-upstream.pid",
        runtime_dir / "cockpit-upstream.pgid",
        runtime_dir / "page_idle.json",
        runtime_dir / "page_idle.lock",
    ):
        if path.exists():
            changed = True
        path.unlink(missing_ok=True)
    return _clear_browser_port(instance_root, actor_id) or changed


def _cancel_browser_owned_pending_schedules(instance_root: Path, actor_id: str) -> list[dict[str, Any]]:
    state_path = daemon_core.daemon_state_file(instance_root)
    if not state_path.exists():
        return []
    payload = _read_instance_payload(instance_root, actor_id)
    thread_id = payload.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id:
        raise BrowserRuntimeManagerError("instance record has no thread id for daemon schedule cleanup")
    state = daemon_core.DaemonState.load(
        instance_root=instance_root,
        actor_id=actor_id,
        main_thread_id=thread_id,
    )
    return state.cancel_pending_schedules_by_source_owner("browser")


def _release_engine(
    *,
    instance_root: Path,
    actor_id: str,
    reason: str | None,
    force: bool = False,
) -> dict[str, object]:
    snapshot = _discover_resources(instance_root=instance_root, actor_id=actor_id)
    mode = _release_mode(reason, force=force)
    ownership = snapshot.ownership
    if ownership == "inactive":
        canceled_schedules = _cancel_browser_owned_pending_schedules(instance_root, actor_id)
        canceled_ids = [row["schedule_id"] for row in canceled_schedules]
        return _success(
            handled=bool(canceled_schedules),
            skip_reason="inactive",
            ownership=ownership,
            release_mode=mode,
            canceled_browser_schedule_ids=canceled_ids,
            canceled_browser_schedule_count=len(canceled_ids),
            state_changed=bool(canceled_schedules),
            durability="runtime" if canceled_schedules else "none",
            message=f"Browser cockpit release skipped: no browser resources recorded for {actor_id}",
        )

    upstream_pids = _stop_upstream_processes(snapshot)
    chrome_pids: list[int] = []
    if ownership in {"owned", "orphaned_owned"}:
        chrome_pids = _stop_owned_chrome_processes(snapshot)

    upstream_ok, upstream_remaining = _verify_upstream_gone(snapshot)
    chrome_ok = True
    chrome_remaining: list[int] = []
    if ownership in {"owned", "orphaned_owned"}:
        chrome_ok, chrome_remaining = _verify_owned_chrome_gone(snapshot)
    if not upstream_ok or not chrome_ok:
        return _failure(
            BrowserRuntimeManagerError(
                "browser release verification failed"
                f"; remaining_upstream={upstream_remaining}"
                f"; remaining_owned_chrome={chrome_remaining}"
            )
        ) | {
            "handled": False,
            "ownership": ownership,
            "release_mode": mode,
            "remaining_upstream_pids": upstream_remaining,
            "remaining_owned_chrome_pids": chrome_remaining,
            "terminated_upstream_pids": upstream_pids,
            "terminated_chrome_pids": chrome_pids,
        }

    changed = _clear_release_state(instance_root, actor_id)
    canceled_schedules = _cancel_browser_owned_pending_schedules(instance_root, actor_id)
    canceled_ids = [row["schedule_id"] for row in canceled_schedules]
    return _success(
        handled=True,
        skip_reason=None,
        ownership=ownership,
        release_mode=mode,
        terminated_upstream_pids=upstream_pids,
        terminated_chrome_pids=chrome_pids,
        canceled_browser_schedule_ids=canceled_ids,
        canceled_browser_schedule_count=len(canceled_ids),
        verification={"upstream_gone": upstream_ok, "owned_chrome_gone": chrome_ok},
        state_changed=(
            changed
            or bool(upstream_pids)
            or bool(chrome_pids)
            or bool(canceled_schedules)
            or ownership in {"owned", "orphaned_owned", "stale_state"}
        ),
        durability="runtime",
        message=f"Browser cockpit released: {actor_id}",
    )


def stop(*, instance_root: Path | str, actor_id: str) -> dict[str, object]:
    root = Path(instance_root)
    try:
        return _release_engine(instance_root=root, actor_id=actor_id, reason="manual_stop", force=True)
    except Exception as exc:
        return _failure(exc)


def release(*, instance_root: Path | str, actor_id: str, reason: str | None = None) -> dict[str, object]:
    root = Path(instance_root)
    try:
        return _release_engine(instance_root=root, actor_id=actor_id, reason=reason)
    except Exception as exc:
        return _failure(exc)


def _print_result(result: dict[str, object]) -> int:
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("ok") is True else 1


def _print_human_result(command: str, result: dict[str, object]) -> int:
    ok = result.get("ok") is True
    ready = result.get("ready") is True
    message = result.get("message")
    if not ok:
        error = result.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            message = error["message"]
        elif not isinstance(message, str):
            message = "Browser runtime manager failed"
    if not isinstance(message, str):
        message = ""

    output_stream = sys.stdout
    exit_code = 0
    if not ok:
        output_stream = sys.stderr
        exit_code = 1
    elif command == "status" and not ready:
        output_stream = sys.stderr
        exit_code = 1

    if message:
        print(message, file=output_stream)
    profile_dir = result.get("profile_dir")
    if isinstance(profile_dir, str) and profile_dir.strip():
        print(f"Profile: {profile_dir}", file=output_stream)
    return exit_code


def _emit_result(command: str, result: dict[str, object], output: str) -> int:
    if output == "human":
        return _print_human_result(command, result)
    return _print_result(result)


def _parse_port(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return _validate_port(int(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid browser port: {value}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage BuddySwitch launcher-owned browser runtime.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("acquire", "status", "release", "stop"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--instance-root", required=True)
        sub.add_argument("--actor-id", required=True)
        sub.add_argument("--output", choices=("json", "human"), default="json")
        if name in {"acquire", "status"}:
            sub.add_argument("--port")
            sub.add_argument("--profile-dir")
        if name == "acquire":
            sub.add_argument("--log-file")
            sub.add_argument("--chrome-bin")
            sub.add_argument("--reason")
        if name == "release":
            sub.add_argument("--reason")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    command = args.command
    if command == "acquire":
        return _emit_result(
            command,
            acquire(
                instance_root=Path(args.instance_root),
                actor_id=args.actor_id,
                requested_port=_parse_port(args.port),
                profile_dir=Path(args.profile_dir) if args.profile_dir else None,
                log_file=Path(args.log_file) if args.log_file else None,
                chrome_bin=Path(args.chrome_bin) if args.chrome_bin else None,
                reason=args.reason,
            ),
            args.output,
        )
    if command == "status":
        return _emit_result(
            command,
            status(
                instance_root=Path(args.instance_root),
                actor_id=args.actor_id,
                requested_port=_parse_port(args.port),
                profile_dir=Path(args.profile_dir) if args.profile_dir else None,
            ),
            args.output,
        )
    if command == "release":
        return _emit_result(
            command,
            release(instance_root=Path(args.instance_root), actor_id=args.actor_id, reason=args.reason),
            args.output,
        )
    if command == "stop":
        return _emit_result(command, stop(instance_root=Path(args.instance_root), actor_id=args.actor_id), args.output)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
