"""Machine-enforced ownership boundaries for the native-Goal Task model."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.support.paths import REPO_ROOT

DOMAIN = Path("scripts/env/domain/task_sys.py")
READ_MODEL = Path("scripts/env/domain/task_read.py")
TOOL = Path("scripts/env/tools/task_sys/tool.py")
TOOL_IMPL = Path("scripts/env/tools/task_sys/_impl.py")
PROTOCOL = Path("scripts/env/tool_runtime/task_goal_runtime_protocol.py")
CLIENT = Path("scripts/env/tool_runtime/task_goal_runtime_client.py")


def _source(relative: Path) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _imports(relative: Path) -> set[str]:
    tree = ast.parse(_source(relative), filename=str(relative))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                modules.add(module)
            modules.update(f"{module}.{alias.name}" if module else alias.name for alias in node.names)
    return modules


def test_task_owner_does_not_implement_or_import_demand_or_daemon_behavior() -> None:
    imports = _imports(DOMAIN)
    source = _source(DOMAIN)

    assert not [name for name in imports if "demand_sys" in name or "daemon" in name or "app_server" in name]
    assert "resolve_demand_ref" not in source
    assert "request_mailbox" not in source
    assert "goal_set" not in source
    assert "goal_get" not in source


def test_actor_tool_resolves_demand_at_boundary_and_exposes_exact_actions() -> None:
    tool_source = _source(TOOL)
    impl_source = _source(TOOL_IMPL)

    for action in ("list", "get", "create", "cancel"):
        assert tool_source.count(f'name="{action}"') == 1
    for retired in ("close", "need_parent"):
        assert f'name="{retired}"' not in tool_source
        assert f"def {retired}(" not in impl_source
    assert "context.rules.demand_sys.resolve_demand_ref" in impl_source
    assert "task_goal_runtime" in impl_source
    assert "execution_brief" not in tool_source
    assert "selection_reason" in tool_source


def test_task_record_has_no_retired_execution_engine_vocabulary() -> None:
    source = _source(DOMAIN)
    for retired in (
        "SIDE_PROCESSING",
        "AWAITING_PARENT",
        "PARENT_PROCESSING",
        "record_task_close",
        "record_side_need_parent",
        "runtime_instruction",
        "side_frame",
        "parent_frame",
        "recoverable",
        "execution_brief",
    ):
        assert retired not in source
    for current in ("ACTIVE = \"active\"", "bind_goal", "record_goal_complete", "record_task_cancel"):
        assert current in source


def test_runtime_client_has_one_reconciliation_command_and_no_business_rules() -> None:
    protocol = _source(PROTOCOL)
    client = _source(CLIENT)

    assert 'RECONCILE_TASK = "task_goal.reconcile_task"' in protocol
    assert "COMMAND_KEYS = frozenset({RECONCILE_TASK})" in protocol
    assert "request_mailbox" in client
    for forbidden in ("demand_sys", "bind_goal", "record_goal_complete", "selection_reason"):
        assert forbidden not in client


def test_read_projection_has_only_active_and_terminal_groups() -> None:
    source = _source(READ_MODEL)

    assert '"active_tasks"' in source
    assert '"terminal_tasks"' in source
    assert "recoverable" not in source
    assert "execution" not in source
