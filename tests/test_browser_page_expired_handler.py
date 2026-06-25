#!/usr/bin/env python3
"""Tests for browser.page.expired daemon handler."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

HANDLER_PATH = ROOT / "tools" / "launcher" / "browser_page_expired_handler.py"
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
    actor_address = {"role_id": "dev", "actor_id": "act-dev-browser"}
    actor_id = "act-dev-browser"
    role = "dev"
    instance_payload = {"browser_port": 9444}
    instance_root = Path("/tmp/buddyswitch-test-instance")


class FakeRuntime:
    def __init__(self, *, activity_status: str = "idle") -> None:
        self.activity_status = activity_status
        self.parent_prompts: list[dict[str, object]] = []

    def parent_activity(self) -> dict[str, object]:
        return {"status": self.activity_status}

    def submit_parent_prompt(
        self,
        text: str,
        *,
        handler_name: str,
        origin_id: str | None,
        interrupt_policy: str = "none",
    ) -> dict[str, object]:
        self.parent_prompts.append(
            {
                "text": text,
                "handler_name": handler_name,
                "origin_id": origin_id,
                "interrupt_policy": interrupt_policy,
            }
        )
        return {"turn_id": "turn-browser-ttl"}


class BrowserPageExpiredHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handler_module = load_module(HANDLER_PATH)
        self.triggers = load_module(TRIGGERS_PATH)

    def _trigger(
        self,
        *,
        target_actor_address: dict[str, str] | None = None,
    ) -> Any:
        return self.triggers.DaemonTrigger(
            source="scheduled_trigger",
            type="browser.page.expired",
            target_actor_address=target_actor_address or {"role_id": "dev", "actor_id": "act-dev-browser"},
            origin_id="schedule-1",
            correlation_id=None,
            payload={"target_id": "target-idle-1"},
            source_context={"schedule_id": "schedule-1"},
        )

    def test_auto_close_closes_existing_target_by_target_id(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_close_page_target(browser_url: str, target_id: str) -> dict[str, str]:
            calls.append({"browser_url": browser_url, "target_id": target_id})
            return {"status": "closed", "target_id": target_id}

        self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(FakeContext(), state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [{"browser_url": "http://127.0.0.1:9444", "target_id": "target-idle-1"}])

    def test_auto_close_missing_target_is_handled(self) -> None:
        def fake_close_page_target(_browser_url: str, target_id: str) -> dict[str, str]:
            return {"status": "already_gone", "target_id": target_id}

        self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(FakeContext(), state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")

    def test_expiry_close_forgets_idle_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self.handler_module.browser_lifecycle._write_page_idle_state(
                instance_root,
                {
                    "current_target_id": "target-idle-1",
                    "current_page_updated_at": "2026-06-24T00:00:00Z",
                    "targets": {
                        "target-idle-1": {
                            "target_id": "target-idle-1",
                            "target_url": "https://example.com/old",
                            "last_used_at": "2026-06-24T00:00:00Z",
                            "page_id": "7",
                        }
                    },
                    "page_id_to_target_id": {"7": "target-idle-1"},
                },
            )
            context = FakeContext()
            context.instance_root = instance_root

            def fake_close_page_target(_browser_url: str, target_id: str) -> dict[str, str]:
                return {"status": "closed", "target_id": target_id}

            self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["targets"], {})
            self.assertEqual(state["page_id_to_target_id"], {})
            self.assertNotIn("current_target_id", state)

    def test_expiry_already_gone_forgets_idle_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self.handler_module.browser_lifecycle._write_page_idle_state(
                instance_root,
                {
                    "targets": {
                        "target-idle-1": {
                            "target_id": "target-idle-1",
                            "target_url": "https://example.com/old",
                            "last_used_at": "2026-06-24T00:00:00Z",
                            "page_id": "7",
                        }
                    },
                    "page_id_to_target_id": {"7": "target-idle-1"},
                },
            )
            context = FakeContext()
            context.instance_root = instance_root

            def fake_close_page_target(_browser_url: str, target_id: str) -> dict[str, str]:
                return {"status": "already_gone", "target_id": target_id}

            self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["targets"], {})
            self.assertEqual(state["page_id_to_target_id"], {})

    def test_auto_close_browser_unavailable_is_handled_as_stale(self) -> None:
        def fake_close_page_target(_browser_url: str, _target_id: str) -> dict[str, str]:
            raise self.handler_module.browser_lifecycle.BrowserLifecycleError(
                "failed to read Chrome DevTools /json/list: connection refused"
            )

        self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(FakeContext(), state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")

    def test_auto_close_close_failure_returns_failed_once(self) -> None:
        def fake_close_page_target(_browser_url: str, _target_id: str) -> dict[str, str]:
            raise self.handler_module.browser_lifecycle.BrowserLifecycleError("simulated close failure")

        self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(FakeContext(), state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.message, "simulated close failure")

    def test_current_page_with_running_parent_turn_refreshes_idle_without_closing(self) -> None:
        close_calls: list[dict[str, object]] = []
        refresh_calls: list[dict[str, object]] = []

        self.handler_module.browser_lifecycle.current_target_id = lambda _instance_root: "target-idle-1"

        def fake_refresh_current_page_idle(**kwargs: object) -> dict[str, object]:
            refresh_calls.append(kwargs)
            return {"idle_refreshed": True, "idle_seconds": 300}

        def fake_close_page_target(browser_url: str, target_id: str) -> dict[str, str]:
            close_calls.append({"browser_url": browser_url, "target_id": target_id})
            return {"status": "closed", "target_id": target_id}

        self.handler_module.browser_lifecycle.refresh_current_page_idle = fake_refresh_current_page_idle
        self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(FakeContext(), state=object(), runtime=FakeRuntime(activity_status="running"), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(close_calls, [])
        self.assertEqual(refresh_calls, [{"instance_root": FakeContext.instance_root, "target_id": "target-idle-1"}])

    def test_non_current_page_closes_even_when_parent_turn_is_running(self) -> None:
        calls: list[dict[str, object]] = []
        self.handler_module.browser_lifecycle.current_target_id = lambda _instance_root: "target-other"

        def fake_close_page_target(browser_url: str, target_id: str) -> dict[str, str]:
            calls.append({"browser_url": browser_url, "target_id": target_id})
            return {"status": "closed", "target_id": target_id}

        self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(FakeContext(), state=object(), runtime=FakeRuntime(activity_status="running"), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [{"browser_url": "http://127.0.0.1:9444", "target_id": "target-idle-1"}])

    def test_current_page_closes_when_parent_is_idle(self) -> None:
        calls: list[dict[str, object]] = []
        self.handler_module.browser_lifecycle.current_target_id = lambda _instance_root: "target-idle-1"

        def fake_close_page_target(browser_url: str, target_id: str) -> dict[str, str]:
            calls.append({"browser_url": browser_url, "target_id": target_id})
            return {"status": "closed", "target_id": target_id}

        self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(FakeContext(), state=object(), runtime=FakeRuntime(activity_status="idle"), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [{"browser_url": "http://127.0.0.1:9444", "target_id": "target-idle-1"}])

    def test_inbound_contract_requires_only_target_id(self) -> None:
        inbound = load_module(BROWSER_INBOUND_PATH)

        self.assertEqual(inbound.BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT["required_fields"], ("target_id",))

    def test_handler_rejects_wrong_target_actor(self) -> None:
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(
            FakeContext(),
            state=object(),
            runtime=FakeRuntime(),
            trigger=self._trigger(target_actor_address={"role_id": "pm", "actor_id": "act-pm-browser"}),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target actor", result.message)


if __name__ == "__main__":
    unittest.main()
