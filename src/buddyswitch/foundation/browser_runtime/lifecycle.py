"""Browser-owned Chrome target lifecycle state and daemon schedules."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import sys
from pathlib import Path
from typing import Any


from buddyswitch.foundation.browser_runtime import config  # noqa: E402
from buddyswitch.foundation.daemon import client as daemon_client  # noqa: E402


BROWSER_PAGE_EXPIRED_TRIGGER = "browser.page.expired"
BROWSER_COCKPIT_RELEASE_TRIGGER = "browser.cockpit.release"
BROWSER_COCKPIT_RELEASE_SCHEDULE_KEY = "browser.cockpit.release"
BROWSER_FAILED_OPEN_PAGE_CLEANUP_TRIGGER = "browser.failed_open_page.cleanup"
BROWSER_FAILED_OPEN_PAGE_CLEANUP_DELAY_SECONDS = 5
BROWSER_FAILED_OPEN_PAGE_CLEANUP_MAX_ATTEMPTS = 3


class BrowserLifecycleError(RuntimeError):
    pass


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


def _normalize_tab_target_id(tab_target_id: object) -> str:
    if not isinstance(tab_target_id, str) or not tab_target_id.strip():
        raise BrowserLifecycleError("tab_target_id must be a non-empty string")
    return tab_target_id.strip()


def _normalize_positive_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BrowserLifecycleError(f"{name} must be a positive integer")
    return value


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


def read_page_idle_state(instance_root: Path) -> dict[str, Any]:
    path = page_idle_state_file(instance_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserLifecycleError(f"failed to read browser target idle state: {exc}") from exc
    if not isinstance(payload, dict):
        payload = {}
    raw_targets = payload.get("targets")
    raw_targets = raw_targets if isinstance(raw_targets, dict) else {}
    targets: dict[str, dict[str, Any]] = {}
    for raw_key, raw_value in raw_targets.items():
        if not isinstance(raw_key, str) or not raw_key.strip() or not isinstance(raw_value, dict):
            continue
        target_id = raw_key.strip()
        record = dict(raw_value)
        record["tab_target_id"] = target_id
        targets[target_id] = record
    state: dict[str, Any] = {"targets": targets}
    active = payload.get("active_tab_target_id")
    if isinstance(active, str) and active.strip() in targets:
        state["active_tab_target_id"] = active.strip()
    return state


def _write_page_idle_state(instance_root: Path, payload: dict[str, Any]) -> None:
    path = page_idle_state_file(instance_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{id(payload)}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def active_tab_target_id(instance_root: Path) -> str | None:
    value = read_page_idle_state(instance_root).get("active_tab_target_id")
    return value if isinstance(value, str) and value else None


def refresh_tab_idle(
    *,
    instance_root: Path,
    tab_target_id: object,
    target_url: str | None = None,
    title: str | None = None,
    active: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(instance_root)
    normalized_target_id = _normalize_tab_target_id(tab_target_id)
    ttl_config = config.load_browser_ttl_config(instance_root=root)
    idle_seconds = ttl_config.page_idle_seconds
    timestamp_value = now or _utc_now()
    daemon_client.schedule_trigger(
        instance_root=root,
        delay_seconds=idle_seconds,
        trigger_type=BROWSER_PAGE_EXPIRED_TRIGGER,
        payload={"tab_target_id": normalized_target_id, "idle_seconds": idle_seconds},
        source_context={"owner": "browser"},
        schedule_key=f"browser.page.idle:{normalized_target_id}",
    )
    with _page_idle_state_lock(root):
        state = read_page_idle_state(root)
        targets = state["targets"]
        record = dict(targets.get(normalized_target_id, {}))
        record.update(
            {
                "tab_target_id": normalized_target_id,
                "last_used_at": _format_utc(timestamp_value),
                "idle_seconds": idle_seconds,
            }
        )
        if isinstance(target_url, str) and target_url.strip():
            record["url"] = target_url.strip()
        if isinstance(title, str) and title.strip():
            record["title"] = title.strip()
        targets[normalized_target_id] = record
        if active:
            state["active_tab_target_id"] = normalized_target_id
        _write_page_idle_state(root, state)
    return {
        "idle_refreshed": True,
        "idle_seconds": idle_seconds,
        "idle_expires_at": _format_utc(timestamp_value + timedelta(seconds=idle_seconds)),
        "tab_target_id": normalized_target_id,
    }


def refresh_active_tab_idle(
    *,
    instance_root: Path,
    tab_target_id: object,
    target_url: str | None = None,
    title: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    return refresh_tab_idle(
        instance_root=instance_root,
        tab_target_id=tab_target_id,
        target_url=target_url,
        title=title,
        active=True,
        now=now,
    )


def tab_idle_expiry_after_due_at(
    *,
    instance_root: Path,
    tab_target_id: object,
    due_at: str | None,
    idle_seconds: object,
) -> bool:
    normalized_target_id = _normalize_tab_target_id(tab_target_id)
    effective_idle_seconds = _normalize_positive_integer(idle_seconds, "idle_seconds")
    if not isinstance(due_at, str) or not due_at.strip():
        return False
    try:
        due_at_value = _parse_utc(due_at)
    except BrowserLifecycleError:
        return False
    record = read_page_idle_state(instance_root)["targets"].get(normalized_target_id)
    if not isinstance(record, dict):
        return False
    last_used_at = record.get("last_used_at")
    if not isinstance(last_used_at, str):
        return False
    try:
        last_used_value = _parse_utc(last_used_at)
    except BrowserLifecycleError:
        return False
    return last_used_value + timedelta(seconds=effective_idle_seconds) > due_at_value


def schedule_browser_cockpit_release(
    *,
    instance_root: Path,
    reason: str = "page_idle_empty",
) -> dict[str, Any]:
    if not isinstance(reason, str) or not reason.strip():
        raise BrowserLifecycleError("release reason must be a non-empty string")
    root = Path(instance_root)
    delay_seconds = config.load_browser_ttl_config(instance_root=root).release_delay_seconds
    return daemon_client.schedule_trigger(
        instance_root=root,
        delay_seconds=delay_seconds,
        trigger_type=BROWSER_COCKPIT_RELEASE_TRIGGER,
        payload={"reason": reason.strip()},
        source_context={"owner": "browser"},
        schedule_key=BROWSER_COCKPIT_RELEASE_SCHEDULE_KEY,
    )


def schedule_failed_open_page_cleanup(
    *,
    instance_root: Path,
    target_id: object,
    url: str | None = None,
    attempts: int = 1,
    first_seen_at: str | None = None,
    delay_seconds: int = BROWSER_FAILED_OPEN_PAGE_CLEANUP_DELAY_SECONDS,
) -> dict[str, Any]:
    normalized_target_id = _normalize_tab_target_id(target_id)
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise BrowserLifecycleError("attempts must be a positive integer")
    if isinstance(delay_seconds, bool) or not isinstance(delay_seconds, int) or delay_seconds < 0:
        raise BrowserLifecycleError("cleanup delay_seconds must be a non-negative integer")
    seen_at = first_seen_at.strip() if isinstance(first_seen_at, str) and first_seen_at.strip() else _format_utc(_utc_now())
    payload: dict[str, Any] = {
        "target_id": normalized_target_id,
        "attempts": attempts,
        "first_seen_at": seen_at,
        "reason": "failed_open_page",
    }
    if isinstance(url, str) and url.strip():
        payload["url"] = url.strip()
    return daemon_client.schedule_trigger(
        instance_root=Path(instance_root),
        delay_seconds=delay_seconds,
        trigger_type=BROWSER_FAILED_OPEN_PAGE_CLEANUP_TRIGGER,
        payload=payload,
        source_context={"owner": "browser"},
        schedule_key=f"browser.failed_open_page.cleanup:{normalized_target_id}",
    )


def forget_tab_idle_target(*, instance_root: Path, tab_target_id: object) -> dict[str, Any]:
    root = Path(instance_root)
    normalized_target_id = _normalize_tab_target_id(tab_target_id)
    with _page_idle_state_lock(root):
        state = read_page_idle_state(root)
        state["targets"].pop(normalized_target_id, None)
        if state.get("active_tab_target_id") == normalized_target_id:
            state.pop("active_tab_target_id", None)
        _write_page_idle_state(root, state)
        return dict(state)
