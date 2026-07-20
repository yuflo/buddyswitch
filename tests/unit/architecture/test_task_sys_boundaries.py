"""Machine-enforced ownership boundaries for Task Sys."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.support.paths import REPO_ROOT


DOMAIN = Path("scripts/env/domain/task_sys.py")
READ_MODEL = Path("scripts/env/domain/task_read.py")
TOOL_ROOT = Path("scripts/env/tools/task_sys")
RUNTIME = Path("tools/launcher/task_sys_runtime.py")
INGRESS = Path("tools/launcher/task_sys_ingress.py")
ARCH = Path("docs/arch/task-sys-architecture.md")


def _imports(relative: Path) -> set[str]:
    path = REPO_ROOT / relative
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                modules.add(module)
            modules.update(
                f"{module}.{alias.name}" if module else alias.name
                for alias in node.names
            )
    return modules


def _task_implementation_files() -> tuple[Path, ...]:
    return (
        DOMAIN,
        READ_MODEL,
        RUNTIME,
        INGRESS,
        *tuple(path.relative_to(REPO_ROOT) for path in sorted((REPO_ROOT / TOOL_ROOT).glob("*.py"))),
    )


def test_task_sys_has_no_demand_implementation_dependency() -> None:
    for relative in _task_implementation_files():
        imports = _imports(relative)
        assert not [name for name in imports if "demand_sys" in name or "repos.demands" in name], relative

        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "demand_sys." not in source, relative
        assert "transact_actor_state" not in source, relative


def test_task_sys_has_one_actor_create_action_and_one_creation_owner() -> None:
    tool_source = (REPO_ROOT / TOOL_ROOT / "tool.py").read_text(encoding="utf-8")
    domain_source = (REPO_ROOT / DOMAIN).read_text(encoding="utf-8")

    assert tool_source.count('name="create"') == 1
    assert 'name="start"' not in tool_source
    assert 'name="begin"' not in tool_source
    assert domain_source.count("def _create_task(") == 1
    assert domain_source.count("_create_task(") == 3
    assert "buddyswitch/local/locks/task-sys" not in domain_source
    assert not (REPO_ROOT / "scripts/env/domain/tasks.py").exists()


def test_current_task_architecture_names_exact_owners_and_forward_only_boundary() -> None:
    text = (REPO_ROOT / ARCH).read_text(encoding="utf-8")

    for token in (
        "one actor-scoped active Task",
        "in_progress.side_processing",
        "in_progress.awaiting_parent",
        "in_progress.parent_processing",
        "task_sys.create",
        "task_sys.completion_frame",
        "opaque DemandRef",
        "Actor + installed task-management skill",
        "Track comment ingress",
    ):
        assert token in text
    for token in ("task_sys.start", "task_sys.begin", "automatic Demand completion", "compatibility"):
        assert token not in text
