"""Browser-owned daemon handlers for exact Chrome target cleanup."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any



from buddyswitch.launcher import daemon_contracts  # noqa: E402
from buddyswitch.foundation.browser_runtime import lifecycle as browser_lifecycle  # noqa: E402
from buddyswitch.foundation.browser_runtime import target as cdp_target  # noqa: E402


BROWSER_PAGE_EXPIRED_EVENT_TYPE = "browser.page.expired"
BROWSER_FAILED_OPEN_PAGE_CLEANUP_EVENT_TYPE = "browser.failed_open_page.cleanup"


def _context_identity_route(context: Any) -> dict[str, str]:
    return {
        "identity_id": str(getattr(context, "actor_id", "")).strip(),
        "role_id": str(getattr(context, "role", "")).strip(),
    }


def _require_target_route(context: Any, trigger: Any) -> None:
    target_route = {
        "identity_id": str(getattr(trigger, "target_identity_id", "")).strip(),
        "role_id": str(getattr(trigger, "target_role_id", "")).strip(),
    }
    if target_route != _context_identity_route(context):
        raise PermissionError("wrong target identity for browser cleanup trigger")


def _payload(trigger: Any) -> dict[str, Any]:
    payload = getattr(trigger, "payload", None)
    if not isinstance(payload, dict):
        raise ValueError("browser page expiry trigger payload must be an object")
    tab_target_id = payload.get("tab_target_id")
    if not isinstance(tab_target_id, str) or not tab_target_id.strip():
        raise ValueError("tab_target_id is required")
    idle_seconds = payload.get("idle_seconds")
    if isinstance(idle_seconds, bool) or not isinstance(idle_seconds, int) or idle_seconds <= 0:
        raise ValueError("idle_seconds must be a positive integer")
    return {"tab_target_id": tab_target_id.strip(), "idle_seconds": idle_seconds}


def _failed_open_cleanup_payload(trigger: Any) -> dict[str, Any]:
    payload = getattr(trigger, "payload", None)
    if not isinstance(payload, dict):
        raise ValueError("browser failed-open cleanup trigger payload must be an object")
    target_id = payload.get("target_id")
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("target_id is required")
    attempts = payload.get("attempts")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        attempts = 1
    first_seen_at = payload.get("first_seen_at")
    url = payload.get("url")
    return {
        "target_id": target_id.strip(),
        "attempts": attempts,
        "first_seen_at": first_seen_at.strip() if isinstance(first_seen_at, str) and first_seen_at.strip() else None,
        "url": url.strip() if isinstance(url, str) and url.strip() else None,
    }


def _trigger_due_at(trigger: Any) -> str | None:
    source_context = getattr(trigger, "source_context", None)
    if not isinstance(source_context, dict):
        return None
    due_at = source_context.get("due_at")
    return due_at.strip() if isinstance(due_at, str) and due_at.strip() else None


def _fresh_instance_payload(context: Any) -> dict[str, Any] | None:
    instance_json = getattr(context, "instance_json", None)
    if instance_json is None:
        return None
    try:
        payload = json.loads(Path(instance_json).read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _browser_endpoint(context: Any) -> str | None:
    payload = _fresh_instance_payload(context)
    if payload is None:
        payload = getattr(context, "instance_payload", None)
    if not isinstance(payload, dict):
        return None
    port = payload.get("browser_port")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        return None
    return f"http://127.0.0.1:{port}"


def _instance_root(context: Any) -> Path | None:
    value = getattr(context, "instance_root", None)
    return Path(value) if value is not None else None


def _parent_turn_is_running(runtime: Any) -> bool:
    activity = runtime.parent_activity() if callable(getattr(runtime, "parent_activity", None)) else {}
    return isinstance(activity, dict) and activity.get("status") == "running"


def _target_id(target: dict[str, Any]) -> str | None:
    value = target.get("targetId")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _target_present(targets: list[dict[str, Any]], target_id: str) -> bool:
    return any(_target_id(target) == target_id for target in targets)


def _tracked_target(instance_root: Path, target_id: str) -> bool:
    targets = browser_lifecycle.read_page_idle_state(instance_root).get("targets")
    return isinstance(targets, dict) and target_id in targets


def _forget_and_release_if_empty(instance_root: Path, target_id: str) -> None:
    state = browser_lifecycle.forget_tab_idle_target(instance_root=instance_root, tab_target_id=target_id)
    targets = state.get("targets")
    if isinstance(targets, dict) and not targets:
        browser_lifecycle.schedule_browser_cockpit_release(
            instance_root=instance_root,
            reason="page_idle_empty",
        )


class BrowserPageExpiredHandler:
    name = "browser_page_expired"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == BROWSER_PAGE_EXPIRED_EVENT_TYPE

    def handle(self, context: Any, state: Any, runtime: Any, trigger: Any) -> daemon_contracts.HandlerResult:
        del state
        if not self.handles(trigger):
            return daemon_contracts.HandlerResult.ignored()
        try:
            _require_target_route(context, trigger)
            payload = _payload(trigger)
            root = _instance_root(context)
            if root is None:
                raise browser_lifecycle.BrowserLifecycleError("instance_root is required for browser target expiry")
            target_id = payload["tab_target_id"]
            if not _tracked_target(root, target_id):
                return daemon_contracts.HandlerResult.handled()
            if browser_lifecycle.active_tab_target_id(root) == target_id and _parent_turn_is_running(runtime):
                browser_lifecycle.refresh_tab_idle(
                    instance_root=root,
                    tab_target_id=target_id,
                    active=True,
                )
                return daemon_contracts.HandlerResult.handled()
            if browser_lifecycle.tab_idle_expiry_after_due_at(
                instance_root=root,
                tab_target_id=target_id,
                due_at=_trigger_due_at(trigger),
                idle_seconds=payload["idle_seconds"],
            ):
                return daemon_contracts.HandlerResult.handled()
            endpoint = _browser_endpoint(context)
            if endpoint is None:
                _forget_and_release_if_empty(root, target_id)
                return daemon_contracts.HandlerResult.handled()
            if cdp_target.get_target_info(endpoint, target_id) is None:
                _forget_and_release_if_empty(root, target_id)
                return daemon_contracts.HandlerResult.handled()
            cdp_target.close_target(endpoint, target_id)
            if cdp_target.get_target_info(endpoint, target_id) is not None:
                return daemon_contracts.HandlerResult.failed(
                    f"browser target still present after exact close: {target_id}"
                )
            _forget_and_release_if_empty(root, target_id)
            return daemon_contracts.HandlerResult.handled()
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))


class BrowserFailedOpenPageCleanupHandler:
    name = "browser_failed_open_page_cleanup"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == BROWSER_FAILED_OPEN_PAGE_CLEANUP_EVENT_TYPE

    def handle(self, context: Any, state: Any, runtime: Any, trigger: Any) -> daemon_contracts.HandlerResult:
        del state, runtime
        if not self.handles(trigger):
            return daemon_contracts.HandlerResult.ignored()
        try:
            _require_target_route(context, trigger)
            return self._cleanup(context, _failed_open_cleanup_payload(trigger))
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))

    def _cleanup(self, context: Any, payload: dict[str, Any]) -> daemon_contracts.HandlerResult:
        endpoint = _browser_endpoint(context)
        if endpoint is None:
            return daemon_contracts.HandlerResult.handled()
        try:
            targets = cdp_target.list_page_targets(endpoint)
        except Exception as exc:
            return self._reschedule_or_escalate(context, payload, reason=str(exc))
        if not _target_present(targets, payload["target_id"]):
            return daemon_contracts.HandlerResult.handled()
        try:
            cdp_target.close_target(endpoint, payload["target_id"])
        except Exception as exc:
            return self._reschedule_or_escalate(context, payload, reason=str(exc))
        try:
            remaining_targets = cdp_target.list_page_targets(endpoint)
        except Exception as exc:
            return self._reschedule_or_escalate(context, payload, reason=str(exc))
        if _target_present(remaining_targets, payload["target_id"]):
            return self._reschedule_or_escalate(
                context,
                payload,
                reason=f"browser target still present after exact close: {payload['target_id']}",
            )
        root = _instance_root(context)
        if root is not None:
            targets = browser_lifecycle.read_page_idle_state(root).get("targets")
            if isinstance(targets, dict) and not targets:
                browser_lifecycle.schedule_browser_cockpit_release(
                    instance_root=root,
                    reason="failed_open_page_cleanup_complete",
                )
        return daemon_contracts.HandlerResult.handled()

    def _reschedule_or_escalate(
        self,
        context: Any,
        payload: dict[str, Any],
        *,
        reason: str,
    ) -> daemon_contracts.HandlerResult:
        root = _instance_root(context)
        if root is None:
            return daemon_contracts.HandlerResult.failed(
                f"instance_root is required for browser failed-open cleanup: {reason}"
            )
        attempts = payload["attempts"]
        if attempts < browser_lifecycle.BROWSER_FAILED_OPEN_PAGE_CLEANUP_MAX_ATTEMPTS:
            browser_lifecycle.schedule_failed_open_page_cleanup(
                instance_root=root,
                target_id=payload["target_id"],
                url=payload.get("url"),
                attempts=attempts + 1,
                first_seen_at=payload.get("first_seen_at"),
            )
            return daemon_contracts.HandlerResult.handled()
        print(
            f"Browser failed-open cleanup exhausted for target {payload['target_id']}: {reason}",
            file=sys.stderr,
        )
        browser_lifecycle.schedule_browser_cockpit_release(
            instance_root=root,
            reason="failed_open_page_cleanup_exhausted",
        )
        return daemon_contracts.HandlerResult.handled()


if __name__ == "__main__":
    raise SystemExit("browser page handlers are not standalone commands")
