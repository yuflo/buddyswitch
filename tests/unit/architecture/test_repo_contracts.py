"""Durable repository-wide ownership, import, and schema contracts."""

from __future__ import annotations

import ast
from pathlib import Path

from buddyswitch.env.tool_runtime import registry as tool_catalog
from tests.support.paths import REPO_ROOT


GENERIC_DAEMON_PATHS = (
    Path("src/buddyswitch/launcher/daemon_contracts.py"),
    Path("src/buddyswitch/launcher/daemon_state.py"),
    Path("src/buddyswitch/launcher/daemon_runtime.py"),
    Path("src/buddyswitch/launcher/daemon_core.py"),
    Path("src/buddyswitch/launcher/daemon_mailbox.py"),
    Path("src/buddyswitch/env/tool_runtime/daemon_client.py"),
)

DEMAND_REPOSITORY_PATH = Path("src/buddyswitch/env/repos/demands.py")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name:
                imported.add(module_name)
            imported.update(
                f"{module_name}.{alias.name}" if module_name else alias.name
                for alias in node.names
            )
    return imported


def _called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    return calls


def _call_count(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == name:
            count += 1
        elif isinstance(node.func, ast.Attribute) and node.func.attr == name:
            count += 1
    return count


def test_public_launcher_is_a_thin_python_cli_bootstrap() -> None:
    launcher = (REPO_ROOT / "buddyswitch-codex").read_text(encoding="utf-8")
    cli_adapter = REPO_ROOT / "src" / "buddyswitch" / "launcher" / "cli.py"

    assert cli_adapter.is_file()
    assert 'activation.json' in launcher
    assert 'venv/bin/python' in launcher
    assert '-m buddyswitch.application.entrypoints.cli' in launcher
    assert "source " not in launcher
    assert "PYTHONPATH" not in launcher


def test_public_cli_adapter_delegates_to_concrete_read_owners() -> None:
    cli_adapter = REPO_ROOT / "src" / "buddyswitch" / "launcher" / "cli.py"
    imports = _imported_modules(cli_adapter)
    calls = _called_names(cli_adapter)

    assert "buddyswitch.launcher.host_control" in imports
    assert "buddyswitch.launcher.actor_session" in imports
    assert "buddyswitch.env.domain.task_read" in imports
    assert "buddyswitch.env.domain.track_read" in imports
    assert not {
        "save_track",
        "create_track",
        "update_track",
        "write_json_object",
        "save_actor_identity_profile",
        "save_external_profile",
        "ingest",
        "record_task_close",
        "record_side_need_parent",
        "record_task_analysis_update",
        "record_side_runtime_failure",
    }.intersection(calls)


def test_generic_daemon_modules_do_not_depend_on_product_adapters() -> None:
    forbidden_import_fragments = (
        "task_sys",
        "im_actor_delivery",
        "im_wake_handler",
        "track_comment",
        "browser_runtime",
        "browser_page",
        "browser_release",
        "web_management",
        "buddyswitch.env.services.messages",
        "buddyswitch.env.repos.messages",
        "buddyswitch.env.repos.tracks",
    )
    for relative in GENERIC_DAEMON_PATHS:
        imports = _imported_modules(REPO_ROOT / relative)
        assert not [
            name
            for name in imports
            if any(fragment in name for fragment in forbidden_import_fragments)
        ], relative


def test_handlers_use_stable_contracts_and_one_composition_root() -> None:
    handlers = (
        "im_wake_handler.py",
        "track_comment_added_handler.py",
        "browser_page_expired_handler.py",
        "browser_release_handler.py",
        "demand_triage_handler.py",
        "task_goal_handler.py",
        "demand_orchestration_handler.py",
    )
    launcher_root = REPO_ROOT / "src" / "buddyswitch" / "launcher"
    for name in handlers:
        imports = _imported_modules(launcher_root / name)
        assert "buddyswitch.launcher.daemon_contracts" in imports
        assert "buddyswitch.launcher.daemon_core" not in imports

    product_adapters = (
        "demand_triage_handler",
        "task_goal_handler",
        "demand_orchestration_handler",
        "im_wake_handler",
        "track_comment_added_handler",
        "browser_page_expired_handler",
        "browser_release_handler",
    )
    composition_roots: list[str] = []
    for path in sorted(launcher_root.glob("*.py")):
        imports = _imported_modules(path)
        if "buddyswitch.launcher.daemon_core" in imports and any(
            fragment in imported
            for imported in imports
            for fragment in product_adapters
        ):
            composition_roots.append(path.name)
    assert composition_roots == ["instance_daemon.py"]


def test_active_runtime_modules_use_owned_repositories_not_env_store() -> None:
    roots = (
        REPO_ROOT / "src" / "buddyswitch" / "runtime_support" / "turn_runtime.py",
        REPO_ROOT / "src" / "buddyswitch" / "env" / "tools",
        REPO_ROOT / "src" / "buddyswitch" / "env" / "domain",
        REPO_ROOT / "src" / "buddyswitch" / "env" / "repos",
    )
    violations: list[str] = []
    for root in roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in paths:
            if "env_store" in _imported_modules(path):
                violations.append(path.relative_to(REPO_ROOT).as_posix())
    assert violations == []


def test_demand_actor_aggregate_has_one_atomic_repository_owner() -> None:
    repository = REPO_ROOT / DEMAND_REPOSITORY_PATH
    assert repository.is_file()
    imports = _imported_modules(repository)
    calls = _called_names(repository)

    assert "fcntl" in imports
    assert "runtime_files" in imports
    assert {"flock", "write_json_object"}.issubset(calls)
    assert _call_count(repository, "write_json_object") == 1

    path_owners: list[str] = []
    for root in (REPO_ROOT / "src" / "buddyswitch" / "env", REPO_ROOT / "src" / "buddyswitch" / "launcher"):
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            constants = {
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            }
            runtime_roots = {
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and node.attr in {"OBJECTS_ROOT", "LOCAL_ROOT"}
            }
            if "demand-sys" in constants and runtime_roots:
                path_owners.append(path.relative_to(REPO_ROOT).as_posix())

    assert path_owners == [DEMAND_REPOSITORY_PATH.as_posix()]


def test_tool_catalog_projections_are_generated_from_definitions() -> None:
    descriptions = tool_catalog.env_tools_description()
    operations = tool_catalog.operation_semantics()
    compact = tool_catalog.compact_tool_affordances()

    for tool in sorted(tool_catalog.supported_tools()):
        definition = tool_catalog.get_definition(tool)
        assert descriptions[tool]["object_model"] == definition.object_model
        assert compact[tool]["object_model"] == definition.object_model
        assert descriptions[tool]["native_mcp"]["tool_name_pattern"] == f"{tool}__<action>"
        assert "input_schemas" not in compact[tool]
        assert "payload_fields" not in compact[tool]
        for action in definition.actions:
            semantic = descriptions[tool]["action_semantics"][action.name]
            operation = operations[f"{tool}.{action.name}"]
            assert descriptions[tool]["native_mcp"]["actions"][action.name] == (
                f"{tool}__{action.name}"
            )
            assert semantic["visibility"] == action.visibility
            assert semantic["durability"] == action.durability
            assert semantic["result_content_level"] == action.result_content_level
            assert semantic["side_effects"]["reads"] == list(action.reads)
            assert semantic["side_effects"]["writes"] == list(action.writes)
            assert semantic["side_effects"]["does_not_write"] == list(
                action.does_not_write
            )
            assert operation["reads"] == list(action.reads)
            assert operation["writes"] == list(action.writes)
            assert operation["does_not_write"] == list(action.does_not_write)


def test_env_tool_catalog_excludes_source_write_capabilities() -> None:
    forbidden_tools = {"project", "dev_env", "source", "filesystem", "workspace_write"}
    forbidden_actions = {"apply_patch", "write_file", "delete_file", "configure_project"}
    supported_tools = set(tool_catalog.supported_tools())
    tool_packages = {
        path.name
        for path in (REPO_ROOT / "src" / "buddyswitch" / "env" / "tools").iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }

    assert forbidden_tools.isdisjoint(supported_tools)
    assert forbidden_tools.isdisjoint(tool_packages)
    for tool in supported_tools:
        assert forbidden_actions.isdisjoint(tool_catalog.supported_actions(tool))
