#!/usr/bin/env python3
"""Single Codex router for BuddySwitch debug switch directives."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from env_manifest import (
    DEFAULT_MANIFEST,
    ManifestError,
    buddy_authority_profile,
    buddy_skill_docs,
    load_manifest,
    require_buddy,
)

try:
    from parse_switch import EXAMPLE, SYNTAX, parse_switch
except ModuleNotFoundError:  # pragma: no cover - defensive path fallback
    from debug.parse_switch import EXAMPLE, SYNTAX, parse_switch


def route_switch(text: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    manifest = load_manifest(manifest_path)
    parsed = parse_switch(text, manifest_path=manifest_path)
    if not parsed.get("ok"):
        return parsed

    buddy_id = parsed["buddy"]
    buddy = require_buddy(manifest, buddy_id)
    demand = parsed["demand"]
    task_id = parsed.get("task_id")
    track_id = parsed.get("track_id")
    route = {
        "ok": True,
        "adapter": "codex",
        "syntax": SYNTAX,
        "example": EXAMPLE,
        "intent": parsed.get("intent", "switch"),
        "buddy": buddy_id,
        "task_id": task_id,
        "track_id": track_id,
        "demand": demand,
        "raw_text": parsed.get("raw_text", text),
        "normalized_text": parsed.get("normalized_text"),
        "invocation": parsed.get(
            "invocation",
            {
                "intent": "switch",
                "buddy": buddy_id,
                "task_id": task_id,
                "track_id": track_id,
                "demand": demand,
                "raw_text": text,
                "normalized_text": parsed.get("normalized_text"),
            },
        ),
        "profile": {
            "id": buddy["id"],
            "label": buddy["label"],
            "scope": buddy["scope"],
            "permissions": buddy["permissions"],
            "authority": buddy_authority_profile(manifest, buddy_id),
            "skills": buddy_skill_docs(manifest, buddy_id),
        },
    }
    return route


def main() -> int:
    parser = argparse.ArgumentParser(description="Route switch directives through BuddySwitch env manifest.")
    parser.add_argument("text", nargs="?", help="Directive text, e.g. 'switch pm: Draft PRD'")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    try:
        payload = route_switch(text, manifest_path=args.manifest)
    except ManifestError as exc:
        payload = {
            "ok": False,
            "error": {
                "code": "E_ENV_MANIFEST",
                "message": str(exc),
                "expected_syntax": SYNTAX,
                "example": EXAMPLE,
            },
        }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
