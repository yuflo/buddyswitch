"""Response contract tests for broker-routed env.tool actions."""

from __future__ import annotations

import json

from tests.integration.env_tool._response_case import EnvToolResponseCase


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
