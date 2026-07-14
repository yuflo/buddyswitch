from tests.integration.browser.cockpit_proxy_harness import *  # noqa: F401,F403


class TestCockpitProxyLifecycle(BrowserCockpitProxyHarness):
    def test_opened_page_then_list_pages_does_not_schedule_empty_release(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})
        search_url = "https://www.google.com/search?q=BuddySwitch+open+current+projection"

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [
                    self._single_call("search_page", {"query": "BuddySwitch open current projection", "engine": "google"}),
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_pages", "arguments": {}}},
                ],
                browser_url=browser_url,
                instance_root=instance_root,
                extra_env={
                    "BUDDYSWITCH_TEST_PROXY_NEW_PAGE_TEXT": (
                        "## Pages\n"
                        "1: about:blank\n"
                        f"2: {search_url} [selected]"
                    )
                },
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual([call["params"]["name"] for call in forwarded], ["new_page", "list_pages"])
            self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
            self.assertFalse(responses[1]["result"].get("isError", False), msg=responses[1])
            text = "\n".join(item["text"] for item in responses[1]["result"]["content"] if item.get("type") == "text")
            self.assertIn("current_page_id: 2", text)
            self.assertIn("selected_page_id: 2", text)
            self.assertIn("page_id: 2", text)
            self.assertIn("current: true", text)
            self.assertIn("selected: true", text)
            self.assertIn("idle_tracked: true", text)
            saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            release_schedules = [
                item
                for item in saved["scheduled_triggers"].values()
                if item["type"] == "browser.cockpit.release" and item.get("payload") == {"reason": "page_idle_empty"}
            ]
            self.assertEqual(release_schedules, [])
            self.assertFalse(thread.is_alive())
    def test_list_pages_projects_page_id_resource_state(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(
                instance_root,
                {
                    "current_page_id": "page-current",
                    "selected_page_id": "page-current",
                    "current_page_updated_at": "2026-07-01T00:00:00Z",
                    "pages": {
                        "page-current": {
                            "page_id": "page-current",
                            "url": "https://example.com/current",
                            "title": "Current Title",
                            "last_used_at": "2026-07-01T00:00:00Z",
                        }
                    },
                },
            )

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
            )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
        text = "\n".join(item["text"] for item in responses[0]["result"]["content"] if item.get("type") == "text")
        self.assertIn("called list_pages", text)
        self.assertIn("BuddySwitch browser page resource projection:", text)
        self.assertIn("current_page_id: page-current", text)
        self.assertIn("selected_page_id: page-current", text)
        self.assertIn("page_id: page-current", text)
        self.assertIn("title: Current Title", text)
        self.assertIn("url: https://example.com/current", text)
        self.assertIn("current: true", text)
        self.assertIn("idle_expires_at: 2026-07-01T00:00:40Z", text)
        self.assertNotIn(LEGACY_CURRENT_TARGET_FIELD, text)
        self.assertNotIn("target_id:", text)
        self.assertNotIn("Browser lifecycle warning:", text)
    def test_list_pages_with_no_tracked_pages_schedules_release(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(len(forwarded), 1)
            self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
            self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
            saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            release_schedules = [
                item
                for item in saved["scheduled_triggers"].values()
                if item["type"] == "browser.cockpit.release"
            ]
            self.assertEqual(len(release_schedules), 1)
            self.assertEqual(release_schedules[0]["payload"], {"reason": "page_idle_empty"})
            self.assertEqual(release_schedules[0]["schedule_key"], "browser.cockpit.release")
    def test_upstream_exit_does_not_stop_proxy_and_next_call_restarts(self) -> None:
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_pages", "arguments": {}},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "close_page", "arguments": {"pageId": 1}},
            },
        ]

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            messages,
            extra_env={"BUDDYSWITCH_TEST_PROXY_EXIT_AFTER_RESPONSE": "1"},
            message_delay_seconds=0.2,
        )

        self.assertEqual([response.get("id") for response in responses], [1, 2])
        self.assertEqual(
            [item["params"]["name"] for item in forwarded if item.get("method") == "tools/call"],
            ["list_pages", "close_page"],
        )
    def test_upstream_exit_during_request_returns_error_and_next_call_restarts(self) -> None:
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_pages", "arguments": {}},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "close_page", "arguments": {"pageId": 1}},
            },
        ]

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            messages,
            exit_without_response_once=True,
            message_delay_seconds=0.2,
        )

        self.assertEqual([response.get("id") for response in responses], [1, 2])
        self.assertTrue(responses[0]["result"].get("isError"), msg=responses[0])
        self.assertIn("exited", responses[0]["result"]["content"][0]["text"])
        self.assertFalse(responses[1]["result"].get("isError"), msg=responses[1])
        self.assertEqual(
            [item["params"]["name"] for item in forwarded if item.get("method") == "tools/call"],
            ["list_pages", "close_page"],
        )
