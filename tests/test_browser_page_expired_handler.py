#!/usr/bin/env python3
"""Tests for browser.page.expired daemon handler."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any
from unittest import mock


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
        lifecycle = self.handler_module.browser_lifecycle
        originals = {
            "close_page_target": lifecycle.close_page_target,
            "schedule_browser_cockpit_release": lifecycle.schedule_browser_cockpit_release,
            "current_target_id": lifecycle.current_target_id,
            "refresh_current_page_idle": lifecycle.refresh_current_page_idle,
        }
        self.addCleanup(lambda: [setattr(lifecycle, name, value) for name, value in originals.items()])

    def _trigger(
        self,
        *,
        target_actor_address: dict[str, str] | None = None,
        due_at: str | None = None,
    ) -> Any:
        source_context = {"schedule_id": "schedule-1"}
        if due_at is not None:
            source_context["due_at"] = due_at
        return self.triggers.DaemonTrigger(
            source="scheduled_trigger",
            type="browser.page.expired",
            target_actor_address=target_actor_address or {"role_id": "dev", "actor_id": "act-dev-browser"},
            origin_id="schedule-1",
            correlation_id=None,
            payload={"target_id": "target-idle-1"},
            source_context=source_context,
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
            self.handler_module.browser_lifecycle.schedule_browser_cockpit_release = lambda **_kwargs: {
                "schedule": {"schedule_id": "schedule-release"}
            }
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["targets"], {})
            self.assertEqual(state["page_id_to_target_id"], {})
            self.assertNotIn("current_target_id", state)

    def test_final_tracked_page_schedules_release_after_close(self) -> None:
        release_calls: list[dict[str, object]] = []
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
                        }
                    },
                    "page_id_to_target_id": {},
                },
            )
            context = FakeContext()
            context.instance_root = instance_root

            def fake_close_page_target(_browser_url: str, target_id: str) -> dict[str, str]:
                return {"status": "closed", "target_id": target_id}

            def fake_schedule_browser_cockpit_release(**kwargs: object) -> dict[str, object]:
                release_calls.append(kwargs)
                return {"schedule": {"schedule_id": "schedule-release"}}

            self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
            self.handler_module.browser_lifecycle.schedule_browser_cockpit_release = fake_schedule_browser_cockpit_release
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            self.assertEqual(release_calls, [{"instance_root": instance_root, "reason": "page_idle_empty"}])

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
            self.handler_module.browser_lifecycle.schedule_browser_cockpit_release = lambda **_kwargs: {
                "schedule": {"schedule_id": "schedule-release"}
            }
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["targets"], {})
            self.assertEqual(state["page_id_to_target_id"], {})

    def test_stale_endpoint_forgets_target_and_schedules_release(self) -> None:
        release_calls: list[dict[str, object]] = []
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
                        }
                    },
                    "page_id_to_target_id": {},
                },
            )
            context = FakeContext()
            context.instance_root = instance_root

            def fake_close_page_target(_browser_url: str, _target_id: str) -> dict[str, str]:
                raise self.handler_module.browser_lifecycle.BrowserLifecycleError(
                    "failed to read Chrome DevTools /json/list: connection refused"
                )

            def fake_schedule_browser_cockpit_release(**kwargs: object) -> dict[str, object]:
                release_calls.append(kwargs)
                return {"schedule": {"schedule_id": "schedule-release"}}

            self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
            self.handler_module.browser_lifecycle.schedule_browser_cockpit_release = fake_schedule_browser_cockpit_release
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["targets"], {})
            self.assertNotIn("current_target_id", state)
            self.assertEqual(release_calls, [{"instance_root": instance_root, "reason": "page_idle_empty"}])

    def test_auto_close_browser_unavailable_is_handled_as_stale(self) -> None:
        def fake_close_page_target(_browser_url: str, _target_id: str) -> dict[str, str]:
            raise self.handler_module.browser_lifecycle.BrowserLifecycleError(
                "failed to read Chrome DevTools /json/list: connection refused"
            )

        self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
        handler = self.handler_module.BrowserPageExpiredHandler()

        result = handler.handle(FakeContext(), state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")

    def test_expiry_reads_fresh_browser_port_from_instance_json(self) -> None:
        calls: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            instance_root.mkdir(parents=True)
            instance_json = instance_root / "instance.json"
            instance_json.write_text(
                json.dumps(
                    {
                        "actor_id": "act-dev-browser",
                        "role": "dev",
                        "browser_port": 9555,
                    },
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )
            context = FakeContext()
            context.instance_payload = {"browser_port": None}
            context.instance_root = instance_root
            context.instance_json = instance_json

            def fake_close_page_target(browser_url: str, target_id: str) -> dict[str, str]:
                calls.append({"browser_url": browser_url, "target_id": target_id})
                return {"status": "already_gone", "target_id": target_id}

            self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
            self.handler_module.browser_lifecycle.schedule_browser_cockpit_release = lambda **_kwargs: {
                "schedule": {"schedule_id": "schedule-release"}
            }
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

            self.assertEqual(result.status, "handled")
            self.assertEqual(calls, [{"browser_url": "http://127.0.0.1:9555", "target_id": "target-idle-1"}])

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

    def test_stale_due_trigger_does_not_close_recently_refreshed_target(self) -> None:
        calls: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-dev-browser"
            self.handler_module.browser_lifecycle._write_page_idle_state(
                instance_root,
                {
                    "targets": {
                        "target-idle-1": {
                            "target_id": "target-idle-1",
                            "target_url": "https://example.com/recent",
                            "last_used_at": "2026-06-24T00:04:30Z",
                        }
                    },
                    "page_id_to_target_id": {},
                },
            )
            context = FakeContext()
            context.instance_root = instance_root

            def fake_close_page_target(browser_url: str, target_id: str) -> dict[str, str]:
                calls.append({"browser_url": browser_url, "target_id": target_id})
                return {"status": "closed", "target_id": target_id}

            self.handler_module.browser_lifecycle.close_page_target = fake_close_page_target
            handler = self.handler_module.BrowserPageExpiredHandler()

            result = handler.handle(
                context,
                state=object(),
                runtime=FakeRuntime(activity_status="idle"),
                trigger=self._trigger(due_at="2026-06-24T00:05:00Z"),
            )

            self.assertEqual(result.status, "handled")
            self.assertEqual(calls, [])
            state = json.loads(self.handler_module.browser_lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertIn("target-idle-1", state["targets"])

    def test_inbound_contract_requires_only_target_id(self) -> None:
        inbound = load_module(BROWSER_INBOUND_PATH)

        self.assertEqual(inbound.BROWSER_PAGE_EXPIRED_PAYLOAD_CONTRACT["required_fields"], ("target_id",))

    def test_inbound_registers_browser_release_event(self) -> None:
        inbound = load_module(BROWSER_INBOUND_PATH)

        registrations = inbound.inbound_registrations()

        by_type = {registration.event_type: registration for registration in registrations}
        self.assertIn("browser.page.expired", by_type)
        self.assertIn("browser.cockpit.release", by_type)
        self.assertEqual(by_type["browser.cockpit.release"].payload_contract["required_fields"], ("reason",))

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


class BrowserReleaseHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.release_module = load_module(RELEASE_HANDLER_PATH)
        self.triggers = load_module(TRIGGERS_PATH)
        self._original_subprocess_run = subprocess.run
        self.addCleanup(setattr, subprocess, "run", self._original_subprocess_run)
        lifecycle = self.release_module.browser_lifecycle
        self._original_read_page_targets = lifecycle.read_page_targets
        self.addCleanup(setattr, lifecycle, "read_page_targets", self._original_read_page_targets)

    def _trigger(self, *, reason: str = "page_idle_empty", target_actor_address: dict[str, str] | None = None) -> Any:
        return self.triggers.DaemonTrigger(
            source="scheduled_trigger",
            type="browser.cockpit.release",
            target_actor_address=target_actor_address or {"role_id": "dev", "actor_id": "act-dev-browser"},
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

    def _write_page_idle(self, instance_root: Path, targets: dict[str, object]) -> None:
        state_path = instance_root / "runtime" / "browser" / "page_idle.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"targets": targets, "page_id_to_target_id": {}}, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _install_launcher_recorder(self, returncode: int = 0) -> list[list[str]]:
        calls: list[list[str]] = []
        if not hasattr(self.release_module, "subprocess"):
            return calls

        class Completed:
            def __init__(self, code: int) -> None:
                self.returncode = code
                self.stdout = ""
                self.stderr = "release failed" if code else ""

        def fake_run(argv: list[str], **_kwargs: object) -> Completed:
            calls.append([str(item) for item in argv])
            return Completed(returncode)

        self.release_module.subprocess.run = fake_run
        return calls

    def _install_cdp_targets(self, targets: list[dict[str, object]]) -> None:
        if hasattr(self.release_module, "browser_lifecycle"):
            self.release_module.browser_lifecycle.read_page_targets = lambda *_args, **_kwargs: targets

    def test_release_noops_when_parent_turn_running(self) -> None:
        calls = self._install_launcher_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(activity_status="running"), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [])

    def test_release_noops_when_page_idle_targets_remain(self) -> None:
        calls = self._install_launcher_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {"target-active": {"target_id": "target-active"}})
            self._install_cdp_targets([])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [])

    def test_release_noops_when_browser_port_missing(self) -> None:
        calls = self._install_launcher_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser", browser_port=None)
            self._write_page_idle(context.instance_root, {})
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [])

    def test_release_noops_when_cdp_has_real_user_page(self) -> None:
        calls = self._install_launcher_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([{"id": "target-user", "type": "page", "url": "https://example.com/open"}])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(calls, [])

    def test_release_invokes_launcher_after_rechecks_pass(self) -> None:
        calls = self._install_launcher_recorder()
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            self._write_page_idle(context.instance_root, {})
            self._install_cdp_targets([{"id": "target-blank", "type": "page", "url": "about:blank"}])
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(context, state=object(), runtime=FakeRuntime(), trigger=self._trigger())

        self.assertEqual(result.status, "handled")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-5:], ["env", "browser", "release", "--instance", "act-dev-browser"])

    def test_release_launcher_env_uses_shared_root_from_instance_root_when_actor_home_is_bound(self) -> None:
        captured: dict[str, Any] = {}

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(argv: list[str], **kwargs: object) -> Completed:
            captured["argv"] = [str(item) for item in argv]
            captured["env"] = dict(kwargs.get("env")) if isinstance(kwargs.get("env"), dict) else {}
            return Completed()

        self.release_module.subprocess.run = fake_run
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
        self.assertEqual(captured["argv"][-5:], ["env", "browser", "release", "--instance", "act-dev-browser"])
        env = captured["env"]
        self.assertEqual(env["BUDDYSWITCH_SHARED_ROOT"], str(shared_root))
        self.assertEqual(env["BUDDYSWITCH_SOURCE_HOME"], str(shared_root.parent))
        self.assertEqual(env["BUDDYSWITCH_REPO_ROOT"], str(ROOT))
        self.assertEqual(env["HOME"], str(context.instance_root / "home"))

    def test_release_rejects_wrong_target_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            context = self._context(Path(temp_root) / "instances" / "act-dev-browser")
            handler = self.release_module.BrowserReleaseHandler()

            result = handler.handle(
                context,
                state=object(),
                runtime=FakeRuntime(),
                trigger=self._trigger(target_actor_address={"role_id": "pm", "actor_id": "act-pm-browser"}),
            )

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target actor", result.message)


if __name__ == "__main__":
    unittest.main()
