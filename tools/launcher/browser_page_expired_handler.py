#!/usr/bin/env python3
"""Browser-owned daemon handler for expired browser page TTL schedules."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import select
import shlex
import signal
import subprocess
import sys
import time
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
DEFAULT_UPSTREAM_COMMAND = "npx chrome-devtools-mcp@1.1.1"
MCP_TOOL_TIMEOUT_SECONDS = 20.0


def _context_identity_route(context: Any) -> dict[str, str]:
    return {
        "identity_id": str(getattr(context, "actor_id", "")).strip(),
        "role_id": str(getattr(context, "role", "")).strip(),
    }


def _payload(trigger: Any) -> dict[str, Any]:
    payload = getattr(trigger, "payload", None)
    if not isinstance(payload, dict):
        raise ValueError("browser page expiry trigger payload must be an object")
    page_id = payload.get("page_id")
    if isinstance(page_id, bool) or page_id is None:
        raise ValueError("page_id is required")
    if isinstance(page_id, str):
        page_id = page_id.strip()
        if not page_id:
            raise ValueError("page_id is required")
    elif not isinstance(page_id, int):
        raise ValueError("page_id must be a string or integer")
    return {
        "page_id": page_id,
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
    payload = _fresh_instance_payload(context)
    if payload is None:
        cached_payload = getattr(context, "instance_payload", None)
        if not isinstance(cached_payload, dict):
            return None
        payload = cached_payload
    port = payload.get("browser_port")
    if isinstance(port, bool) or not isinstance(port, int) or port < 1 or port > 65535:
        return None
    return f"http://127.0.0.1:{port}"


def _fresh_instance_payload(context: Any) -> dict[str, Any] | None:
    instance_json = getattr(context, "instance_json", None)
    if instance_json is None:
        return None
    try:
        payload = json.loads(Path(instance_json).read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


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


def _schedule_release_if_empty(instance_root: Path, state: dict[str, Any]) -> None:
    pages = state.get("pages")
    if isinstance(pages, dict) and not pages:
        browser_lifecycle.schedule_browser_cockpit_release(instance_root=instance_root, reason="page_idle_empty")


def _forget_tracked_page(instance_root: Path, page_id: object) -> dict[str, Any] | None:
    before = browser_lifecycle._read_page_idle_state(instance_root)
    pages = before.get("pages")
    normalized_page_id = str(page_id).strip() if not isinstance(page_id, bool) else ""
    if not isinstance(pages, dict) or normalized_page_id not in pages:
        return None
    return browser_lifecycle.forget_page_idle_page(instance_root=instance_root, page_id=normalized_page_id)


def _tool_response_text(message: dict[str, Any]) -> str:
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


def _write_mcp_message(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if proc.stdin is None:
        raise browser_lifecycle.BrowserLifecycleError("upstream chrome-devtools-mcp stdin is unavailable")
    try:
        proc.stdin.write(json.dumps(message, ensure_ascii=True, separators=(",", ":")) + "\n")
        proc.stdin.flush()
    except OSError as exc:
        raise browser_lifecycle.BrowserLifecycleError(f"failed to write to upstream chrome-devtools-mcp: {exc}") from exc


def _read_mcp_response(
    proc: subprocess.Popen[str],
    response_id: str,
    *,
    operation: str,
    deadline: float,
) -> dict[str, Any]:
    if proc.stdout is None:
        raise browser_lifecycle.BrowserLifecycleError("upstream chrome-devtools-mcp stdout is unavailable")
    while time.monotonic() < deadline:
        remaining = max(0.0, min(0.25, deadline - time.monotonic()))
        ready, _, _ = select.select([proc.stdout], [], [], remaining)
        if not ready:
            if proc.poll() is not None:
                break
            continue
        raw_line = proc.stdout.readline()
        if not raw_line:
            if proc.poll() is not None:
                break
            continue
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and message.get("id") == response_id:
            return message
    if time.monotonic() >= deadline:
        raise browser_lifecycle.BrowserLifecycleError(f"upstream chrome-devtools-mcp timed out during {operation}")
    raise browser_lifecycle.BrowserLifecycleError(f"upstream chrome-devtools-mcp returned no {operation} response")


def _stop_mcp_process(proc: subprocess.Popen[str]) -> None:
    try:
        if proc.stdin is not None and not proc.stdin.closed:
            proc.stdin.close()
    except OSError:
        pass
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
        proc.wait(timeout=2.0)


class McpToolSession:
    def __init__(self, browser_endpoint: str) -> None:
        upstream = shlex.split(os.environ.get("BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_COMMAND", DEFAULT_UPSTREAM_COMMAND))
        if not upstream:
            raise browser_lifecycle.BrowserLifecycleError("upstream chrome-devtools-mcp command is empty")
        argv = upstream + [f"--browser-url={browser_endpoint}"]
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        self._closed = False
        self._call_count = 0
        try:
            self._initialize()
        except Exception:
            self.close()
            raise

    def __enter__(self) -> "McpToolSession":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def _deadline(self) -> float:
        return time.monotonic() + MCP_TOOL_TIMEOUT_SECONDS

    def _initialize(self) -> None:
        initialize_id = "buddyswitch.browser_page_expired.initialize"
        _write_mcp_message(
            self._proc,
            {
                "jsonrpc": "2.0",
                "id": initialize_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "buddyswitch-browser-page-expired", "version": "1.0.0"},
                },
            },
        )
        initialize_response = _read_mcp_response(
            self._proc,
            initialize_id,
            operation="initialize",
            deadline=self._deadline(),
        )
        if isinstance(initialize_response.get("error"), dict):
            raise browser_lifecycle.BrowserLifecycleError(f"upstream chrome-devtools-mcp initialize failed: {initialize_response['error']}")
        _write_mcp_message(self._proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self._call_count += 1
        call_id = f"buddyswitch.browser_page_expired.tool.{self._call_count}"
        _write_mcp_message(
            self._proc,
            {
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        message = _read_mcp_response(self._proc, call_id, operation=name, deadline=self._deadline())
        if isinstance(message.get("error"), dict):
            raise browser_lifecycle.BrowserLifecycleError(f"{name} failed: {message['error']}")
        result = message.get("result")
        if isinstance(result, dict) and result.get("isError") is True:
            raise browser_lifecycle.BrowserLifecycleError(_tool_response_text(message) or f"{name} failed")
        return message

    def list_pages(self) -> list[dict[str, Any]]:
        return _pages_from_mcp_response(self.call_tool("list_pages", {}))

    def close_page(self, page_id: object) -> dict[str, Any]:
        self.call_tool("close_page", {"pageId": _coerce_close_page_id(page_id)})
        return {"status": "closed", "page_id": page_id}

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _stop_mcp_process(self._proc)


def open_mcp_session(browser_endpoint: str) -> McpToolSession:
    return McpToolSession(browser_endpoint)


def _run_mcp_tool(browser_endpoint: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    with open_mcp_session(browser_endpoint) as session:
        return session.call_tool(name, arguments)


def _coerce_close_page_id(page_id: object) -> object:
    if isinstance(page_id, str) and page_id.isdigit():
        return int(page_id)
    return page_id


def _page_id_value(page: dict[str, Any]) -> object:
    for key in ("pageId", "page_id", "id"):
        value = page.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (str, int)) and str(value).strip():
            return value
    return None


def _page_field(page: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = page.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _pages_from_structured(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("pages", "pageList", "items"):
            pages = _pages_from_structured(value.get(key))
            if pages:
                return pages
    return []


def _pages_from_text(text: str) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith(("pages", "# pages")):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = None
        structured_pages = _pages_from_structured(payload)
        if structured_pages:
            pages.extend(structured_pages)
            continue
        match = re.match(r"^(?:[-*]\s*)?(?P<page_id>[A-Za-z0-9_.:-]+)\s*[:.)-]\s*(?P<body>.+)$", line)
        if not match:
            continue
        body = match.group("body").replace("[selected]", "").strip()
        url_match = re.search(r"(https?://\S+|about:blank)", body)
        url = url_match.group(1).rstrip(".,;") if url_match else None
        title = body
        if url:
            title = title.replace(url, "").strip(" -")
        page_id: object = match.group("page_id")
        if isinstance(page_id, str) and page_id.isdigit():
            page_id = int(page_id)
        page: dict[str, Any] = {"pageId": page_id}
        if url:
            page["url"] = url
        if title:
            page["title"] = title
        pages.append(page)
    return pages


def _pages_from_mcp_response(message: dict[str, Any]) -> list[dict[str, Any]]:
    result = message.get("result")
    pages = _pages_from_structured(result)
    if pages:
        return pages
    return _pages_from_text(_tool_response_text(message))


def _recorded_page_state(instance_root: Path, page_id: object) -> dict[str, Any] | None:
    state = browser_lifecycle._read_page_idle_state(instance_root)
    pages = state.get("pages")
    if not isinstance(pages, dict):
        return None
    value = pages.get(str(page_id))
    return value if isinstance(value, dict) else None


def _recorded_identity_candidates(recorded: dict[str, Any], pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recorded_url = _page_field(recorded, "url", "target_url")
    if recorded_url is None:
        return []
    recorded_title = _page_field(recorded, "title")
    candidates: list[dict[str, Any]] = []
    for page in pages:
        observed_url = _page_field(page, "url", "target_url")
        if observed_url != recorded_url:
            continue
        observed_title = _page_field(page, "title")
        if recorded_title and observed_title and observed_title != recorded_title:
            continue
        candidates.append(page)
    return candidates


def _resolve_recorded_page(recorded: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, Any] | None:
    recorded_url = _page_field(recorded, "url", "target_url")
    if recorded_url is None:
        raise browser_lifecycle.BrowserLifecycleError("recorded browser page URL is missing; cannot safely resolve MCP page")
    candidates = _recorded_identity_candidates(recorded, pages)
    if not candidates:
        return None
    if len(candidates) > 1:
        raise browser_lifecycle.BrowserLifecycleError(f"multiple MCP pages match recorded browser page URL: {recorded_url}")
    return candidates[0]


def _recorded_page_visible(recorded: dict[str, Any], pages: list[dict[str, Any]]) -> bool:
    return bool(_recorded_identity_candidates(recorded, pages))


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
            local_route = _context_identity_route(context)
            target_route = {
                "identity_id": str(getattr(trigger, "target_identity_id", "")).strip(),
                "role_id": str(getattr(trigger, "target_role_id", "")).strip(),
            }
            if target_route != local_route:
                raise PermissionError("wrong target identity for browser page expiry trigger")
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
        page_id = payload["page_id"]
        if root is not None:
            current_page_id = browser_lifecycle.current_page_id(root)
            selected_page_id = browser_lifecycle.selected_page_id(root)
            if page_id in {current_page_id, selected_page_id} and _parent_turn_is_running(runtime):
                browser_lifecycle.refresh_page_idle(instance_root=root, page_id=page_id)
                return daemon_core.HandlerResult.handled()
            if browser_lifecycle.page_idle_expiry_after_due_at(
                instance_root=root,
                page_id=page_id,
                due_at=due_at,
            ):
                return daemon_core.HandlerResult.handled()
        return self._auto_close(context, payload)

    def _auto_close(self, context: Any, payload: dict[str, Any]) -> daemon_core.HandlerResult:
        browser_endpoint = _browser_endpoint(context)
        root = _instance_root(context)
        if browser_endpoint is None:
            if root is not None:
                state = _forget_tracked_page(root, payload["page_id"])
                if state is not None:
                    _schedule_release_if_empty(root, state)
            return daemon_core.HandlerResult.handled()
        page_id = payload["page_id"]
        if root is None:
            return daemon_core.HandlerResult.failed("instance_root is required for browser page expiry cleanup")
        recorded_page = _recorded_page_state(root, page_id)
        if recorded_page is None:
            return daemon_core.HandlerResult.handled()
        try:
            with open_mcp_session(browser_endpoint) as session:
                mcp_pages = session.list_pages()
                resolved_page = _resolve_recorded_page(recorded_page, mcp_pages)
                if resolved_page is None:
                    state = _forget_tracked_page(root, page_id)
                    if state is not None:
                        _schedule_release_if_empty(root, state)
                    return daemon_core.HandlerResult.handled()
                close_page_id = _page_id_value(resolved_page)
                if close_page_id is None:
                    raise browser_lifecycle.BrowserLifecycleError("resolved MCP page is missing pageId")
                session.close_page(close_page_id)
                verified_pages = session.list_pages()
                if _recorded_page_visible(recorded_page, verified_pages):
                    recorded_url = _page_field(recorded_page, "url", "target_url") or "<unknown>"
                    return daemon_core.HandlerResult.failed(f"browser page still visible after MCP close: {recorded_url}")
        except browser_lifecycle.BrowserLifecycleError as exc:
            message = str(exc)
            if _is_stale_browser_error(message):
                if root is not None:
                    state = _forget_tracked_page(root, page_id)
                    if state is not None:
                        _schedule_release_if_empty(root, state)
                return daemon_core.HandlerResult.handled()
            return daemon_core.HandlerResult.failed(message)
        if root is not None:
            state = _forget_tracked_page(root, page_id)
            if state is not None:
                _schedule_release_if_empty(root, state)
        return daemon_core.HandlerResult.handled()


if __name__ == "__main__":
    raise SystemExit("browser_page_expired_handler is not a standalone command")
