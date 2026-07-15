"""Browser-owned daemon handler for browser cockpit release schedules."""

from __future__ import annotations

import json
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

import daemon_contracts  # noqa: E402
import browser_runtime_manager  # noqa: E402
import cdp_browser_lifecycle as browser_lifecycle  # noqa: E402
import cdp_target  # noqa: E402


BROWSER_COCKPIT_RELEASE_EVENT_TYPE = "browser.cockpit.release"


def _context_identity_route(context: Any) -> dict[str, str]:
    return {
        "identity_id": str(getattr(context, "actor_id", "")).strip(),
        "role_id": str(getattr(context, "role", "")).strip(),
    }


def _payload(trigger: Any) -> dict[str, Any]:
    payload = getattr(trigger, "payload", None)
    if not isinstance(payload, dict):
        raise ValueError("browser release trigger payload must be an object")
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("release reason is required")
    return {"reason": reason.strip()}


def _instance_root(context: Any) -> Path | None:
    value = getattr(context, "instance_root", None)
    if value is None:
        return None
    return Path(value)


def _fresh_instance_payload(context: Any) -> dict[str, Any]:
    instance_json = getattr(context, "instance_json", None)
    if instance_json is None:
        return {}
    try:
        payload = json.loads(Path(instance_json).read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _browser_endpoint(payload: dict[str, Any]) -> str | None:
    port = payload.get("browser_port")
    if isinstance(port, bool) or not isinstance(port, int) or port < 1 or port > 65535:
        return None
    return f"http://127.0.0.1:{port}"


def _page_idle_targets(instance_root: Path) -> dict[str, Any]:
    state = browser_lifecycle._read_page_idle_state(instance_root)
    targets = state.get("targets")
    return dict(targets) if isinstance(targets, dict) else {}


def _parent_turn_is_running(runtime: Any) -> bool:
    activity = runtime.parent_activity() if callable(getattr(runtime, "parent_activity", None)) else {}
    return isinstance(activity, dict) and activity.get("status") == "running"


def _is_internal_page_url(url: object) -> bool:
    if not isinstance(url, str) or not url.strip():
        return True
    normalized = url.strip().lower()
    return normalized == "about:blank" or normalized.startswith(("chrome://", "devtools://", "edge://", "brave://"))


def _has_real_user_page(browser_url: str) -> bool:
    targets = cdp_target.list_page_targets(browser_url)
    for target in targets:
        if not isinstance(target, dict) or target.get("type") != "page":
            continue
        if not _is_internal_page_url(target.get("url")):
            return True
    return False


def _skip(reason: str) -> daemon_contracts.HandlerResult:
    print(f"Browser cockpit release skipped: {reason}", file=sys.stderr)
    return daemon_contracts.HandlerResult.handled()


class BrowserReleaseHandler:
    name = "browser_cockpit_release"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == BROWSER_COCKPIT_RELEASE_EVENT_TYPE

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> daemon_contracts.HandlerResult:
        del state
        if getattr(trigger, "type", None) != BROWSER_COCKPIT_RELEASE_EVENT_TYPE:
            return daemon_contracts.HandlerResult.ignored()
        try:
            local_route = _context_identity_route(context)
            target_route = {
                "identity_id": str(getattr(trigger, "target_identity_id", "")).strip(),
                "role_id": str(getattr(trigger, "target_role_id", "")).strip(),
            }
            if target_route != local_route:
                raise PermissionError("wrong target identity for browser cockpit release trigger")
            payload = _payload(trigger)
            if _parent_turn_is_running(runtime):
                return _skip("parent_turn_running")
            root = _instance_root(context)
            if root is None:
                return _skip("instance_root_missing")
            if _page_idle_targets(root):
                return _skip("tracked_tab_targets_remain")
            instance_payload = _fresh_instance_payload(context)
            actor_id = instance_payload.get("actor_id")
            if not isinstance(actor_id, str) or not actor_id.strip():
                actor_id = local_route["identity_id"]
            endpoint = _browser_endpoint(instance_payload)
            if endpoint is not None and _has_real_user_page(endpoint):
                return _skip("real_user_page_present")
            result = browser_runtime_manager.release(
                instance_root=root,
                actor_id=actor_id.strip(),
                reason=payload["reason"],
            )
            if result.get("ok") is not True:
                error = result.get("error")
                message = error.get("message") if isinstance(error, dict) else result.get("message")
                detail = message if isinstance(message, str) and message.strip() else "browser runtime manager release failed"
                return daemon_contracts.HandlerResult.failed(detail)
            return daemon_contracts.HandlerResult.handled()
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))


if __name__ == "__main__":
    raise SystemExit("browser_release_handler is not a standalone command")
