from tests.integration.browser.cockpit_proxy_harness import *  # noqa: F401,F403


class TestCockpitProxyPageState(BrowserCockpitProxyHarness):
    def test_select_page_tracks_stable_chrome_target_not_mcp_page_id(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("select_page", {"pageId": "page-3", "bringToFront": True})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(responses[0]["id"], 1)
            self.assertEqual(forwarded[0]["params"]["arguments"]["bringToFront"], False)
            saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:stable-tab-page-3")
            self.assertEqual(
                schedule["payload"],
                {"tab_target_id": "stable-tab-page-3", "idle_seconds": 40},
            )
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["active_tab_target_id"], "stable-tab-page-3")
            self.assertEqual(
                page_idle["targets"]["stable-tab-page-3"]["url"],
                "https://example.com/selected",
            )
            self.assertNotIn("pages", page_idle)
            self.assertNotIn("current_page_id", page_idle)
            internal_names = [
                call.get("params", {}).get("name")
                for call in self._last_proxy_all_calls
                if str(call.get("id", "")).startswith("buddyswitch.internal.")
            ]
            self.assertEqual(internal_names, ["get_tab_id"])
            self.assertFalse(thread.is_alive())

    def test_select_page_identity_bridge_does_not_query_cdp_target_list(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "list_fail": True}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("select_page", {"pageId": "page-4", "bringToFront": True})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(responses[0]["id"], 1)
            self.assertEqual(forwarded[0]["params"]["arguments"]["bringToFront"], False)
            saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:stable-tab-page-4")
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["active_tab_target_id"], "stable-tab-page-4")
            self.assertEqual(cdp_state.get("requests"), [])

    def test_navigation_refreshes_the_same_stable_target_without_re_resolving_page_id(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [
                    self._single_call("select_page", {"pageId": 3}),
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "navigate_page",
                            "arguments": {"type": "url", "url": "https://example.com/after-navigation"},
                        },
                    },
                ],
                browser_url=browser_url,
                instance_root=instance_root,
                message_delay_seconds=0.2,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual([response["id"] for response in responses], [1, 2])
            self.assertEqual([call["params"]["name"] for call in forwarded], ["select_page", "navigate_page"])
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["active_tab_target_id"], "stable-tab-3")
            self.assertEqual(list(page_idle["targets"]), ["stable-tab-3"])
            internal_tab_lookups = [
                call
                for call in self._last_proxy_all_calls
                if call.get("params", {}).get("name") == "get_tab_id"
            ]
            self.assertEqual(len(internal_tab_lookups), 1)

    def test_select_page_without_page_id_reports_lifecycle_warning(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)

            responses, _forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("select_page", {"bringToFront": True})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertFalse(daemon_state.daemon_state_file(instance_root).exists())
            self.assertIn("lifecycle warning", json.dumps(responses, ensure_ascii=True).lower())
            self.assertFalse((instance_root / "runtime" / "browser" / "page_idle.json").exists())
    def test_first_page_scoped_call_bootstraps_actual_selected_target_before_forwarding(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("take_snapshot", {})],
                browser_url=browser_url,
                instance_root=instance_root,
                extra_env={"BUDDYSWITCH_TEST_PROXY_TAB_ID": "stable-selected-after-restart"},
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(responses[0]["id"], 1)
            self.assertEqual(forwarded[0]["params"]["name"], "take_snapshot")
            saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:stable-selected-after-restart")
            self.assertEqual(
                schedule["payload"],
                {"tab_target_id": "stable-selected-after-restart", "idle_seconds": 40},
            )
            ordered_tool_names = [
                call.get("params", {}).get("name")
                for call in self._last_proxy_all_calls
                if call.get("method") == "tools/call"
            ]
            self.assertEqual(ordered_tool_names, ["get_tab_id", "take_snapshot"])
            self.assertFalse(thread.is_alive())

    def test_page_scoped_identity_failure_does_not_block_normal_operation(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("take_snapshot", {})],
                browser_url=browser_url,
                instance_root=instance_root,
                extra_env={"BUDDYSWITCH_TEST_PROXY_GET_TAB_ID_ERROR": "1"},
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded[0]["params"]["name"], "take_snapshot")
            self.assertIn("lifecycle warning", json.dumps(responses, ensure_ascii=True).lower())
            self.assertIn("operation still ran normally", json.dumps(responses, ensure_ascii=True).lower())
            self.assertFalse((instance_root / "runtime" / "browser" / "page_idle.json").exists())

    def test_upstream_exit_during_identity_lookup_returns_one_error_and_next_call_restarts(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [
                self._single_call("take_snapshot", {}),
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_pages", "arguments": {}}},
            ],
            exit_without_response_once=True,
            message_delay_seconds=0.2,
        )

        self.assertEqual([response["id"] for response in responses], [1, 2])
        self.assertTrue(responses[0]["result"].get("isError"), msg=responses[0])
        self.assertIn("exited", responses[0]["result"]["content"][0]["text"])
        self.assertFalse(responses[1]["result"].get("isError", False), msg=responses[1])
        self.assertEqual([call["params"]["name"] for call in forwarded], ["list_pages"])

    def test_manual_close_forgets_exact_resolved_target_after_success(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance, server, thread = self._start_mailbox(instance_root)
            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [
                    self._single_call("select_page", {"pageId": 3, "bringToFront": True}),
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "close_page", "arguments": {"pageId": 3}}},
                ],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual([call["params"]["name"] for call in forwarded], ["select_page", "close_page"])
            self.assertEqual([response["id"] for response in responses], [1, 2])
            state = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(state["targets"], {})
            self.assertNotIn("active_tab_target_id", state)

    def test_internal_structured_content_is_not_exposed_to_client(self) -> None:
        responses, _forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("select_page", {"pageId": 3})]
        )

        self.assertNotIn("structuredContent", responses[0]["result"])
        tools = self._run_proxy([{"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}])[0][0]["result"]["tools"]
        self.assertNotIn("get_tab_id", {tool["name"] for tool in tools})
    def test_select_page_forces_no_bring_to_front(self) -> None:
        _responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("select_page", {"pageId": 3, "bringToFront": True})]
        )

        arguments = forwarded[0]["params"]["arguments"]
        self.assertEqual(arguments["pageId"], 3)
        self.assertIs(arguments["bringToFront"], False)
    def test_focus_rpc_methods_are_rejected_without_forwarding(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [
                {"jsonrpc": "2.0", "id": 1, "method": "Page.bringToFront", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "Target.activateTarget", "params": {}},
            ]
        )

        self.assertEqual(forwarded, [])
        by_id = {response["id"]: response for response in responses}
        for request_id, method in ((1, "Page.bringToFront"), (2, "Target.activateTarget")):
            with self.subTest(method=method):
                response = by_id[request_id]
                self.assertEqual(response["error"]["code"], -32000)
                self.assertIn(method, response["error"]["message"])
                self.assertIn("non-activating", response["error"]["message"])
    def test_tools_list_patches_focus_sensitive_descriptions(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [{"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}]
        )

        self.assertEqual(forwarded, [])
        tools = responses[0]["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        self.assertIn("BuddySwitch", json.dumps(by_name["new_page"], ensure_ascii=True))
        self.assertIn("upstream Chrome DevTools MCP", json.dumps(by_name["new_page"], ensure_ascii=True))
        self.assertIn("background=true", json.dumps(by_name["new_page"], ensure_ascii=True))
        self.assertIn("foreground activation", json.dumps(by_name["select_page"], ensure_ascii=True))
    def test_tool_descriptions_teach_mcp_page_id_truth(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [{"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}]
        )

        self.assertEqual(forwarded, [])
        tools = responses[0]["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        list_pages_text = json.dumps(by_name["list_pages"], ensure_ascii=True)
        select_page_text = json.dumps(by_name["select_page"], ensure_ascii=True)
        snapshot_text = json.dumps(by_name["take_snapshot"], ensure_ascii=True)
        self.assertIn("upstream MCP pageId", list_pages_text)
        self.assertIn("requested upstream MCP pageId", select_page_text)
        self.assertIn("selected upstream MCP pageId", snapshot_text)
        for text in (list_pages_text, select_page_text, snapshot_text):
            self.assertNotIn("browser-session", text)
            self.assertNotIn("target_id", text)
            self.assertNotIn(LEGACY_CURRENT_TARGET_FIELD, text)
    def test_tool_descriptions_teach_open_current_projection(self) -> None:
        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [{"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}]
        )

        self.assertEqual(forwarded, [])
        tools = responses[0]["result"]["tools"]
        by_name = {tool["name"]: tool for tool in tools}
        new_page_text = json.dumps(by_name["new_page"], ensure_ascii=True)
        search_page_text = json.dumps(by_name["search_page"], ensure_ascii=True)
        list_pages_text = json.dumps(by_name["list_pages"], ensure_ascii=True)
        for text in (new_page_text, search_page_text):
            self.assertIn("Chrome tab", text)
            self.assertIn("idle", text)
        self.assertIn("stable tab resource projection", list_pages_text)
