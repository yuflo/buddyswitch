"""Passive typed assembly returned by each explicitly selected product module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buddyswitch.env.tool_runtime.definition import ToolRegistration
    from buddyswitch.launcher.cli_contract import CliCommandRegistration
    from buddyswitch.launcher.daemon_contracts import DaemonHandlerRegistration
    from buddyswitch.runtime_support.env_cleanup import CleanupContribution
    from buddyswitch.runtime_support.skill_contracts import SkillExport


@dataclass(frozen=True)
class ModuleAssembly:
    name: str
    daemon_handlers: tuple[DaemonHandlerRegistration, ...] = ()
    tools: tuple[ToolRegistration, ...] = ()
    cli_commands: tuple[CliCommandRegistration, ...] = ()
    skills: tuple[SkillExport, ...] = ()
    cleanup: tuple[CleanupContribution, ...] = ()
