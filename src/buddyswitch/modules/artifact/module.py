"""Passive typed assembly for the Artifact product module."""

from __future__ import annotations

from buddyswitch.foundation.tool_runtime.definition import ToolRegistration
from buddyswitch.foundation.composition import ModuleAssembly, SkillExport
from buddyswitch.modules.artifact.private.adapters.cleanup import (
    ARTIFACT_ATTACHMENTS_CONTRIBUTION,
    ARTIFACT_RECORDS_CONTRIBUTION,
)
from buddyswitch.modules.artifact.private.adapters.tool.tool import (
    DEFINITION,
    invoke,
)


ARTIFACT = ModuleAssembly(
    name="artifact",
    tools=(
        ToolRegistration(
            definition=DEFINITION,
            invoke=invoke,
        ),
    ),
    skills=(
        SkillExport(
            id="artifact-tool",
            package_path="modules/artifact/skills/artifact-tool",
        ),
    ),
    cleanup=(
        ARTIFACT_RECORDS_CONTRIBUTION,
        ARTIFACT_ATTACHMENTS_CONTRIBUTION,
    ),
)
