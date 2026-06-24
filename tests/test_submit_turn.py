#!/usr/bin/env python3
"""Tests for the launcher-owned shared submit-turn helper."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import unittest
from itertools import count
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUBMIT_TURN_PATH = ROOT / "tools" / "launcher" / "submit_turn.py"
LAUNCHER_PATH = ROOT / "buddyswitch-codex"
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


class SubmitTurnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.submit_turn = load_module(SUBMIT_TURN_PATH)

    def test_submit_turn_delegates_to_app_server_input_turn(self) -> None:
        calls: list[dict[str, object]] = []
        original = self.submit_turn.app_server.input_turn

        def fake_input_turn(socket_path: Path, thread_id: str, text: str, permissions: str) -> dict[str, object]:
            calls.append(
                {
                    "socket_path": socket_path,
                    "thread_id": thread_id,
                    "text": text,
                    "permissions": permissions,
                }
            )
            return {"action": "start", "turn_id": "turn-daemon-1"}

        self.addCleanup(setattr, self.submit_turn.app_server, "input_turn", original)
        self.submit_turn.app_server.input_turn = fake_input_turn

        result = self.submit_turn.submit_turn(
            socket_path=Path("/tmp/app-server.sock"),
            thread_id="thr-main",
            text="daemon prompt",
            permissions="buddyswitch-runtime",
        )

        self.assertEqual(result, {"action": "start", "turn_id": "turn-daemon-1"})
        self.assertEqual(
            calls,
            [
                {
                    "socket_path": Path("/tmp/app-server.sock"),
                    "thread_id": "thr-main",
                    "text": "daemon prompt",
                    "permissions": "buddyswitch-runtime",
                }
            ],
        )

    def test_submit_turn_cli_emits_json_payload(self) -> None:
        original = self.submit_turn.app_server.input_turn

        def fake_input_turn(_socket_path: Path, _thread_id: str, _text: str, _permissions: str) -> dict[str, object]:
            return {"action": "steer", "turn_id": "turn-steer-1", "expected_turn_id": "turn-active-1"}

        self.addCleanup(setattr, self.submit_turn.app_server, "input_turn", original)
        self.submit_turn.app_server.input_turn = fake_input_turn

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = self.submit_turn.main(
                [
                    "--socket",
                    "/tmp/app-server.sock",
                    "--thread-id",
                    "thr-main",
                    "--text",
                    "daemon prompt",
                    "--permissions",
                    "buddyswitch-runtime",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "action": "steer",
                "turn_id": "turn-steer-1",
                "expected_turn_id": "turn-active-1",
            },
        )

    def test_submit_turn_has_no_task_tui_source_coupling(self) -> None:
        source = SUBMIT_TURN_PATH.read_text(encoding="utf-8")
        self.assertNotIn("task_tui", source)
        self.assertNotIn("task_management", source)
        self.assertNotIn("[TASK CHECKOUT]", source)
        self.assertNotIn("[TASK CHECKPOINT]", source)
        self.assertNotIn("task_checkout", source)

    def test_instance_input_source_routes_through_submit_turn_helper(self) -> None:
        source = LAUNCHER_PATH.read_text(encoding="utf-8")
        start = source.index("instance_input() {")
        end = source.index("\ninstance_side()", start)
        instance_input_source = source[start:end]
        self.assertIn('SUBMIT_TURN_HELPER="${REPO_ROOT}/tools/launcher/submit_turn.py"', source)
        self.assertIn('python3 "${SUBMIT_TURN_HELPER}"', instance_input_source)
        self.assertNotIn('buddyswitch_app_server_input "${thread_id}" "${final_text}"', instance_input_source)


if __name__ == "__main__":
    unittest.main()
