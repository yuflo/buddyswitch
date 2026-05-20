#!/usr/bin/env python3
"""evidence env.tool CLI registration."""

from __future__ import annotations

import argparse
from typing import Any

TOOL_ID = "evidence"


def register_cli(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("evidence", help="Evidence env operations")
    evidence_sub = parser.add_subparsers(dest="operation", required=True)

    issue_browser = evidence_sub.add_parser("issue-browser", help="Issue browser preflight evidence")
    issue_browser.add_argument("--target-type", required=True)
    issue_browser.add_argument("--target-id", required=True)
    issue_browser.add_argument("--mode")
    issue_browser.set_defaults(_env_tool=TOOL_ID, _env_action="issue_browser", _env_payload_builder=_issue_browser_payload)

    approve_downgrade = evidence_sub.add_parser("approve-downgrade", help="Issue downgrade approval token")
    approve_downgrade.add_argument("--target-type", required=True)
    approve_downgrade.add_argument("--target-id", required=True)
    approve_downgrade.add_argument("--reason", required=True)
    approve_downgrade.set_defaults(
        _env_tool=TOOL_ID,
        _env_action="approve_downgrade",
        _env_payload_builder=_approve_downgrade_payload,
    )


def _issue_browser_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "target_type": args.target_type,
        "target_id": args.target_id,
    }
    if isinstance(args.mode, str) and args.mode.strip():
        payload["mode"] = args.mode.strip()
    return payload


def _approve_downgrade_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "target_type": args.target_type,
        "target_id": args.target_id,
        "reason": args.reason,
    }
