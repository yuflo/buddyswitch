#!/usr/bin/env python3
"""Tests for shared Chrome DevTools browser lifecycle helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SESSION_PATH = ROOT / "scripts" / "env" / ("cdp_browser_" + "session.py")
LIFECYCLE_PATH = ROOT / "scripts" / "env" / "cdp_browser_lifecycle.py"
MODULE_COUNTER = count()
LEGACY_CURRENT_TARGET_FIELD = "current_" + "target_id"
LEGACY_PAGE_TARGET_MAP_FIELD = "page_id_to_" + "target_id"
LEGACY_TARGETS_FIELD = "tar" + "gets"


def load_lifecycle() -> Any:
    if not LIFECYCLE_PATH.exists():
        raise AssertionError(f"expected module to exist: {LIFECYCLE_PATH}")
    module_name = f"buddyswitch_cdp_browser_lifecycle_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, LIFECYCLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {LIFECYCLE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class CdpBrowserLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lifecycle = load_lifecycle()
        original_schedule_trigger = self.lifecycle.daemon_client.schedule_trigger
        original_utc_now = self.lifecycle._utc_now
        self.addCleanup(setattr, self.lifecycle.daemon_client, "schedule_trigger", original_schedule_trigger)
        self.addCleanup(setattr, self.lifecycle, "_utc_now", original_utc_now)

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

    def test_mark_current_page_waits_for_page_idle_state_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / "act-browser"
            lock_path = instance_root / "runtime" / "browser" / "page_idle.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_file = lock_path.open("a+", encoding="utf-8")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            script = """
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
instance_root = Path(sys.argv[2])
sys.path.insert(0, str(repo_root / "scripts" / "env"))

import cdp_browser_lifecycle as lifecycle

lifecycle.mark_current_page(
    instance_root=instance_root,
    page_id="page-lock-wait",
    target_url="https://example.com/locked",
)
print("done", flush=True)
"""
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(ROOT), str(instance_root)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    process.communicate(timeout=0.25)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=2)
                self.assertEqual(process.returncode, 0, msg=stderr)
                self.assertIn("done", stdout)
            finally:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
                lock_file.close()
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=2)

            state = json.loads(self.lifecycle.page_idle_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(state["current_page_id"], "page-lock-wait")


class BrowserLifecycleTests(unittest.TestCase):
    def test_actor_page_cdp_open_close_helpers_are_removed_or_readiness_scoped(self) -> None:
        self.assertFalse(SESSION_PATH.exists(), "actor page CDP session helper should not remain as a live module")
        lifecycle_source = LIFECYCLE_PATH.read_text(encoding="utf-8")
        forbidden = (
            "def create_background_page_" + "target",
            "def close_page_" + "target",
            "Target." + "closeTarget",
            "target_idle_expiry_after_" + "due_at",
            "forget_page_idle_" + "target",
            LEGACY_CURRENT_TARGET_FIELD,
            LEGACY_PAGE_TARGET_MAP_FIELD,
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, lifecycle_source)

        manager_source = (ROOT / "tools" / "launcher" / "browser_runtime_manager.py").read_text(encoding="utf-8")
        self.assertIn("cdp_background_page", manager_source)
        self.assertNotIn("create_background_page_" + "target", manager_source)


if __name__ == "__main__":
    unittest.main()
