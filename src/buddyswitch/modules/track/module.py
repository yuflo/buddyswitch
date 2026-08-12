"""Construct the passive typed Track product module."""

from __future__ import annotations

from buddyswitch.foundation.tool_runtime.definition import ToolRegistration
from buddyswitch.foundation.composition import ModuleAssembly, SkillExport
from buddyswitch.modules.track.private.adapters.cleanup import (
    TRACK_COMMENTS_CONTRIBUTION,
    TRACK_RECORDS_CONTRIBUTION,
)
from buddyswitch.modules.track.private.adapters.cli import (
    REGISTRATION as CLI_REGISTRATION,
)
from buddyswitch.modules.track.private.adapters.daemon.track_comment_inbound import (
    track_comment_added_registration,
)
from buddyswitch.modules.track.private.adapters.tool.tool import (
    DEFINITION,
    build_invoke,
)
from buddyswitch.modules.track.private.adapters.web import (
    ACTOR_CONSOLE_REGISTRATION,
    ROUTE_REGISTRATION,
)
from buddyswitch.modules.track.public.contracts import (
    ReadReferenceMetadata,
    ResolvePublicationCandidate,
)


def build_track_module(
    *,
    resolve_publication_candidate: ResolvePublicationCandidate,
    read_reference_metadata: ReadReferenceMetadata,
) -> ModuleAssembly:
    return ModuleAssembly(
        name="track",
        tools=(
            ToolRegistration(
                definition=DEFINITION,
                invoke=build_invoke(
                    resolve_publication_candidate,
                    read_reference_metadata,
                ),
            ),
        ),
        cli_commands=(CLI_REGISTRATION,),
        skills=(
            SkillExport(
                id="triage-track",
                package_path="modules/track/skills/triage-track",
            ),
            SkillExport(
                id="track-tool",
                package_path="modules/track/skills/track-tool",
            ),
        ),
        cleanup=(
            TRACK_RECORDS_CONTRIBUTION,
            TRACK_COMMENTS_CONTRIBUTION,
        ),
        actor_console_sections=(ACTOR_CONSOLE_REGISTRATION,),
        inbound_sources=(track_comment_added_registration(),),
        web_routes=(ROUTE_REGISTRATION,),
    )
