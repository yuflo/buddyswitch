from tests.integration.browser.cockpit_proxy_harness import *  # noqa: F401,F403


class TestCockpitProxyOpenSearch(BrowserCockpitProxyHarness):
    def test_tools_list_includes_buddyswitch_search_page(self) -> None:
        responses, _forwarded, _upstream_argv, _stderr = self._run_proxy(
            [{"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}]
        )

        tools = responses[0]["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        self.assertIn("search_page", by_name)
        search_page = by_name["search_page"]
        self.assertIn("BuddySwitch", search_page.get("description", ""))
        self.assertIn("upstream Chrome DevTools MCP new_page", search_page.get("description", ""))
        schema = search_page.get("inputSchema")
        self.assertIsInstance(schema, dict, msg=search_page)
        assert isinstance(schema, dict)
        self.assertEqual(schema.get("required"), ["query"])
        properties = schema.get("properties")
        self.assertIsInstance(properties, dict, msg=schema)
        assert isinstance(properties, dict)
        self.assertIn("query", properties)
        self.assertEqual(properties.get("engine", {}).get("enum"), ["google", "web", "reddit", "x"])
    def test_new_page_forwards_upstream_with_background_true(self) -> None:
        cdp_state: dict[str, object] = {
            "requests": [],
            "targets": _page_targets(1),
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
            )

        self.assertEqual(len(forwarded), 1)
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertIn("--experimental-interop-tools", upstream_argv)
        self.assertIn("--experimental-structured-content", upstream_argv)
        forwarded_call = forwarded[0]
        self.assertEqual(forwarded_call["params"]["name"], "new_page")
        self.assertEqual(
            forwarded_call["params"]["arguments"],
            {"url": "https://example.com/new", "background": True},
        )
        response = responses[0]
        self.assertFalse(response["result"].get("isError", False), msg=response)
        self.assertIn("called new_page", response["result"]["content"][0]["text"])
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_success_tracks_opened_stable_target(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
                extra_env={
                    "BUDDYSWITCH_TEST_PROXY_NEW_PAGE_TEXT": (
                        "## Pages\n"
                        "1: about:blank\n"
                        "2: https://example.com/new [selected]"
                    )
                },
            )
            server.close()
            thread.join(timeout=2)

            self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
            self.assertEqual(forwarded[0]["params"]["name"], "new_page")
            self.assertEqual(
                forwarded[0]["params"]["arguments"],
                {"url": "https://example.com/new", "background": True},
            )
            saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:stable-tab-2")
            self.assertEqual(schedule["payload"], {"tab_target_id": "stable-tab-2", "idle_seconds": 40})
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["active_tab_target_id"], "stable-tab-2")
            self.assertEqual(page_idle["targets"]["stable-tab-2"]["url"], "https://example.com/new")
            self.assertNotIn("pages", page_idle)
            self.assertEqual(cdp_state.get("rpc_requests", [])[0]["method"], "Target.getTargets")
            self.assertFalse(thread.is_alive())
    def test_search_page_success_tracks_opened_stable_target(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)
        search_url = "https://www.google.com/search?q=BuddySwitch+open+current+projection"

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("search_page", {"query": "BuddySwitch open current projection", "engine": "google"})],
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

            self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
            self.assertEqual(forwarded[0]["params"]["name"], "new_page")
            self.assertEqual(forwarded[0]["params"]["arguments"], {"url": search_url, "background": True})
            saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:stable-tab-2")
            self.assertEqual(schedule["payload"], {"tab_target_id": "stable-tab-2", "idle_seconds": 40})
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["active_tab_target_id"], "stable-tab-2")
            self.assertEqual(page_idle["targets"]["stable-tab-2"]["url"], search_url)
            self.assertFalse(thread.is_alive())
    def test_failed_new_page_closes_new_cdp_page_target_and_reports_cleanup(self) -> None:
        existing_targets = _page_targets(1)
        new_target = {"id": "target-new", "type": "page", "url": "https://example.com/failed-open"}
        cdp_state: dict[str, object] = {
            "requests": [],
            "list_payloads": [existing_targets, [*existing_targets, new_target]],
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/failed-open", "forceError": True})],
                browser_url=browser_url,
                instance_root=instance_root,
            )

            self.assertEqual(forwarded[0]["params"]["name"], "new_page")
            self.assertTrue(responses[0]["result"].get("isError"), msg=responses[0])
            response_text = json.dumps(responses[0], ensure_ascii=True)
            self.assertIn("failed new_page", response_text)
            self.assertIn("Browser cleanup", response_text)
            self.assertIn("closed it before returning", response_text)
            self.assertFalse((instance_root / "runtime" / "browser" / "page_idle.json").exists())

        self.assertEqual(
            cdp_state.get("rpc_requests"),
            [
                {"id": 1, "method": "Target.getTargets", "params": {}},
                {"id": 1, "method": "Target.getTargets", "params": {}},
                {"id": 1, "method": "Target.closeTarget", "params": {"targetId": "target-new"}},
            ],
        )
    def test_failed_search_page_closes_new_cdp_page_target_and_reports_cleanup(self) -> None:
        existing_targets = _page_targets(1)
        search_url = "https://www.google.com/search?q=BuddySwitch+failed+open"
        new_target = {"id": "target-search-new", "type": "page", "url": search_url}
        cdp_state: dict[str, object] = {
            "requests": [],
            "list_payloads": [existing_targets, [*existing_targets, new_target]],
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("search_page", {"query": "BuddySwitch failed open", "engine": "google"})],
                browser_url=browser_url,
                instance_root=instance_root,
                extra_env={
                    "BUDDYSWITCH_TEST_PROXY_NEW_PAGE_ERROR_TEXT": "Navigation timeout of 10000 ms exceeded",
                },
            )

            self.assertEqual(forwarded[0]["params"]["name"], "new_page")
            self.assertEqual(forwarded[0]["params"]["arguments"], {"url": search_url, "background": True})
            self.assertTrue(responses[0]["result"].get("isError"), msg=responses[0])
            response_text = json.dumps(responses[0], ensure_ascii=True)
            self.assertIn("Navigation timeout", response_text)
            self.assertIn("Browser cleanup", response_text)
            self.assertIn("closed it before returning", response_text)
            self.assertFalse((instance_root / "runtime" / "browser" / "page_idle.json").exists())

        self.assertEqual(
            cdp_state.get("rpc_requests"),
            [
                {"id": 1, "method": "Target.getTargets", "params": {}},
                {"id": 1, "method": "Target.getTargets", "params": {}},
                {"id": 1, "method": "Target.closeTarget", "params": {"targetId": "target-search-new"}},
            ],
        )
    def test_new_page_without_selected_page_id_closes_new_target_and_reports_not_deliverable(self) -> None:
        existing_targets = _page_targets(1)
        new_target = {"id": "target-undeliverable", "type": "page", "url": "https://example.com/new"}
        cdp_state: dict[str, object] = {
            "requests": [],
            "list_payloads": [existing_targets, [*existing_targets, new_target]],
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
                extra_env={
                    "BUDDYSWITCH_TEST_PROXY_NEW_PAGE_TEXT": "Opened page without selected marker.",
                },
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded[0]["params"]["name"], "new_page")
            response_text = json.dumps(responses[0], ensure_ascii=True)
            self.assertIn("page id was not readable", response_text)
            self.assertIn("not deliverable", response_text)
            self.assertIn("Browser cleanup", response_text)
            self.assertIn("closed it before returning", response_text)
            self.assertFalse((instance_root / "runtime" / "browser" / "page_idle.json").exists())
            if daemon_state.daemon_state_file(instance_root).exists():
                saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
                page_expiry_schedules = [
                    item
                    for item in saved["scheduled_triggers"].values()
                    if item["type"] == "browser.page.expired"
                ]
                self.assertEqual(page_expiry_schedules, [])
            self.assertFalse(thread.is_alive())

        self.assertEqual(
            cdp_state.get("rpc_requests"),
            [
                {"id": 1, "method": "Target.getTargets", "params": {}},
                {"id": 1, "method": "Target.getTargets", "params": {}},
                {"id": 1, "method": "Target.closeTarget", "params": {"targetId": "target-undeliverable"}},
            ],
        )
    def test_failed_new_page_close_failure_schedules_precise_cleanup(self) -> None:
        existing_targets = _page_targets(1)
        new_target = {"id": "target-close-fails", "type": "page", "url": "https://example.com/failed-open"}
        cdp_state: dict[str, object] = {
            "requests": [],
            "list_payloads": [existing_targets, [*existing_targets, new_target]],
            "close_error": "close denied",
        }
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/failed-open", "forceError": True})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded[0]["params"]["name"], "new_page")
            self.assertTrue(responses[0]["result"].get("isError"), msg=responses[0])
            response_text = json.dumps(responses[0], ensure_ascii=True)
            self.assertIn("failed new_page", response_text)
            self.assertIn("Browser cleanup warning", response_text)
            self.assertIn("scheduled short cleanup", response_text)
            self.assertFalse((instance_root / "runtime" / "browser" / "page_idle.json").exists())
            saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            cleanup_schedules = [
                item
                for item in saved["scheduled_triggers"].values()
                if item["type"] == "browser.failed_open_page.cleanup"
            ]
            self.assertEqual(len(cleanup_schedules), 1, msg=saved["scheduled_triggers"])
            self.assertEqual(cleanup_schedules[0]["schedule_key"], "browser.failed_open_page.cleanup:target-close-fails")
            self.assertEqual(cleanup_schedules[0]["payload"]["target_id"], "target-close-fails")
            self.assertEqual(cleanup_schedules[0]["payload"]["url"], "https://example.com/failed-open")
            self.assertEqual(cleanup_schedules[0]["payload"]["attempts"], 1)
            self.assertEqual(cleanup_schedules[0]["payload"]["reason"], "failed_open_page")
            self.assertIsInstance(cleanup_schedules[0]["payload"].get("first_seen_at"), str)
            self.assertFalse(thread.is_alive())

        self.assertEqual(
            cdp_state.get("rpc_requests"),
            [
                {"id": 1, "method": "Target.getTargets", "params": {}},
                {"id": 1, "method": "Target.getTargets", "params": {}},
                {"id": 1, "method": "Target.closeTarget", "params": {"targetId": "target-close-fails"}},
            ],
        )
    def test_new_page_does_not_call_target_create_target(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/no-cdp", "background": False})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        self.assertIs(forwarded[0]["params"]["arguments"]["background"], True)
        self.assertNotIn("Target.createTarget", [item["method"] for item in cdp_state.get("rpc_requests", [])])
    def test_search_page_builds_url_and_forwards_upstream_new_page(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("search_page", {"query": "BuddySwitch browser resource lifecycle", "engine": "google"})],
                browser_url=browser_url,
                instance_root=instance_root,
            )

        self.assertEqual(len(forwarded), 1)
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        self.assertEqual(
            forwarded[0]["params"]["arguments"],
            {
                "url": "https://www.google.com/search?q=BuddySwitch+browser+resource+lifecycle",
                "background": True,
            },
        )
        self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_search_page_does_not_call_target_create_target(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("search_page", {"query": "BuddySwitch", "engine": "reddit"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        self.assertNotIn("Target.createTarget", [item["method"] for item in cdp_state.get("rpc_requests", [])])
    def test_search_page_rejects_blank_query_before_forwarding(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("search_page", {"query": "   ", "engine": "google"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(forwarded, [])
        self.assertEqual(upstream_argv, [])
        response = responses[0]
        self.assertTrue(response["result"].get("isError"), msg=response)
        self.assertIn("query", response["result"]["content"][0]["text"])
        self.assertEqual(cdp_state.get("requests"), [])
    def test_search_page_rejects_unsupported_engine_before_forwarding(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("search_page", {"query": "BuddySwitch", "engine": "unknown"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(forwarded, [])
        self.assertEqual(upstream_argv, [])
        response = responses[0]
        self.assertTrue(response["result"].get("isError"), msg=response)
        text = response["result"]["content"][0]["text"]
        self.assertIn("engine", text)
        self.assertIn("google", text)
        self.assertEqual(cdp_state.get("requests"), [])
    def test_search_page_builds_supported_engine_urls(self) -> None:
        expected_urls = {
            "google": "https://www.google.com/search?q=BuddySwitch+browser+resource+lifecycle",
            "web": "https://www.google.com/search?q=BuddySwitch+browser+resource+lifecycle",
            "reddit": "https://www.reddit.com/search/?q=BuddySwitch+browser+resource+lifecycle",
            "x": "https://x.com/search?q=BuddySwitch+browser+resource+lifecycle&src=typed_query",
        }
        for engine, expected_url in expected_urls.items():
            with self.subTest(engine=engine):
                cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
                browser_url = self._start_cdp_list_server(cdp_state)

                with tempfile.TemporaryDirectory() as temp_root:
                    instance_root = Path(temp_root) / "instances" / f"act-dev-browser-{engine}"
                    responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                        [
                            self._single_call(
                                "search_page",
                                {"query": "BuddySwitch browser resource lifecycle", "engine": engine},
                            )
                        ],
                        browser_url=browser_url,
                        instance_root=instance_root,
                    )

                    self.assertEqual(
                        forwarded[0]["params"]["arguments"],
                        {"url": expected_url, "background": True},
                    )
                    self.assertIn(f"--browser-url={browser_url}", upstream_argv)
                    self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
                    self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_blank_url_is_forwarded_to_upstream(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "   "})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(len(forwarded), 1)
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        self.assertEqual(forwarded[0]["params"]["arguments"], {"url": "   ", "background": True})
        response = responses[0]
        self.assertFalse(response["result"].get("isError", False), msg=response)
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_forwarding_does_not_append_local_page_hint(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(4)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
            )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        self.assertNotIn("Browser pages:", json.dumps(responses, ensure_ascii=True))
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_forwards_with_explicit_instance_root_without_env(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(1)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
                clear_instance_root_env=True,
            )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["arguments"], {"url": "https://example.com/new", "background": True})
        self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_without_instance_root_forwards_upstream(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": []}
        browser_url = self._start_cdp_list_server(cdp_state)

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com/new"})],
            browser_url=browser_url,
            clear_instance_root_env=True,
        )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        self.assertEqual(forwarded[0]["params"]["arguments"], {"url": "https://example.com/new", "background": True})
        response = responses[0]
        self.assertFalse(response["result"].get("isError", False), msg=response)
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_does_not_read_cdp_page_count_before_forwarding(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "list_fail": True}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        self.assertFalse(responses[0]["result"].get("isError", False), msg=responses[0])
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_with_high_cdp_page_count_still_forwards_upstream(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(4)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
            )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        self.assertNotIn(SOFT_PAGE_HINT_5, json.dumps(responses, ensure_ascii=True))
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_no_longer_blocks_from_local_cdp_hard_page_limit(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "targets": _page_targets(10)}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        response = responses[0]
        self.assertFalse(response["result"].get("isError", False), msg=response)
        self.assertNotIn(HARD_PAGE_BLOCK, response["result"]["content"][0]["text"])
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_does_not_reuse_exact_url_through_local_cdp_gate(self) -> None:
        target_url = "https://example.com/new"
        targets = _page_targets(9) + [{"id": "target-existing-page", "type": "page", "url": target_url}]
        cdp_state: dict[str, object] = {"requests": [], "targets": targets}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": target_url})],
                browser_url=browser_url,
                instance_root=instance_root,
            )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["arguments"], {"url": target_url, "background": True})
        response = responses[0]
        self.assertFalse(response["result"].get("isError", False), msg=response)
        text = response["result"]["content"][0]["text"]
        self.assertNotIn("state: reused", text)
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_forwards_when_local_cdp_page_count_is_unavailable(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "list_fail": True}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=Path(temp_root) / "instances" / "act-dev-browser",
            )

        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        response = responses[0]
        self.assertFalse(response["result"].get("isError", False), msg=response)
        self.assertNotIn("page-count", response["result"]["content"][0]["text"].lower())
        self._assert_only_cleanup_snapshot_reads(cdp_state)
    def test_new_page_isolated_context_is_rejected_without_forwarding(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com", "isolatedContext": "login"})]
        )

        self.assertEqual(forwarded, [])
        response = responses[0]
        self.assertEqual(response["id"], 1)
        result = response["result"]
        self.assertIs(result["isError"], True)
        self.assertIn("isolatedContext", result["content"][0]["text"])
        self.assertIn("non-activating", result["content"][0]["text"])
