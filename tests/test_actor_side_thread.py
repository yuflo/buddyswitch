#!/usr/bin/env python3
"""Tests for capability-aware side-thread creation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HELPER_DIR = ROOT / "tools" / "launcher"
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

import actor_capability  # noqa: E402
import actor_side_thread  # noqa: E402


class ActorSideThreadTests(unittest.TestCase):
    def _instance_json(self, temp_root: Path) -> Path:
        instance_root = temp_root / "instances" / "act-dev-test"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps({"actor_id": "act-dev-test", "instance_root": str(instance_root)}) + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _start_kwargs(self, instance_json: Path) -> dict[str, Any]:
        return {
            "socket_path": Path("/tmp/app-server.sock"),
            "instance_json": instance_json,
            "actor_id": "act-dev-test",
            "parent_thread_id": "thread-main",
            "text": "side prompt",
            "purpose": "host_control.side",
            "workspace_dir": Path("/tmp/workspace"),
            "shared_project_workspace_dir": Path("/tmp/project"),
            "permissions": "buddyswitch-runtime",
        }

    def _install_start(self) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        original_start = actor_side_thread.side_thread_lifecycle.start_side_thread

        def fake_start(**kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {
                "action": "start",
                "side_thread_id": "thread-side-1",
                "turn_id": "turn-side-1",
            }

        self.addCleanup(setattr, actor_side_thread.side_thread_lifecycle, "start_side_thread", original_start)
        actor_side_thread.side_thread_lifecycle.start_side_thread = fake_start
        return calls

    def test_saved_fast_side_passes_luna_xhigh_to_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            actor_capability.seed_actor_capabilities(instance_json)
            calls = self._install_start()

            result = actor_side_thread.start_actor_side_thread(**self._start_kwargs(instance_json))

            self.assertEqual(calls[0]["model"], "gpt-5.6-luna")
            self.assertEqual(calls[0]["model_reasoning_effort"], "xhigh")
            self.assertEqual(result["capability_level"], "fast")
            self.assertEqual(result["capability_source"], "actor_config")
            self.assertEqual(result["capability_durability"], "thread_fork_only")

    def test_explicit_deep_level_uses_same_catalog_for_one_new_side(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            actor_capability.seed_actor_capabilities(instance_json)
            calls = self._install_start()
            kwargs = self._start_kwargs(instance_json)
            kwargs["capability_level"] = "deep"

            result = actor_side_thread.start_actor_side_thread(**kwargs)

            self.assertEqual(calls[0]["model"], "gpt-5.6-sol")
            self.assertEqual(calls[0]["model_reasoning_effort"], "xhigh")
            self.assertEqual(result["capability_level"], "deep")
            self.assertEqual(result["capability_source"], "override")
            self.assertEqual(result["capability_durability"], "thread_fork_only")

    def test_invalid_explicit_level_fails_before_lifecycle_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            actor_capability.seed_actor_capabilities(instance_json)
            calls = self._install_start()
            kwargs = self._start_kwargs(instance_json)
            kwargs["capability_level"] = "custom"

            with self.assertRaisesRegex(actor_side_thread.ActorSideThreadError, "side capability invalid"):
                actor_side_thread.start_actor_side_thread(**kwargs)

            self.assertEqual(calls, [])

    def test_missing_capability_config_fails_before_lifecycle_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            original_start = actor_side_thread.side_thread_lifecycle.start_side_thread

            def fail(**_kwargs: Any) -> dict[str, Any]:
                raise AssertionError("missing capability config must fail before lifecycle")

            self.addCleanup(setattr, actor_side_thread.side_thread_lifecycle, "start_side_thread", original_start)
            actor_side_thread.side_thread_lifecycle.start_side_thread = fail

            with self.assertRaisesRegex(actor_side_thread.ActorSideThreadError, "side capability invalid"):
                actor_side_thread.start_actor_side_thread(**self._start_kwargs(instance_json))


if __name__ == "__main__":
    unittest.main()
