"""Validate and flatten explicitly selected module assemblies."""

from __future__ import annotations

from dataclasses import dataclass

from buddyswitch.application.composition import COMPONENTS
from buddyswitch.env.tool_runtime.definition import (
    ToolRegistration,
    validate_registration,
)
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.launcher.cli_contract import CliCommandRegistration
from buddyswitch.launcher.daemon_contracts import DaemonHandlerRegistration
from buddyswitch.runtime_support.env_cleanup import CleanupContribution
from buddyswitch.runtime_support.skill_contracts import SkillExport


@dataclass(frozen=True)
class ApplicationAssembly:
    modules: tuple[ModuleAssembly, ...]
    daemon_handlers: tuple[DaemonHandlerRegistration, ...]
    tools: tuple[ToolRegistration, ...]
    cli_commands: tuple[CliCommandRegistration, ...]
    skills: tuple[SkillExport, ...]
    cleanup: tuple[CleanupContribution, ...]


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
) -> ApplicationAssembly:
    if not isinstance(modules, tuple):
        raise ValueError("modules must be a tuple")

    module_names: set[str] = set()
    daemon_names: set[str] = set()
    tool_ids: set[str] = set()
    cli_names: set[str] = set()
    skill_ids: set[str] = set()
    cleanup_categories: set[str] = set()
    daemon_handlers: list[DaemonHandlerRegistration] = []
    tools: list[ToolRegistration] = []
    cli_commands: list[CliCommandRegistration] = []
    skills: list[SkillExport] = []
    cleanup: list[CleanupContribution] = []

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
            if not isinstance(contribution, CleanupContribution):
                raise ValueError(
                    "cleanup contribution must be CleanupContribution"
                )
            category = _text(
                contribution.category,
                label="cleanup category",
            )
            if not callable(contribution.discover):
                raise ValueError(
                    f"cleanup discoverer for '{category}' must be callable"
                )
            _unique(category, cleanup_categories, label="cleanup category")
            cleanup.append(contribution)

    return ApplicationAssembly(
        modules=modules,
        daemon_handlers=tuple(daemon_handlers),
        tools=tuple(tools),
        cli_commands=tuple(cli_commands),
        skills=tuple(skills),
        cleanup=tuple(cleanup),
    )


def activate_application(
    modules: tuple[ModuleAssembly, ...] = COMPONENTS,
) -> ApplicationAssembly:
    from buddyswitch.env.tool_runtime import native_mcp, registry
    from buddyswitch.launcher import codex_config
    from buddyswitch.runtime_support import env_manifest

    application = build_application(modules)
    registry.configure_tool_registrations(application.tools)
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
    return application
