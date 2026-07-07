#!/usr/bin/env python3
"""Tests for actor-aware parent thread submission."""

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

import parent_thread_submit  # noqa: E402


class ParentThreadSubmitTests(unittest.TestCase):
    def _instance_json(self, temp_root: Path) -> Path:
        instance_root = temp_root / "instances" / "act-pm-test"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps({"actor_id": "act-pm-test", "instance_root": str(instance_root)}, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _write_model_config(self, instance_json: Path, payload: dict[str, object]) -> None:
        (instance_json.parent / "model-config.json").write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_configured_parent_updates_settings_before_submit_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_model_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {"model": "gpt-5.4", "effort": "high"},
                    "side": {},
                },
            )
            calls: list[dict[str, Any]] = []
            original_update = parent_thread_submit.app_server.thread_settings_update
            original_submit = parent_thread_submit.submit_turn.submit_turn

            def fake_update(socket_path: Path, thread_id: str, *, model: str | None, effort: str | None) -> dict[str, Any]:
                calls.append(
                    {
                        "helper": "thread_settings_update",
                        "socket_path": socket_path,
                        "thread_id": thread_id,
                        "model": model,
                        "effort": effort,
                    }
                )
                return {"threadId": thread_id, "model": model, "effort": effort}

            def fake_submit(**kwargs: Any) -> dict[str, Any]:
                calls.append({"helper": "submit_turn", **kwargs})
                return {"action": "start", "turn_id": "turn-parent-1"}

            self.addCleanup(setattr, parent_thread_submit.app_server, "thread_settings_update", original_update)
            self.addCleanup(setattr, parent_thread_submit.submit_turn, "submit_turn", original_submit)
            parent_thread_submit.app_server.thread_settings_update = fake_update
            parent_thread_submit.submit_turn.submit_turn = fake_submit

            result = parent_thread_submit.submit_parent_turn(
                socket_path=Path("/tmp/app-server.sock"),
                instance_json=instance_json,
                thread_id="thread-main",
                text="hello",
                permissions="buddyswitch-runtime",
            )

            self.assertEqual(result["turn_id"], "turn-parent-1")
            self.assertEqual([call["helper"] for call in calls], ["thread_settings_update", "submit_turn"])
            self.assertEqual(calls[0]["model"], "gpt-5.4")
            self.assertEqual(calls[0]["effort"], "high")
            self.assertEqual(calls[1]["thread_id"], "thread-main")
            self.assertEqual(calls[1]["text"], "hello")

    def test_missing_parent_config_skips_settings_update_and_still_submits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            original_update = parent_thread_submit.app_server.thread_settings_update
            original_submit = parent_thread_submit.submit_turn.submit_turn

            def fake_update(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
                raise AssertionError("missing config must not update settings")

            def fake_submit(**kwargs: Any) -> dict[str, Any]:
                self.assertEqual(kwargs["thread_id"], "thread-main")
                return {"action": "start", "turn_id": "turn-parent-default"}

            self.addCleanup(setattr, parent_thread_submit.app_server, "thread_settings_update", original_update)
            self.addCleanup(setattr, parent_thread_submit.submit_turn, "submit_turn", original_submit)
            parent_thread_submit.app_server.thread_settings_update = fake_update
            parent_thread_submit.submit_turn.submit_turn = fake_submit

            result = parent_thread_submit.submit_parent_turn(
                socket_path=Path("/tmp/app-server.sock"),
                instance_json=instance_json,
                thread_id="thread-main",
                text="hello",
                permissions="buddyswitch-runtime",
            )

            self.assertEqual(result["turn_id"], "turn-parent-default")

    def test_invalid_parent_config_fails_before_submit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_model_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {"effort": "maximum"},
                    "side": {},
                },
            )
            original_submit = parent_thread_submit.submit_turn.submit_turn

            def fake_submit(**_kwargs: Any) -> dict[str, Any]:
                raise AssertionError("invalid parent config must fail before submit")

            self.addCleanup(setattr, parent_thread_submit.submit_turn, "submit_turn", original_submit)
            parent_thread_submit.submit_turn.submit_turn = fake_submit

            with self.assertRaisesRegex(parent_thread_submit.ParentThreadSubmitError, "parent model config"):
                parent_thread_submit.submit_parent_turn(
                    socket_path=Path("/tmp/app-server.sock"),
                    instance_json=instance_json,
                    thread_id="thread-main",
                    text="hello",
                    permissions="buddyswitch-runtime",
                )

    def test_active_parent_settings_apply_to_subsequent_turn_before_steer_delegate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            self._write_model_config(
                instance_json,
                {
                    "schema_version": 1,
                    "parent": {"model": "gpt-5.4"},
                    "side": {},
                },
            )
            calls: list[str] = []
            original_update = parent_thread_submit.app_server.thread_settings_update
            original_submit = parent_thread_submit.submit_turn.submit_turn

            def fake_update(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
                calls.append("settings_for_subsequent_turns")
                return {"threadId": "thread-main"}

            def fake_submit(**_kwargs: Any) -> dict[str, Any]:
                calls.append("submit_turn_active_delegate")
                return {"action": "steer", "turn_id": "turn-active-1"}

            self.addCleanup(setattr, parent_thread_submit.app_server, "thread_settings_update", original_update)
            self.addCleanup(setattr, parent_thread_submit.submit_turn, "submit_turn", original_submit)
            parent_thread_submit.app_server.thread_settings_update = fake_update
            parent_thread_submit.submit_turn.submit_turn = fake_submit

            result = parent_thread_submit.submit_parent_turn(
                socket_path=Path("/tmp/app-server.sock"),
                instance_json=instance_json,
                thread_id="thread-main",
                text="steer",
                permissions="buddyswitch-runtime",
            )

            self.assertEqual(result["action"], "steer")
            self.assertEqual(calls, ["settings_for_subsequent_turns", "submit_turn_active_delegate"])


if __name__ == "__main__":
    unittest.main()
