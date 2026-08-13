"""Stable ownership checks for the direct Foundation Web and CLI runtimes."""

from __future__ import annotations

import ast
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = ROOT / "src" / "buddyswitch"
WEB_ROOT = PACKAGE_ROOT / "foundation" / "web_runtime"
CLI_ROOT = PACKAGE_ROOT / "foundation" / "cli_runtime"
RETIRED_PATHS = (
    PACKAGE_ROOT / "launcher" / "web_management.py",
    PACKAGE_ROOT / "launcher" / "web_contracts.py",
    PACKAGE_ROOT / "launcher" / "cli_contract.py",
    PACKAGE_ROOT / "launcher" / "assets" / "web-management",
)
CLI_CONSUMERS = (
    PACKAGE_ROOT / "application" / "build.py",
    PACKAGE_ROOT / "foundation" / "composition" / "__init__.py",
    PACKAGE_ROOT / "foundation" / "cli_runtime" / "runtime.py",
    PACKAGE_ROOT / "modules" / "demand" / "private" / "adapters" / "cli.py",
    PACKAGE_ROOT / "modules" / "task" / "private" / "adapters" / "cli.py",
    PACKAGE_ROOT / "modules" / "track" / "private" / "adapters" / "cli.py",
    WEB_ROOT / "runtime.py",
)
WEB_CONTRACT_CONSUMERS = (
    PACKAGE_ROOT / "application" / "build.py",
    PACKAGE_ROOT / "foundation" / "composition" / "__init__.py",
    PACKAGE_ROOT
    / "modules"
    / "communication"
    / "private"
    / "adapters"
    / "web"
    / "registration.py",
    PACKAGE_ROOT / "modules" / "task" / "private" / "adapters" / "web.py",
    PACKAGE_ROOT / "modules" / "track" / "private" / "adapters" / "web.py",
    WEB_ROOT / "runtime.py",
)
FORBIDDEN_EXECUTABLE_ROOTS = (
    "buddyswitch.application",
    "buddyswitch.launcher",
    "buddyswitch.modules",
    "buddyswitch.runtime_support",
    "buddyswitch/application",
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
            imports.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def _assert_inert_package(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert len(tree.body) == 1
    statement = tree.body[0]
    assert isinstance(statement, ast.Expr)
    assert isinstance(statement.value, ast.Constant)
    assert isinstance(statement.value.value, str)


def _embedded_upward_roots(source: str) -> list[str]:
    return [root for root in FORBIDDEN_EXECUTABLE_ROOTS if root in source]


def test_web_and_cli_runtimes_have_one_direct_foundation_owner() -> None:
    actual_web_files = {
        path.relative_to(WEB_ROOT).as_posix()
        for path in WEB_ROOT.rglob("*")
        if path.is_file()
    }
    assert actual_web_files == {
        "__init__.py",
        "contracts.py",
        "runtime.py",
        "assets/web-management/app.js",
        "assets/web-management/index.html",
        "assets/web-management/markdown-renderer.js",
        "assets/web-management/styles.css",
        "assets/web-management/vendor/PROVENANCE.md",
        "assets/web-management/vendor/dompurify/LICENSE",
        "assets/web-management/vendor/dompurify/LICENSE-MPL",
        "assets/web-management/vendor/dompurify/purify.min.js",
        "assets/web-management/vendor/highlightjs/LICENSE",
        "assets/web-management/vendor/highlightjs/github.min.css",
        "assets/web-management/vendor/highlightjs/highlight.min.js",
        "assets/web-management/vendor/markdown-it/LICENSE",
        "assets/web-management/vendor/markdown-it/markdown-it.min.js",
    }
    actual_cli_files = {
        path.relative_to(CLI_ROOT).as_posix()
        for path in CLI_ROOT.rglob("*")
        if path.is_file()
    }
    assert actual_cli_files == {
        "__init__.py",
        "config.py",
        "contracts.py",
        "diagnostics.py",
        "runtime.py",
        "shell/browser_cockpit.sh",
        "shell/cleanup.sh",
        "shell/env.sh",
    }
    _assert_inert_package(WEB_ROOT / "__init__.py")
    _assert_inert_package(CLI_ROOT / "__init__.py")
    _assert_inert_package(PACKAGE_ROOT / "launcher" / "__init__.py")
    assert all(not path.exists() for path in RETIRED_PATHS)


def test_foundation_web_and_cli_runtimes_have_no_upward_dependencies() -> None:
    forbidden_roots = (
        "buddyswitch.application",
        "buddyswitch.launcher",
        "buddyswitch.modules",
        "buddyswitch.runtime_support",
    )
    for path in (*WEB_ROOT.glob("*.py"), *CLI_ROOT.glob("*.py")):
        for imported in _imports(path):
            assert not any(
                imported == root or imported.startswith(f"{root}.")
                for root in forbidden_roots
            ), f"{path.relative_to(ROOT)} imports {imported}"


def test_foundation_web_and_cli_runtimes_embed_no_upward_executable_roots() -> None:
    owner_files = tuple(
        path
        for root in (WEB_ROOT, CLI_ROOT)
        for path in root.rglob("*")
        if path.is_file()
    )
    for path in owner_files:
        source = path.read_text(encoding="utf-8")
        embedded = _embedded_upward_roots(source)
        assert embedded == [], f"{path.relative_to(ROOT)} embeds {embedded}"


def test_embedded_root_guard_recognizes_dotted_and_path_representations() -> None:
    assert _embedded_upward_roots("-m buddyswitch.application.entrypoints.cli") == [
        "buddyswitch.application"
    ]
    assert _embedded_upward_roots("src/buddyswitch/application/entrypoints/cli.py") == [
        "buddyswitch/application"
    ]


def test_current_consumers_import_the_foundation_contract_owners() -> None:
    for consumer in CLI_CONSUMERS:
        assert "buddyswitch.foundation.cli_runtime.contracts" in _imports(consumer), consumer
    for consumer in WEB_CONTRACT_CONSUMERS:
        assert "buddyswitch.foundation.web_runtime.contracts" in _imports(consumer), consumer

    runtime_consumers = (
        PACKAGE_ROOT / "application" / "build.py",
        PACKAGE_ROOT / "application" / "entrypoints" / "web.py",
    )
    for consumer in runtime_consumers:
        assert "buddyswitch.foundation.web_runtime.runtime" in _imports(consumer), consumer

    retired_modules = {
        "buddyswitch.launcher.web_management",
        "buddyswitch.launcher.web_contracts",
        "buddyswitch.launcher.cli_contract",
    }
    for path in PACKAGE_ROOT.rglob("*.py"):
        assert _imports(path).isdisjoint(retired_modules), path


def test_web_assets_have_owner_local_package_data() -> None:
    package_data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"
    ]["setuptools"]["package-data"]
    assert package_data["buddyswitch.foundation.web_runtime"] == [
        "assets/**/*.md",
        "assets/**/*.html",
        "assets/**/*.css",
        "assets/**/*.js",
        "assets/**/LICENSE*",
    ]
    assert package_data["buddyswitch.launcher"] == [
        "assets/docs/*.md",
    ]
