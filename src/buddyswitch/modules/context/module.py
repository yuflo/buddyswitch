"""Passive typed assembly for the Context capability."""

from __future__ import annotations

from buddyswitch.env.tool_runtime.definition import ToolRegistration
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.modules.context.private.adapters.tool.tool import (
    DEFINITION,
    invoke,
)


CONTEXT = ModuleAssembly(
    name="context",
    tools=(
        ToolRegistration(
            definition=DEFINITION,
            invoke=invoke,
        ),
    ),
)
