"""Validate and flatten explicitly selected module assemblies."""

from __future__ import annotations

from dataclasses import dataclass

from buddyswitch.application.composition import (
    ACTIVE_TASK_PROBE,
    COMPONENTS,
    DAEMON_HANDLER_ORDER,
)
from buddyswitch.foundation.tool_runtime.definition import (
    ToolRegistration,
    validate_registration,
)
from buddyswitch.foundation.cli_runtime.contracts import CliCommandRegistration
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.foundation.daemon.contracts import DaemonHandlerRegistration
from buddyswitch.foundation.daemon import inbound
from buddyswitch.foundation.daemon.inbound import InboundSourceRegistration
from buddyswitch.foundation.web_runtime.contracts import (
    ActorConsoleSectionRegistration,
    WebRouteRegistration,
    WebWorkerRegistration,
    validate_web_route_registrations,
)
from buddyswitch.runtime_support.env_cleanup import (
    CleanupContribution,
    validate_cleanup_contributions,
)
from buddyswitch.runtime_support.skill_contracts import SkillExport


@dataclass(frozen=True)
class ApplicationAssembly:
    modules: tuple[ModuleAssembly, ...]
    daemon_handlers: tuple[DaemonHandlerRegistration, ...]
    tools: tuple[ToolRegistration, ...]
    cli_commands: tuple[CliCommandRegistration, ...]
    skills: tuple[SkillExport, ...]
    cleanup: tuple[CleanupContribution, ...]
    actor_console_sections: tuple[ActorConsoleSectionRegistration, ...]
    inbound_sources: tuple[InboundSourceRegistration, ...]
    web_routes: tuple[WebRouteRegistration, ...]
    web_workers: tuple[WebWorkerRegistration, ...]


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _unique(value: str, seen: set[str], *, label: str) -> None:
    if value in seen:
        raise ValueError(f"duplicate {label}: {value}")
    seen.add(value)


def build_application(
    modules: tuple[ModuleAssembly, ...] = COMPONENTS,
    *,
    daemon_handler_order: tuple[str, ...] = DAEMON_HANDLER_ORDER,
) -> ApplicationAssembly:
    if not isinstance(modules, tuple):
        raise ValueError("modules must be a tuple")

    module_names: set[str] = set()
    daemon_names: set[str] = set()
    tool_ids: set[str] = set()
    cli_names: set[str] = set()
    skill_ids: set[str] = set()
    actor_console_names: set[str] = set()
    inbound_event_types: set[str] = set()
    web_worker_names: set[str] = set()
    command_factory_ids: set[int] = set()
    daemon_handlers: list[DaemonHandlerRegistration] = []
    tools: list[ToolRegistration] = []
    cli_commands: list[CliCommandRegistration] = []
    skills: list[SkillExport] = []
    cleanup: list[CleanupContribution] = []
    actor_console_sections: list[ActorConsoleSectionRegistration] = []
    inbound_sources: list[InboundSourceRegistration] = []
    web_routes: list[WebRouteRegistration] = []
    web_workers: list[WebWorkerRegistration] = []

    for module in modules:
        if not isinstance(module, ModuleAssembly):
            raise ValueError("modules entries must be ModuleAssembly")
        module_name = _text(module.name, label="module name")
        _unique(module_name, module_names, label="module")

        for registration in module.daemon_handlers:
            if not isinstance(registration, DaemonHandlerRegistration):
                raise ValueError("daemon contribution must be DaemonHandlerRegistration")
            name = _text(registration.name, label="daemon handler name")
            if not callable(registration.factory):
                raise ValueError(f"daemon handler factory for '{name}' must be callable")
            command_factory = registration.application_command_factory
            if command_factory is not None:
                if not callable(command_factory):
                    raise ValueError(
                        f"application command factory for '{name}' must be callable"
                    )
                factory_id = id(command_factory)
                if factory_id in command_factory_ids:
                    raise ValueError(
                        f"duplicate application command factory: {name}"
                    )
                command_factory_ids.add(factory_id)
            _unique(name, daemon_names, label="daemon handler")
            daemon_handlers.append(registration)

        for registration in module.tools:
            if not isinstance(registration, ToolRegistration):
                raise ValueError("tool contribution must be ToolRegistration")
            validate_registration(registration)
            tool_id = registration.definition.id
            _unique(tool_id, tool_ids, label="tool")
            tools.append(registration)

        for registration in module.cli_commands:
            if not isinstance(registration, CliCommandRegistration):
                raise ValueError("CLI contribution must be CliCommandRegistration")
            name = _text(registration.name, label="CLI command name")
            if not isinstance(registration.help_rows, tuple) or not all(
                isinstance(row, str) and row.strip()
                for row in registration.help_rows
            ):
                raise ValueError(f"CLI command help rows for '{name}' must be text")
            if not callable(registration.handler):
                raise ValueError(f"CLI command handler for '{name}' must be callable")
            _unique(name, cli_names, label="CLI command")
            cli_commands.append(registration)

        for export in module.skills:
            if not isinstance(export, SkillExport):
                raise ValueError("Skill contribution must be SkillExport")
            skill_id = _text(export.id, label="Skill id")
            _text(export.package_path, label=f"Skill path for '{skill_id}'")
            _unique(skill_id, skill_ids, label="Skill")
            skills.append(export)

        for contribution in module.cleanup:
            cleanup.append(contribution)

        for registration in module.actor_console_sections:
            if not isinstance(registration, ActorConsoleSectionRegistration):
                raise ValueError(
                    "Actor Console contribution must be "
                    "ActorConsoleSectionRegistration"
                )
            name = _text(
                registration.name,
                label="Actor Console section name",
            )
            if not callable(registration.project):
                raise ValueError(
                    f"Actor Console projector for '{name}' must be callable"
                )
            _unique(name, actor_console_names, label="Actor Console section")
            actor_console_sections.append(registration)

        for registration in module.inbound_sources:
            if not isinstance(registration, InboundSourceRegistration):
                raise ValueError(
                    "inbound source contribution must be "
                    "InboundSourceRegistration"
                )
            normalized = inbound.normalized_registrations(
                (registration,)
            )[0]
            _unique(
                normalized.event_type,
                inbound_event_types,
                label="inbound event type",
            )
            inbound_sources.append(normalized)

        for registration in module.web_routes:
            web_routes.append(registration)

        for registration in module.web_workers:
            if not isinstance(registration, WebWorkerRegistration):
                raise ValueError(
                    "Web worker contribution must be WebWorkerRegistration"
                )
            name = _text(registration.name, label="Web worker name")
            if not callable(registration.factory):
                raise ValueError(
                    f"Web worker factory for '{name}' must be callable"
                )
            _unique(name, web_worker_names, label="Web worker name")
            web_workers.append(registration)

    if not isinstance(daemon_handler_order, tuple):
        raise ValueError("daemon handler order must be a tuple")
    normalized_order = tuple(
        _text(name, label="daemon handler order name")
        for name in daemon_handler_order
    )
    if (
        len(normalized_order) != len(set(normalized_order))
        or set(normalized_order) != daemon_names
    ):
        raise ValueError(
            "daemon handler order must be a one-to-one permutation of "
            "contributed handlers"
        )
    daemon_by_name = {
        registration.name.strip(): registration
        for registration in daemon_handlers
    }

    return ApplicationAssembly(
        modules=modules,
        daemon_handlers=tuple(
            daemon_by_name[name]
            for name in normalized_order
        ),
        tools=tuple(tools),
        cli_commands=tuple(cli_commands),
        skills=tuple(skills),
        cleanup=validate_cleanup_contributions(tuple(cleanup)),
        actor_console_sections=tuple(actor_console_sections),
        inbound_sources=tuple(inbound_sources),
        web_routes=validate_web_route_registrations(tuple(web_routes)),
        web_workers=tuple(web_workers),
    )


def activate_application(
    modules: tuple[ModuleAssembly, ...] = COMPONENTS,
    *,
    daemon_handler_order: tuple[str, ...] = DAEMON_HANDLER_ORDER,
    active_task_probe=ACTIVE_TASK_PROBE,
) -> ApplicationAssembly:
    from buddyswitch.foundation.tool_runtime import native_mcp, registry
    from buddyswitch.foundation.web_runtime import runtime as web_runtime
    from buddyswitch.launcher import codex_config
    from buddyswitch.runtime_support import env_manifest, role_auth

    application = build_application(
        modules,
        daemon_handler_order=daemon_handler_order,
    )
    registry.configure_authorizer(role_auth.authorize)
    registry.configure_tool_registrations(application.tools)
    registry.configure_active_task_probe(active_task_probe)
    env_manifest.configure_skill_exports(application.skills)
    codex_config.configure_parent_disabled_tools(
        tuple(
            native_mcp.encode_native_tool_name(
                registration.definition.id,
                action.name,
            )
            for registration in application.tools
            for action in registration.definition.actions
            if action.bound_capability_env is not None
        )
    )
    web_runtime.configure_actor_console_sections(
        application.actor_console_sections
    )
    web_runtime.configure_web_contributions(
        application.web_routes,
        application.web_workers,
    )
    return application
