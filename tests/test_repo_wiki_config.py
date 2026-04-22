import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "tools" / "codex-skills" / "repo-wiki-maintainer"
SCRIPT_DIR = SKILL_ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common import load_repo_config  # noqa: E402

EXPECTED_FILES = (
    SKILL_ROOT / "SKILL.md",
    SKILL_ROOT / "agents" / "openai.yaml",
    SKILL_ROOT / "references" / "workflow.md",
    SKILL_ROOT / "references" / "page-schemas.md",
    SKILL_ROOT / "references" / "repo-config.md",
    SKILL_ROOT / "references" / "lint-rules.md",
    SKILL_ROOT / "scripts" / "common.py",
    ROOT / ".llm-wiki.toml",
)
EXPECTED_OPENAI_YAML_KEYS = {
    "display_name",
    "short_description",
    "default_prompt",
}
REFERENCE_TOP_LEVEL_TITLES = {
    SKILL_ROOT / "references" / "workflow.md": "# Workflow",
    SKILL_ROOT / "references" / "page-schemas.md": "# Page Schemas",
    SKILL_ROOT / "references" / "repo-config.md": "# Repo Config",
    SKILL_ROOT / "references" / "lint-rules.md": "# Lint Rules",
}


def test_repo_wiki_maintainer_skill_package_layout() -> None:
    assert SKILL_ROOT.is_dir(), f"missing skill root: {SKILL_ROOT.relative_to(ROOT)}"
    assert (SKILL_ROOT / "agents").is_dir(), "missing agents directory"
    assert (SKILL_ROOT / "references").is_dir(), "missing references directory"
    for path in EXPECTED_FILES:
        assert path.is_file(), f"missing file: {path.relative_to(ROOT)}"


def test_repo_wiki_skill_scaffold_shape() -> None:
    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    skill_lines = skill_text.splitlines()

    headings = {
        line.strip()
        for line in skill_lines
        if line.strip().startswith("## ")
    }
    assert skill_lines[0].strip() == "---"
    assert "name: repo-wiki-maintainer" in skill_lines
    assert "## Maintenance Actions" in headings
    assert "## Bootstrap Contract" in headings
    assert "## Allowed Write Surface" in headings
    assert "## Runtime Boundary" in headings

    assert "`wiki-init`" in skill_text
    assert "`wiki-refresh`" in skill_text
    assert "`wiki-lint`" in skill_text
    assert "`.llm-wiki.toml`" in skill_text


def test_repo_wiki_scaffold_metadata_and_reference_titles() -> None:
    openai_yaml = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    yaml_top_level_values = {
        line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
        for line in openai_yaml.splitlines()
        if line.strip() and not line.startswith((" ", "\t")) and ":" in line
    }
    assert EXPECTED_OPENAI_YAML_KEYS.issubset(yaml_top_level_values.keys())
    for key in EXPECTED_OPENAI_YAML_KEYS:
        assert yaml_top_level_values[key], f"missing value for {key}"

    prompt = yaml_top_level_values["default_prompt"].lower()
    assert ("init" in prompt) or ("initialize" in prompt)
    assert "refresh" in prompt
    assert "lint" in prompt

    for path, expected_title in REFERENCE_TOP_LEVEL_TITLES.items():
        text = path.read_text(encoding="utf-8")
        first_non_empty_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        assert first_non_empty_line == expected_title, f"unexpected title in {path.relative_to(ROOT)}"


def test_repo_wiki_scaffold_repo_config_and_lint_contract_shape() -> None:
    repo_config_text = (SKILL_ROOT / "references" / "repo-config.md").read_text(encoding="utf-8")
    repo_config_lower = repo_config_text.lower()

    assert "`conflict_policy`" not in repo_config_text
    assert "block_on_canonical_conflict" in repo_config_lower

    page_schemas_text = (SKILL_ROOT / "references" / "page-schemas.md").read_text(encoding="utf-8")
    lint_rules_text = (SKILL_ROOT / "references" / "lint-rules.md").read_text(encoding="utf-8")

    assert "## Required Top-Level Headings" in page_schemas_text
    assert "## Heading Contract Checks" in lint_rules_text


def test_load_repo_config_reads_required_fields(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/llm-wiki/README.md"]\n',
        encoding="utf-8",
    )

    config = load_repo_config(config_path)

    assert config.version == 1
    assert config.wiki_root == "docs/llm-wiki"
    assert config.recent_change_window_days == 45
    assert config.recent_change_max_entries == 8
    assert config.canonical_sources == ["AGENTS.md"]
    assert config.maintained_files == ["docs/llm-wiki/README.md"]
    assert config.allowed_supporting_globs == []


def test_load_repo_config_optional_fields_default_to_empty_strings(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/llm-wiki/README.md"]\n',
        encoding="utf-8",
    )

    config = load_repo_config(config_path)

    assert config.owner == ""
    assert config.notes == ""
    assert config.allowed_supporting_globs == []


def test_load_repo_config_reads_allowed_supporting_globs_when_present(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/llm-wiki/README.md"]\n'
        'allowed_supporting_globs = ["docs/dev*/**", "docs/whiteboard/**"]\n',
        encoding="utf-8",
    )

    config = load_repo_config(config_path)

    assert config.allowed_supporting_globs == ["docs/dev*/**", "docs/whiteboard/**"]


def test_load_repo_config_rejects_missing_required_field(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required config key: maintained_files"):
        load_repo_config(config_path)


@pytest.mark.parametrize(
    "field_name",
    ("version", "recent_change_window_days", "recent_change_max_entries"),
)
def test_load_repo_config_rejects_boolean_for_required_integer_fields(
    tmp_path: Path, field_name: str
) -> None:
    config_values = {
        "version": "1",
        "recent_change_window_days": "45",
        "recent_change_max_entries": "8",
    }
    config_values[field_name] = "true"

    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        f'version = {config_values["version"]}\nwiki_root = "docs/llm-wiki"\n'
        f'recent_change_window_days = {config_values["recent_change_window_days"]}\n'
        f'recent_change_max_entries = {config_values["recent_change_max_entries"]}\n'
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/llm-wiki/README.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=rf"config key {field_name} must be an integer"):
        load_repo_config(config_path)


@pytest.mark.parametrize(
    "maintained_entry",
    ("docs/wiki/README.md",),
)
def test_load_repo_config_rejects_maintained_files_outside_wiki_root(
    tmp_path: Path, maintained_entry: str
) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        f'maintained_files = ["{maintained_entry}"]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="config key maintained_files must contain only files under wiki_root",
    ):
        load_repo_config(config_path)


def test_load_repo_config_rejects_non_canonical_maintained_file_path(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/llm-wiki/../../AGENTS.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="config key maintained_files must be a canonical relative path",
    ):
        load_repo_config(config_path)


def test_load_repo_config_rejects_non_canonical_canonical_source_path(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["../outside.md"]\n'
        'maintained_files = ["docs/llm-wiki/README.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="config key canonical_sources must be a canonical relative path",
    ):
        load_repo_config(config_path)


def test_load_repo_config_rejects_backslash_separated_repo_relative_path(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["framework\\\\docs\\\\architecture-overview.md"]\n'
        'maintained_files = ["docs/llm-wiki/README.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="config key canonical_sources must be a canonical relative path",
    ):
        load_repo_config(config_path)


def test_load_repo_config_rejects_non_canonical_wiki_root_path(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki/.."\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/README.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="config key wiki_root must be a canonical relative path"):
        load_repo_config(config_path)


def test_load_repo_config_rejects_directory_style_maintained_file_entry(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/llm-wiki/subdir/"]\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="config key maintained_files must be a canonical relative path",
    ):
        load_repo_config(config_path)


def test_load_repo_config_rejects_invalid_recent_change_window_days(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 0\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/llm-wiki/README.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="config key recent_change_window_days must be greater than 0"):
        load_repo_config(config_path)


def test_load_repo_config_rejects_invalid_recent_change_max_entries(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 1\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = -1\n"
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/llm-wiki/README.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="config key recent_change_max_entries must be greater than 0"):
        load_repo_config(config_path)


def test_load_repo_config_rejects_unsupported_version(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki.toml"
    config_path.write_text(
        'version = 999\nwiki_root = "docs/llm-wiki"\n'
        "recent_change_window_days = 45\n"
        "recent_change_max_entries = 8\n"
        'canonical_sources = ["AGENTS.md"]\n'
        'maintained_files = ["docs/llm-wiki/README.md"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="config key version must equal 1"):
        load_repo_config(config_path)


def test_repo_llm_wiki_toml_matches_loader_contract() -> None:
    config = load_repo_config(ROOT / ".llm-wiki.toml")

    assert config.version == 1
    assert config.wiki_root == "docs/llm-wiki"
    assert config.recent_change_window_days > 0
    assert config.recent_change_max_entries > 0
    assert config.canonical_sources
    assert config.maintained_files
    assert config.owner == ""
    assert config.notes == ""
