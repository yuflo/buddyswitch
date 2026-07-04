#!/usr/bin/env python3
"""Shared Chrome DevTools browser lifecycle helpers."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


SCRIPTS_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPTS_DIR.parent
for candidate in (SCRIPTS_DIR, SCRIPTS_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from cdp_background_page import (  # noqa: E402
    CdpTargetError,
    _browser_version,
    _connect_websocket,
    _read_server_frame,
    _send_client_frame,
)
from env.tool_runtime import daemon_client  # noqa: E402


BROWSER_PAGE_IDLE_SECONDS = 40
BROWSER_PAGE_EXPIRED_TRIGGER = "browser.page.expired"
BROWSER_COCKPIT_RELEASE_DELAY_SECONDS = 10
BROWSER_COCKPIT_RELEASE_TRIGGER = "browser.cockpit.release"
BROWSER_COCKPIT_RELEASE_SCHEDULE_KEY = "browser.cockpit.release"


class BrowserLifecycleError(RuntimeError):
    pass


def _target_id(target: dict[str, Any]) -> str | None:
    for key in ("id", "targetId"):
        value = target.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _page_targets(targets: list[Any]) -> list[dict[str, Any]]:
    return [target for target in targets if isinstance(target, dict) and target.get("type") == "page"]


def read_page_targets(browser_url: str, timeout_seconds: float = 3.0) -> list[dict[str, Any]]:
    list_url = f"{browser_url.rstrip('/')}/json/list"
    request = Request(list_url, method="GET")
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise BrowserLifecycleError(f"Chrome DevTools returned HTTP {exc.code} for /json/list") from exc
    except (URLError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise BrowserLifecycleError(f"failed to read Chrome DevTools /json/list: {exc}") from exc
    if not isinstance(payload, list):
        raise BrowserLifecycleError("Chrome DevTools /json/list did not return a list")
    return _page_targets(payload)


def new_page_target_id(before_targets: list[Any], after_targets: list[Any]) -> str | None:
    before_ids = {
        target_id
        for target in _page_targets(before_targets)
        for target_id in [_target_id(target)]
        if target_id is not None
    }
    new_ids = [
        target_id
        for target in _page_targets(after_targets)
        for target_id in [_target_id(target)]
        if target_id is not None and target_id not in before_ids
    ]
    if len(new_ids) != 1:
        return None
    return new_ids[0]


def _send_browser_command(
    browser_url: str,
    method: str,
    params: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        version = _browser_version(browser_url, timeout_seconds)
        websocket_url = version.get("webSocketDebuggerUrl")
        if not isinstance(websocket_url, str) or not websocket_url.strip():
            raise BrowserLifecycleError("Chrome DevTools /json/version is missing webSocketDebuggerUrl")
        sock, buffer = _connect_websocket(websocket_url.strip(), timeout_seconds)
    except (CdpTargetError, OSError) as exc:
        raise BrowserLifecycleError(str(exc)) from exc
    try:
        request = {"id": 1, "method": method, "params": dict(params)}
        _send_client_frame(sock, json.dumps(request, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
        while True:
            opcode, payload = _read_server_frame(sock, timeout_seconds, buffer)
            if opcode == 0x8:
                raise BrowserLifecycleError("browser websocket closed before command response")
            if opcode == 0x9:
                _send_client_frame(sock, payload)
                continue
            if opcode != 0x1:
                continue
            try:
                message = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BrowserLifecycleError("browser websocket returned invalid JSON") from exc
            if not isinstance(message, dict) or message.get("id") != 1:
                continue
            if "error" in message:
                error = message.get("error")
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    raise BrowserLifecycleError(error["message"])
                raise BrowserLifecycleError(json.dumps(error, ensure_ascii=True))
            result = message.get("result")
            if not isinstance(result, dict):
                raise BrowserLifecycleError("browser command response missing result object")
            return result
    except CdpTargetError as exc:
        raise BrowserLifecycleError(str(exc)) from exc
    finally:
        try:
            sock.close()
        except OSError:
            pass


def create_background_page_target(browser_url: str, target_url: str, timeout_seconds: float = 5.0) -> str:
    if not isinstance(target_url, str) or not target_url.strip():
        raise BrowserLifecycleError("target_url must be a non-empty string")
    result = _send_browser_command(
        browser_url,
        "Target.createTarget",
        {"url": target_url.strip(), "background": True},
        timeout_seconds,
    )
    target_id = result.get("targetId")
    if not isinstance(target_id, str) or not target_id.strip():
        raise BrowserLifecycleError("Target.createTarget response missing targetId")
    return target_id.strip()


def close_page_target(browser_url: str, target_id: str, timeout_seconds: float = 3.0) -> dict[str, str]:
    if not isinstance(target_id, str) or not target_id.strip():
        raise BrowserLifecycleError("target_id must be a non-empty string")
    normalized_target_id = target_id.strip()
    targets = read_page_targets(browser_url, timeout_seconds=timeout_seconds)
    if normalized_target_id not in {_target_id(target) for target in targets}:
        return {"status": "already_gone", "target_id": normalized_target_id}
    result = _send_browser_command(
        browser_url,
        "Target.closeTarget",
        {"targetId": normalized_target_id},
        timeout_seconds,
    )
    if result.get("success") is not True:
        raise BrowserLifecycleError(f"Chrome DevTools did not close target {normalized_target_id}")
    return {"status": "closed", "target_id": normalized_target_id}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise BrowserLifecycleError("timestamp must be a non-empty string")
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise BrowserLifecycleError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def page_idle_state_file(instance_root: Path) -> Path:
    return Path(instance_root) / "runtime" / "browser" / "page_idle.json"


def page_idle_state_lock_file(instance_root: Path) -> Path:
    return Path(instance_root) / "runtime" / "browser" / "page_idle.lock"


@contextmanager
def _page_idle_state_lock(instance_root: Path) -> Any:
    path = page_idle_state_lock_file(instance_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_page_idle_state(instance_root: Path) -> dict[str, Any]:
    path = page_idle_state_file(instance_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserLifecycleError(f"failed to read browser page idle state: {exc}") from exc
    if not isinstance(payload, dict):
        payload = {}
    targets = payload.get("targets")
    if not isinstance(targets, dict):
        targets = {}
    page_map = payload.get("page_id_to_target_id")
    if not isinstance(page_map, dict):
        page_map = {}
    payload["targets"] = {
        key: dict(value)
        for key, value in targets.items()
        if isinstance(key, str) and key and isinstance(value, dict)
    }
    payload["page_id_to_target_id"] = {
        str(key): value
        for key, value in page_map.items()
        if isinstance(value, str) and value.strip()
    }
    current_target = payload.get("current_target_id")
    if not isinstance(current_target, str) or not current_target.strip():
        payload.pop("current_target_id", None)
    else:
        payload["current_target_id"] = current_target.strip()
    current_updated = payload.get("current_page_updated_at")
    if not isinstance(current_updated, str) or not current_updated.strip():
        payload.pop("current_page_updated_at", None)
    return payload


def _write_page_idle_state(instance_root: Path, payload: dict[str, Any]) -> None:
    path = page_idle_state_file(instance_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{id(payload)}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _normalize_target_id(target_id: str) -> str:
    if not isinstance(target_id, str) or not target_id.strip():
        raise BrowserLifecycleError("target_id must be a non-empty string")
    return target_id.strip()


def _normalize_page_id(page_id: object) -> str | None:
    if page_id is None:
        return None
    if isinstance(page_id, bool):
        raise BrowserLifecycleError("page_id must be a string or integer when provided")
    if isinstance(page_id, int):
        return str(page_id)
    if isinstance(page_id, str) and page_id.strip():
        return page_id.strip()
    raise BrowserLifecycleError("page_id must be a string or integer when provided")


def _apply_target_metadata(
    state: dict[str, Any],
    *,
    target_id: str,
    timestamp: str,
    target_url: str | None = None,
    page_id: object | None = None,
) -> dict[str, Any]:
    normalized_page_id = _normalize_page_id(page_id)
    targets = state.setdefault("targets", {})
    if not isinstance(targets, dict):
        targets = {}
        state["targets"] = targets
    target_state = dict(targets.get(target_id)) if isinstance(targets.get(target_id), dict) else {}
    target_state["target_id"] = target_id
    target_state["last_used_at"] = timestamp
    if isinstance(target_url, str) and target_url.strip():
        target_state["target_url"] = target_url.strip()
    if normalized_page_id is not None:
        target_state["page_id"] = normalized_page_id
        page_map = state.setdefault("page_id_to_target_id", {})
        if not isinstance(page_map, dict):
            page_map = {}
            state["page_id_to_target_id"] = page_map
        page_map[normalized_page_id] = target_id
    targets[target_id] = target_state
    return state


def mark_current_page(
    *,
    instance_root: Path,
    target_id: str,
    target_url: str | None = None,
    page_id: object | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized_target_id = _normalize_target_id(target_id)
    timestamp = _format_utc(now or _utc_now())
    with _page_idle_state_lock(Path(instance_root)):
        state = _read_page_idle_state(instance_root)
        _apply_target_metadata(
            state,
            target_id=normalized_target_id,
            timestamp=timestamp,
            target_url=target_url,
            page_id=page_id,
        )
        state["current_target_id"] = normalized_target_id
        state["current_page_updated_at"] = timestamp
        _write_page_idle_state(instance_root, state)
        return dict(state)


def current_target_id(instance_root: Path) -> str | None:
    state = _read_page_idle_state(instance_root)
    target_id = state.get("current_target_id")
    if isinstance(target_id, str) and target_id.strip():
        return target_id.strip()
    return None


def target_idle_expiry_after_due_at(
    *,
    instance_root: Path,
    target_id: str,
    due_at: str | None,
    idle_seconds: int = BROWSER_PAGE_IDLE_SECONDS,
) -> bool:
    normalized_target_id = _normalize_target_id(target_id)
    if isinstance(idle_seconds, bool) or not isinstance(idle_seconds, int) or idle_seconds <= 0:
        raise BrowserLifecycleError("idle_seconds must be a positive integer")
    if not isinstance(due_at, str) or not due_at.strip():
        return False
    try:
        due_at_dt = _parse_utc(due_at)
    except BrowserLifecycleError:
        return False
    state = _read_page_idle_state(Path(instance_root))
    targets = state.get("targets")
    if not isinstance(targets, dict):
        return False
    target_state = targets.get(normalized_target_id)
    if not isinstance(target_state, dict):
        return False
    last_used_at = target_state.get("last_used_at")
    if not isinstance(last_used_at, str) or not last_used_at.strip():
        return False
    try:
        last_used_dt = _parse_utc(last_used_at)
    except BrowserLifecycleError:
        return False
    return last_used_dt + timedelta(seconds=idle_seconds) > due_at_dt


def target_id_for_page_id(instance_root: Path, page_id: object) -> str | None:
    normalized_page_id = _normalize_page_id(page_id)
    if normalized_page_id is None:
        return None
    state = _read_page_idle_state(instance_root)
    page_map = state.get("page_id_to_target_id")
    if not isinstance(page_map, dict):
        return None
    target_id = page_map.get(normalized_page_id)
    if isinstance(target_id, str) and target_id.strip():
        return target_id.strip()
    return None


def refresh_page_idle(
    *,
    instance_root: Path,
    target_id: str,
    target_url: str | None = None,
    page_id: object | None = None,
    idle_seconds: int = BROWSER_PAGE_IDLE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized_target_id = _normalize_target_id(target_id)
    if isinstance(idle_seconds, bool) or not isinstance(idle_seconds, int) or idle_seconds <= 0:
        raise BrowserLifecycleError("idle_seconds must be a positive integer")
    timestamp_value = now or _utc_now()
    payload = {
        "target_id": normalized_target_id,
    }
    daemon_client.schedule_trigger(
        instance_root=Path(instance_root),
        delay_seconds=idle_seconds,
        trigger_type=BROWSER_PAGE_EXPIRED_TRIGGER,
        payload=payload,
        source_context={"owner": "browser"},
        schedule_key=f"browser.page.idle:{normalized_target_id}",
    )
    with _page_idle_state_lock(Path(instance_root)):
        state = _read_page_idle_state(Path(instance_root))
        _apply_target_metadata(
            state,
            target_id=normalized_target_id,
            timestamp=_format_utc(timestamp_value),
            target_url=target_url,
            page_id=page_id,
        )
        _write_page_idle_state(Path(instance_root), state)
    return {
        "idle_refreshed": True,
        "idle_seconds": idle_seconds,
        "idle_expires_at": _format_utc(timestamp_value + timedelta(seconds=idle_seconds)),
    }


def refresh_current_page_idle(
    *,
    instance_root: Path,
    target_id: str,
    target_url: str | None = None,
    page_id: object | None = None,
    idle_seconds: int = BROWSER_PAGE_IDLE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp_value = now or _utc_now()
    result = refresh_page_idle(
        instance_root=instance_root,
        target_id=target_id,
        target_url=target_url,
        page_id=page_id,
        idle_seconds=idle_seconds,
        now=timestamp_value,
    )
    mark_current_page(
        instance_root=instance_root,
        target_id=target_id,
        target_url=target_url,
        page_id=page_id,
        now=timestamp_value,
    )
    return result


def schedule_browser_cockpit_release(
    *,
    instance_root: Path,
    reason: str = "page_idle_empty",
    delay_seconds: int = BROWSER_COCKPIT_RELEASE_DELAY_SECONDS,
) -> dict[str, Any]:
    if not isinstance(reason, str) or not reason.strip():
        raise BrowserLifecycleError("release reason must be a non-empty string")
    if isinstance(delay_seconds, bool) or not isinstance(delay_seconds, int) or delay_seconds < 0:
        raise BrowserLifecycleError("release delay_seconds must be a non-negative integer")
    return daemon_client.schedule_trigger(
        instance_root=Path(instance_root),
        delay_seconds=delay_seconds,
        trigger_type=BROWSER_COCKPIT_RELEASE_TRIGGER,
        payload={"reason": reason.strip()},
        source_context={"owner": "browser"},
        schedule_key=BROWSER_COCKPIT_RELEASE_SCHEDULE_KEY,
    )


def forget_page_idle_target(*, instance_root: Path, target_id: str) -> dict[str, Any]:
    normalized_target_id = _normalize_target_id(target_id)
    with _page_idle_state_lock(Path(instance_root)):
        state = _read_page_idle_state(Path(instance_root))
        targets = state.setdefault("targets", {})
        if not isinstance(targets, dict):
            targets = {}
            state["targets"] = targets
        targets.pop(normalized_target_id, None)
        page_map = state.setdefault("page_id_to_target_id", {})
        if not isinstance(page_map, dict):
            page_map = {}
            state["page_id_to_target_id"] = page_map
        stale_page_ids = [page_id for page_id, mapped_target in page_map.items() if mapped_target == normalized_target_id]
        for page_id in stale_page_ids:
            page_map.pop(page_id, None)
        if state.get("current_target_id") == normalized_target_id:
            state.pop("current_target_id", None)
            state.pop("current_page_updated_at", None)
        _write_page_idle_state(Path(instance_root), state)
        return dict(state)
