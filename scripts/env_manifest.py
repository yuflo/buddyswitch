#!/usr/bin/env python3
"""Load and validate the BuddySwitch env manifest and skill runtime metadata.

`required_tools` and `required_env` are advisory runtime metadata for the host
session. Buddy `permissions` describe object authority for routing context and
manual/debug mutation APIs; they are not a second runtime permission engine.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]
from pathlib import Path
from typing import Any

from output_schema import OutputSchemaError, normalize_schema_path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "buddyswitch" / "manifest.toml"
_BUDDY_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_SKILL_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+\s*:")
TRACK_MODES = {"optional", "required", "forbidden"}
ADVISORY_RUNTIME_METADATA_POLICY = "advisory"
DEBUG_API_PERMISSION_SCOPE = "manual_debug_apis"
GUIDANCE_HEADINGS = {
    "purpose": "purpose",
    "use when": "use_when",
    "do not use when": "do_not_use_when",
    "inputs": "inputs",
    "outputs": "outputs",
    "verification": "verification",
    "examples": "examples",
    "counterexamples": "counterexamples",
    "gotchas": "gotchas",
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
    # Allow root-level key/value entries before any [section], e.g. `schema_version = 1`.
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


def _require_string_list(node: dict[str, Any], key: str, label: str) -> list[str]:
    value = node.get(key)
    if not isinstance(value, list) or not value:
        raise ManifestError(f"{label}.{key} must be a non-empty list")
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


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1].strip()
    return value


def _parse_scalar(value: str, label: str) -> Any:
    raw = _strip_quotes(value)
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_strip_quotes(part.strip()) for part in inner.split(",") if part.strip()]
    if not raw:
        raise ManifestError(f"{label} must not be empty")
    return raw


def _parse_skill_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise ManifestError(f"{path.relative_to(ROOT)} must start with '---' front matter")

    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise ManifestError(f"{path.relative_to(ROOT)} front matter is missing closing '---'")

    block = lines[1:end]
    data: dict[str, Any] = {}
    i = 0
    while i < len(block):
        line = block[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", stripped)
        if not match:
            raise ManifestError(f"Invalid front matter line in {path.relative_to(ROOT)}: {stripped}")
        key = match.group(1)
        value = match.group(2).strip()

        if value:
            data[key] = _parse_scalar(value, f"{path.relative_to(ROOT)}:{key}")
            i += 1
            continue

        # Parse multiline list values:
        items: list[Any] = []
        i += 1
        while i < len(block):
            next_line = block[i]
            next_stripped = next_line.strip()
            if not next_stripped:
                i += 1
                continue
            if _SKILL_KEY_RE.match(next_stripped) and not next_stripped.startswith("-"):
                break
            item_match = re.match(r"^\s*-\s*(.+)\s*$", next_line)
            if not item_match:
                raise ManifestError(
                    f"Invalid list item for '{key}' in {path.relative_to(ROOT)}: {next_stripped}"
                )
            items.append(_parse_scalar(item_match.group(1), f"{path.relative_to(ROOT)}:{key}"))
            i += 1
        data[key] = items

    return data


def _split_front_matter(path: Path) -> tuple[dict[str, Any], list[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise ManifestError(f"{path.relative_to(ROOT)} must start with '---' front matter")

    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        raise ManifestError(f"{path.relative_to(ROOT)} front matter is missing closing '---'")

    block = lines[1:end]
    data: dict[str, Any] = {}
    i = 0
    while i < len(block):
        line = block[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", stripped)
        if not match:
            raise ManifestError(f"Invalid front matter line in {path.relative_to(ROOT)}: {stripped}")
        key = match.group(1)
        value = match.group(2).strip()

        if value:
            data[key] = _parse_scalar(value, f"{path.relative_to(ROOT)}:{key}")
            i += 1
            continue

        items: list[Any] = []
        i += 1
        while i < len(block):
            next_line = block[i]
            next_stripped = next_line.strip()
            if not next_stripped:
                i += 1
                continue
            if _SKILL_KEY_RE.match(next_stripped) and not next_stripped.startswith("-"):
                break
            item_match = re.match(r"^\s*-\s*(.+)\s*$", next_line)
            if not item_match:
                raise ManifestError(
                    f"Invalid list item for '{key}' in {path.relative_to(ROOT)}: {next_stripped}"
                )
            items.append(_parse_scalar(item_match.group(1), f"{path.relative_to(ROOT)}:{key}"))
            i += 1
        data[key] = items

    return data, lines[end + 1 :]


def _normalize_section_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("- "):
            cleaned.append(line[2:].strip())
            continue
        numbered = re.match(r"^\d+\.\s+(.*)$", line)
        if numbered:
            cleaned.append(numbered.group(1).strip())
            continue
        cleaned.append(line)
    return cleaned


def _parse_skill_guidance(path: Path, body_lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {value: [] for value in GUIDANCE_HEADINGS.values()}
    current_key: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if current_key is None:
            buffer = []
            return
        sections[current_key] = _normalize_section_lines(buffer)
        buffer = []

    for line in body_lines:
        stripped = line.strip()
        heading = re.match(r"^##\s+(.+?)\s*$", stripped)
        if heading:
            flush()
            current_key = GUIDANCE_HEADINGS.get(heading.group(1).strip().lower())
            continue
        if current_key is not None:
            buffer.append(line)

    flush()

    missing = [label for label, key in GUIDANCE_HEADINGS.items() if not sections[key]]
    if missing:
        raise ManifestError(
            f"{path.relative_to(ROOT)} is missing required guidance section(s): {', '.join(missing)}"
        )
    return sections


def _load_skill_runtime(path: Path, skill_id: str) -> dict[str, Any]:
    if not path.exists():
        raise ManifestError(f"Skill file not found: {path.relative_to(ROOT)}")
    front, body_lines = _split_front_matter(path)

    required = ("name", "description", "track_mode", "default_artifact_kind", "auto_summary", "output_schema")
    missing = [key for key in required if key not in front]
    if missing:
        raise ManifestError(
            f"{path.relative_to(ROOT)} is missing required front matter key(s): {', '.join(missing)}"
        )

    name = front["name"]
    if not isinstance(name, str) or not name.strip():
        raise ManifestError(f"{path.relative_to(ROOT)}:name must be a non-empty string")
    if name.strip() != skill_id:
        raise ManifestError(
            f"{path.relative_to(ROOT)}:name '{name}' must match manifest skill id '{skill_id}'"
        )

    description = front["description"]
    if not isinstance(description, str) or not description.strip():
        raise ManifestError(f"{path.relative_to(ROOT)}:description must be a non-empty string")

    track_mode = front["track_mode"]
    if not isinstance(track_mode, str) or track_mode not in TRACK_MODES:
        raise ManifestError(
            f"{path.relative_to(ROOT)}:track_mode must be one of {', '.join(sorted(TRACK_MODES))}"
        )

    artifact_kind = front["default_artifact_kind"]
    if not isinstance(artifact_kind, str) or not artifact_kind.strip():
        raise ManifestError(f"{path.relative_to(ROOT)}:default_artifact_kind must be a non-empty string")

    auto_summary = front["auto_summary"]
    if not isinstance(auto_summary, bool):
        raise ManifestError(f"{path.relative_to(ROOT)}:auto_summary must be true or false")

    output_schema = front["output_schema"]
    if not isinstance(output_schema, str) or not output_schema.strip():
        raise ManifestError(f"{path.relative_to(ROOT)}:output_schema must be a non-empty string")
    try:
        normalized_schema = normalize_schema_path(output_schema.strip())
    except OutputSchemaError as exc:
        raise ManifestError(f"{path.relative_to(ROOT)}:output_schema invalid: {exc}") from exc
    if not (ROOT / normalized_schema).exists():
        raise ManifestError(f"{path.relative_to(ROOT)}:output_schema file not found: {normalized_schema}")

    version = front.get("version")
    if version is not None and (not isinstance(version, str) or not version.strip()):
        raise ManifestError(f"{path.relative_to(ROOT)}:version must be a non-empty string when provided")

    side_effect_level = front.get("side_effect_level")
    if side_effect_level is not None and (not isinstance(side_effect_level, str) or not side_effect_level.strip()):
        raise ManifestError(
            f"{path.relative_to(ROOT)}:side_effect_level must be a non-empty string when provided"
        )

    optional_lists: dict[str, list[str]] = {}
    for key in ("required_tools", "required_env", "produces", "consumes"):
        raw = front.get(key, [])
        if not isinstance(raw, list):
            raise ManifestError(f"{path.relative_to(ROOT)}:{key} must be a list when provided")
        cleaned: list[str] = []
        for item in raw:
            if not isinstance(item, str) or not item.strip():
                raise ManifestError(f"{path.relative_to(ROOT)}:{key} must contain non-empty strings")
            cleaned.append(item.strip())
        optional_lists[key] = cleaned

    guidance = _parse_skill_guidance(path, body_lines)

    return {
        "name": name.strip(),
        "description": description.strip(),
        "track_mode": track_mode,
        "default_artifact_kind": artifact_kind.strip(),
        "auto_summary": auto_summary,
        "output_schema": normalized_schema,
        "version": version.strip() if isinstance(version, str) else None,
        "side_effect_level": side_effect_level.strip() if isinstance(side_effect_level, str) else None,
        "required_tools": optional_lists["required_tools"],
        "required_env": optional_lists["required_env"],
        "produces": optional_lists["produces"],
        "consumes": optional_lists["consumes"],
        "guidance": guidance,
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
    lookup: dict[str, dict[str, Any]] = {}
    for index, skill in enumerate(skills):
        label = f"skills[{index}]"
        if not isinstance(skill, dict):
            raise ManifestError(f"{label} must be an object")
        skill_id = _require_string(skill, "id", label)
        if skill_id in skill_ids:
            raise ManifestError(f"duplicate skill id: {skill_id}")
        skill_ids.add(skill_id)
        skill["path"] = _require_string(skill, "path", label)
        skill["description"] = _require_string(skill, "description", label)
        skill["buddies"] = _require_string_list(skill, "buddies", label)
        skill["objects"] = _require_string_list(skill, "objects", label)
        skill_path = ROOT / skill["path"]
        skill["runtime"] = _load_skill_runtime(skill_path, skill_id)
        lookup[skill_id] = skill

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
            if skill_id not in lookup:
                raise ManifestError(f"{label}.skills contains unknown skill '{skill_id}'")
            if buddy_id not in lookup[skill_id]["buddies"]:
                raise ManifestError(
                    f"{label}.skills '{skill_id}' missing buddy '{buddy_id}' in skills[{skill_id}].buddies"
                )

    for skill_id, skill in lookup.items():
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


def buddy_authority_profile(manifest: dict[str, Any], buddy_id: str) -> dict[str, Any]:
    buddy = require_buddy(manifest, buddy_id)
    return {
        "routing_skills": list(buddy.get("skills", [])),
        "object_permissions": list(buddy.get("permissions", [])),
        "permission_scope": DEBUG_API_PERMISSION_SCOPE,
        "runtime_note": (
            "switch runtime uses buddy->skills as routing authority and leaves "
            "object permission enforcement to manual/debug mutation APIs."
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
                "description": skill["description"],
                "objects": skill["objects"],
                "runtime": dict(skill.get("runtime", {})),
                "guidance": dict(skill.get("runtime", {}).get("guidance", {})),
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
