#!/usr/bin/env python3
"""Issue broker-backed browser evidence tokens for Market runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from runtime_kernel.client import RuntimeBrokerError, request_runtime_broker


def _runtime_error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


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
    response = request_runtime_broker(
        "issue_browser_evidence",
        {"context": context, "mode": mode, "reason": reason},
    )
    if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker response for evidence issuance is invalid.",
        )
    if response.get("ok") is not True:
        return response
    payload = response.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker evidence payload is invalid.",
        )
    return payload


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
        payload = _runtime_error(exc.code, exc.message)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = _runtime_error("E_RUNTIME_BROKER", str(exc))

    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
