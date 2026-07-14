from tests.integration.browser.cockpit_proxy_harness import *  # noqa: F401,F403


class TestCockpitProxyPageState(BrowserCockpitProxyHarness):
    def test_select_page_marks_mcp_page_id_current(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

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
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:page-3")
            self.assertEqual(schedule["payload"], {"page_id": "page-3"})
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["current_page_id"], "page-3")
            self.assertEqual(page_idle["selected_page_id"], "page-3")
            self.assertEqual(page_idle["pages"]["page-3"]["url"], "https://example.com/selected")
            self.assertNotIn(LEGACY_CURRENT_TARGET_FIELD, page_idle)
            self.assertNotIn(LEGACY_PAGE_TARGET_MAP_FIELD, page_idle)
            self.assertNotIn("targets", page_idle)
            self.assertFalse(thread.is_alive())
    def test_select_page_marks_page_current_without_cdp_target_lookup(self) -> None:
        cdp_state: dict[str, object] = {"requests": [], "list_fail": True}
        browser_url = self._start_cdp_list_server(cdp_state)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

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
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:page-4")
            page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
            self.assertEqual(page_idle["current_page_id"], "page-4")
            self.assertEqual(page_idle["selected_page_id"], "page-4")
            self.assertEqual(cdp_state.get("requests"), [])
    def test_select_page_without_page_id_reports_lifecycle_warning(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            daemon_core, server, thread = self._start_mailbox(instance_root)

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
    def test_page_scoped_success_refreshes_selected_page_id_idle(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(
                instance_root,
                {
                    "current_page_id": "page-current",
                    "selected_page_id": "page-current",
                    "current_page_updated_at": "2026-06-23T00:00:00Z",
                    "pages": {
                        "page-current": {
                            "page_id": "page-current",
                            "url": "https://example.com/current",
                            "last_used_at": "2026-06-23T00:00:00Z",
                        }
                    },
                },
            )
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("take_snapshot", {})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(responses[0]["id"], 1)
            self.assertEqual(forwarded[0]["params"]["name"], "take_snapshot")
            saved = json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            schedule = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(schedule["schedule_key"], "browser.page.idle:page-current")
            self.assertEqual(schedule["payload"], {"page_id": "page-current"})
            self.assertFalse(thread.is_alive())
    def test_page_scoped_success_without_selected_page_reports_clear_lifecycle_warning(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(instance_root, {"pages": {}})
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [self._single_call("take_snapshot", {})],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual(forwarded[0]["params"]["name"], "take_snapshot")
            self.assertFalse(daemon_state.daemon_state_file(instance_root).exists())
            self.assertIn("lifecycle warning", json.dumps(responses, ensure_ascii=True).lower())
            self.assertIn("selected page", json.dumps(responses, ensure_ascii=True).lower())
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
        self.assertIn("selected upstream MCP pageId", select_page_text)
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
            self.assertIn("records the returned selected MCP pageId", text)
            self.assertIn("current/selected projection", text)
        self.assertIn("BuddySwitch current/selected projection", list_pages_text)
