from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "tools" / "codex-skills" / "repo-wiki-maintainer"
SCRIPT_DIR = SKILL_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lint_wiki import lint_repo_wiki, main  # noqa: E402


def _write_config(repo_root: Path) -> None:
    (repo_root / ".llm-wiki.toml").write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        "maintained_files = [\n"
        '  "docs/llm-wiki/README.md",\n'
        '  "docs/llm-wiki/recent-important-changes.md",\n'
        '  "docs/llm-wiki/verification-map.md",\n'
        "]\n",
        encoding="utf-8",
    )


def _write_minimal_readme(path: Path) -> None:
    path.write_text(
        "# LLM Wiki\n\n"
        "## Canonical Sources\n\n"
        "## Architecture Map\n\n"
        "## Update Workflow\n",
        encoding="utf-8",
    )


def _write_minimal_recent_changes(path: Path, *, entry_heading: str, include_evidence: bool) -> None:
    evidence_block = (
        "- Verification evidence:\n"
        "  - python3 -m pytest tests/test_repo_wiki_config.py -q\n"
        if include_evidence
        else ""
    )
    path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        f"{entry_heading}\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n"
        f"{evidence_block}",
        encoding="utf-8",
    )


def _write_minimal_verification_map(path: Path) -> None:
    path.write_text(
        "# Verification Map\n\n"
        "## Verification Entries\n\n"
        "| Canonical Claim | Verification Command | Evidence Location |\n"
        "| --- | --- | --- |\n"
        "| TBD | TBD | TBD |\n",
        encoding="utf-8",
    )


def _write_valid_wiki(repo_root: Path) -> None:
    wiki_root = repo_root / "docs" / "llm-wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    _write_minimal_readme(wiki_root / "README.md")
    _write_minimal_recent_changes(
        wiki_root / "recent-important-changes.md",
        entry_heading="## 2026-04-22 | deadbee0 | runtime cutover",
        include_evidence=True,
    )
    _write_minimal_verification_map(wiki_root / "verification-map.md")


def test_lint_flags_recent_change_without_verification(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    _write_minimal_recent_changes(
        tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md",
        entry_heading="## 2026-04-22 | deadbee0 | runtime cutover",
        include_evidence=False,
    )

    findings = lint_repo_wiki(tmp_path)

    assert any("verification evidence" in finding.message for finding in findings)


def test_lint_flags_recent_change_without_commit_sha(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    _write_minimal_recent_changes(
        tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md",
        entry_heading="## 2026-04-22 | missing-sha | runtime cutover",
        include_evidence=True,
    )

    findings = lint_repo_wiki(tmp_path)

    assert any("commit SHA" in finding.message for finding in findings)


def test_lint_flags_missing_required_headers(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    (tmp_path / "docs" / "llm-wiki" / "README.md").write_text(
        "# LLM Wiki\n\n"
        "## Canonical Sources\n\n"
        "## Architecture Map\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any("missing required heading" in finding.message for finding in findings)


def test_lint_does_not_treat_code_fence_line_as_required_heading(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    (tmp_path / "docs" / "llm-wiki" / "README.md").write_text(
        "# LLM Wiki\n\n"
        "## Canonical Sources\n\n"
        "## Architecture Map\n\n"
        "```md\n"
        "## Update Workflow\n"
        "```\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        "missing required heading in docs/llm-wiki/README.md: ## Update Workflow" in finding.message
        for finding in findings
    )


def test_lint_flags_missing_maintained_files(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    (tmp_path / "docs" / "llm-wiki" / "verification-map.md").unlink()

    findings = lint_repo_wiki(tmp_path)

    assert any("missing maintained file" in finding.message for finding in findings)


def test_lint_flags_missing_repo_wiki_config(tmp_path: Path) -> None:
    findings = lint_repo_wiki(tmp_path)

    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].path == ".llm-wiki.toml"
    assert "missing required config file" in findings[0].message


def test_lint_flags_invalid_repo_wiki_config(tmp_path: Path) -> None:
    (tmp_path / ".llm-wiki.toml").write_text(
        "version = [\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].path == ".llm-wiki.toml"
    assert findings[0].message.startswith("invalid config:")


def test_main_exits_non_zero_on_blocking_errors(tmp_path: Path) -> None:
    _write_config(tmp_path)
    (tmp_path / "docs" / "llm-wiki").mkdir(parents=True, exist_ok=True)

    with pytest.raises(SystemExit, match="1"):
        main(["--repo-root", str(tmp_path)])


def test_main_returns_zero_when_no_blocking_errors(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    assert main(["--repo-root", str(tmp_path)]) == 0


def test_recent_changes_non_entry_heading_does_not_trigger_sha_or_evidence_errors(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | deadbee0 | runtime cutover\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n"
        "- Verification evidence:\n"
        "  - python3 -m pytest tests/test_repo_wiki_config.py -q\n\n"
        "## Notes\n\n"
        "- housekeeping details\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)
    recent_change_messages = [
        finding.message
        for finding in findings
        if finding.path == "docs/llm-wiki/recent-important-changes.md"
    ]

    assert not any("recent-change entry missing commit SHA" in message for message in recent_change_messages)
    assert not any("recent-change entry missing verification evidence" in message for message in recent_change_messages)


def test_recent_change_entry_does_not_use_notes_section_evidence(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | deadbee0 | runtime cutover\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n\n"
        "## Notes\n\n"
        "- Verification evidence:\n"
        "  - this note must not satisfy entry evidence\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        "recent-change entry missing verification evidence: ## 2026-04-22 | deadbee0 | runtime cutover"
        in finding.message
        for finding in findings
    )


def test_recent_change_entry_stops_at_notes_when_evidence_details_missing(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | deadbee0 | runtime cutover\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n"
        "- Verification evidence:\n\n"
        "## Notes\n\n"
        "- this notes bullet must not count as verification evidence\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        "recent-change entry missing verification evidence details: ## 2026-04-22 | deadbee0 | runtime cutover"
        in finding.message
        for finding in findings
    )


def test_lint_ignores_required_heading_inside_indented_long_fence(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    (tmp_path / "docs" / "llm-wiki" / "README.md").write_text(
        "# LLM Wiki\n\n"
        "## Canonical Sources\n\n"
        "## Architecture Map\n\n"
        "  ````md\n"
        "  ```md\n"
        "  ## Update Workflow\n"
        "  ```\n"
        "  ````\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        "missing required heading in docs/llm-wiki/README.md: ## Update Workflow" in finding.message
        for finding in findings
    )


def test_lint_ignores_required_heading_inside_tab_indented_long_fence(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    (tmp_path / "docs" / "llm-wiki" / "README.md").write_text(
        "# LLM Wiki\n\n"
        "## Canonical Sources\n\n"
        "## Architecture Map\n\n"
        "\t````md\n"
        "\t## Update Workflow\n"
        "\t````\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        "missing required heading in docs/llm-wiki/README.md: ## Update Workflow" in finding.message
        for finding in findings
    )


def test_lint_ignores_required_heading_inside_four_space_indented_code_block(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    (tmp_path / "docs" / "llm-wiki" / "README.md").write_text(
        "# LLM Wiki\n\n"
        "## Canonical Sources\n\n"
        "## Architecture Map\n\n"
        "    ## Update Workflow\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        "missing required heading in docs/llm-wiki/README.md: ## Update Workflow" in finding.message
        for finding in findings
    )


def test_recent_change_entry_ignores_evidence_inside_indented_long_fence(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | deadbee0 | runtime cutover\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n\n"
        "  ````md\n"
        "  ```txt\n"
        "  - Verification evidence:\n"
        "    - python3 -m pytest tests/test_repo_wiki_config.py -q\n"
        "  ```\n"
        "  ````\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        "recent-change entry missing verification evidence: ## 2026-04-22 | deadbee0 | runtime cutover"
        in finding.message
        for finding in findings
    )


def test_recent_change_entry_ignores_evidence_inside_tab_indented_long_fence(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | deadbee0 | runtime cutover\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n\n"
        "\t````md\n"
        "\t- Verification evidence:\n"
        "\t  - python3 -m pytest tests/test_repo_wiki_config.py -q\n"
        "\t````\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        "recent-change entry missing verification evidence: ## 2026-04-22 | deadbee0 | runtime cutover"
        in finding.message
        for finding in findings
    )


def test_recent_change_entry_does_not_borrow_evidence_from_later_top_level_item(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | deadbee0 | runtime cutover\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n"
        "- Verification evidence:\n"
        "- Follow-up notes:\n"
        "  - python3 -m pytest tests/test_repo_wiki_config.py -q\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        "recent-change entry missing verification evidence details: ## 2026-04-22 | deadbee0 | runtime cutover"
        in finding.message
        for finding in findings
    )


def test_recent_change_entry_ignores_indented_code_block_heading_when_finding_evidence(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | deadbee0 | runtime cutover\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n"
        "\n"
        "    ## Notes shown in a code block\n"
        "\n"
        "- Verification evidence:\n"
        "  - python3 -m pytest tests/test_repo_wiki_config.py -q\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)
    recent_change_messages = [
        finding.message
        for finding in findings
        if finding.path == "docs/llm-wiki/recent-important-changes.md"
    ]

    assert not any("recent-change entry missing verification evidence" in message for message in recent_change_messages)


def test_recent_change_entry_ignores_indented_fake_evidence_before_real_evidence(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22 | deadbee0 | runtime cutover\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n"
        "\n"
        "    - Verification evidence:\n"
        "      - this indented item is code-block content and must be ignored\n"
        "\n"
        "- Verification evidence:\n"
        "  - python3 -m pytest tests/test_repo_wiki_config.py -q\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)
    recent_change_messages = [
        finding.message
        for finding in findings
        if finding.path == "docs/llm-wiki/recent-important-changes.md"
    ]

    assert not any("recent-change entry missing verification evidence" in message for message in recent_change_messages)


def test_recent_change_entry_flags_date_style_heading_that_violates_contract(tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_valid_wiki(tmp_path)

    recent_changes_path = tmp_path / "docs" / "llm-wiki" / "recent-important-changes.md"
    recent_changes_path.write_text(
        "# Recent Important Changes\n\n"
        "## Change Entries\n\n"
        "## 2026-04-22|deadbee0|runtime cutover\n\n"
        "- Why a fresh session should care:\n"
        "- New truth:\n"
        "- Invalidated old assumption:\n"
        "- Canonical files to read:\n"
        "  - AGENTS.md\n"
        "- Verification evidence:\n"
        "  - python3 -m pytest tests/test_repo_wiki_config.py -q\n",
        encoding="utf-8",
    )

    findings = lint_repo_wiki(tmp_path)

    assert any(
        finding.path == "docs/llm-wiki/recent-important-changes.md"
        and "recent-change entry heading malformed" in finding.message
        for finding in findings
    )
