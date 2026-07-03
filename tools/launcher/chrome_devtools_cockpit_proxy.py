#!/usr/bin/env python3
"""BuddySwitch stdio proxy for Chrome DevTools MCP focus control."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import threading
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from env import cdp_browser_lifecycle as browser_lifecycle  # noqa: E402
from env import cdp_browser_session as browser_session  # noqa: E402
from runtime_kernel.client import RuntimeBrokerError, request_runtime_broker  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
STATIC_TOOLS_PATH = ROOT / "tools" / "launcher" / "assets" / "chrome-devtools-mcp-1.1.1-tools.json"
DEFAULT_UPSTREAM_COMMAND = "npx chrome-devtools-mcp@1.1.1"
UPSTREAM_EXIT_GRACE_SECONDS = 2.0
FOCUS_METHODS = {"Page.bringToFront", "Target.activateTarget"}
PAGE_SCOPED_USE_TOOLS = {
    "take_snapshot",
    "take_screenshot",
    "click",
    "type_text",
    "evaluate_script",
    "navigate_page",
    "wait_for",
    "fill",
    "press_key",
}
BROWSER_SESSION_TOOL_DESCRIPTIONS = {
    "new_page": "BuddySwitch chrome-devtools-cockpit opens or reuses a managed browser-session page, registers idle TTL, and does not activate the foreground browser.",
    "list_pages": "Use chrome-devtools-cockpit list_pages to inspect managed browser-session pages, target ids, current-page state, URLs, titles, and idle state before opening more pages.",
    "select_page": "BuddySwitch selects an existing browser-session page without foreground activation and refreshes current-page idle state.",
    "take_snapshot": "Use after list_pages/select_page to inspect the selected browser-session page content.",
    "take_screenshot": "Use after list_pages/select_page to capture the selected browser-session page.",
    "navigate_page": "Page-scoped browser-session action; navigation refreshes managed browser idle state.",
    "click": "Page-scoped browser-session action; interaction refreshes managed browser idle state.",
    "type_text": "Page-scoped browser-session action; interaction refreshes managed browser idle state.",
    "evaluate_script": "Page-scoped browser-session action; evaluation refreshes managed browser idle state.",
    "wait_for": "Page-scoped browser-session action; waiting refreshes managed browser idle state.",
    "fill": "Page-scoped browser-session action; form filling refreshes managed browser idle state.",
    "press_key": "Page-scoped browser-session action; keyboard input refreshes managed browser idle state.",
}
SELECTED_URL_RE = re.compile(r"(https?://\S+)\s+\[selected\]", re.IGNORECASE)
LIFECYCLE_WARNING_PREFIX = "Browser lifecycle warning:"


def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Proxy Chrome DevTools MCP through BuddySwitch focus controls.")
    parser.add_argument(
        "--upstream-command",
        default=os.environ.get("BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_COMMAND", DEFAULT_UPSTREAM_COMMAND),
        help="Command used to start the upstream Chrome DevTools MCP server.",
    )
    parser.add_argument("--instance-root", help="BuddySwitch instance root for browser lifecycle state.")
    parser.add_argument("--broker-socket", help="Runtime broker Unix socket path for product-mode browser acquisition.")
    return parser.parse_known_args(argv)


def apply_broker_socket_arg(args: argparse.Namespace) -> None:
    raw = getattr(args, "broker_socket", None)
    if isinstance(raw, str) and raw.strip():
        os.environ["BUDDYSWITCH_RUNTIME_BROKER_SOCKET"] = raw.strip()


def build_upstream_argv(args: argparse.Namespace, passthrough_args: list[str], browser_url: str) -> list[str]:
    upstream = shlex.split(args.upstream_command)
    if not upstream:
        raise ValueError("--upstream-command must not be empty")
    return upstream + passthrough_args + [f"--browser-url={browser_url}"]


def is_jsonrpc_request(message: dict[str, Any]) -> bool:
    return "id" in message


def tool_error_response(request: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "jsonrpc": request.get("jsonrpc", "2.0"),
        "id": request.get("id"),
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
            "isError": True,
        },
    }


def tool_success_response(request: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "jsonrpc": request.get("jsonrpc", "2.0"),
        "id": request.get("id"),
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        },
    }


def rpc_error_response(request: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "jsonrpc": request.get("jsonrpc", "2.0"),
        "id": request.get("id"),
        "error": {
            "code": -32000,
            "message": text,
        },
    }


def initialize_response(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": request.get("jsonrpc", "2.0"),
        "id": request.get("id"),
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "chrome-devtools-cockpit",
                "version": "1.1.1",
            },
        },
    }


def upstream_initialize_request(request_id: str, client_initialize_params: dict[str, Any] | None) -> dict[str, Any]:
    params = copy.deepcopy(client_initialize_params) if isinstance(client_initialize_params, dict) else {}
    params.setdefault("protocolVersion", "2024-11-05")
    params.setdefault("capabilities", {})
    params.setdefault(
        "clientInfo",
        {
            "name": "buddyswitch-chrome-devtools-cockpit",
            "version": "1.0.0",
        },
    )
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "initialize",
        "params": params,
    }


def upstream_initialized_notification() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    }


def load_static_tools() -> list[dict[str, Any]]:
    payload = json.loads(STATIC_TOOLS_PATH.read_text(encoding="utf-8"))
    tools = payload.get("tools")
    if not isinstance(tools, list):
        raise RuntimeError("static Chrome DevTools MCP tools asset is missing tools list")
    return [dict(tool) for tool in tools if isinstance(tool, dict)]


def tools_list_response(request: dict[str, Any]) -> dict[str, Any]:
    return patch_tool_list_message(
        {
            "jsonrpc": request.get("jsonrpc", "2.0"),
            "id": request.get("id"),
            "result": {"tools": load_static_tools()},
        }
    )


def acquire_browser_url() -> str:
    try:
        result = request_runtime_broker("browser.acquire", {"reason": "chrome-devtools-cockpit"})
    except RuntimeBrokerError as exc:
        raise RuntimeError(f"browser acquire failed: {exc.message}") from exc
    if result.get("ok") is not True:
        error = result.get("error") if isinstance(result.get("error"), dict) else {}
        detail = error.get("message") if isinstance(error.get("message"), str) else "broker returned a failed result"
        raise RuntimeError(f"browser acquire failed: {detail}")
    browser_url = result.get("browser_url")
    if not isinstance(browser_url, str) or not browser_url.strip():
        raise RuntimeError("browser acquire failed: broker did not return browser_url")
    return browser_url.strip()


def focus_block_text(method: str) -> str:
    return (
        f"BuddySwitch blocked {method} because chrome-devtools-cockpit runs in "
        "non-activating mode. Use a user-visible handoff before requesting browser focus."
    )


def _instance_root_path(instance_root: str | None) -> Path | None:
    if not isinstance(instance_root, str) or not instance_root.strip():
        return None
    return Path(instance_root.strip())


def _idle_hint_from_result(result: dict[str, Any] | None) -> str:
    idle_seconds = result.get("idle_seconds") if isinstance(result, dict) else None
    if isinstance(idle_seconds, int):
        return f"Browser page idle refreshed: {idle_seconds}s."
    return "Browser page idle refreshed."


def _refresh_current_idle_hint(
    *,
    root: Path,
    target_id: str,
    target_url: str | None = None,
    page_id: object | None = None,
) -> str:
    result = browser_lifecycle.refresh_current_page_idle(
        instance_root=root,
        target_id=target_id,
        target_url=target_url,
        page_id=page_id,
    )
    return _idle_hint_from_result(result)


def _browser_session_open_text(result: browser_session.BrowserSessionOpenResult) -> str:
    action = "opened" if result.kind == "opened" else "reused"
    lines = [
        f"BuddySwitch browser-session {action} page.",
        f"state: {result.kind}",
        f"target_url: {result.target_url}",
        f"target_id: {result.target_id or '<unknown>'}",
    ]
    if result.page_count is not None:
        if result.projected_page_count is not None and result.projected_page_count != result.page_count:
            lines.append(f"page_count: {result.page_count} -> {result.projected_page_count}")
        else:
            lines.append(f"page_count: {result.page_count}")
    if (
        result.kind == "opened"
        and result.projected_page_count is not None
        and result.projected_page_count >= browser_session.BROWSER_PAGE_HINT_THRESHOLD
    ):
        lines.append(browser_session.BROWSER_PAGE_HINT_TEMPLATE.format(count=result.projected_page_count))
    if result.idle_refreshed:
        idle = f"Browser page idle refreshed: {result.idle_seconds}s" if result.idle_seconds is not None else "Browser page idle refreshed"
        if result.idle_expires_at:
            idle = f"{idle}; idle_expires_at: {result.idle_expires_at}"
        lines.append(f"{idle}.")
    return "\n".join(lines)


def _browser_session_error_text(result: browser_session.BrowserSessionOpenResult) -> str:
    lines = [
        "BuddySwitch browser-session did not open a page.",
        f"state: {result.kind}",
    ]
    if result.target_url:
        lines.append(f"target_url: {result.target_url}")
    if result.target_id:
        lines.append(f"target_id: {result.target_id}")
    if result.page_count is not None:
        lines.append(f"page_count: {result.page_count}")
    if result.message:
        lines.append(result.message)
    return "\n".join(lines)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _target_id(target: dict[str, Any]) -> str | None:
    for key in ("id", "targetId"):
        value = target.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _browser_session_state_text(*, browser_url: str, instance_root: str | None) -> str:
    try:
        targets = browser_lifecycle.read_page_targets(browser_url)
    except Exception as exc:
        detail = str(exc).replace(browser_url, "browser endpoint")
        return f"BuddySwitch browser-session state:\n- unavailable: {detail}"
    root = _instance_root_path(instance_root)
    idle_state: dict[str, Any] = {}
    if root is not None:
        try:
            idle_state = browser_lifecycle._read_page_idle_state(root)
        except Exception:
            idle_state = {}
    current_target_id = idle_state.get("current_target_id")
    current_target_id = current_target_id.strip() if isinstance(current_target_id, str) and current_target_id.strip() else None
    idle_targets = idle_state.get("targets")
    idle_targets = idle_targets if isinstance(idle_targets, dict) else {}

    lines = [
        "BuddySwitch browser-session state:",
        f"- current_target_id: {current_target_id or '<none>'}",
        "- pages:",
    ]
    if not targets:
        lines.append("  - <none>")
        return "\n".join(lines)
    for target in targets:
        target_id = _target_id(target) or "<unknown>"
        title = target.get("title")
        url = target.get("url")
        target_idle = idle_targets.get(target_id)
        target_idle = target_idle if isinstance(target_idle, dict) else {}
        last_used_at = target_idle.get("last_used_at")
        expires_at = None
        parsed_last_used = _parse_utc(last_used_at) if isinstance(last_used_at, str) else None
        if parsed_last_used is not None:
            expires_at = _format_utc(parsed_last_used + timedelta(seconds=browser_lifecycle.BROWSER_PAGE_IDLE_SECONDS))
        lines.extend(
            [
                f"  - target_id: {target_id}",
                f"    title: {title if isinstance(title, str) and title else '<untitled>'}",
                f"    url: {url if isinstance(url, str) and url else '<unknown>'}",
                f"    current: {'true' if target_id == current_target_id else 'false'}",
                f"    idle_tracked: {'true' if target_idle else 'false'}",
            ]
        )
        if isinstance(last_used_at, str) and last_used_at.strip():
            lines.append(f"    last_used_at: {last_used_at.strip()}")
        if expires_at is not None:
            lines.append(f"    idle_expires_at: {expires_at}")
    return "\n".join(lines)


def _schedule_release_if_no_tracked_pages(root: Path) -> str | None:
    try:
        state = browser_lifecycle._read_page_idle_state(root)
        targets = state.get("targets")
        if isinstance(targets, dict) and targets:
            return None
        browser_lifecycle.schedule_browser_cockpit_release(
            instance_root=root,
            reason="page_idle_empty",
        )
        return None
    except Exception as exc:
        return f"{LIFECYCLE_WARNING_PREFIX} list_pages idle release was not scheduled: {exc}"


def _refresh_page_idle_hint(
    *,
    root: Path,
    target_id: str,
    target_url: str | None = None,
    page_id: object | None = None,
) -> str:
    result = browser_lifecycle.refresh_page_idle(
        instance_root=root,
        target_id=target_id,
        target_url=target_url,
        page_id=page_id,
    )
    return _idle_hint_from_result(result)


def mutate_tool_call(
    message: dict[str, Any],
    browser_url: str,
    instance_root: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, Any | None]:
    params = message.get("params")
    if not isinstance(params, dict):
        return message, None, None
    name = params.get("name")
    arguments = params.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return message, None, None

    if name == "new_page":
        if "isolatedContext" in arguments:
            return None, tool_error_response(
                message,
                "BuddySwitch blocked new_page with isolatedContext because upstream Chrome DevTools MCP "
                "does not apply background creation to isolated browser contexts. This keeps the "
                "chrome-devtools-cockpit path non-activating.",
            ), None
        if _instance_root_path(instance_root) is None:
            return None, tool_error_response(
                message,
                "BuddySwitch blocked new_page because chrome-devtools-cockpit requires --instance-root "
                "to register browser lifecycle state before opening pages.",
            ), None
        root = _instance_root_path(instance_root)
        assert root is not None
        target_url = arguments.get("url")
        result = browser_session.open_or_reuse_page(
            instance_root=root,
            browser_url=browser_url,
            target_url=target_url if isinstance(target_url, str) else "",
        )
        if result.kind in {"opened", "reused"}:
            return None, tool_success_response(message, _browser_session_open_text(result)), None
        return None, tool_error_response(message, _browser_session_error_text(result)), None

    if name == "list_pages":
        return message, None, {"kind": "list_pages"}

    if name == "select_page":
        rewritten = copy.deepcopy(message)
        rewritten_params = rewritten.setdefault("params", {})
        rewritten_arguments = dict(arguments)
        rewritten_arguments["bringToFront"] = False
        rewritten_params["arguments"] = rewritten_arguments
        return rewritten, None, {"kind": "select_page", "page_id": arguments.get("pageId")}

    if name in PAGE_SCOPED_USE_TOOLS:
        return message, None, {"kind": "current_page"}

    return message, None, None


def mutate_client_message(
    message: dict[str, Any],
    browser_url: str,
    instance_root: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, Any | None]:
    method = message.get("method")
    if method in FOCUS_METHODS and is_jsonrpc_request(message):
        return None, rpc_error_response(message, focus_block_text(str(method))), None
    if method == "tools/call":
        return mutate_tool_call(message, browser_url, instance_root=instance_root)
    return message, None, None


def append_description(value: object, addition: str) -> str:
    base = value if isinstance(value, str) else ""
    if addition in base:
        return base
    if base:
        return f"{base}\n\n{addition}"
    return addition


def patch_schema_property(tool: dict[str, Any], property_name: str, description: str) -> None:
    input_schema = tool.get("inputSchema")
    if not isinstance(input_schema, dict):
        return
    properties = input_schema.get("properties")
    if not isinstance(properties, dict):
        return
    field = properties.get(property_name)
    if not isinstance(field, dict):
        return
    field["description"] = description


def patch_tool_list_message(message: dict[str, Any]) -> dict[str, Any]:
    result = message.get("result")
    if not isinstance(result, dict):
        return message
    tools = result.get("tools")
    if not isinstance(tools, list):
        return message

    patched = copy.deepcopy(message)
    patched_tools = patched["result"]["tools"]
    for tool in patched_tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        if isinstance(name, str) and name in BROWSER_SESSION_TOOL_DESCRIPTIONS:
            tool["description"] = append_description(tool.get("description"), BROWSER_SESSION_TOOL_DESCRIPTIONS[name])
        if name == "new_page":
            patch_schema_property(
                tool,
                "background",
                "Ignored by BuddySwitch because chrome-devtools-cockpit opens managed browser-session pages without foreground activation.",
            )
            patch_schema_property(
                tool,
                "isolatedContext",
                "BuddySwitch blocks this parameter because upstream does not apply background creation to this path.",
            )
        elif name == "select_page":
            patch_schema_property(
                tool,
                "bringToFront",
                "BuddySwitch forces this to false for chrome-devtools-cockpit.",
            )
    return patched


def patch_tool_response_hint(message: dict[str, Any], hint: str) -> dict[str, Any]:
    result = message.get("result")
    if not isinstance(result, dict):
        return message
    patched = copy.deepcopy(message)
    patched_result = patched.setdefault("result", {})
    content = patched_result.get("content")
    if not isinstance(content, list):
        content = []
        patched_result["content"] = content
    content.append({"type": "text", "text": hint})
    return patched


def tool_response_text(message: dict[str, Any]) -> str:
    result = message.get("result")
    if not isinstance(result, dict):
        return ""
    content = result.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)


def selected_url_from_response(message: dict[str, Any]) -> str | None:
    match = SELECTED_URL_RE.search(tool_response_text(message))
    if not match:
        return None
    return match.group(1).strip()


def unique_page_target_for_url(browser_url: str, target_url: str) -> str | None:
    targets = browser_lifecycle.read_page_targets(browser_url)
    matches = [
        target.get("id")
        for target in targets
        if isinstance(target, dict)
        and target.get("type") == "page"
        and target.get("url") == target_url
        and isinstance(target.get("id"), str)
        and target.get("id")
    ]
    if len(matches) != 1:
        return None
    return str(matches[0])


def _tool_response_succeeded(message: dict[str, Any]) -> bool:
    result = message.get("result")
    return isinstance(result, dict) and result.get("isError") is not True


def patch_tool_response_page_use_metadata(
    message: dict[str, Any],
    metadata: dict[str, Any],
    *,
    browser_url: str,
    instance_root: str | None,
) -> dict[str, Any]:
    patched = message
    page_hint = metadata.get("page_hint")
    if isinstance(page_hint, str) and page_hint:
        patched = patch_tool_response_hint(patched, page_hint)
    kind = metadata.get("kind")
    if kind != "new_page" and not _tool_response_succeeded(message):
        return patched
    root = _instance_root_path(instance_root)
    if root is None:
        return patched
    if kind == "list_pages":
        if not _tool_response_succeeded(message):
            return patched
        patched = patch_tool_response_hint(patched, _browser_session_state_text(browser_url=browser_url, instance_root=instance_root))
        warning = _schedule_release_if_no_tracked_pages(root)
        if warning:
            patched = patch_tool_response_hint(patched, warning)
        return patched
    if kind == "select_page":
        page_id = metadata.get("page_id")
        target_id: str | None = None
        target_url: str | None = None
        try:
            target_id = browser_lifecycle.target_id_for_page_id(root, page_id)
        except Exception:
            target_id = None
        if target_id is None:
            target_url = selected_url_from_response(message)
            if target_url is None:
                return patch_tool_response_hint(
                    patched,
                    f"{LIFECYCLE_WARNING_PREFIX} selected page target was not resolved; browser idle was not refreshed.",
                )
            try:
                target_id = unique_page_target_for_url(browser_url, target_url)
            except Exception:
                target_id = None
            if target_id is None:
                return patch_tool_response_hint(
                    patched,
                    f"{LIFECYCLE_WARNING_PREFIX} selected page URL was ambiguous or missing in Chrome target list; browser idle was not refreshed.",
                )
        try:
            hint = _refresh_current_idle_hint(
                root=root,
                target_id=target_id,
                target_url=target_url,
                page_id=page_id,
            )
        except Exception as exc:
            return patch_tool_response_hint(
                patched,
                f"{LIFECYCLE_WARNING_PREFIX} selected page idle was not refreshed: {exc}",
            )
        return patch_tool_response_hint(patched, hint)
    if kind == "current_page":
        try:
            target_id = browser_lifecycle.current_target_id(root)
        except Exception as exc:
            return patch_tool_response_hint(
                patched,
                f"{LIFECYCLE_WARNING_PREFIX} current page target was not readable; browser idle was not refreshed: {exc}",
            )
        if target_id is None:
            return patch_tool_response_hint(
                patched,
                f"{LIFECYCLE_WARNING_PREFIX} current page target is unknown; browser idle was not refreshed.",
            )
        try:
            hint = _refresh_page_idle_hint(root=root, target_id=target_id)
        except Exception as exc:
            return patch_tool_response_hint(
                patched,
                f"{LIFECYCLE_WARNING_PREFIX} current page idle was not refreshed: {exc}",
            )
        return patch_tool_response_hint(patched, hint)
    return patched


def write_json_line(message: dict[str, Any], output_lock: threading.Lock) -> None:
    with output_lock:
        sys.stdout.write(json.dumps(message, ensure_ascii=True, separators=(",", ":")) + "\n")
        sys.stdout.flush()


def write_raw_line(line: str, output_lock: threading.Lock) -> None:
    with output_lock:
        sys.stdout.write(line)
        if not line.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()


def close_upstream(upstream: subprocess.Popen[str]) -> int:
    if upstream.stdin is not None and not upstream.stdin.closed:
        try:
            upstream.stdin.close()
        except OSError:
            pass
    try:
        return upstream.wait(timeout=UPSTREAM_EXIT_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        upstream.terminate()
    try:
        return upstream.wait(timeout=UPSTREAM_EXIT_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        upstream.kill()
        return upstream.wait(timeout=UPSTREAM_EXIT_GRACE_SECONDS)


class UpstreamManager:
    def __init__(
        self,
        *,
        args: argparse.Namespace,
        passthrough_args: list[str],
        instance_root: str | None,
        output_lock: threading.Lock,
        client_initialize_params: dict[str, Any] | None = None,
    ) -> None:
        self.args = args
        self.passthrough_args = passthrough_args
        self.instance_root = instance_root
        self.output_lock = output_lock
        self.client_initialize_params = copy.deepcopy(client_initialize_params)
        self.ids_lock = threading.Lock()
        self.upstream: subprocess.Popen[str] | None = None
        self.relay: threading.Thread | None = None
        self.browser_url: str | None = None
        self.initialized = False
        self.generation = 0
        self.drop_response_ids: set[Any] = set()
        self.pending_requests: dict[Any, tuple[dict[str, Any], subprocess.Popen[str]]] = {}
        self.pending_hints: dict[Any, tuple[Any, str, subprocess.Popen[str]]] = {}

    def set_client_initialize_params(self, params: Any) -> None:
        self.client_initialize_params = copy.deepcopy(params) if isinstance(params, dict) else {}

    def is_started(self) -> bool:
        return self.upstream is not None and self.upstream.poll() is None

    def start(self, browser_url: str) -> None:
        try:
            upstream_argv = build_upstream_argv(self.args, self.passthrough_args, browser_url)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        try:
            upstream = subprocess.Popen(
                upstream_argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except OSError as exc:
            raise RuntimeError(f"failed to start upstream chrome-devtools-mcp: {exc}") from exc
        self.upstream = upstream
        self.browser_url = browser_url
        self.initialized = False
        self.generation += 1
        self.write_pid_markers(upstream)
        self.relay = threading.Thread(target=self._relay, args=(upstream, browser_url), daemon=True)
        self.relay.start()

    def ensure_started(self, browser_url: str) -> None:
        if self.is_started() and self.browser_url == browser_url:
            return
        if self.upstream is not None:
            self.stop()
        self.start(browser_url)

    def ensure_initialized(self) -> None:
        if self.initialized:
            return
        upstream = self._active_upstream()
        request_id = f"buddyswitch.initialize.{self.generation}"
        with self.ids_lock:
            self.drop_response_ids.add(request_id)
        self._write_to_upstream(upstream, upstream_initialize_request(request_id, self.client_initialize_params))
        self._write_to_upstream(upstream, upstream_initialized_notification())
        self.initialized = True

    def send_request(self, message: dict[str, Any], response_hint: Any | None) -> None:
        upstream = self._active_upstream()
        message_id = message.get("id")
        if is_jsonrpc_request(message):
            with self.ids_lock:
                self.pending_requests[message_id] = (copy.deepcopy(message), upstream)
                if response_hint:
                    browser_url = self.browser_url or ""
                    self.pending_hints[message_id] = (response_hint, browser_url, upstream)
        try:
            self._write_to_upstream(upstream, message)
        except RuntimeError:
            if is_jsonrpc_request(message):
                with self.ids_lock:
                    self.pending_requests.pop(message_id, None)
                    self.pending_hints.pop(message_id, None)
            raise

    def forward_raw_if_started(self, raw_line: str) -> None:
        if not self.is_started():
            return
        upstream = self._active_upstream()
        assert upstream.stdin is not None
        try:
            upstream.stdin.write(raw_line)
            upstream.stdin.flush()
        except OSError as exc:
            raise RuntimeError(f"failed to write raw message to upstream chrome-devtools-mcp: {exc}") from exc

    def stop(self) -> None:
        upstream = self.upstream
        if upstream is not None:
            close_upstream(upstream)
        relay = self.relay
        if relay is not None:
            relay.join(timeout=UPSTREAM_EXIT_GRACE_SECONDS)
        self.upstream = None
        self.relay = None
        self.browser_url = None
        self.initialized = False
        self.clear_pid_markers()

    def note_exited(self, upstream: subprocess.Popen[str]) -> None:
        pending: list[dict[str, Any]] = []
        with self.ids_lock:
            for message_id, (request, request_upstream) in list(self.pending_requests.items()):
                if request_upstream is upstream:
                    pending.append(request)
                    self.pending_requests.pop(message_id, None)
                    self.pending_hints.pop(message_id, None)
            for message_id, (_hint, _browser_url, hint_upstream) in list(self.pending_hints.items()):
                if hint_upstream is upstream:
                    self.pending_hints.pop(message_id, None)
        for request in pending:
            write_json_line(
                tool_error_response(request, "Upstream chrome-devtools-mcp exited before completing this browser tool call."),
                self.output_lock,
            )
        if self.upstream is upstream:
            self.upstream = None
            self.relay = None
            self.browser_url = None
            self.initialized = False
            self.clear_pid_markers()

    def write_pid_markers(self, upstream: subprocess.Popen[str]) -> None:
        paths = self._marker_paths()
        if paths is None:
            return
        pid_path, pgid_path = paths
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(f"{upstream.pid}\n", encoding="ascii")
        try:
            pgid = os.getpgid(upstream.pid)
        except OSError:
            pgid = upstream.pid
        pgid_path.write_text(f"{pgid}\n", encoding="ascii")

    def clear_pid_markers(self) -> None:
        paths = self._marker_paths()
        if paths is None:
            return
        for path in paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def _marker_paths(self) -> tuple[Path, Path] | None:
        root = _instance_root_path(self.instance_root)
        if root is None:
            return None
        runtime_dir = root / "runtime" / "browser"
        return runtime_dir / "cockpit-upstream.pid", runtime_dir / "cockpit-upstream.pgid"

    def _active_upstream(self) -> subprocess.Popen[str]:
        if self.upstream is None or self.upstream.poll() is not None:
            raise RuntimeError("upstream chrome-devtools-mcp is not running")
        return self.upstream

    def _write_to_upstream(self, upstream: subprocess.Popen[str], message: dict[str, Any]) -> None:
        if upstream.stdin is None:
            raise RuntimeError("upstream chrome-devtools-mcp stdin is unavailable")
        try:
            upstream.stdin.write(json.dumps(message, ensure_ascii=True, separators=(",", ":")) + "\n")
            upstream.stdin.flush()
        except OSError as exc:
            raise RuntimeError(f"failed to write to upstream chrome-devtools-mcp: {exc}") from exc

    def _relay(self, upstream: subprocess.Popen[str], browser_url: str) -> None:
        assert upstream.stdout is not None
        try:
            for raw_line in upstream.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    write_raw_line(raw_line, self.output_lock)
                    continue
                if not isinstance(message, dict):
                    write_raw_line(raw_line, self.output_lock)
                    continue
                message_id = message.get("id")
                response_hint: Any | None = None
                hint_browser_url = browser_url
                with self.ids_lock:
                    if message_id in self.drop_response_ids:
                        self.drop_response_ids.discard(message_id)
                        continue
                    self.pending_requests.pop(message_id, None)
                    pending = self.pending_hints.pop(message_id, None)
                    if pending is not None:
                        response_hint, hint_browser_url, _hint_upstream = pending
                if isinstance(response_hint, dict):
                    message = patch_tool_response_page_use_metadata(
                        message,
                        response_hint,
                        browser_url=hint_browser_url,
                        instance_root=self.instance_root,
                    )
                elif response_hint:
                    message = patch_tool_response_hint(message, response_hint)
                write_json_line(message, self.output_lock)
        finally:
            self.note_exited(upstream)


def run_proxy(args: argparse.Namespace, passthrough_args: list[str], instance_root: str | None = None) -> int:
    output_lock = threading.Lock()
    manager = UpstreamManager(
        args=args,
        passthrough_args=passthrough_args,
        instance_root=instance_root,
        output_lock=output_lock,
    )

    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                try:
                    manager.forward_raw_if_started(raw_line)
                except RuntimeError as exc:
                    print(str(exc), file=sys.stderr)
                    return 1
                continue
            if not isinstance(message, dict):
                continue

            method = message.get("method")
            if method == "initialize" and is_jsonrpc_request(message):
                manager.set_client_initialize_params(message.get("params"))
                write_json_line(initialize_response(message), output_lock)
                continue
            if method == "notifications/initialized":
                continue
            if method == "tools/list" and is_jsonrpc_request(message):
                write_json_line(tools_list_response(message), output_lock)
                continue
            if method in FOCUS_METHODS and is_jsonrpc_request(message):
                write_json_line(rpc_error_response(message, focus_block_text(str(method))), output_lock)
                continue
            if method != "tools/call":
                if is_jsonrpc_request(message):
                    write_json_line(rpc_error_response(message, "Unsupported chrome-devtools-cockpit method."), output_lock)
                continue

            try:
                active_browser_url = acquire_browser_url()
            except RuntimeError as exc:
                if is_jsonrpc_request(message):
                    write_json_line(tool_error_response(message, str(exc)), output_lock)
                    continue
                return 1
            outbound, local_response, response_hint = mutate_client_message(
                message,
                active_browser_url,
                instance_root=instance_root,
            )
            if local_response is not None:
                write_json_line(local_response, output_lock)
                continue
            if outbound is None:
                continue
            try:
                manager.ensure_started(active_browser_url)
                manager.ensure_initialized()
                manager.send_request(outbound, response_hint)
            except RuntimeError as exc:
                if is_jsonrpc_request(message):
                    write_json_line(
                        tool_error_response(message, str(exc)),
                        output_lock,
                    )
                    continue
                return 1
    except BrokenPipeError:
        return 1
    finally:
        manager.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    args, passthrough_args = parse_args(sys.argv[1:] if argv is None else argv)
    apply_broker_socket_arg(args)
    return run_proxy(args, passthrough_args, args.instance_root)


if __name__ == "__main__":
    raise SystemExit(main())
