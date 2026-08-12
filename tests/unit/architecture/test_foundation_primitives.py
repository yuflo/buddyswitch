"""Static contract for the Foundation primitive owners."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.support.paths import REPO_ROOT


PACKAGE_ROOT = REPO_ROOT / "src" / "buddyswitch"
FOUNDATION_ROOT = PACKAGE_ROOT / "foundation"
OWNER_FILES = {
    "identity.model": FOUNDATION_ROOT / "identity" / "model.py",
    "identity.profiles": FOUNDATION_ROOT / "identity" / "profiles.py",
    "state.runtime": FOUNDATION_ROOT / "state" / "runtime.py",
    "state.actor_private": FOUNDATION_ROOT / "state" / "actor_private.py",
    "process_runtime.process_identity": (
        FOUNDATION_ROOT / "process_runtime" / "process_identity.py"
    ),
    "process_runtime.runtime_lock": (
        FOUNDATION_ROOT / "process_runtime" / "runtime_lock.py"
    ),
}
PACKAGE_ROOTS = (
    FOUNDATION_ROOT / "identity" / "__init__.py",
    FOUNDATION_ROOT / "state" / "__init__.py",
)
RETIRED_PATHS = (
    PACKAGE_ROOT / "env",
    PACKAGE_ROOT / "runtime_kernel" / "process_identity.py",
)
ARCHITECTURE_DOC = REPO_ROOT / "docs" / "arch" / "foundation-primitives-architecture.md"
RETIRED_IMPORTS = (
    "buddyswitch.env",
    "buddyswitch.runtime_kernel.process_identity",
)
RETIRED_SOURCE_MARKERS = (
    "buddyswitch/env",
    "runtime_kernel/process_identity.py",
    "env_legacy_store",
)
SHELL_RETIRED_PROCESS_IMPORT = re.compile(
    r"from\s+buddyswitch\.runtime_kernel\s+import\s+"
    r"(?:\([^)]*\bprocess_identity\b[^)]*\)|[^\n#]*\bprocess_identity\b)",
    re.MULTILINE,
)
DEAD_STATE_SURFACES = {
    "_RUNTIME_ROOT_LISTENERS",
    "WORKSPACE_ROOT",
    "MESSAGES_DIR",
    "CONTENT_ROOT",
    "ACTOR_PRIVATE_DIR",
    "register_runtime_root_listener",
    "shared_state_root_is_bound",
    "instance_tmp_dir",
    "instance_root_from_context",
    "rel",
    "runtime_workspace_agents_file",
    "ensure_runtime_dirs",
    "slugify",
}
DEAD_ACTOR_PRIVATE_SURFACES = {
    "ACTOR_PRIVATE_PRIVACY_MESSAGE",
    "ActorPrivateLogicalNameError",
    "build_actor_private_desc",
    "normalize_logical_name",
    "normalize_logical_prefix",
    "current_identity_private_root",
    "ensure_current_identity_private_root",
    "_resolved_path_within_any_root",
    "_resolved_write_parent_stays_in_root",
    "_updated_at_from_stat",
    "file_summary",
    "state_summary",
    "list_private_file_summaries",
    "read_private_file",
    "write_private_file",
    "import_private_file",
}


def _tree(path: Path) -> ast.Module:
    assert path.is_file(), f"missing Foundation primitive owner: {path}"
    return ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())


def _bound_target_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.List, ast.Tuple)):
        return {
            name
            for element in target.elts
            for name in _bound_target_names(element)
        }
    if isinstance(target, ast.Starred):
        return _bound_target_names(target.value)
    return set()


def _top_level_bound_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in _tree(path).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(_bound_target_names(target))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            names.update(_bound_target_names(node.target))
        elif isinstance(node, ast.Import):
            names.update(
                alias.asname or alias.name.split(".", 1)[0]
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            names.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name != "*"
            )
    return names


def _resolved_import_from_module(
    owner_name: str, node: ast.ImportFrom
) -> str | None:
    if not node.level:
        return node.module
    package_parts = [
        "buddyswitch",
        "foundation",
        *owner_name.split(".")[:-1],
    ]
    parent_count = node.level - 1
    if parent_count > len(package_parts):
        return None
    base_parts = package_parts[: len(package_parts) - parent_count]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _owner_dependencies(owner_name: str, path: Path) -> set[str]:
    dependencies: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "buddyswitch.foundation":
                    dependencies.add("<foundation-root>")
                elif alias.name.startswith("buddyswitch.foundation."):
                    dependencies.add(
                        alias.name.removeprefix("buddyswitch.foundation.")
                    )
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _resolved_import_from_module(owner_name, node)
        if module == "buddyswitch":
            if any(alias.name == "foundation" for alias in node.names):
                dependencies.add("<foundation-root>")
            continue
        if module == "buddyswitch.foundation":
            base = ""
        elif module and module.startswith("buddyswitch.foundation."):
            base = module.removeprefix("buddyswitch.foundation.")
        else:
            continue
        if base in OWNER_FILES:
            dependencies.add(base)
            continue
        for alias in node.names:
            if alias.name == "*":
                dependencies.add(base or "<foundation-root>")
            else:
                dependencies.add(".".join(part for part in (base, alias.name) if part))
    return dependencies


def _static_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left)
        right = _static_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _retired_imports(tree: ast.Module) -> set[str]:
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.update(
                alias.name
                for alias in node.names
                if alias.name == "buddyswitch.env"
                or alias.name.startswith("buddyswitch.env.")
                or alias.name == "buddyswitch.runtime_kernel.process_identity"
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "buddyswitch" and any(
                alias.name == "env" for alias in node.names
            ):
                violations.add("from buddyswitch import env")
            if node.module == "buddyswitch.env" or node.module.startswith(
                "buddyswitch.env."
            ):
                violations.add(node.module)
            if node.module == "buddyswitch.runtime_kernel" and any(
                alias.name == "process_identity" for alias in node.names
            ):
                violations.add("from buddyswitch.runtime_kernel import process_identity")
            if node.module == "buddyswitch.runtime_kernel.process_identity":
                violations.add(node.module)
    return violations


def _retired_static_strings(tree: ast.Module) -> set[str]:
    violations: set[str] = set()
    for node in ast.walk(tree):
        value = _static_string(node)
        if value is None:
            continue
        violations.update(
            marker
            for marker in (*RETIRED_IMPORTS, *RETIRED_SOURCE_MARKERS)
            if marker in value
        )
    return violations


def test_foundation_primitive_cutover_has_one_inert_owner_topology() -> None:
    assert [path.as_posix() for path in RETIRED_PATHS if path.exists()] == []
    assert [name for name, path in OWNER_FILES.items() if not path.is_file()] == []
    assert [path.as_posix() for path in PACKAGE_ROOTS if not path.is_file()] == []
    assert ARCHITECTURE_DOC.is_file()

    for path in PACKAGE_ROOTS:
        tree = _tree(path)
        assert all(
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            for node in tree.body
        )


def test_foundation_primitive_dependencies_point_only_between_direct_owners() -> None:
    graph = {
        name: _owner_dependencies(name, path) for name, path in OWNER_FILES.items()
    }
    assert graph == {
        "identity.model": set(),
        "identity.profiles": {"identity.model", "state.runtime"},
        "state.runtime": set(),
        "state.actor_private": set(),
        "process_runtime.process_identity": set(),
        "process_runtime.runtime_lock": set(),
    }

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        assert name not in visiting, f"Foundation primitive dependency cycle at {name}"
        if name in visited:
            return
        visiting.add(name)
        for dependency in graph[name]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for owner in graph:
        visit(owner)


def test_foundation_primitive_owners_do_not_depend_on_product_or_host_layers() -> None:
    forbidden_prefixes = (
        "buddyswitch.application",
        "buddyswitch.launcher",
        "buddyswitch.modules",
        "buddyswitch.foundation.runtime_broker",
        "buddyswitch.runtime_support",
    )
    violations: list[tuple[str, str]] = []
    for name, path in OWNER_FILES.items():
        for node in ast.walk(_tree(path)):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            violations.extend(
                (name, module)
                for module in imported
                if module.startswith(forbidden_prefixes)
            )
    assert violations == []


def test_production_sources_name_only_current_foundation_primitive_owners() -> None:
    violations: list[tuple[str, str]] = []
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".sh"}:
            continue
        document = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        raw_markers = {
            marker
            for marker in (*RETIRED_IMPORTS, *RETIRED_SOURCE_MARKERS)
            if marker in document
        }
        if path.suffix == ".py":
            tree = _tree(path)
            raw_markers.update(_retired_imports(tree))
            raw_markers.update(_retired_static_strings(tree))
        else:
            if SHELL_RETIRED_PROCESS_IMPORT.search(document):
                raw_markers.add(
                    "from buddyswitch.runtime_kernel import process_identity"
                )
        violations.extend((relative, marker) for marker in sorted(raw_markers))
    assert violations == []


def test_foundation_state_exposes_only_live_primitive_surfaces() -> None:
    assert _top_level_bound_names(OWNER_FILES["state.runtime"]).isdisjoint(
        DEAD_STATE_SURFACES
    )
    assert _top_level_bound_names(OWNER_FILES["state.actor_private"]).isdisjoint(
        DEAD_ACTOR_PRIVATE_SURFACES
    )


def test_retired_pid_liveness_helpers_are_absent_from_lifecycle_owners() -> None:
    for path in (
        PACKAGE_ROOT / "foundation" / "daemon" / "central_process.py",
        PACKAGE_ROOT / "foundation" / "runtime_broker" / "lifecycle.py",
    ):
        assert "pid_is_live" not in _top_level_bound_names(path), path.relative_to(
            REPO_ROOT
        )
