"""Actor-scoped Browser Foundation runtime lifecycle."""

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


from buddyswitch.foundation.browser_runtime import lifecycle as browser_lifecycle  # noqa: E402
from buddyswitch.foundation.browser_runtime import target as cdp_target  # noqa: E402
from buddyswitch.launcher import daemon_state  # noqa: E402
import buddyswitch.foundation.process_runtime.process_identity as process_identity  # noqa: E402


PORT_START = 9222
PORT_END = 9321
DEFAULT_READY_ATTEMPTS = 50
DEFAULT_READY_DELAY_SECONDS = 0.1
_DETACHED_BROWSER_PROCESSES: list[subprocess.Popen[str]] = []


class BrowserRuntimeManagerError(RuntimeError):
    pass


def _remember_detached_browser_process(proc: subprocess.Popen[str]) -> None:
    _DETACHED_BROWSER_PROCESSES[:] = [item for item in _DETACHED_BROWSER_PROCESSES if item.poll() is None]
    _DETACHED_BROWSER_PROCESSES.append(proc)


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
        "marker_record",
        "marker_pid",
        "marker_pgid",
        "upstream_record",
        "upstream_pid",
        "upstream_pgid",
        "port_listener_pids",
        "profile_owned_processes",
        "tab_idle_target_count",
        "ownership",
    )

    def __init__(
        self,
        *,
        instance_root: Path,
        profile_dir: Path,
        recorded_port: int | None,
        marker_record: process_identity.RecordedProcess | None,
        marker_pid: int | None,
        marker_pgid: int | None,
        upstream_record: process_identity.RecordedProcess | None,
        upstream_pid: int | None,
        upstream_pgid: int | None,
        port_listener_pids: tuple[int, ...],
        profile_owned_processes: tuple[ProcessInfo, ...],
        tab_idle_target_count: int,
        ownership: str,
    ) -> None:
        self.instance_root = instance_root
        self.profile_dir = profile_dir
        self.recorded_port = recorded_port
        self.marker_record = marker_record
        self.marker_pid = marker_pid
        self.marker_pgid = marker_pgid
        self.upstream_record = upstream_record
        self.upstream_pid = upstream_pid
        self.upstream_pgid = upstream_pgid
        self.port_listener_pids = port_listener_pids
        self.profile_owned_processes = profile_owned_processes
        self.tab_idle_target_count = tab_idle_target_count
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
    cdp_target.create_background_target(_browser_url(port), "about:blank", timeout_seconds=5.0)
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
    for proc in tuple(_DETACHED_BROWSER_PROCESSES):
        if proc.pid != pid:
            continue
        if proc.poll() is None:
            return False
        _DETACHED_BROWSER_PROCESSES.remove(proc)
        return True
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


def _tab_idle_target_count(instance_root: Path) -> int:
    state = browser_lifecycle.read_page_idle_state(instance_root)
    targets = state.get("targets")
    return len(targets) if isinstance(targets, dict) else 0


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
    marker_file = _pid_file(instance_root)
    marker_pid = _read_numeric_file(marker_file)
    recorded_marker = process_identity.read_record(marker_file)
    marker_record = (
        recorded_marker
        if recorded_marker is not None and process_identity.is_running(recorded_marker)
        else None
    )
    marker_pgid = _process_pgid(marker_record.pid) if marker_record is not None else None
    runtime_dir = _runtime_browser_dir(instance_root)
    upstream_file = runtime_dir / "cockpit-upstream.pid"
    upstream_pid = _read_numeric_file(upstream_file)
    recorded_upstream = process_identity.read_record(upstream_file)
    upstream_record = (
        recorded_upstream
        if recorded_upstream is not None and process_identity.is_running(recorded_upstream)
        else None
    )
    upstream_pgid = _process_pgid(upstream_record.pid) if upstream_record is not None else None
    port_listener_pids = _port_listener_pids(recorded_port) if recorded_port is not None else []
    profile_processes: list[ProcessInfo] = []
    if marker_record is not None:
        command_line = _process_command_line(marker_record.pid)
        if _is_profile_owned_process(command_line, effective_profile_dir):
            profile_processes.append(
                ProcessInfo(
                    pid=marker_record.pid,
                    pgid=marker_pgid,
                    command_line=command_line,
                )
            )
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
        marker_record=marker_record,
        marker_pid=marker_pid,
        marker_pgid=marker_pgid,
        upstream_record=upstream_record,
        upstream_pid=upstream_pid,
        upstream_pgid=upstream_pgid,
        port_listener_pids=tuple(port_listener_pids),
        profile_owned_processes=tuple(profile_processes),
        tab_idle_target_count=_tab_idle_target_count(instance_root),
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
            process_identity.write_record(marker_file, proc.pid)
        finally:
            log_handle.close()

        for _attempt in range(DEFAULT_READY_ATTEMPTS):
            if _endpoint_ready(port):
                try:
                    _ensure_usable_page(port)
                except Exception:
                    break
                _set_browser_port(root, actor_id, port)
                if proc is not None:
                    _remember_detached_browser_process(proc)
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
            record = process_identity.read_record(marker_file)
            if record is not None:
                _terminate_owned_record(record)
        process_identity.remove_record(marker_file)
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
                tab_idle_target_count=snapshot.tab_idle_target_count,
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
            tab_idle_target_count=snapshot.tab_idle_target_count,
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
    if snapshot.upstream_record is None:
        return []
    if not _terminate_owned_record(snapshot.upstream_record):
        return []
    return [snapshot.upstream_record.pid]


def _marker_matches_profile(snapshot: BrowserResourceSnapshot) -> bool:
    if snapshot.marker_record is None:
        return False
    if not process_identity.is_running(snapshot.marker_record):
        return False
    command_line = _process_command_line(snapshot.marker_record.pid)
    return _is_profile_owned_process(command_line, snapshot.profile_dir)


def _terminate_owned_record(record: process_identity.RecordedProcess) -> bool:
    try:
        if not process_identity.is_running(record):
            return False
        try:
            pgid = os.getpgid(record.pid)
            current_pgid = os.getpgid(os.getpid())
        except (ProcessLookupError, PermissionError):
            return False
        if pgid == current_pgid or not process_identity.is_running(record):
            return False
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return False
        if not _wait_pgid_gone(pgid):
            if not process_identity.is_running(record) and not _pgid_alive(pgid):
                return True
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                return not _pgid_alive(pgid)
            _wait_pgid_gone(pgid)
        return True
    finally:
        _reap_child_pid(record.pid)


def _stop_owned_chrome_processes(snapshot: BrowserResourceSnapshot) -> list[int]:
    if not _marker_matches_profile(snapshot):
        return []
    assert snapshot.marker_record is not None
    if not _terminate_owned_record(snapshot.marker_record):
        return []
    return [snapshot.marker_record.pid]


def _verify_owned_chrome_gone(snapshot: BrowserResourceSnapshot) -> tuple[bool, list[int]]:
    remaining: list[int] = []
    if snapshot.marker_record is not None and process_identity.is_running(snapshot.marker_record):
        remaining.append(snapshot.marker_record.pid)
    return not remaining, remaining


def _verify_upstream_gone(snapshot: BrowserResourceSnapshot) -> tuple[bool, list[int]]:
    remaining: list[int] = []
    if snapshot.upstream_record is not None and process_identity.is_running(snapshot.upstream_record):
        remaining.append(snapshot.upstream_record.pid)
    return not remaining, remaining


def _clear_release_state(instance_root: Path, actor_id: str) -> bool:
    runtime_dir = _runtime_browser_dir(instance_root)
    changed = False
    for pid_file in (
        _pid_file(instance_root),
        runtime_dir / "cockpit-upstream.pid",
    ):
        if pid_file.exists() or process_identity.identity_file(pid_file).exists():
            changed = True
        process_identity.remove_record(pid_file)
    for path in (
        runtime_dir / "cockpit-upstream.pgid",
        runtime_dir / "page_idle.json",
        runtime_dir / "page_idle.lock",
    ):
        if path.exists():
            changed = True
        path.unlink(missing_ok=True)
    return _clear_browser_port(instance_root, actor_id) or changed


def _cancel_browser_owned_pending_schedules(instance_root: Path, actor_id: str) -> list[dict[str, Any]]:
    payload = _read_instance_payload(instance_root, actor_id)
    thread_id = payload.get("thread_id")
    return daemon_state.cancel_pending_schedules_by_source_owner(
        instance_root=instance_root,
        actor_id=actor_id,
        main_thread_id=thread_id if isinstance(thread_id, str) else None,
        source_owner="browser",
    )


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
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result.get("ok") is True else 1


def _parse_port(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return _validate_port(int(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid browser port: {value}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the BuddySwitch Actor-scoped browser runtime.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("acquire", "status", "release", "stop"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--instance-root", required=True)
        sub.add_argument("--actor-id", required=True)
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
        return _print_result(
            acquire(
                instance_root=Path(args.instance_root),
                actor_id=args.actor_id,
                requested_port=_parse_port(args.port),
                profile_dir=Path(args.profile_dir) if args.profile_dir else None,
                log_file=Path(args.log_file) if args.log_file else None,
                chrome_bin=Path(args.chrome_bin) if args.chrome_bin else None,
                reason=args.reason,
            )
        )
    if command == "status":
        return _print_result(
            status(
                instance_root=Path(args.instance_root),
                actor_id=args.actor_id,
                requested_port=_parse_port(args.port),
                profile_dir=Path(args.profile_dir) if args.profile_dir else None,
            )
        )
    if command == "release":
        return _print_result(release(instance_root=Path(args.instance_root), actor_id=args.actor_id, reason=args.reason))
    if command == "stop":
        return _print_result(stop(instance_root=Path(args.instance_root), actor_id=args.actor_id))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
