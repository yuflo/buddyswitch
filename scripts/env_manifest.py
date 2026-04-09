#!/usr/bin/env python3
"""Load and validate the BuddySwitch env manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
_BUDDY_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class ManifestError(ValueError):
    """Raised when the env manifest is invalid."""


def _require_string(node: dict[str, Any], key: str, label: str) -> str:
    value = node.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label}.{key} must be a non-empty string")
    return value


def _require_string_list(node: dict[str, Any], key: str, label: str) -> list[str]:
    value = node.get(key)
    if not isinstance(value, list) or not value:
        raise ManifestError(f"{label}.{key} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ManifestError(f"{label}.{key} must contain only non-empty strings")
    return value


def _validate_permission(permission: str, label: str) -> None:
    if "." not in permission:
        raise ManifestError(f"{label} permission '{permission}' must use '<object>.<action>' format")
    obj, action = permission.split(".", 1)
    if obj not in {"track", "artifact"}:
        raise ManifestError(f"{label} permission '{permission}' has unsupported object '{obj}'")
    if not action:
        raise ManifestError(f"{label} permission '{permission}' has empty action")


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")

    try:
        manifest = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"Invalid TOML in {path}: {exc}") from exc

    schema_version = manifest.get("schema_version")
    if schema_version != 1:
        raise ManifestError("schema_version must be 1")

    env_node = manifest.get("env")
    if not isinstance(env_node, dict):
        raise ManifestError("env section is required")
    _require_string(env_node, "id", "env")
    _require_string(env_node, "label", "env")

    adapters = manifest.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        raise ManifestError("adapters must be a non-empty list")
    for index, adapter in enumerate(adapters):
        label = f"adapters[{index}]"
        if not isinstance(adapter, dict):
            raise ManifestError(f"{label} must be an object")
        _require_string(adapter, "id", label)
        _require_string(adapter, "path", label)
        _require_string(adapter, "description", label)

    skills = manifest.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ManifestError("skills must be a non-empty list")
    skill_ids: set[str] = set()
    skills_by_id: dict[str, dict[str, Any]] = {}
    for index, skill in enumerate(skills):
        label = f"skills[{index}]"
        if not isinstance(skill, dict):
            raise ManifestError(f"{label} must be an object")
        skill_id = _require_string(skill, "id", label)
        if skill_id in skill_ids:
            raise ManifestError(f"duplicate skill id: {skill_id}")
        skill_ids.add(skill_id)
        _require_string(skill, "path", label)
        _require_string(skill, "description", label)
        _require_string_list(skill, "buddies", label)
        _require_string_list(skill, "objects", label)
        skills_by_id[skill_id] = skill

    buddies = manifest.get("buddies")
    if not isinstance(buddies, list) or not buddies:
        raise ManifestError("buddies must be a non-empty list")

    buddy_ids: set[str] = set()
    for index, buddy in enumerate(buddies):
        label = f"buddies[{index}]"
        if not isinstance(buddy, dict):
            raise ManifestError(f"{label} must be an object")
        buddy_id = _require_string(buddy, "id", label)
        if not _BUDDY_ID_RE.match(buddy_id):
            raise ManifestError(f"{label}.id must match /^[a-z][a-z0-9-]*$/")
        if buddy_id in buddy_ids:
            raise ManifestError(f"duplicate buddy id: {buddy_id}")
        buddy_ids.add(buddy_id)
        _require_string(buddy, "label", label)
        _require_string(buddy, "scope", label)
        declared_skills = _require_string_list(buddy, "skills", label)
        permissions = _require_string_list(buddy, "permissions", label)
        for permission in permissions:
            _validate_permission(permission, label)

        for skill_id in declared_skills:
            if skill_id not in skills_by_id:
                raise ManifestError(f"{label}.skills contains unknown skill '{skill_id}'")
            if buddy_id not in skills_by_id[skill_id]["buddies"]:
                raise ManifestError(
                    f"{label}.skills '{skill_id}' missing buddy '{buddy_id}' in skills.{skill_id}.buddies"
                )

    for skill_id, skill in skills_by_id.items():
        for buddy_id in skill["buddies"]:
            if buddy_id not in buddy_ids:
                raise ManifestError(f"skills[{skill_id}].buddies contains unknown buddy '{buddy_id}'")

    return manifest


def buddies_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {buddy["id"]: buddy for buddy in manifest.get("buddies", [])}


def skills_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {skill["id"]: skill for skill in manifest.get("skills", [])}


def get_buddy(manifest: dict[str, Any], buddy_id: str) -> dict[str, Any] | None:
    return buddies_by_id(manifest).get(buddy_id)


def require_buddy(manifest: dict[str, Any], buddy_id: str) -> dict[str, Any]:
    buddy = get_buddy(manifest, buddy_id)
    if buddy is None:
        valid = sorted(buddies_by_id(manifest))
        raise ManifestError(f"Unknown buddy '{buddy_id}'. Valid: {', '.join(valid)}")
    return buddy


def buddy_permissions(manifest: dict[str, Any], buddy_id: str) -> set[str]:
    buddy = require_buddy(manifest, buddy_id)
    return set(buddy.get("permissions", []))


def buddy_skill_docs(manifest: dict[str, Any], buddy_id: str) -> list[dict[str, Any]]:
    buddy = require_buddy(manifest, buddy_id)
    lookup = skills_by_id(manifest)
    docs: list[dict[str, Any]] = []
    for skill_id in buddy.get("skills", []):
        skill = lookup[skill_id]
        docs.append(
            {
                "id": skill["id"],
                "path": skill["path"],
                "description": skill["description"],
                "objects": skill["objects"],
            }
        )
    return docs


def _cmd_print(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    print(json.dumps(manifest, ensure_ascii=True, indent=2))
    return 0


def _cmd_list_buddies(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    for buddy in manifest["buddies"]:
        print(f"{buddy['id']}\t{buddy['label']}\t{buddy['scope']}")
    return 0


def _cmd_show_buddy(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    buddy = require_buddy(manifest, args.buddy_id)
    payload = dict(buddy)
    payload["resolved_skills"] = buddy_skill_docs(manifest, args.buddy_id)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect BuddySwitch env manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)

    cmd_print = subparsers.add_parser("print", help="Print full manifest as JSON")
    cmd_print.set_defaults(func=_cmd_print)

    cmd_list = subparsers.add_parser("list-buddies", help="List buddies")
    cmd_list.set_defaults(func=_cmd_list_buddies)

    cmd_show = subparsers.add_parser("show-buddy", help="Show one buddy profile")
    cmd_show.add_argument("buddy_id")
    cmd_show.set_defaults(func=_cmd_show_buddy)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
