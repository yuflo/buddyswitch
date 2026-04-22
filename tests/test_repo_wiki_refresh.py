from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "tools" / "codex-skills" / "repo-wiki-maintainer"
SCRIPT_DIR = SKILL_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import refresh_wiki  # noqa: E402
from refresh_wiki import CanonicalConflictError, promote_change, refresh_repo_wiki  # noqa: E402


def _test_config(max_entries: int = 8) -> refresh_wiki.RepoWikiConfig:
    return refresh_wiki.RepoWikiConfig(
        version=1,
        wiki_root="docs/llm-wiki",
        recent_change_window_days=45,
        recent_change_max_entries=max_entries,
        canonical_sources=[
            "AGENTS.md",
            "README.md",
            "framework/docs/architecture-overview.md",
            "framework/docs/switch-spec.md",
            "tools/launcher/assets/runtime-AGENTS.md",
        ],
        maintained_files=[
            "docs/llm-wiki/README.md",
            "docs/llm-wiki/recent-important-changes.md",
            "docs/llm-wiki/verification-map.md",
        ],
        allowed_supporting_globs=[
            "docs/dev*/**",
            "docs/reviews/**",
            "docs/whiteboard/**",
        ],
        owner="",
        notes="",
    )


def _write_config(repo_root: Path) -> None:
    (repo_root / ".llm-wiki.toml").write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = [\n'
        '  "AGENTS.md",\n'
        '  "README.md",\n'
        '  "framework/docs/architecture-overview.md",\n'
        '  "framework/docs/switch-spec.md",\n'
        '  "tools/launcher/assets/runtime-AGENTS.md",\n'
        "]\n"
        "maintained_files = [\n"
        '  "docs/llm-wiki/README.md",\n'
        '  "docs/llm-wiki/recent-important-changes.md",\n'
        '  "docs/llm-wiki/verification-map.md",\n'
        "]\n",
        encoding="utf-8",
    )


def _write_canonical_sources(repo_root: Path) -> None:
    (repo_root / "framework" / "docs").mkdir(parents=True, exist_ok=True)
    (repo_root / "tools" / "launcher" / "assets").mkdir(parents=True, exist_ok=True)

    (repo_root / "AGENTS.md").write_text("# AGENTS\n\nBuddySwitch repo rules.\n", encoding="utf-8")
    (repo_root / "README.md").write_text(
        "# BuddySwitch\n\n"
        "resolve may materialize a zero-run task and reserve the next run envelope.\n",
        encoding="utf-8",
    )
    (repo_root / "framework" / "docs" / "architecture-overview.md").write_text(
        "# Architecture\n\n"
        "Prepare execution context without writing state.\n",
        encoding="utf-8",
    )
    (repo_root / "framework" / "docs" / "switch-spec.md").write_text(
        "# Switch Spec\n\n"
        "materialize create-mode task context when needed and reserve the next run envelope\n",
        encoding="utf-8",
    )
    (repo_root / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").write_text(
        "# Runtime AGENTS\n\nLauncher-managed runtime session notes.\n",
        encoding="utf-8",
    )


def _write_scaffolded_wiki(repo_root: Path) -> None:
    wiki_root = repo_root / "docs" / "llm-wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    (wiki_root / "README.md").write_text(
        "# LLM Wiki\n\n"
        "Status: derived\n"
        "Last verified: TBD\n"
        "Covers through commit: deadbee0\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "- README.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n\n"
        "## What BuddySwitch Is Now\n\n"
        "placeholder\n",
        encoding="utf-8",
    )
    (wiki_root / "recent-important-changes.md").write_text(
        "# Recent Important Changes\n\n"
        "Status: derived\n"
        "Last verified: TBD\n"
        "Covers through commit: deadbee0\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "- README.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n\n"
        "## Change Entries\n\n"
        "- No entries yet.\n",
        encoding="utf-8",
    )
    (wiki_root / "verification-map.md").write_text(
        "# Verification Map\n\n"
        "Status: derived\n"
        "Last verified: TBD\n"
        "Covers through commit: deadbee0\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "- README.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n\n"
        "## Verification Entries\n\n"
        "| Canonical Claim | Verification Command | Evidence Location |\n"
        "| --- | --- | --- |\n"
        "| TBD | TBD | TBD |\n",
        encoding="utf-8",
    )


def _seed_repo(repo_root: Path) -> None:
    _write_config(repo_root)
    _write_canonical_sources(repo_root)
    _write_scaffolded_wiki(repo_root)


def test_promote_change_when_runtime_model_shifted() -> None:
    change = {
        "summary": "feat: complete all-buddy runtime cutover",
        "touched_files": [
            "README.md",
            "framework/docs/switch-spec.md",
            "scripts/switch_runtime.py",
        ],
    }

    assert promote_change(change, _test_config()) is True


def test_do_not_promote_local_bugfix_without_orientation_impact() -> None:
    change = {
        "summary": "fix: tighten wiki fence parsing",
        "touched_files": [
            "tools/codex-skills/repo-wiki-maintainer/scripts/lint_wiki.py",
            "tests/test_repo_wiki_lint.py",
        ],
    }

    assert promote_change(change, _test_config()) is False


def test_promote_change_when_supporting_whiteboard_shifted_system_model() -> None:
    change = {
        "summary": "docs: track runtime redesign whiteboard",
        "touched_files": [
            "docs/whiteboard/2026-04-21-all-buddy-agentic-runtime-redesign.md",
        ],
    }

    assert promote_change(change, _test_config()) is True


def test_promote_change_uses_default_supporting_globs_when_config_omits_them() -> None:
    config_without_supporting_globs = replace(_test_config(), allowed_supporting_globs=[])
    change = {
        "summary": "docs: track runtime redesign whiteboard",
        "touched_files": [
            "docs/whiteboard/2026-04-21-all-buddy-agentic-runtime-redesign.md",
        ],
    }

    assert promote_change(change, config_without_supporting_globs) is True


def test_extract_covers_through_commit_ignores_checkpoint_without_change_entries(
    tmp_path: Path,
) -> None:
    _seed_repo(tmp_path)

    assert refresh_wiki._extract_covers_through_commit(tmp_path) is None


def test_extract_covers_through_commit_ignores_untracked_wiki_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md").write_text(
        "# Recent Important Changes\n\n"
        "Status: derived\n"
        "Last verified: 2026-04-23\n"
        "Covers through commit: deadbee0\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | cafebab | feat: complete all-buddy runtime cutover\n",
        encoding="utf-8",
    )

    def _fake_run_git(repo_root: Path, args: list[str] | tuple[str, ...]) -> str:
        if args[0] == "ls-files":
            raise subprocess.CalledProcessError(1, ["git", *args], "", "")
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(refresh_wiki, "_run_git", _fake_run_git)

    assert refresh_wiki._extract_covers_through_commit(tmp_path) is None


def test_extract_covers_through_commit_ignores_tracked_wiki_only_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs" / "llm-wiki" / "README.md").write_text(
        "# LLM Wiki\n\n"
        "Status: derived\n"
        "Last verified: 2026-04-23\n"
        "Covers through commit: cafebabe1234567\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "- README.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md").write_text(
        "# Recent Important Changes\n\n"
        "Status: derived\n"
        "Last verified: 2026-04-23\n"
        "Covers through commit: cafebabe1234567\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | cafebab | feat: complete all-buddy runtime cutover\n",
        encoding="utf-8",
    )

    resolved_sha = "cafebabe1234567890abcdef1234567890abcdef"

    def _fake_run_git(repo_root: Path, args: list[str] | tuple[str, ...]) -> str:
        if args[0] == "ls-files":
            return ""
        if args[0] == "rev-parse" and args[1] == "--verify" and args[2] == "cafebabe1234567^{commit}":
            return f"{resolved_sha}\n"
        if args[0] == "show" and args[-1] == resolved_sha:
            return "\n".join(
                [
                    "docs/llm-wiki/README.md",
                    "docs/llm-wiki/recent-important-changes.md",
                    "docs/llm-wiki/verification-map.md",
                ]
            )
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(refresh_wiki, "_run_git", _fake_run_git)

    assert refresh_wiki._extract_covers_through_commit(tmp_path) is None


def test_extract_covers_through_commit_normalizes_moving_revspec_to_full_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs" / "llm-wiki" / "README.md").write_text(
        "# LLM Wiki\n\n"
        "Status: derived\n"
        "Last verified: 2026-04-23\n"
        "Covers through commit: HEAD~1\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "- README.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md").write_text(
        "# Recent Important Changes\n\n"
        "Status: derived\n"
        "Last verified: 2026-04-23\n"
        "Covers through commit: HEAD~1\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | cafebab | feat: complete all-buddy runtime cutover\n",
        encoding="utf-8",
    )
    resolved_sha = "0123456789abcdef0123456789abcdef01234567"

    def _fake_run_git(repo_root: Path, args: list[str] | tuple[str, ...]) -> str:
        if args[0] == "ls-files":
            return ""
        if args[0] == "rev-parse" and args[1] == "--verify" and args[2] == "HEAD~1^{commit}":
            return f"{resolved_sha}\n"
        if args[0] == "show":
            return "README.md\n"
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(refresh_wiki, "_run_git", _fake_run_git)

    assert refresh_wiki._extract_covers_through_commit(tmp_path) == resolved_sha


def test_evidence_sha_parses_git_show_bullet_lines() -> None:
    block_lines = [
        "## 2026-04-22 | cafebab | feat: complete all-buddy runtime cutover",
        "- Verification evidence:",
        "  - git show --stat --oneline cafebabe1234567cafebabe1234567cafebabe",
    ]

    assert (
        refresh_wiki._evidence_sha(block_lines)
        == "cafebabe1234567cafebabe1234567cafebabe"
    )


def test_read_git_changes_does_not_let_non_promoted_rows_crowd_out_promoted_commits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _test_config(max_entries=2)
    full_rows = [
        "1111111\x1f2026-04-01\x1fchore: small cleanup",
        "2222222\x1f2026-04-02\x1ftest: add fixture",
        "a8f7a78\x1f2026-04-03\x1fdocs: update AGENTS",
        "3ba214b\x1f2026-04-04\x1fdocs: update switch spec",
    ]

    touched_files_by_sha = {
        "1111111": "tools/codex-skills/repo-wiki-maintainer/scripts/refresh_wiki.py\n",
        "2222222": "tests/test_repo_wiki_refresh.py\n",
        "a8f7a78": "AGENTS.md\n",
        "3ba214b": "framework/docs/switch-spec.md\n",
    }

    def _fake_run_git(repo_root: Path, args: list[str] | tuple[str, ...]) -> str:
        if args[0] == "log":
            # Simulate git log truncation when max-count is applied too early.
            if any(str(arg).startswith("--max-count=") for arg in args):
                return "\n".join(full_rows[:2])
            return "\n".join(full_rows)
        if args[0] == "show":
            return touched_files_by_sha[args[-1]]
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(refresh_wiki, "_run_git", _fake_run_git)

    changes = refresh_wiki.read_git_changes(tmp_path, since_commit=None, config=config)
    promoted = [change["sha"] for change in changes if promote_change(change, config)]

    assert promoted == ["a8f7a78", "3ba214b"]


def test_render_recent_changes_keeps_most_recent_promoted_entries() -> None:
    config = _test_config(max_entries=2)
    recent_changes_text = refresh_wiki._render_recent_changes(
        config,
        [
            {
                "sha": "1111111aaaaaaa",
                "date": "2026-04-01",
                "summary": "docs: first change",
                "touched_files": ["AGENTS.md"],
            },
            {
                "sha": "2222222bbbbbbb",
                "date": "2026-04-02",
                "summary": "docs: second change",
                "touched_files": ["README.md"],
            },
            {
                "sha": "3333333ccccccc",
                "date": "2026-04-03",
                "summary": "docs: third change",
                "touched_files": ["framework/docs/switch-spec.md"],
            },
        ],
        "headcommit1234567",
    )

    assert "## 2026-04-01 | 1111111 | docs: first change" not in recent_changes_text
    assert "## 2026-04-02 | 2222222 | docs: second change" in recent_changes_text
    assert "## 2026-04-03 | 3333333 | docs: third change" in recent_changes_text


def test_render_recent_changes_keeps_durable_turns_even_outside_recent_entry_limit() -> None:
    config = _test_config(max_entries=2)
    recent_changes_text = refresh_wiki._render_recent_changes(
        config,
        [
            {
                "sha": "a8f7a78abcdef12",
                "date": "2026-04-21",
                "summary": "docs: record parallel architecture rollout journey",
                "touched_files": ["docs/whiteboard/buddyswitch-parallel-architecture-recommendation-2026-04-21.md"],
            },
            {
                "sha": "2222222bbbbbbb",
                "date": "2026-04-22",
                "summary": "docs: second change",
                "touched_files": ["README.md"],
            },
            {
                "sha": "3333333ccccccc",
                "date": "2026-04-22",
                "summary": "docs: third change",
                "touched_files": ["framework/docs/switch-spec.md"],
            },
        ],
        "headcommit1234567",
    )

    assert "## 2026-04-21 | a8f7a78 | docs: record parallel architecture rollout journey" in recent_changes_text
    assert "## 2026-04-22 | 2222222 | docs: second change" in recent_changes_text
    assert "## 2026-04-22 | 3333333 | docs: third change" in recent_changes_text


def test_render_recent_changes_preserves_existing_durable_entries_when_incremental_refresh_appends_fresh_changes() -> None:
    config = _test_config(max_entries=2)
    existing_entries = [
        refresh_wiki.ExistingRecentChangeEntry(
            match_sha="a8f7a78fd7022f138cd9519e8307f96d75127cad",
            block_lines=(
                "## 2026-04-21 | a8f7a78 | docs: record parallel architecture rollout journey",
                "- Verification evidence:",
                "  - git show --stat --oneline a8f7a78fd7022f138cd9519e8307f96d75127cad",
            ),
        ),
        refresh_wiki.ExistingRecentChangeEntry(
            match_sha="3ba214be502d0ec9c0d09c70b0e9eb7cd2435e79",
            block_lines=(
                "## 2026-04-22 | 3ba214b | feat: complete all-buddy runtime cutover",
                "- Verification evidence:",
                "  - git show --stat --oneline 3ba214be502d0ec9c0d09c70b0e9eb7cd2435e79",
            ),
        ),
    ]
    recent_changes_text = refresh_wiki._render_recent_changes(
        config,
        [
            {
                "sha": "a77f0509f56a5ddc81b398a6000302ca56d1bce0",
                "date": "2026-04-22",
                "summary": "docs: track runtime redesign whiteboard",
                "touched_files": ["README.md"],
            },
        ],
        "headcommit1234567",
        existing_entries=existing_entries,
    )

    assert "## 2026-04-21 | a8f7a78 | docs: record parallel architecture rollout journey" in recent_changes_text
    assert "## 2026-04-22 | 3ba214b | feat: complete all-buddy runtime cutover" in recent_changes_text
    assert "## 2026-04-22 | a77f050 | docs: track runtime redesign whiteboard" in recent_changes_text
    assert recent_changes_text.count("\n## 2026-") == 3


def test_refresh_repo_wiki_rewrites_only_maintained_files_and_counts_promoted_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)
    untouched_path = tmp_path / "notes.md"
    untouched_path.write_text("leave me alone\n", encoding="utf-8")

    monkeypatch.setattr(
        refresh_wiki,
        "read_git_changes",
        lambda repo_root, since_commit, config: [
            {
                "sha": "cafebabe1234567",
                "date": "2026-04-22",
                "summary": "feat: complete all-buddy runtime cutover",
                "touched_files": ["README.md", "framework/docs/switch-spec.md"],
            },
            {
                "sha": "facefeed7654321",
                "date": "2026-04-21",
                "summary": "fix: tighten wiki fence parsing",
                "touched_files": ["tests/test_repo_wiki_lint.py"],
            },
        ],
    )
    monkeypatch.setattr(refresh_wiki, "resolve_head_commit", lambda repo_root: "cafebabe1234567")
    monkeypatch.setattr(refresh_wiki, "find_canonical_conflicts", lambda canonical: [])
    monkeypatch.setattr(refresh_wiki, "lint_repo_wiki", lambda repo_root: [])

    result = refresh_repo_wiki(tmp_path)

    assert result.promoted_count == 1
    assert result.updated_files == [
        "docs/llm-wiki/README.md",
        "docs/llm-wiki/recent-important-changes.md",
        "docs/llm-wiki/verification-map.md",
    ]

    readme_text = (tmp_path / "docs" / "llm-wiki" / "README.md").read_text(encoding="utf-8")
    assert "Covers through commit: cafebabe1234567" in readme_text
    assert "## Reading Order" in readme_text
    assert "- framework/docs/switch-spec.md" in readme_text

    recent_changes_text = (
        tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    ).read_text(encoding="utf-8")
    assert "## 2026-04-22 | cafebab | feat: complete all-buddy runtime cutover" in recent_changes_text
    assert "facefeed7654321" not in recent_changes_text
    assert "git show --stat --oneline cafebabe1234567" in recent_changes_text

    verification_map_text = (
        tmp_path / "docs" / "llm-wiki" / "verification-map.md"
    ).read_text(encoding="utf-8")
    assert "python3 tools/codex-skills/repo-wiki-maintainer/scripts/lint_wiki.py --repo-root ." in verification_map_text
    assert untouched_path.read_text(encoding="utf-8") == "leave me alone\n"


def test_refresh_repo_wiki_preserves_existing_recent_entries_when_incremental_range_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)
    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "Status: derived\n"
        "Last verified: 2026-04-22\n"
        "Covers through commit: cafebabe1234567\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "- README.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n\n"
        "## Change Entries\n\n"
        "## 2026-04-21 | a8f7a78 | docs: record parallel architecture rollout journey\n"
        "- Why a fresh session should care:\n"
        "  - This change touched canonical orientation paths or runtime-routing paths.\n"
        "- New truth:\n"
        "  - Re-read the cited canonical files before trusting older summaries.\n"
        "- Invalidated old assumption:\n"
        "  - Previous fresh-session context may be stale past this commit.\n"
        "- Canonical files to read:\n"
        "  - README.md\n"
        "- Verification evidence:\n"
        "  - git show --stat --oneline a8f7a78fd7022f138cd9519e8307f96d75127cad\n"
        "\n"
        "## 2026-04-22 | 3ba214b | feat: complete all-buddy runtime cutover\n"
        "- Why a fresh session should care:\n"
        "  - This change touched canonical orientation paths or runtime-routing paths.\n"
        "- New truth:\n"
        "  - Re-read the cited canonical files before trusting older summaries.\n"
        "- Invalidated old assumption:\n"
        "  - Previous fresh-session context may be stale past this commit.\n"
        "- Canonical files to read:\n"
        "  - README.md\n"
        "  - framework/docs/switch-spec.md\n"
        "- Verification evidence:\n"
        "  - git show --stat --oneline 3ba214be502d0ec9c0d09c70b0e9eb7cd2435e79\n"
        "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        refresh_wiki,
        "_extract_covers_through_commit",
        lambda repo_root: "cafebabe1234567",
    )
    monkeypatch.setattr(refresh_wiki, "_has_trusted_wiki_surface", lambda repo_root: True)
    monkeypatch.setattr(refresh_wiki, "read_git_changes", lambda repo_root, since_commit, config: [])
    monkeypatch.setattr(refresh_wiki, "resolve_head_commit", lambda repo_root: "headcommit1234567")
    monkeypatch.setattr(refresh_wiki, "find_canonical_conflicts", lambda canonical: [])
    monkeypatch.setattr(refresh_wiki, "lint_repo_wiki", lambda repo_root: [])

    first_result = refresh_repo_wiki(tmp_path)

    assert first_result.promoted_count == 0
    first_recent_changes_text = recent_changes_path.read_text(encoding="utf-8")
    assert "Covers through commit: cafebabe1234567" in first_recent_changes_text
    assert "- No promoted changes in the current refresh window." not in first_recent_changes_text
    assert "## 2026-04-21 | a8f7a78 | docs: record parallel architecture rollout journey" in first_recent_changes_text
    assert "## 2026-04-22 | 3ba214b | feat: complete all-buddy runtime cutover" in first_recent_changes_text
    assert (
        "  - git show --stat --oneline a8f7a78fd7022f138cd9519e8307f96d75127cad"
        in first_recent_changes_text
    )
    assert (
        "  - git show --stat --oneline 3ba214be502d0ec9c0d09c70b0e9eb7cd2435e79"
        in first_recent_changes_text
    )
    first_readme_text = (tmp_path / "docs" / "llm-wiki" / "README.md").read_text(encoding="utf-8")
    first_verification_map_text = (
        tmp_path / "docs" / "llm-wiki" / "verification-map.md"
    ).read_text(encoding="utf-8")
    assert "Covers through commit: cafebabe1234567" in first_readme_text
    assert "Covers through commit: cafebabe1234567" in first_verification_map_text

    second_result = refresh_repo_wiki(tmp_path)
    assert second_result.promoted_count == 0

    second_recent_changes_text = recent_changes_path.read_text(encoding="utf-8")
    second_readme_text = (tmp_path / "docs" / "llm-wiki" / "README.md").read_text(encoding="utf-8")
    second_verification_map_text = (
        tmp_path / "docs" / "llm-wiki" / "verification-map.md"
    ).read_text(encoding="utf-8")

    assert second_recent_changes_text == first_recent_changes_text
    assert second_readme_text == first_readme_text
    assert second_verification_map_text == first_verification_map_text


def test_refresh_repo_wiki_does_not_preserve_seeded_recent_entries_when_wiki_surface_is_untracked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)
    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "Status: derived\n"
        "Last verified: 2026-04-23\n"
        "Covers through commit: deadbee0\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "- README.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | cafebab | feat: complete all-buddy runtime cutover\n"
        "- Why a fresh session should care:\n"
        "  - This change touched canonical orientation paths or runtime-routing paths.\n"
        "- New truth:\n"
        "  - Re-read the cited canonical files before trusting older summaries.\n"
        "- Invalidated old assumption:\n"
        "  - Previous fresh-session context may be stale past this commit.\n"
        "- Canonical files to read:\n"
        "  - README.md\n"
        "- Verification evidence:\n"
        "  - git show --stat --oneline cafebabe1234567cafebabe1234567cafebabe\n",
        encoding="utf-8",
    )

    def _fake_run_git(repo_root: Path, args: list[str] | tuple[str, ...]) -> str:
        if args[0] == "ls-files":
            raise subprocess.CalledProcessError(1, ["git", *args], "", "")
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(refresh_wiki, "_run_git", _fake_run_git)
    monkeypatch.setattr(refresh_wiki, "read_git_changes", lambda repo_root, since_commit, config: [])
    monkeypatch.setattr(refresh_wiki, "resolve_head_commit", lambda repo_root: "headcommit1234567")
    monkeypatch.setattr(refresh_wiki, "find_canonical_conflicts", lambda canonical: [])
    monkeypatch.setattr(refresh_wiki, "lint_repo_wiki", lambda repo_root: [])

    result = refresh_repo_wiki(tmp_path)

    assert result.promoted_count == 0
    refreshed_recent_changes_text = recent_changes_path.read_text(encoding="utf-8")
    assert "## 2026-04-22 | cafebab | feat: complete all-buddy runtime cutover" not in refreshed_recent_changes_text
    assert "cafebabe1234567cafebabe1234567cafebabe" not in refreshed_recent_changes_text
    assert "- No promoted changes in the current refresh window." in refreshed_recent_changes_text

    readme_text = (tmp_path / "docs" / "llm-wiki" / "README.md").read_text(encoding="utf-8")
    verification_map_text = (
        tmp_path / "docs" / "llm-wiki" / "verification-map.md"
    ).read_text(encoding="utf-8")
    assert "Covers through commit: headcommit1234567" in refreshed_recent_changes_text
    assert "Covers through commit: headcommit1234567" in readme_text
    assert "Covers through commit: headcommit1234567" in verification_map_text


def test_refresh_repo_wiki_does_not_preserve_seeded_recent_entries_when_tracked_surface_has_no_valid_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)
    readme_path = tmp_path / "docs" / "llm-wiki" / "README.md"
    readme_path.write_text(
        readme_path.read_text(encoding="utf-8").replace(
            "Covers through commit: deadbee0",
            "Covers through commit: TBD",
        ),
        encoding="utf-8",
    )

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "Status: derived\n"
        "Last verified: 2026-04-23\n"
        "Covers through commit: deadbee0\n"
        "Canonical sources:\n"
        "- AGENTS.md\n"
        "- README.md\n"
        "Do not infer:\n"
        "- This file does not replace canonical docs.\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | cafebab | feat: complete all-buddy runtime cutover\n"
        "- Why a fresh session should care:\n"
        "  - This change touched canonical orientation paths or runtime-routing paths.\n"
        "- New truth:\n"
        "  - Re-read the cited canonical files before trusting older summaries.\n"
        "- Invalidated old assumption:\n"
        "  - Previous fresh-session context may be stale past this commit.\n"
        "- Canonical files to read:\n"
        "  - README.md\n"
        "- Verification evidence:\n"
        "  - git show --stat --oneline cafebabe1234567cafebabe1234567cafebabe\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(refresh_wiki, "_has_trusted_wiki_surface", lambda repo_root: True)
    assert refresh_wiki._extract_covers_through_commit(tmp_path) is None

    monkeypatch.setattr(refresh_wiki, "read_git_changes", lambda repo_root, since_commit, config: [])
    monkeypatch.setattr(refresh_wiki, "resolve_head_commit", lambda repo_root: "headcommit1234567")
    monkeypatch.setattr(refresh_wiki, "find_canonical_conflicts", lambda canonical: [])
    monkeypatch.setattr(refresh_wiki, "lint_repo_wiki", lambda repo_root: [])

    result = refresh_repo_wiki(tmp_path)

    assert result.promoted_count == 0
    refreshed_recent_changes_text = recent_changes_path.read_text(encoding="utf-8")
    assert "## 2026-04-22 | cafebab | feat: complete all-buddy runtime cutover" not in refreshed_recent_changes_text
    assert "cafebabe1234567cafebabe1234567cafebabe" not in refreshed_recent_changes_text
    assert "- No promoted changes in the current refresh window." in refreshed_recent_changes_text

    verification_map_text = (
        tmp_path / "docs" / "llm-wiki" / "verification-map.md"
    ).read_text(encoding="utf-8")
    assert "Covers through commit: headcommit1234567" in refreshed_recent_changes_text
    assert "Covers through commit: headcommit1234567" in readme_path.read_text(encoding="utf-8")
    assert "Covers through commit: headcommit1234567" in verification_map_text


def test_refresh_repo_wiki_blocks_on_canonical_conflict_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)
    readme_path = tmp_path / "docs" / "llm-wiki" / "README.md"
    original_readme = readme_path.read_text(encoding="utf-8")

    monkeypatch.setattr(refresh_wiki, "read_git_changes", lambda repo_root, since_commit, config: [])
    monkeypatch.setattr(refresh_wiki, "resolve_head_commit", lambda repo_root: "cafebabe1234567")
    monkeypatch.setattr(
        refresh_wiki,
        "find_canonical_conflicts",
        lambda canonical: ["resolve create-mode task materialization conflict"],
    )

    with pytest.raises(CanonicalConflictError, match="resolve create-mode task materialization conflict"):
        refresh_repo_wiki(tmp_path)

    assert readme_path.read_text(encoding="utf-8") == original_readme
