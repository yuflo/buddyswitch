#!/usr/bin/env python3
"""Single Codex router for BuddySwitch env-backed switch directives."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from env_manifest import DEFAULT_MANIFEST, ManifestError, buddy_skill_docs, load_manifest, require_buddy
from parse_switch import EXAMPLE, SYNTAX, parse_switch


def route_switch(text: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    manifest = load_manifest(manifest_path)
    parsed = parse_switch(text, manifest_path=manifest_path)
    if not parsed.get("ok"):
        return parsed

    buddy_id = parsed["buddy"]
    buddy = require_buddy(manifest, buddy_id)
    route = {
        "ok": True,
        "adapter": "codex",
        "syntax": SYNTAX,
        "example": EXAMPLE,
        "buddy": buddy_id,
        "task": parsed["task"],
        "profile": {
            "id": buddy["id"],
            "label": buddy["label"],
            "scope": buddy["scope"],
            "permissions": buddy["permissions"],
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
