#!/usr/bin/env python3
"""Load and validate the BuddySwitch env manifest.

Manifest skill entries define buddy membership and persistence contract only.
Codex-native skill metadata is validated from package `SKILL.md` frontmatter.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]

from output_schema import OutputSchemaError, normalize_schema_path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
_BUDDY_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_FRONTMATTER_OPEN = "---"
_FRONTMATTER_CLOSE = "---"
ADVISORY_RUNTIME_METADATA_POLICY = "advisory"
DEBUG_API_PERMISSION_SCOPE = "manual_debug_apis"
# Retained for compatibility with older turn-runtime imports.
BROWSER_COCKPIT_HOST_EXECUTION = {
    "execution_mode": "browser-cockpit-native",
    "browser_mode": "headed-only",
    "browser_profile": "instance-browser",
    "browser_executor": "chrome-devtools-cockpit",
    "discovery_mode": "browser-native",
    "login_policy": "mandatory-takeover",
    "fallback_policy": "no-silent-degrade",
    "session_continuity": "instance-cockpit",
    "evidence_capture_level": "medium",
}


class ManifestError(ValueError):
    """Raised when the env manifest is invalid."""


def _strip_toml_comment(line: str) -> str:
    in_quote = False
    escape = False
    for index, char in enumerate(line):
        if char == "\\" and in_quote:
            escape = not escape
            continue
        if char == '"' and not escape:
            in_quote = not in_quote
        if char == "#" and not in_quote:
            return line[:index].rstrip()
        escape = False
    return line.rstrip()


def _split_array_items(raw: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    in_quote = False
    escape = False
    for char in raw:
        if char == "\\" and in_quote:
            escape = not escape
            current.append(char)
            continue
        if char == '"' and not escape:
            in_quote = not in_quote
            current.append(char)
            continue
        if char == "," and not in_quote:
            part = "".join(current).strip()
            if part:
                items.append(part)
            current = []
            continue
        current.append(char)
        escape = False
    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def _parse_toml_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        raise ManifestError("TOML scalar must not be empty")
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.match(r"^-?\d+$", value):
        return int(value)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_toml_scalar(item) for item in _split_array_items(inner)]
    return value


def _parse_toml_array(
    *,
    raw: str,
    lines: list[str],
    index: int,
    path: Path,
) -> tuple[list[Any], int]:
    stripped = raw.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return _parse_toml_scalar(stripped), index  # type: ignore[return-value]
    if stripped != "[":
        raise ManifestError(f"Invalid TOML array syntax in {path}: {raw}")

    items: list[Any] = []
    pointer = index + 1
    while pointer < len(lines):
        line = _strip_toml_comment(lines[pointer]).strip()
        if not line:
            pointer += 1
            continue
        if line == "]":
            return items, pointer
        if line.endswith(","):
            line = line[:-1].rstrip()
        items.append(_parse_toml_scalar(line))
        pointer += 1

    raise ManifestError(f"Invalid TOML in {path}: unterminated array")


def _load_toml(path: Path) -> dict[str, Any]:
    if tomllib is not None:
        try:
            return tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - delegated to stdlib parser
            raise ManifestError(f"Invalid TOML in {path}: {exc}") from exc

    lines = path.read_text(encoding="utf-8").splitlines()
    manifest: dict[str, Any] = {}
    current: dict[str, Any] | None = manifest
    pointer = 0

    while pointer < len(lines):
        line = _strip_toml_comment(lines[pointer]).strip()
        if not line:
            pointer += 1
            continue

        if line.startswith("[[") and line.endswith("]]"):
            section = line[2:-2].strip()
            if not section:
                raise ManifestError(f"Invalid TOML in {path}: empty [[section]] name")
            node = manifest.get(section)
            if node is None:
                manifest[section] = []
                node = manifest[section]
            if not isinstance(node, list):
                raise ManifestError(f"Invalid TOML in {path}: [[{section}]] conflicts with table value")
            entry: dict[str, Any] = {}
            node.append(entry)
            current = entry
            pointer += 1
            continue

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            if not section:
                raise ManifestError(f"Invalid TOML in {path}: empty [section] name")
            entry = manifest.get(section)
            if entry is None:
                entry = {}
                manifest[section] = entry
            if not isinstance(entry, dict):
                raise ManifestError(f"Invalid TOML in {path}: [{section}] conflicts with array-table")
            current = entry
            pointer += 1
            continue

        if "=" not in line:
            raise ManifestError(f"Invalid TOML in {path}: expected key/value, got '{line}'")
        if current is None:
            raise ManifestError(f"Invalid TOML in {path}: key/value outside table: '{line}'")

        key, raw = line.split("=", 1)
        key = key.strip()
        raw = raw.strip()
        if not key:
            raise ManifestError(f"Invalid TOML in {path}: empty key in line '{line}'")

        if raw.startswith("["):
            value, pointer = _parse_toml_array(raw=raw, lines=lines, index=pointer, path=path)
        else:
            value = _parse_toml_scalar(raw)
        current[key] = value
        pointer += 1

    return manifest


def _require_string(node: dict[str, Any], key: str, label: str) -> str:
    value = node.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def _require_string_list(node: dict[str, Any], key: str, label: str, *, allow_empty: bool = False) -> list[str]:
    value = node.get(key)
    if not isinstance(value, list) or (not allow_empty and not value):
        message = f"{label}.{key} must be a list" if allow_empty else f"{label}.{key} must be a non-empty list"
        raise ManifestError(message)
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ManifestError(f"{label}.{key} must contain only non-empty strings")
        cleaned.append(item.strip())
    return cleaned


def _validate_permission(permission: str, label: str) -> None:
    if "." not in permission:
        raise ManifestError(f"{label} permission '{permission}' must use '<object>.<action>' format")
    obj, action = permission.split(".", 1)
    if obj not in {"track", "artifact", "task"}:
        raise ManifestError(f"{label} permission '{permission}' has unsupported object '{obj}'")
    if not action:
        raise ManifestError(f"{label} permission '{permission}' has empty action")


def _unwrap_quoted_scalar(value: str) -> str:
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        return value[1:-1]
    return value


def _parse_skill_frontmatter(skill_md: Path) -> dict[str, str]:
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_OPEN:
        raise ManifestError(f"{skill_md.relative_to(ROOT)} must start with YAML frontmatter")

    close_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_CLOSE:
            close_index = index
            break
    if close_index is None:
        raise ManifestError(f"{skill_md.relative_to(ROOT)} frontmatter must end with closing '---'")

    parsed: dict[str, str] = {}
    for raw in lines[1:close_index]:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ManifestError(f"{skill_md.relative_to(ROOT)} frontmatter line must use key: value syntax: '{raw}'")
        key, value = line.split(":", 1)
        key = key.strip()
        value = _unwrap_quoted_scalar(value.strip())
        if not key:
            raise ManifestError(f"{skill_md.relative_to(ROOT)} frontmatter key must not be empty")
        parsed[key] = value
    return parsed


def _resolve_skill_package_root(skill_path: str, label: str) -> Path:
    path_obj = Path(skill_path)
    if path_obj.is_absolute():
        raise ManifestError(f"{label}.path must be repo-relative, got absolute path: {skill_path}")
    resolved = (ROOT / path_obj).resolve(strict=False)
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ManifestError(f"{label}.path must stay within repository root: {skill_path}") from exc
    return resolved


def _validate_skill_package(package_root: Path, skill_id: str) -> None:
    if not package_root.exists() or not package_root.is_dir():
        raise ManifestError(f"Skill package not found: {package_root.relative_to(ROOT)}")

    skill_toml = package_root / "skill.toml"
    if skill_toml.exists():
        raise ManifestError(f"{skill_toml.relative_to(ROOT)} is not allowed; use SKILL.md frontmatter only")

    skill_md = package_root / "SKILL.md"
    if not skill_md.exists() or not skill_md.is_file():
        raise ManifestError(f"{skill_md.relative_to(ROOT)} not found")

    parsed = _parse_skill_frontmatter(skill_md)
    name = parsed.get("name", "").strip()
    if not name:
        raise ManifestError(f"{skill_md.relative_to(ROOT)} frontmatter must include non-empty name")
    if name != skill_id:
        raise ManifestError(
            f"{skill_md.relative_to(ROOT)} frontmatter name '{name}' must match manifest skill id '{skill_id}'"
        )
    description = parsed.get("description", "").strip()
    if not description:
        raise ManifestError(f"{skill_md.relative_to(ROOT)} frontmatter must include non-empty description")


def _parse_skill_persistence(skill: dict[str, Any], label: str, skill_id: str) -> dict[str, Any]:
    produces_artifact = skill.get("produces_artifact")
    if not isinstance(produces_artifact, bool):
        raise ManifestError(f"{label}.produces_artifact must be true or false")

    output_schema_raw = skill.get("output_schema")
    if not isinstance(output_schema_raw, str) or not output_schema_raw.strip():
        raise ManifestError(f"{label}.output_schema must be a non-empty string")
    try:
        output_schema = normalize_schema_path(output_schema_raw.strip())
    except OutputSchemaError as exc:
        raise ManifestError(f"{label}.output_schema invalid: {exc}") from exc
    if not (ROOT / output_schema).exists():
        raise ManifestError(f"{label}.output_schema file not found: {output_schema}")

    output_slot_raw = skill.get("output_slot")
    if not produces_artifact:
        raise ManifestError("produces_artifact=false is not supported")
    if not isinstance(output_slot_raw, str) or not output_slot_raw.strip():
        raise ManifestError(f"{label}.output_slot is required when produces_artifact=true")
    output_slot = output_slot_raw.strip()

    return {
        "produces_artifact": produces_artifact,
        "output_slot": output_slot,
        "output_schema": output_schema,
    }


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")

    manifest = _load_toml(path)

    schema_version = manifest.get("schema_version")
    if schema_version != 1:
        raise ManifestError("schema_version must be 1")

    env_node = manifest.get("env")
    if not isinstance(env_node, dict):
        raise ManifestError("env section is required")
    _require_string(env_node, "id", "env")
    _require_string(env_node, "label", "env")

    skills = manifest.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ManifestError("skills must be a non-empty list")

    skill_ids: set[str] = set()
    skill_lookup: dict[str, dict[str, Any]] = {}
    for index, skill in enumerate(skills):
        label = f"skills[{index}]"
        if not isinstance(skill, dict):
            raise ManifestError(f"{label} must be an object")

        skill_id = _require_string(skill, "id", label)
        if skill_id in skill_ids:
            raise ManifestError(f"duplicate skill id: {skill_id}")
        skill_ids.add(skill_id)

        skill_path = _require_string(skill, "path", label)
        package_root = _resolve_skill_package_root(skill_path, label)
        _validate_skill_package(package_root, skill_id)

        persistence = _parse_skill_persistence(skill, label, skill_id)
        skill["path"] = skill_path
        skill["persistence"] = persistence
        skill_lookup[skill_id] = skill

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
        declared_skills = _require_string_list(buddy, "skills", label, allow_empty=True)
        permissions = _require_string_list(buddy, "permissions", label)
        for permission in permissions:
            _validate_permission(permission, label)
        for declared_skill in declared_skills:
            if declared_skill not in skill_lookup:
                raise ManifestError(f"{label}.skills contains unknown skill '{declared_skill}'")

    return manifest


def buddies_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {buddy["id"]: buddy for buddy in manifest.get("buddies", []) if isinstance(buddy, dict)}


def skills_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {skill["id"]: skill for skill in manifest.get("skills", []) if isinstance(skill, dict)}


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


def buddy_authority_profile(manifest: dict[str, Any], buddy_id: str) -> dict[str, Any]:
    buddy = require_buddy(manifest, buddy_id)
    return {
        "routing_skills": list(buddy.get("skills", [])),
        "object_permissions": list(buddy.get("permissions", [])),
        "permission_scope": DEBUG_API_PERMISSION_SCOPE,
        "runtime_note": (
            "buddy->skills controls which runtime packages are materialized under .agents/skills, "
            "and persist accepts only skill_id values from that active membership. "
            "object permission enforcement remains in manual/debug mutation APIs."
        ),
    }


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
                "persistence": dict(skill.get("persistence", {})),
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
    payload["authority"] = buddy_authority_profile(manifest, args.buddy_id)
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
