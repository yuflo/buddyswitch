#!/usr/bin/env python3
"""Issue broker-backed browser evidence tokens for Market runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from runtime_kernel.client import RuntimeBrokerError, broker_unavailable_feedback, request_runtime_broker


def _runtime_error(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if extra:
        error.update(extra)
    return {"ok": False, "error": error}


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"context must be a JSON object: {path}")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Issue BuddySwitch browser evidence tokens.")
    sub = parser.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("issue", help="Issue browser cockpit preflight token")
    issue.add_argument("--context", required=True, type=Path)
    issue.add_argument("--mode", required=True, choices=["browser-cockpit-preflight"])

    downgrade = sub.add_parser("approve-downgrade", help="Issue approved downgrade token")
    downgrade.add_argument("--context", required=True, type=Path)
    downgrade.add_argument("--reason", required=True)
    return parser.parse_args()


def _dispatch_issue(*, context: dict[str, Any], mode: str, reason: str | None) -> dict[str, Any]:
    if mode == "browser-cockpit-preflight":
        action = "issue_browser"
        args: dict[str, Any] = {"context": context}
    elif mode == "approved-downgrade":
        action = "approve_downgrade"
        args = {"context": context, "reason": reason}
    else:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            f"unsupported evidence mode: {mode}",
            details=broker_unavailable_feedback(),
        )
    response = request_runtime_broker("env.tool", {"tool": "evidence", "action": action, "args": args})
    if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker response for evidence issuance is invalid.",
            details=broker_unavailable_feedback(),
        )
    if response.get("ok") is not True:
        return response
    if not isinstance(response.get("tool_evidence"), dict) or not isinstance(response.get("feedback"), dict):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker evidence payload is invalid.",
            details=broker_unavailable_feedback(),
        )
    return {
        "ok": True,
        "tool_evidence": response["tool_evidence"],
        "feedback": response["feedback"],
    }


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "issue":
            context = _load_json_object(args.context)
            payload = _dispatch_issue(context=context, mode=args.mode, reason=None)
        elif args.command == "approve-downgrade":
            context = _load_json_object(args.context)
            payload = _dispatch_issue(
                context=context,
                mode="approved-downgrade",
                reason=args.reason,
            )
        else:
            payload = _runtime_error("E_RUNTIME_BROKER", f"unsupported command: {args.command}")
    except RuntimeBrokerError as exc:
        payload = _runtime_error(exc.code, exc.message, exc.details)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = _runtime_error("E_RUNTIME_BROKER", str(exc))

    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
