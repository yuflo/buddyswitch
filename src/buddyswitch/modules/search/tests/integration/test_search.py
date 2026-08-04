"""Tests for broker-routed search env tool behavior."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT

from buddyswitch.runtime_support import env_manifest  # noqa: E402
import buddyswitch.modules.search.private.adapters.tool._impl as search_impl  # noqa: E402
from buddyswitch.foundation.tool_runtime.registry import dispatch_env_tool_request  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402

MANIFEST = ROOT / "src" / "buddyswitch" / "catalog" / "manifest.toml"


class SearchEnvToolTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()

    def _instance_json(
        self,
        *,
        actor_id: str = "act-search-example",
        role: str = "market",
        browser_port: object = 9222,
    ) -> Path:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        instance_json = self._runtime_path(f"{actor_id}.json")
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": actor_id,
                    "role": role,
                    "status": "active",
                    "current_task_id": None,
                    "current_track_id": None,
                    "workspace_dir": str(self.runtime_root),
                    "browser_port": browser_port,
                    "created_at": "2026-05-13T00:00:00Z",
                    "updated_at": "2026-05-13T00:00:00Z",
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._seed_active_task_for_instance(
            instance_json=instance_json,
            role=role,
            actor_id=actor_id,
            task_slug=f"{role}-search-env",
        )
        return instance_json

    def _dispatch(
        self,
        *,
        action: str,
        args: dict[str, object],
        instance_json: Path,
        actor_id: str = "act-search-example",
        role: str = "market",
    ) -> dict[str, object]:
        actor_id = self._runtime_actor_id(role=role, label=actor_id)
        manifest = env_manifest.load_manifest(MANIFEST)
        instance_payload = json.loads(instance_json.read_text(encoding="utf-8"))
        return dispatch_env_tool_request(
            payload={"tool": "search", "action": action, "args": args},
            active_role=role,
            actor_id=actor_id,
            instance_json=instance_json,
            instance_payload=instance_payload,
            manifest=manifest,
            manifest_path=MANIFEST,
        )

    def _start_cdp_server(self, state: dict[str, object]) -> tuple[HTTPServer, threading.Thread, int]:
        server = HTTPServer(("127.0.0.1", 0), _make_cdp_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return server, thread, int(server.server_port)

    def _assert_no_env_cli_hint(self, response: dict[str, object]) -> None:
        self.assertNotIn("command_hint", response, msg=response)
        self.assertNotIn("scripts/env/client.py", json.dumps(response, ensure_ascii=True), msg=response)

    def _assert_next_option(self, response: dict[str, object], *, tool: str, action: str) -> None:
        options = response.get("allowed_next_action_options")
        self.assertIsInstance(options, list, msg=response)
        assert isinstance(options, list)
        expected_native = f"{tool}__{action}"
        for option in options:
            if not isinstance(option, dict):
                continue
            if option.get("tool") == tool and option.get("action") == action:
                self.assertEqual(option.get("native_tool"), expected_native, msg=option)
                self.assertIsInstance(option.get("reason"), str, msg=option)
                return
        self.fail(f"missing next action option {expected_native}: {response}")

    def _assert_no_next_option(self, response: dict[str, object], *, tool: str, action: str) -> None:
        options = response.get("allowed_next_action_options")
        if options is None:
            return
        self.assertIsInstance(options, list, msg=response)
        assert isinstance(options, list)
        for option in options:
            if isinstance(option, dict) and option.get("tool") == tool and option.get("action") == action:
                self.fail(f"unexpected next action option {tool}.{action}: {response}")

    def _assert_cockpit_search_page_guidance(self, response: dict[str, object]) -> None:
        dumped = json.dumps(response, ensure_ascii=True)
        self.assertIn("chrome-devtools-cockpit.search_page", dumped, msg=response)
        self.assertNotIn("search.open_browser", dumped, msg=response)
        self.assertNotIn("search__open_browser", dumped, msg=response)
        self._assert_no_next_option(response, tool="search", action="open_browser")

    def _assert_no_browser_endpoint_leak(self, response: dict[str, object]) -> None:
        dumped = json.dumps(response, ensure_ascii=True)
        self.assertNotIn("browser_endpoint", dumped, msg=response)
        self.assertNotIn("browser_url", dumped, msg=response)



    def test_search_status_reports_market_profile_backend_and_cockpit_search_boundary(self) -> None:
        instance_json = self._instance_json(role="market", browser_port=9222)

        response = self._dispatch(action="status", args={}, instance_json=instance_json, role="market")

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("tool"), "search")
        self.assertEqual(response.get("action"), "search.status")
        self.assertEqual(response.get("active_role"), "market")
        self.assertEqual(response.get("native_codex_web_search"), "disabled")
        self.assertEqual(response.get("available_backends"), ["browser"])
        backend_status = response.get("backend_status")
        self.assertIsInstance(backend_status, dict, msg=response)
        assert isinstance(backend_status, dict)
        self.assertEqual(backend_status["browser"]["available"], True)
        self.assertNotIn("browser_url", backend_status["browser"])
        self.assertEqual(backend_status["search_api"]["available"], False)
        self.assertEqual(backend_status["search_api"]["permission"], "user-approved-only")
        self.assertEqual(
            response.get("capability_boundary"),
            {
                "native_codex_web_search": "disabled",
                "browser_cockpit": "required",
                "search_api": "user-approved-only",
            },
        )
        self.assertIn("permission_boundary", response)
        self.assertIn("allowed_next_actions", response)
        self._assert_no_env_cli_hint(response)
        self._assert_cockpit_search_page_guidance(response)
        self.assertNotIn("preferred_backend", response)
        self.assertNotIn("market_workflow", response)

    def test_search_status_reports_non_market_boundary_without_market_workflow_default(self) -> None:
        instance_json = self._instance_json(role="dev", browser_port=9222)

        response = self._dispatch(action="status", args={}, instance_json=instance_json, role="dev")

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("capability_boundary", {}).get("browser_cockpit"), "available")
        self.assertEqual(response.get("capability_boundary", {}).get("search_api"), "available")
        for forbidden in ("market_workflow", "browser_native_required_by_market", "preferred_backend"):
            self.assertNotIn(forbidden, response)

    def test_search_request_browser_returns_actionable_instruction_without_opening_page(self) -> None:
        instance_json = self._instance_json(role="market", browser_port=9222)

        response = self._dispatch(
            action="request",
            args={"query": "creator analytics pain", "backend": "browser", "engine": "reddit"},
            instance_json=instance_json,
            role="market",
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("backend"), "browser")
        self.assertEqual(response.get("engine"), "reddit")
        self.assertEqual(response.get("query"), "creator analytics pain")
        self.assertEqual(response.get("target_url"), "https://www.reddit.com/search/?q=creator+analytics+pain")
        self._assert_no_browser_endpoint_leak(response)
        self.assertEqual(response.get("required_cockpit_tool"), "chrome-devtools-cockpit")
        self.assertEqual(response.get("page_opened"), False)
        self.assertNotIn("tool_evidence", response)
        self._assert_cockpit_search_page_guidance(response)
        self._assert_no_env_cli_hint(response)

    def test_search_request_next_action_option_does_not_echo_raw_query(self) -> None:
        instance_json = self._instance_json(browser_port=9222)
        query = "creator' && echo pwned"
        response = self._dispatch(
            action="request",
            args={"query": query, "backend": "browser", "engine": "google"},
            instance_json=instance_json,
        )
        self.assertTrue(response.get("ok"), msg=response)
        self._assert_no_env_cli_hint(response)
        self._assert_cockpit_search_page_guidance(response)
        options_text = json.dumps(response.get("allowed_next_action_options"), ensure_ascii=True)
        self.assertNotIn(query, options_text)
        self.assertNotIn("&&", options_text)

    def test_search_open_browser_action_is_removed(self) -> None:
        instance_json = self._instance_json(role="market", browser_port=9222)

        response = self._dispatch(
            action="open_browser",
            args={"query": "creator analytics pain", "engine": "google"},
            instance_json=instance_json,
            role="market",
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_ENV_TOOL", msg=response)
        self.assertEqual(response.get("permission_boundary"), "env.tool")
        response_text = json.dumps(response, ensure_ascii=True)
        self.assertIn("unsupported env.tool payload.action for search: open_browser", response_text)
        self.assertFalse(response.get("state_changed", False), msg=response)
        self.assertNotIn("browser.open_url", response_text, msg=response)

    def test_search_request_browser_builds_expected_url_for_supported_engines(self) -> None:
        instance_json = self._instance_json(browser_port=9222)
        expected = {
            "google": "https://www.google.com/search?q=creator+analytics+pain",
            "web": "https://www.google.com/search?q=creator+analytics+pain",
            "reddit": "https://www.reddit.com/search/?q=creator+analytics+pain",
            "x": "https://x.com/search?q=creator+analytics+pain&src=typed_query",
        }

        for engine, target_url in expected.items():
            with self.subTest(engine=engine):
                response = self._dispatch(
                    action="request",
                    args={"query": "creator analytics pain", "backend": "browser", "engine": engine},
                    instance_json=instance_json,
                )
                self.assertTrue(response.get("ok"), msg=response)
                self.assertEqual(response.get("target_url"), target_url)

    def test_search_request_rejects_missing_or_unknown_backend(self) -> None:
        instance_json = self._instance_json()
        for args in ({"query": "x"}, {"query": "x", "backend": "auto"}):
            with self.subTest(args=args):
                response = self._dispatch(action="request", args=args, instance_json=instance_json)
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BACKEND")
                self.assertEqual(response.get("allowed_backends"), ["browser", "search_api"])
                self.assertIn("permission_boundary", response)
                self.assertIn("allowed_next_actions", response)
                self._assert_no_env_cli_hint(response)
                self._assert_next_option(response, tool="search", action="status")

    def test_search_request_rejects_empty_null_and_non_string_backend(self) -> None:
        instance_json = self._instance_json()
        for backend in ("", None, []):
            with self.subTest(backend=backend):
                response = self._dispatch(
                    action="request",
                    args={"query": "x", "backend": backend},
                    instance_json=instance_json,
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BACKEND")

    def test_search_request_search_api_returns_market_approval_required(self) -> None:
        instance_json = self._instance_json(role="market")

        response = self._dispatch(
            action="request",
            args={"query": "creator analytics pain", "backend": "search_api", "engine": "web"},
            instance_json=instance_json,
            role="market",
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BACKEND_APPROVAL_REQUIRED")
        self.assertEqual(response.get("permission_boundary"), "search.search_api.user_approved_only")
        self._assert_no_env_cli_hint(response)
        self._assert_cockpit_search_page_guidance(response)

    def test_search_request_search_api_returns_non_market_provider_unavailable(self) -> None:
        instance_json = self._instance_json(role="dev")

        response = self._dispatch(
            action="request",
            args={"query": "release notes", "backend": "search_api", "engine": "web"},
            instance_json=instance_json,
            role="dev",
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_BACKEND_UNAVAILABLE")
        self.assertIn("No BuddySwitch-managed search API provider is configured", response.get("reason", ""))
        self._assert_no_env_cli_hint(response)
        self._assert_cockpit_search_page_guidance(response)

    def test_search_source_has_no_direct_json_new_page_open(self) -> None:
        source_path = (
            ROOT
            / "src"
            / Path(*search_impl.__name__.split(".")).with_suffix(".py")
        )
        text = source_path.read_text(encoding="utf-8")
        self.assertNotIn("/json/new", text)
        self.assertNotIn('"tools"', text)
        self.assertNotIn('"launcher"', text)
        self.assertNotIn('request_runtime_broker("browser.open_url"', text)
        self.assertNotIn("browser_client.open_url", text)
        self.assertNotIn("def open_browser_for_active_instance", text)
        self.assertNotIn("'open_browser': open_browser_for_active_instance", text)
        self.assertNotIn("tools" + "/launcher", text)
        self.assertNotIn("scripts/env/client.py", text)
        self.assertNotIn("cdp_background_page.py", text)
        self.assertNotIn("Target." + "createTarget", text)
        self.assertFalse((ROOT / "src" / "buddyswitch" / "launcher" / "cdp_background_page.py").exists())

    def test_search_rejects_empty_query_and_unknown_engine(self) -> None:
        instance_json = self._instance_json()
        bad_query_cases = ("", "   ", [])
        for query in bad_query_cases:
            with self.subTest(query=query):
                response = self._dispatch(
                    action="request",
                    args={"query": query, "backend": "browser", "engine": "google"},
                    instance_json=instance_json,
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_QUERY")
                self._assert_no_env_cli_hint(response)
                self._assert_next_option(response, tool="search", action="status")

        for engine in ("", "bing"):
            with self.subTest(engine=engine):
                response = self._dispatch(
                    action="request",
                    args={"query": "x", "backend": "browser", "engine": engine},
                    instance_json=instance_json,
                )
                self.assertFalse(response.get("ok"), msg=response)
                self.assertEqual(response.get("error", {}).get("code"), "E_SEARCH_ENGINE")
                self.assertEqual(response.get("allowed_engines"), ["google", "web", "reddit", "x"])
                self._assert_no_env_cli_hint(response)
                self._assert_next_option(response, tool="search", action="status")

    def test_browser_and_search_dependency_rejections_include_semantic_impact(self) -> None:
        self.test_search_request_search_api_returns_market_approval_required()
        self.test_search_request_search_api_returns_non_market_provider_unavailable()
