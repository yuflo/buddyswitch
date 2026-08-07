"""Passive Communication contributions to the generic WebHost."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from buddyswitch.foundation.identity.model import ActorIdentityProfile
from buddyswitch.foundation.daemon import client as daemon_client
from buddyswitch.launcher.web_contracts import (
    ActorConsoleSectionRegistration,
    WebHostAccess,
    WebRouteRegistration,
    WebWorkerRegistration,
)
from buddyswitch.modules.communication.private.adapters.actor import (
    im_actor_delivery,
)
from buddyswitch.modules.communication.private.adapters.web import (
    external_im_session,
    im_http_router,
    imessage_channel,
    web_im_identity,
)


class CommunicationWebRoute:
    def __init__(
        self,
        access: WebHostAccess,
        *,
        im_session: Any | None = None,
        web_identity_provider: Any | None = None,
    ) -> None:
        self._access = access
        self._session = (
            im_session
            if im_session is not None
            else external_im_session.ExternalImSession(
                actor_lister=self._list_actor_contacts,
                actor_reachability_checker=self._check_actor_reachability,
                actor_delivery_handler=self._deliver_actor,
            )
        )
        self._identity = (
            web_identity_provider
            if web_identity_provider is not None
            else web_im_identity.WebImIdentityProvider(im_session=self._session)
        )
        self._router = im_http_router.ImHttpRouter(
            actor_lister=self._list_actor_contacts,
            actor_reachability_checker=self._check_actor_reachability,
            actor_delivery_handler=self._deliver_actor,
            im_session=self._session,
            web_external_session_provider=self._identity.ensure,
        )

    def prepare(self) -> None:
        self._identity.ensure()

    def handle(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: Mapping[str, str] | None,
    ) -> tuple[int, dict[str, Any]]:
        try:
            return self._router.handle(method, path, body, headers)
        except web_im_identity.WebImIdentityError as exc:
            return 502, {
                "ok": False,
                "error": {
                    "code": "IM_IDENTITY_FAILED",
                    "message": str(exc),
                },
            }
        except ValueError as exc:
            return 409, {
                "ok": False,
                "error": {
                    "code": "IM_IDENTITY_BLOCKED",
                    "message": str(exc),
                },
            }

    def _list_actor_contacts(
        self,
        role_id: str | None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for instance in self._access.list_instances():
            identity_id = instance.get("actor_id")
            current_role = instance.get("role")
            if (
                not isinstance(identity_id, str)
                or not identity_id
                or not isinstance(current_role, str)
                or not current_role
            ):
                continue
            if role_id is not None and current_role != role_id:
                continue
            status = instance.get("status")
            rows.append(
                {
                    "identity_id": identity_id,
                    "identity": {"id": identity_id, "type": "actor"},
                    "role_id": current_role,
                    "status": status
                    if isinstance(status, str) and status
                    else "online",
                }
            )
        return rows

    @staticmethod
    def _check_actor_reachability(**kwargs: Any) -> dict[str, Any]:
        return daemon_client.check_reachability(**kwargs)

    @staticmethod
    def _deliver_actor(payload: dict[str, Any]) -> dict[str, Any]:
        return im_actor_delivery.deliver(payload)


def build_web_route(access: WebHostAccess) -> CommunicationWebRoute:
    return CommunicationWebRoute(access)


def build_imessage_worker(
    server_url: str,
) -> imessage_channel.ImessageChannelWorker:
    config = imessage_channel.ChannelConfig(server=server_url)
    controller = imessage_channel.ImessageChannelController(config=config)
    return imessage_channel.ImessageChannelWorker(controller)


def project_actor_console(
    profile: ActorIdentityProfile,
) -> Mapping[str, object]:
    return {
        "target": {
            "identity": profile.identity.to_payload(),
            "identity_id": profile.identity.id,
            "role_id": profile.role_id,
        }
    }


ROUTE_REGISTRATION = WebRouteRegistration(
    name="communication-im",
    factory=build_web_route,
    prefixes=("/api/im/",),
)
WORKER_REGISTRATION = WebWorkerRegistration(
    name="communication-imessage",
    factory=build_imessage_worker,
)
ACTOR_CONSOLE_REGISTRATION = ActorConsoleSectionRegistration(
    name="im",
    project=project_actor_console,
)
