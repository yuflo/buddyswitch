#!/usr/bin/env python3
"""Track CRUD and advance operations for BuddySwitch env debug/manual APIs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from env_manifest import DEFAULT_MANIFEST, ManifestError, buddy_permissions, get_buddy, load_manifest
from env_store import (
    attach_artifact,
    create_track,
    detach_artifact,
    get_track,
    list_tracks,
    update_track,
)


def require_permission(manifest: dict, actor: str, permission: str) -> None:
    permissions = buddy_permissions(manifest, actor)
    if permission not in permissions:
        raise ValueError(f"buddy '{actor}' is not allowed to perform '{permission}'")


def _validate_buddy_ref(manifest: dict, buddy_id: str | None, field: str) -> str | None:
    if buddy_id is None:
        return None
    if get_buddy(manifest, buddy_id) is None:
        raise ValueError(f"{field} must reference a known buddy")
    return buddy_id


def cmd_list(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "track.read")
    print(json.dumps(list_tracks(), ensure_ascii=True, indent=2))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "track.read")
    track = get_track(args.track_id)
    if track is None:
        raise ValueError(f"track not found: {args.track_id}")
    print(json.dumps(track, ensure_ascii=True, indent=2))
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "track.create")
    track = create_track(
        args.track_id,
        args.title,
        status=args.status,
        current_buddy=_validate_buddy_ref(manifest, args.current_buddy, "current_buddy") or "pm",
        next_buddy=_validate_buddy_ref(manifest, args.next_buddy, "next_buddy"),
        summary=args.summary or "",
    )
    print(json.dumps(track, ensure_ascii=True, indent=2))
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "track.update")
    patch = {}
    if args.title is not None:
        patch["title"] = args.title
    if args.status is not None:
        patch["status"] = args.status
    if args.current_buddy is not None:
        patch["current_buddy"] = _validate_buddy_ref(manifest, args.current_buddy, "current_buddy")
    if args.next_buddy is not None:
        patch["next_buddy"] = None if args.next_buddy == "null" else _validate_buddy_ref(
            manifest, args.next_buddy, "next_buddy"
        )
    if args.summary is not None:
        patch["summary"] = args.summary
    if not patch:
        raise ValueError("update requires at least one field")
    track = update_track(args.track_id, patch)
    print(json.dumps(track, ensure_ascii=True, indent=2))
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "track.advance")
    patch = {}
    if args.current_buddy is not None:
        patch["current_buddy"] = _validate_buddy_ref(manifest, args.current_buddy, "current_buddy")
    if args.next_buddy is not None:
        patch["next_buddy"] = None if args.next_buddy == "null" else _validate_buddy_ref(
            manifest, args.next_buddy, "next_buddy"
        )
    if args.status is not None:
        patch["status"] = args.status
    if args.summary is not None:
        patch["summary"] = args.summary
    if not patch:
        raise ValueError("advance requires at least one field")
    track = update_track(args.track_id, patch)
    print(json.dumps(track, ensure_ascii=True, indent=2))
    return 0


def cmd_attach(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "track.attach_artifact")
    artifact = attach_artifact(args.track_id, args.artifact_id)
    print(json.dumps(artifact, ensure_ascii=True, indent=2))
    return 0


def cmd_detach(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "track.detach_artifact")
    artifact = detach_artifact(args.track_id, args.artifact_id)
    print(json.dumps(artifact, ensure_ascii=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage BuddySwitch track objects through manual/debug APIs. These commands enforce actor permissions and are not the switch runtime."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)

    cmd = subparsers.add_parser("list")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_list)

    cmd = subparsers.add_parser("show")
    cmd.add_argument("track_id")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_show)

    cmd = subparsers.add_parser("create")
    cmd.add_argument("track_id")
    cmd.add_argument("--title", required=True)
    cmd.add_argument("--status", default="active")
    cmd.add_argument("--current-buddy", default="pm")
    cmd.add_argument("--next-buddy")
    cmd.add_argument("--summary")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_create)

    cmd = subparsers.add_parser("update")
    cmd.add_argument("track_id")
    cmd.add_argument("--title")
    cmd.add_argument("--status")
    cmd.add_argument("--current-buddy")
    cmd.add_argument("--next-buddy")
    cmd.add_argument("--summary")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_update)

    cmd = subparsers.add_parser("advance")
    cmd.add_argument("track_id")
    cmd.add_argument("--current-buddy")
    cmd.add_argument("--next-buddy")
    cmd.add_argument("--status")
    cmd.add_argument("--summary")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_advance)

    cmd = subparsers.add_parser("attach-artifact")
    cmd.add_argument("track_id")
    cmd.add_argument("--artifact-id", required=True)
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_attach)

    cmd = subparsers.add_parser("detach-artifact")
    cmd.add_argument("track_id")
    cmd.add_argument("--artifact-id", required=True)
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_detach)
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
