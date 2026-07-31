"""Track-owned Actor Console section projection."""

from __future__ import annotations

from buddyswitch.env.domain.identity import ActorIdentityProfile
from buddyswitch.launcher.web_contracts import ActorConsoleSectionRegistration
from buddyswitch.modules.track import public as track_public


def project(actor_profile: ActorIdentityProfile) -> dict[str, object]:
    return {
        "items": track_public.list_external_tracks(
            owner_identity=actor_profile.identity.to_payload(),
        ),
        "source": "web-track-summary",
    }


REGISTRATION = ActorConsoleSectionRegistration(
    name="tracks",
    project=project,
)
