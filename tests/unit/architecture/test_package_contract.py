"""Static contract for the single BuddySwitch distribution."""

from __future__ import annotations

from pathlib import Path
import tomllib

from tests.support.paths import REPO_ROOT


PYPROJECT = REPO_ROOT / "pyproject.toml"
PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"
OLD_RUNTIME_SOURCES = (
    "scripts/env",
    "scripts/runtime_kernel",
    "scripts/runtime_store",
    "scripts/artifact_selection.py",
    "scripts/browser_evidence.py",
    "scripts/env_cleanup.py",
    "scripts/env_legacy_store.py",
    "scripts/env_manifest.py",
    "scripts/env_profiles.py",
    "scripts/env_store.py",
    "scripts/output_schema.py",
    "scripts/runtime_skills.py",
    "scripts/turn_runtime.py",
    "tools/__init__.py",
    "tools/launcher",
    "buddyswitch/skills",
    "buddyswitch/env-profiles",
    "buddyswitch/manifest.toml",
    "framework/contracts",
    "framework/config",
    "framework/schemas",
    "framework/agent-registry.md",
)
PACKAGE_OWNER_FILES = (
    "catalog/__init__.py",
    "catalog/manifest.toml",
    "config/__init__.py",
    "contracts/__init__.py",
    "env/__init__.py",
    "launcher/__init__.py",
    "runtime_kernel/__init__.py",
    "runtime_support/__init__.py",
    "skills/__init__.py",
)
PACKAGE_ENTRYPOINTS = (
    "runtime_activation",
    "cli",
    "web",
    "central_daemon",
    "instance_daemon",
    "runtime_broker",
    "env_mcp",
    "app_server",
    "actor_build",
    "browser_runtime",
    "browser_cockpit_proxy",
    "cleanup",
    "diagnostics",
    "browser_evidence",
    "artifact_selection",
)


def test_pyproject_is_the_only_exact_package_build_owner() -> None:
    assert PYPROJECT.is_file()
    assert not (REPO_ROOT / "setup.py").exists()
    assert not (REPO_ROOT / "setup.cfg").exists()

    document = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert document["build-system"] == {
        "requires": ["setuptools>=58", "wheel"],
        "build-backend": "setuptools.build_meta",
    }
    project = document["project"]
    assert project["name"] == "buddyswitch"
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.11"
    assert project.get("dependencies", []) == []
    assert project.get("scripts", {}) == {}

    setuptools = document["tool"]["setuptools"]
    assert setuptools["package-dir"] == {"": "src"}
    assert setuptools["include-package-data"] is False
    assert setuptools["packages"]["find"] == {
        "where": ["src"],
        "include": ["buddyswitch*"],
        "exclude": [
            "buddyswitch.tests*",
            "buddyswitch.*.tests*",
        ],
        "namespaces": False,
    }


def test_package_data_is_limited_to_explicit_runtime_asset_roots_and_classes() -> None:
    document = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    package_data = document["tool"]["setuptools"]["package-data"]
    assert set(package_data) == {
        "buddyswitch.catalog",
        "buddyswitch.config",
        "buddyswitch.contracts",
        "buddyswitch.launcher",
        "buddyswitch.skills",
    }
    patterns = {
        pattern
        for rows in package_data.values()
        for pattern in rows
    }
    for suffix in (".toml", ".json", ".md", ".html", ".css", ".js", ".sh"):
        assert any(pattern.endswith(suffix) for pattern in patterns)
    assert all(
        not any(retired in pattern for retired in ("tests/", "docs/", "projects/"))
        for pattern in patterns
    )


def test_minimal_package_and_activation_entrypoint_exist_under_src_only() -> None:
    expected = (
        PACKAGE_ROOT / "__init__.py",
        PACKAGE_ROOT / "application" / "__init__.py",
        PACKAGE_ROOT / "application" / "entrypoints" / "__init__.py",
        PACKAGE_ROOT / "application" / "entrypoints" / "runtime_activation.py",
        PACKAGE_ROOT / "foundation" / "__init__.py",
        PACKAGE_ROOT / "foundation" / "process_runtime" / "__init__.py",
        PACKAGE_ROOT / "foundation" / "process_runtime" / "activation.py",
    )
    assert [path.relative_to(REPO_ROOT).as_posix() for path in expected if not path.is_file()] == []


def test_atomic_cutover_has_one_source_and_entrypoint_topology() -> None:
    old_paths = [
        relative
        for relative in OLD_RUNTIME_SOURCES
        if (REPO_ROOT / relative).exists()
    ]
    missing_owners = [
        relative
        for relative in PACKAGE_OWNER_FILES
        if not (PACKAGE_ROOT / relative).is_file()
    ]
    missing_entrypoints = [
        module
        for module in PACKAGE_ENTRYPOINTS
        if not (
            PACKAGE_ROOT
            / "application"
            / "entrypoints"
            / f"{module}.py"
        ).is_file()
    ]

    assert old_paths == []
    assert missing_owners == []
    assert missing_entrypoints == []


def test_current_guidance_names_only_current_installed_package_owners() -> None:
    retired_tokens = (
        "scripts/env/",
        "scripts/runtime_kernel/",
        "tools/launcher/",
        "framework/contracts/",
        "buddyswitch/manifest.toml",
        "buddyswitch/env-profiles/",
        "env_legacy_store",
        "sys.path.insert",
        "spec_from_file_location",
        "--repo-root",
        "PYTHONPATH",
    )
    guidance_paths = (
        REPO_ROOT / "README.md",
        REPO_ROOT / "AGENTS.md",
        *sorted((REPO_ROOT / "docs" / "arch").glob("*.md")),
        *sorted(
            (REPO_ROOT / "src" / "buddyswitch" / "launcher" / "assets" / "roles").glob(
                "*/AGENTS.md"
            )
        ),
        *sorted(
            (REPO_ROOT / "src" / "buddyswitch" / "skills").glob("**/SKILL.md")
        ),
    )
    violations: list[tuple[str, str]] = []
    for path in guidance_paths:
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        document = path.read_text(encoding="utf-8")
        for token in retired_tokens:
            violations.extend(
                (relative_path, token)
                for _ in range(document.count(token))
            )
    assert sorted(violations) == []

    required_paths_by_owner = {
        REPO_ROOT / "README.md": (
            "pyproject.toml",
            "src/buddyswitch/catalog/manifest.toml",
            "src/buddyswitch/env/tool_runtime/definition.py",
            "src/buddyswitch/env/tool_runtime/context.py",
            "src/buddyswitch/env/tool_runtime/results.py",
            "src/buddyswitch/env/tool_runtime/registry.py",
            "src/buddyswitch/env/tools/<tool>/tool.py",
            "src/buddyswitch/env/tools/<tool>/_impl.py",
            "src/buddyswitch/runtime_kernel/protocol.py",
            "src/buddyswitch/runtime_kernel/dispatcher.py",
            "src/buddyswitch/contracts/prepare-turn-context.json",
            "src/buddyswitch/contracts/{pm,design,dev,market,test}.md",
            "src/buddyswitch/launcher/assets/roles/<role>/AGENTS.md",
            "tests/",
        ),
        REPO_ROOT / "AGENTS.md": (
            "src/buddyswitch/catalog/manifest.toml",
            "src/buddyswitch/launcher/assets/roles/<role>/AGENTS.md",
        ),
        REPO_ROOT / "docs" / "arch" / "daemon-service-architecture.md": (
            "src/buddyswitch/launcher/instance_daemon.py",
        ),
        REPO_ROOT / "docs" / "arch" / "demand-sys-architecture.md": (
            "src/buddyswitch/env/domain/demand_sys.py",
            "src/buddyswitch/env/repos/demands.py",
        ),
        REPO_ROOT / "docs" / "arch" / "task-sys-architecture.md": (
            "src/buddyswitch/env/domain/task_sys.py",
            "src/buddyswitch/launcher/task_goal_handler.py",
        ),
    }
    missing_required_paths = sorted(
        (owner.relative_to(REPO_ROOT).as_posix(), required_path)
        for owner, required_paths in required_paths_by_owner.items()
        for required_path in required_paths
        if required_path not in owner.read_text(encoding="utf-8")
    )
    assert missing_required_paths == []
