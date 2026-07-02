#!/usr/bin/env python3
"""Launcher-owned browser runtime lifecycle manager."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
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
if str(SCRIPTS_ENV) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ENV))

import cdp_browser_lifecycle as browser_lifecycle  # noqa: E402


PORT_START = 9222
PORT_END = 9321
DEFAULT_READY_ATTEMPTS = 50
DEFAULT_READY_DELAY_SECONDS = 0.1


class BrowserRuntimeManagerError(RuntimeError):
    pass


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
    browser_lifecycle.create_background_page_target(_browser_url(port), "about:blank")
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
    return True


def _reap_child_pid(pid: int) -> bool:
    try:
        waited_pid, _status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return False
    return waited_pid == pid


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
    return True


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


def ownership_state(instance_root: Path, actor_id: str) -> str:
    port = _recorded_port(instance_root, actor_id)
    if port is None:
        return "inactive"
    if not _endpoint_ready(port):
        return "inactive"
    marker_pid = _read_numeric_file(_pid_file(instance_root))
    if _pid_alive(marker_pid):
        return "owned"
    if marker_pid is not None:
        _pid_file(instance_root).unlink(missing_ok=True)

    target_profile = str(_default_profile_dir(instance_root))
    found_foreign = False
    for pid in _port_listener_pids(port):
        command_line = _process_command_line(pid)
        if f"--user-data-dir={target_profile}" in command_line:
            return "owned"
        if "--user-data-dir=" in command_line:
            found_foreign = True
    if found_foreign:
        return "foreign"
    return "unknown"


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
        if state == "inactive" and _port_available(recorded):
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
        _read_instance_payload(root, actor_id)
        effective_profile_dir = Path(profile_dir) if profile_dir is not None else _default_profile_dir(root)
        port = _validate_port(requested_port) if requested_port is not None else _recorded_port(root, actor_id)
        if port is None:
            return _success(
                ready=False,
                browser_port=None,
                browser_url=None,
                profile_dir=str(effective_profile_dir),
                ownership="inactive",
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
            ownership=ownership_state(root, actor_id),
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


def _stop_upstream(instance_root: Path) -> None:
    runtime_dir = _runtime_browser_dir(instance_root)
    pid_file = runtime_dir / "cockpit-upstream.pid"
    pgid_file = runtime_dir / "cockpit-upstream.pgid"
    marker_pid = _read_numeric_file(pid_file)
    marker_pgid = _read_numeric_file(pgid_file)
    if not _terminate_pgid(marker_pgid):
        _terminate_pid(marker_pid)
    pid_file.unlink(missing_ok=True)
    pgid_file.unlink(missing_ok=True)


def _clear_page_idle_state(instance_root: Path) -> None:
    runtime_dir = _runtime_browser_dir(instance_root)
    (runtime_dir / "page_idle.json").unlink(missing_ok=True)
    (runtime_dir / "page_idle.lock").unlink(missing_ok=True)


def stop(*, instance_root: Path | str, actor_id: str) -> dict[str, object]:
    root = Path(instance_root)
    try:
        _read_instance_payload(root, actor_id)
        _stop_upstream(root)
        marker = _pid_file(root)
        _terminate_pid(_read_numeric_file(marker))
        marker.unlink(missing_ok=True)
        _clear_page_idle_state(root)
        changed = _clear_browser_port(root, actor_id)
        return _success(
            handled=True,
            state_changed=changed,
            durability="runtime",
            message=f"Browser cockpit stopped: {actor_id}",
        )
    except Exception as exc:
        return _failure(exc)


def release(*, instance_root: Path | str, actor_id: str, reason: str | None = None) -> dict[str, object]:
    del reason
    root = Path(instance_root)
    try:
        port = _recorded_port(root, actor_id)
        if port is None:
            return _success(
                handled=False,
                skip_reason="browser_port_missing",
                ownership="inactive",
                state_changed=False,
                durability="none",
                message=f"Browser cockpit release skipped: no browser port recorded for {actor_id}",
            )
        ownership = ownership_state(root, actor_id)
        if ownership in {"owned", "inactive"}:
            stopped = stop(instance_root=root, actor_id=actor_id)
            if stopped.get("ok") is not True:
                return stopped
            return _success(
                handled=True,
                skip_reason=None,
                ownership=ownership,
                state_changed=True,
                durability="runtime",
                message=f"Browser cockpit released: {actor_id}",
            )
        changed = _clear_browser_port(root, actor_id)
        return _success(
            handled=True,
            skip_reason=None,
            ownership=ownership,
            state_changed=changed,
            durability="runtime",
            message=f"Browser cockpit release skipped: {ownership} endpoint on {port}; cleared stale browser_port for {actor_id}",
        )
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
