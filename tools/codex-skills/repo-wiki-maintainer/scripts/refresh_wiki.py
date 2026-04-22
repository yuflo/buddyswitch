from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Sequence

from common import RepoWikiConfig, load_repo_config
from lint_wiki import lint_repo_wiki

PROMOTION_PATHS = frozenset(
    {
        "AGENTS.md",
        "README.md",
        "framework/docs/architecture-overview.md",
        "framework/docs/switch-spec.md",
        "tools/launcher/assets/runtime-AGENTS.md",
        "scripts/switch_runtime.py",
    }
)
DEFAULT_ALLOWED_SUPPORTING_GLOBS = (
    "docs/dev*/**",
    "docs/reviews/**",
    "docs/whiteboard/**",
)
README_REL_PATH = "docs/llm-wiki/README.md"
RECENT_CHANGES_REL_PATH = "docs/llm-wiki/recent-important-changes.md"
VERIFICATION_MAP_REL_PATH = "docs/llm-wiki/verification-map.md"
MATERIALIZES_TASK_SNIPPET = "materialize"
ZERO_RUN_SNIPPET = "zero-run task"
NO_TASK_SNIPPET = "does not create a task"


@dataclass(frozen=True)
class RefreshResult:
    updated_files: list[str]
    promoted_count: int


@dataclass(frozen=True)
class ExistingRecentChangeEntry:
    match_sha: str
    block_lines: tuple[str, ...]


class CanonicalConflictError(RuntimeError):
    pass


class BlockingLintError(RuntimeError):
    pass


def _run_git(repo_root: Path, args: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def resolve_head_commit(repo_root: Path) -> str:
    return _run_git(repo_root, ["rev-parse", "HEAD"]).strip()


def _load_config(repo_root: Path) -> RepoWikiConfig:
    return load_repo_config(repo_root / ".llm-wiki.toml")


def read_canonical_sources(repo_root: Path, config: RepoWikiConfig) -> dict[str, str]:
    return {
        rel_path: (repo_root / rel_path).read_text(encoding="utf-8")
        for rel_path in config.canonical_sources
    }


def _line_number_containing(text: str, needle: str) -> int | None:
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    return None


def find_canonical_conflicts(canonical: dict[str, str]) -> list[str]:
    findings: list[str] = []

    readme_text = canonical.get("README.md", "")
    switch_spec_text = canonical.get("framework/docs/switch-spec.md", "")
    architecture_text = canonical.get("framework/docs/architecture-overview.md", "")

    materializes_task = []
    if MATERIALIZES_TASK_SNIPPET in readme_text and ZERO_RUN_SNIPPET in readme_text:
        line_number = _line_number_containing(readme_text, ZERO_RUN_SNIPPET)
        materializes_task.append(f"README.md:{line_number}")
    if MATERIALIZES_TASK_SNIPPET in switch_spec_text:
        line_number = _line_number_containing(switch_spec_text, MATERIALIZES_TASK_SNIPPET)
        materializes_task.append(f"framework/docs/switch-spec.md:{line_number}")

    if NO_TASK_SNIPPET in architecture_text and materializes_task:
        line_number = _line_number_containing(architecture_text, NO_TASK_SNIPPET)
        findings.append(
            "resolve create-mode task materialization conflict: "
            + ", ".join([*materializes_task, f"framework/docs/architecture-overview.md:{line_number}"])
        )

    return findings


def _extract_covers_through_commit(repo_root: Path) -> str | None:
    if not _has_trusted_wiki_surface(repo_root):
        return None

    readme_path = repo_root / README_REL_PATH
    recent_changes_path = repo_root / RECENT_CHANGES_REL_PATH
    has_change_entries = any(
        _is_recent_change_entry_heading(line)
        for line in recent_changes_path.read_text(encoding="utf-8").splitlines()
    )
    if not has_change_entries:
        return None

    for line in readme_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("Covers through commit:"):
            continue
        _, value = line.split(":", 1)
        cover_ref = value.strip()
        if not cover_ref or cover_ref == "TBD":
            return None
        cover_sha = _resolve_commit_checkpoint(repo_root, cover_ref)
        if cover_sha is None:
            return None
        try:
            touched_files = [
                file_path
                for file_path in _run_git(
                    repo_root,
                    ["show", "--format=", "--name-only", cover_sha],
                ).splitlines()
                if file_path
            ]
        except subprocess.CalledProcessError:
            return None
        if touched_files and all(
            file_path in {README_REL_PATH, RECENT_CHANGES_REL_PATH, VERIFICATION_MAP_REL_PATH}
            for file_path in touched_files
        ):
            return None
        return cover_sha

    return None


def _resolve_commit_checkpoint(repo_root: Path, checkpoint_ref: str) -> str | None:
    try:
        resolved = _run_git(
            repo_root,
            ["rev-parse", "--verify", f"{checkpoint_ref}^{{commit}}"],
        ).strip()
    except subprocess.CalledProcessError:
        return None
    normalized = resolved.lower()
    if len(normalized) != 40 or not all(char in "0123456789abcdef" for char in normalized):
        return None
    return normalized


def _has_trusted_wiki_surface(repo_root: Path) -> bool:
    readme_path = repo_root / README_REL_PATH
    recent_changes_path = repo_root / RECENT_CHANGES_REL_PATH
    verification_map_path = repo_root / VERIFICATION_MAP_REL_PATH
    if not (
        readme_path.is_file()
        and recent_changes_path.is_file()
        and verification_map_path.is_file()
    ):
        return False

    try:
        _run_git(
            repo_root,
            [
                "ls-files",
                "--error-unmatch",
                README_REL_PATH,
                RECENT_CHANGES_REL_PATH,
                VERIFICATION_MAP_REL_PATH,
            ],
        )
    except subprocess.CalledProcessError:
        return False
    return True


def read_git_changes(repo_root: Path, since_commit: str | None, config: RepoWikiConfig) -> list[dict[str, Any]]:
    git_args = [
        "log",
        "--reverse",
        "--format=%H%x1f%ad%x1f%s",
        "--date=short",
    ]
    if since_commit:
        git_args.append(f"{since_commit}..HEAD")
    else:
        git_args.extend(
            [
                f"--since={config.recent_change_window_days}.days",
            ]
        )

    change_rows = _run_git(repo_root, git_args).splitlines()
    changes: list[dict[str, Any]] = []
    for row in change_rows:
        if not row:
            continue
        sha, change_date, summary = row.split("\x1f", 2)
        touched_files = [
            line
            for line in _run_git(repo_root, ["show", "--format=", "--name-only", sha]).splitlines()
            if line
        ]
        changes.append(
            {
                "sha": sha,
                "date": change_date,
                "summary": summary,
                "touched_files": touched_files,
            }
        )
    return changes


def _matches_supporting_glob(path: str, supporting_globs: Sequence[str]) -> bool:
    pure_path = PurePosixPath(path)
    return any(pure_path.match(pattern) for pattern in supporting_globs)


def _is_recent_change_entry_heading(line: str) -> bool:
    if not line.startswith("## "):
        return False
    try:
        change_date, sha, summary = line[3:].split(" | ", 2)
    except ValueError:
        return False

    if not summary:
        return False
    try:
        date.fromisoformat(change_date)
    except ValueError:
        return False
    return len(sha) >= 7 and all(char in "0123456789abcdef" for char in sha.lower())


def _heading_sha(line: str) -> str | None:
    if not _is_recent_change_entry_heading(line):
        return None
    _, sha, _ = line[3:].split(" | ", 2)
    return sha


def _evidence_sha(block_lines: Sequence[str]) -> str | None:
    marker = "git show --stat --oneline "
    for line in block_lines:
        candidate = line.strip()
        if candidate.startswith("- "):
            candidate = candidate[2:].strip()
        if not candidate.startswith(marker):
            continue
        sha = candidate.removeprefix(marker).strip()
        if sha and all(char in "0123456789abcdef" for char in sha.lower()):
            return sha
    return None


def _read_existing_recent_change_entries(repo_root: Path) -> list[ExistingRecentChangeEntry]:
    if not _has_trusted_wiki_surface(repo_root):
        return []

    recent_changes_path = repo_root / RECENT_CHANGES_REL_PATH
    parsed_entries: list[ExistingRecentChangeEntry] = []
    current_block: list[str] = []
    current_heading_sha: str | None = None

    def _flush_entry() -> None:
        nonlocal current_block, current_heading_sha
        if not current_block or current_heading_sha is None:
            current_block = []
            current_heading_sha = None
            return
        normalized_block = list(current_block)
        while normalized_block and normalized_block[-1] == "":
            normalized_block.pop()
        parsed_entries.append(
            ExistingRecentChangeEntry(
                match_sha=_evidence_sha(normalized_block) or current_heading_sha,
                block_lines=tuple(normalized_block),
            )
        )
        current_block = []
        current_heading_sha = None

    for line in recent_changes_path.read_text(encoding="utf-8").splitlines():
        heading_sha = _heading_sha(line)
        if heading_sha is not None:
            _flush_entry()
            current_heading_sha = heading_sha
            current_block = [line]
            continue
        if current_block:
            current_block.append(line)

    _flush_entry()
    return parsed_entries


def _existing_entry_matches_sha(existing_entry: ExistingRecentChangeEntry, sha: str) -> bool:
    return sha.startswith(existing_entry.match_sha) or existing_entry.match_sha.startswith(sha)


def _effective_supporting_globs(config: RepoWikiConfig) -> Sequence[str]:
    if config.allowed_supporting_globs:
        return config.allowed_supporting_globs
    return DEFAULT_ALLOWED_SUPPORTING_GLOBS


def _is_durable_supporting_turn(change: dict[str, Any], config: RepoWikiConfig) -> bool:
    touched_files = [str(path) for path in change.get("touched_files", [])]
    supporting_globs = _effective_supporting_globs(config)
    return any(_matches_supporting_glob(path, supporting_globs) for path in touched_files)


def promote_change(change: dict[str, Any], config: RepoWikiConfig) -> bool:
    touched_files = {str(path) for path in change.get("touched_files", [])}
    return bool(
        PROMOTION_PATHS & touched_files
        or _is_durable_supporting_turn(change, config)
    )


def _shared_header(config: RepoWikiConfig, head_commit: str) -> list[str]:
    header = [
        "Status: derived",
        f"Last verified: {date.today().isoformat()}",
        f"Covers through commit: {head_commit}",
        "Canonical sources:",
    ]
    header.extend(f"- {path}" for path in config.canonical_sources)
    header.extend(
        [
            "Do not infer:",
            "- This file does not replace canonical docs.",
            "- If canonical sources disagree, stop and resolve the conflict before refreshing.",
        ]
    )
    return header


def _render_readme(config: RepoWikiConfig, head_commit: str) -> str:
    lines = ["# LLM Wiki", ""]
    lines.extend(_shared_header(config, head_commit))
    lines.extend(
        [
            "",
            "## Canonical Sources",
            *[f"- {path}" for path in config.canonical_sources],
            "",
            "## Reading Order",
            "- AGENTS.md",
            "- README.md",
            "- framework/docs/architecture-overview.md",
            "- framework/docs/switch-spec.md",
            "- tools/launcher/assets/runtime-AGENTS.md",
            "",
            "## Architecture Map",
            "- `projects/app/`: primary application code.",
            "- `framework/docs/`: canonical behavior and system contracts.",
            "- `tools/launcher/assets/runtime-AGENTS.md`: launcher-managed runtime contract.",
            "- `docs/llm-wiki/`: derived orientation layer only.",
            "",
            "## Update Workflow",
            "1. Update canonical sources first.",
            "2. Re-run `wiki-refresh` to rewrite this derived layer.",
            "3. Re-run `wiki-lint` before trusting the refreshed wiki.",
        ]
    )
    return "\n".join(lines) + "\n"


def _promoted_canonical_files(change: dict[str, Any], config: RepoWikiConfig) -> list[str]:
    touched_files = [str(path) for path in change.get("touched_files", [])]
    promoted = [path for path in config.canonical_sources if path in touched_files]
    if "scripts/switch_runtime.py" in touched_files:
        promoted.append("scripts/switch_runtime.py")
    return promoted


def _render_generated_recent_change_entry(
    change: dict[str, Any],
    config: RepoWikiConfig,
) -> list[str]:
    sha = str(change["sha"])
    summary = str(change["summary"])
    change_date = str(change["date"])
    touched_canonical_files = _promoted_canonical_files(change, config)
    lines = [
        f"## {change_date} | {sha[:7]} | {summary}",
        "- Why a fresh session should care:",
        "  - This change touched canonical orientation paths or runtime-routing paths.",
        "- New truth:",
        "  - Re-read the cited canonical files before trusting older summaries.",
        "- Invalidated old assumption:",
        "  - Previous fresh-session context may be stale past this commit.",
        "- Canonical files to read:",
    ]
    if touched_canonical_files:
        lines.extend(f"  - {path}" for path in touched_canonical_files)
    else:
        lines.append("  - README.md")
    lines.extend(
        [
            "- Verification evidence:",
            f"  - git show --stat --oneline {sha}",
        ]
    )
    return lines


def _render_recent_changes(
    config: RepoWikiConfig,
    promoted_changes: list[dict[str, Any]],
    head_commit: str,
    existing_entries: Sequence[ExistingRecentChangeEntry] | None = None,
) -> str:
    lines = ["# Recent Important Changes", ""]
    lines.extend(_shared_header(config, head_commit))
    lines.extend(["", "## Change Entries"])

    kept_existing_entries = list(existing_entries or [])

    tail_shas = {
        str(change["sha"])
        for change in promoted_changes[-config.recent_change_max_entries :]
    }
    selected_changes: list[dict[str, Any]] = []
    selected_shas: set[str] = set()
    for change in promoted_changes:
        sha = str(change["sha"])
        if sha in selected_shas:
            continue
        if sha in tail_shas or _is_durable_supporting_turn(change, config):
            selected_changes.append(change)
            selected_shas.add(sha)

    if not selected_changes and not kept_existing_entries:
        lines.extend(["- No promoted changes in the current refresh window."])
        return "\n".join(lines) + "\n"

    for existing_entry in kept_existing_entries:
        lines.extend(["", *existing_entry.block_lines])

    for change in selected_changes:
        sha = str(change["sha"])
        if any(_existing_entry_matches_sha(entry, sha) for entry in kept_existing_entries):
            continue
        lines.extend(["", *_render_generated_recent_change_entry(change, config)])

    return "\n".join(lines) + "\n"


def _render_verification_map(config: RepoWikiConfig, head_commit: str) -> str:
    lines = ["# Verification Map", ""]
    lines.extend(_shared_header(config, head_commit))
    lines.extend(
        [
            "",
            "## Verification Entries",
            "| Canonical Claim | Verification Command | Evidence Location |",
            "| --- | --- | --- |",
            "| Repo wiki shape is structurally valid | python3 tools/codex-skills/repo-wiki-maintainer/scripts/lint_wiki.py --repo-root . | docs/llm-wiki/recent-important-changes.md |",
            "| Repo wiki scripts stay covered by focused tests | python3 -m pytest tests/test_repo_wiki_config.py tests/test_repo_wiki_init.py tests/test_repo_wiki_refresh.py tests/test_repo_wiki_lint.py -q | tests/test_repo_wiki_refresh.py |",
        ]
    )
    return "\n".join(lines) + "\n"


def rewrite_wiki_files(
    repo_root: Path,
    config: RepoWikiConfig,
    promoted_changes: list[dict[str, Any]],
    head_commit: str,
    existing_recent_entries: Sequence[ExistingRecentChangeEntry],
) -> list[str]:
    rendered_pages = {
        README_REL_PATH: _render_readme(config, head_commit),
        RECENT_CHANGES_REL_PATH: _render_recent_changes(
            config,
            promoted_changes,
            head_commit,
            existing_entries=existing_recent_entries,
        ),
        VERIFICATION_MAP_REL_PATH: _render_verification_map(config, head_commit),
    }

    updated_files: list[str] = []
    for rel_path in config.maintained_files:
        target_path = repo_root / rel_path
        if rel_path not in rendered_pages:
            continue
        target_path.write_text(rendered_pages[rel_path], encoding="utf-8")
        updated_files.append(rel_path)
    return updated_files


def refresh_repo_wiki(repo_root: Path) -> RefreshResult:
    config = _load_config(repo_root)
    canonical = read_canonical_sources(repo_root, config)
    conflicts = find_canonical_conflicts(canonical)
    if conflicts:
        raise CanonicalConflictError("\n".join(conflicts))

    since_commit = _extract_covers_through_commit(repo_root)
    existing_recent_entries = _read_existing_recent_change_entries(repo_root) if since_commit else []
    promoted_changes: list[dict[str, Any]] = []
    changes = read_git_changes(repo_root, since_commit, config)
    for change in changes:
        if not promote_change(change, config):
            continue
        promoted_changes.append(change)
    head_commit = resolve_head_commit(repo_root)
    covered_commit = (
        str(promoted_changes[-1]["sha"])
        if promoted_changes
        else (since_commit or head_commit)
    )
    updated_files = rewrite_wiki_files(
        repo_root,
        config,
        promoted_changes,
        covered_commit,
        existing_recent_entries,
    )

    lint_findings = lint_repo_wiki(repo_root)
    blocking_messages = [
        f"{finding.path}: {finding.message}"
        for finding in lint_findings
        if finding.severity == "error"
    ]
    if blocking_messages:
        raise BlockingLintError("\n".join(blocking_messages))

    return RefreshResult(
        updated_files=updated_files,
        promoted_count=len(promoted_changes),
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh repo wiki pages from canonical sources and recent important changes.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    refresh_repo_wiki(Path(args.repo_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
