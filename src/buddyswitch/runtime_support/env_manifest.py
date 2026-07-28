"""Load and validate the BuddySwitch env manifest.

Manifest skill entries define role membership and package paths.
Role rows define routing skills and artifact templates.
Codex-native package acceptance is owned by Codex after materialization.
Env tool role-action authority is owned by the runtime tool dispatch policy.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PACKAGE_ROOT / "catalog" / "manifest.toml"
_SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_VALID_ARTIFACT_TEMPLATES = ("brief", "proposal", "design", "decision", "proof", "note")
_LEGACY_ARTIFACT_KINDS_KEY = "artifact_" + "kinds"
ADVISORY_RUNTIME_METADATA_POLICY = "advisory"
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

_LEGACY_KIND_TEMPLATE_MAP: dict[str, str] = {}
for _kind in {
    "prd",
    "scope-brief",
    "insight-brief",
    "market-scan",
    "pmf-report",
    "customer-discovery",
    "positioning-brief",
    "channel-plan",
    "launch-prep",
    "track-note",
    "prototype-brief",
    "implementation-report",
}:
    _LEGACY_KIND_TEMPLATE_MAP[_kind] = "brief"
for _kind in {"solution-spec", "technical-proposal", "proposal"}:
    _LEGACY_KIND_TEMPLATE_MAP[_kind] = "proposal"
_LEGACY_KIND_TEMPLATE_MAP["design-handoff"] = "design"
for _kind in {"pm-decision", "decision"}:
    _LEGACY_KIND_TEMPLATE_MAP[_kind] = "decision"
for _kind in {"verification-proof", "smoke-test", "test-report"}:
    _LEGACY_KIND_TEMPLATE_MAP[_kind] = "proof"


def _legacy_kind_to_template(kind: str) -> str:
    return _LEGACY_KIND_TEMPLATE_MAP.get(kind, "note")


class ManifestError(ValueError):
    """Raised when the env manifest is invalid."""


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - delegated to stdlib parser
        raise ManifestError(f"Invalid TOML in {path}: {exc}") from exc


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
        skill["path"] = skill_path
        skill_lookup[skill_id] = skill

    roles = manifest.get("roles")
    if not isinstance(roles, list) or not roles:
        raise ManifestError("roles must be a non-empty list")

    role_ids: set[str] = set()
    for index, role in enumerate(roles):
        label = f"roles[{index}]"
        if not isinstance(role, dict):
            raise ManifestError(f"{label} must be an object")

        role_id = _require_string(role, "id", label)
        if not _SAFE_ID_RE.match(role_id):
            raise ManifestError(f"{label}.id must match /^[a-z][a-z0-9-]*$/")
        if role_id in role_ids:
            raise ManifestError(f"duplicate role id: {role_id}")
        role_ids.add(role_id)

        _require_string(role, "label", label)
        _require_string(role, "scope", label)
        if "permissions" in role:
            raise ManifestError(f"{label}.permissions is retired; role-action authority is owned by env.tool runtime policy")
        declared_skills = _require_string_list(role, "skills", label, allow_empty=True)
        raw_templates = role.get("artifact_templates")
        normalized_artifact_templates: list[str] = []
        if raw_templates is None:
            legacy_kinds = _require_string_list(role, _LEGACY_ARTIFACT_KINDS_KEY, label)
            seen_templates: set[str] = set()
            for artifact_kind in legacy_kinds:
                if not _SAFE_ID_RE.match(artifact_kind):
                    raise ManifestError(
                        f"{label}.{_LEGACY_ARTIFACT_KINDS_KEY} values must match /^[a-z][a-z0-9-]*$/; got '{artifact_kind}'"
                    )
                template = _legacy_kind_to_template(artifact_kind)
                if template in seen_templates:
                    continue
                seen_templates.add(template)
                normalized_artifact_templates.append(template)
        else:
            artifact_templates = _require_string_list(role, "artifact_templates", label)
            seen_artifact_templates: set[str] = set()
            for artifact_template in artifact_templates:
                if artifact_template not in _VALID_ARTIFACT_TEMPLATES:
                    raise ManifestError(
                        f"{label}.artifact_templates must contain only {', '.join(_VALID_ARTIFACT_TEMPLATES)}; "
                        f"got '{artifact_template}'"
                    )
                if artifact_template in seen_artifact_templates:
                    raise ManifestError(
                        f"{label}.artifact_templates contains duplicate value '{artifact_template}'"
                    )
                seen_artifact_templates.add(artifact_template)
                normalized_artifact_templates.append(artifact_template)
        if not normalized_artifact_templates:
            raise ManifestError(f"{label}.artifact_templates must not be empty after normalization")
        role["artifact_templates"] = normalized_artifact_templates
        role.pop(_LEGACY_ARTIFACT_KINDS_KEY, None)
        for declared_skill in declared_skills:
            if declared_skill not in skill_lookup:
                raise ManifestError(f"{label}.skills contains unknown skill '{declared_skill}'")

    return manifest


def roles_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {role["id"]: role for role in manifest.get("roles", []) if isinstance(role, dict)}


def skills_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {skill["id"]: skill for skill in manifest.get("skills", []) if isinstance(skill, dict)}


def get_role(manifest: dict[str, Any], role_id: str) -> dict[str, Any] | None:
    return roles_by_id(manifest).get(role_id)


def require_role(manifest: dict[str, Any], role_id: str) -> dict[str, Any]:
    role = get_role(manifest, role_id)
    if role is None:
        valid = sorted(roles_by_id(manifest))
        raise ManifestError(f"Unknown role '{role_id}'. Valid: {', '.join(valid)}")
    return role


def role_authority_profile(manifest: dict[str, Any], role_id: str) -> dict[str, Any]:
    role = require_role(manifest, role_id)
    return {
        "routing_skills": list(role.get("skills", [])),
        "runtime_note": (
            "role->skills controls which runtime packages are materialized under .agents/skills, "
            "while env.tool role-action authority is computed by the runtime tool dispatch policy."
        ),
    }


def role_skill_docs(manifest: dict[str, Any], role_id: str) -> list[dict[str, Any]]:
    role = require_role(manifest, role_id)
    lookup = skills_by_id(manifest)
    docs: list[dict[str, Any]] = []
    for skill_id in role.get("skills", []):
        skill = lookup[skill_id]
        docs.append(
            {
                "id": skill["id"],
                "path": skill["path"],
            }
        )
    return docs


def _cmd_print(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    print(json.dumps(manifest, ensure_ascii=True, sort_keys=True))
    return 0


def _cmd_list_roles(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    roles = [
        {
            "id": role["id"],
            "label": role["label"],
            "scope": role["scope"],
        }
        for role in manifest["roles"]
    ]
    print(json.dumps({"roles": roles}, ensure_ascii=True, sort_keys=True))
    return 0


def _cmd_show_role(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    role = require_role(manifest, args.role_id)
    payload = dict(role)
    payload["authority"] = role_authority_profile(manifest, args.role_id)
    payload["resolved_skills"] = role_skill_docs(manifest, args.role_id)
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect BuddySwitch env manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)

    cmd_print = subparsers.add_parser("print", help="Print full manifest as JSON")
    cmd_print.set_defaults(func=_cmd_print)

    cmd_list = subparsers.add_parser("list-roles", help="List roles")
    cmd_list.set_defaults(func=_cmd_list_roles)

    cmd_show = subparsers.add_parser("show-role", help="Show one role profile")
    cmd_show.add_argument("role_id")
    cmd_show.set_defaults(func=_cmd_show_role)
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
