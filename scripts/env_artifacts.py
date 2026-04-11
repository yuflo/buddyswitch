#!/usr/bin/env python3
"""Artifact CRUD, auto-registration, and admin cleanup operations for BuddySwitch env."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from env_manifest import DEFAULT_MANIFEST, ManifestError, buddy_permissions, get_buddy, load_manifest
from env_store import (
    create_artifact,
    delete_all_artifacts,
    delete_artifact,
    delete_artifacts_by_buddy,
    get_artifact,
    list_artifacts,
    update_artifact,
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
    require_permission(manifest, args.actor, "artifact.read")
    print(json.dumps(list_artifacts(), ensure_ascii=True, indent=2))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "artifact.read")
    artifact = get_artifact(args.artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {args.artifact_id}")
    print(json.dumps(artifact, ensure_ascii=True, indent=2))
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "artifact.create")
    artifact = create_artifact(
        artifact_id=args.artifact_id,
        title=args.title,
        kind=args.kind,
        path=args.path,
        producer_buddy=_validate_buddy_ref(manifest, args.producer_buddy, "producer_buddy") or args.producer_buddy,
        source_skill=args.source_skill,
        context_track_id=args.context_track_id,
        auto_register=not args.no_auto_register,
    )
    print(json.dumps(artifact, ensure_ascii=True, indent=2))
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "artifact.update")
    patch = {}
    for field in ("title", "kind", "path", "producer_buddy", "source_skill"):
        value = getattr(args, field)
        if value is not None:
            if field == "producer_buddy":
                patch[field] = _validate_buddy_ref(manifest, value, field)
            else:
                patch[field] = value
    if args.context_track_id is not None:
        patch["context_track_id"] = None if args.context_track_id == "null" else args.context_track_id
    if not patch:
        raise ValueError("update requires at least one field")
    artifact = update_artifact(args.artifact_id, patch, auto_register=not args.no_auto_register)
    print(json.dumps(artifact, ensure_ascii=True, indent=2))
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    require_permission(manifest, args.actor, "artifact.delete")
    artifact = delete_artifact(args.artifact_id, delete_file=args.delete_file)
    print(json.dumps(artifact, ensure_ascii=True, indent=2))
    return 0


def cmd_cleanup_buddy(args: argparse.Namespace) -> int:
    targets = delete_artifacts_by_buddy(args.buddy, delete_files=args.delete_files, dry_run=args.dry_run)
    print(json.dumps({"count": len(targets), "artifacts": targets}, ensure_ascii=True, indent=2))
    return 0


def cmd_cleanup_all(args: argparse.Namespace) -> int:
    targets = delete_all_artifacts(delete_files=args.delete_files, dry_run=args.dry_run)
    print(json.dumps({"count": len(targets), "artifacts": targets}, ensure_ascii=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage BuddySwitch artifact objects. Cleanup commands are admin maintenance helpers and are not buddy-scoped mutation APIs."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)

    cmd = subparsers.add_parser("list")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_list)

    cmd = subparsers.add_parser("show")
    cmd.add_argument("artifact_id")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_show)

    cmd = subparsers.add_parser("create")
    cmd.add_argument("--artifact-id")
    cmd.add_argument("--title", required=True)
    cmd.add_argument("--kind", required=True)
    cmd.add_argument("--path")
    cmd.add_argument("--producer-buddy", required=True)
    cmd.add_argument("--source-skill", required=True)
    cmd.add_argument("--context-track-id")
    cmd.add_argument("--no-auto-register", action="store_true")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_create)

    cmd = subparsers.add_parser("update")
    cmd.add_argument("artifact_id")
    cmd.add_argument("--title")
    cmd.add_argument("--kind")
    cmd.add_argument("--path")
    cmd.add_argument("--producer-buddy")
    cmd.add_argument("--source-skill")
    cmd.add_argument("--context-track-id")
    cmd.add_argument("--no-auto-register", dest="no_auto_register", action="store_true")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_update)

    cmd = subparsers.add_parser("delete")
    cmd.add_argument("artifact_id")
    cmd.add_argument("--delete-file", action="store_true")
    cmd.add_argument("--actor", default="pm")
    cmd.set_defaults(func=cmd_delete)

    cmd = subparsers.add_parser("cleanup-buddy", help="Admin cleanup for artifacts produced by one buddy")
    cmd.add_argument("--buddy", required=True)
    cmd.add_argument("--delete-files", action="store_true")
    cmd.add_argument("--dry-run", action="store_true")
    cmd.set_defaults(func=cmd_cleanup_buddy)

    cmd = subparsers.add_parser("cleanup-all", help="Admin cleanup for all artifact objects")
    cmd.add_argument("--delete-files", action="store_true")
    cmd.add_argument("--dry-run", action="store_true")
    cmd.set_defaults(func=cmd_cleanup_all)
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
