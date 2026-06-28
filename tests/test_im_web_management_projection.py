#!/usr/bin/env python3
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

    def create_connection(self, *, display_name: str) -> dict[str, object]:
        self.calls.append(("create_connection", {"display_name": display_name}))
        return {"ok": True, "connection_key": "imck-bridge"}

    def authenticate(self, connection_key: str) -> dict[str, object]:
        self.calls.append(("authenticate", {"connection_key": connection_key}))
        return {"ok": True, "connection": {"identity_id": "ext-bridge"}}

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


class ImWebManagementProjectionTests(unittest.TestCase):
    def test_web_management_exposes_external_im_routes_for_bridge(self) -> None:
        session = _FakeExternalImSession()
        service = web_management.WebManagementService(repo_root=ROOT, im_session=session)  # type: ignore[arg-type]

        status, created = service.handle_api("POST", "/api/im/connections", b'{"display_name":"Bridge"}', {})
        self.assertEqual(status, 200)
        self.assertEqual(created["connection_key"], "imck-bridge")

        status, actors = service.handle_api(
            "GET",
            "/api/im/actors?role_id=market",
            b"",
            {"Authorization": "Bearer imck-bridge"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(actors["count"], 1)
        self.assertEqual(actors["actors"][0]["identity_id"], "act-market-demo")

        self.assertEqual(
            session.calls,
            [
                ("create_connection", {"display_name": "Bridge"}),
                ("authenticate", {"connection_key": "imck-bridge"}),
                ("list_actors", {"role_id": "market"}),
            ],
        )

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
            "message_service." + "create_external_connection",
            "message_service." + "authenticate_external_connection_key",
            "message_service." + "send_external_connection_message",
            "message_service." + "read_external_connection_events",
            "message_service." + "get_im_direct_conversation",
            "message_service." + "get_im_message",
            "message_service." + "list_im_replies",
            "message_service." + "update_im_disposition",
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


if __name__ == "__main__":
    unittest.main()
