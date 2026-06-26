#!/usr/bin/env python3
"""Browser-owned daemon handler for expired browser page TTL schedules."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPTS_ENV = SCRIPTS / "env"
for candidate in (HELPER_DIR, SCRIPTS, SCRIPTS_ENV):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import daemon_core  # noqa: E402
import cdp_browser_lifecycle as browser_lifecycle  # noqa: E402


BROWSER_PAGE_EXPIRED_EVENT_TYPE = "browser.page.expired"


def _context_actor_address(context: Any) -> dict[str, str]:
    value = getattr(context, "actor_address", None)
    if isinstance(value, dict):
        role_id = value.get("role_id")
        actor_id = value.get("actor_id")
        if isinstance(role_id, str) and role_id and isinstance(actor_id, str) and actor_id:
            return {"role_id": role_id, "actor_id": actor_id}
    return daemon_core.actor_address_for_context(context).to_payload()


def _payload(trigger: Any) -> dict[str, Any]:
    payload = getattr(trigger, "payload", None)
    if not isinstance(payload, dict):
        raise ValueError("browser page expiry trigger payload must be an object")
    target_id = payload.get("target_id")
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("target_id is required")
    return {
        "target_id": target_id.strip(),
    }


def _trigger_due_at(trigger: Any) -> str | None:
    source_context = getattr(trigger, "source_context", None)
    if not isinstance(source_context, dict):
        return None
    due_at = source_context.get("due_at")
    if isinstance(due_at, str) and due_at.strip():
        return due_at.strip()
    return None


def _browser_endpoint(context: Any) -> str | None:
    instance_payload = getattr(context, "instance_payload", None)
    if not isinstance(instance_payload, dict):
        return None
    port = instance_payload.get("browser_port")
    if isinstance(port, bool) or not isinstance(port, int) or port < 1 or port > 65535:
        return None
    return f"http://127.0.0.1:{port}"


def _instance_root(context: Any) -> Path | None:
    value = getattr(context, "instance_root", None)
    if value is None:
        return None
    return Path(value)


def _parent_turn_is_running(runtime: Any) -> bool:
    activity = runtime.parent_activity() if callable(getattr(runtime, "parent_activity", None)) else {}
    return isinstance(activity, dict) and activity.get("status") == "running"


def _is_stale_browser_error(message: str) -> bool:
    return (
        "failed to read Chrome DevTools /json/list" in message
        or "Chrome DevTools returned HTTP" in message
        or "connection refused" in message
        or "timed out" in message
    )


class BrowserPageExpiredHandler:
    name = "browser_page_expired"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == BROWSER_PAGE_EXPIRED_EVENT_TYPE

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> daemon_core.HandlerResult:
        del state
        if getattr(trigger, "type", None) != BROWSER_PAGE_EXPIRED_EVENT_TYPE:
            return daemon_core.HandlerResult.ignored()
        try:
            local_actor = _context_actor_address(context)
            target_actor = getattr(trigger, "target_actor_address", None)
            if target_actor != local_actor:
                raise PermissionError("wrong target actor for browser page expiry trigger")
            payload = _payload(trigger)
            return self._handle_expiry(context, runtime, payload, due_at=_trigger_due_at(trigger))
        except Exception as exc:
            return daemon_core.HandlerResult.failed(str(exc))

    def _handle_expiry(
        self,
        context: Any,
        runtime: Any,
        payload: dict[str, Any],
        *,
        due_at: str | None = None,
    ) -> daemon_core.HandlerResult:
        root = _instance_root(context)
        target_id = payload["target_id"]
        if root is not None:
            current_target_id = browser_lifecycle.current_target_id(root)
            if current_target_id == target_id and _parent_turn_is_running(runtime):
                browser_lifecycle.refresh_current_page_idle(instance_root=root, target_id=target_id)
                return daemon_core.HandlerResult.handled()
            if browser_lifecycle.target_idle_expiry_after_due_at(
                instance_root=root,
                target_id=target_id,
                due_at=due_at,
            ):
                return daemon_core.HandlerResult.handled()
        return self._auto_close(context, payload)

    def _auto_close(self, context: Any, payload: dict[str, Any]) -> daemon_core.HandlerResult:
        browser_endpoint = _browser_endpoint(context)
        if browser_endpoint is None:
            return daemon_core.HandlerResult.handled()
        try:
            close_result = browser_lifecycle.close_page_target(browser_endpoint, payload["target_id"])
        except browser_lifecycle.BrowserLifecycleError as exc:
            message = str(exc)
            if _is_stale_browser_error(message):
                return daemon_core.HandlerResult.handled()
            return daemon_core.HandlerResult.failed(message)
        if close_result.get("status") in {"closed", "already_gone"}:
            root = _instance_root(context)
            if root is not None:
                browser_lifecycle.forget_page_idle_target(instance_root=root, target_id=payload["target_id"])
        return daemon_core.HandlerResult.handled()


if __name__ == "__main__":
    raise SystemExit("browser_page_expired_handler is not a standalone command")
