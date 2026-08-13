"""Static contract for the single BuddySwitch distribution."""

from __future__ import annotations

from pathlib import Path
import tomllib

from tests.support.paths import REPO_ROOT


PYPROJECT = REPO_ROOT / "pyproject.toml"
PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"

RETIRED_EMPTY_PACKAGE_ROOTS = (
    PACKAGE_ROOT / "config",
    PACKAGE_ROOT / "launcher",
)


def test_retired_empty_packages_are_absent() -> None:
    for path in RETIRED_EMPTY_PACKAGE_ROOTS:
        assert not path.exists(), path


def test_pyproject_is_the_only_exact_package_build_owner() -> None:
    assert PYPROJECT.is_file()
    assert not (REPO_ROOT / "setup.py").exists()
    assert not (REPO_ROOT / "setup.cfg").exists()

    document = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert document["build-system"] == {
        "requires": ["setuptools>=58", "wheel"],
        "build-backend": "setuptools.build_meta",
    }
    assert document["project"]["name"] == "buddyswitch"
    assert document["tool"]["setuptools"]["package-dir"] == {"": "src"}
    assert document["tool"]["setuptools"]["include-package-data"] is False


def test_package_data_names_only_current_runtime_asset_owners() -> None:
    package_data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))[
        "tool"
    ]["setuptools"]["package-data"]
    assert set(package_data) == {
        "buddyswitch.roles",
        "buddyswitch.contracts",
        "buddyswitch.foundation.app_server",
        "buddyswitch.foundation.browser_runtime",
        "buddyswitch.foundation.cli_runtime",
        "buddyswitch.foundation.host_control",
        "buddyswitch.foundation.web_runtime",
        "buddyswitch.modules.artifact",
        "buddyswitch.modules.demand",
        "buddyswitch.modules.track",
    }
    assert package_data["buddyswitch.roles"] == [
        "*/AGENTS.md",
        "*/skills/**/*.md",
        "*/skills/**/*.json",
        "*/assets/**/*.md",
        "*/assets/**/*.json",
    ]
    role_patterns = package_data["buddyswitch.roles"]
    assert "*/AGENTS.md" in role_patterns
    assert "*/skills/**/*.md" in role_patterns
    assert not any("tests" in pattern for pattern in role_patterns)


def test_role_packages_and_role_host_are_packaged_source_owners() -> None:
    assert (PACKAGE_ROOT / "foundation" / "role_host" / "__init__.py").is_file()
    role_packages = {
        path.name: path
        for path in (PACKAGE_ROOT / "roles").iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }
    assert role_packages
    for package in role_packages.values():
        assert (package / "__init__.py").is_file()
        assert (package / "role.py").is_file()
        assert (package / "AGENTS.md").is_file()
        assert (package / "assets" / "result-schema.json").is_file()


def test_retired_central_role_truth_and_entrypoints_are_absent() -> None:
    for path in (
        PACKAGE_ROOT / "catalog",
        PACKAGE_ROOT / "runtime_support",
        PACKAGE_ROOT / "skills",
        PACKAGE_ROOT / "launcher" / "assets" / "roles",
        PACKAGE_ROOT / "application" / "role_source.py",
        PACKAGE_ROOT / "application" / "entrypoints" / "env_manifest.py",
        PACKAGE_ROOT / "application" / "entrypoints" / "env_profiles.py",
        PACKAGE_ROOT / "contracts" / "role-env-profile.json",
        PACKAGE_ROOT / "contracts" / "schemas" / "dev" / "dev-result.json",
    ):
        assert not path.exists(), path


def test_current_guidance_names_rolehost_and_role_packages_only() -> None:
    current_documents = (
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        *sorted((REPO_ROOT / "docs" / "arch").glob("*.md")),
    )
    retired_tokens = (
        "src/buddyswitch/catalog/manifest.toml",
        "src/buddyswitch/runtime_support/",
        "src/buddyswitch/launcher/assets/roles/",
        "src/buddyswitch/skills/",
    )
    violations = [
        (path.relative_to(REPO_ROOT).as_posix(), token)
        for path in current_documents
        for token in retired_tokens
        if token in path.read_text(encoding="utf-8")
    ]
    assert violations == []
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "src/buddyswitch/foundation/role_host/" in readme
    assert "src/buddyswitch/roles/<package_name>/" in readme
