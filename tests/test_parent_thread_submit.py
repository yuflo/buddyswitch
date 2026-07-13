"""Tests for capability-aware parent thread submission."""

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
import parent_thread_submit  # noqa: E402


class ParentThreadSubmitTests(unittest.TestCase):
    def _instance_json(self, temp_root: Path) -> Path:
        instance_root = temp_root / "instances" / "act-pm-test"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        instance_json.write_text(
            json.dumps({"actor_id": "act-pm-test", "instance_root": str(instance_root)}) + "\n",
            encoding="utf-8",
        )
        return instance_json

    def _install_calls(self) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        original_update = parent_thread_submit.app_server.thread_settings_update
        original_submit = parent_thread_submit.submit_turn.submit_turn

        def fake_update(
            socket_path: Path,
            thread_id: str,
            *,
            model: str | None,
            effort: str | None,
        ) -> dict[str, Any]:
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
        return calls

    def test_balanced_parent_updates_terra_high_before_submit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            actor_capability.seed_actor_capabilities(instance_json)
            calls = self._install_calls()

            result = parent_thread_submit.submit_parent_turn(
                socket_path=Path("/tmp/app-server.sock"),
                instance_json=instance_json,
                thread_id="thread-main",
                text="hello",
                permissions="buddyswitch-runtime",
            )

            self.assertEqual(result["turn_id"], "turn-parent-1")
            self.assertEqual([call["helper"] for call in calls], ["thread_settings_update", "submit_turn"])
            self.assertEqual(calls[0]["model"], "gpt-5.6-terra")
            self.assertEqual(calls[0]["effort"], "high")
            self.assertEqual(calls[1]["thread_id"], "thread-main")

    def test_deep_parent_applies_sol_xhigh_before_submit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            actor_capability.seed_actor_capabilities(instance_json)
            actor_capability.replace_actor_capabilities(instance_json, parent_level="deep", side_level="fast")
            calls = self._install_calls()

            result = parent_thread_submit.submit_parent_turn(
                socket_path=Path("/tmp/app-server.sock"),
                instance_json=instance_json,
                thread_id="thread-main",
                text="steer",
                permissions="buddyswitch-runtime",
            )

            self.assertEqual(result["action"], "start")
            self.assertEqual(calls[0]["model"], "gpt-5.6-sol")
            self.assertEqual(calls[0]["effort"], "xhigh")
            self.assertEqual([call["helper"] for call in calls], ["thread_settings_update", "submit_turn"])

    def test_settings_update_failure_prevents_submit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            actor_capability.seed_actor_capabilities(instance_json)
            original_update = parent_thread_submit.app_server.thread_settings_update
            original_submit = parent_thread_submit.submit_turn.submit_turn
            submit_calls: list[dict[str, Any]] = []

            def fail_update(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
                raise parent_thread_submit.app_server.AppServerError("settings rejected")

            def record_submit(**kwargs: Any) -> dict[str, Any]:
                submit_calls.append(kwargs)
                return {"action": "start", "turn_id": "unexpected"}

            self.addCleanup(setattr, parent_thread_submit.app_server, "thread_settings_update", original_update)
            self.addCleanup(setattr, parent_thread_submit.submit_turn, "submit_turn", original_submit)
            parent_thread_submit.app_server.thread_settings_update = fail_update
            parent_thread_submit.submit_turn.submit_turn = record_submit

            with self.assertRaisesRegex(parent_thread_submit.ParentThreadSubmitError, "parent settings update failed"):
                parent_thread_submit.submit_parent_turn(
                    socket_path=Path("/tmp/app-server.sock"),
                    instance_json=instance_json,
                    thread_id="thread-main",
                    text="hello",
                    permissions="buddyswitch-runtime",
                )

            self.assertEqual(submit_calls, [])

    def test_missing_capability_config_fails_before_settings_or_submit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_json = self._instance_json(Path(temp_root))
            original_update = parent_thread_submit.app_server.thread_settings_update
            original_submit = parent_thread_submit.submit_turn.submit_turn

            def fail(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
                raise AssertionError("missing capability config must fail before runtime calls")

            self.addCleanup(setattr, parent_thread_submit.app_server, "thread_settings_update", original_update)
            self.addCleanup(setattr, parent_thread_submit.submit_turn, "submit_turn", original_submit)
            parent_thread_submit.app_server.thread_settings_update = fail
            parent_thread_submit.submit_turn.submit_turn = fail

            with self.assertRaisesRegex(parent_thread_submit.ParentThreadSubmitError, "parent capability invalid"):
                parent_thread_submit.submit_parent_turn(
                    socket_path=Path("/tmp/app-server.sock"),
                    instance_json=instance_json,
                    thread_id="thread-main",
                    text="hello",
                    permissions="buddyswitch-runtime",
                )


if __name__ == "__main__":
    unittest.main()
