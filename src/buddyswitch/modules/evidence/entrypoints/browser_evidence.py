"""Issue broker-backed target-scoped Evidence metadata."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from buddyswitch.foundation.runtime_broker.client import RuntimeBrokerError, broker_unavailable_feedback, request_runtime_broker


def _runtime_error(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
        "permission_boundary": "runtime.broker",
        "human_summary": message,
        "why_blocked": message,
        "impact": "No evidence token was issued and no runtime state was changed.",
        "state_changed": False,
        "retryable": True,
        "retry_guidance": "Fix broker/context inputs and retry.",
    }
    if extra:
        payload.update(extra)
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Issue BuddySwitch browser evidence tokens.")
    sub = parser.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("issue", help="Issue browser evidence token")
    issue.add_argument("--target-type", required=True, choices=["artifact"])
    issue.add_argument("--target-id", required=True)
    issue.add_argument("--mode", default="browser-cockpit-preflight")

    downgrade = sub.add_parser("approve-downgrade", help="Issue approved downgrade token")
    downgrade.add_argument("--target-type", required=True, choices=["artifact"])
    downgrade.add_argument("--target-id", required=True)
    downgrade.add_argument("--reason", required=True)
    return parser.parse_args()


def _dispatch_issue(*, target_type: str, target_id: str, mode: str) -> dict[str, Any]:
    response = request_runtime_broker(
        "env.tool",
        {
            "tool": "evidence",
            "action": "issue_browser",
            "args": {
                "target_type": target_type,
                "target_id": target_id,
                "mode": mode,
            },
        },
    )
    if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker response for evidence issuance is invalid.",
            details=broker_unavailable_feedback(),
        )
    if response.get("ok") is not True:
        return response
    if not isinstance(response.get("tool_evidence"), dict):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker evidence payload is invalid.",
            details=broker_unavailable_feedback(),
        )
    return response


def _dispatch_approve(*, target_type: str, target_id: str, reason: str) -> dict[str, Any]:
    response = request_runtime_broker(
        "env.tool",
        {
            "tool": "evidence",
            "action": "approve_downgrade",
            "args": {
                "target_type": target_type,
                "target_id": target_id,
                "reason": reason,
            },
        },
    )
    if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker response for downgrade approval is invalid.",
            details=broker_unavailable_feedback(),
        )
    if response.get("ok") is not True:
        return response
    if not isinstance(response.get("tool_evidence"), dict):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker downgrade evidence payload is invalid.",
            details=broker_unavailable_feedback(),
        )
    return response


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "issue":
            payload = _dispatch_issue(
                target_type=args.target_type,
                target_id=args.target_id,
                mode=args.mode,
            )
        elif args.command == "approve-downgrade":
            payload = _dispatch_approve(
                target_type=args.target_type,
                target_id=args.target_id,
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
