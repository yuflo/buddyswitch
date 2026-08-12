"""Track-owned Web read projections."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from buddyswitch.foundation.identity.model import ActorIdentityProfile
from buddyswitch.foundation.web_runtime.contracts import (
    ActorConsoleSectionRegistration,
    HttpError,
    WebHostAccess,
    WebRouteRegistration,
)
from buddyswitch.modules.track import public as track_public


def project(actor_profile: ActorIdentityProfile) -> dict[str, object]:
    return {
        "items": track_public.list_external_tracks(
            owner_identity=actor_profile.identity.to_payload(),
        ),
        "source": "web-track-summary",
    }


ACTOR_CONSOLE_REGISTRATION = ActorConsoleSectionRegistration(
    name="tracks",
    project=project,
)


class TrackWebRoute:
    def prepare(self) -> None:
        return None

    def handle(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: Mapping[str, str] | None,
    ) -> tuple[int, dict[str, Any]]:
        del body, headers
        route = urlsplit(path).path
        if method == "GET" and route == "/api/tracks":
            return 200, {
                "ok": True,
                "tracks": track_public.list_external_tracks(),
            }
        if method == "GET" and route.startswith("/api/tracks/"):
            track_id = route[len("/api/tracks/") :]
            if "/" not in track_id:
                try:
                    detail = track_public.get_external_track(track_id)
                except ValueError as exc:
                    raise HttpError(
                        status=400,
                        code="INVALID_REQUEST",
                        message=str(exc),
                    ) from exc
                if detail is None:
                    raise HttpError(
                        status=404,
                        code="NOT_FOUND",
                        message=f"track not found: {track_id}",
                    )
                return 200, {"ok": True, "track": detail}
        raise HttpError(
            status=404,
            code="NOT_FOUND",
            message="API route not found.",
        )


def build_web_route(_access: WebHostAccess) -> TrackWebRoute:
    return TrackWebRoute()


ROUTE_REGISTRATION = WebRouteRegistration(
    name="track-read",
    factory=build_web_route,
    exact_paths=("/api/tracks",),
    prefixes=("/api/tracks/",),
)
