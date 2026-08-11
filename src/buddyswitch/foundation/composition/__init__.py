"""Passive typed assembly returned by each explicitly selected product module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buddyswitch.foundation.tool_runtime.definition import ToolRegistration
    from buddyswitch.launcher.cli_contract import CliCommandRegistration
    from buddyswitch.foundation.daemon.contracts import DaemonHandlerRegistration
    from buddyswitch.foundation.daemon.inbound import InboundSourceRegistration
    from buddyswitch.launcher.web_contracts import (
        ActorConsoleSectionRegistration,
        WebRouteRegistration,
        WebWorkerRegistration,
    )
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
    actor_console_sections: tuple[ActorConsoleSectionRegistration, ...] = ()
    inbound_sources: tuple[InboundSourceRegistration, ...] = ()
    web_routes: tuple[WebRouteRegistration, ...] = ()
    web_workers: tuple[WebWorkerRegistration, ...] = ()
