from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from common import RepoWikiConfig, load_repo_config

REQUIRED_TOP_LEVEL_HEADINGS: dict[str, tuple[str, ...]] = {
    "docs/llm-wiki/README.md": (
        "# LLM Wiki",
        "## Canonical Sources",
        "## Architecture Map",
        "## Update Workflow",
    ),
    "docs/llm-wiki/recent-important-changes.md": (
        "# Recent Important Changes",
        "## Change Entries",
    ),
    "docs/llm-wiki/verification-map.md": (
        "# Verification Map",
        "## Verification Entries",
    ),
}
RECENT_ENTRY_HEADING_RE = re.compile(
    r"^##\s+\d{4}-\d{2}-\d{2}\s+\|\s+([0-9a-f]{7,40})\s+\|\s+.+$"
)
RECENT_ENTRY_PREFIX_RE = re.compile(r"^##\s+\d{4}-\d{2}-\d{2}\s+\|")
RECENT_ENTRY_DATE_STYLE_PREFIX_RE = re.compile(r"^##\s+\d{4}-\d{2}-\d{2}\s*\|")


@dataclass(frozen=True)
class LintFinding:
    severity: str
    message: str
    path: str


def _error(path: str, message: str) -> LintFinding:
    return LintFinding(severity="error", message=message, path=path)


def _load_config(repo_root: Path) -> tuple[RepoWikiConfig | None, list[LintFinding]]:
    config_path = repo_root / ".llm-wiki.toml"
    if not config_path.is_file():
        return None, [_error(".llm-wiki.toml", "missing required config file")]
    try:
        return load_repo_config(config_path), []
    except Exception as exc:  # pragma: no cover - defensive path
        return None, [_error(".llm-wiki.toml", f"invalid config: {exc}")]


def _check_maintained_files_exist(repo_root: Path, config: RepoWikiConfig) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for rel_path in config.maintained_files:
        if not (repo_root / rel_path).is_file():
            findings.append(_error(rel_path, f"missing maintained file: {rel_path}"))
    return findings


def _check_required_headers(repo_root: Path, config: RepoWikiConfig) -> list[LintFinding]:
    findings: list[LintFinding] = []
    maintained_files = set(config.maintained_files)
    for rel_path, required_headings in REQUIRED_TOP_LEVEL_HEADINGS.items():
        if rel_path not in maintained_files:
            continue
        target_path = repo_root / rel_path
        if not target_path.is_file():
            continue
        lines = _markdown_heading_lines(target_path)
        for heading in required_headings:
            if heading not in lines:
                findings.append(
                    _error(
                        rel_path,
                        f"missing required heading in {rel_path}: {heading}",
                    )
                )
    return findings


def _entry_section_bounds(entry_line_index: int, heading_line_indexes: list[int], total_lines: int) -> tuple[int, int]:
    start = entry_line_index + 1
    end = total_lines
    for heading_line_index in heading_line_indexes:
        if heading_line_index <= entry_line_index:
            continue
        end = heading_line_index
        break
    return start, end


def _parse_fence_marker(line: str) -> tuple[str, int, str] | None:
    stripped_leading_whitespace = line.lstrip(" \t")
    indent_width = len(line) - len(stripped_leading_whitespace)
    if indent_width > 3:
        return None
    if not stripped_leading_whitespace:
        return None

    marker_char = stripped_leading_whitespace[0]
    if marker_char not in ("`", "~"):
        return None

    marker_length = 0
    for char in stripped_leading_whitespace:
        if char != marker_char:
            break
        marker_length += 1

    if marker_length < 3:
        return None

    remainder = stripped_leading_whitespace[marker_length:]
    return marker_char, marker_length, remainder


def _toggle_fence_state(line: str, active_fence: str | None) -> str | None:
    fence_marker = _parse_fence_marker(line)
    if fence_marker is None:
        return active_fence

    marker_char, marker_length, marker_remainder = fence_marker
    if active_fence is None:
        return marker_char * marker_length

    if marker_char != active_fence[0]:
        return active_fence
    if marker_length < len(active_fence):
        return active_fence
    if marker_remainder.strip():
        return active_fence
    return None


def _iter_non_fenced_lines(lines: list[str]) -> list[tuple[int, str]]:
    non_fenced_lines: list[tuple[int, str]] = []
    active_fence: str | None = None
    for index, line in enumerate(lines):
        next_fence = _toggle_fence_state(line, active_fence)
        if next_fence != active_fence:
            active_fence = next_fence
            continue
        if active_fence is None:
            non_fenced_lines.append((index, line))
    return non_fenced_lines


def _leading_indentation_columns(line: str) -> int:
    columns = 0
    for char in line:
        if char == " ":
            columns += 1
            continue
        if char == "\t":
            columns += 4 - (columns % 4)
            continue
        break
    return columns


def _is_indented_code_block_line(line: str) -> bool:
    if not line.lstrip(" \t"):
        return False
    return _leading_indentation_columns(line) >= 4


def _markdown_heading_lines(path: Path) -> set[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {
        line.strip()
        for _, line in _iter_non_fenced_lines(lines)
        if not _is_indented_code_block_line(line)
        if line.strip().startswith("#")
    }


def _check_recent_change_entries(path: Path, rel_path: str) -> list[LintFinding]:
    findings: list[LintFinding] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    non_fenced_lines = _iter_non_fenced_lines(lines)
    heading_candidates = [
        (index, line.strip())
        for index, line in non_fenced_lines
        if not _is_indented_code_block_line(line)
        if line.strip().startswith("## ")
    ]
    heading_line_indexes = [
        index
        for index, stripped_line in heading_candidates
        if stripped_line != "## Change Entries"
    ]

    entry_line_indexes: list[int] = []
    for index, stripped in heading_candidates:
        if stripped == "## Change Entries":
            continue
        if RECENT_ENTRY_HEADING_RE.match(stripped):
            entry_line_indexes.append(index)
            continue
        if RECENT_ENTRY_PREFIX_RE.match(stripped):
            findings.append(
                _error(
                    rel_path,
                    f"recent-change entry missing commit SHA: {stripped}",
                )
            )
            continue
        if RECENT_ENTRY_DATE_STYLE_PREFIX_RE.match(stripped):
            findings.append(
                _error(
                    rel_path,
                    f"recent-change entry heading malformed: {stripped}",
                )
            )

    for entry_index in entry_line_indexes:
        start, end = _entry_section_bounds(entry_index, heading_line_indexes, len(lines))
        section_lines = [
            line
            for line_index, line in non_fenced_lines
            if start <= line_index < end
        ]
        evidence_scan_lines = [
            line
            for line in section_lines
            if not _is_indented_code_block_line(line)
        ]
        evidence_index = None
        for section_index, section_line in enumerate(evidence_scan_lines):
            if section_line.strip() == "- Verification evidence:":
                evidence_index = section_index
                break

        if evidence_index is None:
            findings.append(
                _error(
                    rel_path,
                    f"recent-change entry missing verification evidence: {lines[entry_index].strip()}",
                )
            )
            continue

        evidence_detail_lines: list[str] = []
        for candidate_line in evidence_scan_lines[evidence_index + 1 :]:
            if not candidate_line.startswith("  - "):
                break
            evidence_detail_lines.append(candidate_line)

        has_evidence_item = any(line.strip() != "-" for line in evidence_detail_lines)
        if not has_evidence_item:
            findings.append(
                _error(
                    rel_path,
                    f"recent-change entry missing verification evidence details: {lines[entry_index].strip()}",
                )
            )
    return findings


def _check_recent_changes_shape(repo_root: Path, config: RepoWikiConfig) -> list[LintFinding]:
    recent_changes_rel_path = next(
        (path for path in config.maintained_files if path.endswith("/recent-important-changes.md")),
        None,
    )
    if recent_changes_rel_path is None:
        return []

    target_path = repo_root / recent_changes_rel_path
    if not target_path.is_file():
        return []
    return _check_recent_change_entries(target_path, recent_changes_rel_path)


def lint_repo_wiki(repo_root: Path) -> list[LintFinding]:
    config, findings = _load_config(repo_root)
    if config is None:
        return findings

    findings.extend(_check_maintained_files_exist(repo_root, config))
    findings.extend(_check_required_headers(repo_root, config))
    findings.extend(_check_recent_changes_shape(repo_root, config))
    return findings


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint repo wiki files for deterministic maintenance checks.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    findings = lint_repo_wiki(Path(args.repo_root))

    for finding in findings:
        print(f"{finding.severity.upper()}: {finding.path}: {finding.message}")

    if any(finding.severity == "error" for finding in findings):
        raise SystemExit(1)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
