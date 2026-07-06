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
    pages = payload.get("pages")
    if not isinstance(pages, dict):
        pages = {}
    normalized_pages: dict[str, dict[str, Any]] = {}
    for key, value in pages.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(value, dict):
            continue
        page_id = key.strip()
        page_state = dict(value)
        page_state["page_id"] = page_id
        normalized_pages[page_id] = page_state

    state: dict[str, Any] = {"pages": normalized_pages}
    current_page = payload.get("current_page_id")
    if isinstance(current_page, str) and current_page.strip():
        state["current_page_id"] = current_page.strip()
    selected_page = payload.get("selected_page_id")
    if isinstance(selected_page, str) and selected_page.strip():
        state["selected_page_id"] = selected_page.strip()
    current_updated = payload.get("current_page_updated_at")
    if isinstance(current_updated, str) and current_updated.strip():
        state["current_page_updated_at"] = current_updated.strip()
    return state


def _write_page_idle_state(instance_root: Path, payload: dict[str, Any]) -> None:
    path = page_idle_state_file(instance_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{id(payload)}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


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


def _apply_page_metadata(
    state: dict[str, Any],
    *,
    page_id: str,
    timestamp: str,
    target_url: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    pages = state.setdefault("pages", {})
    if not isinstance(pages, dict):
        pages = {}
        state["pages"] = pages
    page_state = dict(pages.get(page_id)) if isinstance(pages.get(page_id), dict) else {}
    page_state["page_id"] = page_id
    page_state["last_used_at"] = timestamp
    if isinstance(target_url, str) and target_url.strip():
        page_state["url"] = target_url.strip()
    if isinstance(title, str) and title.strip():
        page_state["title"] = title.strip()
    pages[page_id] = page_state
    return state


def mark_current_page(
    *,
    instance_root: Path,
    page_id: object,
    target_url: str | None = None,
    title: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized_page_id = _normalize_page_id(page_id)
    if normalized_page_id is None:
        raise BrowserLifecycleError("page_id must be provided")
    timestamp = _format_utc(now or _utc_now())
    with _page_idle_state_lock(Path(instance_root)):
        state = _read_page_idle_state(instance_root)
        _apply_page_metadata(
            state,
            page_id=normalized_page_id,
            timestamp=timestamp,
            target_url=target_url,
            title=title,
        )
        state["current_page_id"] = normalized_page_id
        state["selected_page_id"] = normalized_page_id
        state["current_page_updated_at"] = timestamp
        _write_page_idle_state(instance_root, state)
        return dict(state)


def current_page_id(instance_root: Path) -> str | None:
    state = _read_page_idle_state(instance_root)
    page_id = state.get("current_page_id")
    if isinstance(page_id, str) and page_id.strip():
        return page_id.strip()
    return None


def selected_page_id(instance_root: Path) -> str | None:
    state = _read_page_idle_state(instance_root)
    page_id = state.get("selected_page_id")
    if isinstance(page_id, str) and page_id.strip():
        return page_id.strip()
    return current_page_id(instance_root)


def page_idle_expiry_after_due_at(
    *,
    instance_root: Path,
    page_id: object,
    due_at: str | None,
    idle_seconds: int = BROWSER_PAGE_IDLE_SECONDS,
) -> bool:
    normalized_page_id = _normalize_page_id(page_id)
    if normalized_page_id is None:
        return False
    if isinstance(idle_seconds, bool) or not isinstance(idle_seconds, int) or idle_seconds <= 0:
        raise BrowserLifecycleError("idle_seconds must be a positive integer")
    if not isinstance(due_at, str) or not due_at.strip():
        return False
    try:
        due_at_dt = _parse_utc(due_at)
    except BrowserLifecycleError:
            return False
    state = _read_page_idle_state(Path(instance_root))
    pages = state.get("pages")
    if not isinstance(pages, dict):
        return False
    page_state = pages.get(normalized_page_id)
    if not isinstance(page_state, dict):
        return False
    last_used_at = page_state.get("last_used_at")
    if not isinstance(last_used_at, str) or not last_used_at.strip():
        return False
    try:
        last_used_dt = _parse_utc(last_used_at)
    except BrowserLifecycleError:
        return False
    return last_used_dt + timedelta(seconds=idle_seconds) > due_at_dt


def refresh_page_idle(
    *,
    instance_root: Path,
    page_id: object,
    target_url: str | None = None,
    title: str | None = None,
    idle_seconds: int = BROWSER_PAGE_IDLE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized_page_id = _normalize_page_id(page_id)
    if normalized_page_id is None:
        raise BrowserLifecycleError("page_id must be provided")
    if isinstance(idle_seconds, bool) or not isinstance(idle_seconds, int) or idle_seconds <= 0:
        raise BrowserLifecycleError("idle_seconds must be a positive integer")
    timestamp_value = now or _utc_now()
    payload = {
        "page_id": normalized_page_id,
    }
    daemon_client.schedule_trigger(
        instance_root=Path(instance_root),
        delay_seconds=idle_seconds,
        trigger_type=BROWSER_PAGE_EXPIRED_TRIGGER,
        payload=payload,
        source_context={"owner": "browser"},
        schedule_key=f"browser.page.idle:{normalized_page_id}",
    )
    with _page_idle_state_lock(Path(instance_root)):
        state = _read_page_idle_state(Path(instance_root))
        _apply_page_metadata(
            state,
            page_id=normalized_page_id,
            timestamp=_format_utc(timestamp_value),
            target_url=target_url,
            title=title,
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
    page_id: object,
    target_url: str | None = None,
    title: str | None = None,
    idle_seconds: int = BROWSER_PAGE_IDLE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp_value = now or _utc_now()
    result = refresh_page_idle(
        instance_root=instance_root,
        page_id=page_id,
        target_url=target_url,
        title=title,
        idle_seconds=idle_seconds,
        now=timestamp_value,
    )
    mark_current_page(
        instance_root=instance_root,
        page_id=page_id,
        target_url=target_url,
        title=title,
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


def forget_page_idle_page(*, instance_root: Path, page_id: object) -> dict[str, Any]:
    normalized_page_id = _normalize_page_id(page_id)
    if normalized_page_id is None:
        raise BrowserLifecycleError("page_id must be provided")
    with _page_idle_state_lock(Path(instance_root)):
        state = _read_page_idle_state(Path(instance_root))
        pages = state.setdefault("pages", {})
        if not isinstance(pages, dict):
            pages = {}
            state["pages"] = pages
        pages.pop(normalized_page_id, None)
        if state.get("current_page_id") == normalized_page_id:
            state.pop("current_page_id", None)
            state.pop("current_page_updated_at", None)
        if state.get("selected_page_id") == normalized_page_id:
            state.pop("selected_page_id", None)
        _write_page_idle_state(Path(instance_root), state)
        return dict(state)

