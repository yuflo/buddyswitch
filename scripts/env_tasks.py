#!/usr/bin/env python3
"""Task read/update operations for BuddySwitch env debug/manual APIs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from env_manifest import DEFAULT_MANIFEST, ManifestError, buddy_permissions, load_manifest
from env_store import get_task, list_tasks, update_task


def require_permission(manifest: dict, actor: str, permission: str) -> None:
    permissions = buddy_permissions(manifest, actor)
    if permission not in permissions:
        raise ValueError(f"buddy '{actor}' is not allowed to perform '{permission}'")


def cmd_list(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "task.read")
    print(json.dumps(list_tasks(), ensure_ascii=True, indent=2))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "task.read")
    task = get_task(args.task_id)
    if task is None:
        raise ValueError(f"task not found: {args.task_id}")
    print(json.dumps(task, ensure_ascii=True, indent=2))
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "task.update")
    patch = {}
    if args.title is not None:
        patch["title"] = args.title
    if args.status is not None:
        patch["status"] = args.status
    if args.summary is not None:
        patch["summary"] = args.summary
    if args.track_id is not None:
        patch["track_id"] = None if args.track_id == "null" else args.track_id
    if not patch:
        raise ValueError("update requires at least one field")
    task = update_task(args.task_id, patch)
    print(json.dumps(task, ensure_ascii=True, indent=2))
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "task.archive")
    task = update_task(args.task_id, {"status": "archived"})
    print(json.dumps(task, ensure_ascii=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage BuddySwitch task objects through manual/debug APIs."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)

    cmd = subparsers.add_parser("list")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_list)

    cmd = subparsers.add_parser("show")
    cmd.add_argument("task_id")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_show)

    cmd = subparsers.add_parser("update")
    cmd.add_argument("task_id")
    cmd.add_argument("--title")
    cmd.add_argument("--status")
    cmd.add_argument("--summary")
    cmd.add_argument("--track-id")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_update)

    cmd = subparsers.add_parser("archive")
    cmd.add_argument("task_id")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_archive)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ValueError, ManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
