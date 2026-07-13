"""WebManagement projection tests for Central IM."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from tools.launcher import web_management  # noqa: E402


class _FakeExternalImSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def create_external_session(self, *, display_name: str) -> dict[str, object]:
        self.calls.append(("create_external_session", {"display_name": display_name}))
        return {"ok": True, "external_session_key": "imsk-bridge"}

    def authenticate_external_session_key(self, external_session_key: str) -> dict[str, object]:
        self.calls.append(("authenticate_external_session_key", {"external_session_key": external_session_key}))
        return {
            "ok": True,
            "identity": {"id": "ext-bridge", "type": "external"},
            "external_session": {"identity_id": "ext-bridge"},
        }

    def list_actors(self, *, role_id: str | None = None) -> dict[str, object]:
        self.calls.append(("list_actors", {"role_id": role_id}))
        return {
            "ok": True,
            "actors": [
                {
                    "identity": {"id": "act-market-demo", "type": "actor"},
                    "identity_id": "act-market-demo",
                    "role_id": "market",
                    "reachability_status": "active",
                }
            ],
            "count": 1,
        }

    def send_message(
        self,
        *,
        external_session: dict[str, object],
        target_identity_id: object,
        content: str,
        reply_to: object = None,
    ) -> dict[str, object]:
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
        return {"ok": True, "delivery_status": "accepted", "message": {"id": "msg-bridge"}}

    def read_events(self, *, external_session: dict[str, object], limit: int = 50, wait_ms: int = 0) -> dict[str, object]:
        self.calls.append(("read_events", {"external_session": external_session, "limit": limit, "wait_ms": wait_ms}))
        return {"ok": True, "events": [{"event_id": "imev-bridge", "message_id": "msg-reply"}]}

    def ack_event(self, *, external_session: dict[str, object], event_id: str) -> dict[str, object]:
        self.calls.append(("ack_event", {"external_session": external_session, "event_id": event_id}))
        return {"ok": True, "event_id": event_id}


class _FakeWebIdentityProvider:
    def __init__(self) -> None:
        self.external_session = {"identity_id": "ext-web"}
        self.calls: list[str] = []

    def ensure(self) -> dict[str, object]:
        self.calls.append("ensure")
        return {
            "identity": {"id": "ext-web", "type": "external"},
            "external_session": self.external_session,
            "external_session_key": "imsk-secret",
            "client_kind": "web-management",
            "display_name": "BuddySwitch Web",
        }


class ImWebManagementProjectionTests(unittest.TestCase):
    def test_web_management_exposes_external_im_routes_for_bridge(self) -> None:
        session = _FakeExternalImSession()
        service = web_management.WebManagementService(repo_root=ROOT, im_session=session)  # type: ignore[arg-type]

        status, created = service.handle_api("POST", "/api/im/external-sessions", b'{"display_name":"Bridge"}', {})
        self.assertEqual(status, 200)
        self.assertEqual(created["external_session_key"], "imsk-bridge")
        self.assertNotIn("external_session_key_hash", created)

        status, removed = service.handle_api("POST", "/api/im/connections", b'{"display_name":"Bridge"}', {})
        self.assertEqual(status, 404)
        self.assertFalse(removed["ok"])

        status, actors = service.handle_api(
            "GET",
            "/api/im/actors?role_id=market",
            b"",
            {"Authorization": "Bearer imsk-bridge"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(actors["count"], 1)
        self.assertEqual(actors["actors"][0]["identity_id"], "act-market-demo")

        self.assertEqual(
            session.calls,
            [
                ("create_external_session", {"display_name": "Bridge"}),
                ("authenticate_external_session_key", {"external_session_key": "imsk-bridge"}),
                ("list_actors", {"role_id": "market"}),
            ],
        )

    def test_web_management_exposes_browser_im_routes_through_shared_router(self) -> None:
        session = _FakeExternalImSession()
        provider = _FakeWebIdentityProvider()
        service = web_management.WebManagementService(
            repo_root=ROOT,
            im_session=session,  # type: ignore[arg-type]
            web_im_identity_provider=provider,  # type: ignore[arg-type]
        )

        status, web_session = service.handle_api("GET", "/api/im/session", b"", {})
        self.assertEqual(status, 200)
        self.assertEqual(web_session["identity"], {"id": "ext-web", "type": "external"})
        self.assertNotIn("external_session_key", web_session)

        status, sent = service.handle_api(
            "POST",
            "/api/im/messages",
            b'{"target_identity_id":"act-market-demo","content":"ping"}',
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(sent["delivery_status"], "accepted")

        status, events = service.handle_api("GET", "/api/im/events?limit=5&wait_ms=10", b"", {})
        self.assertEqual(status, 200)
        self.assertEqual(events["events"][0]["event_id"], "imev-bridge")

        status, acked = service.handle_api("POST", "/api/im/events/ack", b'{"event_id":"imev-bridge"}', {})
        self.assertEqual(status, 200)
        self.assertTrue(acked["ok"])

        self.assertEqual(provider.calls, ["ensure", "ensure", "ensure", "ensure"])
        self.assertEqual(
            session.calls,
            [
                (
                    "send_message",
                    {
                        "external_session": provider.external_session,
                        "target_identity_id": "act-market-demo",
                        "content": "ping",
                        "reply_to": None,
                    },
                ),
                ("read_events", {"external_session": provider.external_session, "limit": 5, "wait_ms": 10}),
                ("ack_event", {"external_session": provider.external_session, "event_id": "imev-bridge"}),
            ],
        )

    def test_web_management_does_not_expose_retired_web_im_route_family(self) -> None:
        service = web_management.WebManagementService(repo_root=ROOT)
        retired_prefix = "/api/web/" + "im"

        for method, path, body in (
            ("GET", retired_prefix + "/session", b""),
            ("POST", retired_prefix + "/messages", b"{}"),
            ("GET", retired_prefix + "/events?identity_id=act-market-demo&wait_ms=0", b""),
            ("GET", retired_prefix + "/conversations/direct?identity_id=act-market-demo&limit=20", b""),
        ):
            with self.subTest(path=path):
                with self.assertRaises(web_management.HttpError) as raised:
                    service.handle_api(method, path, body, {})
                self.assertEqual(raised.exception.status, 404)

    def test_web_management_removes_old_message_send_route(self) -> None:
        service = web_management.WebManagementService(repo_root=ROOT)

        with self.assertRaises(web_management.HttpError) as raised:
            old_route = "/api/messages" + "/send"
            service.handle_api("POST", old_route, b'{"actor_id":"act-dev-demo","content":"hello"}')
        self.assertEqual(raised.exception.status, 404)

    def test_web_management_no_longer_imports_fake_web_user_actor(self) -> None:
        source = (ROOT / "tools" / "launcher" / "web_management.py").read_text(encoding="utf-8")

        self.assertNotIn("import web_user_actor", source)
        self.assertNotIn("WebUser" + "ActorRuntime", source)
        self.assertNotIn("send_web_user_message", source)

    def test_http_and_web_projections_do_not_own_external_im_session_semantics(self) -> None:
        surfaces = (
            ROOT / "tools" / "launcher" / "im_http_router.py",
            ROOT / "tools" / "launcher" / "web_management.py",
            ROOT / "tools" / "launcher" / "web_im_identity.py",
        )
        forbidden_fragments = (
            "from env.services import messages",
            "import messages as message_service",
            "message_service." + "create_external_session",
            "message_service." + "authenticate_external_session_key",
            "message_service." + "send_external_session_message",
            "message_service." + "read_external_session_events",
            "message_service." + "get_im_direct_conversation",
            "message_service." + "get_im_message",
            "message_service." + "list_im_replies",
            "message_service." + "update_im_disposition",
            "self._im_session." + "send_message",
            "self._im_session." + "read_events",
            "self._im_session." + "get_message",
            "self._im_session." + "ack_event",
            "self._im_session." + "get_direct_conversation",
        )

        for surface in surfaces:
            source = surface.read_text(encoding="utf-8")
            for forbidden in forbidden_fragments:
                with self.subTest(surface=surface.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)

    def test_live_surfaces_do_not_describe_retired_im_architecture(self) -> None:
        surfaces = (
            ROOT / "tools" / "launcher" / "im_http_router.py",
            ROOT / "tools" / "launcher" / "web_management.py",
            ROOT / "tools" / "launcher" / "web_im_identity.py",
            ROOT / "tools" / "launcher" / "assets" / "web-management" / "app.js",
            ROOT / "tests" / "test_im_http_router.py",
            ROOT / "tests" / "test_web_management.py",
            ROOT / "tests" / "test_im_web_management_projection.py",
            ROOT / "tests" / "web_management_ui_contract.test.js",
            ROOT / "docs" / "arch" / "web-interface-call-architecture.md",
        )
        forbidden_fragments = (
            "two IM product " + "implementations",
            "separate IM " + "product",
            "Web IM routes should delegate to the " + "message service",
            "i" + "Message" + " Central IM Core",
            "Central IM" + " i" + "Message",
            "channel " + "plugin",
            "plugin " + "framework",
            "external-" + "participants",
            "/api/messages/" + "send",
        )
        negative_assertion_markers = ("assertExcludes", "assertNotIn", "old_route")

        for surface in surfaces:
            for line_number, line in enumerate(surface.read_text(encoding="utf-8").splitlines(), start=1):
                for forbidden in forbidden_fragments:
                    if forbidden not in line:
                        continue
                    if any(marker in line for marker in negative_assertion_markers):
                        continue
                    self.fail(f"{surface}:{line_number} contains retired IM architecture wording: {forbidden}")

    def test_live_surfaces_have_no_retired_web_im_route_or_helper_residue(self) -> None:
        surfaces = (
            ROOT / "tools" / "launcher" / "web_management.py",
            ROOT / "tools" / "launcher" / "im_http_router.py",
            ROOT / "tools" / "launcher" / "external_im_session.py",
            ROOT / "tools" / "launcher" / "web_im_identity.py",
            ROOT / "tools" / "launcher" / "assets" / "web-management" / "app.js",
            ROOT / "tests" / "test_web_management.py",
            ROOT / "tests" / "test_im_http_router.py",
            ROOT / "tests" / "test_im_web_management_projection.py",
            ROOT / "tests" / "test_external_im_projection_contract.py",
            ROOT / "tests" / "web_management_ui_contract.test.js",
            ROOT / "tests" / "web_management_ui_state.test.js",
            ROOT / "docs" / "arch" / "web-interface-call-architecture.md",
        )
        forbidden_fragments = (
            "/api/web/" + "im",
            "_handle_" + "web_im",
            "_web_im_" + "send_message",
            "_web_im_" + "events",
            "_web_im_" + "direct_conversation",
            "_im_event_" + "targets_identity",
            "assertExcludes(appJs, " + "'/api/im')",
        )

        for surface in surfaces:
            source = surface.read_text(encoding="utf-8")
            for forbidden in forbidden_fragments:
                with self.subTest(surface=surface.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
