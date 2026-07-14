from tests.integration.browser.cockpit_proxy_harness import *  # noqa: F401,F403


class TestCockpitProxyProtocol(BrowserCockpitProxyHarness):
    def test_initialize_and_tools_list_do_not_start_upstream_without_browser_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            upstream = temp_root_path / "fake_upstream.py"
            calls_path = temp_root_path / "calls.jsonl"
            argv_path = temp_root_path / "argv.jsonl"
            instance_root = temp_root_path / "instance"
            instance_root.mkdir()
            self._write_fake_upstream(upstream)

            env = os.environ.copy()
            env["BUDDYSWITCH_TEST_PROXY_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_PROXY_ARGV"] = str(argv_path)
            command = [
                PYTHON,
                str(PROXY),
                "--upstream-command",
                f"{PYTHON} {upstream}",
                f"--instance-root={instance_root}",
            ]
            proc = ResourceLedger.from_environment().start_process(
                command,
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "test"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            ]
            input_text = "".join(json.dumps(message, ensure_ascii=True) + "\n" for message in messages)
            try:
                stdout, stderr = proc.communicate(input=input_text, timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
                self.fail(f"proxy timed out\nstdout:\n{stdout}\nstderr:\n{stderr}")

            self.assertEqual(proc.returncode, 0, msg=f"proxy failed\nstdout:\n{stdout}\nstderr:\n{stderr}")
            self.assertFalse(argv_path.exists(), "initialize/tools-list must not spawn upstream")
            self.assertFalse(calls_path.exists(), "initialize/tools-list must not forward to upstream")
            responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            self.assertEqual([response.get("id") for response in responses], [1, 2])
            self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "chrome-devtools-cockpit")
            tools = responses[1]["result"]["tools"]
            by_name = {tool["name"]: tool for tool in tools}
            self.assertIn("new_page", by_name)
            self.assertIn("BuddySwitch", json.dumps(by_name["new_page"], ensure_ascii=True))
    def test_first_tools_call_uses_broker_acquire_not_ensure_subprocess(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
                initial_browser_port_missing=True,
                extra_env={
                    "BUDDYSWITCH_TEST_PROXY_BROKER_BROWSER_URL": browser_url,
                },
            )

        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertEqual([call.get("method") for call in self._last_proxy_broker_calls], ["browser.acquire"])
        broker_params = self._last_proxy_broker_calls[0].get("params")
        self.assertIsInstance(broker_params, dict, msg=self._last_proxy_broker_calls[0])
        assert isinstance(broker_params, dict)
        self.assertEqual(broker_params.get("reason"), "chrome-devtools-cockpit")
        broker_params_text = json.dumps(broker_params, ensure_ascii=True)
        self.assertNotIn("source_root", broker_params_text)
        self.assertNotIn("launcher_path", broker_params_text)
        self.assertNotIn("buddyswitch-" + "codex", broker_params_text)
    def test_broker_socket_arg_sets_runtime_broker_socket_for_first_tools_call(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
                initial_browser_port_missing=True,
                set_broker_socket_env=False,
                pass_broker_socket_arg=True,
            )

        self.assertEqual(stderr, "")
        self.assertEqual(responses[0]["id"], 1)
        self.assertFalse(responses[0].get("result", {}).get("isError", False), msg=responses[0])
        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertEqual([call.get("method") for call in self._last_proxy_broker_calls], ["browser.acquire"])
    def test_invalid_json_before_upstream_does_not_start_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            temp_root_path = Path(temp_root)
            upstream = temp_root_path / "fake_upstream.py"
            calls_path = temp_root_path / "calls.jsonl"
            argv_path = temp_root_path / "argv.jsonl"
            instance_root = temp_root_path / "instance"
            instance_root.mkdir()
            self._write_fake_upstream(upstream)

            env = os.environ.copy()
            env["BUDDYSWITCH_TEST_PROXY_CALLS"] = str(calls_path)
            env["BUDDYSWITCH_TEST_PROXY_ARGV"] = str(argv_path)
            command = [
                PYTHON,
                str(PROXY),
                "--upstream-command",
                f"{PYTHON} {upstream}",
                f"--instance-root={instance_root}",
            ]
            proc = ResourceLedger.from_environment().start_process(
                command,
                cwd=ROOT,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = proc.communicate(input="{not-json}\n", timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
                self.fail(f"proxy timed out\nstdout:\n{stdout}\nstderr:\n{stderr}")

            self.assertEqual(proc.returncode, 0, msg=f"proxy failed\nstdout:\n{stdout}\nstderr:\n{stderr}")
            self.assertEqual(stdout, "")
            self.assertFalse(argv_path.exists(), "invalid JSON before a tool call must not spawn upstream")
    def test_first_tools_call_acquires_browser_and_starts_upstream(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("list_pages", {})],
                browser_url=browser_url,
                instance_root=instance_root,
                initial_browser_port_missing=True,
            )

        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "list_pages")
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertEqual([call.get("method") for call in self._last_proxy_broker_calls], ["browser.acquire"])
        self.assertEqual(self._last_proxy_broker_calls[0].get("params"), {"reason": "chrome-devtools-cockpit"})
        self.assertEqual(
            [message.get("method") for message in self._last_proxy_all_calls],
            ["initialize", "notifications/initialized", "tools/call"],
        )
        self.assertNotEqual(self._last_proxy_all_calls[0].get("id"), responses[0].get("id"))
        self.assertTrue(self._last_proxy_marker_snapshot.get("pid"), msg=self._last_proxy_marker_snapshot)
        self.assertTrue(self._last_proxy_marker_snapshot.get("pgid"), msg=self._last_proxy_marker_snapshot)
        self.assertFalse((instance_root / "runtime" / "browser" / "cockpit-upstream.pid").exists())
        self.assertFalse((instance_root / "runtime" / "browser" / "cockpit-upstream.pgid").exists())
    def test_first_tools_call_broker_acquire_params_do_not_include_source_root_when_actor_home_is_bound(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": _page_targets(1)})

        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / "act-dev-browser"
            responses, forwarded, upstream_argv, _stderr = self._run_proxy(
                [self._single_call("new_page", {"url": "https://example.com/new"})],
                browser_url=browser_url,
                instance_root=instance_root,
                initial_browser_port_missing=True,
                extra_env={
                    "HOME": str(instance_root / "home"),
                    "CODEX_HOME": str(instance_root / "codex-home"),
                },
                unset_env=["BUDDYSWITCH_SHARED_ROOT", "BUDDYSWITCH_SOURCE_HOME"],
        )

        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(len(forwarded), 1)
        self.assertEqual(forwarded[0]["params"]["name"], "new_page")
        self.assertEqual(forwarded[0]["params"]["arguments"], {"url": "https://example.com/new", "background": True})
        self.assertIn(f"--browser-url={browser_url}", upstream_argv)
        self.assertEqual([call.get("method") for call in self._last_proxy_broker_calls], ["browser.acquire"])
        broker_params_text = json.dumps(self._last_proxy_broker_calls[0].get("params"), ensure_ascii=True)
        self.assertNotIn(str(ROOT), broker_params_text)
        self.assertNotIn(str(shared_root), broker_params_text)
        self.assertNotIn(str(shared_root.parent), broker_params_text)
        self.assertNotIn("HOME", broker_params_text)
        self.assertNotIn("CODEX_HOME", broker_params_text)
    def test_non_page_use_and_failed_page_response_do_not_refresh_idle(self) -> None:
        browser_url = self._start_cdp_list_server({"requests": [], "targets": []})

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_idle_state(
                instance_root,
                {
                    "current_page_id": "page-current",
                    "selected_page_id": "page-current",
                    "current_page_updated_at": "2026-06-23T00:00:00Z",
                    "pages": {"page-current": {"page_id": "page-current", "last_used_at": "2026-06-23T00:00:00Z"}},
                },
            )
            daemon_core, server, thread = self._start_mailbox(instance_root)

            responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
                [
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_pages", "arguments": {}}},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "close_page", "arguments": {"pageId": 3}}},
                    {
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {"name": "take_snapshot", "arguments": {"forceError": True}},
                    },
                ],
                browser_url=browser_url,
                instance_root=instance_root,
            )
            server.close()
            thread.join(timeout=2)

            self.assertEqual([response["id"] for response in responses], [1, 2, 3, 4])
            self.assertEqual([item["params"]["name"] for item in forwarded if item.get("method") == "tools/call"], ["list_pages", "close_page", "take_snapshot"])
            self.assertFalse(daemon_state.daemon_state_file(instance_root).exists())
            self.assertFalse(thread.is_alive())
