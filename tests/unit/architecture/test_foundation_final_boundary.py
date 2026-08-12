"""Bounded final S5 ownership and residue proof for Foundation."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from tests.support.paths import REPO_ROOT


PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"
FOUNDATION_ROOT = PACKAGE_ROOT / "foundation"
RUNTIME_SUPPORT_ROOT = PACKAGE_ROOT / "runtime_support"
LAUNCHER_ROOT = PACKAGE_ROOT / "launcher"
CATALOG_ROOT = PACKAGE_ROOT / "catalog"
FINAL_OWNER_FILES = (
    FOUNDATION_ROOT / "composition" / "__init__.py",
    FOUNDATION_ROOT / "state" / "cleanup.py",
    FOUNDATION_ROOT / "cli_runtime" / "diagnostics.py",
)
RETIRED_GENERIC_FILES = (
    RUNTIME_SUPPORT_ROOT / "env_cleanup.py",
    RUNTIME_SUPPORT_ROOT / "skill_contracts.py",
    RUNTIME_SUPPORT_ROOT / "turn_runtime.py",
)
FORBIDDEN_FOUNDATION_IMPORT_ROOTS = (
    "buddyswitch.application",
    "buddyswitch.launcher",
    "buddyswitch.modules",
    "buddyswitch.runtime_support",
)
FORBIDDEN_FOUNDATION_EMBEDDED_ROOTS = (
    "buddyswitch/launcher",
    "buddyswitch/modules",
    "buddyswitch/runtime_support",
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


def test_generic_foundation_owners_and_passive_contracts_are_direct() -> None:
    assert all(path.is_file() for path in FINAL_OWNER_FILES)
    assert all(not path.exists() for path in RETIRED_GENERIC_FILES)

    from buddyswitch.foundation.composition import (
        CleanupContribution,
        CleanupIndexProjection,
        ModuleAssembly,
        OwnedStatePath,
        SkillExport,
    )

    assert {
        owner.__module__
        for owner in (
            ModuleAssembly,
            SkillExport,
            CleanupContribution,
            CleanupIndexProjection,
            OwnedStatePath,
        )
    } == {"buddyswitch.foundation.composition"}


def test_every_foundation_representation_is_free_of_upward_roots() -> None:
    violations: list[tuple[str, str]] = []
    for path in sorted(FOUNDATION_ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in {
            ".py",
            ".sh",
            ".json",
            ".md",
            ".html",
            ".css",
            ".js",
        }:
            continue
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        violations.extend(
            (relative, root)
            for root in FORBIDDEN_FOUNDATION_EMBEDDED_ROOTS
            if root in source
        )
        if path.suffix == ".py":
            violations.extend(
                (relative, imported)
                for imported in _imports(path)
                if any(
                    imported == root or imported.startswith(f"{root}.")
                    for root in FORBIDDEN_FOUNDATION_IMPORT_ROOTS
                )
            )
    assert violations == []


def test_role_dependent_foundation_inputs_are_required_and_application_supplied() -> None:
    from buddyswitch.foundation.cli_runtime import diagnostics
    from buddyswitch.foundation.runtime_broker import broker, dispatcher
    from buddyswitch.foundation.state import cleanup

    _required_parameter(diagnostics.main, "manifest_path")
    _required_parameter(cleanup.main, "default_manifest_path")
    _required_parameter(cleanup.main, "valid_role_ids_loader")
    _required_parameter(cleanup.build_cleanup_plan, "valid_role_ids_loader")
    _required_parameter(dispatcher.dispatch_runtime_request, "manifest_loader")
    _required_parameter(broker.dispatch_runtime_request, "manifest_loader")
    _required_parameter(broker.main, "manifest_loader")

    application_sources = {
        "cleanup": (
            PACKAGE_ROOT / "application" / "entrypoints" / "cleanup.py"
        ).read_text(encoding="utf-8"),
        "diagnostics": (
            PACKAGE_ROOT / "application" / "entrypoints" / "diagnostics.py"
        ).read_text(encoding="utf-8"),
        "runtime_broker": (
            PACKAGE_ROOT / "application" / "entrypoints" / "runtime_broker.py"
        ).read_text(encoding="utf-8"),
    }
    assert "valid_role_ids_loader=load_valid_role_ids" in application_sources["cleanup"]
    assert "default_manifest_path=env_manifest.DEFAULT_MANIFEST" in application_sources["cleanup"]
    assert "diagnostics.main(manifest_path=env_manifest.DEFAULT_MANIFEST)" in application_sources["diagnostics"]
    assert "broker.main(manifest_loader=env_manifest.load_manifest)" in application_sources["runtime_broker"]


def test_remaining_historical_roots_are_only_current_s6_role_inputs() -> None:
    assert {
        path.relative_to(RUNTIME_SUPPORT_ROOT).as_posix()
        for path in RUNTIME_SUPPORT_ROOT.rglob("*")
        if path.is_file()
    } == {
        "__init__.py",
        "env_manifest.py",
        "env_profiles.py",
        "role_auth.py",
        "runtime_skills.py",
    }
    assert {
        path.relative_to(LAUNCHER_ROOT).as_posix()
        for path in LAUNCHER_ROOT.rglob("*")
        if path.is_file()
    } == {
        "__init__.py",
        "assets/roles/design/AGENTS.md",
        "assets/roles/dev/AGENTS.md",
        "assets/roles/market/AGENTS.md",
        "assets/roles/pm/AGENTS.md",
        "assets/roles/test/AGENTS.md",
    }
    assert {
        path.relative_to(CATALOG_ROOT).as_posix()
        for path in CATALOG_ROOT.rglob("*")
        if path.is_file()
    } == {
        "__init__.py",
        "env-profiles/design.json",
        "env-profiles/dev.json",
        "env-profiles/market.json",
        "env-profiles/pm.json",
        "env-profiles/test.json",
        "manifest.toml",
    }

    for package_root in (
        RUNTIME_SUPPORT_ROOT / "__init__.py",
        LAUNCHER_ROOT / "__init__.py",
        CATALOG_ROOT / "__init__.py",
    ):
        tree = ast.parse(package_root.read_text(encoding="utf-8"))
        assert len(tree.body) == 1
        statement = tree.body[0]
        assert isinstance(statement, ast.Expr)
        assert isinstance(statement.value, ast.Constant)
        assert isinstance(statement.value.value, str)
