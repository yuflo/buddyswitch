#!/usr/bin/env python3
"""Skill-facing CLI for broker-routed runless env tool operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_kernel.client import RuntimeBrokerError, broker_unavailable_feedback, request_runtime_broker


def _error_payload(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {"code": code, "message": message},
    }
    if not extra:
        return payload
    top_level = {
        "tool",
        "action",
        "permission_boundary",
        "allowed_next_actions",
        "allowed_next_action_options",
        "command_hint",
        "stop_condition",
        "request_id",
        "retriable",
        "retry_after_ms",
        "feedback",
        "broker_status",
    }
    for key, value in extra.items():
        if key in {"code", "message"}:
            continue
        if key in top_level:
            payload[key] = value
        else:
            payload["error"][key] = value
    return payload


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"payload file must contain a JSON object: {path}")
    return payload


def _operation_to_action(operation: str) -> str:
    return operation.replace("-", "_")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call broker-routed BuddySwitch env operations.")
    sub = parser.add_subparsers(dest="resource", required=True)

    task = sub.add_parser("task", help="Task env tool operations")
    task_sub = task.add_subparsers(dest="operation", required=True)
    create = task_sub.add_parser("create", help="Create active-buddy task")
    create.add_argument("--payload", required=True, type=Path)
    task_sub.add_parser("list", help="List active-buddy tasks")
    get = task_sub.add_parser("get", help="Get active-buddy task by id")
    get.add_argument("--task-id", required=True)
    update = task_sub.add_parser("update", help="Update active-buddy task fields")
    update.add_argument("--payload", required=True, type=Path)
    archive = task_sub.add_parser("archive", help="Archive active-buddy task")
    archive.add_argument("--task-id", required=True)

    track = sub.add_parser("track", help="Track env tool operations")
    track_sub = track.add_subparsers(dest="operation", required=True)
    create_track = track_sub.add_parser("create", help="Create PM-owned track")
    create_track.add_argument("--payload", required=True, type=Path)
    track_sub.add_parser("list", help="List readable tracks")
    get_track = track_sub.add_parser("get", help="Get track by id")
    get_track.add_argument("--track-id", required=True)
    join_track = track_sub.add_parser("join", help="Create or reuse active-buddy task linked to track")
    join_track.add_argument("--track-id", required=True)
    join_track.add_argument("--task-id")
    update_track = track_sub.add_parser("update", help="Update PM-owned track metadata")
    update_track.add_argument("--payload", required=True, type=Path)
    advance_track = track_sub.add_parser("advance", help="Advance PM-owned track lifecycle")
    advance_track.add_argument("--payload", required=True, type=Path)
    archive_track = track_sub.add_parser("archive", help="Archive PM-owned track")
    archive_track.add_argument("--track-id", required=True)
    attach_task = track_sub.add_parser("attach-task", help="Attach active-buddy task to track")
    attach_task.add_argument("--track-id", required=True)
    attach_task.add_argument("--task-id", required=True)
    detach_task = track_sub.add_parser("detach-task", help="Detach active-buddy task from track")
    detach_task.add_argument("--track-id", required=True)
    detach_task.add_argument("--task-id", required=True)

    artifact = sub.add_parser("artifact", help="Artifact env tool operations")
    artifact_sub = artifact.add_subparsers(dest="operation", required=True)
    artifact_list = artifact_sub.add_parser("list", help="List track artifact summaries")
    artifact_list.add_argument("--track-id", required=True)
    get_artifact = artifact_sub.add_parser("get", help="Get readable artifact by id")
    get_artifact.add_argument("--artifact-id", required=True)
    validate_artifact = artifact_sub.add_parser("validate-payload", help="Validate artifact revision payload")
    validate_artifact.add_argument("--payload", required=True, type=Path)
    create_artifact = artifact_sub.add_parser("create-revision", help="Create a new artifact revision")
    create_artifact.add_argument("--payload", required=True, type=Path)
    update_artifact = artifact_sub.add_parser("update-metadata", help="Update artifact title/summary/source refs")
    update_artifact.add_argument("--payload", required=True, type=Path)

    context_parser = sub.add_parser("context", help="Context env operations")
    context_sub = context_parser.add_subparsers(dest="operation", required=True)
    context_get = context_sub.add_parser("get", help="Get runless context sections")
    context_get.add_argument("--track-id")
    context_get.add_argument("--task-id")
    context_get.add_argument("--limit", type=int)
    context_summarize = context_sub.add_parser("summarize", help="Summarize runless context")
    context_summarize.add_argument("--track-id")
    context_summarize.add_argument("--task-id")
    context_summarize.add_argument("--limit", type=int)
    context_sub.add_parser("list-sources", help="List context source descriptions")

    handoff = sub.add_parser("handoff", help="Handoff validation env operations")
    handoff_sub = handoff.add_subparsers(dest="operation", required=True)
    list_handoff = handoff_sub.add_parser("list", help="List handoff records")
    list_handoff.add_argument("--track-id")
    list_handoff.add_argument("--target-buddy")
    list_handoff.add_argument("--status")
    list_handoff.add_argument("--limit", type=int)
    validate_handoff = handoff_sub.add_parser("validate", help="Validate a handoff payload")
    validate_handoff.add_argument("--payload", required=True, type=Path)
    create_handoff = handoff_sub.add_parser("create", help="Create an explicit handoff record")
    create_handoff.add_argument("--payload", required=True, type=Path)

    buddybox = sub.add_parser("buddybox", help="Buddybox env operations")
    buddybox_sub = buddybox.add_subparsers(dest="operation", required=True)
    buddybox_sub.add_parser("desc", help="Describe active buddy private local workspace")
    buddybox_list = buddybox_sub.add_parser("list", help="List buddybox files")
    buddybox_list.add_argument("--logical-name")
    buddybox_list.add_argument("--recursive", action="store_true")
    buddybox_list.add_argument("--limit", type=int)
    buddybox_read = buddybox_sub.add_parser("read", help="Read buddybox file")
    buddybox_read.add_argument("--logical-name", required=True)
    buddybox_read.add_argument("--encoding")
    buddybox_write = buddybox_sub.add_parser("write", help="Write buddybox file")
    buddybox_write.add_argument("--payload", required=True, type=Path)
    buddybox_delete = buddybox_sub.add_parser("delete", help="Delete buddybox file")
    buddybox_delete.add_argument("--logical-name", required=True)

    evidence = sub.add_parser("evidence", help="Evidence env operations")
    evidence_sub = evidence.add_subparsers(dest="operation", required=True)
    issue_browser = evidence_sub.add_parser("issue-browser", help="Issue browser preflight evidence")
    issue_browser.add_argument("--target-type", required=True)
    issue_browser.add_argument("--target-id", required=True)
    issue_browser.add_argument("--mode")
    approve_downgrade = evidence_sub.add_parser("approve-downgrade", help="Issue downgrade approval token")
    approve_downgrade.add_argument("--target-type", required=True)
    approve_downgrade.add_argument("--target-id", required=True)
    approve_downgrade.add_argument("--reason", required=True)

    search = sub.add_parser(
        "search",
        help="Search env operations",
        description="Search actions use --query (request/open-browser), --backend (request), and optional --engine.",
    )
    search_sub = search.add_subparsers(dest="operation", required=True)
    status = search_sub.add_parser("status", help="Show runtime search configuration")
    status.add_argument("--query")
    request = search_sub.add_parser("request", help="Issue search request")
    request.add_argument("--query", required=True)
    request.add_argument("--backend", required=True, choices=["browser", "search_api"])
    request.add_argument("--engine", choices=["google", "web", "reddit", "x"])
    open_browser = search_sub.add_parser("open-browser", help="Open browser search URL")
    open_browser.add_argument("--query", required=True)
    open_browser.add_argument("--engine", choices=["google", "web", "reddit", "x"])

    return parser.parse_args()


def _context_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    if args.operation == "list-sources":
        return {}
    payload: dict[str, Any] = {}
    for field in ("track_id", "task_id", "limit"):
        value = getattr(args, field, None)
        if value is not None:
            payload[field] = value
    return payload


def _dispatch_env_tool(tool: str, action: str, args: dict[str, Any]) -> dict[str, Any]:
    params = {
        "tool": tool,
        "action": action,
        "args": args,
    }
    try:
        return request_runtime_broker("env.tool", params)
    except RuntimeBrokerError as exc:
        extra: dict[str, Any] = dict(exc.details)
        if exc.response and isinstance(exc.response, dict):
            for key, value in exc.response.items():
                if key in {"protocol", "request_id", "ok", "error"}:
                    continue
                extra[key] = value
        if exc.code == "E_RUNTIME_BROKER_UNAVAILABLE":
            unavailable = broker_unavailable_feedback()
            unavailable.update(extra)
            extra = unavailable
        return _error_payload(exc.code, exc.message, extra)


def _dispatch_task(args: argparse.Namespace) -> dict[str, Any]:
    action = _operation_to_action(args.operation)
    if args.operation in {"create", "update"}:
        payload = _load_json_object(args.payload)
        return _dispatch_env_tool("task", action, payload)
    if args.operation in {"get", "archive"}:
        return _dispatch_env_tool("task", action, {"task_id": args.task_id})
    return _dispatch_env_tool("task", action, {})


def _dispatch_track(args: argparse.Namespace) -> dict[str, Any]:
    action = _operation_to_action(args.operation)
    if args.operation in {"create", "update", "advance"}:
        payload = _load_json_object(args.payload)
        return _dispatch_env_tool("track", action, payload)
    if args.operation == "get":
        return _dispatch_env_tool("track", action, {"track_id": args.track_id})
    if args.operation == "join":
        payload: dict[str, Any] = {"track_id": args.track_id}
        if isinstance(args.task_id, str) and args.task_id.strip():
            payload["task_id"] = args.task_id.strip()
        return _dispatch_env_tool("track", action, payload)
    if args.operation == "archive":
        return _dispatch_env_tool("track", action, {"track_id": args.track_id})
    if args.operation in {"attach-task", "detach-task"}:
        return _dispatch_env_tool(
            "track",
            action,
            {"track_id": args.track_id, "task_id": args.task_id},
        )
    return _dispatch_env_tool("track", action, {})


def _dispatch_artifact(args: argparse.Namespace) -> dict[str, Any]:
    action = _operation_to_action(args.operation)
    if args.operation in {"validate-payload", "create-revision", "update-metadata"}:
        return _dispatch_env_tool("artifact", action, _load_json_object(args.payload))
    if args.operation == "list":
        return _dispatch_env_tool("artifact", action, {"track_id": args.track_id})
    if args.operation == "get":
        return _dispatch_env_tool("artifact", action, {"artifact_id": args.artifact_id})
    raise ValueError(f"unsupported artifact operation: {args.operation}")


def _dispatch_context(args: argparse.Namespace) -> dict[str, Any]:
    action = _operation_to_action(args.operation)
    return _dispatch_env_tool("context", action, _context_args_from_cli(args))


def _dispatch_handoff(args: argparse.Namespace) -> dict[str, Any]:
    action = _operation_to_action(args.operation)
    if args.operation in {"validate", "create"}:
        payload = _load_json_object(args.payload)
        return _dispatch_env_tool("handoff", action, payload)
    payload: dict[str, Any] = {}
    for field in ("track_id", "target_buddy", "status", "limit"):
        value = getattr(args, field, None)
        if value is not None:
            payload[field] = value
    return _dispatch_env_tool("handoff", action, payload)


def _dispatch_buddybox(args: argparse.Namespace) -> dict[str, Any]:
    action = _operation_to_action(args.operation)
    if args.operation == "desc":
        return _dispatch_env_tool("buddybox", action, {})
    if args.operation == "write":
        return _dispatch_env_tool("buddybox", action, _load_json_object(args.payload))
    if args.operation == "read":
        payload: dict[str, Any] = {"logical_name": args.logical_name}
        if isinstance(args.encoding, str) and args.encoding.strip():
            payload["encoding"] = args.encoding.strip()
        return _dispatch_env_tool("buddybox", action, payload)
    if args.operation == "delete":
        return _dispatch_env_tool("buddybox", action, {"logical_name": args.logical_name})
    payload = {}
    if isinstance(args.logical_name, str) and args.logical_name.strip():
        payload["logical_name"] = args.logical_name.strip()
    if args.recursive:
        payload["recursive"] = True
    if isinstance(args.limit, int):
        payload["limit"] = args.limit
    return _dispatch_env_tool("buddybox", action, payload)


def _dispatch_evidence(args: argparse.Namespace) -> dict[str, Any]:
    action = _operation_to_action(args.operation)
    payload: dict[str, Any] = {
        "target_type": args.target_type,
        "target_id": args.target_id,
    }
    if args.operation == "issue-browser":
        if isinstance(args.mode, str) and args.mode.strip():
            payload["mode"] = args.mode.strip()
    else:
        payload["reason"] = args.reason
    return _dispatch_env_tool("evidence", action, payload)


def _dispatch_search(args: argparse.Namespace) -> dict[str, Any]:
    action = _operation_to_action(args.operation)
    payload: dict[str, Any] = {}
    for field in ("query", "backend", "engine"):
        value = getattr(args, field, None)
        if value is not None:
            payload[field] = value
    return _dispatch_env_tool("search", action, payload)


def main() -> int:
    try:
        args = _parse_args()
        if args.resource == "task":
            payload = _dispatch_task(args)
        elif args.resource == "track":
            payload = _dispatch_track(args)
        elif args.resource == "artifact":
            payload = _dispatch_artifact(args)
        elif args.resource == "context":
            payload = _dispatch_context(args)
        elif args.resource == "handoff":
            payload = _dispatch_handoff(args)
        elif args.resource == "buddybox":
            payload = _dispatch_buddybox(args)
        elif args.resource == "evidence":
            payload = _dispatch_evidence(args)
        elif args.resource == "search":
            payload = _dispatch_search(args)
        else:
            payload = _error_payload("E_ENV_TOOL", f"unsupported resource: {args.resource}")
    except Exception as exc:
        payload = _error_payload("E_ENV_TOOL", str(exc))

    print(json.dumps(payload, ensure_ascii=True))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
