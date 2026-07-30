"""Machine-enforced ownership boundaries for the native-Goal Task model."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from tests.support.paths import REPO_ROOT

DOMAIN = Path("src/buddyswitch/env/domain/task_sys.py")
READ_MODEL = Path("src/buddyswitch/env/domain/task_read.py")
TOOL = Path("src/buddyswitch/env/tools/task_sys/tool.py")
TOOL_IMPL = Path("src/buddyswitch/env/tools/task_sys/_impl.py")
PROTOCOL = Path("src/buddyswitch/env/tool_runtime/task_goal_runtime_protocol.py")
CLIENT = Path("src/buddyswitch/env/tool_runtime/task_goal_runtime_client.py")
HANDLER = Path("src/buddyswitch/launcher/task_goal_handler.py")
TASK_ROOT = Path("src/buddyswitch/modules/task")
FINAL_DOMAIN = TASK_ROOT / "private/domain/task_sys.py"
FINAL_READ_MODEL = TASK_ROOT / "private/read_model.py"
FINAL_TOOL_ROOT = TASK_ROOT / "private/adapters/tool"
FINAL_GOAL_ROOT = TASK_ROOT / "private/adapters/goal"
FINAL_UNIT_TEST_ROOT = TASK_ROOT / "tests/unit"
FINAL_INTEGRATION_TEST_ROOT = TASK_ROOT / "tests/integration"
TASK_PUBLIC = TASK_ROOT / "public/operations.py"
TASK_MODULE = TASK_ROOT / "module.py"
APPLICATION_COMPOSITION = Path("src/buddyswitch/application/composition.py")
APPLICATION_BUILD = Path("src/buddyswitch/application/build.py")
MODULE_ASSEMBLY = Path("src/buddyswitch/foundation/composition/__init__.py")
WEB_CONTRACTS = Path("src/buddyswitch/launcher/web_contracts.py")
GENERIC_HOSTS = (
    Path("src/buddyswitch/env/tool_runtime/context.py"),
    Path("src/buddyswitch/env/tool_runtime/registry.py"),
    Path("src/buddyswitch/launcher/cli.py"),
    Path("src/buddyswitch/launcher/instance_daemon.py"),
    Path("src/buddyswitch/launcher/web_management.py"),
)
RETIRED_OWNER_PATHS = (
    DOMAIN,
    READ_MODEL,
    Path("src/buddyswitch/env/tools/task_sys"),
    HANDLER,
    CLIENT,
    PROTOCOL,
    Path("tests/integration/task_sys"),
    Path("tests/integration/goal_mode/test_task_goal_reconciliation.py"),
)


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


def test_task_has_one_final_physical_owner_and_no_retired_live_path() -> None:
    for relative in (
        FINAL_DOMAIN,
        FINAL_READ_MODEL,
        FINAL_TOOL_ROOT / "tool.py",
        FINAL_TOOL_ROOT / "_impl.py",
        FINAL_GOAL_ROOT / "handler.py",
        FINAL_GOAL_ROOT / "client.py",
        FINAL_GOAL_ROOT / "protocol.py",
        FINAL_UNIT_TEST_ROOT,
        FINAL_INTEGRATION_TEST_ROOT,
        TASK_PUBLIC,
        TASK_MODULE,
    ):
        assert (REPO_ROOT / relative).exists(), relative

    for retired in RETIRED_OWNER_PATHS:
        assert not (REPO_ROOT / retired).exists(), retired


def test_application_selects_task_once_and_declares_exact_daemon_order() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.application.composition import COMPONENTS

    assert [component.name for component in COMPONENTS] == ["demand", "task"]
    application = build_application()
    assert [registration.name for registration in application.daemon_handlers] == [
        "demand_triage",
        "task_goal",
        "demand_orchestration",
    ]


def test_task_dependency_graph_is_acyclic_and_composition_owns_concrete_wires() -> None:
    for relative in (
        FINAL_DOMAIN,
        FINAL_READ_MODEL,
        FINAL_TOOL_ROOT / "_impl.py",
        FINAL_GOAL_ROOT / "handler.py",
        TASK_PUBLIC,
        TASK_MODULE,
    ):
        assert (REPO_ROOT / relative).is_file(), relative

    for path in (REPO_ROOT / TASK_ROOT).rglob("*.py"):
        relative = path.relative_to(REPO_ROOT)
        imports = _imports(relative)
        assert not [
            name
            for name in imports
            if name.startswith("buddyswitch.modules.demand")
        ], relative

    demand_private = REPO_ROOT / "src/buddyswitch/modules/demand/private"
    for path in demand_private.rglob("*.py"):
        relative = path.relative_to(REPO_ROOT)
        task_imports = [
            name for name in _imports(relative) if "task" in name
        ]
        assert all(
            name == "buddyswitch.modules.task.public"
            or name.startswith("buddyswitch.modules.task.public.")
            for name in task_imports
        ), relative

    composition = _source(APPLICATION_COMPOSITION)
    assert composition.count("build_task_module(") == 1
    assert "resolve_demand_ref" in composition
    assert "has_active_task" in composition
    assert "demand_triage" in composition
    assert "task_goal" in composition
    assert "demand_orchestration" in composition


def test_task_contributions_are_typed_and_generic_hosts_have_no_task_private_state() -> None:
    assert (REPO_ROOT / WEB_CONTRACTS).is_file(), WEB_CONTRACTS

    from buddyswitch.foundation.composition import ModuleAssembly

    assert [field.name for field in fields(ModuleAssembly)] == [
        "name",
        "daemon_handlers",
        "tools",
        "cli_commands",
        "skills",
        "cleanup",
        "actor_console_sections",
    ]

    for relative in GENERIC_HOSTS:
        imports = _imports(relative)
        assert not [
            name
            for name in imports
            if name.startswith("buddyswitch.modules.task.private")
            or name in {
                "buddyswitch.env.domain.task_sys",
                "buddyswitch.env.domain.task_read",
                "buddyswitch.env.tool_runtime.task_goal_runtime_client",
                "buddyswitch.env.tool_runtime.task_goal_runtime_protocol",
                "buddyswitch.launcher.task_goal_handler",
            }
        ], relative

    from buddyswitch.env.tool_runtime.context import ToolContext

    context_fields = {field.name for field in fields(ToolContext)}
    assert "task_goal_runtime" not in context_fields
    assert "task_sys" not in context_fields

    daemon_source = _source(Path("src/buddyswitch/launcher/instance_daemon.py"))
    assert "TaskGoalHandler" not in daemon_source
    assert "task_goal.reconcile_task" not in daemon_source


def test_task_owner_does_not_implement_or_import_demand_or_daemon_behavior() -> None:
    imports = _imports(FINAL_DOMAIN)
    source = _source(FINAL_DOMAIN)

    assert not [
        name
        for name in imports
        if "demand" in name or "daemon" in name or "app_server" in name
    ]
    assert "resolve_demand_ref" not in source
    assert "request_mailbox" not in source
    assert "goal_set" not in source
    assert "goal_get" not in source


def test_actor_tool_uses_injected_demand_resolver_and_exposes_exact_actions() -> None:
    tool_source = _source(FINAL_TOOL_ROOT / "tool.py")
    impl_source = _source(FINAL_TOOL_ROOT / "_impl.py")

    for action in ("list", "get", "create", "cancel"):
        assert tool_source.count(f'name="{action}"') == 1
    for retired in ("close", "need_parent"):
        assert f'name="{retired}"' not in tool_source
        assert f"def {retired}(" not in impl_source
    assert "demand_selection_resolver" in impl_source
    assert "TaskGoalClient" in impl_source
    assert "instance_json" in impl_source
    assert "modules.demand" not in impl_source
    assert "execution_brief" not in tool_source
    assert "selection_reason" in tool_source


def test_task_record_has_no_retired_execution_engine_vocabulary() -> None:
    source = _source(FINAL_DOMAIN)
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
    protocol = _source(FINAL_GOAL_ROOT / "protocol.py")
    client = _source(FINAL_GOAL_ROOT / "client.py")

    assert 'RECONCILE_TASK = "task_goal.reconcile_task"' in protocol
    assert "COMMAND_KEYS = frozenset({RECONCILE_TASK})" in protocol
    assert "request_mailbox" in client
    for forbidden in ("demand_sys", "bind_goal", "record_goal_complete", "selection_reason"):
        assert forbidden not in client


def test_read_projection_has_only_active_and_terminal_groups() -> None:
    source = _source(FINAL_READ_MODEL)

    assert '"active_tasks"' in source
    assert '"terminal_tasks"' in source
    assert "recoverable" not in source
    assert "execution" not in source
