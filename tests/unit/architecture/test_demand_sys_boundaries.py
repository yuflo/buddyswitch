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
    assert 'getattr(rules, "demand_sys", None)' in impl_text

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


def test_phase_two_has_one_demand_daemon_adapter_and_no_task_or_generic_daemon_coupling() -> None:
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
    assert "env.domain.demand_sys" in adapter_imports
    assert not any("env.repos.demands" in name for name in adapter_imports)
    adapter_source = (REPO_ROOT / adapter).read_text(encoding="utf-8").lower()
    assert "task_sys" not in adapter_source
    assert "task sys" not in adapter_source
    assert "task lifecycle" not in adapter_source
    assert "task selection" not in adapter_source

    track_source = (REPO_ROOT / "tools/launcher/track_comment_added_handler.py").read_text(encoding="utf-8")
    task_ingress = (REPO_ROOT / "tools/launcher/task_sys_ingress.py").read_text(encoding="utf-8")
    task_runtime = (REPO_ROOT / "tools/launcher/task_sys_runtime.py").read_text(encoding="utf-8")
    actor_session = (REPO_ROOT / "tools/launcher/actor_session.py").read_text(encoding="utf-8")
    assert "demand_sys" not in track_source
    assert "ingest_im_message" not in task_ingress
    assert 'source_type == "im.message.created"' not in task_runtime
    assert "demand_sys" not in actor_session
    assert "demand-sys" not in actor_session


def test_phase_one_has_one_tool_name_and_one_actor_scoped_read_path() -> None:
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
    text = (REPO_ROOT / "docs/arch/demand-sys-architecture.md").read_text(encoding="utf-8")

    assert "opaque DemandRef" in text
    assert "Actor + installed task-management skill" in text
    assert "Task Sys -> IM or Demand" not in text
    assert "Task implementation -> Demand import, read, validation, call, subscription, or mutation" in text
