#!/usr/bin/env python3
"""BuddySwitch stdio proxy for Chrome DevTools MCP focus control."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shlex
import subprocess
import sys
import threading
from typing import Any


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


def mutate_tool_call(message: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    params = message.get("params")
    if not isinstance(params, dict):
        return message, None
    name = params.get("name")
    arguments = params.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return message, None

    if name == "new_page":
        if "isolatedContext" in arguments:
            return None, tool_error_response(
                message,
                "BuddySwitch blocked new_page with isolatedContext because upstream Chrome DevTools MCP "
                "does not apply background creation to isolated browser contexts. This keeps the "
                "chrome-devtools-cockpit path non-activating.",
            )
        rewritten = copy.deepcopy(message)
        rewritten_params = rewritten.setdefault("params", {})
        rewritten_arguments = dict(arguments)
        rewritten_arguments["background"] = True
        rewritten_params["arguments"] = rewritten_arguments
        return rewritten, None

    if name == "select_page":
        rewritten = copy.deepcopy(message)
        rewritten_params = rewritten.setdefault("params", {})
        rewritten_arguments = dict(arguments)
        rewritten_arguments["bringToFront"] = False
        rewritten_params["arguments"] = rewritten_arguments
        return rewritten, None

    return message, None


def mutate_client_message(message: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    method = message.get("method")
    if method in FOCUS_METHODS and is_jsonrpc_request(message):
        return None, rpc_error_response(message, focus_block_text(str(method)))
    if method == "tools/call":
        return mutate_tool_call(message)
    return message, None


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
    ids_lock: threading.Lock,
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
        with ids_lock:
            if message_id in tools_list_ids:
                tools_list_ids.discard(message_id)
                should_patch = True
        if should_patch:
            message = patch_tool_list_message(message)
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


def run_proxy(upstream_argv: list[str]) -> int:
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
    relay = threading.Thread(
        target=upstream_to_client,
        args=(upstream, output_lock, tools_list_ids, ids_lock),
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

            outbound, local_response = mutate_client_message(message)
            if local_response is not None:
                write_json_line(local_response, output_lock)
                continue
            if outbound is None:
                continue
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
    return run_proxy(upstream_argv)


if __name__ == "__main__":
    raise SystemExit(main())
