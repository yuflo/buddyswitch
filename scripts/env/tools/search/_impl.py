#!/usr/bin/env python3
"""Search capability service for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, TypedDict
from urllib.parse import urlencode

import env_profiles
from env.cdp_browser_session import (
    BROWSER_PAGE_LIMIT,
    BROWSER_PAGE_LIMIT_BLOCK_TEXT,
    evaluate_page_open_gate,
)
from env.tool_runtime.context import default_manifest_path as DEFAULT_MANIFEST
from .tool import DEFINITION
from env.tool_runtime import results as tool_results

ALLOWED_BACKENDS = ("browser", "search_api")
ALLOWED_ENGINES = ("google", "web", "reddit", "x")
SEARCH_API_PROVIDER_AVAILABLE = False
REQUIRED_COCKPIT_TOOL = "chrome-devtools-cockpit"


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


def _browser_endpoint(instance_payload: dict[str, Any]) -> tuple[str | None, str | None]:
    port = instance_payload.get("browser_port")
    if port is None:
        return None, "instance browser_port is missing"
    if isinstance(port, bool) or not isinstance(port, int):
        return None, f"invalid browser port: {port}"
    if port < 1 or port > 65535:
        return None, f"invalid browser port: {port}"
    return f"http://127.0.0.1:{port}", None


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


def _open_browser_page(browser_endpoint: str, target_url: str) -> tuple[bool, str | None]:
    helper = env_profiles.ROOT / "scripts" / "env" / "cdp_background_page.py"
    try:
        completed = subprocess.run(
            [
                "python3",
                str(helper),
                "--browser-url",
                browser_endpoint,
                "--url",
                target_url,
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=5.0,
        )
    except subprocess.TimeoutExpired:
        return False, "Chrome DevTools Target.createTarget timed out"
    except OSError as exc:
        return False, str(exc)
    if completed.returncode == 0:
        return True, None
    reason = completed.stderr.strip() or completed.stdout.strip()
    if reason:
        return False, reason
    return False, f"Chrome DevTools Target.createTarget exited with status {completed.returncode}"


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
    browser_endpoint: str | None = None,
) -> dict[str, Any]:
    extra: dict[str, Any] = {
        "reason": reason,
    }
    if target_url is not None:
        extra["target_url"] = target_url
    if browser_endpoint is not None:
        extra["browser_endpoint"] = browser_endpoint
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
            "Ensure the launcher-managed browser for this instance is running.",
            "Retry search.open_browser after browser ensure succeeds.",
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
    browser_endpoint: str,
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
            "browser_endpoint": browser_endpoint,
            "reason": reason,
        },
    )


def _browser_page_count_unverified(
    *,
    context: SearchServiceContext,
    target_url: str,
    browser_endpoint: str,
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
            "browser_endpoint": browser_endpoint,
            "browser_page_limit": BROWSER_PAGE_LIMIT,
            "page_opened": False,
            "reason": reason,
        },
    )


def _browser_page_limit_reached(
    *,
    context: SearchServiceContext,
    target_url: str,
    browser_endpoint: str,
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
            "browser_endpoint": browser_endpoint,
            "browser_page_count": browser_page_count,
            "browser_page_limit": BROWSER_PAGE_LIMIT,
            "page_opened": False,
        },
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
                "Use search.open_browser for browser-native discovery.",
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
            "Use search.open_browser for browser-native discovery.",
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


def _status_payload(context: SearchServiceContext, boundary: dict[str, Any]) -> dict[str, Any]:
    browser_endpoint, browser_reason = _browser_endpoint(context["instance_payload"])
    browser_available = browser_endpoint is not None and boundary.get("browser_cockpit") != "unavailable"
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
                "browser_url": browser_endpoint,
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
            "Use search.open_browser with backend browser for browser-native discovery.",
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
    browser_endpoint, browser_reason = _browser_endpoint(context["instance_payload"])
    if browser_endpoint is None:
        return _browser_unavailable(
            action="search.request",
            context=context,
            reason=browser_reason or "instance browser endpoint is missing",
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
        read_scope="search request planning metadata and target URL intent without browser session mutation",
        allowed_next_actions=[
            "Call search.open_browser to open the target in the instance browser, then traverse result pages in chrome-devtools-cockpit.",
        ],
        allowed_next_action_options=[
            tool_results.next_action_option(
                tool="search",
                action="open_browser",
                option_id="search_open_when_host_needs_page_open",
                reason="Use when the host needs to open the planned target URL in the browser session.",
            )
        ],
        extra={
            "backend": "browser",
            "engine": engine,
            "query": query,
            "target_url": target_url,
            "browser_endpoint": browser_endpoint,
            "required_cockpit_tool": REQUIRED_COCKPIT_TOOL,
            "page_opened": False,
            "permission_boundary": "search.browser",
        },
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
    browser_endpoint, browser_reason = _browser_endpoint(context["instance_payload"])
    if browser_endpoint is None:
        return _browser_unavailable(
            action="search.open_browser",
            context=context,
            reason=browser_reason or "instance browser endpoint is missing",
            target_url=target_url,
        )
    page_gate = evaluate_page_open_gate(browser_endpoint, target_url)
    if page_gate.kind == "verification_failed":
        return _browser_page_count_unverified(
            context=context,
            target_url=target_url,
            browser_endpoint=browser_endpoint,
            reason=page_gate.message or "Browser page-count verification failed.",
        )
    if page_gate.kind == "block":
        return _browser_page_limit_reached(
            context=context,
            target_url=target_url,
            browser_endpoint=browser_endpoint,
            browser_page_count=page_gate.page_count or BROWSER_PAGE_LIMIT,
        )
    if page_gate.kind == "reuse":
        target_id = page_gate.target_id or ""
        return tool_results.success(
            tool="search",
            action="search.open_browser",
            active_actor=context["active_actor"],
            active_role=context["active_role"],
            effect_summary="Reused an existing browser page for the planned target URL; no new page was opened.",
            state_changed=False,
            durability="none",
            allowed_next_actions=[
                "Use chrome-devtools-cockpit to select the reused page, inspect result pages, and capture evidence.",
            ],
            extra={
                "engine": engine,
                "query": query,
                "target_url": target_url,
                "browser_endpoint": browser_endpoint,
                "page_opened": False,
                "page_reused": True,
                "reused_target_id": target_id,
                "browser_page_count": page_gate.page_count,
                "browser_page_limit": BROWSER_PAGE_LIMIT,
                "permission_boundary": "search.browser",
                "mutates_product_state": False,
            },
        )
    opened, open_reason = _open_browser_page(browser_endpoint, target_url)
    if not opened:
        return _browser_open_failed(
            context=context,
            target_url=target_url,
            browser_endpoint=browser_endpoint,
            reason=open_reason or "Chrome DevTools page open failed",
        )
    hint = page_gate.hint_text()
    effect_summary = "Opened the planned target URL in launcher-managed browser session without writing product objects."
    if hint:
        effect_summary = f"{effect_summary} {hint}"
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
            "browser_endpoint": browser_endpoint,
            "page_opened": True,
            "browser_page_count": page_gate.projected_page_count,
            "browser_page_limit": BROWSER_PAGE_LIMIT,
            "permission_boundary": "search.browser",
            "mutates_product_state": False,
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
