#!/usr/bin/env python3
"""Projection-contract tests for External IM HTTP/Web surfaces."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from tools.launcher import im_http_router  # noqa: E402
from tools.launcher import web_management  # noqa: E402


class _FakeExternalImSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.connection = {"identity_id": "ext-fake"}
        self.participant = {"kind": "external", "external_id": "ext-fake"}

    def create_connection(self, *, display_name: str) -> dict[str, Any]:
        self.calls.append(("create_connection", {"display_name": display_name}))
        return {"ok": True, "connection_key": "imck-fake"}

    def authenticate(self, connection_key: str) -> dict[str, Any]:
        self.calls.append(("authenticate", {"connection_key": connection_key}))
        return {
            "ok": True,
            "identity": {"id": "ext-fake", "type": "external"},
            "participant": self.participant,
            "connection": self.connection,
        }

    def list_actors(self, *, role_id: str | None = None) -> dict[str, Any]:
        self.calls.append(("list_actors", {"role_id": role_id}))
        return {
            "ok": True,
            "actors": [
                {
                    "identity": {"id": "act-market-demo", "type": "actor"},
                    "identity_id": "act-market-demo",
                    "role_id": "market",
                    "reachability_status": "online",
                }
            ],
            "count": 1,
        }

    def send_message(
        self,
        *,
        connection: dict[str, Any],
        target_identity_id: Any,
        content: str,
        reply_to: Any = None,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "send_message",
                {
                    "connection": connection,
                    "target_identity_id": target_identity_id,
                    "content": content,
                    "reply_to": reply_to,
                },
            )
        )
        return {
            "ok": True,
            "message": {"id": "msg-fake", "conversation_id": "conv-fake", "reply_to": reply_to},
            "event_id": "imev-fake",
            "delivery_status": "accepted",
            "wake_status": "submitted",
        }

    def read_events(self, *, connection: dict[str, Any], limit: int = 50, wait_ms: int = 0) -> dict[str, Any]:
        self.calls.append(("read_events", {"connection": connection, "limit": limit, "wait_ms": wait_ms}))
        return {"ok": True, "events": []}

    def get_direct_conversation(
        self,
        *,
        connection: dict[str, Any],
        identity_id: Any,
        limit: int = 20,
    ) -> dict[str, Any]:
        self.calls.append(("get_direct_conversation", {"connection": connection, "identity_id": identity_id, "limit": limit}))
        return {"ok": False, "error": {"code": "E_IM_NOT_FOUND", "message": "direct conversation not found"}}

    def get_message(self, *, connection: dict[str, Any], message_id: str) -> dict[str, Any]:
        self.calls.append(("get_message", {"connection": connection, "message_id": message_id}))
        return {"ok": True, "message": {"id": message_id, "content": "pong"}}

    def list_replies(self, *, connection: dict[str, Any], message_id: str) -> dict[str, Any]:
        self.calls.append(("list_replies", {"connection": connection, "message_id": message_id}))
        return {"ok": True, "message_id": message_id, "replies": [], "count": 0}

    def update_disposition(
        self,
        *,
        connection: dict[str, Any],
        message_id: str,
        disposition: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "update_disposition",
                {
                    "connection": connection,
                    "message_id": message_id,
                    "disposition": disposition,
                    "reason": reason,
                },
            )
        )
        return {"ok": True, "message_id": message_id, "disposition": disposition}


class _FakeWebIdentityProvider:
    def __init__(self, connection: dict[str, Any]) -> None:
        self.connection = connection

    def ensure(self) -> dict[str, Any]:
        return {
            "identity": {"id": "ext-fake", "type": "external"},
            "connection": self.connection,
        }


class ExternalImProjectionContractTests(unittest.TestCase):
    def test_integration_router_rejects_missing_auth_without_session_call(self) -> None:
        session = _FakeExternalImSession()
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda _role_id: [],
            wake_actor=lambda _payload: {},
            im_session=session,
        )

        status, payload = router.handle("GET", "/api/im/events?wait_ms=0", b"", {})

        self.assertEqual(status, 401)
        self.assertFalse(payload["ok"])
        self.assertEqual(session.calls, [])

    def test_integration_router_maps_http_fields_to_external_session(self) -> None:
        session = _FakeExternalImSession()
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda _role_id: [],
            wake_actor=lambda _payload: {},
            im_session=session,
        )

        status, created = router.handle("POST", "/api/im/connections", b'{"display_name":"Bridge"}', {})
        self.assertEqual(status, 200)
        self.assertEqual(created["connection_key"], "imck-fake")

        status, actors = router.handle(
            "GET",
            "/api/im/actors?role_id=market",
            b"",
            {"Authorization": "Bearer imck-fake"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(actors["count"], 1)

        status, sent = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps(
                {
                    "target_identity_id": "act-market-demo",
                    "content": "ping",
                    "reply_to": None,
                }
            ).encode("utf-8"),
            {"Authorization": "Bearer imck-fake"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(sent["delivery_status"], "accepted")

        self.assertEqual(
            session.calls,
            [
                ("create_connection", {"display_name": "Bridge"}),
                ("authenticate", {"connection_key": "imck-fake"}),
                ("list_actors", {"role_id": "market"}),
                ("authenticate", {"connection_key": "imck-fake"}),
                (
                    "send_message",
                    {
                        "connection": session.connection,
                        "target_identity_id": "act-market-demo",
                        "content": "ping",
                        "reply_to": None,
                    },
                ),
            ],
        )

    def test_web_bff_rejects_cursor_before_session_read(self) -> None:
        session = _FakeExternalImSession()
        service = web_management.WebManagementService(
            repo_root=ROOT,
            web_im_identity_provider=_FakeWebIdentityProvider(session.connection),
            im_session=session,
        )

        with self.assertRaises(web_management.HttpError) as raised:
            service.handle_api(
                "GET",
                "/api/web/im/events?identity_id=act-market-demo&cursor=imev-old&wait_ms=0",
                b"",
                {},
            )

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(session.calls, [])

    def test_web_bff_shapes_events_and_empty_direct_conversation_around_session(self) -> None:
        session = _FakeExternalImSession()
        session.read_events = lambda **kwargs: (  # type: ignore[method-assign]
            session.calls.append(("read_events", dict(kwargs)))
            or {
                "ok": True,
                "events": [
                    {
                        "event_id": "imev-reply",
                        "message_id": "msg-reply",
                        "from_identity_id": "act-market-demo",
                        "to_identity_id": "ext-fake",
                    }
                ],
            }
        )
        service = web_management.WebManagementService(
            repo_root=ROOT,
            web_im_identity_provider=_FakeWebIdentityProvider(session.connection),
            im_session=session,
        )

        status, events = service.handle_api(
            "GET",
            "/api/web/im/events?identity_id=act-market-demo&wait_ms=0&limit=10",
            b"",
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual([event["event_id"] for event in events["events"]], ["imev-reply"])
        self.assertEqual(events["messages"], [{"id": "msg-reply", "content": "pong"}])

        status, conversation = service.handle_api(
            "GET",
            "/api/web/im/conversations/direct?identity_id=act-market-demo&limit=20",
            b"",
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(conversation, {"ok": True, "conversation": None, "messages": [], "count": 0})
        self.assertEqual(
            session.calls,
            [
                ("read_events", {"connection": session.connection, "limit": 10, "wait_ms": 0}),
                ("get_message", {"connection": session.connection, "message_id": "msg-reply"}),
                (
                    "get_direct_conversation",
                    {"connection": session.connection, "identity_id": "act-market-demo", "limit": 20},
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
