"""Passive typed assembly for the Artifact product module."""

from __future__ import annotations

from buddyswitch.env.tool_runtime.definition import ToolRegistration
from buddyswitch.foundation.composition import ModuleAssembly
from buddyswitch.modules.artifact.private.adapters.cleanup import (
    ARTIFACT_ATTACHMENTS_CONTRIBUTION,
    ARTIFACT_RECORDS_CONTRIBUTION,
)
from buddyswitch.modules.artifact.private.adapters.tool.tool import (
    DEFINITION,
    invoke,
)
from buddyswitch.runtime_support.skill_contracts import SkillExport


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
