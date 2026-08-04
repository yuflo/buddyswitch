"""Construct the passive typed Communication product module."""

from __future__ import annotations

from buddyswitch.env.tool_runtime.definition import ToolRegistration
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.modules.communication.private.adapters.cleanup import (
    CONTRIBUTION as CLEANUP_CONTRIBUTION,
)
from buddyswitch.modules.communication.private.adapters.daemon.message_inbound import (
    im_message_created_registration,
)
from buddyswitch.modules.communication.private.adapters.tool.tool import (
    DEFINITION,
    invoke,
)
from buddyswitch.modules.communication.private.adapters.web.registration import (
    ACTOR_CONSOLE_REGISTRATION,
    ROUTE_REGISTRATION,
    WORKER_REGISTRATION,
)
from buddyswitch.modules.communication.public.contracts import DemandEnqueue


def build_communication_module(
    *,
    enqueue_inbound: DemandEnqueue,
) -> ModuleAssembly:
    if not callable(enqueue_inbound):
        raise ValueError("Demand enqueue input must be callable")
    return ModuleAssembly(
        name="communication",
        tools=(
            ToolRegistration(
                definition=DEFINITION,
                invoke=invoke,
            ),
        ),
        cleanup=(CLEANUP_CONTRIBUTION,),
        actor_console_sections=(ACTOR_CONSOLE_REGISTRATION,),
        inbound_sources=(
            im_message_created_registration(enqueue_inbound),
        ),
        web_routes=(ROUTE_REGISTRATION,),
        web_workers=(WORKER_REGISTRATION,),
    )
