"""Tests for browser.page.expired daemon handler."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any
from unittest import mock

from tests.python_runtime import PYTHON


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

HANDLER_PATH = ROOT / "tools" / "launcher" / "browser_page_expired_handler.py"
RELEASE_HANDLER_PATH = ROOT / "tools" / "launcher" / "browser_release_handler.py"
TRIGGERS_PATH = ROOT / "tools" / "launcher" / "daemon_triggers.py"
BROWSER_INBOUND_PATH = ROOT / "tools" / "launcher" / "browser_inbound.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    module_name = f"buddyswitch_{path.stem}_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeContext:
    identity_route = {"role_id": "dev", "actor_id": "act-dev-browser"}
    actor_id = "act-dev-browser"
    role = "dev"
    instance_payload = {"browser_port": 9444}
    instance_root = Path("/tmp/buddyswitch-test-instance")


class FakeRuntime:
    def __init__(self, *, activity_status: str = "idle") -> None:
        self.activity_status = activity_status

    def parent_activity(self) -> dict[str, object]:
        return {"status": self.activity_status}


class BrowserPageExpiredHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler_module = load_module(HANDLER_PATH)
        self.triggers = load_module(TRIGGERS_PATH)
        self.release_calls: list[dict[str, object]] = []
        self.close_calls: list[dict[str, object]] = []
        self.failed_open_close_calls: list[dict[str, object]] = []
        self.failed_open_cleanup_schedules: list[dict[str, object]] = []
        self.failed_open_targets: list[dict[str, object]] = []
        self.failed_open_close_error: Exception | None = None
        self.list_pages_payload: list[dict[str, object]] = []
        self.mcp_list_batches: list[list[dict[str, object]]] | None = None
        self.mcp_sessions: list[Any] = []
        lifecycle = self.handler_module.browser_lifecycle
        self._original_schedule_browser_cockpit_release = lifecycle.schedule_browser_cockpit_release
        self._original_refresh_page_idle = lifecycle.refresh_page_idle
        self._original_read_page_targets = lifecycle.read_page_targets
        self._original_schedule_failed_open_page_cleanup = getattr(lifecycle, "schedule_failed_open_page_cleanup", None)
        self._had_cdp_background_page = hasattr(self.handler_module, "cdp_background_page")
        self._original_cdp_background_page = getattr(self.handler_module, "cdp_background_page", None)
        self.addCleanup(
            setattr,
            lifecycle,
            "schedule_browser_cockpit_release",
            self._original_schedule_browser_cockpit_release,
        )
        self.addCleanup(setattr, lifecycle, "refresh_page_idle", self._original_refresh_page_idle)
        self.addCleanup(setattr, lifecycle, "read_page_targets", self._original_read_page_targets)
        if self._original_schedule_failed_open_page_cleanup is None:
            self.addCleanup(delattr, lifecycle, "schedule_failed_open_page_cleanup")
        else:
            self.addCleanup(
                setattr,
                lifecycle,
                "schedule_failed_open_page_cleanup",
                self._original_schedule_failed_open_page_cleanup,
            )
        if self._had_cdp_background_page:
            self.addCleanup(setattr, self.handler_module, "cdp_background_page", self._original_cdp_background_page)
        else:
            self.addCleanup(delattr, self.handler_module, "cdp_background_page")

        def fake_schedule_browser_cockpit_release(**kwargs: object) -> dict[str, object]:
            self.release_calls.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-release"}}

        def fake_schedule_failed_open_page_cleanup(**kwargs: object) -> dict[str, object]:
            self.failed_open_cleanup_schedules.append(kwargs)
            return {"schedule": {"schedule_id": "schedule-failed-open"}}

        def fake_read_page_targets(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
            return [dict(target) for target in self.failed_open_targets]

        test_case = self

        class FakeCdpBackgroundPage:
            @staticmethod
            def close_target(browser_url: str, target_id: str, timeout_seconds: float = 3.0) -> dict[str, object]:
                test_case.failed_open_close_calls.append(
                    {"browser_url": browser_url, "target_id": target_id, "timeout_seconds": timeout_seconds}
                )
                if test_case.failed_open_close_error is not None:
                    raise test_case.failed_open_close_error
                test_case.failed_open_targets = [
                    target
                    for target in test_case.failed_open_targets
                    if target.get("id") != target_id and target.get("targetId") != target_id
                ]
                return {"success": True}

        class FakeMcpSession:
            def __init__(self, browser_endpoint: str) -> None:
                self.browser_endpoint = browser_endpoint
                self.operations: list[str] = []
                self.closed = False
                self._pages = [dict(item) for item in test_case.list_pages_payload]
                test_case.mcp_sessions.append(self)

            def __enter__(self) -> "FakeMcpSession":
                return self

            def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
                self.close()

            def list_pages(self) -> list[dict[str, object]]:
                self.operations.append("list_pages")
                if test_case.mcp_list_batches is not None:
                    if not test_case.mcp_list_batches:
                        return []
                    return [dict(item) for item in test_case.mcp_list_batches.pop(0)]
                return [dict(item) for item in self._pages]

            def close_page(self, page_id: object) -> dict[str, object]:
                self.operations.append("close_page")
                test_case.close_calls.append({"browser_endpoint": self.browser_endpoint, "page_id": page_id})
                self._pages = [
                    page
                    for page in self._pages
                    if str(page.get("pageId") or page.get("page_id") or page.get("id")) != str(page_id)
                ]
                return {"status": "closed", "page_id": page_id}

            def close(self) -> None:
                self.closed = True

        def fake_open_mcp_session(browser_endpoint: str) -> FakeMcpSession:
            return FakeMcpSession(browser_endpoint)

        lifecycle.schedule_browser_cockpit_release = fake_schedule_browser_cockpit_release
        lifecycle.schedule_failed_open_page_cleanup = fake_schedule_failed_open_page_cleanup
        lifecycle.read_page_targets = fake_read_page_targets
        self.handler_module.cdp_background_page = FakeCdpBackgroundPage
        self.handler_module.open_mcp_session = fake_open_mcp_session

    def _trigger(
        self,
        *,
        page_id: object = "page-idle-1",
        target_identity_route: dict[str, str] | None = None,
        due_at: str | None = None,
    ) -> Any:
        source_context = {"schedule_id": "schedule-1"}
        if due_at is not None:
            source_context["due_at"] = due_at
        return self.triggers.DaemonTrigger(
            source="scheduled_trigger",
            type="browser.page.expired",
            target_identity_id=(target_identity_route or {"actor_id": "act-dev-browser"})["actor_id"],
            target_role_id=(target_identity_route or {"role_id": "dev"})["role_id"],
            origin_id="schedule-1",
            correlation_id=None,
            payload={"page_id": page_id},
            source_context=source_context,
        )

    def _failed_open_trigger(
        self,
        *,
        target_id: object = "target-failed-open",
        url: str = "https://example.com/failed-open",
        attempts: int = 1,
        target_identity_route: dict[str, str] | None = None,
    ) -> Any:
        return self.triggers.DaemonTrigger(
            source="scheduled_trigger",
            type="browser.failed_open_page.cleanup",
            target_identity_id=(target_identity_route or {"actor_id": "act-dev-browser"})["actor_id"],
            target_role_id=(target_identity_route or {"role_id": "dev"})["role_id"],
            origin_id="schedule-failed-open",
            correlation_id=None,
            payload={
                "target_id": target_id,
                "url": url,
                "attempts": attempts,
                "first_seen_at": "2026-07-07T00:00:00Z",
                "reason": "failed_open_page",
            },
            source_context={"schedule_id": "schedule-failed-open", "owner": "browser"},
        )

    def _write_page_state(
        self,
        instance_root: Path,
        *,
        page_id: str = "page-idle-1",
        url: str = "https://example.com/old",
        title: str = "Old Title",
        current: bool = False,
    ) -> None:
        state: dict[str, object] = {
            "pages": {
                page_id: {
                    "page_id": page_id,
                    "url": url,
                    "title": title,
                    "last_used_at": "2026-06-24T00:00:00Z",
                }
            }
        }
        if current:
            state["current_page_id"] = page_id
            state["selected_page_id"] = page_id
            state["current_page_updated_at"] = "2026-06-24T00:00:00Z"
        self.handler_module.browser_lifecycle._write_page_idle_state(instance_root, state)

    def _context(self, instance_root: Path, *, browser_port: int | None = 9444) -> Any:
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps({"actor_id": "act-dev-browser", "role": "dev", "browser_port": browser_port}, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        context = FakeContext()
        context.instance_root = instance_root
        context.instance_json = instance_json
        context.instance_payload = {"browser_port": None}
        return context

    def _failed_open_cleanup_handler(self) -> Any:
        self.assertTrue(
            hasattr(self.handler_module, "BrowserFailedOpenPageCleanupHandler"),
            "BrowserFailedOpenPageCleanupHandler is required",
        )
        return self.handler_module.BrowserFailedOpenPageCleanupHandler()

    def test_failed_open_cleanup_target_absent_is_handled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            context = self._context(instance_root)
            self.failed_open_targets = []
            handler = self._failed_open_cleanup_handler()

            result = handler.handle(
                context,
                state=object(),
                runtime=FakeRuntime(),
                trigger=self._failed_open_trigger(target_id="target-already-gone"),
            )

        self.assertEqual(result.status, "handled", msg=getattr(result, "message", None))
        self.assertEqual(self.failed_open_close_calls, [])
        self.assertEqual(self.failed_open_cleanup_schedules, [])
        self.assertEqual(self.close_calls, [])

    def test_failed_open_cleanup_closes_exact_cdp_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            context = self._context(instance_root)
            self.failed_open_targets = [
                {"id": "target-keep", "type": "page", "url": "https://example.com/keep"},
                {"id": "target-failed-open", "type": "page", "url": "https://example.com/failed-open"},
            ]
            handler = self._failed_open_cleanup_handler()

            result = handler.handle(
                context,
                state=object(),
                runtime=FakeRuntime(),
                trigger=self._failed_open_trigger(target_id="target-failed-open"),
            )

        self.assertEqual(result.status, "handled", msg=getattr(result, "message", None))
        self.assertEqual(
            self.failed_open_close_calls,
            [
                {
                    "browser_url": "http://127.0.0.1:9444",
                    "target_id": "target-failed-open",
                    "timeout_seconds": 3.0,
                }
            ],
        )
        self.assertEqual(self.failed_open_cleanup_schedules, [])
        self.assertEqual(self.close_calls, [])
        self.assertEqual(self.failed_open_targets, [{"id": "target-keep", "type": "page", "url": "https://example.com/keep"}])

    def test_failed_open_cleanup_reschedules_same_target_after_close_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            context = self._context(instance_root)
            self.failed_open_targets = [
                {"id": "target-failed-open", "type": "page", "url": "https://example.com/failed-open"},
            ]
            self.failed_open_close_error = self.handler_module.browser_lifecycle.BrowserLifecycleError("close denied")
            handler = self._failed_open_cleanup_handler()

            result = handler.handle(
                context,
                state=object(),
                runtime=FakeRuntime(),
                trigger=self._failed_open_trigger(target_id="target-failed-open", attempts=1),
            )

        self.assertEqual(result.status, "handled", msg=getattr(result, "message", None))
        self.assertEqual(len(self.failed_open_close_calls), 1)
        self.assertEqual(
            self.failed_open_cleanup_schedules,
            [
                {
                    "instance_root": instance_root,
                    "target_id": "target-failed-open",
                    "url": "https://example.com/failed-open",
                    "attempts": 2,
                    "first_seen_at": "2026-07-07T00:00:00Z",
                }
            ],
        )
        self.assertEqual(self.close_calls, [])

    def test_expiry_payload_requires_page_id(self) -> None:
        inbound = load_module(BROWSER_INBOUND_PATH)
        self.assertEqual(inbound.BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT["required_fields"], ("page_id",))

        trigger = self._trigger(page_id=" ")
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(FakeContext(), state=object(), runtime=FakeRuntime(), trigger=trigger)

        self.assertEqual(result.status, "failed")
        self.assertIn("page_id", result.message)

    def test_expiry_closes_confirmed_mcp_page_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_state(instance_root)
            context = self._context(instance_root)
            self.list_pages_payload = [{"pageId": "page-idle-1", "url": "https://example.com/old", "title": "Old Title"}]
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            self.assertEqual(self.close_calls, [{"browser_endpoint": "http://127.0.0.1:9444", "page_id": "page-idle-1"}])
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["pages"], {})

    def test_expiry_forgets_when_recorded_page_already_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_state(instance_root)
            context = self._context(instance_root)
            self.list_pages_payload = []
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            self.assertEqual(self.close_calls, [])
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["pages"], {})
            self.assertEqual(self.release_calls, [{"instance_root": instance_root, "reason": "page_idle_empty"}])

    def test_expiry_resolves_session_local_page_id_by_recorded_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_state(instance_root, page_id="2", url="https://example.com/search", title="Search")
            context = self._context(instance_root)
            self.list_pages_payload = [
                {"pageId": 1, "url": "https://example.com/search", "title": "Search"},
                {"pageId": 2, "url": "about:blank", "title": "about:blank"},
            ]
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger(page_id="2"))

            self.assertEqual(result.status, "handled")
            self.assertEqual(self.close_calls, [{"browser_endpoint": "http://127.0.0.1:9444", "page_id": 1}])
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["pages"], {})
            self.assertEqual(self.release_calls, [{"instance_root": instance_root, "reason": "page_idle_empty"}])

    def test_expiry_does_not_forget_when_close_verification_still_sees_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_state(instance_root, page_id="1", url="https://example.com/search", title="Search")
            context = self._context(instance_root)
            self.list_pages_payload = [{"pageId": 1, "url": "https://example.com/search", "title": "Search"}]
            self.mcp_list_batches = [
                [{"pageId": 1, "url": "https://example.com/search", "title": "Search"}],
                [{"pageId": 1, "url": "https://example.com/search", "title": "Search"}],
            ]
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger(page_id="1"))

            self.assertEqual(result.status, "failed")
            self.assertIn("still visible", result.message)
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertIn("1", state["pages"])
            self.assertEqual(self.release_calls, [])

    def test_expiry_does_not_close_or_forget_when_recorded_url_matches_multiple_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_state(instance_root, page_id="1", url="https://example.com/search", title="Search")
            context = self._context(instance_root)
            self.list_pages_payload = [
                {"pageId": 1, "url": "https://example.com/search", "title": "Search"},
                {"pageId": 3, "url": "https://example.com/search", "title": "Search"},
            ]
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger(page_id="1"))

            self.assertEqual(result.status, "failed")
            self.assertIn("multiple", result.message)
            self.assertEqual(self.close_calls, [])
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertIn("1", state["pages"])
            self.assertEqual(self.release_calls, [])

    def test_expiry_uses_one_mcp_session_for_list_close_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_state(instance_root, page_id="1", url="https://example.com/search", title="Search")
            context = self._context(instance_root)
            self.list_pages_payload = [{"pageId": 1, "url": "https://example.com/search", "title": "Search"}]
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger(page_id="1"))

            self.assertEqual(result.status, "handled")
            self.assertEqual(len(self.mcp_sessions), 1)
            self.assertEqual(self.mcp_sessions[0].operations, ["list_pages", "close_page", "list_pages"])
            self.assertTrue(self.mcp_sessions[0].closed)

    def test_expiry_keeps_current_selected_page_when_parent_turn_running(self) -> None:
        refresh_calls: list[dict[str, object]] = []

        def fake_refresh_page_idle(**kwargs: object) -> dict[str, object]:
            refresh_calls.append(kwargs)
            return {"idle_refreshed": True, "idle_seconds": 40}

        self.handler_module.browser_lifecycle.refresh_page_idle = fake_refresh_page_idle
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_state(instance_root, current=True)
            context = self._context(instance_root)
            self.list_pages_payload = [{"pageId": "page-idle-1", "url": "https://example.com/old", "title": "Old Title"}]
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(activity_status="running"), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            self.assertEqual(self.close_calls, [])
            self.assertEqual(refresh_calls, [{"instance_root": instance_root, "page_id": "page-idle-1"}])

    def test_final_tracked_page_schedules_release_after_mcp_close(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_state(instance_root)
            context = self._context(instance_root)
            self.list_pages_payload = [{"pageId": "page-idle-1", "url": "https://example.com/old", "title": "Old Title"}]
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            self.assertEqual(self.release_calls, [{"instance_root": instance_root, "reason": "page_idle_empty"}])

    def test_page_expiry_never_calls_cdp_target_close(self) -> None:
        self.assertFalse(hasattr(self.handler_module.browser_lifecycle, "close_page_" + "target"))
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self._write_page_state(instance_root)
            context = self._context(instance_root)
            self.list_pages_payload = [{"pageId": "page-idle-1", "url": "https://example.com/old", "title": "Old Title"}]
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            self.assertEqual(len(self.close_calls), 1)

    def test_stale_due_trigger_does_not_close_recently_refreshed_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self.handler_module.browser_lifecycle._write_page_idle_state(
                instance_root,
                {
                    "pages": {
                        "page-idle-1": {
                            "page_id": "page-idle-1",
                            "url": "https://example.com/old",
                            "title": "Old Title",
                            "last_used_at": "2026-06-24T00:04:30Z",
                        }
                    }
                },
            )
            context = self._context(instance_root)
            self.list_pages_payload = [{"pageId": "page-idle-1", "url": "https://example.com/old", "title": "Old Title"}]
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(
                context,
                state=object(),
                runtime=FakeRuntime(activity_status="idle"),
                trigger=self._trigger(due_at="2026-06-24T00:05:00Z"),
            )

            self.assertEqual(result.status, "handled")
            self.assertEqual(self.close_calls, [])
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertIn("page-idle-1", state["pages"])

    def test_inbound_contract_requires_only_page_id(self) -> None:
        inbound = load_module(BROWSER_INBOUND_PATH)

        self.assertEqual(inbound.BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT["required_fields"], ("page_id",))

    def test_inbound_registers_browser_release_event(self) -> None:
        inbound = load_module(BROWSER_INBOUND_PATH)

        registrations = inbound.inbound_registrations()

        by_type = {registration.event_type: registration for registration in registrations}
        self.assertIn("browser.page.expired", by_type)
        self.assertIn("browser.cockpit.release", by_type)
        self.assertIn("browser.failed_open_page.cleanup", by_type)
        self.assertEqual(by_type["browser.cockpit.release"].payload_contract["required_fields"], ("reason",))
        self.assertEqual(by_type["browser.failed_open_page.cleanup"].payload_contract["required_fields"], ("target_id",))

    def test_handler_rejects_wrong_target_actor(self) -> None:
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(
            FakeContext(),
            state=object(),
            runtime=FakeRuntime(),
            trigger=self._trigger(target_identity_route={"role_id": "pm", "actor_id": "act-pm-browser"}),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target identity", result.message)

    def test_run_mcp_tool_waits_for_initialize_before_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            stub_path = Path(temp_root) / "staged_mcp.py"
            stub_path.write_text(
                "\n".join(
                    [
                        "import json, select, sys",
                        "first = sys.stdin.readline()",
                        "if not first:",
                        "    raise SystemExit(1)",
                        "ready, _, _ = select.select([sys.stdin], [], [], 0.05)",
                        "if ready:",
                        "    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': 'init', 'result': {'protocolVersion': '2024-11-05'}}) + '\\n')",
                        "    sys.stdout.flush()",
                        "    raise SystemExit(0)",
                        "init = json.loads(first)",
                        "sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': init['id'], 'result': {'protocolVersion': '2024-11-05'}}) + '\\n')",
                        "sys.stdout.flush()",
                        "for raw in sys.stdin:",
                        "    message = json.loads(raw)",
                        "    if message.get('method') == 'tools/call':",
                        "        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'result': {'content': [{'type': 'text', 'text': '## Pages\\n2: https://example.test [selected]'}]}}) + '\\n')",
                        "        sys.stdout.flush()",
                        "        raise SystemExit(0)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            command = f"{shlex.quote(PYTHON)} {shlex.quote(str(stub_path))}"

            self.handler_module.open_mcp_session = self.handler_module.McpToolSession
            with mock.patch.dict(os.environ, {"BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_COMMAND": command}):
                message = self.handler_module._run_mcp_tool("http://127.0.0.1:9444", "list_pages", {})

            self.assertIn("## Pages", self.handler_module._tool_response_text(message))


class BrowserReleaseHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.release_module = load_module(RELEASE_HANDLER_PATH)
        self.triggers = load_module(TRIGGERS_PATH)
        lifecycle = self.release_module.browser_lifecycle
        self._original_read_page_targets = lifecycle.read_page_targets
        self.addCleanup(setattr, lifecycle, "read_page_targets", self._original_read_page_targets)

    def _trigger(self, *, reason: str = "page_idle_empty", target_identity_route: dict[str, str] | None = None) -> Any:
        return self.triggers.DaemonTrigger(
            source="scheduled_trigger",
            type="browser.cockpit.release",
            target_identity_id=(target_identity_route or {"actor_id": "act-dev-browser"})["actor_id"],
            target_role_id=(target_identity_route or {"role_id": "dev"})["role_id"],
            origin_id="schedule-release",
            correlation_id=None,
            payload={"reason": reason},
            source_context={"schedule_id": "schedule-release", "owner": "browser"},
        )

    def _context(self, instance_root: Path, *, browser_port: int | None = 9444) -> Any:
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps(
                {
                    "actor_id": "act-dev-browser",
                    "role": "dev",
                    "instance_root": str(instance_root),
                    "workspace_dir": str(instance_root / "workspace"),
                    "thread_id": "thr-main",
                    "browser_port": browser_port,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        context = FakeContext()
        context.instance_root = instance_root
        context.instance_json = instance_json
        context.instance_payload = {"browser_port": None}
        return context

    def _write_page_idle(self, instance_root: Path, pages: dict[str, object]) -> None:
        state_path = instance_root / "runtime" / "browser" / "page_idle.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"pages": pages}, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _install_manager_recorder(self, result: dict[str, object] | None = None) -> list[dict[str, object]]:
        calls: list[dict[str, object]] = []
        had_manager = hasattr(self.release_module, "browser_runtime_manager")
        original_manager = getattr(self.release_module, "browser_runtime_manager", None)

        class FakeBrowserRuntimeManager:
            @staticmethod
            def release(**kwargs: object) -> dict[str, object]:
                calls.append(dict(kwargs))
                if result is not None:
                    return dict(result)
                return {
                    "ok": True,
                    "handled": True,
                    "skip_reason": None,
                    "state_changed": True,
                    "durability": "runtime",
                }

        self.release_module.browser_runtime_manager = FakeBrowserRuntimeManager
        if had_manager:
            self.addCleanup(setattr, self.release_module, "browser_runtime_manager", original_manager)
        else:
            self.addCleanup(delattr, self.release_module, "browser_runtime_manager")
        return calls

    def _install_cdp_targets(self, targets: list[dict[str, object]]) -> None:
        if hasattr(self.release_module, "browser_lifecycle"):
            self.release_module.browser_lifecycle.read_page_targets = lambda *_args, **_kwargs: targets

    def test_manager_release_uses_browser_runtime_manager_directly(self) -> None:
        manager_calls: list[dict[str, object]] = []

        class FakeBrowserRuntimeManager:
            @staticmethod
            def release(**kwargs: object) -> dict[str, object]:
                manager_calls.append(dict(kwargs))
                return {
                    "ok": True,
                    "handled": True,
                    "skip_reason": None,
                    "state_changed": True,
                    "durability": "runtime",
                }

        self.release_module.browser_runtime_manager = FakeBrowserRuntimeManager
        self.addCleanup(delattr, self.release_module, "browser_runtime_manager")

        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled", msg=getattr(result, "message", None))
        self.assertEqual(len(manager_calls), 1)
        self.assertEqual(manager_calls[0]["actor_id"], "act-dev-browser")
        self.assertEqual(manager_calls[0]["reason"], "page_idle_empty")

    def test_release_noops_when_parent_turn_running(self) -> None:
        calls = self._install_manager_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(activity_status="running"), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [])

    def test_release_noops_when_page_idle_pages_remain(self) -> None:
        calls = self._install_manager_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {"page-active": {"page_id": "page-active"}})
            self._install_cdp_targets([])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [])

    def test_release_handler_calls_manager_when_browser_port_missing(self) -> None:
        calls = self._install_manager_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser", browser_port=None)
            self._write_page_idle(context.instance_root, {})
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["actor_id"], "act-dev-browser")
        self.assertEqual(calls[0]["reason"], "page_idle_empty")

    def test_release_noops_when_cdp_has_real_user_page(self) -> None:
        calls = self._install_manager_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([{"id": "target-user", "type": "page", "url": "https://example.com/open"}])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [])

    def test_release_logs_skip_reason_when_real_user_page_exists(self) -> None:
        calls = self._install_manager_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([{"id": "target-user", "type": "page", "url": "https://example.com/open"}])
            handler = self.release_module.BrowserReleaseHandler()
            with mock.patch.object(self.release_module.sys, "stderr") as stderr:
                result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [])
        self.assertTrue(stderr.write.called)
        written = "".join(str(call.args[0]) for call in stderr.write.call_args_list if call.args)
        self.assertIn("Browser cockpit release skipped: real_user_page_present", written)

    def test_release_invokes_manager_after_rechecks_pass(self) -> None:
        calls = self._install_manager_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([{"id": "target-blank", "type": "page", "url": "about:blank"}])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["actor_id"], "act-dev-browser")
        self.assertEqual(calls[0]["reason"], "page_idle_empty")

    def test_release_surfaces_manager_failure(self) -> None:
        calls = self._install_manager_recorder({"ok": False, "error": {"message": "manager release failed"}})
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([{"id": "target-blank", "type": "page", "url": "about:blank"}])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "failed")
        self.assertIn("manager release failed", result.message)
        self.assertEqual(len(calls), 1)

    def test_release_manager_uses_instance_root_when_actor_home_is_bound(self) -> None:
        calls = self._install_manager_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / ".codex-buddyswitch"
            context = self._context(shared_root / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([{"id": "target-blank", "type": "page", "url": "about:blank"}])
            handler = self.release_module.BrowserReleaseHandler()
            with mock.patch.dict(
                os.environ,
                {
                    "HOME": str(context.instance_root / "home"),
                    "CODEX_HOME": str(context.instance_root / "codex-home"),
                },
                clear=False,
            ):
                os.environ.pop("BUDDYSWITCH_SHARED_ROOT", None)
                os.environ.pop("BUDDYSWITCH_SOURCE_HOME", None)

                result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["instance_root"], context.instance_root)
        self.assertEqual(calls[0]["actor_id"], "act-dev-browser")
        self.assertEqual(calls[0]["reason"], "page_idle_empty")

    def test_release_rejects_wrong_target_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(
                context,
                state=object(),
                runtime=FakeRuntime(),
                trigger=self._trigger(target_identity_route={"role_id": "pm", "actor_id": "act-pm-browser"}),
            )

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target identity", result.message)


if __name__ == "__main__":
    unittest.main()
