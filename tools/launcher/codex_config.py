#!/usr/bin/env python3
"""Patch CODEX_HOME/config.toml with BuddySwitch-managed automation permissions."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


SANDBOX_TABLE = "sandbox_workspace_write"
MANAGED_COMMENT = "# BuddySwitch managed automation permissions"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch Codex config automation permissions for BuddySwitch runtime.")
    parser.add_argument("--config", required=True, help="Path to config.toml")
    parser.add_argument("--shared-root", required=True, help="BuddySwitch shared root")
    parser.add_argument("--repo-root", required=True, help="BuddySwitch repo root")
    parser.add_argument(
        "--temp-root",
        action="append",
        default=[],
        help="Additional writable temp roots (repeatable)",
    )
    return parser.parse_args()


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_managed_top_level_block() -> str:
    return (
        """
# BuddySwitch managed automation permissions
sandbox_mode = "workspace-write"
approval_policy = { granular = {
  sandbox_approval = true,
  rules = false,
  mcp_elicitations = false,
  request_permissions = false,
  skill_approval = false,
} }
""".strip()
        + "\n"
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
    stripped = line.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    if stripped.startswith("[[") and stripped.endswith("]]"):
        return stripped[2:-2].strip()
    return stripped[1:-1].strip()


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
            if header == SANDBOX_TABLE:
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


def build_writable_roots(shared_root: str, repo_root: str, temp_roots: list[str]) -> list[Path]:
    roots: list[Path] = [
        canonical(shared_root),
        repo_git_common_dir(canonical(repo_root)),
    ]
    for temp_root in temp_roots:
        roots.append(canonical(temp_root))
    return dedupe_paths(roots)


def patched_config_text(existing_text: str, roots: list[Path]) -> str:
    preserved = strip_managed_sections(existing_text).rstrip("\n")
    managed_top_level = render_managed_top_level_block()
    sandbox_workspace_write = render_sandbox_workspace_write_block(roots)
    if preserved:
        return f"{managed_top_level}\n{preserved}\n\n{sandbox_workspace_write}"
    return f"{managed_top_level}\n{sandbox_workspace_write}"


def main() -> int:
    args = parse_args()
    config_path = canonical(args.config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    roots = build_writable_roots(args.shared_root, args.repo_root, args.temp_root)
    config_path.write_text(patched_config_text(existing_text, roots), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
