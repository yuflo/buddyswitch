#!/usr/bin/env python3
"""BuddySwitch stdio proxy for Chrome DevTools MCP focus control."""

from __future__ import annotations

import argparse
import copy
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
from env.cdp_browser_session import BROWSER_PAGE_LIMIT_BLOCK_TEXT, evaluate_page_open_gate  # noqa: E402


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
    return parser.parse_known_args(argv)


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


def read_instance_payload(instance_root: str | None) -> dict[str, Any]:
    root = _instance_root_path(instance_root)
    if root is None:
        return {}
    try:
        payload = json.loads((root / "instance.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def browser_url_from_instance(instance_root: str | None) -> str | None:
    payload = read_instance_payload(instance_root)
    port = payload.get("browser_port")
    if isinstance(port, bool) or not isinstance(port, int) or port < 1 or port > 65535:
        return None
    return f"http://127.0.0.1:{port}"


def ensure_browser_url(instance_root: str | None) -> str | None:
    root = _instance_root_path(instance_root)
    if root is None:
        return None
    payload = read_instance_payload(instance_root)
    actor_id = payload.get("actor_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        return browser_url_from_instance(instance_root)
    override = os.environ.get("BUDDYSWITCH_BROWSER_COCKPIT_ENSURE_COMMAND")
    if override:
        command = shlex.split(override) + [str(root)]
    else:
        command = [str(ROOT / "buddyswitch-codex"), "env", "browser", "ensure", "--instance", actor_id.strip()]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=30.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"browser ensure failed: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit status {completed.returncode}"
        raise RuntimeError(f"browser ensure failed: {detail}")
    return browser_url_from_instance(instance_root)


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


def _lifecycle_error_text(action: str, exc: BaseException, close_result: dict[str, Any] | None = None) -> str:
    text = f"Browser page lifecycle registration failed during {action}: {exc}"
    if close_result is not None:
        text = f"{text} Closed browser target: {json.dumps(close_result, ensure_ascii=True)}"
    return text


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
        target_url = arguments.get("url")
        hint: str | None = None
        if isinstance(target_url, str) and target_url.strip():
            gate = evaluate_page_open_gate(browser_url, target_url.strip())
            if gate.kind == "verification_failed":
                return None, tool_error_response(
                    message,
                    gate.message or "Browser page-count verification failed.",
                ), None
            if gate.kind == "block":
                return None, tool_error_response(message, BROWSER_PAGE_LIMIT_BLOCK_TEXT), None
            if gate.kind == "reuse":
                target_id = gate.target_id or "<unknown>"
                root = _instance_root_path(instance_root)
                assert root is not None
                try:
                    idle_hint = _refresh_current_idle_hint(
                        root=root,
                        target_id=target_id,
                        target_url=target_url.strip(),
                    )
                except Exception as exc:
                    return None, tool_error_response(message, _lifecycle_error_text("new_page reuse", exc)), None
                suffix = f" {idle_hint}" if idle_hint else ""
                return None, tool_success_response(
                    message,
                    f"Reused existing browser page {target_id}. No new page was opened.{suffix}",
                ), None
            hint = gate.hint_text()
            try:
                before_targets = browser_lifecycle.read_page_targets(browser_url)
            except browser_lifecycle.BrowserLifecycleError:
                before_targets = None
        rewritten = copy.deepcopy(message)
        rewritten_params = rewritten.setdefault("params", {})
        rewritten_arguments = dict(arguments)
        rewritten_arguments["background"] = True
        rewritten_params["arguments"] = rewritten_arguments
        if isinstance(target_url, str) and target_url.strip():
            return rewritten, None, {
                "kind": "new_page",
                "target_url": target_url.strip(),
                "before_targets": before_targets,
                "page_hint": hint,
            }
        return rewritten, None, hint

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
        if name == "new_page":
            tool["description"] = append_description(
                tool.get("description"),
                "BuddySwitch proxy forces background:true so new tabs are opened through the non-activating cockpit path.",
            )
            patch_schema_property(
                tool,
                "background",
                "BuddySwitch forces this to true for chrome-devtools-cockpit.",
            )
            patch_schema_property(
                tool,
                "isolatedContext",
                "BuddySwitch blocks this parameter because upstream does not apply background creation to this path.",
            )
        elif name == "select_page":
            tool["description"] = append_description(
                tool.get("description"),
                "BuddySwitch proxy forces bringToFront:false for non-activating page selection.",
            )
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


def _new_page_target_ids(before_targets: list[Any], after_targets: list[Any]) -> list[str]:
    before_ids: set[str] = set()
    for target in before_targets:
        if not isinstance(target, dict) or target.get("type") != "page":
            continue
        for key in ("id", "targetId"):
            target_id = target.get(key)
            if isinstance(target_id, str) and target_id.strip():
                before_ids.add(target_id.strip())

    new_ids: list[str] = []
    for target in after_targets:
        if not isinstance(target, dict) or target.get("type") != "page":
            continue
        for key in ("id", "targetId"):
            target_id = target.get(key)
            if isinstance(target_id, str) and target_id.strip() and target_id.strip() not in before_ids:
                new_ids.append(target_id.strip())
    return new_ids


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
    if kind != "new_page":
        return patched
    before_targets = metadata.get("before_targets")
    target_url = metadata.get("target_url")
    if not isinstance(before_targets, list) or not isinstance(target_url, str) or not target_url:
        return patched
    target_id: str | None = None
    try:
        after_targets = browser_lifecycle.read_page_targets(browser_url)
        target_id = browser_lifecycle.new_page_target_id(before_targets, after_targets)
        if target_id is None:
            if not _new_page_target_ids(before_targets, after_targets):
                return patched
            return tool_error_response(
                message,
                _lifecycle_error_text(
                    "new_page",
                    browser_lifecycle.BrowserLifecycleError(
                        "created browser target was not uniquely resolved after upstream response"
                    ),
                ),
            )
        hint = _refresh_current_idle_hint(
            root=root,
            target_id=target_id,
            target_url=target_url,
        )
    except Exception as exc:
        close_result: dict[str, Any] | None = None
        if target_id:
            try:
                close_result = browser_lifecycle.close_page_target(browser_url, target_id)
            except Exception as close_exc:
                return tool_error_response(
                    message,
                    f"{_lifecycle_error_text('new_page', exc)} Failed to close browser target {target_id}: {close_exc}",
                )
        return tool_error_response(message, _lifecycle_error_text("new_page", exc, close_result))
    return patch_tool_response_hint(patched, hint)


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
                active_browser_url = ensure_browser_url(instance_root) or ""
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
    return run_proxy(args, passthrough_args, args.instance_root)


if __name__ == "__main__":
    raise SystemExit(main())
