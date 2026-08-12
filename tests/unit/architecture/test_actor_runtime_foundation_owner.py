"""Stable ownership checks for the direct Foundation Actor Runtime."""

from __future__ import annotations

import ast
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"
LAUNCHER_ROOT = PACKAGE_ROOT / "launcher"
OWNER_ROOT = PACKAGE_ROOT / "foundation" / "actor_runtime"
OWNER_FILES = {
    "__init__.py",
    "capability.py",
    "codex_runtime.py",
    "environment.py",
    "session.py",
    "side_thread.py",
    "side_thread_lifecycle.py",
    "side_thread_registry.py",
}
RETIRED_FILES = {
    "actor_capability.py",
    "codex_runtime.py",
    "actor_session.py",
    "actor_side_thread.py",
    "side_thread_lifecycle.py",
    "side_thread_registry.py",
}
RETIRED_MODULES = {
    f"buddyswitch.launcher.{Path(name).stem}" for name in RETIRED_FILES
}
LIVE_PYTHON_ROOTS = (
    PACKAGE_ROOT,
    REPO_ROOT / "tests",
)
RETIRED_SHELL_IMPORTS = (
    "from buddyswitch.launcher import actor_capability",
    "from buddyswitch.launcher import codex_runtime",
)
CLASSIFIED_COMPONENT_JOIN_PATHS = {
    REPO_ROOT / "tests" / "unit" / "actor" / "test_session.py": {
        "src",
        "buddyswitch",
        "foundation",
        "actor_runtime",
        "session.py",
    },
    REPO_ROOT / "tests" / "unit" / "actor" / "test_side_thread.py": {
        "src",
        "buddyswitch",
        "foundation",
        "actor_runtime",
        "side_thread.py",
    },
    REPO_ROOT / "tests" / "unit" / "actor" / "test_side_thread_registry.py": {
        "src",
        "buddyswitch",
        "foundation",
        "actor_runtime",
        "side_thread_registry.py",
    },
    REPO_ROOT / "tests" / "integration" / "actor" / "test_side_thread_lifecycle.py": {
        "src",
        "buddyswitch",
        "foundation",
        "actor_runtime",
        "side_thread_lifecycle.py",
        "side_thread_registry.py",
    },
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
            imports.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def _resolved_from_base(node: ast.ImportFrom, *, package: str) -> str:
    if node.level == 0:
        return node.module or ""
    package_parts = package.split(".") if package else []
    keep = len(package_parts) - (node.level - 1)
    if keep < 0:
        return ""
    base_parts = package_parts[:keep]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _retired_import_hits(source: str, *, package: str) -> set[str]:
    tree = ast.parse(source)
    candidates: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidates.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _resolved_from_base(node, package=package)
            if base:
                candidates.add(base)
                candidates.update(f"{base}.{alias.name}" for alias in node.names)
    return {
        retired
        for candidate in candidates
        for retired in RETIRED_MODULES
        if (
            candidate == retired or candidate.startswith(f"{retired}.")
        )
    }


def _package_for_path(path: Path) -> str:
    source_root = REPO_ROOT / "src"
    relative = path.relative_to(source_root if path.is_relative_to(source_root) else REPO_ROOT)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
        return ".".join(parts)
    return ".".join(parts[:-1])


def test_actor_runtime_has_one_exact_inert_foundation_owner() -> None:
    assert {
        path.relative_to(OWNER_ROOT).as_posix()
        for path in OWNER_ROOT.rglob("*")
        if path.is_file()
    } == OWNER_FILES

    package_tree = ast.parse((OWNER_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert len(package_tree.body) == 1
    package_docstring = package_tree.body[0]
    assert isinstance(package_docstring, ast.Expr)
    assert isinstance(package_docstring.value, ast.Constant)
    assert isinstance(package_docstring.value.value, str)

    assert not [name for name in sorted(RETIRED_FILES) if (LAUNCHER_ROOT / name).exists()]


def test_launcher_package_root_is_inert_without_reexport_or_fallback() -> None:
    package_tree = ast.parse((LAUNCHER_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert len(package_tree.body) == 1
    package_docstring = package_tree.body[0]
    assert isinstance(package_docstring, ast.Expr)
    assert isinstance(package_docstring.value, ast.Constant)
    assert isinstance(package_docstring.value.value, str)


def test_classified_component_join_paths_use_only_current_actor_runtime_root() -> None:
    for path, required_segments in CLASSIFIED_COMPONENT_JOIN_PATHS.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        string_literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert "launcher" not in string_literals, path
        assert required_segments <= string_literals, path


def test_actor_runtime_dependencies_point_only_to_direct_foundation_owners() -> None:
    forbidden_prefixes = (
        "buddyswitch.application",
        "buddyswitch.launcher",
        "buddyswitch.modules",
        "buddyswitch.runtime_support",
    )
    allowed_prefixes = (
        "buddyswitch.foundation.actor_runtime",
        "buddyswitch.foundation.app_server",
        "buddyswitch.foundation.process_runtime",
    )
    for path in sorted(OWNER_ROOT.glob("*.py")):
        for name in _imports(path):
            assert not name.startswith(forbidden_prefixes), (path, name)
            if name.startswith("buddyswitch."):
                assert name.startswith(allowed_prefixes), (path, name)
            else:
                assert name == "__future__" or name.split(".", 1)[0] in sys.stdlib_module_names, (
                    path,
                    name,
                )


def test_current_consumers_import_direct_actor_runtime_modules() -> None:
    expected_imports = {
        PACKAGE_ROOT / "application" / "daemon_host.py": {
            "buddyswitch.foundation.actor_runtime.session",
        },
        PACKAGE_ROOT / "launcher" / "cli.py": {
            "buddyswitch.foundation.actor_runtime.codex_runtime",
            "buddyswitch.foundation.actor_runtime.session",
        },
        PACKAGE_ROOT / "launcher" / "host_control.py": {
            "buddyswitch.foundation.actor_runtime.capability",
            "buddyswitch.foundation.actor_runtime.codex_runtime",
        },
        PACKAGE_ROOT
        / "modules"
        / "demand"
        / "private"
        / "adapters"
        / "daemon"
        / "demand_triage_handler.py": {
            "buddyswitch.foundation.actor_runtime.side_thread",
            "buddyswitch.foundation.actor_runtime.side_thread_registry",
        },
        PACKAGE_ROOT
        / "modules"
        / "demand"
        / "private"
        / "adapters"
        / "daemon"
        / "demand_triage_runtime.py": {
            "buddyswitch.foundation.actor_runtime.side_thread_registry",
        },
    }
    for path, required in expected_imports.items():
        assert required <= _imports(path), path

    shell = (PACKAGE_ROOT / "launcher" / "shell" / "host_control.sh").read_text(
        encoding="utf-8"
    )
    assert "from buddyswitch.foundation.actor_runtime import capability as actor_capability" in shell
    assert "from buddyswitch.foundation.actor_runtime import codex_runtime" in shell


def test_retired_import_guard_covers_absolute_multiline_dotted_and_launcher_relative_forms() -> None:
    source = """
import buddyswitch.launcher.actor_session
from buddyswitch.launcher import (
    actor_capability,
    codex_runtime,
)
from buddyswitch.launcher.actor_side_thread import start_actor_side_thread
from . import side_thread_lifecycle
from .side_thread_registry import SideThreadRegistryError
"""
    assert _retired_import_hits(source, package="buddyswitch.launcher") == {
        "buddyswitch.launcher.actor_capability",
        "buddyswitch.launcher.actor_session",
        "buddyswitch.launcher.actor_side_thread",
        "buddyswitch.launcher.codex_runtime",
        "buddyswitch.launcher.side_thread_lifecycle",
        "buddyswitch.launcher.side_thread_registry",
    }


def test_retired_actor_runtime_imports_and_source_paths_are_absent() -> None:
    python_paths = sorted(
        path
        for root in LIVE_PYTHON_ROOTS
        for path in root.rglob("*.py")
    )
    violations: dict[str, list[str]] = {}
    for path in python_paths:
        hits = _retired_import_hits(
            path.read_text(encoding="utf-8"),
            package=_package_for_path(path),
        )
        if hits:
            violations[path.relative_to(REPO_ROOT).as_posix()] = sorted(hits)
    assert violations == {}

    for path in PACKAGE_ROOT.rglob("*.sh"):
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in RETIRED_SHELL_IMPORTS), path

    retired_paths = tuple(
        f"launcher/{name}" for name in sorted(RETIRED_FILES)
    )
    for root in LIVE_PYTHON_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".sh"}:
                continue
            source = path.read_text(encoding="utf-8")
            assert not any(token in source for token in retired_paths), path
