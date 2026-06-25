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


class _RouterStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes, object]] = []

    def handle(self, method: str, path: str, body: bytes, headers: object) -> tuple[int, dict[str, object]]:
        self.calls.append((method, path, body, headers))
        return 200, {"ok": True, "route": path}


class ImWebManagementProjectionTests(unittest.TestCase):
    def test_web_management_delegates_im_routes_and_removes_old_message_send_route(self) -> None:
        router = _RouterStub()
        service = web_management.WebManagementService(repo_root=ROOT, im_router=router)

        status, payload = service.handle_api("POST", "/api/im/external-participants", b"{}", {})

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True, "route": "/api/im/external-participants"})
        self.assertEqual(router.calls[0][0:3], ("POST", "/api/im/external-participants", b"{}"))
        with self.assertRaises(web_management.HttpError) as raised:
            old_route = "/api/messages" + "/send"
            service.handle_api("POST", old_route, b'{"actor_id":"act-dev-demo","content":"hello"}')
        self.assertEqual(raised.exception.status, 404)

    def test_web_management_no_longer_imports_fake_web_user_actor(self) -> None:
        source = (ROOT / "tools" / "launcher" / "web_management.py").read_text(encoding="utf-8")

        self.assertNotIn("import web_user_actor", source)
        self.assertNotIn("WebUser" + "ActorRuntime", source)
        self.assertNotIn("send_web_user_message", source)


if __name__ == "__main__":
    unittest.main()
