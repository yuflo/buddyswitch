from __future__ import annotations

import json
from urllib.request import ProxyHandler, build_opener

from tests.support.fake_cdp import FakeCdpServer


def test_parent_cdp_server_owns_a_port_zero_listener() -> None:
    server = FakeCdpServer().start()
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(
            f"http://127.0.0.1:{server.port}/json/version",
            timeout=1.0,
        ) as response:
            assert json.loads(response.read())["Browser"] == "fake"
    finally:
        server.close()
