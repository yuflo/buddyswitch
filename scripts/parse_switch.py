#!/usr/bin/env python3
"""Parser for BuddySwitch switch directives backed by env manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from env_manifest import DEFAULT_MANIFEST, ManifestError, buddies_by_id, load_manifest

SYNTAX = "switch <buddy>: <task>"
EXAMPLE = "switch pm: Draft an MVP PRD from artifacts/art-live-space--research.md"


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


def _build_invocation(raw_text: str, buddy: str, task: str) -> dict:
    normalized_text = f"switch {buddy}: {task}"
    return {
        "intent": "switch",
        "buddy": buddy,
        "task": task,
        "raw_text": raw_text,
        "normalized_text": normalized_text,
    }


def parse_switch(text: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
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

    match = re.match(r"^switch\s+([a-z][a-z0-9-]*)\s*:(.*)$", raw)
    if not match:
        return error(
            "E_INVALID_SYNTAX",
            "Invalid switch syntax.",
            {"expected_syntax": SYNTAX, "example": EXAMPLE},
        )

    agent = match.group(1)
    task = match.group(2).strip()

    manifest = load_manifest(manifest_path)
    valid_agents = sorted(buddies_by_id(manifest).keys())
    if agent not in valid_agents:
        return error(
            "E_UNKNOWN_AGENT",
            f"Unknown buddy '{agent}'.",
            {
                "valid_agents": valid_agents,
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

    invocation = _build_invocation(text, agent, task)
    return {
        "ok": True,
        "agent": agent,
        "buddy": agent,
        "task": task,
        "intent": invocation["intent"],
        "raw_text": invocation["raw_text"],
        "normalized_text": invocation["normalized_text"],
        "invocation": invocation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse BuddySwitch switch directive.")
    parser.add_argument("text", nargs="?", help="Directive text, e.g. 'switch pm: continue track'")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    try:
        result = parse_switch(text, manifest_path=args.manifest)
    except ManifestError as exc:
        result = error(
            "E_ENV_MANIFEST",
            str(exc),
            {"expected_syntax": SYNTAX, "example": EXAMPLE},
        )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
