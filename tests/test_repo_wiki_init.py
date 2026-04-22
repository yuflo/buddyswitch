from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "tools" / "codex-skills" / "repo-wiki-maintainer"
SCRIPT_DIR = SKILL_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common import load_repo_config  # noqa: E402
from init_wiki import scaffold_repo_wiki  # noqa: E402

EXPECTED_SCAFFOLD_FILES = {
    "docs/llm-wiki/README.md",
    "docs/llm-wiki/recent-important-changes.md",
    "docs/llm-wiki/verification-map.md",
    ".llm-wiki.toml",
}
EXPECTED_SHARED_HEADER_LINES = [
    "Status: derived",
    "Last verified: TBD",
    "Covers through commit: TBD",
    "Canonical sources:",
    "Do not infer:",
    "- This file does not replace canonical docs.",
]
EXPECTED_PAGE_HEADINGS = {
    "docs/llm-wiki/README.md": [
        "# LLM Wiki",
        "## Canonical Sources",
        "## Architecture Map",
        "## Update Workflow",
    ],
    "docs/llm-wiki/recent-important-changes.md": [
        "# Recent Important Changes",
        "## Change Entries",
    ],
    "docs/llm-wiki/verification-map.md": [
        "# Verification Map",
        "## Verification Entries",
    ],
}


def test_scaffold_repo_wiki_creates_expected_files(tmp_path: Path) -> None:
    scaffold_repo_wiki(tmp_path)

    for rel in EXPECTED_SCAFFOLD_FILES:
        assert (tmp_path / rel).is_file(), f"missing scaffold file: {rel}"

    for rel, required_headings in EXPECTED_PAGE_HEADINGS.items():
        content = (tmp_path / rel).read_text(encoding="utf-8")
        for shared_header_line in EXPECTED_SHARED_HEADER_LINES:
            assert (
                shared_header_line in content
            ), f"missing shared header line in {rel}: {shared_header_line}"
        for heading in required_headings:
            assert heading in content, f"missing required heading in {rel}: {heading}"
        assert "BuddySwitch" not in content, "templates must remain generic"

    readme_content = (tmp_path / "docs/llm-wiki/README.md").read_text(encoding="utf-8")
    assert "Last refreshed:" not in readme_content
    assert "configured workflow" not in readme_content
    assert "wiki drift" not in readme_content

    generated_config = load_repo_config(tmp_path / ".llm-wiki.toml")
    assert generated_config.wiki_root == "docs/llm-wiki"
    assert generated_config.maintained_files == [
        "docs/llm-wiki/README.md",
        "docs/llm-wiki/recent-important-changes.md",
        "docs/llm-wiki/verification-map.md",
    ]


def test_scaffold_repo_wiki_fails_fast_on_existing_file_target(tmp_path: Path) -> None:
    existing_readme = tmp_path / "docs/llm-wiki/README.md"
    existing_readme.parent.mkdir(parents=True, exist_ok=True)
    existing_readme.write_text("# Existing README\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="docs/llm-wiki/README.md"):
        scaffold_repo_wiki(tmp_path)

    assert existing_readme.read_text(encoding="utf-8") == "# Existing README\n"
    assert not (tmp_path / "docs/llm-wiki/recent-important-changes.md").exists()
    assert not (tmp_path / "docs/llm-wiki/verification-map.md").exists()
    assert not (tmp_path / ".llm-wiki.toml").exists()


def test_scaffold_repo_wiki_allows_existing_valid_repo_specific_config(
    tmp_path: Path,
) -> None:
    repo_specific_config = """\
version = 1
wiki_root = "docs/llm-wiki"
recent_change_window_days = 45
recent_change_max_entries = 8
canonical_sources = [
  "AGENTS.md",
  "README.md",
  "framework/docs/architecture-overview.md",
]
maintained_files = [
  "docs/llm-wiki/README.md",
  "docs/llm-wiki/recent-important-changes.md",
  "docs/llm-wiki/verification-map.md",
]
# Optional fields are represented as strings and default to empty strings.
owner = ""
notes = ""
"""
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(repo_specific_config, encoding="utf-8")

    scaffold_repo_wiki(tmp_path)

    assert config_path.read_text(encoding="utf-8") == repo_specific_config
    assert (tmp_path / "docs/llm-wiki/README.md").is_file()
    assert (tmp_path / "docs/llm-wiki/recent-important-changes.md").is_file()
    assert (tmp_path / "docs/llm-wiki/verification-map.md").is_file()


def test_scaffold_repo_wiki_fails_fast_on_non_file_target_conflict(tmp_path: Path) -> None:
    conflicting_readme_path = tmp_path / "docs/llm-wiki/README.md"
    conflicting_readme_path.mkdir(parents=True, exist_ok=True)

    with pytest.raises(FileExistsError, match="docs/llm-wiki/README.md"):
        scaffold_repo_wiki(tmp_path)

    assert not (tmp_path / "docs/llm-wiki/recent-important-changes.md").exists()
    assert not (tmp_path / "docs/llm-wiki/verification-map.md").exists()
    assert not (tmp_path / ".llm-wiki.toml").exists()


def test_scaffold_repo_wiki_fails_fast_on_broken_symlink_target(tmp_path: Path) -> None:
    conflicting_readme_path = tmp_path / "docs/llm-wiki/README.md"
    conflicting_readme_path.parent.mkdir(parents=True, exist_ok=True)
    broken_symlink_target = tmp_path / "missing-target" / "README.md"
    try:
        conflicting_readme_path.symlink_to(broken_symlink_target)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink setup unavailable: {exc}")

    with pytest.raises(FileExistsError, match="docs/llm-wiki/README.md"):
        scaffold_repo_wiki(tmp_path)

    assert conflicting_readme_path.is_symlink()
    assert not (tmp_path / "docs/llm-wiki/recent-important-changes.md").exists()
    assert not (tmp_path / "docs/llm-wiki/verification-map.md").exists()
    assert not (tmp_path / ".llm-wiki.toml").exists()


def test_scaffold_repo_wiki_fails_fast_on_ancestor_symlink_conflict(
    tmp_path: Path,
) -> None:
    redirected_wiki_root = tmp_path / "redirected-wiki-root"
    redirected_wiki_root.mkdir(parents=True, exist_ok=True)

    symlinked_wiki_root = tmp_path / "docs/llm-wiki"
    symlinked_wiki_root.parent.mkdir(parents=True, exist_ok=True)
    try:
        symlinked_wiki_root.symlink_to(redirected_wiki_root, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink setup unavailable: {exc}")

    with pytest.raises(FileExistsError, match="docs/llm-wiki"):
        scaffold_repo_wiki(tmp_path)

    assert symlinked_wiki_root.is_symlink()
    assert not any(redirected_wiki_root.iterdir())
    assert not (tmp_path / ".llm-wiki.toml").exists()
