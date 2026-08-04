"""Passive typed assembly for the Search capability."""

from __future__ import annotations

from buddyswitch.foundation.tool_runtime.definition import ToolRegistration
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.modules.search.private.adapters.tool.tool import (
    DEFINITION,
    invoke,
)


SEARCH = ModuleAssembly(
    name="search",
    tools=(
        ToolRegistration(
            definition=DEFINITION,
            invoke=invoke,
        ),
    ),
)
