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


class ImWebManagementProjectionTests(unittest.TestCase):
    def test_web_management_does_not_expose_lower_im_routes(self) -> None:
        service = web_management.WebManagementService(repo_root=ROOT)

        for method, path in (
            ("POST", "/api/im/external-participants"),
            ("POST", "/api/im/messages"),
            ("GET", "/api/im/events?cursor=imev-000000000000&wait_ms=0"),
            ("GET", "/api/im/conversations/direct?kind=actor&role_id=dev&actor_id=act-dev-demo"),
        ):
            with self.subTest(path=path):
                with self.assertRaises(web_management.HttpError) as raised:
                    service.handle_api(method, path, b"{}", {})
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


if __name__ == "__main__":
    unittest.main()
