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
        self.external_session = {"identity_id": "ext-fake"}

    def create_external_session(self, *, display_name: str) -> dict[str, Any]:
        self.calls.append(("create_external_session", {"display_name": display_name}))
        return {"ok": True, "external_session_key": "imsk-fake"}

    def authenticate_external_session_key(self, external_session_key: str) -> dict[str, Any]:
        self.calls.append(("authenticate_external_session_key", {"external_session_key": external_session_key}))
        return {
            "ok": True,
            "identity": {"id": "ext-fake", "type": "external"},
            "external_session": self.external_session,
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
        external_session: dict[str, Any],
        target_identity_id: Any,
        content: str,
        reply_to: Any = None,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "send_message",
                {
                    "external_session": external_session,
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
            "actor_handling_status": "submitted",
        }

    def read_events(self, *, external_session: dict[str, Any], limit: int = 50, wait_ms: int = 0) -> dict[str, Any]:
        self.calls.append(("read_events", {"external_session": external_session, "limit": limit, "wait_ms": wait_ms}))
        return {"ok": True, "events": []}

    def get_direct_conversation(
        self,
        *,
        external_session: dict[str, Any],
        identity_id: Any,
        limit: int = 20,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_direct_conversation",
                {"external_session": external_session, "identity_id": identity_id, "limit": limit},
            )
        )
        return {"ok": False, "error": {"code": "E_IM_NOT_FOUND", "message": "direct conversation not found"}}

    def get_message(self, *, external_session: dict[str, Any], message_id: str) -> dict[str, Any]:
        self.calls.append(("get_message", {"external_session": external_session, "message_id": message_id}))
        return {"ok": True, "message": {"id": message_id, "content": "pong"}}

    def ack_event(self, *, external_session: dict[str, Any], event_id: str) -> dict[str, Any]:
        self.calls.append(("ack_event", {"external_session": external_session, "event_id": event_id}))
        return {"ok": True, "event_id": event_id}

    def list_replies(self, *, external_session: dict[str, Any], message_id: str) -> dict[str, Any]:
        self.calls.append(("list_replies", {"external_session": external_session, "message_id": message_id}))
        return {"ok": True, "message_id": message_id, "replies": [], "count": 0}

    def update_disposition(
        self,
        *,
        external_session: dict[str, Any],
        message_id: str,
        disposition: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "update_disposition",
                {
                    "external_session": external_session,
                    "message_id": message_id,
                    "disposition": disposition,
                    "reason": reason,
                },
            )
        )
        return {"ok": True, "message_id": message_id, "disposition": disposition}


class _FakeWebIdentityProvider:
    def __init__(self, external_session: dict[str, Any]) -> None:
        self.external_session = external_session
        self.calls: list[str] = []

    def ensure(self) -> dict[str, Any]:
        self.calls.append("ensure")
        return {
            "identity": {"id": "ext-fake", "type": "external"},
            "external_session": self.external_session,
            "external_session_key": "imsk-secret",
            "participant_token": "pt-secret",
            "event_cursor": "imev-secret",
            "client_kind": "web-management",
            "display_name": "BuddySwitch Web",
        }


class ExternalImProjectionContractTests(unittest.TestCase):
    def test_integration_router_rejects_missing_auth_without_session_call(self) -> None:
        session = _FakeExternalImSession()
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda _role_id: [],
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
            im_session=session,
        )

        status, created = router.handle("POST", "/api/im/external-sessions", b'{"display_name":"Bridge"}', {})
        self.assertEqual(status, 200)
        self.assertEqual(created["external_session_key"], "imsk-fake")
        self.assertNotIn("external_session_key_hash", created)

        status, removed = router.handle("POST", "/api/im/connections", b'{"display_name":"Bridge"}', {})
        self.assertEqual(status, 404)
        self.assertFalse(removed["ok"])

        status, actors = router.handle(
            "GET",
            "/api/im/actors?role_id=market",
            b"",
            {"Authorization": "Bearer imsk-fake"},
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
            {"Authorization": "Bearer imsk-fake"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(sent["delivery_status"], "accepted")

        self.assertEqual(
            session.calls,
            [
                ("create_external_session", {"display_name": "Bridge"}),
                ("authenticate_external_session_key", {"external_session_key": "imsk-fake"}),
                ("list_actors", {"role_id": "market"}),
                ("authenticate_external_session_key", {"external_session_key": "imsk-fake"}),
                (
                    "send_message",
                    {
                        "external_session": session.external_session,
                        "target_identity_id": "act-market-demo",
                        "content": "ping",
                        "reply_to": None,
                    },
                ),
            ],
        )

    def test_router_web_provider_session_and_protected_routes_use_shared_session(self) -> None:
        session = _FakeExternalImSession()
        provider = _FakeWebIdentityProvider(session.external_session)
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda _role_id: [],
            im_session=session,
            web_external_session_provider=provider.ensure,
        )

        status, web_session = router.handle("GET", "/api/im/session", b"", {})
        self.assertEqual(status, 200)
        self.assertEqual(
            web_session,
            {
                "ok": True,
                "identity": {"id": "ext-fake", "type": "external"},
                "client_kind": "web-management",
                "display_name": "BuddySwitch Web",
            },
        )
        self.assertNotIn("external_session_key", web_session)
        self.assertNotIn("participant_token", web_session)
        self.assertNotIn("event_cursor", web_session)
        self.assertNotIn("external_session", web_session)

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
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(sent["delivery_status"], "accepted")

        status, events = router.handle("GET", "/api/im/events?wait_ms=25&limit=3", b"", {})
        self.assertEqual(status, 200)
        self.assertEqual(events, {"ok": True, "events": []})

        status, acked = router.handle("POST", "/api/im/events/ack", b'{"event_id":"imev-fake"}', {})
        self.assertEqual(status, 200)
        self.assertEqual(acked, {"ok": True, "event_id": "imev-fake"})

        self.assertEqual(provider.calls, ["ensure", "ensure", "ensure", "ensure"])
        self.assertEqual(
            session.calls,
            [
                (
                    "send_message",
                    {
                        "external_session": session.external_session,
                        "target_identity_id": "act-market-demo",
                        "content": "ping",
                        "reply_to": None,
                    },
                ),
                ("read_events", {"external_session": session.external_session, "limit": 3, "wait_ms": 25}),
                ("ack_event", {"external_session": session.external_session, "event_id": "imev-fake"}),
            ],
        )

    def test_router_rejects_malformed_authorization_without_web_provider_fallback(self) -> None:
        session = _FakeExternalImSession()
        provider = _FakeWebIdentityProvider(session.external_session)
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda _role_id: [],
            im_session=session,
            web_external_session_provider=provider.ensure,
        )

        status, payload = router.handle("GET", "/api/im/session", b"", {"Authorization": "Basic nope"})

        self.assertEqual(status, 401)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "E_IM_AUTH")
        self.assertEqual(provider.calls, [])
        self.assertEqual(session.calls, [])

    def test_web_management_browser_im_projection_uses_unified_router_without_bff_event_shaping(self) -> None:
        session = _FakeExternalImSession()
        session.read_events = lambda **kwargs: (  # type: ignore[method-assign]
            session.calls.append(("read_events", dict(kwargs)))
            or {
                "ok": True,
                "events": [
                    {
                        "event_id": "imev-reply",
                        "message_id": "msg-reply",
                        "sender_identity": {"id": "act-market-demo", "type": "actor"},
                        "target_identity": {"id": "ext-fake", "type": "external"},
                    }
                ],
            }
        )
        session.get_direct_conversation = lambda **kwargs: (  # type: ignore[method-assign]
            session.calls.append(("get_direct_conversation", dict(kwargs)))
            or {"ok": True, "conversation": {"id": "conv-direct"}, "messages": [], "count": 0}
        )
        service = web_management.WebManagementService(
            repo_root=ROOT,
            web_im_identity_provider=_FakeWebIdentityProvider(session.external_session),
            im_session=session,
        )

        status, events = service.handle_api(
            "GET",
            "/api/im/events?wait_ms=0&limit=10",
            b"",
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual([event["event_id"] for event in events["events"]], ["imev-reply"])
        self.assertNotIn("messages", events)
        self.assertEqual(
            session.calls,
            [("read_events", {"external_session": session.external_session, "limit": 10, "wait_ms": 0})],
        )

        status, message = service.handle_api("GET", "/api/im/messages/msg-reply", b"", {})
        self.assertEqual(status, 200)
        self.assertEqual(message["message"], {"id": "msg-reply", "content": "pong"})

        status, acked = service.handle_api("POST", "/api/im/events/ack", b'{"event_id":"imev-reply"}', {})
        self.assertEqual(status, 200)
        self.assertEqual(acked, {"ok": True, "event_id": "imev-reply"})

        status, conversation = service.handle_api(
            "GET",
            "/api/im/conversations/direct?identity_id=act-market-demo&limit=20",
            b"",
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(conversation, {"ok": True, "conversation": {"id": "conv-direct"}, "messages": [], "count": 0})
        self.assertEqual(
            session.calls,
            [
                ("read_events", {"external_session": session.external_session, "limit": 10, "wait_ms": 0}),
                ("get_message", {"external_session": session.external_session, "message_id": "msg-reply"}),
                ("ack_event", {"external_session": session.external_session, "event_id": "imev-reply"}),
                (
                    "get_direct_conversation",
                    {"external_session": session.external_session, "identity_id": "act-market-demo", "limit": 20},
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
