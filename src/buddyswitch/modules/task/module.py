"""Construct the passive typed Task product module."""

from __future__ import annotations

from buddyswitch.foundation.tool_runtime.definition import ToolRegistration
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.launcher.daemon_contracts import DaemonHandlerRegistration
from buddyswitch.modules.task.private.adapters.cleanup import CONTRIBUTION
from buddyswitch.modules.task.private.adapters.cli import REGISTRATION as CLI_REGISTRATION
from buddyswitch.modules.task.private.adapters.goal.handler import (
    TaskGoalHandler,
    command_handlers,
)
from buddyswitch.modules.task.private.adapters.tool.tool import (
    DEFINITION,
    build_invoke,
)
from buddyswitch.modules.task.private.adapters.web import (
    REGISTRATION as WEB_REGISTRATION,
)
from buddyswitch.modules.task.public.contracts import DemandSelectionResolver


def build_task_module(
    *,
    demand_selection_resolver: DemandSelectionResolver,
) -> ModuleAssembly:
    if not callable(demand_selection_resolver):
        raise ValueError("Demand selection resolver must be callable")
    return ModuleAssembly(
        name="task",
        daemon_handlers=(
            DaemonHandlerRegistration(
                name="task_goal",
                factory=TaskGoalHandler,
                application_command_factory=command_handlers,
            ),
        ),
        tools=(
            ToolRegistration(
                definition=DEFINITION,
                invoke=build_invoke(demand_selection_resolver),
            ),
        ),
        cli_commands=(CLI_REGISTRATION,),
        cleanup=(CONTRIBUTION,),
        actor_console_sections=(WEB_REGISTRATION,),
    )
