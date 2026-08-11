"""Stable architecture and replacement proof for the Foundation Runtime Broker."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.support.paths import REPO_ROOT


PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"
BROKER_ROOT = PACKAGE_ROOT / "foundation" / "runtime_broker"
FRAMING_OWNER = PACKAGE_ROOT / "foundation" / "process_runtime" / "json_framing.py"
ARCHITECTURE_DOC = REPO_ROOT / "docs" / "arch" / "runtime-broker-architecture.md"
BROKER_MODULES = {
    "broker.py",
    "client.py",
    "coordinator.py",
    "dispatcher.py",
    "lifecycle.py",
    "protocol.py",
    "server.py",
}
DAEMON_FRAMING_CONSUMERS = (
    PACKAGE_ROOT / "foundation" / "daemon" / "client.py",
    PACKAGE_ROOT / "foundation" / "daemon" / "central_service.py",
    PACKAGE_ROOT / "foundation" / "daemon" / "mailbox.py",
)
BROKER_CLIENT_CONSUMERS = (
    PACKAGE_ROOT / "foundation" / "browser_runtime" / "cockpit_proxy.py",
    PACKAGE_ROOT / "foundation" / "tool_runtime" / "client.py",
    PACKAGE_ROOT / "foundation" / "tool_runtime" / "mcp_server.py",
    PACKAGE_ROOT / "modules" / "evidence" / "entrypoints" / "browser_evidence.py",
)


def _tree(path: Path) -> ast.Module:
    assert path.is_file(), f"missing owner: {path.relative_to(REPO_ROOT)}"
    return ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())


def _buddyswitch_imports(path: Path) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name
                for alias in node.names
                if alias.name == "buddyswitch" or alias.name.startswith("buddyswitch.")
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "buddyswitch" or node.module.startswith("buddyswitch."):
                imports.update(
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
    return imports


def test_runtime_broker_cutover_has_one_direct_inert_owner() -> None:
    assert not (PACKAGE_ROOT / "runtime_kernel").exists()
    assert BROKER_ROOT.is_dir()
    assert {
        path.name
        for path in BROKER_ROOT.glob("*.py")
        if path.name != "__init__.py"
    } == BROKER_MODULES

    package_tree = _tree(BROKER_ROOT / "__init__.py")
    assert all(
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        for node in package_tree.body
    )

    assert FRAMING_OWNER.is_file()
    assert ARCHITECTURE_DOC.is_file()


def test_json_framing_is_direct_shared_process_runtime_ownership() -> None:
    assert _buddyswitch_imports(FRAMING_OWNER) == set()
    assert "broker" not in FRAMING_OWNER.read_text(encoding="utf-8").lower()

    protocol_names = {
        node.name
        for node in _tree(BROKER_ROOT / "protocol.py").body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    assert {"read_message", "write_message", "JsonFramingError"}.isdisjoint(
        protocol_names
    )

    for path in (
        BROKER_ROOT / "client.py",
        BROKER_ROOT / "lifecycle.py",
        BROKER_ROOT / "server.py",
        *DAEMON_FRAMING_CONSUMERS,
    ):
        imports = _buddyswitch_imports(path)
        assert "buddyswitch.foundation.process_runtime.json_framing" in imports

    for path in DAEMON_FRAMING_CONSUMERS:
        assert not any(
            imported.startswith("buddyswitch.foundation.runtime_broker")
            for imported in _buddyswitch_imports(path)
        )


def test_runtime_broker_dependencies_are_product_neutral_and_acyclic() -> None:
    forbidden_prefixes = (
        "buddyswitch.application",
        "buddyswitch.launcher",
        "buddyswitch.modules",
        "buddyswitch.skills",
    )
    dependency_graph: dict[str, set[str]] = {}
    for module_name in BROKER_MODULES:
        path = BROKER_ROOT / module_name
        imports = _buddyswitch_imports(path)
        assert not [
            imported
            for imported in imports
            if imported.startswith(forbidden_prefixes)
        ]
        dependency_graph[module_name.removesuffix(".py")] = {
            imported.removeprefix("buddyswitch.foundation.runtime_broker.")
            for imported in imports
            if imported.startswith("buddyswitch.foundation.runtime_broker.")
            and imported.removeprefix("buddyswitch.foundation.runtime_broker.")
            in {name.removesuffix(".py") for name in BROKER_MODULES}
        }

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module_name: str) -> None:
        assert module_name not in visiting, f"Runtime Broker dependency cycle at {module_name}"
        if module_name in visited:
            return
        visiting.add(module_name)
        for dependency in dependency_graph[module_name]:
            visit(dependency)
        visiting.remove(module_name)
        visited.add(module_name)

    for module_name in dependency_graph:
        visit(module_name)


def test_current_consumers_and_guidance_name_only_the_final_broker_owner() -> None:
    application_imports = _buddyswitch_imports(
        PACKAGE_ROOT / "application" / "entrypoints" / "runtime_broker.py"
    )
    assert "buddyswitch.foundation.runtime_broker.broker" in application_imports

    for path in BROKER_CLIENT_CONSUMERS:
        assert "buddyswitch.foundation.runtime_broker.client.RuntimeBrokerError" in _buddyswitch_imports(path)

    retired_import = ".".join(("buddyswitch", "runtime_kernel"))
    retired_source = "/".join(("src", "buddyswitch", "runtime_kernel"))
    current_surfaces = (
        REPO_ROOT / "README.md",
        *sorted((REPO_ROOT / "docs" / "arch").glob("*.md")),
        *sorted(PACKAGE_ROOT.rglob("*.py")),
    )
    violations = [
        (path.relative_to(REPO_ROOT).as_posix(), token)
        for path in current_surfaces
        for token in (retired_import, retired_source)
        if token in path.read_text(encoding="utf-8")
    ]
    assert violations == []
