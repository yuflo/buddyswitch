"""Machine-enforced ownership boundaries for Communication."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.support.paths import REPO_ROOT


COMMUNICATION_ROOT = Path("src/buddyswitch/modules/communication")
COMMUNICATION_PRIVATE = COMMUNICATION_ROOT / "private"
RETIRED_PATHS = (
    Path("src/buddyswitch/env/repos/messages.py"),
    Path("src/buddyswitch/env/services/messages.py"),
    Path("src/buddyswitch/env/tools/message"),
    Path("src/buddyswitch/foundation/tool_runtime/im_client.py"),
    Path("src/buddyswitch/foundation/tool_runtime/im_actor_delivery.py"),
    Path("src/buddyswitch/launcher/external_im_session.py"),
    Path("src/buddyswitch/launcher/im_http_router.py"),
    Path("src/buddyswitch/launcher/im_wake_handler.py"),
    Path("src/buddyswitch/launcher/imessage_channel.py"),
    Path("src/buddyswitch/launcher/message_inbound.py"),
    Path("src/buddyswitch/launcher/web_im_identity.py"),
)
REQUIRED_PRODUCTION = (
    COMMUNICATION_ROOT / "__init__.py",
    COMMUNICATION_ROOT / "module.py",
    COMMUNICATION_ROOT / "public/__init__.py",
    COMMUNICATION_ROOT / "public/contracts.py",
    COMMUNICATION_ROOT / "public/operations.py",
    COMMUNICATION_PRIVATE / "state/messages.py",
    COMMUNICATION_PRIVATE / "domain/messages.py",
    COMMUNICATION_PRIVATE / "adapters/cleanup.py",
    COMMUNICATION_PRIVATE / "adapters/actor/im_actor_delivery.py",
    COMMUNICATION_PRIVATE / "adapters/actor/im_client.py",
    COMMUNICATION_PRIVATE / "adapters/daemon/im_wake_handler.py",
    COMMUNICATION_PRIVATE / "adapters/daemon/message_inbound.py",
    COMMUNICATION_PRIVATE / "adapters/tool/tool.py",
    COMMUNICATION_PRIVATE / "adapters/tool/_impl.py",
    COMMUNICATION_PRIVATE / "adapters/web/external_im_session.py",
    COMMUNICATION_PRIVATE / "adapters/web/im_http_router.py",
    COMMUNICATION_PRIVATE / "adapters/web/imessage_channel.py",
    COMMUNICATION_PRIVATE / "adapters/web/registration.py",
    COMMUNICATION_PRIVATE / "adapters/web/web_im_identity.py",
)
MOVED_TESTS = (
    COMMUNICATION_ROOT / "tests/unit/test_actor_delivery.py",
    COMMUNICATION_ROOT / "tests/unit/test_delivery.py",
    COMMUNICATION_ROOT / "tests/unit/test_imessage_command_client.py",
    COMMUNICATION_ROOT / "tests/unit/test_imessage_inbound_parser.py",
    COMMUNICATION_ROOT / "tests/integration/_imessage_fakes.py",
    COMMUNICATION_ROOT / "tests/integration/test_external_session.py",
    COMMUNICATION_ROOT / "tests/integration/test_http_router.py",
    COMMUNICATION_ROOT / "tests/integration/test_imessage_outbound.py",
    COMMUNICATION_ROOT / "tests/integration/test_imessage_routing.py",
    COMMUNICATION_ROOT / "tests/integration/test_imessage_state.py",
    COMMUNICATION_ROOT / "tests/integration/test_imessage_worker.py",
    COMMUNICATION_ROOT / "tests/integration/test_product_core.py",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            if module:
                imported.add(module)
            imported.update(
                f"{module}.{alias.name}" if module else alias.name
                for alias in node.names
            )
    return imported


def test_communication_has_one_physical_owner_and_no_retired_live_path() -> None:
    assert [
        path.as_posix()
        for path in (*REQUIRED_PRODUCTION, *MOVED_TESTS)
        if not (REPO_ROOT / path).is_file()
    ] == []
    for retired in RETIRED_PATHS:
        assert not (REPO_ROOT / retired).exists(), retired


def test_communication_is_selected_once_with_exact_contributions() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.application.composition import COMMUNICATION, COMPONENTS
    from buddyswitch.foundation.tool_runtime import registry
    from buddyswitch.foundation.composition import ModuleAssembly

    assert isinstance(COMMUNICATION, ModuleAssembly)
    assert sum(component is COMMUNICATION for component in COMPONENTS) == 1
    assert len(COMMUNICATION.tools) == 1
    assert COMMUNICATION.tools[0].definition.id == "message"
    assert len(COMMUNICATION.inbound_sources) == 1
    assert COMMUNICATION.inbound_sources[0].event_type == "im.message.created"
    assert [route.exact_paths for route in COMMUNICATION.web_routes] == [()]
    assert [route.prefixes for route in COMMUNICATION.web_routes] == [
        ("/api/im/",)
    ]
    assert [worker.name for worker in COMMUNICATION.web_workers] == [
        "communication-imessage"
    ]
    assert [section.name for section in COMMUNICATION.actor_console_sections] == [
        "im"
    ]
    assert [item.category for item in COMMUNICATION.cleanup] == [
        "message_objects"
    ]
    application = build_application()
    assert [tool.definition.id for tool in application.tools].count("message") == 1
    assert [source.event_type for source in application.inbound_sources].count(
        "im.message.created"
    ) == 1


def test_communication_public_and_input_port_are_exact() -> None:
    from buddyswitch.modules.communication import public

    assert set(public.__all__) == {
        "get_im_message",
        "list_im_replies",
        "send_im_message",
        "list_im_events_for_identity",
    }
    public_root = REPO_ROOT / COMMUNICATION_ROOT / "public"
    assert {path.name for path in public_root.glob("*.py")} == {
        "__init__.py",
        "contracts.py",
        "operations.py",
    }
    module_source = (REPO_ROOT / COMMUNICATION_ROOT / "module.py").read_text(
        encoding="utf-8"
    )
    composition_source = (
        REPO_ROOT / "src/buddyswitch/application/composition.py"
    ).read_text(encoding="utf-8")
    assert "DemandEnqueue" in module_source
    assert "enqueue_inbound=demand_public.enqueue_inbound" in composition_source


def test_dependency_direction_uses_public_edges_and_generic_hosts() -> None:
    communication_private_imports: list[tuple[str, str]] = []
    for path in sorted((REPO_ROOT / COMMUNICATION_PRIVATE).rglob("*.py")):
        for imported in _imports(path):
            if imported.startswith("buddyswitch.modules.demand"):
                communication_private_imports.append(
                    (path.relative_to(REPO_ROOT).as_posix(), imported)
                )
    assert communication_private_imports == []

    demand_private = REPO_ROOT / "src/buddyswitch/modules/demand/private"
    assert not [
        (path.relative_to(REPO_ROOT).as_posix(), imported)
        for path in sorted(demand_private.rglob("*.py"))
        for imported in _imports(path)
        if imported.startswith("buddyswitch.modules.communication.private")
    ]
    triage_imports = _imports(
        demand_private / "adapters/daemon/demand_triage_runtime.py"
    )
    context_imports = _imports(
        REPO_ROOT
        / "src/buddyswitch/modules/context/private/adapters/tool/_impl.py"
    )
    assert "buddyswitch.modules.communication" in triage_imports
    assert "buddyswitch.modules.communication" in context_imports

    for relative in (
        Path("src/buddyswitch/launcher/web_management.py"),
        Path("src/buddyswitch/launcher/instance_daemon.py"),
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        imports = _imports(REPO_ROOT / relative)
        assert not [
            imported
            for imported in imports
            if imported.startswith("buddyswitch.modules.communication")
        ], relative
        assert "/api/im/" not in source, relative
        assert "iMessage" not in source, relative


def test_module_test_roots_import_private_code_only_from_their_owner() -> None:
    violations: list[tuple[str, str]] = []
    modules_root = REPO_ROOT / "src/buddyswitch/modules"
    for test_root in sorted(modules_root.glob("*/tests")):
        owner = test_root.parent.name
        for path in sorted(test_root.rglob("*.py")):
            for imported in _imports(path):
                prefix = "buddyswitch.modules."
                if not imported.startswith(prefix) or ".private" not in imported:
                    continue
                imported_owner = imported[len(prefix) :].split(".", 1)[0]
                if imported_owner != owner:
                    violations.append(
                        (path.relative_to(REPO_ROOT).as_posix(), imported)
                    )
    assert violations == []


def test_cleanup_host_uses_generic_multi_owner_and_index_projection_contracts() -> None:
    cleanup_path = REPO_ROOT / "src/buddyswitch/runtime_support/env_cleanup.py"
    source = cleanup_path.read_text(encoding="utf-8")
    assert "owner_roles" in source
    assert "CleanupIndexProjection" in source
    assert "contribution.index_projection" in source
    for retired_helper in (
        "discover_message_objects",
        "add_indexed_message",
        "message_object_json_path",
    ):
        assert retired_helper not in source
    for product_enumeration in (
        "CATEGORY_ORDER",
        '"message_objects"',
        '"artifact_objects"',
        '"comment_objects"',
        '"artifact_object_ids"',
        '"message_object_ids"',
        '"comment_object_ids"',
        '"artifact_records"',
        '"message_records"',
        '"comment_records"',
    ):
        assert product_enumeration not in source
    tree = ast.parse(source, filename=str(cleanup_path))
    category_branches = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and any(
            isinstance(comparator, ast.Constant)
            and comparator.value in {
                "message_objects",
                "artifact_objects",
                "comment_objects",
            }
            for comparator in node.comparators
        )
    ]
    assert category_branches == []


def test_application_rejects_cleanup_projection_collisions_without_discovery() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.foundation.composition import ModuleAssembly
    from buddyswitch.runtime_support.env_cleanup import (
        CleanupContribution,
        CleanupIndexProjection,
    )

    discoveries: list[str] = []

    def discover(_root: Path):
        discoveries.append("called")
        return ()

    valid = CleanupContribution(
        category="probe_objects",
        discover=discover,
        index_projection=CleanupIndexProjection(
            object_ids_field="probe_object_ids",
            records_field="probe_records",
        ),
    )
    application = build_application(
        (ModuleAssembly(name="valid", cleanup=(valid,)),),
        daemon_handler_order=(),
    )
    assert application.cleanup == (valid,)
    assert discoveries == []

    invalid_projections = (
        CleanupIndexProjection("warnings", "probe_records_2"),
        CleanupIndexProjection("same", "same"),
    )
    for index, projection in enumerate(invalid_projections):
        invalid = CleanupContribution(
            category=f"invalid_{index}",
            discover=discover,
            index_projection=projection,
        )
        with pytest.raises(ValueError, match="cleanup.*field"):
            build_application(
                (ModuleAssembly(name=f"invalid-{index}", cleanup=(invalid,)),),
                daemon_handler_order=(),
            )

    duplicate = CleanupContribution(
        category="duplicate_objects",
        discover=discover,
        index_projection=CleanupIndexProjection(
            object_ids_field="probe_object_ids",
            records_field="duplicate_records",
        ),
    )
    with pytest.raises(ValueError, match="cleanup.*field"):
        build_application(
            (ModuleAssembly(name="duplicate", cleanup=(valid, duplicate)),),
            daemon_handler_order=(),
        )
    assert discoveries == []


def test_current_guidance_names_only_the_communication_owner_and_generic_host_edge() -> None:
    architecture = REPO_ROOT / "docs/arch/communication-capability-architecture.md"
    web_architecture = REPO_ROOT / "docs/arch/web-interface-call-architecture.md"
    assert architecture.is_file()
    text = architecture.read_text(encoding="utf-8") + web_architecture.read_text(
        encoding="utf-8"
    )
    assert "src/buddyswitch/modules/communication/" in text
    assert "WebRouteRegistration" in text
    assert "WebWorkerRegistration" in text
    for retired in (
        "src/buddyswitch/env/repos/messages.py",
        "src/buddyswitch/env/services/messages.py",
        "src/buddyswitch/env/tools/message",
        "src/buddyswitch/launcher/im_http_router.py",
        "src/buddyswitch/launcher/im_wake_handler.py",
    ):
        assert retired not in text
