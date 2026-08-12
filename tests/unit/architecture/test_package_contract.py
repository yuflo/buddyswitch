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
    "launcher/__init__.py",
    "foundation/runtime_broker/__init__.py",
    "runtime_support/__init__.py",
    "skills/__init__.py",
)
FOUNDATION_PRIMITIVE_FILES = (
    "foundation/identity/__init__.py",
    "foundation/identity/model.py",
    "foundation/identity/profiles.py",
    "foundation/state/__init__.py",
    "foundation/state/runtime.py",
    "foundation/state/actor_private.py",
    "foundation/process_runtime/json_framing.py",
    "foundation/process_runtime/process_identity.py",
)
FOUNDATION_PRIMITIVE_DOC = "docs/arch/foundation-primitives-architecture.md"
RUNTIME_BROKER_DOC = "docs/arch/runtime-broker-architecture.md"
ACTOR_RUNTIME_DOC = "docs/arch/actor-runtime-architecture.md"
ACTOR_RUNTIME_FILES = (
    "foundation/actor_runtime/__init__.py",
    "foundation/actor_runtime/capability.py",
    "foundation/actor_runtime/codex_runtime.py",
    "foundation/actor_runtime/environment.py",
    "foundation/actor_runtime/session.py",
    "foundation/actor_runtime/side_thread.py",
    "foundation/actor_runtime/side_thread_lifecycle.py",
    "foundation/actor_runtime/side_thread_registry.py",
)
RETIRED_FOUNDATION_PATHS = (
    "src/buddyswitch/env",
    "src/buddyswitch/runtime_kernel",
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
    "env_manifest",
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
        "buddyswitch.foundation.app_server",
        "buddyswitch.foundation.browser_runtime",
        "buddyswitch.launcher",
        "buddyswitch.modules.artifact",
        "buddyswitch.modules.demand",
        "buddyswitch.modules.track",
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
        *(PACKAGE_ROOT / relative for relative in ACTOR_RUNTIME_FILES),
        *(PACKAGE_ROOT / relative for relative in FOUNDATION_PRIMITIVE_FILES),
        REPO_ROOT / ACTOR_RUNTIME_DOC,
        REPO_ROOT / FOUNDATION_PRIMITIVE_DOC,
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
    retired_foundation_paths = [
        relative
        for relative in RETIRED_FOUNDATION_PATHS
        if (REPO_ROOT / relative).exists()
    ]

    assert old_paths == []
    assert missing_owners == []
    assert missing_entrypoints == []
    assert retired_foundation_paths == []


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
        "src/buddyswitch/runtime_kernel",
        "buddyswitch.runtime_kernel",
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
        *sorted(
            (REPO_ROOT / "src" / "buddyswitch" / "modules").glob(
                "*/skills/**/SKILL.md"
            )
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
            "src/buddyswitch/foundation/tool_runtime/definition.py",
            "src/buddyswitch/foundation/tool_runtime/context.py",
            "src/buddyswitch/foundation/tool_runtime/results.py",
            "src/buddyswitch/foundation/tool_runtime/registry.py",
            "src/buddyswitch/modules/<component>/private/adapters/tool/{tool.py,_impl.py}",
            "src/buddyswitch/modules/context/",
            "src/buddyswitch/foundation/runtime_broker/protocol.py",
            "src/buddyswitch/foundation/runtime_broker/dispatcher.py",
            "src/buddyswitch/foundation/process_runtime/json_framing.py",
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
            "src/buddyswitch/application/daemon.py",
            "src/buddyswitch/application/daemon_host.py",
            "src/buddyswitch/foundation/browser_runtime/inbound.py",
            "src/buddyswitch/foundation/process_runtime/json_framing.py",
        ),
        REPO_ROOT / "docs" / "arch" / "browser-runtime-architecture.md": (
            "src/buddyswitch/foundation/browser_runtime/",
            "src/buddyswitch/application/entrypoints/browser_runtime.py",
            "src/buddyswitch/application/entrypoints/browser_cockpit_proxy.py",
            "src/buddyswitch/foundation/runtime_broker/dispatcher.py",
            "src/buddyswitch/application/daemon.py",
        ),
        REPO_ROOT / "docs" / "arch" / "demand-sys-architecture.md": (
            "src/buddyswitch/modules/demand/private/domain/demand_sys.py",
            "src/buddyswitch/modules/demand/private/state/demands.py",
        ),
        REPO_ROOT / "docs" / "arch" / "task-sys-architecture.md": (
            "src/buddyswitch/modules/task/private/domain/task_sys.py",
            "src/buddyswitch/modules/task/private/adapters/goal/handler.py",
        ),
        REPO_ROOT / "docs" / "arch" / "search-capability-architecture.md": (
            "src/buddyswitch/modules/search/module.py",
            "src/buddyswitch/modules/search/private/adapters/tool/tool.py",
            "src/buddyswitch/modules/search/private/adapters/tool/_impl.py",
            "src/buddyswitch/modules/search/tests/integration",
        ),
        REPO_ROOT / "docs" / "arch" / "track-capability-architecture.md": (
            "src/buddyswitch/modules/track/",
            "buddyswitch/objects/tracks",
            "buddyswitch/objects/track-comments",
        ),
        REPO_ROOT / "docs" / "arch" / "artifact-capability-architecture.md": (
            "src/buddyswitch/modules/artifact/",
            "buddyswitch/objects/artifacts",
            "buddyswitch/objects/artifact-attachments",
        ),
        REPO_ROOT / "docs" / "arch" / "context-capability-architecture.md": (
            "src/buddyswitch/modules/context/",
            "src/buddyswitch/modules/context/module.py",
            "src/buddyswitch/modules/context/private/adapters/tool/tool.py",
            "src/buddyswitch/modules/context/private/adapters/tool/_impl.py",
        ),
        REPO_ROOT / "docs" / "arch" / "communication-capability-architecture.md": (
            "src/buddyswitch/modules/communication/",
            "WebRouteRegistration",
            "WebWorkerRegistration",
        ),
        REPO_ROOT / FOUNDATION_PRIMITIVE_DOC: (
            "src/buddyswitch/foundation/identity/model.py",
            "src/buddyswitch/foundation/identity/profiles.py",
            "src/buddyswitch/foundation/state/runtime.py",
            "src/buddyswitch/foundation/state/actor_private.py",
            "src/buddyswitch/foundation/process_runtime/process_identity.py",
            "src/buddyswitch/foundation/process_runtime/json_framing.py",
        ),
        REPO_ROOT / RUNTIME_BROKER_DOC: (
            "src/buddyswitch/foundation/runtime_broker/",
            "src/buddyswitch/foundation/runtime_broker/protocol.py",
            "src/buddyswitch/foundation/runtime_broker/coordinator.py",
            "src/buddyswitch/foundation/runtime_broker/dispatcher.py",
            "src/buddyswitch/foundation/runtime_broker/client.py",
            "src/buddyswitch/foundation/runtime_broker/server.py",
            "src/buddyswitch/foundation/runtime_broker/lifecycle.py",
            "src/buddyswitch/foundation/process_runtime/json_framing.py",
        ),
        REPO_ROOT / ACTOR_RUNTIME_DOC: (
            "src/buddyswitch/foundation/actor_runtime/",
            "src/buddyswitch/foundation/actor_runtime/capability.py",
            "src/buddyswitch/foundation/actor_runtime/codex_runtime.py",
            "src/buddyswitch/foundation/actor_runtime/environment.py",
            "src/buddyswitch/foundation/actor_runtime/session.py",
            "src/buddyswitch/foundation/actor_runtime/side_thread.py",
            "src/buddyswitch/foundation/actor_runtime/side_thread_lifecycle.py",
            "src/buddyswitch/foundation/actor_runtime/side_thread_registry.py",
        ),
    }
    missing_required_paths = sorted(
        (owner.relative_to(REPO_ROOT).as_posix(), required_path)
        for owner, required_paths in required_paths_by_owner.items()
        for required_path in required_paths
        if required_path not in owner.read_text(encoding="utf-8")
    )
    assert missing_required_paths == []
