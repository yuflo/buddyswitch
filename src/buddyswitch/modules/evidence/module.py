"""Passive typed assembly for the Evidence capability."""

from __future__ import annotations

from buddyswitch.foundation.tool_runtime.definition import ToolRegistration
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.modules.evidence.private.adapters.tool.tool import (
    DEFINITION,
    invoke,
)


EVIDENCE = ModuleAssembly(
    name="evidence",
    tools=(
        ToolRegistration(
            definition=DEFINITION,
            invoke=invoke,
        ),
    ),
)
