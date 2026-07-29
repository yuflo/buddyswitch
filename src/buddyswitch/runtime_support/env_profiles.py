"""Load and validate BuddySwitch role environment profiles."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from buddyswitch.runtime_support.env_manifest import DEFAULT_MANIFEST, ManifestError, load_manifest, require_role

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTRACT = PACKAGE_ROOT / "contracts" / "role-env-profile.json"
_SAFE_ROLE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
PRIVATE_WORKSPACE_ROOT = "private"


class EnvProfileError(ValueError):
    """Raised when a BuddySwitch env profile is missing or invalid."""


def env_profiles_root(root: Path | None = None) -> Path:
    base = root if root is not None else PACKAGE_ROOT
    return Path(base) / "catalog" / "env-profiles"


def env_profile_path(role_id: str, root: Path | None = None) -> Path:
    if not isinstance(role_id, str) or not _SAFE_ROLE_ID_RE.match(role_id):
        raise EnvProfileError(
            "role_id must match /^[a-z][a-z0-9-]*$/ for env profile lookup; "
            f"got {role_id!r}"
        )
    return env_profiles_root(root) / f"{role_id}.json"


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
    package_root = Path(root) if root is not None else PACKAGE_ROOT
    path = package_root / "contracts" / "role-env-profile.json"
    return _load_json_object(path, label="env profile contract")


def load_env_profile(role_id: str, root: Path | None = None) -> dict[str, Any]:
    path = env_profile_path(role_id, root)
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


def _manifest_role_ids(manifest: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for role in manifest.get("roles", []):
        if isinstance(role, dict) and isinstance(role.get("id"), str):
            ids.append(role["id"])
    return ids


def _require_search_capability(
    *,
    tool_capability: dict[str, Any],
    enums: dict[str, Any],
    role_id: str,
    browser_cockpit: str,
) -> dict[str, str]:
    search = _require_dict(tool_capability.get("search"), "tool_capability.search")
    native_codex_web_search = _require_enum(
        enums=enums,
        key="tool_capability.search.native_codex_web_search",
        value=search.get("native_codex_web_search"),
        label="tool_capability.search.native_codex_web_search",
    )
    search_browser_cockpit = _require_enum(
        enums=enums,
        key="tool_capability.search.browser_cockpit",
        value=search.get("browser_cockpit"),
        label="tool_capability.search.browser_cockpit",
    )
    search_api = _require_enum(
        enums=enums,
        key="tool_capability.search.search_api",
        value=search.get("search_api"),
        label="tool_capability.search.search_api",
    )
    if native_codex_web_search != "disabled":
        raise EnvProfileError("tool_capability.search.native_codex_web_search must be 'disabled'")
    if search_browser_cockpit != browser_cockpit:
        raise EnvProfileError(
            "tool_capability.search.browser_cockpit must match tool_capability.browser_cockpit"
        )
    expected_search_api = "user-approved-only" if role_id == "market" else "available"
    if search_api != expected_search_api:
        raise EnvProfileError(
            f"tool_capability.search.search_api mismatch for '{role_id}': "
            f"expected {expected_search_api!r}, got {search_api!r}"
        )
    return {
        "native_codex_web_search": native_codex_web_search,
        "browser_cockpit": search_browser_cockpit,
        "search_api": search_api,
    }


def resolve_private_workspace_root(root_value: str, *, role_id: str) -> str:
    if root_value != PRIVATE_WORKSPACE_ROOT:
        raise EnvProfileError(
            f"private_workspace.root must be {PRIVATE_WORKSPACE_ROOT!r}; got {root_value!r}"
        )
    return root_value


def validate_env_profile(
    profile: dict[str, Any],
    *,
    role_id: str,
    manifest: dict[str, Any],
    package_root: Path | None = None,
) -> dict[str, Any]:
    repo = Path(package_root) if package_root is not None else PACKAGE_ROOT
    contract = profile_contract(repo)
    require_role(manifest, role_id)

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

    actual_role_id = _require_string(profile.get("role_id"), "role_id")
    if actual_role_id != role_id:
        raise EnvProfileError(
            f"profile role_id mismatch: expected {role_id!r}, got {actual_role_id!r}"
        )
    if not _SAFE_ROLE_ID_RE.match(actual_role_id):
        raise EnvProfileError(f"profile role_id is invalid: {actual_role_id!r}")

    contract_path = _require_string(profile.get("contract_path"), "contract_path")
    expected_contract_path = f"contracts/{role_id}.md"
    if contract_path != expected_contract_path:
        raise EnvProfileError(
            f"contract_path mismatch for '{role_id}': expected {expected_contract_path!r}, got {contract_path!r}"
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

    private_workspace = _require_dict(profile.get("private_workspace"), "private_workspace")
    private_workspace_root = _require_string(private_workspace.get("root"), "private_workspace.root")
    resolve_private_workspace_root(private_workspace_root, role_id=role_id)

    fs_capability = _require_dict(profile.get("filesystem_capability"), "filesystem_capability")
    host_writable = _require_string_list(fs_capability.get("host_writable"), "filesystem_capability.host_writable")
    source_root_access = _require_enum(
        enums=enums,
        key="filesystem_capability.source_root",
        value=fs_capability.get("source_root"),
        label="filesystem_capability.source_root",
    )
    if "project_workspace" in fs_capability:
        raise EnvProfileError("filesystem_capability.project_workspace is retired; use source_root")
    _require_enum(
        enums=enums,
        key="filesystem_capability.raw_state",
        value=fs_capability.get("raw_state"),
        label="filesystem_capability.raw_state",
    )

    expected_host_writable = ["home", "codex-home", "xdg-config", "scratch", "runtime-temp"]
    if role_id == "dev":
        expected_host_writable = [*expected_host_writable, "source-root"]
    if host_writable != expected_host_writable:
        raise EnvProfileError(
            f"filesystem_capability.host_writable mismatch for '{role_id}': "
            f"expected {expected_host_writable}, got {host_writable}"
        )

    state_capability = _require_dict(profile.get("state_capability"), "state_capability")
    _require_enum(
        enums=enums,
        key="state_capability.artifact_templates",
        value=state_capability.get("artifact_templates"),
        label="state_capability.artifact_templates",
    )
    task_effects = _require_string_list(state_capability.get("task_effects"), "state_capability.task_effects")
    expected_task_effects = ["create", "update", "priority", "status", "archive", "history"]
    if task_effects != expected_task_effects:
        raise EnvProfileError(
            f"state_capability.task_effects must be exactly {expected_task_effects}"
        )
    track_effects = _require_string_list(state_capability.get("track_effects"), "state_capability.track_effects")
    expected_track_effects = [
        "create",
        "update_requirements",
        "update_status",
        "add_material",
        "add_update",
        "add_proof",
        "archive",
    ]
    if track_effects != expected_track_effects:
        raise EnvProfileError(
            f"state_capability.track_effects mismatch for '{role_id}': "
            f"expected {expected_track_effects}, got {track_effects}"
        )

    comment_effects = _require_string_list(state_capability.get("comment_effects"), "state_capability.comment_effects")
    expected_comment_effects = ["resolve"]
    if comment_effects != expected_comment_effects:
        raise EnvProfileError(
            f"state_capability.comment_effects mismatch for '{role_id}': "
            f"expected {expected_comment_effects}, got {comment_effects}"
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
    _require_search_capability(
        tool_capability=tool_capability,
        enums=enums,
        role_id=role_id,
        browser_cockpit=browser_cockpit,
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

    expected_project_access = "write" if role_id == "dev" else "read-only"
    expected_source_root_access = "write" if role_id == "dev" else "read-only"
    if project_access != expected_project_access:
        raise EnvProfileError(
            f"project.access mismatch for '{role_id}': expected {expected_project_access!r}, got {project_access!r}"
        )
    if source_root_access != expected_source_root_access:
        raise EnvProfileError(
            "filesystem_capability.source_root mismatch for "
            f"'{role_id}': expected {expected_source_root_access!r}, got {source_root_access!r}"
        )

    if role_id == "market":
        if browser_cockpit != "required":
            raise EnvProfileError("market profile must set tool_capability.browser_cockpit to 'required'")
        if market_evidence != "required":
            raise EnvProfileError("market profile must require market_research_evidence")
        if ordinary_web_fallback != "user-approved-only":
            raise EnvProfileError("market profile ordinary_web_fallback must be 'user-approved-only'")
    else:
        if browser_cockpit != "available":
            raise EnvProfileError(f"{role_id} profile browser_cockpit must be 'available'")
        if market_evidence != "not-required":
            raise EnvProfileError(f"{role_id} profile market_research_evidence must be 'not-required'")
        if ordinary_web_fallback != "available":
            raise EnvProfileError(f"{role_id} profile ordinary_web_fallback must be 'available'")

    normalized: dict[str, Any] = {}
    for key in top_level_order:
        normalized[key] = profile[key]

    manifest_roles = _manifest_role_ids(manifest)
    if role_id not in manifest_roles:
        raise EnvProfileError(f"role '{role_id}' is not in manifest")
    return normalized


def require_env_profile(
    role_id: str,
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    package_root: Path | None = None,
) -> dict[str, Any]:
    try:
        manifest = load_manifest(manifest_path)
        require_role(manifest, role_id)
    except ManifestError as exc:
        raise EnvProfileError(str(exc)) from exc

    profile = load_env_profile(role_id, package_root)
    return validate_env_profile(
        profile,
        role_id=role_id,
        manifest=manifest,
        package_root=package_root,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BuddySwitch env profiles.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Manifest TOML path")
    parser.add_argument(
        "--package-root",
        dest="package_root",
        type=Path,
        default=PACKAGE_ROOT,
        help="Installed package root containing catalog profiles",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate one profile")
    validate.add_argument("--role", required=True, help="Role id")

    sub.add_parser("validate-all", help="Validate profiles for all manifest roles")

    show = sub.add_parser("show", help="Show one normalized profile")
    show.add_argument("--role", required=True, help="Role id")
    return parser.parse_args()


def _cmd_validate(args: argparse.Namespace) -> int:
    profile = require_env_profile(
        args.role,
        manifest_path=args.manifest,
        package_root=args.package_root,
    )
    print(f"{profile['role_id']}: ok")
    return 0


def _cmd_validate_all(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    for role in manifest.get("roles", []):
        if not isinstance(role, dict):
            continue
        role_id = role.get("id")
        if not isinstance(role_id, str):
            continue
        require_env_profile(
            role_id,
            manifest_path=args.manifest,
            package_root=args.package_root,
        )
        print(f"{role_id}: ok")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    profile = require_env_profile(
        args.role,
        manifest_path=args.manifest,
        package_root=args.package_root,
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
