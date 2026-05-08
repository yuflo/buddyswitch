#!/usr/bin/env python3
"""Validate runtime AGENTS templates against buddy profile boundaries."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

from env_manifest import DEFAULT_MANIFEST, ManifestError, load_manifest, require_buddy
import env_profiles

ROOT = Path(__file__).resolve().parents[1]


class RuntimeAgentsError(ValueError):
    """Raised when a runtime AGENTS template misses required boundary text."""


def _require_contains(*, text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise RuntimeAgentsError(message)


def _require_contains_any(*, text: str, needles: list[str], message: str) -> None:
    for needle in needles:
        if needle in text:
            return
    raise RuntimeAgentsError(message)


def validate_runtime_agents_template(
    *,
    buddy_id: str,
    template_path: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    try:
        manifest = load_manifest(manifest_path)
        require_buddy(manifest, buddy_id)
    except ManifestError as exc:
        raise RuntimeAgentsError(str(exc)) from exc

    profile = env_profiles.require_env_profile(
        buddy_id,
        manifest_path=manifest_path,
        repo_root=ROOT,
    )

    try:
        text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeAgentsError(f"cannot read template: {template_path}: {exc}") from exc

    lowered = text.lower()

    _require_contains(
        text=text,
        needle="# BuddySwitch Runtime Workspace",
        message="missing runtime workspace header",
    )
    _require_contains(
        text=text,
        needle=f"`{buddy_id}`",
        message=f"missing active buddy id `{buddy_id}` in template body",
    )
    _require_contains(
        text=text,
        needle="scripts/turn_runtime.py prepare",
        message="missing prepare command reference",
    )
    _require_contains(
        text=text,
        needle="scripts/turn_runtime.py persist",
        message="missing persist command reference",
    )

    project_access = profile["project"]["access"]
    scratch_root = profile["scratch"]["root"]

    _require_contains(
        text=lowered,
        needle=f"project.access={project_access}".lower(),
        message=f"missing profile project access wording: project.access={project_access}",
    )
    _require_contains(
        text=text,
        needle=scratch_root,
        message=f"missing buddy scratch root wording: {scratch_root}",
    )
    _require_contains_any(
        text=lowered,
        needles=[
            "raw state is broker-only",
            "raw state remains broker-only",
            "broker-only state",
        ],
        message="missing broker-only raw state wording",
    )
    _require_contains_any(
        text=lowered,
        needles=[
            "agents.md describes context projection only",
            "agents.md is context projection only",
            "agents.md is not the permission source",
        ],
        message="missing AGENTS context projection wording",
    )
    _require_contains(
        text=text,
        needle="prepare.runtime_context",
        message="missing prepare.runtime_context reference",
    )
    _require_contains_any(
        text=lowered,
        needles=[
            "structured tool feedback",
            "runtime tool rejects",
            "runtime tool is rejected",
        ],
        message="missing structured tool feedback wording for runtime rejections",
    )
    _require_contains_any(
        text=lowered,
        needles=[
            "do not bypass",
            "do not route around",
            "do not bypass runtime",
        ],
        message="missing do-not-bypass runtime tool wording",
    )
    _require_contains_any(
        text=lowered,
        needles=["receipt", "## receipt"],
        message="missing receipt section",
    )
    _require_contains_any(
        text=lowered,
        needles=["summary", "## summary"],
        message="missing summary section",
    )

    if buddy_id == "dev":
        _require_contains_any(
            text=lowered,
            needles=[
                "dev can write projects/app",
                "dev can write `projects/app`",
                "can write projects/app",
                "project source is writable",
            ],
            message="missing dev source-write authority wording",
        )
    else:
        _require_contains_any(
            text=lowered,
            needles=[
                "project source is read-only",
                "source is read-only",
                "cannot edit source",
            ],
            message="missing non-dev source read-only wording",
        )
        _require_contains_any(
            text=lowered,
            needles=[
                "hand off to dev",
                "handoff to dev",
                "hand source fixes to dev",
            ],
            message="missing non-dev dev-handoff wording",
        )

    if buddy_id == "market":
        _require_contains(
            text=text,
            needle="prepare.runtime_context.tool_requirements",
            message="missing market tool requirements pointer",
        )

    return {"ok": True, "buddy_id": buddy_id, "template_path": str(template_path)}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BuddySwitch runtime AGENTS templates.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate one AGENTS template")
    validate.add_argument("--buddy", required=True)
    validate.add_argument("--template", required=True, type=Path)

    sub.add_parser("validate-all", help="Validate all buddy AGENTS templates")
    return parser.parse_args()


def _buddy_template_path(buddy_id: str) -> Path:
    return ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy_id / "AGENTS.md"


def _cmd_validate(args: argparse.Namespace) -> int:
    validate_runtime_agents_template(
        buddy_id=args.buddy,
        template_path=args.template,
        manifest_path=args.manifest,
    )
    print(f"{args.buddy}: ok")
    return 0


def _cmd_validate_all(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    for buddy in manifest.get("buddies", []):
        if not isinstance(buddy, dict):
            continue
        buddy_id = buddy.get("id")
        if not isinstance(buddy_id, str):
            continue
        validate_runtime_agents_template(
            buddy_id=buddy_id,
            template_path=_buddy_template_path(buddy_id),
            manifest_path=args.manifest,
        )
        print(f"{buddy_id}: ok")
    return 0


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "validate":
            return _cmd_validate(args)
        if args.command == "validate-all":
            return _cmd_validate_all(args)
        raise RuntimeAgentsError(f"unsupported command: {args.command}")
    except (RuntimeAgentsError, ManifestError, env_profiles.EnvProfileError) as exc:
        print(f"Runtime AGENTS invalid: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
