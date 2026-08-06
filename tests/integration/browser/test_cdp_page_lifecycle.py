from tests.integration.browser.cdp_lifecycle_harness import *  # noqa: F401,F403


class TestCdpPageLifecycle(CdpBrowserLifecycleHarness):
    def _write_ttl_config(self, instance_root: Path, *, page: int = 40, release: int = 10) -> Path:
        shared_root = instance_root.parent.parent
        path = shared_root / "config" / "browser.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"schema_version = 1\n\n[ttl]\npage_idle_seconds = {page}\nrelease_delay_seconds = {release}\n",
            encoding="utf-8",
        )
        return path

    def test_target_transport_lists_only_page_targets(self) -> None:
        target = load_target_transport()
        cdp_state: dict[str, object] = {
            "rpc_requests": [],
            "targets": [
                {"targetId": "tab-one", "type": "page", "url": "https://example.com/one"},
                {"targetId": "worker-one", "type": "service_worker", "url": "https://example.com/sw.js"},
            ],
        }
        browser_url = _start_cdp_browser_server(self, cdp_state)

        result = target.list_page_targets(browser_url, timeout_seconds=1.0)

        self.assertEqual(result, [{"targetId": "tab-one", "type": "page", "url": "https://example.com/one"}])
        self.assertEqual(
            cdp_state["rpc_requests"],
            [{"id": 1, "method": "Target.getTargets", "params": {}}],
        )

    def test_close_target_sends_target_close_target_for_exact_id(self) -> None:
        target = load_target_transport()
        cdp_state: dict[str, object] = {
            "rpc_requests": [],
            "targets": [{"targetId": "target-close-exact", "type": "page"}],
        }
        browser_url = _start_cdp_browser_server(self, cdp_state)

        result = target.close_target(browser_url, "target-close-exact", timeout_seconds=1.0)

        self.assertEqual(result, {"success": True})
        self.assertEqual(
            cdp_state["rpc_requests"],
            [{"id": 1, "method": "Target.closeTarget", "params": {"targetId": "target-close-exact"}}],
        )
        self.assertEqual(cdp_state["targets"], [])

    def test_get_target_info_reads_exact_outer_tab_target(self) -> None:
        target = load_target_transport()
        cdp_state: dict[str, object] = {
            "targets": [
                {"targetId": "outer-tab", "type": "tab", "url": "https://example.com"},
                {"targetId": "inner-page", "type": "page", "url": "https://example.com"},
            ]
        }
        browser_url = _start_cdp_browser_server(self, cdp_state)

        result = target.get_target_info(browser_url, "outer-tab", timeout_seconds=1.0)

        self.assertEqual(result, {"targetId": "outer-tab", "type": "tab", "url": "https://example.com"})
        self.assertEqual(
            cdp_state["rpc_requests"],
            [{"id": 1, "method": "Target.getTargetInfo", "params": {"targetId": "outer-tab"}}],
        )

    def test_get_target_info_returns_none_only_for_missing_exact_target(self) -> None:
        target = load_target_transport()
        cdp_state: dict[str, object] = {"targets": []}
        browser_url = _start_cdp_browser_server(self, cdp_state)

        self.assertIsNone(target.get_target_info(browser_url, "missing-tab", timeout_seconds=1.0))

    def test_close_target_raises_clear_error_on_cdp_error(self) -> None:
        target = load_target_transport()
        cdp_state: dict[str, object] = {"rpc_requests": [], "close_error": "No target with given id found"}
        browser_url = _start_cdp_browser_server(self, cdp_state)

        with self.assertRaisesRegex(target.CdpTargetError, "No target with given id found"):
            target.close_target(browser_url, "target-missing", timeout_seconds=1.0)

    def test_schedule_failed_open_page_cleanup_uses_exact_target_key(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs) or {
            "schedule": {"schedule_id": "schedule-failed-open"}
        }

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            result = self.lifecycle.schedule_failed_open_page_cleanup(
                instance_root=instance_root,
                target_id="target-cleanup",
                url="https://example.com/failed-open",
                attempts=1,
                first_seen_at="2026-07-07T00:00:00Z",
            )

        self.assertEqual(result, {"schedule": {"schedule_id": "schedule-failed-open"}})
        self.assertEqual(calls[0]["schedule_key"], "browser.failed_open_page.cleanup:target-cleanup")
        self.assertEqual(calls[0]["payload"]["target_id"], "target-cleanup")

    def test_refresh_tab_idle_uses_stable_target_payload_config_and_state(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs) or {
            "schedule": {"schedule_id": "schedule-1"}
        }
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-browser"
            self._write_ttl_config(instance_root, page=3)

            result = self.lifecycle.refresh_tab_idle(
                instance_root=instance_root,
                tab_target_id="stable-tab-1",
                target_url="https://example.com/background",
                active=True,
            )

            state = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))

        self.assertEqual(
            result,
            {
                "idle_refreshed": True,
                "idle_seconds": 3,
                "idle_expires_at": "2026-06-24T00:00:03Z",
                "tab_target_id": "stable-tab-1",
            },
        )
        self.assertEqual(
            calls,
            [
                {
                    "instance_root": instance_root,
                    "delay_seconds": 3,
                    "trigger_type": "browser.page.expired",
                    "payload": {"tab_target_id": "stable-tab-1", "idle_seconds": 3},
                    "source_context": {"owner": "browser"},
                    "schedule_key": "browser.page.idle:stable-tab-1",
                }
            ],
        )
        self.assertEqual(state["active_tab_target_id"], "stable-tab-1")
        self.assertEqual(
            state["targets"]["stable-tab-1"],
            {
                "tab_target_id": "stable-tab-1",
                "url": "https://example.com/background",
                "last_used_at": "2026-06-24T00:00:00Z",
                "idle_seconds": 3,
            },
        )
        self.assertNotIn("pages", state)
        self.assertNotIn("current_page_id", state)
        self.assertNotIn("selected_page_id", state)

    def test_config_edit_applies_only_to_next_target_refresh(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs) or {}
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-browser"
            path = self._write_ttl_config(instance_root, page=2)
            self.lifecycle.refresh_tab_idle(instance_root=instance_root, tab_target_id="stable-tab-1")
            path.write_text(
                "schema_version = 1\n\n[ttl]\npage_idle_seconds = 7\nrelease_delay_seconds = 1\n",
                encoding="utf-8",
            )
            self.lifecycle.refresh_tab_idle(instance_root=instance_root, tab_target_id="stable-tab-1")

            state = self.lifecycle.read_page_idle_state(instance_root)

        self.assertEqual([call["delay_seconds"] for call in calls], [2, 7])
        self.assertEqual([call["payload"]["idle_seconds"] for call in calls], [2, 7])
        self.assertEqual(state["targets"]["stable-tab-1"]["idle_seconds"], 7)

    def test_stale_due_check_uses_effective_ttl_from_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-browser"
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "active_tab_target_id": "stable-tab-1",
                    "targets": {
                        "stable-tab-1": {
                            "tab_target_id": "stable-tab-1",
                            "last_used_at": "2026-06-24T00:00:05Z",
                            "idle_seconds": 7,
                        }
                    },
                },
            )

            stale = self.lifecycle.tab_idle_expiry_after_due_at(
                instance_root=instance_root,
                tab_target_id="stable-tab-1",
                due_at="2026-06-24T00:00:07Z",
                idle_seconds=7,
            )

        self.assertTrue(stale)

    def test_schedule_browser_release_uses_current_config(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs) or {
            "schedule": {"schedule_id": "schedule-release"}
        }

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-browser"
            self._write_ttl_config(instance_root, release=0)
            result = self.lifecycle.schedule_browser_cockpit_release(instance_root=instance_root)

        self.assertEqual(result, {"schedule": {"schedule_id": "schedule-release"}})
        self.assertEqual(calls[0]["delay_seconds"], 0)
        self.assertEqual(calls[0]["schedule_key"], "browser.cockpit.release")

    def test_refresh_schedule_failure_leaves_no_target_state(self) -> None:
        self.lifecycle.daemon_client.schedule_trigger = lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("daemon unavailable")
        )

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-browser"
            self._write_ttl_config(instance_root)
            with self.assertRaisesRegex(RuntimeError, "daemon unavailable"):
                self.lifecycle.refresh_tab_idle(instance_root=instance_root, tab_target_id="unmanaged-tab")

            self.assertFalse(self.lifecycle.page_idle_state_file(instance_root).exists())

    def test_forget_target_removes_active_identity_only_after_explicit_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-browser"
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "active_tab_target_id": "tab-forget",
                    "targets": {
                        "tab-forget": {"tab_target_id": "tab-forget", "last_used_at": "2026-06-24T00:00:00Z", "idle_seconds": 40},
                        "tab-keep": {"tab_target_id": "tab-keep", "last_used_at": "2026-06-24T00:00:00Z", "idle_seconds": 40},
                    },
                },
            )

            state = self.lifecycle.forget_tab_idle_target(
                instance_root=instance_root,
                tab_target_id="tab-forget",
            )

        self.assertNotIn("tab-forget", state["targets"])
        self.assertIn("tab-keep", state["targets"])
        self.assertNotIn("active_tab_target_id", state)

    def test_old_page_identity_state_is_not_read_as_target_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-browser"
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "current_page_id": "7",
                    "selected_page_id": "7",
                    "pages": {"7": {"page_id": "7", "url": "https://example.com/old"}},
                },
            )

            state = self.lifecycle.read_page_idle_state(instance_root)

        self.assertEqual(state, {"targets": {}})
