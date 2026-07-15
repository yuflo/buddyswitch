"""Exact Chrome target expiry and browser release behavior."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from typing import Any


@dataclass
class FakeTrigger:
    type: str = "browser.page.expired"
    payload: dict[str, Any] | None = None
    target_identity_id: str = "act-dev-browser"
    target_role_id: str = "dev"
    source_context: dict[str, Any] | None = None


class FakeContext:
    actor_id = "act-dev-browser"
    role = "dev"

    def __init__(self, instance_root: Path, *, browser_port: int | None = 9444) -> None:
        self.instance_root = instance_root
        self.instance_json = instance_root / "instance.json"
        self.instance_json.parent.mkdir(parents=True, exist_ok=True)
        self.instance_json.write_text(
            json.dumps({"actor_id": self.actor_id, "role": self.role, "browser_port": browser_port}) + "\n",
            encoding="utf-8",
        )
        self.instance_payload = {"browser_port": browser_port}


class FakeRuntime:
    def __init__(self, status: str = "idle") -> None:
        self.status = status

    def parent_activity(self) -> dict[str, str]:
        return {"status": self.status}


class TestBrowserPageExpiredHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.handler_module = importlib.reload(importlib.import_module("browser_page_expired_handler"))
        self.inbound_module = importlib.reload(importlib.import_module("browser_inbound"))
        original_list_page_targets = self.handler_module.cdp_target.list_page_targets
        original_close_target = self.handler_module.cdp_target.close_target
        original_schedule_release = self.handler_module.browser_lifecycle.schedule_browser_cockpit_release
        original_refresh = self.handler_module.browser_lifecycle.refresh_tab_idle
        self.addCleanup(setattr, self.handler_module.cdp_target, "list_page_targets", original_list_page_targets)
        self.addCleanup(setattr, self.handler_module.cdp_target, "close_target", original_close_target)
        self.addCleanup(
            setattr,
            self.handler_module.browser_lifecycle,
            "schedule_browser_cockpit_release",
            original_schedule_release,
        )
        self.addCleanup(setattr, self.handler_module.browser_lifecycle, "refresh_tab_idle", original_refresh)
        self.targets: list[dict[str, Any]] = []
        self.list_error: Exception | None = None
        self.close_error: Exception | None = None
        self.keep_after_close = False
        self.close_calls: list[tuple[str, str]] = []
        self.release_calls: list[dict[str, Any]] = []
        self.refresh_calls: list[dict[str, Any]] = []

        def list_page_targets(browser_url: str, timeout_seconds: float = 3.0) -> list[dict[str, Any]]:
            del browser_url, timeout_seconds
            if self.list_error is not None:
                raise self.list_error
            return [dict(target) for target in self.targets]

        def close_target(browser_url: str, target_id: str, timeout_seconds: float = 3.0) -> dict[str, Any]:
            del timeout_seconds
            self.close_calls.append((browser_url, target_id))
            if self.close_error is not None:
                raise self.close_error
            if not self.keep_after_close:
                self.targets = [target for target in self.targets if target.get("targetId") != target_id]
            return {"success": True}

        def schedule_release(**kwargs: Any) -> dict[str, Any]:
            self.release_calls.append(kwargs)
            return {}

        def refresh(**kwargs: Any) -> dict[str, Any]:
            self.refresh_calls.append(kwargs)
            return {"idle_refreshed": True, "idle_seconds": 40}

        self.handler_module.cdp_target.list_page_targets = list_page_targets
        self.handler_module.cdp_target.close_target = close_target
        self.handler_module.browser_lifecycle.schedule_browser_cockpit_release = schedule_release
        self.handler_module.browser_lifecycle.refresh_tab_idle = refresh

    def _state(self, instance_root: Path, *, target_id: str = "stable-tab-1", active: bool = False, last_used_at: str = "2026-07-15T00:00:00Z") -> None:
        state: dict[str, Any] = {
            "targets": {
                target_id: {
                    "tab_target_id": target_id,
                    "last_used_at": last_used_at,
                    "idle_seconds": 40,
                    "url": "https://example.com/before-navigation",
                }
            }
        }
        if active:
            state["active_tab_target_id"] = target_id
        self.handler_module.browser_lifecycle._write_page_idle_state(instance_root, state)

    def _trigger(
        self,
        *,
        target_id: object = "stable-tab-1",
        idle_seconds: object = 40,
        due_at: str = "2026-07-15T00:00:40Z",
    ) -> FakeTrigger:
        return FakeTrigger(
            payload={"tab_target_id": target_id, "idle_seconds": idle_seconds},
            source_context={"due_at": due_at},
        )

    def _persisted(self, instance_root: Path) -> dict[str, Any]:
        return json.loads(
            self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8")
        )

    def test_inbound_contract_requires_stable_target_and_effective_ttl(self) -> None:
        self.assertEqual(
            self.inbound_module.BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT["required_fields"],
            ("tab_target_id", "idle_seconds"),
        )

    def test_expiry_closes_exact_target_after_navigation_changed_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            self._state(instance_root)
            self.targets = [
                {"targetId": "stable-tab-1", "type": "page", "url": "https://example.com/after-navigation"},
                {"targetId": "stable-tab-2", "type": "page", "url": "https://example.com/before-navigation"},
            ]

            result = self.handler_module.BrowserPageExpiredHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

            self.assertEqual(result.status, "handled", msg=result.message)
            self.assertEqual(self.close_calls, [("http://127.0.0.1:9444", "stable-tab-1")])
            self.assertNotIn("stable-tab-1", self._persisted(instance_root)["targets"])
            self.assertEqual([target["targetId"] for target in self.targets], ["stable-tab-2"])
            self.assertEqual(self.release_calls, [{"instance_root": instance_root, "reason": "page_idle_empty"}])

    def test_duplicate_urls_do_not_affect_exact_target_close(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            self._state(instance_root)
            self.targets = [
                {"targetId": "stable-tab-1", "type": "page", "url": "https://example.com/same"},
                {"targetId": "stable-tab-2", "type": "page", "url": "https://example.com/same"},
            ]

            result = self.handler_module.BrowserPageExpiredHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(self.close_calls[0][1], "stable-tab-1")

    def test_absent_target_is_forgotten_and_release_is_scheduled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            self._state(instance_root)

            result = self.handler_module.BrowserPageExpiredHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

            self.assertEqual(result.status, "handled", msg=result.message)
            self.assertEqual(self.close_calls, [])
            self.assertEqual(self._persisted(instance_root)["targets"], {})
            self.assertEqual(len(self.release_calls), 1)

    def test_query_failure_retains_owned_target_and_does_not_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            self._state(instance_root)
            self.list_error = self.handler_module.cdp_target.CdpTargetError("query unavailable")

            result = self.handler_module.BrowserPageExpiredHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

            self.assertEqual(result.status, "failed")
            self.assertIn("query unavailable", result.message)
            self.assertIn("stable-tab-1", self._persisted(instance_root)["targets"])
            self.assertEqual(self.release_calls, [])

    def test_close_failure_retains_owned_target_and_does_not_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            self._state(instance_root)
            self.targets = [{"targetId": "stable-tab-1", "type": "page"}]
            self.close_error = self.handler_module.cdp_target.CdpTargetError("close denied")

            result = self.handler_module.BrowserPageExpiredHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

            self.assertEqual(result.status, "failed")
            self.assertIn("close denied", result.message)
            self.assertIn("stable-tab-1", self._persisted(instance_root)["targets"])
            self.assertEqual(self.release_calls, [])

    def test_close_verification_failure_retains_owned_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            self._state(instance_root)
            self.targets = [{"targetId": "stable-tab-1", "type": "page"}]
            self.keep_after_close = True

            result = self.handler_module.BrowserPageExpiredHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

            self.assertEqual(result.status, "failed")
            self.assertIn("still present", result.message)
            self.assertIn("stable-tab-1", self._persisted(instance_root)["targets"])
            self.assertEqual(self.release_calls, [])

    def test_running_parent_refreshes_active_target_instead_of_closing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            self._state(instance_root, active=True)
            self.targets = [{"targetId": "stable-tab-1", "type": "page"}]

            result = self.handler_module.BrowserPageExpiredHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime("running"), self._trigger()
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(
            self.refresh_calls,
            [{"instance_root": instance_root, "tab_target_id": "stable-tab-1", "active": True}],
        )
        self.assertEqual(self.close_calls, [])

    def test_stale_due_trigger_does_not_close_recently_refreshed_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            self._state(instance_root, last_used_at="2026-07-15T00:00:30Z")
            self.targets = [{"targetId": "stable-tab-1", "type": "page"}]

            result = self.handler_module.BrowserPageExpiredHandler().handle(
                FakeContext(instance_root),
                object(),
                FakeRuntime(),
                self._trigger(due_at="2026-07-15T00:00:40Z"),
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(self.close_calls, [])

    def test_missing_browser_endpoint_forgets_target_without_raw_close(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            self._state(instance_root)

            result = self.handler_module.BrowserPageExpiredHandler().handle(
                FakeContext(instance_root, browser_port=None), object(), FakeRuntime(), self._trigger()
            )

            self.assertEqual(result.status, "handled", msg=result.message)
            self.assertEqual(self._persisted(instance_root)["targets"], {})
            self.assertEqual(self.close_calls, [])

    def test_expiry_module_has_no_mcp_session_path(self) -> None:
        self.assertFalse(hasattr(self.handler_module, "McpToolSession"))
        self.assertFalse(hasattr(self.handler_module, "open_mcp_session"))


class TestBrowserFailedOpenCleanup(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.reload(importlib.import_module("browser_page_expired_handler"))
        original_list_page_targets = self.module.cdp_target.list_page_targets
        original_close_target = self.module.cdp_target.close_target
        original_schedule_release = self.module.browser_lifecycle.schedule_browser_cockpit_release
        original_schedule_failed_cleanup = self.module.browser_lifecycle.schedule_failed_open_page_cleanup
        self.addCleanup(setattr, self.module.cdp_target, "list_page_targets", original_list_page_targets)
        self.addCleanup(setattr, self.module.cdp_target, "close_target", original_close_target)
        self.addCleanup(
            setattr,
            self.module.browser_lifecycle,
            "schedule_browser_cockpit_release",
            original_schedule_release,
        )
        self.addCleanup(
            setattr,
            self.module.browser_lifecycle,
            "schedule_failed_open_page_cleanup",
            original_schedule_failed_cleanup,
        )
        self.targets = [{"targetId": "failed-target", "type": "page", "url": "https://example.com/failed"}]
        self.close_calls: list[str] = []
        self.schedules: list[dict[str, Any]] = []
        self.keep_after_close = False

        self.module.cdp_target.list_page_targets = lambda *_args, **_kwargs: [dict(target) for target in self.targets]

        def close_target(_browser_url: str, target_id: str, _timeout_seconds: float = 3.0) -> dict[str, bool]:
            self.close_calls.append(target_id)
            if not self.keep_after_close:
                self.targets = [target for target in self.targets if target["targetId"] != target_id]
            return {"success": True}

        self.module.cdp_target.close_target = close_target
        self.module.browser_lifecycle.schedule_browser_cockpit_release = lambda **_kwargs: {}
        self.module.browser_lifecycle.schedule_failed_open_page_cleanup = lambda **kwargs: self.schedules.append(kwargs) or {}

    def test_failed_open_cleanup_closes_exact_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            context = FakeContext(instance_root)
            trigger = FakeTrigger(
                type="browser.failed_open_page.cleanup",
                payload={"target_id": "failed-target", "attempts": 1, "first_seen_at": "2026-07-15T00:00:00Z"},
            )

            result = self.module.BrowserFailedOpenPageCleanupHandler().handle(
                context, object(), FakeRuntime(), trigger
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(self.close_calls, ["failed-target"])
        self.assertEqual(self.schedules, [])

    def test_failed_open_cleanup_retries_when_target_remains_after_close(self) -> None:
        self.keep_after_close = True
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            context = FakeContext(instance_root)
            trigger = FakeTrigger(
                type="browser.failed_open_page.cleanup",
                payload={"target_id": "failed-target", "attempts": 1, "first_seen_at": "2026-07-15T00:00:00Z"},
            )

            result = self.module.BrowserFailedOpenPageCleanupHandler().handle(
                context, object(), FakeRuntime(), trigger
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(self.close_calls, ["failed-target"])
        self.assertEqual(self.schedules[0]["target_id"], "failed-target")
        self.assertEqual(self.schedules[0]["attempts"], 2)


class TestBrowserReleaseHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.reload(importlib.import_module("browser_release_handler"))
        original_release = self.module.browser_runtime_manager.release
        original_list_page_targets = self.module.cdp_target.list_page_targets
        self.addCleanup(setattr, self.module.browser_runtime_manager, "release", original_release)
        self.addCleanup(setattr, self.module.cdp_target, "list_page_targets", original_list_page_targets)
        self.manager_calls: list[dict[str, Any]] = []
        self.module.browser_runtime_manager.release = lambda **kwargs: self.manager_calls.append(kwargs) or {
            "ok": True,
            "status": "released",
        }

    def _trigger(self) -> FakeTrigger:
        return FakeTrigger(
            type="browser.cockpit.release",
            payload={"reason": "page_idle_empty"},
            source_context={},
        )

    def test_release_skips_when_tracked_targets_remain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            lifecycle = importlib.import_module("env.cdp_browser_lifecycle")
            lifecycle._write_page_idle_state(
                instance_root,
                {"targets": {"stable-tab-1": {"tab_target_id": "stable-tab-1"}}},
            )

            result = self.module.BrowserReleaseHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(self.manager_calls, [])

    def test_release_skips_when_untracked_real_page_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            lifecycle = importlib.import_module("env.cdp_browser_lifecycle")
            lifecycle._write_page_idle_state(instance_root, {"targets": {}})
            self.module.cdp_target.list_page_targets = lambda *_args, **_kwargs: [
                {"targetId": "real-user-tab", "type": "page", "url": "https://example.com"}
            ]

            result = self.module.BrowserReleaseHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(self.manager_calls, [])

    def test_release_calls_runtime_manager_only_when_state_and_browser_are_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            lifecycle = importlib.import_module("env.cdp_browser_lifecycle")
            lifecycle._write_page_idle_state(instance_root, {"targets": {}})
            self.module.cdp_target.list_page_targets = lambda *_args, **_kwargs: []

            result = self.module.BrowserReleaseHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

        self.assertEqual(result.status, "handled", msg=result.message)
        self.assertEqual(
            self.manager_calls,
            [{"instance_root": instance_root, "actor_id": "act-dev-browser", "reason": "page_idle_empty"}],
        )

    def test_release_target_query_failure_is_retried_instead_of_killing_browser(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "shared" / "instances" / "act-dev-browser"
            lifecycle = importlib.import_module("env.cdp_browser_lifecycle")
            lifecycle._write_page_idle_state(instance_root, {"targets": {}})

            def fail_query(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
                raise self.module.cdp_target.CdpTargetError("target query unavailable")

            self.module.cdp_target.list_page_targets = fail_query
            result = self.module.BrowserReleaseHandler().handle(
                FakeContext(instance_root), object(), FakeRuntime(), self._trigger()
            )

        self.assertEqual(result.status, "failed")
        self.assertIn("target query unavailable", result.message or "")
        self.assertEqual(self.manager_calls, [])
