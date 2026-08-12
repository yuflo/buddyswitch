"""Passive typed assembly returned by each explicitly selected product module."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from buddyswitch.foundation.tool_runtime.definition import ToolRegistration
    from buddyswitch.foundation.cli_runtime.contracts import CliCommandRegistration
    from buddyswitch.foundation.daemon.contracts import DaemonHandlerRegistration
    from buddyswitch.foundation.daemon.inbound import InboundSourceRegistration
    from buddyswitch.foundation.web_runtime.contracts import (
        ActorConsoleSectionRegistration,
        WebRouteRegistration,
        WebWorkerRegistration,
    )


@dataclass(frozen=True)
class SkillExport:
    id: str
    package_path: str
    enabled_by_default: bool = True


@dataclass(frozen=True)
class OwnedStatePath:
    relative_path: str
    owner_roles: tuple[str, ...] = ()
    index_record: Mapping[str, Any] | None = None
    warning: str | None = None


@dataclass(frozen=True)
class CleanupIndexProjection:
    object_ids_field: str
    records_field: str


@dataclass(frozen=True)
class CleanupContribution:
    category: str
    discover: Callable[[Path], tuple[OwnedStatePath, ...]]
    required_directories: tuple[str, ...] = ()
    index_projection: CleanupIndexProjection | None = None


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
