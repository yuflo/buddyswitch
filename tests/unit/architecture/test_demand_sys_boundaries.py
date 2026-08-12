"""Machine-enforced ownership boundaries for Demand Sys."""

from __future__ import annotations

import ast
from dataclasses import fields, replace
from pathlib import Path

import pytest

from tests.support.paths import REPO_ROOT


DOMAIN = Path("src/buddyswitch/env/domain/demand_sys.py")
READ_MODEL = Path("src/buddyswitch/env/domain/demand_read.py")
REPOSITORY = Path("src/buddyswitch/env/repos/demands.py")
TOOL_ROOT = Path("src/buddyswitch/env/tools/demand_sys")
CONTEXT = Path("src/buddyswitch/foundation/tool_runtime/context.py")
CLI = Path("src/buddyswitch/foundation/cli_runtime/runtime.py")
ROLE_AUTH = Path("src/buddyswitch/runtime_support/role_auth.py")
CONTEXT_IMPL = Path(
    "src/buddyswitch/modules/context/private/adapters/tool/_impl.py"
)
DAEMON_ADAPTER = Path("src/buddyswitch/launcher/demand_sys_daemon_adapter.py")
DEMAND_TRIAGE_HANDLER = Path("src/buddyswitch/launcher/demand_triage_handler.py")
DEMAND_ORCHESTRATION_HANDLER = Path("src/buddyswitch/launcher/demand_orchestration_handler.py")
ARCH_ROOT = Path("docs/arch")
SKILLS_ROOT = Path("src/buddyswitch/skills")
ROLE_ROOT = Path("src/buddyswitch/launcher/assets/roles")
GENERIC_DAEMON_PATHS = (
    Path("src/buddyswitch/foundation/daemon/contracts.py"),
    Path("src/buddyswitch/foundation/daemon/state.py"),
    Path("src/buddyswitch/foundation/daemon/runtime.py"),
    Path("src/buddyswitch/foundation/daemon/instance.py"),
    Path("src/buddyswitch/foundation/daemon/mailbox.py"),
    Path("src/buddyswitch/foundation/daemon/client.py"),
)
DEMAND_ROOT = Path("src/buddyswitch/modules/demand")
FINAL_DOMAIN = DEMAND_ROOT / "private/domain/demand_sys.py"
FINAL_READ_MODEL = DEMAND_ROOT / "private/read_model.py"
FINAL_REPOSITORY = DEMAND_ROOT / "private/state/demands.py"
FINAL_TOOL_ROOT = DEMAND_ROOT / "private/adapters/tool"
FINAL_DAEMON_ROOT = DEMAND_ROOT / "private/adapters/daemon"
FINAL_SKILLS_ROOT = DEMAND_ROOT / "skills"
FINAL_UNIT_TEST_ROOT = DEMAND_ROOT / "tests/unit"
FINAL_INTEGRATION_TEST_ROOT = DEMAND_ROOT / "tests/integration"
APPLICATION_COMPOSITION = Path("src/buddyswitch/application/composition.py")
APPLICATION_BUILD = Path("src/buddyswitch/application/build.py")
MODULE_ASSEMBLY = Path("src/buddyswitch/foundation/composition/__init__.py")
DEMAND_PUBLIC = Path("src/buddyswitch/modules/demand/public/operations.py")
COMPOSED_HOST_IMPLEMENTATIONS = (
    Path("src/buddyswitch/foundation/cli_runtime/runtime.py"),
    Path("src/buddyswitch/foundation/daemon/instance_process.py"),
    Path("src/buddyswitch/foundation/tool_runtime/mcp_server.py"),
    Path("src/buddyswitch/foundation/runtime_broker/broker.py"),
    Path("src/buddyswitch/foundation/actor_runtime/environment.py"),
    Path("src/buddyswitch/runtime_support/runtime_skills.py"),
    Path("src/buddyswitch/runtime_support/env_cleanup.py"),
    Path("src/buddyswitch/foundation/tool_runtime/client.py"),
    Path("src/buddyswitch/runtime_support/turn_runtime.py"),
    Path("src/buddyswitch/foundation/app_server/runtime.py"),
    Path("src/buddyswitch/foundation/web_runtime/runtime.py"),
    Path("src/buddyswitch/foundation/cli_runtime/config.py"),
)


def test_demand_is_one_passive_module_selected_once_by_application_composition() -> None:
    for relative in (
        MODULE_ASSEMBLY,
        APPLICATION_BUILD,
        APPLICATION_COMPOSITION,
        DEMAND_ROOT / "module.py",
    ):
        assert (REPO_ROOT / relative).is_file(), relative

    from buddyswitch.application.composition import COMPONENTS
    from buddyswitch.foundation.composition import ModuleAssembly
    from buddyswitch.modules.demand.module import DEMAND

    assert COMPONENTS[0] is DEMAND
    assert sum(module is DEMAND for module in COMPONENTS) == 1
    assert isinstance(DEMAND, ModuleAssembly)
    assert [field.name for field in fields(ModuleAssembly)] == [
        "name",
        "daemon_handlers",
        "tools",
        "cli_commands",
        "skills",
        "cleanup",
        "actor_console_sections",
        "inbound_sources",
        "web_routes",
        "web_workers",
    ]

    composition_imports = _imports(APPLICATION_COMPOSITION)
    assert {
        "buddyswitch.modules.demand",
        "buddyswitch.modules.demand.public",
        "buddyswitch.modules.demand.module",
        "buddyswitch.modules.demand.module.DEMAND",
    }.issubset(composition_imports)
    assert not [
        imported
        for imported in composition_imports
        if imported.startswith("buddyswitch.modules.demand.private")
    ]
    composition_source = (REPO_ROOT / APPLICATION_COMPOSITION).read_text(encoding="utf-8")
    for private_name in (
        "DemandTriageHandler",
        "DemandOrchestrationHandler",
        "demand_sys",
        "demand-triage",
        "demand-orchestration",
        "CleanupContribution",
    ):
        assert private_name not in composition_source


def test_application_build_rejects_duplicate_and_invalid_contributions() -> None:
    assert (REPO_ROOT / APPLICATION_BUILD).is_file()
    assert (REPO_ROOT / DEMAND_ROOT / "module.py").is_file()

    from buddyswitch.application.build import build_application
    from buddyswitch.foundation.composition import ModuleAssembly
    from buddyswitch.modules.demand.module import DEMAND

    built = build_application(
        (DEMAND,),
        daemon_handler_order=("demand_triage", "demand_orchestration"),
    )
    assert built.modules == (DEMAND,)
    assert len(built.daemon_handlers) == 2
    assert len(built.tools) == 1
    assert len(built.cli_commands) == 1
    assert len(built.skills) == 2
    assert len(built.cleanup) == 1
    assert len(built.actor_console_sections) == 0

    with pytest.raises(ValueError, match="module name"):
        build_application(
            (replace(DEMAND, name=""),),
            daemon_handler_order=("demand_triage", "demand_orchestration"),
        )
    with pytest.raises(ValueError, match="duplicate module"):
        build_application(
            (DEMAND, DEMAND),
            daemon_handler_order=("demand_triage", "demand_orchestration"),
        )

    duplicate_cases = (
        ("daemon handler", "daemon_handlers"),
        ("tool", "tools"),
        ("CLI command", "cli_commands"),
        ("Skill", "skills"),
        ("cleanup category", "cleanup"),
    )
    for expected, field_name in duplicate_cases:
        duplicate = ModuleAssembly(
            name=f"demand-duplicate-{field_name}",
            **{field_name: getattr(DEMAND, field_name)},
        )
        with pytest.raises(ValueError, match=expected):
            build_application(
                (DEMAND, duplicate),
                daemon_handler_order=("demand_triage", "demand_orchestration"),
            )

    invalid = ModuleAssembly(name="invalid", tools=(object(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="ToolRegistration"):
        build_application((invalid,), daemon_handler_order=())


def test_demand_owner_public_and_local_proofs_have_one_final_physical_root() -> None:
    for relative in (
        FINAL_DOMAIN,
        FINAL_READ_MODEL,
        FINAL_REPOSITORY,
        FINAL_TOOL_ROOT / "tool.py",
        FINAL_TOOL_ROOT / "_impl.py",
        FINAL_DAEMON_ROOT / "demand_sys_daemon_adapter.py",
        FINAL_DAEMON_ROOT / "demand_triage_runtime.py",
        FINAL_DAEMON_ROOT / "demand_triage_handler.py",
        FINAL_DAEMON_ROOT / "demand_orchestration_handler.py",
        FINAL_SKILLS_ROOT / "demand-triage/SKILL.md",
        FINAL_SKILLS_ROOT / "demand-orchestration/SKILL.md",
        FINAL_UNIT_TEST_ROOT,
        FINAL_INTEGRATION_TEST_ROOT,
        DEMAND_PUBLIC,
    ):
        assert (REPO_ROOT / relative).exists(), relative

    for retired in (
        DOMAIN,
        READ_MODEL,
        REPOSITORY,
        TOOL_ROOT,
        DAEMON_ADAPTER,
        Path("src/buddyswitch/launcher/demand_triage_runtime.py"),
        DEMAND_TRIAGE_HANDLER,
        DEMAND_ORCHESTRATION_HANDLER,
        Path("src/buddyswitch/skills/shared/demand-triage"),
        Path("src/buddyswitch/skills/shared/demand-orchestration"),
        Path("tests/unit/demand_sys"),
        Path("tests/integration/demand_sys"),
    ):
        assert not (REPO_ROOT / retired).exists(), retired

    assert _call_owners("transact_actor_state") == [FINAL_DOMAIN.as_posix()]
    assert _call_owners("write_json_object").count(FINAL_REPOSITORY.as_posix()) == 1


def test_hosts_receive_typed_contributions_and_consumers_use_demand_public() -> None:
    assert (REPO_ROOT / DEMAND_PUBLIC).is_file()
    host_paths = (
        Path("src/buddyswitch/foundation/tool_runtime/context.py"),
        Path("src/buddyswitch/foundation/tool_runtime/native_mcp.py"),
        Path("src/buddyswitch/foundation/tool_runtime/registry.py"),
        Path("src/buddyswitch/foundation/runtime_broker/dispatcher.py"),
        Path("src/buddyswitch/foundation/daemon/instance_process.py"),
        Path("src/buddyswitch/foundation/cli_runtime/runtime.py"),
        Path("src/buddyswitch/foundation/tool_runtime/mcp_server.py"),
        Path("src/buddyswitch/foundation/cli_runtime/config.py"),
        Path("src/buddyswitch/foundation/actor_runtime/environment.py"),
        Path("src/buddyswitch/runtime_support/env_cleanup.py"),
        Path("src/buddyswitch/runtime_support/env_manifest.py"),
        Path("src/buddyswitch/runtime_support/runtime_skills.py"),
    )
    for relative in host_paths:
        imports = _imports(relative)
        assert not [
            name
            for name in imports
            if name.startswith("buddyswitch.modules.demand")
            or name in {
                "buddyswitch.env.domain.demand_sys",
                "buddyswitch.env.domain.demand_read",
                "buddyswitch.launcher.demand_triage_runtime",
                "buddyswitch.launcher.demand_triage_handler",
                "buddyswitch.launcher.demand_orchestration_handler",
            }
        ], relative

    consumer = Path(
        "src/buddyswitch/modules/track/private/adapters/daemon/"
        "track_comment_added_handler.py"
    )
    imports = _imports(consumer)
    assert "buddyswitch.modules.demand.public" in imports
    assert not any(name.startswith("buddyswitch.modules.demand.private") for name in imports)

    communication_handler = Path(
        "src/buddyswitch/modules/communication/private/adapters/daemon/"
        "im_wake_handler.py"
    )
    handler_imports = _imports(communication_handler)
    assert not any(name.startswith("buddyswitch.modules.demand") for name in handler_imports)
    composition_source = (REPO_ROOT / APPLICATION_COMPOSITION).read_text(encoding="utf-8")
    assert "enqueue_inbound=demand_public.enqueue_inbound" in composition_source


def test_composed_host_implementations_are_not_direct_module_entrypoints() -> None:
    for relative in COMPOSED_HOST_IMPLEMENTATIONS:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert 'if __name__ == "__main__":' not in source, relative


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


def _call_owners(name: str) -> list[str]:
    owners: list[str] = []
    root = REPO_ROOT / "src" / "buddyswitch"
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.relative_to(root).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == name
            for node in ast.walk(tree)
        ):
            owners.append(path.relative_to(REPO_ROOT).as_posix())
    return owners


def _demand_implementation_files() -> tuple[Path, ...]:
    return (
        FINAL_DOMAIN,
        FINAL_READ_MODEL,
        FINAL_REPOSITORY,
        *tuple(
            path.relative_to(REPO_ROOT)
            for path in sorted((REPO_ROOT / FINAL_TOOL_ROOT).glob("*.py"))
        ),
    )


def _current_demand_surfaces() -> tuple[Path, ...]:
    return (
        *_demand_implementation_files(),
        ROLE_AUTH,
        CONTEXT_IMPL,
        FINAL_DAEMON_ROOT / "demand_sys_daemon_adapter.py",
        FINAL_DAEMON_ROOT / "demand_triage_handler.py",
        FINAL_DAEMON_ROOT / "demand_orchestration_handler.py",
        FINAL_SKILLS_ROOT / "demand-orchestration/SKILL.md",
        *tuple(path.relative_to(REPO_ROOT) for path in sorted((REPO_ROOT / ARCH_ROOT).glob("*.md"))),
        *tuple(path.relative_to(REPO_ROOT) for path in sorted((REPO_ROOT / SKILLS_ROOT).rglob("SKILL.md"))),
        *tuple(path.relative_to(REPO_ROOT) for path in sorted((REPO_ROOT / ROLE_ROOT).glob("*/AGENTS.md"))),
    )


def _retired_demand_tokens() -> tuple[str, ...]:
    return (
        "demand_triage." + "resolve",
        "buddyswitch-" + "demand-triage",
        "demand." + "ingress.resolve",
        "demand_sys__" + "create",
        "demand_sys__" + "revise",
        "demand_sys__" + "cancel",
        "actor_creation_" + "receipts",
        "parent" + "_id",
        "depends" + "_on",
        "demand_sys." + "set_parent",
        "demand_sys." + "add_dependency",
        "demand_sys." + "remove_dependency",
        "demand_sys." + "split",
        "demand_sys." + "mark_duplicate",
        "demand_sys." + "supersede",
        "Demand" + "RelationConflict",
        "E_DEMAND_" + "RELATION",
        "terminal lineage",
        "live organization",
        "[DEMAND " + "CHECK]",
        "demand_sys." + "check",
        "demand_sys." + "get_many",
        "demand_sys." + "complete_check",
        "demand_sys." + "absorb_into",
        "checked_" + "revision",
        '"absorbed"',
        "expected_" + "revision",
    )


def test_dependency_direction_stays_inside_the_demand_owner_boundary() -> None:
    domain_imports = _imports(FINAL_DOMAIN)
    repository_imports = _imports(FINAL_REPOSITORY)
    read_imports = _imports(FINAL_READ_MODEL)
    tool_impl_imports = _imports(FINAL_TOOL_ROOT / "_impl.py")
    context_imports = _imports(CONTEXT)

    assert "buddyswitch.modules.demand.private.state.demands" in domain_imports
    assert "buddyswitch.foundation.state.runtime" in domain_imports
    assert "buddyswitch.foundation.state.runtime" in repository_imports
    assert "buddyswitch.modules.demand.private.domain.demand_sys" in read_imports
    assert not any(name.startswith("buddyswitch.env.repos") for name in read_imports)
    assert not any(name.startswith("buddyswitch.env.repos") for name in tool_impl_imports)
    assert "buddyswitch.modules.demand.private.domain.demand_sys" in tool_impl_imports
    assert not any("demand" in name for name in context_imports)

    impl_text = (REPO_ROOT / FINAL_TOOL_ROOT / "_impl.py").read_text(encoding="utf-8")
    assert 'getattr(getattr(context, "rules", None), "demand_sys", None)' not in impl_text

    for relative in (FINAL_DOMAIN, FINAL_READ_MODEL, FINAL_REPOSITORY):
        assert not [
            imported
            for imported in _imports(relative)
            if imported.startswith("buddyswitch.launcher")
        ], relative


def test_demand_mutation_has_one_domain_owner_and_one_repository_write_path() -> None:
    assert _call_owners("transact_actor_state") == [FINAL_DOMAIN.as_posix()]
    assert _call_owners("write_json_object").count(FINAL_REPOSITORY.as_posix()) == 1

    repository_source = (REPO_ROOT / FINAL_REPOSITORY).read_text(encoding="utf-8")
    domain_source = (REPO_ROOT / FINAL_DOMAIN).read_text(encoding="utf-8")
    assert repository_source.count("write_json_object(") == 1
    assert "demands.transact_actor_state(" in domain_source


def test_first_class_intake_state_and_domain_commands_are_absent() -> None:
    repository_source = (REPO_ROOT / FINAL_REPOSITORY).read_text(encoding="utf-8")
    domain_source = (REPO_ROOT / FINAL_DOMAIN).read_text(encoding="utf-8")

    assert '"intakes"' not in repository_source
    for command in (
        "capture_" + "intake",
        "get_" + "intake",
        "begin_" + "triage",
        "record_" + "triage",
        "retry_" + "intake",
        "apply_" + "triage_proposal",
    ):
        assert f"def {command}(" not in domain_source


def test_current_demand_surfaces_do_not_preserve_retired_models_or_transports() -> None:
    for relative in _current_demand_surfaces():
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for token in _retired_demand_tokens():
            assert token not in source, (relative, token)


def test_demand_attention_is_registered_product_code_and_generic_daemon_stays_neutral() -> None:
    for relative in GENERIC_DAEMON_PATHS:
        assert not [name for name in _imports(relative) if "demand" in name], relative
        source = (REPO_ROOT / relative).read_text(encoding="utf-8").lower()
        assert "demand_sys" not in source, relative
        assert "demand-sys" not in source, relative

    handler = Path(
        "src/buddyswitch/modules/communication/private/adapters/daemon/"
        "im_wake_handler.py"
    )
    adapter = FINAL_DAEMON_ROOT / "demand_sys_daemon_adapter.py"
    handler_imports = _imports(handler)
    adapter_imports = _imports(adapter)
    assert not any(name.startswith("buddyswitch.modules.demand") for name in handler_imports)
    assert "buddyswitch.modules.communication.private.domain" in handler_imports
    composition_source = (REPO_ROOT / APPLICATION_COMPOSITION).read_text(encoding="utf-8")
    assert "enqueue_inbound=demand_public.enqueue_inbound" in composition_source
    assert not any("task_sys" in name for name in handler_imports)
    assert not any("demand_sys" in name for name in adapter_imports)
    adapter_source = (REPO_ROOT / adapter).read_text(encoding="utf-8").lower()
    assert "task_sys" not in adapter_source
    assert "task sys" not in adapter_source
    assert "task lifecycle" not in adapter_source
    assert "task selection" not in adapter_source

    triage_imports = _imports(FINAL_DAEMON_ROOT / "demand_triage_handler.py")
    assert "buddyswitch.modules.demand.private.domain.demand_sys" in triage_imports
    assert "buddyswitch.env.domain.task_sys" not in triage_imports
    assert "buddyswitch.foundation.daemon.contracts" in triage_imports

    orchestration_imports = _imports(FINAL_DAEMON_ROOT / "demand_orchestration_handler.py")
    assert "buddyswitch.modules.demand.private.domain.demand_sys" in orchestration_imports
    assert "buddyswitch.modules.task.public" in orchestration_imports
    assert not any(
        name.startswith("buddyswitch.modules.task.private")
        for name in orchestration_imports
    )
    assert "buddyswitch.foundation.daemon.contracts" in orchestration_imports
    instance_daemon_source = (REPO_ROOT / "src/buddyswitch/foundation/daemon/instance_process.py").read_text(encoding="utf-8")
    assert "DemandTriageHandler" not in instance_daemon_source
    assert "DemandOrchestrationHandler" not in instance_daemon_source
    assert "DaemonHandlerRegistration" not in instance_daemon_source
    application_daemon_source = (
        REPO_ROOT / "src/buddyswitch/application/daemon.py"
    ).read_text(encoding="utf-8")
    assert "DaemonHandlerRegistration" in application_daemon_source

    track_handler = Path(
        "src/buddyswitch/modules/track/private/adapters/daemon/"
        "track_comment_added_handler.py"
    )
    track_imports = _imports(track_handler)
    track_source = (REPO_ROOT / track_handler).read_text(encoding="utf-8")
    actor_session = (
        REPO_ROOT / "src/buddyswitch/foundation/actor_runtime/session.py"
    ).read_text(encoding="utf-8")
    assert "buddyswitch.modules.demand.public" in track_imports
    assert not any("task_sys" in name for name in track_imports)
    assert "enqueue_inbound(" in track_source
    assert not (REPO_ROOT / "src/buddyswitch/launcher/task_sys_ingress.py").exists()
    assert "demand_sys" not in actor_session
    assert "demand-sys" not in actor_session


def test_demand_sys_has_one_tool_name_and_one_actor_scoped_read_path() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.foundation.tool_runtime import registry

    tool_root = REPO_ROOT / "src" / "buddyswitch" / "env" / "tools"
    assert not (tool_root / "demand_sys").exists()
    tool_ids = [
        registration.definition.id
        for registration in build_application().tools
    ]
    assert tool_ids.count("demand_sys") == 1

    read_imports = _imports(FINAL_READ_MODEL)
    cli_imports = _imports(CLI)
    assert "buddyswitch.modules.demand.private.domain.demand_sys" in read_imports
    assert not any("demand" in name for name in cli_imports)
    assert not any(name.startswith("buddyswitch.env.repos") for name in cli_imports)

    cli_source = (REPO_ROOT / CLI).read_text(encoding="utf-8")
    assert "list_external_demands" not in cli_source
    assert "get_external_demand" not in cli_source
    assert "demand-sys" not in cli_source
    assert "OBJECTS_ROOT" not in cli_source

    for path in (REPO_ROOT / "src" / "buddyswitch" / "env").rglob("*.py"):
        if path in {
            REPO_ROOT / FINAL_DOMAIN,
            REPO_ROOT / FINAL_READ_MODEL,
            REPO_ROOT / FINAL_REPOSITORY,
            REPO_ROOT / CONTEXT,
        } or (REPO_ROOT / FINAL_TOOL_ROOT) in path.parents:
            continue
        source = path.read_text(encoding="utf-8").lower()
        assert "demand_v2" not in source, path
        assert "legacy_demand" not in source, path
        assert "fallback_demand" not in source, path


def test_demand_public_surface_has_one_four_action_definition_and_no_goal_filter() -> None:
    from buddyswitch.modules.demand.private.adapters.tool.tool import DEFINITION

    assert {action.name for action in DEFINITION.actions} == {
        "list",
        "get",
        "resolve_inbound",
        "complete",
    }
    tool_source = (REPO_ROOT / FINAL_TOOL_ROOT / "tool.py").read_text(encoding="utf-8")
    impl_source = (REPO_ROOT / FINAL_TOOL_ROOT / "_impl.py").read_text(encoding="utf-8")
    for retired in ('name="create"', 'name="revise"', 'name="cancel"'):
        assert retired not in tool_source
    for goal_filter in ("goal_thread", "goal-specific", "goal_specific"):
        assert goal_filter not in tool_source.lower()
        assert goal_filter not in impl_source.lower()

    domain_source = (REPO_ROOT / FINAL_DOMAIN).read_text(encoding="utf-8")
    repository_source = (REPO_ROOT / FINAL_REPOSITORY).read_text(encoding="utf-8")
    for retired_definition in ("def create(", "def revise(", "def cancel("):
        assert retired_definition not in domain_source
    assert "actor_creation_" + "receipts" not in repository_source
    assert not (REPO_ROOT / "src/buddyswitch/launcher/demand_triage_mcp_server.py").exists()


def test_current_architecture_allows_only_opaque_task_reference_collaboration() -> None:
    demand_text = (REPO_ROOT / "docs/arch/demand-sys-architecture.md").read_text(encoding="utf-8")
    task_text = (REPO_ROOT / "docs/arch/task-sys-architecture.md").read_text(encoding="utf-8")
    normalized = " ".join(demand_text.split())
    normalized_task = " ".join(task_text.split())

    assert "private source-keyed ingress receipt" in demand_text
    assert "isolated demand-triage side" in demand_text
    assert "`demand_sys__resolve_inbound` through the normal unified" in demand_text
    assert "one-use capability" in demand_text
    assert "opaque current `demand_ref`" in demand_text
    assert "independent parent Demand orchestration" in demand_text
    assert "IM and Track owners first validate and persist their exact source fact" in normalized
    assert "The ingress receipt is recovery metadata" in demand_text
    assert "A terminal Task never mutates a Demand automatically" in demand_text
    assert "same Actor, same Demand, and completed" in demand_text
    assert "list, get, and complete" in demand_text
    assert "list, get, and resolve_inbound" in demand_text
    assert "## Explicit non-goals" in demand_text
    assert "No Demand graph" in demand_text
    assert "No first-class pre-Demand product object" in demand_text
    assert "Task domain code does not import or mutate Demand state" in normalized_task
    assert "Demand domain code does not import or mutate Task state" in normalized_task
