from __future__ import annotations

import ast
from pathlib import Path
import unittest

from tests.support.paths import REPO_ROOT


ROOT = REPO_ROOT
PACKAGE_ROOT = ROOT / "src" / "buddyswitch"
BROWSER_ROOT = PACKAGE_ROOT / "foundation" / "browser_runtime"
BROWSER_PACKAGE = "buddyswitch.foundation.browser_runtime"
CURRENT_OWNER_ASSET = BROWSER_ROOT / "assets" / "chrome-devtools-mcp-1.1.1-tools.json"
HOST_PATHS = (
    PACKAGE_ROOT / "application" / "entrypoints" / "browser_runtime.py",
    PACKAGE_ROOT / "application" / "entrypoints" / "browser_cockpit_proxy.py",
    PACKAGE_ROOT / "foundation" / "runtime_broker" / "dispatcher.py",
    PACKAGE_ROOT / "launcher" / "instance_daemon.py",
)
RETIRED_PATHS = (
    PACKAGE_ROOT / "env" / "browser_ttl_config.py",
    PACKAGE_ROOT / "env" / "cdp_target.py",
    PACKAGE_ROOT / "env" / "cdp_browser_lifecycle.py",
    PACKAGE_ROOT / "env" / ("cdp_browser_" + "session.py"),
    PACKAGE_ROOT / "env" / ("cdp_background_" + "page.py"),
    PACKAGE_ROOT / "launcher" / "browser_runtime_manager.py",
    PACKAGE_ROOT / "launcher" / "browser_page_expired_handler.py",
    PACKAGE_ROOT / "launcher" / "browser_release_handler.py",
    PACKAGE_ROOT / "launcher" / "browser_inbound.py",
    PACKAGE_ROOT / "launcher" / "chrome_devtools_cockpit_proxy.py",
    PACKAGE_ROOT / "launcher" / "assets" / "chrome-devtools-mcp-1.1.1-tools.json",
)
RETIRED_MODULES = {
    "buddyswitch.env.browser_ttl_config",
    "buddyswitch.env.cdp_target",
    "buddyswitch.env.cdp_browser_lifecycle",
    "buddyswitch.launcher.browser_runtime_manager",
    "buddyswitch.launcher.browser_page_expired_handler",
    "buddyswitch.launcher.browser_release_handler",
    "buddyswitch.launcher.browser_inbound",
    "buddyswitch.launcher.chrome_devtools_cockpit_proxy",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _production_python_files(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in root.rglob("*.py")
            if path.is_file()
            and not any(part.startswith(".") or part in {"__pycache__", "tests"} for part in path.relative_to(root).parts)
            and not path.name.startswith("test_")
            and not path.name.endswith("_test.py")
        )
    )


def _browser_modules() -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in _production_python_files(BROWSER_ROOT):
        relative_parts = path.relative_to(BROWSER_ROOT).with_suffix("").parts
        if relative_parts == ("__init__",):
            continue
        module_parts = relative_parts[:-1] if path.name == "__init__.py" else relative_parts
        modules[".".join(module_parts)] = path
    return modules


def _source_package(path: Path) -> str:
    package_parts = path.relative_to(PACKAGE_ROOT).with_suffix("").parts[:-1]
    return ".".join(("buddyswitch", *package_parts))


def _resolved_from_module(node: ast.ImportFrom, path: Path) -> str:
    if node.level == 0:
        return node.module or ""
    package_parts = _source_package(path).split(".")
    parent_count = node.level - 1
    if parent_count > len(package_parts):
        return ""
    resolved_parts = package_parts[: len(package_parts) - parent_count]
    if node.module:
        resolved_parts.extend(node.module.split("."))
    return ".".join(resolved_parts)


def _dotted_name(node: ast.expr) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    return ".".join((current.id, *reversed(parts)))


def _browser_import_contract(
    path: Path,
    modules: dict[str, Path],
) -> tuple[set[str], list[tuple[int, str]]]:
    qualified_modules = {
        f"{BROWSER_PACKAGE}.{module_name}": module_name for module_name in modules
    }
    declared: set[str] = set()
    module_aliases: set[str] = set()
    violations: list[tuple[int, str]] = []
    tree = _tree(path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == BROWSER_PACKAGE:
                    violations.append((node.lineno, "package-root facade import"))
                    continue
                if not alias.name.startswith(f"{BROWSER_PACKAGE}."):
                    continue
                target = qualified_modules.get(alias.name)
                if target is None:
                    violations.append((node.lineno, f"unknown Browser module: {alias.name}"))
                    continue
                if any(part.startswith("_") for part in target.split(".")):
                    violations.append((node.lineno, f"private Browser module: {alias.name}"))
                declared.add(target)
                module_aliases.add(alias.asname or alias.name)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue
        from_module = _resolved_from_module(node, path)
        if from_module != BROWSER_PACKAGE and not from_module.startswith(
            f"{BROWSER_PACKAGE}."
        ):
            continue
        from_target = qualified_modules.get(from_module)
        for alias in node.names:
            if alias.name == "*":
                violations.append((node.lineno, f"star import from {from_module}"))
                continue
            imported_module = qualified_modules.get(f"{from_module}.{alias.name}")
            if imported_module is not None:
                if any(part.startswith("_") for part in imported_module.split(".")):
                    violations.append(
                        (node.lineno, f"private Browser module: {from_module}.{alias.name}")
                    )
                declared.add(imported_module)
                module_aliases.add(alias.asname or alias.name)
            elif from_target is not None:
                declared.add(from_target)
                if alias.name.startswith("_"):
                    violations.append(
                        (node.lineno, f"private Browser import: {from_module}.{alias.name}")
                    )
            else:
                violations.append(
                    (node.lineno, f"package facade or unknown Browser import: {from_module}.{alias.name}")
                )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not node.attr.startswith("_"):
            continue
        base_name = _dotted_name(node.value)
        if base_name in module_aliases:
            violations.append(
                (node.lineno, f"private Browser operation: {base_name}.{node.attr}")
            )
    return declared, violations


def _browser_dependency_graph(modules: dict[str, Path]) -> dict[str, set[str]]:
    return {
        module_name: _browser_import_contract(path, modules)[0]
        for module_name, path in modules.items()
    }


def _find_dependency_cycle(graph: dict[str, set[str]]) -> tuple[str, ...] | None:
    visited: set[str] = set()
    active: list[str] = []
    positions: dict[str, int] = {}

    def visit(module_name: str) -> tuple[str, ...] | None:
        if module_name in positions:
            return (*active[positions[module_name] :], module_name)
        if module_name in visited:
            return None
        positions[module_name] = len(active)
        active.append(module_name)
        for dependency in sorted(graph[module_name]):
            cycle = visit(dependency)
            if cycle is not None:
                return cycle
        active.pop()
        positions.pop(module_name)
        visited.add(module_name)
        return None

    for module_name in sorted(graph):
        cycle = visit(module_name)
        if cycle is not None:
            return cycle
    return None


def _imported_modules(path: Path) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            from_module = _resolved_from_module(node, path)
            if from_module:
                imported.add(from_module)
                imported.update(f"{from_module}.{alias.name}" for alias in node.names)
    return imported


class TestCdpArchitecture(unittest.TestCase):
    def test_browser_runtime_has_one_current_owner_and_no_retired_paths(self) -> None:
        self.assertTrue(BROWSER_ROOT.is_dir())
        self.assertTrue(CURRENT_OWNER_ASSET.is_file())
        self.assertEqual(
            [path.relative_to(ROOT).as_posix() for path in RETIRED_PATHS if path.exists()],
            [],
        )

    def test_browser_package_root_is_inert_and_internal_graph_is_acyclic(self) -> None:
        body = list(_tree(BROWSER_ROOT / "__init__.py").body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
        body = [
            node
            for node in body
            if not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
        ]
        self.assertEqual(body, [], "Browser package root must remain inert")

        modules = _browser_modules()
        self.assertTrue(modules, "Browser Runtime must have production owner modules")
        graph = _browser_dependency_graph(modules)
        self.assertIsNone(_find_dependency_cycle(graph), graph)

    def test_hosts_use_public_browser_modules_and_retired_imports_are_absent(self) -> None:
        modules = _browser_modules()
        for path in HOST_PATHS:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertTrue(path.is_file())
                declared, violations = _browser_import_contract(path, modules)
                self.assertTrue(declared, "host must depend on a current Browser owner module")
                self.assertEqual(violations, [])

        retired_imports = sorted(
            (path.relative_to(ROOT).as_posix(), imported)
            for path in _production_python_files(PACKAGE_ROOT)
            for imported in _imported_modules(path)
            if imported in RETIRED_MODULES
            or any(imported.startswith(f"{retired}.") for retired in RETIRED_MODULES)
        )
        self.assertEqual(retired_imports, [])

    def test_browser_modules_use_public_operations(self) -> None:
        modules = _browser_modules()
        violations = sorted(
            (module_name, lineno, message)
            for module_name, path in modules.items()
            for lineno, message in _browser_import_contract(path, modules)[1]
        )
        self.assertEqual(violations, [])

        operation_definitions = [
            (module_name, node.name, node.lineno)
            for module_name, path in modules.items()
            for node in ast.walk(_tree(path))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"read_page_idle_state", "_read_page_idle_state"}
        ]
        public_definitions = [
            definition
            for definition in operation_definitions
            if definition[1] == "read_page_idle_state"
        ]
        self.assertEqual(len(public_definitions), 1, public_definitions)
        self.assertEqual(
            [definition for definition in operation_definitions if definition[1] == "_read_page_idle_state"],
            [],
        )

    def test_retired_actor_page_helpers_and_state_are_absent(self) -> None:
        forbidden = (
            "def create_background_page_" + "target",
            "def close_page_" + "target",
            "target_idle_expiry_after_" + "due_at",
            "forget_page_idle_" + "target",
            "current_" + "target_id",
            "page_id_to_" + "target_id",
        )
        sources = {
            module_name: path.read_text(encoding="utf-8")
            for module_name, path in _browser_modules().items()
        }
        for module_name, source in sources.items():
            for token in forbidden:
                with self.subTest(module=module_name, token=token):
                    self.assertNotIn(token, source)

        idle_owners = [
            module_name
            for module_name, path in _browser_modules().items()
            if any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "read_page_idle_state"
                for node in ast.walk(_tree(path))
            )
        ]
        self.assertEqual(len(idle_owners), 1, idle_owners)
        self.assertNotIn("Target." + "closeTarget", sources[idle_owners[0]])
