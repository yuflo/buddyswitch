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
    target_url = payload.get("target_url")
    ttl_seconds = payload.get("ttl_seconds")
    expiry_policy = payload.get("expiry_policy")
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("target_id is required")
    if not isinstance(target_url, str) or not target_url.strip():
        raise ValueError("target_url is required")
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be a positive integer")
    if expiry_policy not in {"auto_close", "notify"}:
        raise ValueError("expiry_policy must be auto_close or notify")
    return {
        "target_id": target_id.strip(),
        "target_url": target_url.strip(),
        "ttl_seconds": ttl_seconds,
        "expiry_policy": expiry_policy,
    }


def _browser_endpoint(context: Any) -> str | None:
    instance_payload = getattr(context, "instance_payload", None)
    if not isinstance(instance_payload, dict):
        return None
    port = instance_payload.get("browser_port")
    if isinstance(port, bool) or not isinstance(port, int) or port < 1 or port > 65535:
        return None
    return f"http://127.0.0.1:{port}"


def _origin_id(trigger: Any) -> str | None:
    value = getattr(trigger, "origin_id", None)
    return value if isinstance(value, str) and value else None


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
            if payload["expiry_policy"] == "notify":
                return self._notify(runtime, trigger, payload)
            return self._auto_close(context, payload)
        except Exception as exc:
            return daemon_core.HandlerResult.failed(str(exc))

    def _notify(self, runtime: Any, trigger: Any, payload: dict[str, Any]) -> daemon_core.HandlerResult:
        prompt = (
            "Browser page TTL expired.\n"
            f"Target URL: {payload['target_url']}\n"
            f"TTL: {payload['ttl_seconds']}s."
        )
        runtime.submit_parent_prompt(
            prompt,
            handler_name=self.name,
            origin_id=_origin_id(trigger),
            interrupt_policy="none",
        )
        return daemon_core.HandlerResult.handled()

    def _auto_close(self, context: Any, payload: dict[str, Any]) -> daemon_core.HandlerResult:
        browser_endpoint = _browser_endpoint(context)
        if browser_endpoint is None:
            return daemon_core.HandlerResult.handled()
        try:
            browser_lifecycle.close_page_target(browser_endpoint, payload["target_id"])
        except browser_lifecycle.BrowserLifecycleError as exc:
            message = str(exc)
            if _is_stale_browser_error(message):
                return daemon_core.HandlerResult.handled()
            return daemon_core.HandlerResult.failed(message)
        return daemon_core.HandlerResult.handled()


if __name__ == "__main__":
    raise SystemExit("browser_page_expired_handler is not a standalone command")
