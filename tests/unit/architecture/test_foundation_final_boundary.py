"""Bounded Foundation and RoleHost ownership proof."""

from __future__ import annotations

import ast
from dataclasses import fields
import inspect
from pathlib import Path

from tests.support.paths import REPO_ROOT


PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"
FOUNDATION_ROOT = PACKAGE_ROOT / "foundation"
ROLES_ROOT = PACKAGE_ROOT / "roles"
FORBIDDEN_FOUNDATION_IMPORT_ROOTS = (
    "buddyswitch.application",
    "buddyswitch.launcher",
    "buddyswitch.modules",
    "buddyswitch.runtime_support",
    "buddyswitch.roles",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _required_parameter(callable_object: object, name: str) -> None:
    parameter = inspect.signature(callable_object).parameters[name]
    assert parameter.default is inspect.Parameter.empty


def test_foundation_imports_no_application_module_or_concrete_role() -> None:
    violations: list[tuple[str, str]] = []
    for path in sorted(FOUNDATION_ROOT.rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        violations.extend(
            (relative, imported)
            for imported in _imports(path)
            if any(
                imported == root or imported.startswith(f"{root}.")
                for root in FORBIDDEN_FOUNDATION_IMPORT_ROOTS
            )
        )
    assert violations == []


def test_role_dependent_foundation_inputs_are_narrow_and_application_supplied() -> None:
    from buddyswitch.foundation.state import cleanup
    from buddyswitch.foundation.tool_runtime import registry

    _required_parameter(cleanup.main, "valid_role_ids")
    _required_parameter(cleanup.build_cleanup_plan, "valid_role_ids")
    _required_parameter(registry.configure_authorizer, "authorizer")
    _required_parameter(registry.configure_role_runtime_resolver, "resolver")

    build_source = (PACKAGE_ROOT / "application" / "build.py").read_text(encoding="utf-8")
    cleanup_source = (
        PACKAGE_ROOT / "application" / "entrypoints" / "cleanup.py"
    ).read_text(encoding="utf-8")
    assert "RoleHost.discover(" in build_source
    assert "artifact_public.VALID_ARTIFACT_TEMPLATES" in build_source
    assert "registry.configure_role_runtime_resolver(application.role_host.runtime)" in build_source
    assert "valid_role_ids=application.role_host.valid_role_ids" in cleanup_source


def test_retired_central_role_roots_and_entrypoints_are_absent() -> None:
    for path in (
        PACKAGE_ROOT / "catalog",
        PACKAGE_ROOT / "runtime_support",
        PACKAGE_ROOT / "skills",
        PACKAGE_ROOT / "launcher" / "assets" / "roles",
        PACKAGE_ROOT / "application" / "role_source.py",
        PACKAGE_ROOT / "application" / "entrypoints" / "env_manifest.py",
        PACKAGE_ROOT / "application" / "entrypoints" / "env_profiles.py",
        PACKAGE_ROOT / "contracts" / "role-env-profile.json",
    ):
        assert not path.exists(), path


def test_reviewed_role_packages_are_the_only_live_role_topology() -> None:
    package_directories = {
        path.name
        for path in ROLES_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }
    assert package_directories
    for package_name in package_directories:
        package = ROLES_ROOT / package_name
        assert (package / "role.py").is_file()
        assert (package / "AGENTS.md").is_file()


def test_role_host_contract_contains_only_consumer_earned_role_facts() -> None:
    from buddyswitch.foundation.role_host import RoleDescriptor, RoleRuntime

    descriptor_fields = {field.name for field in fields(RoleDescriptor)}
    runtime_fields = {field.name for field in fields(RoleRuntime)}
    for retired in (
        "market_research_evidence",
        "ordinary_web_fallback",
        "native_codex_web_search",
    ):
        assert retired not in descriptor_fields
        assert retired not in runtime_fields

    source = (
        PACKAGE_ROOT / "foundation" / "role_host" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "_VALID_ARTIFACT_TEMPLATES" not in source
