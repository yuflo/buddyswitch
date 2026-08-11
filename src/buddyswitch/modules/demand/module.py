"""Passive typed assembly for the Demand product module."""

from __future__ import annotations

from buddyswitch.foundation.tool_runtime.definition import ToolRegistration
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.foundation.daemon.contracts import DaemonHandlerRegistration
from buddyswitch.modules.demand.private.adapters.cleanup import CONTRIBUTION
from buddyswitch.modules.demand.private.adapters.cli import REGISTRATION
from buddyswitch.modules.demand.private.adapters.daemon.demand_orchestration_handler import (
    DemandOrchestrationHandler,
)
from buddyswitch.modules.demand.private.adapters.daemon.demand_triage_handler import (
    DemandTriageHandler,
)
from buddyswitch.modules.demand.private.adapters.tool.tool import DEFINITION, invoke
from buddyswitch.runtime_support.skill_contracts import SkillExport


DEMAND = ModuleAssembly(
    name="demand",
    daemon_handlers=(
        DaemonHandlerRegistration(
            name="demand_triage",
            factory=DemandTriageHandler,
        ),
        DaemonHandlerRegistration(
            name="demand_orchestration",
            factory=DemandOrchestrationHandler,
        ),
    ),
    tools=(
        ToolRegistration(
            definition=DEFINITION,
            invoke=invoke,
        ),
    ),
    cli_commands=(REGISTRATION,),
    skills=(
        SkillExport(
            id="demand-triage",
            package_path="modules/demand/skills/demand-triage",
            enabled_by_default=False,
        ),
        SkillExport(
            id="demand-orchestration",
            package_path="modules/demand/skills/demand-orchestration",
        ),
    ),
    cleanup=(CONTRIBUTION,),
)
