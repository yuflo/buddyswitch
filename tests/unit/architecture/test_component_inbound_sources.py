"""Typed application and Daemon proof for component inbound sources."""

from __future__ import annotations

import ast
from dataclasses import fields, replace
from pathlib import Path

import pytest

from tests.support.paths import REPO_ROOT


INSTANCE_DAEMON = Path("src/buddyswitch/launcher/instance_daemon.py")
APPLICATION_ENTRYPOINT = Path(
    "src/buddyswitch/application/entrypoints/instance_daemon.py"
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_module_assembly_has_only_the_approved_inbound_source_host_seam() -> None:
    from buddyswitch.foundation.composition import ModuleAssembly

    assert [field.name for field in fields(ModuleAssembly)] == [
        "name",
        "daemon_handlers",
        "tools",
        "cli_commands",
        "skills",
        "cleanup",
        "actor_console_sections",
        "inbound_sources",
    ]


def test_application_validates_and_rejects_duplicate_inbound_events() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.application.composition import TRACK
    from buddyswitch.foundation.composition import ModuleAssembly
    from buddyswitch.launcher.notification_center import (
        InboundSourceRegistration,
    )

    with pytest.raises(ValueError, match="InboundSourceRegistration"):
        build_application(
            (ModuleAssembly(name="invalid", inbound_sources=(object(),)),),
            daemon_handler_order=(),
        )

    def handler_factory() -> object:
        return object()

    cases = (
        (
            InboundSourceRegistration(
                event_type="",
                payload_contract={},
                handler_factory=handler_factory,
                owner_module="owner",
            ),
            "event_type",
        ),
        (
            InboundSourceRegistration(
                event_type="example.ready",
                payload_contract=None,  # type: ignore[arg-type]
                handler_factory=handler_factory,
                owner_module="owner",
            ),
            "payload_contract",
        ),
        (
            InboundSourceRegistration(
                event_type="example.ready",
                payload_contract={},
                handler_factory=None,  # type: ignore[arg-type]
                owner_module="owner",
            ),
            "handler_factory",
        ),
        (
            InboundSourceRegistration(
                event_type="example.ready",
                payload_contract={},
                handler_factory=handler_factory,
                owner_module="",
            ),
            "owner_module",
        ),
    )
    for registration, message in cases:
        with pytest.raises(ValueError, match=message):
            build_application(
                (
                    ModuleAssembly(
                        name=f"invalid-{message}",
                        inbound_sources=(registration,),
                    ),
                ),
                daemon_handler_order=(),
            )

    duplicate = replace(
        TRACK,
        name="duplicate-track-inbound",
        tools=(),
        cli_commands=(),
        skills=(),
        cleanup=(),
        actor_console_sections=(),
    )
    with pytest.raises(ValueError, match="duplicate inbound event type"):
        build_application(
            (TRACK, duplicate),
            daemon_handler_order=(),
        )


def test_track_inbound_is_contributed_once_and_generic_daemon_stays_neutral() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.launcher import instance_daemon

    application = build_application()
    assert [
        registration.event_type for registration in application.inbound_sources
    ] == ["track.comment.added"]
    assert instance_daemon.default_notify_subscriptions(
        application.inbound_sources
    ) == ["im.message.created", "track.comment.added"]

    imports = _imports(REPO_ROOT / INSTANCE_DAEMON)
    assert not [
        imported
        for imported in imports
        if imported.startswith("buddyswitch.modules.track")
        or "track_comment" in imported
    ]
    entrypoint_source = (REPO_ROOT / APPLICATION_ENTRYPOINT).read_text(
        encoding="utf-8"
    )
    assert "application.inbound_sources" in entrypoint_source


def test_message_and_browser_built_ins_remain_exact() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.launcher import browser_inbound, instance_daemon

    application = build_application()
    handlers = instance_daemon.default_daemon_handlers(
        application.daemon_handlers,
        application.inbound_sources,
    )
    assert [getattr(handler, "name", None) for handler in handlers] == [
        "im_message_created",
        "track_comment_added",
        "browser_page_expired",
        "browser_cockpit_release",
        "browser_failed_open_page_cleanup",
        "demand_triage",
        "task_goal",
        "demand_orchestration",
    ]
    assert [
        registration.event_type
        for registration in browser_inbound.inbound_registrations()
    ] == [
        "browser.page.expired",
        "browser.cockpit.release",
        "browser.failed_open_page.cleanup",
    ]
