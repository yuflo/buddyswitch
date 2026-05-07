#!/usr/bin/env python3
"""Load and validate BuddySwitch buddy environment profiles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from env_manifest import DEFAULT_MANIFEST, ManifestError, load_manifest, require_buddy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "framework" / "contracts" / "buddy-env-profile.json"
_SAFE_BUDDY_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class EnvProfileError(ValueError):
    """Raised when a BuddySwitch env profile is missing or invalid."""


def env_profiles_root(root: Path | None = None) -> Path:
    base = root if root is not None else ROOT
    return Path(base) / "buddyswitch" / "env-profiles"


def env_profile_path(buddy_id: str, root: Path | None = None) -> Path:
    if not isinstance(buddy_id, str) or not _SAFE_BUDDY_ID_RE.match(buddy_id):
        raise EnvProfileError(
            "buddy_id must match /^[a-z][a-z0-9-]*$/ for env profile lookup; "
            f"got {buddy_id!r}"
        )
    return env_profiles_root(root) / f"{buddy_id}.json"


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EnvProfileError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EnvProfileError(f"{label} is not valid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise EnvProfileError(f"failed reading {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EnvProfileError(f"{label} must be a JSON object: {path}")
    return payload


def profile_contract(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root) if root is not None else ROOT
    path = repo_root / "framework" / "contracts" / "buddy-env-profile.json"
    if path == DEFAULT_CONTRACT:
        path = DEFAULT_CONTRACT
    return _load_json_object(path, label="env profile contract")


def load_env_profile(buddy_id: str, root: Path | None = None) -> dict[str, Any]:
    path = env_profile_path(buddy_id, root)
    return _load_json_object(path, label="env profile")


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EnvProfileError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnvProfileError(f"{label} must be a non-empty string")
    return value.strip()


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise EnvProfileError(f"{label} must be a list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise EnvProfileError(f"{label} must contain non-empty strings")
        out.append(item.strip())
    return out


def _require_enum(
    *,
    enums: dict[str, Any],
    key: str,
    value: Any,
    label: str,
) -> str:
    choices = enums.get(key)
    if not isinstance(choices, list) or not choices:
        raise EnvProfileError(f"contract enum missing for '{key}'")
    text = _require_string(value, label)
    if text not in choices:
        raise EnvProfileError(f"{label} must be one of {choices}; got {text!r}")
    return text


def _manifest_buddy_ids(manifest: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for buddy in manifest.get("buddies", []):
        if isinstance(buddy, dict) and isinstance(buddy.get("id"), str):
            ids.append(buddy["id"])
    return ids


def validate_env_profile(
    profile: dict[str, Any],
    *,
    buddy_id: str,
    manifest: dict[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root) if repo_root is not None else ROOT
    contract = profile_contract(repo)
    require_buddy(manifest, buddy_id)

    top_level_order = contract.get("top_level_key_order")
    required_top_level = contract.get("required_top_level_keys")
    enums = contract.get("enums")
    if not isinstance(top_level_order, list) or not all(isinstance(item, str) for item in top_level_order):
        raise EnvProfileError("contract top_level_key_order must be a string list")
    if not isinstance(required_top_level, list) or not all(isinstance(item, str) for item in required_top_level):
        raise EnvProfileError("contract required_top_level_keys must be a string list")
    if not isinstance(enums, dict):
        raise EnvProfileError("contract enums must be an object")

    missing = [key for key in required_top_level if key not in profile]
    if missing:
        raise EnvProfileError(f"profile missing required top-level keys: {missing}")
    unexpected = [key for key in profile.keys() if key not in required_top_level]
    if unexpected:
        raise EnvProfileError(f"profile contains unsupported top-level keys: {unexpected}")
    if list(profile.keys()) != top_level_order:
        raise EnvProfileError("profile top-level key order does not match contract")

    actual_buddy_id = _require_string(profile.get("buddy_id"), "buddy_id")
    if actual_buddy_id != buddy_id:
        raise EnvProfileError(
            f"profile buddy_id mismatch: expected {buddy_id!r}, got {actual_buddy_id!r}"
        )
    if not _SAFE_BUDDY_ID_RE.match(actual_buddy_id):
        raise EnvProfileError(f"profile buddy_id is invalid: {actual_buddy_id!r}")

    contract_path = _require_string(profile.get("contract_path"), "contract_path")
    expected_contract_path = f"framework/contracts/{buddy_id}.md"
    if contract_path != expected_contract_path:
        raise EnvProfileError(
            f"contract_path mismatch for '{buddy_id}': expected {expected_contract_path!r}, got {contract_path!r}"
        )
    resolved_contract_path = repo / contract_path
    if not resolved_contract_path.exists():
        raise EnvProfileError(f"contract_path does not exist: {resolved_contract_path}")

    project = _require_dict(profile.get("project"), "project")
    _require_enum(
        enums=enums,
        key="project.visibility",
        value=project.get("visibility"),
        label="project.visibility",
    )
    project_access = _require_enum(
        enums=enums,
        key="project.access",
        value=project.get("access"),
        label="project.access",
    )
    project_path = _require_string(project.get("path"), "project.path")
    if project_path != "projects/app":
        raise EnvProfileError(f"project.path must be 'projects/app', got {project_path!r}")

    scratch = _require_dict(profile.get("scratch"), "scratch")
    scratch_root = _require_string(scratch.get("root"), "scratch.root")
    expected_scratch_root = f"runs/raw/{buddy_id}"
    if scratch_root != expected_scratch_root:
        raise EnvProfileError(
            f"scratch.root mismatch for '{buddy_id}': expected {expected_scratch_root!r}, got {scratch_root!r}"
        )

    fs_capability = _require_dict(profile.get("filesystem_capability"), "filesystem_capability")
    host_writable = _require_string_list(fs_capability.get("host_writable"), "filesystem_capability.host_writable")
    project_workspace_access = _require_enum(
        enums=enums,
        key="filesystem_capability.project_workspace",
        value=fs_capability.get("project_workspace"),
        label="filesystem_capability.project_workspace",
    )
    _require_enum(
        enums=enums,
        key="filesystem_capability.raw_state",
        value=fs_capability.get("raw_state"),
        label="filesystem_capability.raw_state",
    )

    expected_host_writable = ["home", "codex-home", "xdg-config", "scratch", "temp"]
    if buddy_id == "dev":
        expected_host_writable = [*expected_host_writable, "project-workspace"]
    if host_writable != expected_host_writable:
        raise EnvProfileError(
            f"filesystem_capability.host_writable mismatch for '{buddy_id}': "
            f"expected {expected_host_writable}, got {host_writable}"
        )

    state_capability = _require_dict(profile.get("state_capability"), "state_capability")
    _require_enum(
        enums=enums,
        key="state_capability.artifact_kinds",
        value=state_capability.get("artifact_kinds"),
        label="state_capability.artifact_kinds",
    )
    task_effects = _require_string_list(state_capability.get("task_effects"), "state_capability.task_effects")
    if task_effects != ["status", "summary"]:
        raise EnvProfileError(
            "state_capability.task_effects must be exactly ['status', 'summary']"
        )
    track_effects = _require_string_list(state_capability.get("track_effects"), "state_capability.track_effects")
    expected_track_effects = ["create", "update", "advance", "archive"] if buddy_id == "pm" else []
    if track_effects != expected_track_effects:
        raise EnvProfileError(
            f"state_capability.track_effects mismatch for '{buddy_id}': "
            f"expected {expected_track_effects}, got {track_effects}"
        )
    _require_enum(
        enums=enums,
        key="state_capability.handoff_targets",
        value=state_capability.get("handoff_targets"),
        label="state_capability.handoff_targets",
    )

    tool_capability = _require_dict(profile.get("tool_capability"), "tool_capability")
    browser_cockpit = _require_enum(
        enums=enums,
        key="tool_capability.browser_cockpit",
        value=tool_capability.get("browser_cockpit"),
        label="tool_capability.browser_cockpit",
    )
    market_evidence = _require_enum(
        enums=enums,
        key="tool_capability.market_research_evidence",
        value=tool_capability.get("market_research_evidence"),
        label="tool_capability.market_research_evidence",
    )
    ordinary_web_fallback = _require_enum(
        enums=enums,
        key="tool_capability.ordinary_web_fallback",
        value=tool_capability.get("ordinary_web_fallback"),
        label="tool_capability.ordinary_web_fallback",
    )

    context_projection = _require_dict(profile.get("context_projection"), "context_projection")
    _require_enum(
        enums=enums,
        key="context_projection.agents_md",
        value=context_projection.get("agents_md"),
        label="context_projection.agents_md",
    )
    _require_enum(
        enums=enums,
        key="context_projection.skills",
        value=context_projection.get("skills"),
        label="context_projection.skills",
    )

    expected_project_access = "write" if buddy_id == "dev" else "read-only"
    expected_workspace_access = "write" if buddy_id == "dev" else "read-only"
    if project_access != expected_project_access:
        raise EnvProfileError(
            f"project.access mismatch for '{buddy_id}': expected {expected_project_access!r}, got {project_access!r}"
        )
    if project_workspace_access != expected_workspace_access:
        raise EnvProfileError(
            "filesystem_capability.project_workspace mismatch for "
            f"'{buddy_id}': expected {expected_workspace_access!r}, got {project_workspace_access!r}"
        )

    if buddy_id == "market":
        if browser_cockpit != "required":
            raise EnvProfileError("market profile must set tool_capability.browser_cockpit to 'required'")
        if market_evidence != "required":
            raise EnvProfileError("market profile must require market_research_evidence")
        if ordinary_web_fallback != "user-approved-only":
            raise EnvProfileError("market profile ordinary_web_fallback must be 'user-approved-only'")
    else:
        if browser_cockpit != "available":
            raise EnvProfileError(f"{buddy_id} profile browser_cockpit must be 'available'")
        if market_evidence != "not-required":
            raise EnvProfileError(f"{buddy_id} profile market_research_evidence must be 'not-required'")
        if ordinary_web_fallback != "available":
            raise EnvProfileError(f"{buddy_id} profile ordinary_web_fallback must be 'available'")

    normalized: dict[str, Any] = {}
    for key in top_level_order:
        normalized[key] = profile[key]

    manifest_buddies = _manifest_buddy_ids(manifest)
    if buddy_id not in manifest_buddies:
        raise EnvProfileError(f"buddy '{buddy_id}' is not in manifest")
    return normalized


def require_env_profile(
    buddy_id: str,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    try:
        manifest = load_manifest(manifest_path)
        require_buddy(manifest, buddy_id)
    except ManifestError as exc:
        raise EnvProfileError(str(exc)) from exc

    profile = load_env_profile(buddy_id, repo_root)
    return validate_env_profile(
        profile,
        buddy_id=buddy_id,
        manifest=manifest,
        repo_root=repo_root,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BuddySwitch env profiles.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Manifest TOML path")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="Repo root containing env profiles")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate one profile")
    validate.add_argument("--buddy", required=True, help="Buddy id")

    sub.add_parser("validate-all", help="Validate profiles for all manifest buddies")

    show = sub.add_parser("show", help="Show one normalized profile")
    show.add_argument("--buddy", required=True, help="Buddy id")
    return parser.parse_args()


def _cmd_validate(args: argparse.Namespace) -> int:
    profile = require_env_profile(
        args.buddy,
        manifest_path=args.manifest,
        repo_root=args.repo_root,
    )
    print(f"{profile['buddy_id']}: ok")
    return 0


def _cmd_validate_all(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    for buddy in manifest.get("buddies", []):
        if not isinstance(buddy, dict):
            continue
        buddy_id = buddy.get("id")
        if not isinstance(buddy_id, str):
            continue
        require_env_profile(
            buddy_id,
            manifest_path=args.manifest,
            repo_root=args.repo_root,
        )
        print(f"{buddy_id}: ok")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    profile = require_env_profile(
        args.buddy,
        manifest_path=args.manifest,
        repo_root=args.repo_root,
    )
    print(json.dumps(profile, ensure_ascii=True, indent=2))
    return 0


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "validate":
            return _cmd_validate(args)
        if args.command == "validate-all":
            return _cmd_validate_all(args)
        if args.command == "show":
            return _cmd_show(args)
        raise EnvProfileError(f"unsupported command: {args.command}")
    except (EnvProfileError, ManifestError) as exc:
        print(f"Env profile invalid: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
