#!/usr/bin/env python3
"""Minimal parser for BuddySwitch v1 switch directives."""

from __future__ import annotations

import argparse
import json
import re
import sys

VALID_AGENTS = ("market", "pm", "design", "dev", "test")
SYNTAX = "switch <agent>: <task>"
EXAMPLE = "switch pm: Draft an MVP PRD from artifacts/research/live-space.md"


def error(code: str, message: str, extra: dict | None = None) -> dict:
    payload = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if extra:
        payload["error"].update(extra)
    return payload


def parse_switch(text: str) -> dict:
    raw = text.strip()
    if not raw:
        return error(
            "E_EMPTY_INPUT",
            "Input is empty.",
            {"expected_syntax": SYNTAX, "example": EXAMPLE},
        )

    if not raw.startswith("switch"):
        return error(
            "E_INVALID_SYNTAX",
            "Input must start with 'switch'.",
            {"expected_syntax": SYNTAX, "example": EXAMPLE},
        )

    match = re.match(r"^switch\s+([a-z]+)\s*:(.*)$", raw)
    if not match:
        return error(
            "E_INVALID_SYNTAX",
            "Invalid switch syntax.",
            {"expected_syntax": SYNTAX, "example": EXAMPLE},
        )

    agent = match.group(1)
    task = match.group(2).strip()

    if agent not in VALID_AGENTS:
        return error(
            "E_UNKNOWN_AGENT",
            f"Unknown agent '{agent}'.",
            {
                "valid_agents": list(VALID_AGENTS),
                "expected_syntax": SYNTAX,
                "example": EXAMPLE,
            },
        )

    if not task:
        return error(
            "E_EMPTY_TASK",
            "Task is empty. Provide content after ':'.",
            {"expected_syntax": SYNTAX, "example": EXAMPLE},
        )

    return {"ok": True, "agent": agent, "task": task}


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse BuddySwitch v1 switch directive.")
    parser.add_argument("text", nargs="?", help="Directive text, e.g. 'switch pm: Draft PRD'")
    args = parser.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    result = parse_switch(text)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
