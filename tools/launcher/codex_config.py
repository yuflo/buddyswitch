#!/usr/bin/env python3
"""Patch CODEX_HOME/config.toml with BuddySwitch-managed automation permissions."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SANDBOX_TABLE = "sandbox_workspace_write"
PERMISSION_PROFILE = "buddyswitch-runtime"
PERMISSION_PROFILE_PREFIX = f"permissions.{PERMISSION_PROFILE}"
MANAGED_COMMENT = "# BuddySwitch managed automation permissions"
MCP_SERVER_PREFIX = "mcp_servers."
MCP_TOOLS_APPROVAL_KEY = "default_tools_approval_mode"
WEB_SEARCH_KEY = "web_search"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch Codex config automation permissions for BuddySwitch runtime.")
    parser.add_argument("--config", required=True, help="Path to config.toml")
    parser.add_argument("--repo-root", required=True, help="BuddySwitch repo root")
    parser.add_argument("--shared-root", required=True, help="BuddySwitch shared root")
    parser.add_argument("--source-codex-home", help="Source Codex home that must not be writable")
    parser.add_argument("--manifest", help="Path to env manifest TOML")
    parser.add_argument("--buddy", help="Active buddy id for instance mode")
    parser.add_argument("--instance-root", help="Active instance root path")
    parser.add_argument("--workspace-dir", help="Active workspace path")
    parser.add_argument("--project-workspace-dir", help="Shared project workspace path")
    parser.add_argument("--home", help="Instance HOME path")
    parser.add_argument("--codex-home", help="Instance CODEX_HOME path")
    parser.add_argument("--xdg-config-home", help="Instance XDG_CONFIG_HOME path")
    parser.add_argument("--broker-socket", help="Runtime broker Unix socket path for product mode")
    parser.add_argument(
        "--temp-root",
        action="append",
        default=[],
        help="Additional writable temp roots (repeatable)",
    )
    return parser.parse_args()


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_approval_policy() -> str:
    return (
        "approval_policy = { granular = { sandbox_approval = true, rules = false, "
        "mcp_elicitations = false, request_permissions = false, skill_approval = false } }\n"
    )


def render_managed_top_level_block() -> str:
    return (
        """
# BuddySwitch managed automation permissions
web_search = "disabled"
sandbox_mode = "workspace-write"
""".strip()
        + "\n"
        + render_approval_policy()
    )


def render_managed_permission_top_level_block() -> str:
    return (
        f"""
# BuddySwitch managed automation permissions
web_search = "disabled"
default_permissions = {toml_string(PERMISSION_PROFILE)}
""".strip()
        + "\n"
        + render_approval_policy()
    )


def render_sandbox_workspace_write_block(roots: list[Path]) -> str:
    rendered_roots = ",\n  ".join(toml_string(str(root)) for root in roots)
    return (
        f"""
[sandbox_workspace_write]
network_access = true
writable_roots = [
  {rendered_roots}
]
""".strip()
        + "\n"
    )


def render_permission_profile_block(
    filesystem_entries: dict[str, str],
    unix_sockets: list[Path] | None = None,
) -> str:
    rendered_filesystem_rows: list[str] = []
    for key, value in filesystem_entries.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("permission profile filesystem entries must use string keys and values")
        rendered_filesystem_rows.append(f"{toml_string(str(key))} = {toml_string(value)}")

    filesystem_block = "\n".join(rendered_filesystem_rows)
    unix_socket_entries = ""
    if unix_sockets:
        rendered_sockets = ", ".join(f"{toml_string(str(path))} = \"allow\"" for path in unix_sockets)
        unix_socket_entries = f"\nunix_sockets = {{ {rendered_sockets} }}"
    return (
        f"""
[permissions.{PERMISSION_PROFILE}.filesystem]
{filesystem_block}

[permissions.{PERMISSION_PROFILE}.network]
enabled = true
mode = "full"{unix_socket_entries}
""".strip()
        + "\n"
    )


def canonical(path: str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def repo_git_common_dir(repo_root: Path) -> Path:
    output = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
        text=True,
    ).strip()
    git_dir = Path(output)
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir
    return canonical(str(git_dir))


def dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    ordered: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def parse_section_header(line: str) -> str | None:
    stripped = strip_inline_comment(line).strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    if stripped.startswith("[[") and stripped.endswith("]]"):
        return stripped[2:-2].strip()
    return stripped[1:-1].strip()


def strip_inline_comment(line: str) -> str:
    in_single_quote = False
    in_double_quote = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if in_double_quote and char == "\\":
            escaped = True
            continue
        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue
        if char == "#" and not in_single_quote and not in_double_quote:
            return line[:index]
    return line


def top_level_key_assignment(line: str, key: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if "=" not in stripped:
        return False
    return stripped.split("=", 1)[0].strip() == key


def brace_delta(text: str) -> int:
    return text.count("{") - text.count("}")


def strip_managed_sections(config_text: str) -> str:
    lines = config_text.splitlines(keepends=True)
    output: list[str] = []
    current_section: str | None = None
    index = 0

    while index < len(lines):
        line = lines[index]
        header = parse_section_header(line)
        if header is not None:
            current_section = header
            if header == SANDBOX_TABLE or header == PERMISSION_PROFILE_PREFIX or header.startswith(
                f"{PERMISSION_PROFILE_PREFIX}."
            ):
                index += 1
                while index < len(lines):
                    next_header = parse_section_header(lines[index])
                    if next_header is not None:
                        break
                    index += 1
                continue
            output.append(line)
            index += 1
            continue

        if line.strip() == MANAGED_COMMENT:
            index += 1
            continue

        if current_section in (None, "features") and top_level_key_assignment(line, "sandbox_mode"):
            index += 1
            continue

        if current_section in (None, "features") and top_level_key_assignment(line, "default_permissions"):
            index += 1
            continue

        if current_section in (None, "features") and top_level_key_assignment(line, WEB_SEARCH_KEY):
            index += 1
            continue

        if current_section in (None, "features") and top_level_key_assignment(line, "approval_policy"):
            balance = brace_delta(line.partition("=")[2])
            index += 1
            while balance > 0 and index < len(lines):
                balance += brace_delta(lines[index])
                index += 1
            continue

        output.append(line)
        index += 1

    return "".join(output)


def is_mcp_server_section(section: str | None) -> bool:
    return isinstance(section, str) and section.startswith(MCP_SERVER_PREFIX) and len(section) > len(MCP_SERVER_PREFIX)


def approval_line_like(line: str) -> str:
    indent = line[: len(line) - len(line.lstrip())]
    newline = "\n" if line.endswith("\n") else ""
    return f'{indent}{MCP_TOOLS_APPROVAL_KEY} = "approve"{newline}'


def append_mcp_approval(output: list[str]) -> None:
    approval_line = f'{MCP_TOOLS_APPROVAL_KEY} = "approve"\n'
    if output and output[-1].strip() == "":
        trailing_blank = output.pop()
        output.append(approval_line)
        output.append(trailing_blank)
        return
    output.append(approval_line)


def patch_mcp_server_approvals(config_text: str) -> str:
    lines = config_text.splitlines(keepends=True)
    output: list[str] = []
    in_mcp_section = False
    mcp_section_has_approval = False

    def finish_section() -> None:
        nonlocal in_mcp_section, mcp_section_has_approval
        if in_mcp_section and not mcp_section_has_approval:
            append_mcp_approval(output)
        in_mcp_section = False
        mcp_section_has_approval = False

    for line in lines:
        header = parse_section_header(line)
        if header is not None:
            finish_section()
            in_mcp_section = is_mcp_server_section(header)
            mcp_section_has_approval = False
            output.append(line)
            continue

        if in_mcp_section and top_level_key_assignment(line, MCP_TOOLS_APPROVAL_KEY):
            if not mcp_section_has_approval:
                output.append(approval_line_like(line))
                mcp_section_has_approval = True
            continue

        output.append(line)

    finish_section()
    return "".join(output)


def path_contains(container: Path, path: Path) -> bool:
    if container == path:
        return True
    try:
        path.relative_to(container)
    except ValueError:
        return False
    return True


def is_safe_writable_root(root: Path, repo_root: Path, source_codex_home: Path) -> bool:
    try:
        if path_contains(root, repo_root) or path_contains(repo_root, root):
            raise ValueError(f"refusing writable root that grants source checkout: {root}")
        if path_contains(root, source_codex_home) or path_contains(source_codex_home, root):
            raise ValueError(f"refusing writable root that grants source Codex home: {root}")
    except ValueError:
        return False
    return True


def _import_env_profiles(repo_root: Path):
    scripts_dir = repo_root / "scripts"
    scripts_key = str(scripts_dir)
    if scripts_key not in sys.path:
        sys.path.insert(0, scripts_key)
    import env_profiles  # type: ignore

    return env_profiles


def _profile_mode(args: argparse.Namespace) -> bool:
    return isinstance(args.buddy, str) and bool(args.buddy.strip())


def _require_profile_mode_args(args: argparse.Namespace) -> None:
    required = (
        "instance_root",
        "workspace_dir",
        "project_workspace_dir",
        "home",
        "codex_home",
        "xdg_config_home",
    )
    missing = [
        name
        for name in required
        if not isinstance(getattr(args, name), str) or not str(getattr(args, name)).strip()
    ]
    if missing:
        joined = ", ".join(f"--{item.replace('_', '-')}" for item in missing)
        raise ValueError(f"profile mode requires: {joined}")


def _safe_temp_roots(
    *,
    temp_roots: list[str],
    repo_root: Path,
    source_codex_home: Path,
    forbidden: list[Path],
) -> list[Path]:
    allowed: list[Path] = []
    for raw in temp_roots:
        candidate = canonical(raw)
        if not is_safe_writable_root(candidate, repo_root, source_codex_home):
            continue
        blocked = False
        for guard in forbidden:
            if guard == candidate or path_contains(candidate, guard) or path_contains(guard, candidate):
                blocked = True
                break
        if not blocked:
            allowed.append(candidate)
    return allowed


def _profile_mode_workspace_deny_rules(workspace_dir: Path) -> dict[str, str]:
    denied_paths = [
        workspace_dir / "buddyswitch" / "skills",
        workspace_dir / "tools",
        workspace_dir / "tests",
        workspace_dir / "docs",
        workspace_dir / "buddyswitch" / "objects",
        workspace_dir / "README.md",
        workspace_dir / "buddyswitch-codex",
    ]
    return {str(canonical(str(path))): "none" for path in denied_paths}


def _build_profile_mode_filesystem(args: argparse.Namespace) -> dict[str, str]:
    _require_profile_mode_args(args)

    canonical_repo_root = canonical(args.repo_root)
    canonical_shared_root = canonical(args.shared_root)
    canonical_source_codex_home = (
        canonical(args.source_codex_home)
        if args.source_codex_home
        else canonical(str(Path.home() / ".codex"))
    )
    manifest_path = canonical(args.manifest) if args.manifest else canonical_repo_root / "buddyswitch" / "manifest.toml"
    buddy_id = str(args.buddy).strip()

    env_profiles = _import_env_profiles(canonical_repo_root)
    profile = env_profiles.require_env_profile(
        buddy_id,
        manifest_path=manifest_path,
        repo_root=canonical_repo_root,
    )

    instance_root = canonical(str(args.instance_root))
    workspace_dir = canonical(str(args.workspace_dir))
    project_workspace_dir = canonical(str(args.project_workspace_dir))
    state_root = canonical_shared_root / "state"
    project_root = canonical_shared_root / "project"

    home = canonical(str(args.home))
    codex_home = canonical(str(args.codex_home))
    xdg_config_home = canonical(str(args.xdg_config_home))
    buddybox_root_relative = env_profiles.resolve_buddybox_root(
        str(profile["buddybox"]["root"]),
        buddy_id=buddy_id,
    )
    buddybox_root = workspace_dir / buddybox_root_relative

    filesystem_entries: dict[str, str] = {}
    filesystem_entries["/"] = "read"
    filesystem_entries[str(canonical_repo_root)] = "none"
    filesystem_entries[str(project_workspace_dir)] = (
        "write" if profile.get("project", {}).get("access") == "write" else "read"
    )
    filesystem_entries.update(_profile_mode_workspace_deny_rules(workspace_dir))

    writable_roots: list[Path] = [home, codex_home, xdg_config_home, buddybox_root]
    forbidden_temp = [
        canonical_shared_root,
        project_root,
        project_workspace_dir,
        state_root,
        instance_root,
        workspace_dir,
    ]
    writable_roots.extend(
        _safe_temp_roots(
            temp_roots=args.temp_root,
            repo_root=canonical_repo_root,
            source_codex_home=canonical_source_codex_home,
            forbidden=forbidden_temp,
        )
    )

    blocked_roots = [canonical_shared_root, project_root, state_root, instance_root, workspace_dir]
    for root in writable_roots:
        if not is_safe_writable_root(root, canonical_repo_root, canonical_source_codex_home):
            raise ValueError(f"refusing writable root: {root}")
        if root in blocked_roots:
            raise ValueError(f"refusing writable root boundary: {root}")
        for blocked in blocked_roots:
            if path_contains(root, blocked):
                raise ValueError(f"refusing writable root that grants boundary: {root}")
    for path in dedupe_paths([canonical(str(path)) for path in writable_roots]):
        filesystem_entries[str(path)] = "write"
    return filesystem_entries


def _build_profile_mode_unix_sockets(args: argparse.Namespace) -> list[Path]:
    raw = getattr(args, "broker_socket", None)
    if not isinstance(raw, str) or not raw.strip():
        return []
    return [canonical(raw.strip())]


def _build_local_mode_roots(args: argparse.Namespace) -> list[Path]:
    canonical_shared_root = canonical(args.shared_root)
    canonical_repo_root = canonical(args.repo_root)
    canonical_source_codex_home = (
        canonical(args.source_codex_home)
        if args.source_codex_home
        else canonical(str(Path.home() / ".codex"))
    )
    git_common_dir = repo_git_common_dir(canonical_repo_root)
    roots: list[Path] = [canonical_shared_root, git_common_dir]
    for root in roots:
        if root == git_common_dir:
            continue
        if not is_safe_writable_root(root, canonical_repo_root, canonical_source_codex_home):
            raise ValueError(f"refusing writable root that grants source boundary: {root}")
    for temp_root in args.temp_root:
        candidate = canonical(temp_root)
        if is_safe_writable_root(candidate, canonical_repo_root, canonical_source_codex_home):
            roots.append(candidate)
    return dedupe_paths(roots)


def build_writable_roots(args: argparse.Namespace) -> list[Path]:
    return _build_local_mode_roots(args)


def patched_config_text(
    existing_text: str,
    roots: list[Path],
    *,
    profile_mode: bool = False,
    profile_filesystem_entries: dict[str, str] | None = None,
    unix_sockets: list[Path] | None = None,
) -> str:
    preserved = patch_mcp_server_approvals(strip_managed_sections(existing_text)).rstrip("\n")
    managed_top_level = render_managed_permission_top_level_block() if profile_mode else render_managed_top_level_block()
    if profile_mode:
        if profile_filesystem_entries is None:
            raise ValueError("profile filesystem entries are required in profile mode")
        permissions_block = render_permission_profile_block(profile_filesystem_entries, unix_sockets=unix_sockets)
    else:
        permissions_block = render_sandbox_workspace_write_block(roots)
    if preserved:
        return f"{managed_top_level}\n{preserved}\n\n{permissions_block}"
    return f"{managed_top_level}\n{permissions_block}"


def main() -> int:
    args = parse_args()
    config_path = canonical(args.config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    profile_mode = _profile_mode(args)
    roots: list[Path] = []
    profile_filesystem_entries: dict[str, str] | None = None
    try:
        if profile_mode:
            profile_filesystem_entries = _build_profile_mode_filesystem(args)
        else:
            roots = build_writable_roots(args)
    except Exception as exc:
        if exc.__class__.__name__ == "EnvProfileError":
            print(f"Env profile invalid: {exc}", file=sys.stderr)
            return 2
        print(f"refusing writable root: {exc}", file=sys.stderr)
        return 2
    unix_sockets = _build_profile_mode_unix_sockets(args) if profile_mode else []
    config_path.write_text(
        patched_config_text(
            existing_text,
            roots,
            profile_mode=profile_mode,
            profile_filesystem_entries=profile_filesystem_entries,
            unix_sockets=unix_sockets,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
