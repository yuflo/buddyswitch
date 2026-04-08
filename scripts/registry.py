#!/usr/bin/env python3
"""Manage the BuddySwitch v1 local Track Registry dump."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "artifacts" / "workspace-registry.json"
VALID_ROLES = ("market", "pm", "design", "dev", "test")
VALID_TYPES = ("research", "prd", "design-spec", "implementation-report", "smoke-test")


def default_registry() -> dict[str, Any]:
    project_id = ROOT.name
    project_name = "BuddySwitch" if project_id == "buddyswitch" else project_id.replace("-", " ").title()
    return {
        "schema_version": 1,
        "project": {"id": project_id, "name": project_name},
        "tracks": [],
    }


def repo_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"path must be repo-relative and must not contain '..': {raw_path}")
    return path.as_posix()


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_registry()

    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {display_path(path)}: {exc}") from exc

    validate_registry_shape(registry)
    return registry


def validate_registry_shape(registry: dict[str, Any]) -> None:
    if not isinstance(registry, dict):
        raise ValueError("registry must be a JSON object")
    if registry.get("schema_version") != 1:
        raise ValueError("registry schema_version must be 1")
    if not isinstance(registry.get("project", {}), dict):
        raise ValueError("registry project must be an object")
    if not isinstance(registry.get("tracks"), list):
        raise ValueError("registry tracks must be a list")

    seen_tracks: set[str] = set()
    for track in registry["tracks"]:
        if not isinstance(track, dict):
            raise ValueError("each track must be an object")
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id:
            raise ValueError("each track must include a non-empty id")
        if track_id in seen_tracks:
            raise ValueError(f"duplicate track id: {track_id}")
        seen_tracks.add(track_id)
        if not isinstance(track.get("artifacts", []), list):
            raise ValueError(f"track {track_id} artifacts must be a list")
        for artifact in track.get("artifacts", []):
            validate_artifact(artifact, context=f"track {track_id}")


def validate_artifact(artifact: dict[str, Any], context: str = "artifact") -> None:
    if not isinstance(artifact, dict):
        raise ValueError(f"{context} artifact entry must be an object")
    role = artifact.get("role")
    artifact_type = artifact.get("type")
    path = artifact.get("path")
    if role not in VALID_ROLES:
        raise ValueError(f"{context} has invalid role: {role}")
    if artifact_type not in VALID_TYPES:
        raise ValueError(f"{context} has invalid type: {artifact_type}")
    if not isinstance(path, str) or not path:
        raise ValueError(f"{context} artifact path must be a non-empty string")
    repo_path(path)


def write_registry(path: Path, registry: dict[str, Any]) -> None:
    validate_registry_shape(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(registry, indent=2, ensure_ascii=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def find_track(registry: dict[str, Any], track_id: str) -> dict[str, Any] | None:
    for track in registry["tracks"]:
        if track["id"] == track_id:
            return track
    return None


def require_track(registry: dict[str, Any], track_id: str) -> dict[str, Any]:
    track = find_track(registry, track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    return track


def save_if_needed(args: argparse.Namespace, registry: dict[str, Any], changed: bool, message: str) -> int:
    if args.dry_run:
        prefix = "Would update" if changed else "No registry update needed"
        print(f"{prefix}: {message}")
        return 0
    if changed:
        write_registry(args.registry, registry)
        print(f"Updated: {message}")
    else:
        print(f"No registry update needed: {message}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    validate_registry_shape(registry)
    print(f"OK: {display_path(args.registry)} ({len(registry['tracks'])} track(s))")
    return 0


def cmd_list_tracks(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    if not registry["tracks"]:
        print("No tracks.")
        return 0
    for track in registry["tracks"]:
        print(f"{track['id']}\t{track.get('state', 'active')}\t{track.get('title', track['id'])}")
    return 0


def cmd_show_track(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    track = require_track(registry, args.track_id)
    print(json.dumps(track, indent=2, ensure_ascii=True))
    return 0


def cmd_create_track(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    if find_track(registry, args.track_id):
        return save_if_needed(args, registry, False, f"track already exists: {args.track_id}")

    registry["tracks"].append(
        {"id": args.track_id, "title": args.title, "state": args.state, "artifacts": []}
    )
    return save_if_needed(args, registry, True, f"created track {args.track_id}")


def cmd_delete_track(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    before = len(registry["tracks"])
    registry["tracks"] = [track for track in registry["tracks"] if track["id"] != args.track_id]
    changed = len(registry["tracks"]) != before
    return save_if_needed(args, registry, changed, f"deleted track {args.track_id}")


def cmd_add_artifact(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    track = require_track(registry, args.track_id)
    artifact = {"role": args.role, "type": args.artifact_type, "path": repo_path(args.path)}
    validate_artifact(artifact)

    artifacts = track.setdefault("artifacts", [])
    for index, existing in enumerate(artifacts):
        if existing.get("path") == artifact["path"]:
            changed = existing != artifact
            artifacts[index] = artifact
            return save_if_needed(args, registry, changed, f"upserted artifact {artifact['path']}")

    artifacts.append(artifact)
    return save_if_needed(args, registry, True, f"added artifact {artifact['path']}")


def cmd_remove_artifact(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    track = require_track(registry, args.track_id)
    artifact_path = repo_path(args.path)
    before = len(track.get("artifacts", []))
    track["artifacts"] = [item for item in track.get("artifacts", []) if item.get("path") != artifact_path]
    changed = len(track["artifacts"]) != before
    return save_if_needed(args, registry, changed, f"removed artifact {artifact_path} from {args.track_id}")


def cmd_remove_role_artifacts(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    removed = 0
    removed_tracks: list[str] = []
    kept_tracks = []

    for track in registry["tracks"]:
        artifacts = track.get("artifacts", [])
        next_artifacts = [item for item in artifacts if item.get("role") != args.role]
        removed += len(artifacts) - len(next_artifacts)
        track["artifacts"] = next_artifacts
        if args.drop_empty_tracks and not next_artifacts:
            removed_tracks.append(track["id"])
            continue
        kept_tracks.append(track)

    registry["tracks"] = kept_tracks
    message = f"removed {removed} {args.role} artifact(s)"
    if removed_tracks:
        message += f"; dropped empty track(s): {', '.join(removed_tracks)}"
    return save_if_needed(args, registry, bool(removed or removed_tracks), message)


def cmd_clear(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    count = len(registry["tracks"])
    registry["tracks"] = []
    return save_if_needed(args, registry, bool(count), f"cleared {count} track(s)")


def add_common_write_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true", help="Preview registry change without writing")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the BuddySwitch local Track Registry dump.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY, help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.set_defaults(func=cmd_validate)

    list_tracks = subparsers.add_parser("list-tracks")
    list_tracks.set_defaults(func=cmd_list_tracks)

    show_track = subparsers.add_parser("show-track")
    show_track.add_argument("track_id")
    show_track.set_defaults(func=cmd_show_track)

    create_track = subparsers.add_parser("create-track")
    create_track.add_argument("track_id")
    create_track.add_argument("--title", required=True)
    create_track.add_argument("--state", default="active")
    add_common_write_flags(create_track)
    create_track.set_defaults(func=cmd_create_track)

    delete_track = subparsers.add_parser("delete-track")
    delete_track.add_argument("track_id")
    delete_track.add_argument("--force", action="store_true", required=True)
    add_common_write_flags(delete_track)
    delete_track.set_defaults(func=cmd_delete_track)

    add_artifact = subparsers.add_parser("add-artifact")
    add_artifact.add_argument("track_id")
    add_artifact.add_argument("--role", required=True, choices=VALID_ROLES)
    add_artifact.add_argument("--type", dest="artifact_type", required=True, choices=VALID_TYPES)
    add_artifact.add_argument("--path", required=True)
    add_common_write_flags(add_artifact)
    add_artifact.set_defaults(func=cmd_add_artifact)

    remove_artifact = subparsers.add_parser("remove-artifact")
    remove_artifact.add_argument("track_id")
    remove_artifact.add_argument("--path", required=True)
    add_common_write_flags(remove_artifact)
    remove_artifact.set_defaults(func=cmd_remove_artifact)

    remove_role = subparsers.add_parser("remove-role-artifacts")
    remove_role.add_argument("--role", required=True, choices=VALID_ROLES)
    remove_role.add_argument("--drop-empty-tracks", action="store_true")
    add_common_write_flags(remove_role)
    remove_role.set_defaults(func=cmd_remove_role_artifacts)

    clear = subparsers.add_parser("clear")
    clear.add_argument("--force", action="store_true", required=True)
    add_common_write_flags(clear)
    clear.set_defaults(func=cmd_clear)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.registry = args.registry if args.registry.is_absolute() else (ROOT / args.registry)

    try:
        return args.func(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
