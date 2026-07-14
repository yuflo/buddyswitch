from tests.integration.browser.cdp_lifecycle_harness import *  # noqa: F401,F403


class TestCdpPageLifecycle(CdpBrowserLifecycleHarness):
    def test_close_target_sends_target_close_target_for_exact_id(self) -> None:
        background = load_background_page()
        self.assertTrue(hasattr(background, "close_target"), "close_target primitive is required")
        cdp_state: dict[str, object] = {"rpc_requests": []}
        browser_url = _start_cdp_browser_server(self, cdp_state)

        result = background.close_target(browser_url, "target-close-exact", timeout_seconds=1.0)

        self.assertEqual(result, {"success": True})
        self.assertEqual(
            cdp_state["rpc_requests"],
            [{"id": 1, "method": "Target.closeTarget", "params": {"targetId": "target-close-exact"}}],
        )
    def test_close_target_raises_clear_error_on_cdp_error(self) -> None:
        background = load_background_page()
        self.assertTrue(hasattr(background, "close_target"), "close_target primitive is required")
        cdp_state: dict[str, object] = {"rpc_requests": [], "close_error": "No target with given id found"}
        browser_url = _start_cdp_browser_server(self, cdp_state)

        with self.assertRaisesRegex(background.CdpTargetError, "No target with given id found"):
            background.close_target(browser_url, "target-missing", timeout_seconds=1.0)

        self.assertEqual(
            cdp_state["rpc_requests"],
            [{"id": 1, "method": "Target.closeTarget", "params": {"targetId": "target-missing"}}],
        )
    def test_schedule_failed_open_page_cleanup_uses_exact_target_key(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-failed-open"}}

        self.lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger
        self.assertTrue(
            hasattr(self.lifecycle, "schedule_failed_open_page_cleanup"),
            "schedule_failed_open_page_cleanup helper is required",
        )

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
        self.assertEqual(
            calls,
            [
                {
                    "instance_root": instance_root,
                    "delay_seconds": 5,
                    "trigger_type": "browser.failed_open_page.cleanup",
                    "payload": {
                        "target_id": "target-cleanup",
                        "url": "https://example.com/failed-open",
                        "attempts": 1,
                        "first_seen_at": "2026-07-07T00:00:00Z",
                        "reason": "failed_open_page",
                    },
                    "source_context": {"owner": "browser"},
                    "schedule_key": "browser.failed_open_page.cleanup:target-cleanup",
                }
            ],
        )
    def test_refresh_page_idle_uses_page_id_payload_and_state(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-1"}}

        self.lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            result = self.lifecycle.refresh_page_idle(
                instance_root=instance_root,
                page_id="page-idle-1",
                target_url="https://example.com/background",
            )

            self.assertEqual(
                result,
                {
                    "idle_refreshed": True,
                    "idle_seconds": 40,
                    "idle_expires_at": "2026-06-24T00:00:40Z",
                },
            )
            self.assertEqual(
                calls,
                [
                    {
                        "instance_root": instance_root,
                        "delay_seconds": 40,
                        "trigger_type": "browser.page.expired",
                        "payload": {"page_id": "page-idle-1"},
                        "source_context": {"owner": "browser"},
                        "schedule_key": "browser.page.idle:page-idle-1",
                    }
                ],
            )
            state_path = instance_root / "runtime" / "browser" / "page_idle.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn(LEGACY_CURRENT_TARGET_FIELD, state)
            self.assertNotIn(LEGACY_PAGE_TARGET_MAP_FIELD, state)
            self.assertNotIn(LEGACY_TARGETS_FIELD, state)
            self.assertNotIn("current_page_updated_at", state)
            self.assertEqual(state["pages"]["page-idle-1"]["url"], "https://example.com/background")
            self.assertEqual(state["pages"]["page-idle-1"]["last_used_at"], "2026-06-24T00:00:00Z")
    def test_mark_current_page_does_not_schedule_idle(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs)
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            state = self.lifecycle.mark_current_page(
                instance_root=instance_root,
                page_id="page-current-1",
                target_url="https://example.com/current",
            )

            self.assertEqual(calls, [])
            self.assertEqual(state["current_page_id"], "page-current-1")
            self.assertEqual(state["selected_page_id"], "page-current-1")
            self.assertEqual(state["current_page_updated_at"], "2026-06-24T00:00:00Z")
            self.assertEqual(state["pages"]["page-current-1"]["url"], "https://example.com/current")
            self.assertNotIn(LEGACY_CURRENT_TARGET_FIELD, state)
            self.assertNotIn(LEGACY_PAGE_TARGET_MAP_FIELD, state)
    def test_refresh_current_page_idle_sets_current_and_schedules(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-1"}}

        self.lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger
        self.lifecycle._utc_now = lambda: datetime(2026, 6, 24, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            result = self.lifecycle.refresh_current_page_idle(
                instance_root=instance_root,
                page_id="page-current-idle",
                target_url="https://example.com/current",
            )

            self.assertTrue(result["idle_refreshed"])
            self.assertEqual(calls[0]["schedule_key"], "browser.page.idle:page-current-idle")
            self.assertEqual(calls[0]["payload"], {"page_id": "page-current-idle"})
            state = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["current_page_id"], "page-current-idle")
            self.assertEqual(state["selected_page_id"], "page-current-idle")
            self.assertEqual(state["pages"]["page-current-idle"]["url"], "https://example.com/current")
    def test_schedule_browser_cockpit_release_uses_keyed_browser_release_trigger(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_schedule_trigger(**kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-release"}}

        self.lifecycle.daemon_client.schedule_trigger = fake_schedule_trigger

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            result = self.lifecycle.schedule_browser_cockpit_release(instance_root=instance_root)

        self.assertEqual(result, {"schedule": {"schedule_id": "schedule-release"}})
        self.assertEqual(
            calls,
            [
                {
                    "instance_root": instance_root,
                    "delay_seconds": 10,
                    "trigger_type": "browser.cockpit.release",
                    "payload": {"reason": "page_idle_empty"},
                    "source_context": {"owner": "browser"},
                    "schedule_key": "browser.cockpit.release",
                }
            ],
        )
    def test_refresh_page_idle_schedule_failure_leaves_no_idle_state(self) -> None:
        def failing_schedule_trigger(**_kwargs: object) -> dict[str, object]:
            raise RuntimeError("daemon unavailable")

        self.lifecycle.daemon_client.schedule_trigger = failing_schedule_trigger

        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"

            with self.assertRaisesRegex(RuntimeError, "daemon unavailable"):
                self.lifecycle.refresh_page_idle(
                    instance_root=instance_root,
                    page_id="page-unmanaged",
                    target_url="https://example.com/unmanaged",
                )

            self.assertFalse(self.lifecycle.page_idle_state_file(instance_root).exists())
    def test_forget_page_idle_page_removes_page_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "current_page_id": "page-forget",
                    "selected_page_id": "page-forget",
                    "current_page_updated_at": "2026-06-24T00:00:00Z",
                    "pages": {
                        "page-forget": {
                            "page_id": "page-forget",
                            "url": "https://example.com/forget",
                            "last_used_at": "2026-06-24T00:00:00Z",
                        },
                        "page-keep": {"page_id": "page-keep", "last_used_at": "2026-06-24T00:00:00Z"},
                    },
                },
            )

            state = self.lifecycle.forget_page_idle_page(instance_root=instance_root, page_id="page-forget")

            self.assertNotIn("page-forget", state["pages"])
            self.assertIn("page-keep", state["pages"])
            self.assertNotIn("current_page_id", state)
            self.assertNotIn("selected_page_id", state)
            persisted = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(persisted, state)
    def test_refresh_page_idle_rejects_blank_page_id_before_scheduling(self) -> None:
        calls: list[dict[str, object]] = []
        self.lifecycle.daemon_client.schedule_trigger = lambda **kwargs: calls.append(kwargs)

        with tempfile.TemporaryDirectory() as temp_root:
            with self.assertRaisesRegex(self.lifecycle.BrowserLifecycleError, "page_id"):
                self.lifecycle.refresh_page_idle(instance_root=Path(temp_root), page_id=" ")

        self.assertEqual(calls, [])
    def test_page_idle_state_ignores_unknown_legacy_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            self.lifecycle._write_page_idle_state(
                instance_root,
                {
                    "legacy_current": "legacy-cdp-1",
                    "legacy_map": {"7": "legacy-cdp-1"},
                    "legacy_pages": {"legacy-cdp-1": {"legacy_id": "legacy-cdp-1"}},
                    "current_page_id": "page-7",
                    "selected_page_id": "page-7",
                    "pages": {"page-7": {"page_id": "page-7", "last_used_at": "2026-06-24T00:00:00Z"}},
                },
            )

            state = self.lifecycle._read_page_idle_state(instance_root)

            self.assertEqual(state["current_page_id"], "page-7")
            self.assertEqual(state["selected_page_id"], "page-7")
            self.assertEqual(state["pages"], {"page-7": {"page_id": "page-7", "last_used_at": "2026-06-24T00:00:00Z"}})
            self.assertNotIn("legacy_current", state)
            self.assertNotIn("legacy_map", state)
            self.assertNotIn("legacy_pages", state)
