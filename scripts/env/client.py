#!/usr/bin/env python3
"""Skill-facing CLI for broker-routed env tool operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_kernel.client import (
    RuntimeBrokerError,
    broker_unavailable_feedback,
    canonical_result_hash,
    make_persist_idempotency_key,
    request_runtime_broker,
)


def _error_payload(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {"code": code, "message": message},
    }
    if not extra:
        return payload

    top_level_keys = {
        "tool",
        "action",
        "permission_boundary",
        "allowed_next_actions",
        "allowed_next_action_options",
        "command_hint",
        "stop_condition",
        "persist_payload_hint",
        "request_id",
        "retriable",
        "retry_after_ms",
        "feedback",
        "broker_status",
    }
    for key, value in extra.items():
        if key in {"code", "message"}:
            continue
        if key in top_level_keys:
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

    task_sub.add_parser("get-current", help="Get active instance current task binding")

    set_current = task_sub.add_parser("set-current", help="Set active instance current task binding")
    set_current.add_argument("--task-id", required=True)

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

    join_track = track_sub.add_parser("join", help="Create or reuse active-buddy task and bind it to a track")
    join_track.add_argument("--track-id", required=True)
    join_track.add_argument("--task-id")

    track_sub.add_parser("get-current", help="Get active instance current track binding")

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

    get_artifact = artifact_sub.add_parser("get", help="Get active-buddy artifact by id")
    get_artifact.add_argument("--artifact-id", required=True)

    get_current_artifact = artifact_sub.add_parser("get-current", help="Get current artifact revisions for active task")
    get_current_artifact.add_argument("--kind")

    validate_artifact = artifact_sub.add_parser("validate-payload", help="Validate artifact revision payload")
    validate_artifact.add_argument("--payload", required=True, type=Path)

    create_artifact = artifact_sub.add_parser("create-revision", help="Create a new artifact revision")
    create_artifact.add_argument("--payload", required=True, type=Path)

    update_artifact = artifact_sub.add_parser("update-metadata", help="Update artifact title or summary")
    update_artifact.add_argument("--payload", required=True, type=Path)

    context_parser = sub.add_parser("context", help="Context env operations")
    context_sub = context_parser.add_subparsers(dest="operation", required=True)

    get_context = context_sub.add_parser("get", help="Get active binding context")
    get_context.add_argument("--context", type=Path, help="Optional prepared context payload to validate")

    context_sub.add_parser("summarize", help="Summarize active binding context")
    context_sub.add_parser("list-sources", help="List context source descriptions")

    binding = sub.add_parser("binding", help="Active instance binding env operations")
    binding_sub = binding.add_subparsers(dest="operation", required=True)

    binding_sub.add_parser("get", help="Get active instance binding")

    set_task = binding_sub.add_parser("set-task", help="Bind active instance to an active-buddy task")
    set_task.add_argument("--task-id", required=True)

    set_track = binding_sub.add_parser("set-track", help="Bind active PM instance to a track")
    set_track.add_argument("--track-id", required=True)

    binding_sub.add_parser("clear", help="Clear active instance task and track binding")

    handoff = sub.add_parser("handoff", help="Handoff validation env operations")
    handoff_sub = handoff.add_subparsers(dest="operation", required=True)

    list_handoff = handoff_sub.add_parser("list", help="List handoff records and run-audit handoffs")
    list_handoff.add_argument("--track-id")

    validate_handoff = handoff_sub.add_parser("validate", help="Validate a handoff payload")
    validate_handoff.add_argument("--payload", required=True, type=Path)

    create_handoff = handoff_sub.add_parser("create", help="Create an explicit handoff record")
    create_handoff.add_argument("--payload", required=True, type=Path)

    evidence = sub.add_parser("evidence", help="Browser evidence env operations")
    evidence_sub = evidence.add_subparsers(dest="operation", required=True)

    issue_browser = evidence_sub.add_parser("issue-browser", help="Issue browser cockpit preflight evidence")
    issue_browser.add_argument("--context", required=True, type=Path)

    approve_downgrade = evidence_sub.add_parser("approve-downgrade", help="Issue an approved downgrade token")
    approve_downgrade.add_argument("--context", required=True, type=Path)
    approve_downgrade.add_argument("--reason", required=True)

    run = sub.add_parser("run", help="Run reservation and commit env operations")
    run_sub = run.add_subparsers(dest="operation", required=True)

    commit_run = run_sub.add_parser("commit", help="Commit a prepared buddy run")
    commit_run.add_argument("--context", required=True, type=Path)
    commit_run.add_argument("--result", required=True, type=Path)

    validate_run = run_sub.add_parser("validate-result", help="Validate a run result without committing")
    validate_run.add_argument("--context", required=True, type=Path)
    validate_run.add_argument("--result", required=True, type=Path)

    get_receipt = run_sub.add_parser("get-receipt", help="Get a committed run receipt")
    get_receipt.add_argument("--run-id", required=True)

    get_raw = run_sub.add_parser("get-raw", help="Get raw committed run audit content")
    get_raw.add_argument("--run-id", required=True)

    search = sub.add_parser(
        "search",
        help="Search env operations",
        epilog=(
            "request args: --query <query> --backend <browser|search_api> [--engine <google|web|reddit|x>]\n"
            "open-browser args: --query <query> [--engine <google|web|reddit|x>]"
        ),
    )
    search_sub = search.add_subparsers(dest="operation", required=True)

    search_sub.add_parser("status", help="Get search capability boundary and backend status")

    search_request = search_sub.add_parser(
        "request",
        help="Build search backend request feedback without opening browser page",
    )
    search_request.add_argument("--query", required=True)
    search_request.add_argument("--backend", required=True, choices=("browser", "search_api"))
    search_request.add_argument("--engine", choices=("google", "web", "reddit", "x"), default="google")

    open_browser = search_sub.add_parser("open-browser", help="Open search page in instance browser through CDP")
    open_browser.add_argument("--query", required=True)
    open_browser.add_argument("--engine", choices=("google", "web", "reddit", "x"), default="google")
    return parser.parse_args()


def _task_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation in {"create", "update"}:
        payload_path = getattr(args, "payload", None)
        if not isinstance(payload_path, Path):
            raise ValueError("payload file is required")
        return _load_json_object(payload_path)
    if operation in {"get", "set-current", "archive"}:
        task_id = getattr(args, "task_id", None)
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task id is required")
        return {"task_id": task_id.strip()}
    if operation in {"list", "get-current"}:
        return {}
    raise ValueError(f"unsupported task operation: {operation}")


def _track_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation in {"create", "update", "advance"}:
        payload_path = getattr(args, "payload", None)
        if not isinstance(payload_path, Path):
            raise ValueError("payload file is required")
        return _load_json_object(payload_path)
    if operation in {"get", "archive"}:
        track_id = getattr(args, "track_id", None)
        if not isinstance(track_id, str) or not track_id.strip():
            raise ValueError("track id is required")
        return {"track_id": track_id.strip()}
    if operation == "join":
        track_id = getattr(args, "track_id", None)
        if not isinstance(track_id, str) or not track_id.strip():
            raise ValueError("track id is required")
        payload: dict[str, Any] = {"track_id": track_id.strip()}
        task_id = getattr(args, "task_id", None)
        if isinstance(task_id, str) and task_id.strip():
            payload["task_id"] = task_id.strip()
        return payload
    if operation in {"attach-task", "detach-task"}:
        track_id = getattr(args, "track_id", None)
        task_id = getattr(args, "task_id", None)
        if not isinstance(track_id, str) or not track_id.strip():
            raise ValueError("track id is required")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task id is required")
        return {"track_id": track_id.strip(), "task_id": task_id.strip()}
    if operation in {"list", "get-current"}:
        return {}
    raise ValueError(f"unsupported track operation: {operation}")


def _artifact_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation in {"validate-payload", "create-revision", "update-metadata"}:
        payload_path = getattr(args, "payload", None)
        if not isinstance(payload_path, Path):
            raise ValueError("payload file is required")
        return _load_json_object(payload_path)
    if operation == "get":
        artifact_id = getattr(args, "artifact_id", None)
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise ValueError("artifact id is required")
        return {"artifact_id": artifact_id.strip()}
    if operation == "get-current":
        kind = getattr(args, "kind", None)
        if kind is None:
            return {}
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("kind must be a non-empty string when provided")
        return {"kind": kind.strip()}
    if operation == "list":
        track_id = getattr(args, "track_id", None)
        if not isinstance(track_id, str) or not track_id.strip():
            raise ValueError("track id is required")
        return {"track_id": track_id.strip()}
    raise ValueError(f"unsupported artifact operation: {operation}")


def _context_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation == "get":
        context_path = getattr(args, "context", None)
        if context_path is None:
            return {}
        if not isinstance(context_path, Path):
            raise ValueError("context file must be a path when provided")
        return {"context": _load_json_object(context_path)}
    if operation in {"summarize", "list-sources"}:
        return {}
    raise ValueError(f"unsupported context operation: {operation}")


def _binding_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation == "set-task":
        task_id = getattr(args, "task_id", None)
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task id is required")
        return {"task_id": task_id.strip()}
    if operation == "set-track":
        track_id = getattr(args, "track_id", None)
        if not isinstance(track_id, str) or not track_id.strip():
            raise ValueError("track id is required")
        return {"track_id": track_id.strip()}
    if operation in {"get", "clear"}:
        return {}
    raise ValueError(f"unsupported binding operation: {operation}")


def _handoff_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation in {"validate", "create"}:
        payload_path = getattr(args, "payload", None)
        if not isinstance(payload_path, Path):
            raise ValueError("payload file is required")
        return _load_json_object(payload_path)
    if operation == "list":
        track_id = getattr(args, "track_id", None)
        if track_id is None:
            return {}
        if not isinstance(track_id, str) or not track_id.strip():
            raise ValueError("track id must be a non-empty string when provided")
        return {"track_id": track_id.strip()}
    raise ValueError(f"unsupported handoff operation: {operation}")


def _evidence_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation in {"issue-browser", "approve-downgrade"}:
        context_path = getattr(args, "context", None)
        if not isinstance(context_path, Path):
            raise ValueError("context file is required")
        payload: dict[str, Any] = {"context": _load_json_object(context_path)}
        if operation == "approve-downgrade":
            reason = getattr(args, "reason", None)
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("reason is required")
            payload["reason"] = reason.strip()
        return payload
    raise ValueError(f"unsupported evidence operation: {operation}")


def _run_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation in {"commit", "validate-result"}:
        context_path = getattr(args, "context", None)
        result_path = getattr(args, "result", None)
        if not isinstance(context_path, Path):
            raise ValueError("context file is required")
        if not isinstance(result_path, Path):
            raise ValueError("result file is required")
        return {
            "context": _load_json_object(context_path),
            "result": _load_json_object(result_path),
        }
    if operation in {"get-receipt", "get-raw"}:
        run_id = getattr(args, "run_id", None)
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run id is required")
        return {"run_id": run_id.strip()}
    raise ValueError(f"unsupported run operation: {operation}")


def _search_args_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    operation = args.operation
    if operation == "status":
        return {}
    if operation == "request":
        query = getattr(args, "query", None)
        backend = getattr(args, "backend", None)
        engine = getattr(args, "engine", None)
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query is required")
        if not isinstance(backend, str) or not backend.strip():
            raise ValueError("backend is required")
        payload: dict[str, Any] = {
            "query": query.strip(),
            "backend": backend.strip(),
        }
        if isinstance(engine, str) and engine.strip():
            payload["engine"] = engine.strip()
        return payload
    if operation == "open-browser":
        query = getattr(args, "query", None)
        engine = getattr(args, "engine", None)
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query is required")
        payload = {"query": query.strip()}
        if isinstance(engine, str) and engine.strip():
            payload["engine"] = engine.strip()
        return payload
    raise ValueError(f"unsupported search operation: {operation}")


def _dispatch_env_tool(
    tool: str,
    action: str,
    args: dict[str, Any],
    *,
    envelope_idempotency_key: str | None = None,
    envelope_result_hash: str | None = None,
) -> dict[str, Any]:
    payload = {"tool": tool, "action": action, "args": args}
    response = request_runtime_broker(
        "env.tool",
        payload,
        idempotency_key=envelope_idempotency_key,
        result_hash=envelope_result_hash,
    )
    if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
        return _error_payload(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            f"runtime broker response for env.tool {tool} envelope is invalid",
            broker_unavailable_feedback(),
        )
    return response


def _dispatch_task(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    return _dispatch_env_tool("task", action, _task_args_from_cli(args))


def _dispatch_track(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    return _dispatch_env_tool("track", action, _track_args_from_cli(args))


def _dispatch_artifact(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    return _dispatch_env_tool("artifact", action, _artifact_args_from_cli(args))


def _dispatch_context(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    return _dispatch_env_tool("context", action, _context_args_from_cli(args))


def _dispatch_binding(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    return _dispatch_env_tool("binding", action, _binding_args_from_cli(args))


def _dispatch_handoff(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    return _dispatch_env_tool("handoff", action, _handoff_args_from_cli(args))


def _dispatch_evidence(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    return _dispatch_env_tool("evidence", action, _evidence_args_from_cli(args))


def _dispatch_run(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    payload_args = _run_args_from_cli(args)
    envelope_idempotency_key: str | None = None
    envelope_result_hash: str | None = None
    if action == "commit":
        context = payload_args.get("context")
        result = payload_args.get("result")
        if isinstance(context, dict) and isinstance(result, dict):
            envelope_idempotency_key = make_persist_idempotency_key(context, result)
            envelope_result_hash = canonical_result_hash(result)
    return _dispatch_env_tool(
        "run",
        action,
        payload_args,
        envelope_idempotency_key=envelope_idempotency_key,
        envelope_result_hash=envelope_result_hash,
    )


def _dispatch_search(args: argparse.Namespace) -> dict[str, Any]:
    operation = str(args.operation)
    action = _operation_to_action(operation)
    return _dispatch_env_tool("search", action, _search_args_from_cli(args))


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
        elif args.resource == "binding":
            payload = _dispatch_binding(args)
        elif args.resource == "handoff":
            payload = _dispatch_handoff(args)
        elif args.resource == "evidence":
            payload = _dispatch_evidence(args)
        elif args.resource == "run":
            payload = _dispatch_run(args)
        elif args.resource == "search":
            payload = _dispatch_search(args)
        else:
            raise ValueError(f"unsupported resource: {args.resource}")
    except RuntimeBrokerError as exc:
        payload = _error_payload(exc.code, exc.message, exc.details)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: payload file is not readable or invalid JSON object: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
