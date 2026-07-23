"""Machine-enforced ownership boundaries for Demand Sys."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.support.paths import REPO_ROOT


DOMAIN = Path("scripts/env/domain/demand_sys.py")
READ_MODEL = Path("scripts/env/domain/demand_read.py")
REPOSITORY = Path("scripts/env/repos/demands.py")
TOOL_ROOT = Path("scripts/env/tools/demand_sys")
CONTEXT = Path("scripts/env/tool_runtime/context.py")
CLI = Path("tools/launcher/cli.py")
ROLE_AUTH = Path("scripts/env/tool_runtime/role_auth.py")
CONTEXT_IMPL = Path("scripts/env/tools/context/_impl.py")
DAEMON_ADAPTER = Path("tools/launcher/demand_sys_daemon_adapter.py")
DEMAND_TRIAGE_HANDLER = Path("tools/launcher/demand_triage_handler.py")
DEMAND_ORCHESTRATION_HANDLER = Path("tools/launcher/demand_orchestration_handler.py")
DEMAND_ORCHESTRATION_SKILL = Path("buddyswitch/skills/shared/demand-orchestration/SKILL.md")
ARCH_ROOT = Path("docs/arch")
SKILLS_ROOT = Path("buddyswitch/skills")
ROLE_ROOT = Path("tools/launcher/assets/roles")
GENERIC_DAEMON_PATHS = (
    Path("tools/launcher/daemon_contracts.py"),
    Path("tools/launcher/daemon_state.py"),
    Path("tools/launcher/daemon_runtime.py"),
    Path("tools/launcher/daemon_core.py"),
    Path("tools/launcher/daemon_mailbox.py"),
    Path("scripts/env/tool_runtime/daemon_client.py"),
)


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
    for root in (REPO_ROOT / "scripts" / "env", REPO_ROOT / "tools" / "launcher"):
        for path in sorted(root.rglob("*.py")):
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
        DOMAIN,
        READ_MODEL,
        REPOSITORY,
        *tuple(path.relative_to(REPO_ROOT) for path in sorted((REPO_ROOT / TOOL_ROOT).glob("*.py"))),
    )


def _current_demand_surfaces() -> tuple[Path, ...]:
    return (
        *_demand_implementation_files(),
        ROLE_AUTH,
        CONTEXT_IMPL,
        DAEMON_ADAPTER,
        DEMAND_TRIAGE_HANDLER,
        DEMAND_ORCHESTRATION_HANDLER,
        DEMAND_ORCHESTRATION_SKILL,
        *tuple(path.relative_to(REPO_ROOT) for path in sorted((REPO_ROOT / ARCH_ROOT).glob("*.md"))),
        *tuple(path.relative_to(REPO_ROOT) for path in sorted((REPO_ROOT / SKILLS_ROOT).rglob("SKILL.md"))),
        *tuple(path.relative_to(REPO_ROOT) for path in sorted((REPO_ROOT / ROLE_ROOT).glob("*/AGENTS.md"))),
    )


def _retired_demand_tokens() -> tuple[str, ...]:
    return (
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
    domain_imports = _imports(DOMAIN)
    repository_imports = _imports(REPOSITORY)
    read_imports = _imports(READ_MODEL)
    tool_impl_imports = _imports(TOOL_ROOT / "_impl.py")
    context_imports = _imports(CONTEXT)

    assert "env.repos.demands" in domain_imports
    assert "env.repos.runtime_files" in domain_imports
    assert "runtime_files" in repository_imports
    assert "env.domain.demand_sys" in read_imports
    assert not any(name.startswith("env.repos") for name in read_imports)
    assert not any(name.startswith("env.domain") for name in tool_impl_imports)
    assert not any(name.startswith("env.repos") for name in tool_impl_imports)
    assert "env.domain.demand_sys" in context_imports

    impl_text = (REPO_ROOT / TOOL_ROOT / "_impl.py").read_text(encoding="utf-8")
    assert 'getattr(getattr(context, "rules", None), "demand_sys", None)' in impl_text

    forbidden_fragments = ("task_sys", "tools.launcher", "daemon_")
    for relative in _demand_implementation_files():
        imports = _imports(relative)
        assert not [
            imported
            for imported in imports
            if any(fragment in imported for fragment in forbidden_fragments)
        ], relative


def test_demand_mutation_has_one_domain_owner_and_one_repository_write_path() -> None:
    assert _call_owners("transact_actor_state") == [DOMAIN.as_posix()]
    assert _call_owners("write_json_object").count(REPOSITORY.as_posix()) == 1

    repository_source = (REPO_ROOT / REPOSITORY).read_text(encoding="utf-8")
    domain_source = (REPO_ROOT / DOMAIN).read_text(encoding="utf-8")
    assert repository_source.count("write_json_object(") == 1
    assert "demands.transact_actor_state(" in domain_source


def test_first_class_intake_state_and_domain_commands_are_absent() -> None:
    repository_source = (REPO_ROOT / REPOSITORY).read_text(encoding="utf-8")
    domain_source = (REPO_ROOT / DOMAIN).read_text(encoding="utf-8")

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


def test_current_demand_surfaces_do_not_preserve_the_retired_graph_model() -> None:
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

    handler = Path("tools/launcher/im_wake_handler.py")
    adapter = Path("tools/launcher/demand_sys_daemon_adapter.py")
    handler_imports = _imports(handler)
    adapter_imports = _imports(adapter)
    assert "demand_sys_daemon_adapter" in handler_imports
    assert "env.services.messages" in handler_imports
    assert not any("task_sys" in name for name in handler_imports)
    assert "env.domain.demand_sys" not in adapter_imports
    assert not any("env.repos.demands" in name for name in adapter_imports)
    adapter_source = (REPO_ROOT / adapter).read_text(encoding="utf-8").lower()
    assert "task_sys" not in adapter_source
    assert "task sys" not in adapter_source
    assert "task lifecycle" not in adapter_source
    assert "task selection" not in adapter_source

    triage_imports = _imports(DEMAND_TRIAGE_HANDLER)
    assert "env.domain.demand_sys" in triage_imports
    assert "env.domain.task_sys" not in triage_imports
    assert "daemon_contracts" in triage_imports

    orchestration_imports = _imports(DEMAND_ORCHESTRATION_HANDLER)
    assert "env.domain.demand_sys" in orchestration_imports
    assert "env.domain.task_sys" in orchestration_imports
    assert "daemon_contracts" in orchestration_imports
    instance_daemon_source = (REPO_ROOT / "tools/launcher/instance_daemon.py").read_text(encoding="utf-8")
    assert "DemandTriageHandler()" in instance_daemon_source
    assert "DemandOrchestrationHandler()" in instance_daemon_source

    track_handler = Path("tools/launcher/track_comment_added_handler.py")
    track_imports = _imports(track_handler)
    track_source = (REPO_ROOT / track_handler).read_text(encoding="utf-8")
    actor_session = (REPO_ROOT / "tools/launcher/actor_session.py").read_text(encoding="utf-8")
    assert "demand_sys_daemon_adapter" in track_imports
    assert not any("task_sys" in name for name in track_imports)
    assert "enqueue_inbound(" in track_source
    assert not (REPO_ROOT / "tools/launcher/task_sys_ingress.py").exists()
    assert "demand_sys" not in actor_session
    assert "demand-sys" not in actor_session


def test_demand_sys_has_one_tool_name_and_one_actor_scoped_read_path() -> None:
    tool_root = REPO_ROOT / "scripts" / "env" / "tools"
    assert (tool_root / "demand_sys" / "tool.py").is_file()
    assert not (tool_root / "demand").exists()
    assert not (tool_root / "demand_v2").exists()

    read_imports = _imports(READ_MODEL)
    cli_imports = _imports(CLI)
    assert "env.domain.demand_sys" in read_imports
    assert "env.domain.demand_read" in cli_imports
    assert not any(name.startswith("env.repos") for name in cli_imports)

    cli_source = (REPO_ROOT / CLI).read_text(encoding="utf-8")
    assert "list_external_demands" in cli_source
    assert "get_external_demand" in cli_source
    assert "demand-sys" not in cli_source
    assert "OBJECTS_ROOT" not in cli_source

    for path in (REPO_ROOT / "scripts" / "env").rglob("*.py"):
        if path in {
            REPO_ROOT / DOMAIN,
            REPO_ROOT / READ_MODEL,
            REPO_ROOT / REPOSITORY,
            REPO_ROOT / CONTEXT,
        } or (REPO_ROOT / TOOL_ROOT) in path.parents:
            continue
        source = path.read_text(encoding="utf-8").lower()
        assert "demand_v2" not in source, path
        assert "legacy_demand" not in source, path
        assert "fallback_demand" not in source, path


def test_current_architecture_allows_only_opaque_task_reference_collaboration() -> None:
    demand_text = (REPO_ROOT / "docs/arch/demand-sys-architecture.md").read_text(encoding="utf-8")
    task_text = (REPO_ROOT / "docs/arch/task-sys-architecture.md").read_text(encoding="utf-8")
    normalized = " ".join(demand_text.split())
    normalized_task = " ".join(task_text.split())

    assert "private source-keyed ingress receipt" in demand_text
    assert "isolated demand-triage side" in demand_text
    assert "demand_triage.resolve" in demand_text
    assert "strict final-message JSON shape" in demand_text
    assert "opaque current `demand_ref`" in demand_text
    assert "independent parent Demand orchestration" in demand_text
    assert "IM and Track owners first validate and persist their exact source fact" in normalized
    assert "The ingress receipt is recovery metadata" in demand_text
    assert "A terminal Task never mutates a Demand automatically" in demand_text
    assert "## Explicit non-goals" in demand_text
    assert "No Demand graph" in demand_text
    assert "No first-class pre-Demand product object" in demand_text
    assert "Task domain code does not import or mutate Demand state" in normalized_task
    assert "Demand domain code does not import or mutate Task state" in normalized_task
