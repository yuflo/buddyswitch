#!/usr/bin/env python3
"""Search capability service for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urlencode

import env_profiles
from env.cdp_browser_session import (
    BROWSER_PAGE_HINT_TEMPLATE,
    BROWSER_PAGE_HINT_THRESHOLD,
    BROWSER_PAGE_LIMIT,
    BROWSER_PAGE_LIMIT_BLOCK_TEXT,
)
from env.tool_runtime.context import default_manifest_path as DEFAULT_MANIFEST
from .tool import DEFINITION
from env.tool_runtime import results as tool_results
from env.tool_runtime.broker_client import RuntimeBrokerError, broker_unavailable_feedback, request_runtime_broker

ALLOWED_BACKENDS = ("browser", "search_api")
ALLOWED_ENGINES = ("google", "web", "reddit", "x")
SEARCH_API_PROVIDER_AVAILABLE = False
REQUIRED_COCKPIT_TOOL = "chrome-devtools-cockpit"


class _RuntimeBrowserClient:
    @staticmethod
    def open_url(*, target_url: str, source_tool: str) -> dict[str, Any]:
        try:
            return request_runtime_broker("browser.open_url", {"target_url": target_url, "source_tool": source_tool})
        except RuntimeBrokerError as exc:
            extra: dict[str, Any] = dict(exc.details)
            if exc.response:
                for key, value in exc.response.items():
                    if key not in {"protocol", "request_id", "ok", "error"}:
                        extra[key] = value
            if exc.code == "E_RUNTIME_BROKER_UNAVAILABLE":
                unavailable = broker_unavailable_feedback()
                unavailable.update(extra)
                extra = unavailable
            payload: dict[str, Any] = {
                "ok": False,
                "error": {"code": exc.code, "message": exc.message},
            }
            for key, value in extra.items():
                if key in {"code", "message"}:
                    continue
                payload[key] = value
            return payload


browser_client = _RuntimeBrowserClient


_ACTION_DEFINITION_MAP = {
    'actions': [
        {
            'name': row.name,
            'payload_fields': [
                field
                for field in (row.input_schema.get('properties') or {})
                if isinstance(field, str)
            ],
        }
        for row in DEFINITION.actions
    ]
}

class SearchServiceContext(TypedDict):
    active_role: str
    active_actor: dict[str, Any]
    actor_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]
    manifest_path: Path | None


def _load_search_boundary(context: SearchServiceContext) -> dict[str, Any]:
    profile = env_profiles.require_env_profile(
        context["active_role"],
        manifest_path=context.get("manifest_path") or DEFAULT_MANIFEST,
        repo_root=env_profiles.ROOT,
    )
    tool_capability = profile.get("tool_capability")
    if not isinstance(tool_capability, dict):
        raise ValueError("env profile tool_capability must be an object")
    search = tool_capability.get("search")
    if not isinstance(search, dict):
        raise ValueError("env profile tool_capability.search must be an object")
    return dict(search)


def _normalize_query(args: dict[str, Any]) -> str | None:
    query = args.get("query")
    if not isinstance(query, str):
        return None
    query = query.strip()
    return query or None


def _normalize_engine(args: dict[str, Any]) -> str:
    engine = args.get("engine", "google")
    if engine is None:
        return "google"
    if not isinstance(engine, str):
        return ""
    return engine.strip() or ""


def _normalize_backend(args: dict[str, Any]) -> str | None:
    backend = args.get("backend")
    if not isinstance(backend, str):
        return None
    backend = backend.strip()
    return backend or None


def _require_allowed_fields(action: str, args: dict[str, Any], context: SearchServiceContext) -> dict[str, Any] | None:
    _, action_name = action.split(".", 1)
    allowed = set()
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            allowed = {field for field in row.get("payload_fields", []) if isinstance(field, str)}
            break
    unknown = sorted(key for key in args if key not in allowed)
    if not unknown:
        return None
    return tool_results.rejection(
        tool="search",
        action=action,
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_PAYLOAD",
        message=f"unsupported payload fields: {', '.join(unknown)}",
        permission_boundary="request-payload",
        human_summary="Search payload contains unsupported fields.",
        why_blocked=f"unsupported payload fields: {', '.join(unknown)}",
        impact="No search request was executed and no runtime state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Remove unsupported payload fields and retry.",
        allowed_next_actions=[
            "Use search.status to inspect supported payload fields and capability boundary.",
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="status",
                option_id="search_status_for_payload_boundary",
                reason="Use when you need supported field and capability metadata before retrying.",
            )
        ],
        correctable_fields=unknown,
    )


def _build_search_url(query: str, engine: str) -> str:
    encoded = urlencode({"q": query})
    if engine in {"google", "web"}:
        return f"https://www.google.com/search?{encoded}"
    if engine == "reddit":
        return f"https://www.reddit.com/search/?{encoded}"
    if engine == "x":
        return f"https://x.com/search?{encoded}&src=typed_query"
    raise ValueError(f"unsupported search engine: {engine}")


def _engine_error(*, action: str, context: SearchServiceContext) -> dict[str, Any]:
    return tool_results.rejection(
        tool="search",
        action=action,
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_ENGINE",
        message=f"search engine must be one of {list(ALLOWED_ENGINES)}",
        permission_boundary="request-payload",
        human_summary="Search engine is not supported.",
        why_blocked="engine must match one of the configured supported search engines.",
        impact="No search request was executed and no runtime state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Choose a supported engine value and retry the same action.",
        allowed_next_actions=[
            "Choose a supported search engine and retry.",
            "Use search.status to inspect the available search capability boundary.",
        ],
        correctable_fields=["engine"],
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="search",
                action="status",
                condition="Use when you need backend and engine boundary metadata before retrying.",
            )
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="status",
                option_id="search_status_for_engine_boundary",
                reason="Use when you need supported engine values before retrying.",
            )
        ],
        extra={
            "allowed_engines": list(ALLOWED_ENGINES),
        },
    )


def _query_error(*, action: str, context: SearchServiceContext) -> dict[str, Any]:
    return tool_results.rejection(
        tool="search",
        action=action,
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_QUERY",
        message="search query must be a non-empty string",
        permission_boundary="request-payload",
        human_summary="Search query is missing.",
        why_blocked="query must be a non-empty string.",
        impact="No search request was executed and no runtime state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Provide a non-empty query and retry.",
        allowed_next_actions=[
            "Provide a non-empty query and retry.",
            "Use search.status to inspect the available search capability boundary.",
        ],
        correctable_fields=["query"],
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="search",
                action="status",
                condition="Use when you need search boundary metadata before retrying a query.",
            )
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="status",
                option_id="search_status_for_query_boundary",
                reason="Use when you need search capability metadata before retrying a query.",
            )
        ],
    )


def _backend_error(*, context: SearchServiceContext) -> dict[str, Any]:
    return tool_results.rejection(
        tool="search",
        action="search.request",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_BACKEND",
        message=f"search backend must be explicit and one of {list(ALLOWED_BACKENDS)}",
        permission_boundary="request-payload",
        human_summary="Search backend is missing or unsupported.",
        why_blocked="backend must be explicitly set to one of the supported backend values.",
        impact="No backend request ran and no runtime state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Set backend explicitly to a supported backend and retry.",
        allowed_next_actions=[
            "Choose backend browser for browser-native discovery.",
            "Do not use implicit backend auto selection.",
        ],
        correctable_fields=["backend"],
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="search",
                action="status",
                condition="Use when you need the allowed backend set before retrying.",
            )
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="status",
                option_id="search_status_for_backend_boundary",
                reason="Use when you need allowed backend metadata before retrying.",
            )
        ],
        extra={
            "allowed_backends": list(ALLOWED_BACKENDS),
        },
    )


def _browser_unavailable(
    *,
    action: str,
    context: SearchServiceContext,
    reason: str,
    target_url: str | None = None,
) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "reason": reason,
    }
    if target_url is not None:
        extra["target_url"] = target_url
    return tool_results.rejection(
        tool="search",
        action=action,
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_BROWSER_UNAVAILABLE",
        message="instance browser endpoint is unavailable for search",
        permission_boundary="search.browser",
        human_summary="Browser endpoint is unavailable for search actions.",
        why_blocked=reason,
        impact="No browser page was opened and no BuddySwitch runtime state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Restore browser endpoint readiness for this instance, then retry.",
        allowed_next_actions=[
            "Use browser.status to inspect launcher-managed browser readiness.",
            "Retry search.open_browser after browser readiness is restored.",
        ],
        correctable_fields=["browser readiness"],
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="search",
                action="status",
                condition="Use when you need browser readiness metadata before retrying browser actions.",
            )
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="status",
                option_id="search_status_for_browser_readiness",
                reason="Use when you need browser readiness metadata before retrying browser actions.",
            )
        ],
        extra=extra,
    )


def _browser_open_failed(
    *,
    context: SearchServiceContext,
    target_url: str,
    reason: str,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="search",
        action="search.open_browser",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_BROWSER_OPEN_FAILED",
        message="failed to open search page through Chrome DevTools",
        permission_boundary="search.browser",
        human_summary="Browser endpoint responded but page open failed.",
        why_blocked=reason,
        impact="No reliable browser session change was committed for this request.",
        state_changed=False,
        retryable=True,
        retry_guidance="Ensure browser endpoint is healthy, then retry opening the page.",
        allowed_next_actions=[
            "Ensure the launcher-managed browser endpoint is reachable.",
            "Retry search.open_browser or open the target URL manually in the instance browser.",
        ],
        correctable_fields=["browser readiness", "query", "engine"],
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="search",
                action="status",
                condition="Use when you need browser endpoint health metadata before retrying.",
            ),
            tool_results.alternative_capability(
                tool="search",
                action="request",
                condition="Use when you need to re-validate target URL intent before opening browser.",
            ),
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="status",
                option_id="search_status_for_browser_open_failure",
                reason="Use when you need browser endpoint health metadata before retrying.",
            ),
            tool_results.next_action_option(
                tool="search",
                action="request",
                option_id="search_request_to_revalidate_target",
                reason="Use when you need to re-validate target URL intent before opening browser.",
            ),
        ],
        extra={
            "target_url": target_url,
            "reason": reason,
        },
    )


def _browser_page_count_unverified(
    *,
    context: SearchServiceContext,
    target_url: str,
    reason: str,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="search",
        action="search.open_browser",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_BROWSER_PAGE_COUNT_UNVERIFIED",
        message="browser page-count verification failed",
        permission_boundary="search.browser.page_limit",
        human_summary="Browser page-count verification failed.",
        why_blocked=reason,
        impact="No browser page was opened and no BuddySwitch runtime state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Ensure the browser page list endpoint is readable, then retry opening this URL.",
        allowed_next_actions=[
            "Check browser endpoint readiness and retry search.open_browser.",
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="status",
                option_id="search_status_for_browser_page_count_verification",
                reason="Use when you need browser readiness metadata before retrying.",
            )
        ],
        extra={
            "target_url": target_url,
            "browser_page_limit": BROWSER_PAGE_LIMIT,
            "page_opened": False,
            "reason": reason,
        },
    )


def _browser_page_limit_reached(
    *,
    context: SearchServiceContext,
    target_url: str,
    browser_page_count: int,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="search",
        action="search.open_browser",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_BROWSER_PAGE_LIMIT_REACHED",
        message=BROWSER_PAGE_LIMIT_BLOCK_TEXT,
        permission_boundary="search.browser.page_limit",
        human_summary="Browser page limit reached.",
        why_blocked=BROWSER_PAGE_LIMIT_BLOCK_TEXT,
        impact="No browser page was opened and no BuddySwitch runtime state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Close or reuse existing browser pages, then retry opening this URL.",
        allowed_next_actions=[
            "Close or reuse existing browser pages, then retry search.open_browser.",
        ],
        extra={
            "target_url": target_url,
            "browser_page_count": browser_page_count,
            "browser_page_limit": BROWSER_PAGE_LIMIT,
            "page_opened": False,
        },
    )


def _browser_lifecycle_registration_failed(
    *,
    context: SearchServiceContext,
    target_url: str,
    reason: str,
    page_reused: bool,
    target_id: str | None,
    close_result: dict[str, Any] | None = None,
    close_error: str | None = None,
    browser_page_count: int | None = None,
) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "target_url": target_url,
        "page_opened": False,
        "page_reused": page_reused,
        "idle_refreshed": False,
        "idle_refresh_error": reason,
        "browser_page_limit": BROWSER_PAGE_LIMIT,
    }
    if target_id:
        extra["reused_target_id" if page_reused else "created_target_id"] = target_id
    if browser_page_count is not None:
        extra["browser_page_count"] = browser_page_count
    if close_result is not None:
        extra["close_result"] = close_result
    if close_error is not None:
        extra["close_error"] = close_error
    return tool_results.rejection(
        tool="search",
        action="search.open_browser",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_BROWSER_LIFECYCLE_REGISTRATION_FAILED",
        message="browser page lifecycle registration failed",
        permission_boundary="search.browser.lifecycle",
        human_summary="Browser page lifecycle registration failed.",
        why_blocked=reason,
        impact="No unmanaged browser page is reported as opened for this request.",
        state_changed=False,
        retryable=True,
        retry_guidance="Ensure the BuddySwitch daemon is running, then retry search.open_browser.",
        allowed_next_actions=[
            "Check BuddySwitch daemon readiness and retry search.open_browser.",
            "Use search.status to inspect browser backend availability before retrying.",
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="status",
                option_id="search_status_for_browser_lifecycle_registration",
                reason="Use when you need browser lifecycle readiness metadata before retrying.",
            )
        ],
        extra=extra,
    )


def _search_api_unavailable(*, context: SearchServiceContext, boundary: dict[str, Any]) -> dict[str, Any]:
    permission = boundary.get("search_api")
    if permission == "user-approved-only":
        return tool_results.rejection(
            tool="search",
            action="search.request",
            active_actor=context["active_actor"],
            active_role=context["active_role"],
            code="E_SEARCH_BACKEND_APPROVAL_REQUIRED",
            message="search_api requires explicit user approval and no BuddySwitch-managed search API provider is configured",
            permission_boundary="search.search_api.user_approved_only",
            human_summary="search_api backend is blocked without explicit user-approved downgrade path.",
            why_blocked="No managed search_api provider is configured and profile marks search_api as user-approved-only.",
            impact="No external request was sent and no runtime state changed.",
            state_changed=False,
            retryable=True,
            retry_guidance="Use browser backend now or obtain explicit user-approved fallback before retry.",
            allowed_next_actions=[
                "Use chrome-devtools-cockpit for browser-native discovery; use search.open_browser only for search query URL construction.",
                "Ask the user for explicit one-off approval before requesting a non-browser downgrade.",
            ],
            correctable_fields=["backend"],
            alternative_capabilities=[
                tool_results.alternative_capability(
                    tool="search",
                    action="open_browser",
                    condition="Use when browser backend is available and search_api is blocked.",
                ),
                tool_results.alternative_capability(
                    tool="search",
                    action="status",
                    condition="Use when you need backend availability metadata before retrying.",
                ),
            ],
            allowed_next_action_options=[
                tool_results.next_action_option(
                    tool="search",
                    action="open_browser",
                    option_id="search_open_browser_when_search_api_blocked",
                    reason="Use when browser backend is available and search_api is blocked.",
                ),
                tool_results.next_action_option(
                    tool="search",
                    action="status",
                    option_id="search_status_for_backend_availability",
                    reason="Use when you need backend availability metadata before retrying.",
                ),
            ],
            extra={
                "reason": "No BuddySwitch-managed search API provider is configured.",
            },
        )
    return tool_results.rejection(
        tool="search",
        action="search.request",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code="E_SEARCH_BACKEND_UNAVAILABLE",
        message="search_api backend is unavailable",
        permission_boundary="search.search_api",
        human_summary="search_api backend is unavailable in this runtime profile.",
        why_blocked="No BuddySwitch-managed search_api provider is configured.",
        impact="No external request was sent and no runtime state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Use browser backend or configure search_api provider before retry.",
        allowed_next_actions=[
            "Use chrome-devtools-cockpit for browser-native discovery; use search.open_browser only for search query URL construction.",
            "Configure a BuddySwitch-managed search API provider before using search_api.",
        ],
        correctable_fields=["backend"],
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="search",
                action="open_browser",
                condition="Use when browser backend is available and search_api provider is unavailable.",
            ),
            tool_results.alternative_capability(
                tool="search",
                action="status",
                condition="Use when you need backend availability metadata before retrying.",
            ),
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="open_browser",
                option_id="search_open_browser_when_search_api_unavailable",
                reason="Use when browser backend is available and search_api provider is unavailable.",
            ),
            tool_results.next_action_option(
                tool="search",
                action="status",
                option_id="search_status_for_backend_availability",
                reason="Use when you need backend availability metadata before retrying.",
            ),
        ],
        extra={
            "reason": "No BuddySwitch-managed search API provider is configured.",
        },
    )


def _browser_payload_reason(instance_payload: dict[str, Any]) -> str | None:
    port = instance_payload.get("browser_port")
    if port is None or port == "":
        return "instance browser_port is not recorded"
    try:
        value = int(port)
    except (TypeError, ValueError):
        return "invalid browser port recorded in active instance"
    if value < 1 or value > 65535:
        return "invalid browser port recorded in active instance"
    return None


def _status_payload(context: SearchServiceContext, boundary: dict[str, Any]) -> dict[str, Any]:
    browser_reason = _browser_payload_reason(context["instance_payload"])
    browser_available = boundary.get("browser_cockpit") != "unavailable"
    search_api_permission = boundary.get("search_api")
    search_api_available = bool(SEARCH_API_PROVIDER_AVAILABLE and search_api_permission == "available")
    available_backends: list[str] = []
    if browser_available:
        available_backends.append("browser")
    if search_api_available:
        available_backends.append("search_api")
    return {
        "native_codex_web_search": "disabled",
        "available_backends": available_backends,
        "backend_status": {
            "browser": {
                "available": browser_available,
                "required_cockpit_tool": REQUIRED_COCKPIT_TOOL,
                **({"reason": browser_reason} if browser_reason else {}),
            },
            "search_api": {
                "available": search_api_available,
                "permission": search_api_permission,
                "reason": "No BuddySwitch-managed search API provider is configured.",
            },
        },
        "capability_boundary": dict(boundary),
    }


def status_for_active_instance(*, args: dict[str, Any], context: SearchServiceContext) -> dict[str, Any]:
    payload_error = _require_allowed_fields("search.status", args, context)
    if payload_error is not None:
        return payload_error
    boundary = _load_search_boundary(context)
    return tool_results.success(
        tool="search",
        action="search.status",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        effect_summary="Returned search capability metadata and backend/browser readiness status without opening a browser page.",
        state_changed=False,
        durability="none",
        read_scope="search capability and backend/browser readiness metadata",
        allowed_next_actions=[
            "Use chrome-devtools-cockpit for browser-native discovery; use search.open_browser only for focused search query URL construction.",
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="open_browser",
                option_id="search_open_for_browser_native_discovery",
                reason="Use when the browser backend is available and the host needs browser-native discovery.",
            )
        ],
        extra={
            **_status_payload(context, boundary),
            "permission_boundary": "search.profile",
        },
    )


def request_for_active_instance(*, args: dict[str, Any], context: SearchServiceContext) -> dict[str, Any]:
    payload_error = _require_allowed_fields("search.request", args, context)
    if payload_error is not None:
        return payload_error
    boundary = _load_search_boundary(context)
    backend = _normalize_backend(args)
    if backend not in ALLOWED_BACKENDS:
        return _backend_error(context=context)
    query = _normalize_query(args)
    if query is None:
        return _query_error(action="search.request", context=context)
    engine = _normalize_engine(args)
    if engine not in ALLOWED_ENGINES:
        return _engine_error(action="search.request", context=context)

    if backend == "search_api":
        return _search_api_unavailable(context=context, boundary=boundary)

    if boundary.get("browser_cockpit") == "unavailable":
        return _browser_unavailable(
            action="search.request",
            context=context,
            reason="profile search browser_cockpit is unavailable",
        )
    target_url = _build_search_url(query, engine)
    return tool_results.success(
        tool="search",
        action="search.request",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        effect_summary="Validated search request and returned target URL browser intent with page_opened=false.",
        state_changed=False,
        durability="none",
        read_scope="search request planning metadata and target URL intent without browser mutation",
        allowed_next_actions=[
            "Use chrome-devtools-cockpit for page inspection; call search.open_browser only to hand this planned search URL to the broker browser capability when you need that wrapper.",
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="open_browser",
                option_id="search_open_when_host_needs_page_open",
                reason="Use when the host needs to open the planned target URL in the browser.",
            )
        ],
        extra={
            "backend": "browser",
            "engine": engine,
            "query": query,
            "target_url": target_url,
            "required_cockpit_tool": REQUIRED_COCKPIT_TOOL,
            "page_opened": False,
            "permission_boundary": "search.browser",
        },
    )


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _broker_target_id(result: dict[str, Any]) -> str | None:
    target_id = result.get("target_id")
    return target_id if isinstance(target_id, str) and target_id.strip() else None


def _broker_page_count(result: dict[str, Any]) -> int | None:
    for key in ("browser_page_count", "projected_page_count", "page_count"):
        value = _optional_int(result.get(key))
        if value is not None:
            return value
    return None


def _idle_extra_from_open_result(result: dict[str, Any]) -> dict[str, Any]:
    extra: dict[str, Any] = {"idle_refreshed": result.get("idle_refreshed") is True}
    idle_seconds = _optional_int(result.get("idle_seconds"))
    if idle_seconds is not None:
        extra["idle_seconds"] = idle_seconds
    idle_expires_at = result.get("idle_expires_at")
    if isinstance(idle_expires_at, str) and idle_expires_at:
        extra["idle_expires_at"] = idle_expires_at
    return extra


def _idle_summary(result: dict[str, Any]) -> str | None:
    idle_seconds = _optional_int(result.get("idle_seconds"))
    if result.get("idle_refreshed") is True and idle_seconds is not None:
        return f"Browser page idle refreshed: {idle_seconds}s."
    if result.get("idle_refreshed") is True:
        return "Browser page idle refreshed."
    return None


def _page_hint(result: dict[str, Any]) -> str | None:
    if result.get("kind") != "opened":
        return None
    page_count = _broker_page_count(result)
    if page_count is None or page_count < BROWSER_PAGE_HINT_THRESHOLD:
        return None
    return BROWSER_PAGE_HINT_TEMPLATE.format(count=page_count)


def _broker_message(result: dict[str, Any], fallback: str) -> str:
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    message = error.get("message") if isinstance(error.get("message"), str) else result.get("message")
    return message if isinstance(message, str) and message.strip() else fallback


def _broker_code(result: dict[str, Any], fallback: str) -> str:
    error = result.get("error") if isinstance(result.get("error"), dict) else {}
    code = error.get("code") if isinstance(error.get("code"), str) else None
    return code.strip() if isinstance(code, str) and code.strip() else fallback


def _normalize_broker_next_action_options(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    options: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        tool = row.get("tool")
        action = row.get("action")
        reason = row.get("reason")
        if not isinstance(tool, str) or not isinstance(action, str) or not isinstance(reason, str):
            continue
        if isinstance(row.get("native_tool"), str) and isinstance(row.get("source_refs"), list):
            options.append(dict(row))
            continue
        option_id = row.get("id") if isinstance(row.get("id"), str) else row.get("option_id")
        options.append(
            tool_results.next_action_option(
                tool=tool,
                action=action,
                option_id=option_id if isinstance(option_id, str) else None,
                reason=reason,
            )
        )
    return options


def _broker_failure_passthrough(
    *,
    context: SearchServiceContext,
    target_url: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    message = _broker_message(result, "browser.open_url failed")
    permission_boundary = result.get("permission_boundary")
    if not isinstance(permission_boundary, str) or not permission_boundary.strip():
        permission_boundary = "browser.open_url"
    options = _normalize_broker_next_action_options(result.get("allowed_next_action_options"))
    if not options:
        options = [
            tool_results.next_action_option(
                tool="browser",
                action="status",
                option_id="browser_status_for_search_open_failure",
                reason="Use when you need broker-owned browser readiness before retrying.",
            )
        ]

    extra: dict[str, Any] = {
        "target_url": target_url,
        "page_opened": False,
        "reason": result.get("why_blocked") if isinstance(result.get("why_blocked"), str) else message,
    }
    for key in ("request_id", "command_hint", "stop_condition", "retriable", "retry_after_ms"):
        value = result.get(key)
        if value is not None:
            extra[key] = value

    return tool_results.rejection(
        tool="search",
        action="search.open_browser",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        code=_broker_code(result, "E_SEARCH_BROWSER_OPEN_FAILED"),
        message=message,
        permission_boundary=permission_boundary,
        human_summary="Browser broker request failed.",
        why_blocked=extra["reason"],
        impact="No browser page was opened and no BuddySwitch product state changed.",
        state_changed=False,
        durability=str(result.get("durability") or "none"),
        retryable=bool(result.get("retryable", True)),
        retry_guidance="Inspect broker-owned browser status, then retry search.open_browser when browser readiness is restored.",
        allowed_next_actions=[
            "Use browser.status to inspect broker-owned browser readiness.",
            "Retry search.open_browser after browser readiness is restored.",
        ],
        allowed_next_action_options=options,
        extra=extra,
    )


def open_browser_for_active_instance(*, args: dict[str, Any], context: SearchServiceContext) -> dict[str, Any]:
    payload_error = _require_allowed_fields("search.open_browser", args, context)
    if payload_error is not None:
        return payload_error
    boundary = _load_search_boundary(context)
    query = _normalize_query(args)
    if query is None:
        return _query_error(action="search.open_browser", context=context)
    engine = _normalize_engine(args)
    if engine not in ALLOWED_ENGINES:
        return _engine_error(action="search.open_browser", context=context)
    if boundary.get("browser_cockpit") == "unavailable":
        return _browser_unavailable(
            action="search.open_browser",
            context=context,
            reason="profile search browser_cockpit is unavailable",
        )
    target_url = _build_search_url(query, engine)
    result = browser_client.open_url(target_url=target_url, source_tool="search.open_browser")
    if result.get("ok") is not True:
        kind = result.get("kind")
        reason = _broker_message(result, "browser.open_url failed")
        if kind == "verification_failed":
            return _browser_page_count_unverified(
                context=context,
                target_url=target_url,
                reason=reason,
            )
        if kind == "blocked":
            return _browser_page_limit_reached(
                context=context,
                target_url=target_url,
                browser_page_count=_broker_page_count(result) or BROWSER_PAGE_LIMIT,
            )
        if kind == "registration_failed":
            return _browser_lifecycle_registration_failed(
                context=context,
                target_url=target_url,
                reason=reason,
                page_reused=result.get("page_reused") is True,
                target_id=_broker_target_id(result),
                browser_page_count=_broker_page_count(result),
            )
        if kind in {"open_failed", "invalid_request"}:
            return _browser_open_failed(
                context=context,
                target_url=target_url,
                reason=reason,
            )
        return _broker_failure_passthrough(context=context, target_url=target_url, result=result)

    kind = result.get("kind")
    if kind == "verification_failed":
        return _browser_page_count_unverified(
            context=context,
            target_url=target_url,
            reason=_broker_message(result, "Browser page-count verification failed."),
        )
    if kind == "blocked":
        return _browser_page_limit_reached(
            context=context,
            target_url=target_url,
            browser_page_count=_broker_page_count(result) or BROWSER_PAGE_LIMIT,
        )
    if kind == "registration_failed":
        return _browser_lifecycle_registration_failed(
            context=context,
            target_url=target_url,
            reason=_broker_message(result, "browser page lifecycle registration failed"),
            page_reused=result.get("page_reused") is True,
            target_id=_broker_target_id(result),
            browser_page_count=_broker_page_count(result),
        )
    if kind in {"open_failed", "invalid_request"}:
        return _browser_open_failed(
            context=context,
            target_url=target_url,
            reason=_broker_message(result, "browser.open_url page open failed"),
        )
    if result.get("page_reused") is True or kind == "reused":
        effect_summary = "Reused an existing browser page for the planned target URL; no new page was opened."
        idle_summary = _idle_summary(result)
        if idle_summary:
            effect_summary = f"{effect_summary} {idle_summary}"
        page_count = _broker_page_count(result)
        target_id = _broker_target_id(result)
        return tool_results.success(
            tool="search",
            action="search.open_browser",
            active_actor=context["active_actor"],
            active_role=context["active_role"],
            effect_summary=effect_summary,
            state_changed=False,
            durability="none",
            allowed_next_actions=[
                "Use chrome-devtools-cockpit to select the reused page, inspect result pages, and capture evidence.",
            ],
            extra={
                "engine": engine,
                "query": query,
                "target_url": target_url,
                "page_opened": False,
                "page_reused": True,
                "target_id": target_id,
                "reused_target_id": target_id,
                "browser_page_count": page_count,
                "browser_page_limit": BROWSER_PAGE_LIMIT,
                "permission_boundary": "search.browser",
                "mutates_product_state": False,
                **_idle_extra_from_open_result(result),
            },
        )
    effect_summary = "Opened the planned target URL in launcher-managed browser session without writing product objects."
    idle_summary = _idle_summary(result)
    if idle_summary:
        effect_summary = f"{effect_summary} {idle_summary}"
    hint = _page_hint(result)
    if hint:
        effect_summary = f"{effect_summary} {hint}"
    page_count = _broker_page_count(result)
    target_id = _broker_target_id(result)
    return tool_results.success(
        tool="search",
        action="search.open_browser",
        active_actor=context["active_actor"],
        active_role=context["active_role"],
        effect_summary=effect_summary,
        state_changed=True,
        durability="transient",
        state_changes=[
            {
                "object_type": "browser_session",
                "change": "opened_search_page",
                "target_url": target_url,
            }
        ],
        allowed_next_actions=[
            "Use chrome-devtools-cockpit to select the opened page, inspect result pages, and capture evidence.",
        ],
        extra={
            "engine": engine,
            "query": query,
            "target_url": target_url,
            "page_opened": True,
            "target_id": target_id,
            "created_target_id": target_id,
            "browser_page_count": page_count,
            "browser_page_limit": BROWSER_PAGE_LIMIT,
            "permission_boundary": "search.browser",
            "mutates_product_state": False,
            **_idle_extra_from_open_result(result),
        },
    )


_ACTION_HANDLERS = {
    'open_browser': open_browser_for_active_instance,
    'request': request_for_active_instance,
    'status': status_for_active_instance,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
