#!/usr/bin/env python3
"""BuddySwitch stdio proxy for Chrome DevTools MCP focus control."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
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


DEFAULT_UPSTREAM_COMMAND = "npx chrome-devtools-mcp@1.1.1"
UPSTREAM_EXIT_GRACE_SECONDS = 2.0
FOCUS_METHODS = {"Page.bringToFront", "Target.activateTarget"}


def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="Proxy Chrome DevTools MCP through BuddySwitch focus controls.")
    parser.add_argument("--browser-url", required=True, help="Chrome remote debugging browser URL.")
    parser.add_argument(
        "--upstream-command",
        default=os.environ.get("BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_COMMAND", DEFAULT_UPSTREAM_COMMAND),
        help="Command used to start the upstream Chrome DevTools MCP server.",
    )
    return parser.parse_known_args(argv)


def build_upstream_argv(args: argparse.Namespace, passthrough_args: list[str]) -> list[str]:
    upstream = shlex.split(args.upstream_command)
    if not upstream:
        raise ValueError("--upstream-command must not be empty")
    return upstream + passthrough_args + [f"--browser-url={args.browser_url}"]


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


def focus_block_text(method: str) -> str:
    return (
        f"BuddySwitch blocked {method} because chrome-devtools-cockpit runs in "
        "non-activating mode. Use a user-visible handoff before requesting browser focus."
    )


def mutate_tool_call(
    message: dict[str, Any],
    browser_url: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
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
                return None, tool_success_response(
                    message,
                    f"Reused existing browser page {target_id}. No new page was opened.",
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
        return rewritten, None, None

    return message, None, None


def mutate_client_message(
    message: dict[str, Any],
    browser_url: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    method = message.get("method")
    if method in FOCUS_METHODS and is_jsonrpc_request(message):
        return None, rpc_error_response(message, focus_block_text(str(method))), None
    if method == "tools/call":
        return mutate_tool_call(message, browser_url)
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


def patch_tool_response_new_page_metadata(
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
    result = message.get("result")
    if not isinstance(result, dict) or result.get("isError") is True:
        return patched
    before_targets = metadata.get("before_targets")
    target_url = metadata.get("target_url")
    if not isinstance(before_targets, list) or not isinstance(target_url, str) or not target_url:
        return patch_tool_response_hint(patched, "Browser page TTL not registered.")
    try:
        after_targets = browser_lifecycle.read_page_targets(browser_url)
        target_id = browser_lifecycle.new_page_target_id(before_targets, after_targets)
        if target_id is None:
            return patch_tool_response_hint(patched, "Browser page TTL not registered.")
        if not isinstance(instance_root, str) or not instance_root.strip():
            return patch_tool_response_hint(patched, "Browser page TTL not registered.")
        ttl = browser_lifecycle.register_browser_page_ttl(
            instance_root=Path(instance_root.strip()),
            target_id=target_id,
            target_url=target_url,
        )
    except Exception:
        return patch_tool_response_hint(patched, "Browser page TTL not registered.")
    ttl_seconds = ttl.get("ttl_seconds") if isinstance(ttl, dict) else None
    if not isinstance(ttl_seconds, int):
        ttl_seconds = browser_lifecycle.BROWSER_PAGE_TTL_SECONDS
    return patch_tool_response_hint(patched, f"Browser page TTL: {ttl_seconds}s.")


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


def upstream_to_client(
    upstream: subprocess.Popen[str],
    output_lock: threading.Lock,
    tools_list_ids: set[Any],
    pending_hints: dict[Any, Any],
    ids_lock: threading.Lock,
    browser_url: str,
    instance_root: str | None,
) -> None:
    assert upstream.stdout is not None
    for raw_line in upstream.stdout:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            write_raw_line(raw_line, output_lock)
            continue
        if not isinstance(message, dict):
            write_raw_line(raw_line, output_lock)
            continue
        message_id = message.get("id")
        should_patch = False
        response_hint: Any | None = None
        with ids_lock:
            if message_id in tools_list_ids:
                tools_list_ids.discard(message_id)
                should_patch = True
            response_hint = pending_hints.pop(message_id, None)
        if should_patch:
            message = patch_tool_list_message(message)
        if isinstance(response_hint, dict):
            message = patch_tool_response_new_page_metadata(
                message,
                response_hint,
                browser_url=browser_url,
                instance_root=instance_root,
            )
        elif response_hint:
            message = patch_tool_response_hint(message, response_hint)
        write_json_line(message, output_lock)


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


def run_proxy(upstream_argv: list[str], browser_url: str) -> int:
    try:
        upstream = subprocess.Popen(
            upstream_argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        print(f"failed to start upstream chrome-devtools-mcp: {exc}", file=sys.stderr)
        return 127

    output_lock = threading.Lock()
    ids_lock = threading.Lock()
    tools_list_ids: set[Any] = set()
    pending_hints: dict[Any, Any] = {}
    relay = threading.Thread(
        target=upstream_to_client,
        args=(
            upstream,
            output_lock,
            tools_list_ids,
            pending_hints,
            ids_lock,
            browser_url,
            os.environ.get("BUDDYSWITCH_INSTANCE_ROOT"),
        ),
        daemon=True,
    )
    relay.start()

    assert upstream.stdin is not None
    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                upstream.stdin.write(raw_line)
                upstream.stdin.flush()
                continue
            if not isinstance(message, dict):
                upstream.stdin.write(raw_line)
                upstream.stdin.flush()
                continue

            if message.get("method") == "tools/list" and is_jsonrpc_request(message):
                with ids_lock:
                    tools_list_ids.add(message.get("id"))

            outbound, local_response, response_hint = mutate_client_message(message, browser_url)
            if local_response is not None:
                write_json_line(local_response, output_lock)
                continue
            if outbound is None:
                continue
            if response_hint and is_jsonrpc_request(outbound):
                with ids_lock:
                    pending_hints[outbound.get("id")] = response_hint
            upstream.stdin.write(json.dumps(outbound, ensure_ascii=True, separators=(",", ":")) + "\n")
            upstream.stdin.flush()
    except BrokenPipeError:
        return 1
    finally:
        exit_code = close_upstream(upstream)
        relay.join(timeout=UPSTREAM_EXIT_GRACE_SECONDS)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args, passthrough_args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        upstream_argv = build_upstream_argv(args, passthrough_args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return run_proxy(upstream_argv, args.browser_url)


if __name__ == "__main__":
    raise SystemExit(main())
