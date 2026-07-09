#!/usr/bin/env python3
"""Tests for actor-aware side-thread creation."""

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

import actor_side_thread  # noqa: E402


class ActorSideThreadTests(unittest.TestCase):
    def _instance_json(self, temp_root: Path) -> Path:
        instance_root = temp_root / "instances" / "act-dev-test"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps({"actor_id": "act-dev-test", "instance_root": str(instance_root)}, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _write_model_config(self, instance_json: Path, payload: dict[str, object]) -> None:
        (instance_json.parent / "model-config.json").write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

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

    def test_configured_side_passes_model_and_effort_to_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_model_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {},
                    "side": {"model": "gpt-5.4-mini", "effort": "medium"},
                },
            )
            calls: list[dict[str, Any]] = []
            original_start = actor_side_thread.side_thread_lifecycle.start_side_thread

            def fake_start(**kwargs: Any) -> dict[str, Any]:
                calls.append(kwargs)
                return {
                    "action": "start",
                    "side_thread_id": "thread-side-1",
                    "turn_id": "turn-side-1",
                    "model_source": "override",
                    "model_reasoning_effort_source": "override",
                }

            self.addCleanup(setattr, actor_side_thread.side_thread_lifecycle, "start_side_thread", original_start)
            actor_side_thread.side_thread_lifecycle.start_side_thread = fake_start

            result = actor_side_thread.start_actor_side_thread(**self._start_kwargs(instance_json))

            self.assertEqual(calls[0]["model"], "gpt-5.4-mini")
            self.assertEqual(calls[0]["model_reasoning_effort"], "medium")
            self.assertEqual(result["model"], "gpt-5.4-mini")
            self.assertEqual(result["model_reasoning_effort"], "medium")
            self.assertEqual(result["model_source"], "actor_config")
            self.assertEqual(result["model_reasoning_effort_source"], "actor_config")
            self.assertEqual(result["model_config_durability"], "thread_fork_only")

    def test_explicit_side_values_override_config_field_by_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_model_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {},
                    "side": {"model": "gpt-5.4-mini", "effort": "medium"},
                },
            )
            calls: list[dict[str, Any]] = []
            original_start = actor_side_thread.side_thread_lifecycle.start_side_thread

            def fake_start(**kwargs: Any) -> dict[str, Any]:
                calls.append(kwargs)
                return {"action": "start", "side_thread_id": "thread-side-1", "turn_id": "turn-side-1"}

            self.addCleanup(setattr, actor_side_thread.side_thread_lifecycle, "start_side_thread", original_start)
            actor_side_thread.side_thread_lifecycle.start_side_thread = fake_start

            kwargs = self._start_kwargs(instance_json)
            kwargs["model"] = "gpt-5.4"
            result = actor_side_thread.start_actor_side_thread(**kwargs)

            self.assertEqual(calls[0]["model"], "gpt-5.4")
            self.assertEqual(calls[0]["model_reasoning_effort"], "medium")
            self.assertEqual(result["model_source"], "override")
            self.assertEqual(result["model_reasoning_effort_source"], "actor_config")

    def test_missing_side_config_uses_creation_default_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            calls: list[dict[str, Any]] = []
            original_start = actor_side_thread.side_thread_lifecycle.start_side_thread

            def fake_start(**kwargs: Any) -> dict[str, Any]:
                calls.append(kwargs)
                return {
                    "action": "start",
                    "side_thread_id": "thread-side-1",
                    "turn_id": "turn-side-1",
                    "model_source": "parent_thread",
                    "model_reasoning_effort_source": "parent_thread",
                }

            self.addCleanup(setattr, actor_side_thread.side_thread_lifecycle, "start_side_thread", original_start)
            actor_side_thread.side_thread_lifecycle.start_side_thread = fake_start

            result = actor_side_thread.start_actor_side_thread(**self._start_kwargs(instance_json))

            self.assertEqual(calls[0]["model"], "gpt-5.5")
            self.assertEqual(calls[0]["model_reasoning_effort"], "medium")
            self.assertEqual(result["model"], "gpt-5.5")
            self.assertEqual(result["model_reasoning_effort"], "medium")
            self.assertEqual(result["model_source"], "actor_config")
            self.assertEqual(result["model_reasoning_effort_source"], "actor_config")

    def test_empty_side_config_uses_codex_default_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_model_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {},
                    "side": {},
                },
            )
            calls: list[dict[str, Any]] = []
            original_start = actor_side_thread.side_thread_lifecycle.start_side_thread

            def fake_start(**kwargs: Any) -> dict[str, Any]:
                calls.append(kwargs)
                return {
                    "action": "start",
                    "side_thread_id": "thread-side-1",
                    "turn_id": "turn-side-1",
                    "model_source": "parent_thread",
                    "model_reasoning_effort_source": "parent_thread",
                }

            self.addCleanup(setattr, actor_side_thread.side_thread_lifecycle, "start_side_thread", original_start)
            actor_side_thread.side_thread_lifecycle.start_side_thread = fake_start

            result = actor_side_thread.start_actor_side_thread(**self._start_kwargs(instance_json))

            self.assertIsNone(calls[0]["model"])
            self.assertIsNone(calls[0]["model_reasoning_effort"])
            self.assertNotIn("model", result)
            self.assertNotIn("model_reasoning_effort", result)
            self.assertEqual(result["model_source"], "codex_default")
            self.assertEqual(result["model_reasoning_effort_source"], "codex_default")

    def test_invalid_side_config_fails_before_lifecycle_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_model_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {},
                    "side": {"model": ""},
                },
            )
            original_start = actor_side_thread.side_thread_lifecycle.start_side_thread

            def fake_start(**_kwargs: Any) -> dict[str, Any]:
                raise AssertionError("invalid side config must fail before lifecycle")

            self.addCleanup(setattr, actor_side_thread.side_thread_lifecycle, "start_side_thread", original_start)
            actor_side_thread.side_thread_lifecycle.start_side_thread = fake_start

            with self.assertRaisesRegex(actor_side_thread.ActorSideThreadError, "side model config"):
                actor_side_thread.start_actor_side_thread(**self._start_kwargs(instance_json))


if __name__ == "__main__":
    unittest.main()
