"""Response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sys
import threading
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

from tests.support.paths import REPO_ROOT
from tests.support.fake_cdp import (
    read_client_text_frame as _read_client_text_frame,
    websocket_accept_value as _websocket_accept_value,
    write_server_text_frame as _write_server_text_frame,
)

ROOT = REPO_ROOT

import buddyswitch.runtime_kernel.broker as runtime_broker  # noqa: E402
from buddyswitch.env.domain import task_sys  # noqa: E402
from buddyswitch.env.repos import messages as message_repo  # noqa: E402
from buddyswitch.env.services import messages as message_service  # noqa: E402
from buddyswitch.env.tool_runtime import registry as tool_catalog  # noqa: E402
from buddyswitch.env.tool_runtime import results as tool_results  # noqa: E402
from buddyswitch.env.tool_runtime import context as runtime_context  # noqa: E402
import buddyswitch.env.tools.search._impl as search_impl  # noqa: E402
from buddyswitch.runtime_support import turn_runtime  # noqa: E402
from tests.integration.env_tool._response_case import EnvToolResponseCase, _make_cdp_handler

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"
PROTOCOL = "buddyswitch-runtime-broker/v2"


class EnvToolSearchResponseTests(EnvToolResponseCase):
    def test_search_open_browser_removed_action_returns_standard_rejection(self) -> None:
        actor_id = "act-dev-search-open-removed-contract"
        dev_instance = self._instance_json(role="dev", actor_id=f"{actor_id}-dev")
        dev_payload = json.loads(dev_instance.read_text(encoding="utf-8"))
        dev_payload["browser_port"] = 9222
        dev_instance.write_text(json.dumps(dev_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

        response = self._dispatch(
            instance_json=dev_instance,
            actor_id=f"{actor_id}-dev",
            role="dev",
            tool="search",
            action="open_browser",
            args={"query": "BuddySwitch", "engine": "google"},
        )

        self._assert_rejection_contract(response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_ENV_TOOL", msg=response)
        self.assertEqual(response.get("permission_boundary"), "env.tool", msg=response)
        response_text = json.dumps(response, ensure_ascii=True)
        self.assertIn("unsupported env.tool payload.action for search: open_browser", response_text)
        self.assertNotIn("browser.open_url", response_text)
        self.assertNotIn("browser_endpoint", response_text)
        self.assertNotIn("browser_url", response_text)
