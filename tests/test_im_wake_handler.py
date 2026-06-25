#!/usr/bin/env python3
"""Runtime wake handling tests for Central IM."""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HELPER_DIR = ROOT / "tools" / "launcher"
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import im_wake_handler  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402


@dataclass
class _Context:
    actor_address: ActorAddress


@dataclass
class _Trigger:
    type: str
    target_actor_address: dict[str, str]
    payload: dict[str, str]


class _Runtime:
    def __init__(self, status: str) -> None:
        self.status = status
        self.parent_prompts: list[dict[str, Any]] = []
        self.side_prompts: list[dict[str, Any]] = []

    def parent_activity(self) -> dict[str, str]:
        return {"status": self.status}

    def submit_parent_prompt(self, prompt: str, **kwargs: Any) -> None:
        self.parent_prompts.append({"prompt": prompt, **kwargs})

    def submit_side_triage_prompt(self, prompt: str, **kwargs: Any) -> None:
        self.side_prompts.append({"prompt": prompt, **kwargs})


class ImWakeHandlerTests(unittest.TestCase):
    def _actor(self) -> ActorAddress:
        return ActorAddress(role_id="market", actor_id="act-market-test")

    def _trigger(self, actor: ActorAddress | None = None) -> _Trigger:
        target = actor or self._actor()
        return _Trigger(
            type="im.message.created",
            target_actor_address=target.to_payload(),
            payload={
                "message_id": "msg-abc123",
                "conversation_id": "conv-abc123",
                "event_id": "imev-abc123",
            },
        )

    def test_idle_parent_receives_im_message_prompt_with_ids_only(self) -> None:
        actor = self._actor()
        runtime = _Runtime("idle")
        handler = im_wake_handler.ImMessageCreatedHandler()

        result = handler.handle(_Context(actor), None, runtime, self._trigger(actor))

        self.assertEqual(result.status, "handled")
        self.assertEqual(len(runtime.parent_prompts), 1)
        self.assertEqual(runtime.side_prompts, [])
        submitted = runtime.parent_prompts[0]
        self.assertEqual(submitted["handler_name"], "im_message_created")
        self.assertEqual(submitted["origin_id"], "msg-abc123")
        self.assertEqual(submitted["interrupt_policy"], "none")
        self.assertIn('message__get with message_id="msg-abc123"', submitted["prompt"])
        self.assertIn('message__send(content=..., reply_to="msg-abc123")', submitted["prompt"])
        self.assertNotIn("target_actor_address", submitted["prompt"])

    def test_running_parent_receives_side_triage(self) -> None:
        actor = self._actor()
        runtime = _Runtime("running")
        handler = im_wake_handler.ImMessageCreatedHandler()

        result = handler.handle(_Context(actor), None, runtime, self._trigger(actor))

        self.assertEqual(result.status, "handled")
        self.assertEqual(runtime.parent_prompts, [])
        self.assertEqual(len(runtime.side_prompts), 1)
        self.assertEqual(runtime.side_prompts[0]["handler_name"], "im_message_created")
        self.assertEqual(runtime.side_prompts[0]["origin_id"], "msg-abc123")

    def test_wrong_target_actor_fails(self) -> None:
        handler = im_wake_handler.ImMessageCreatedHandler()
        wrong = ActorAddress(role_id="market", actor_id="act-market-other")

        result = handler.handle(_Context(self._actor()), None, _Runtime("idle"), self._trigger(wrong))

        self.assertEqual(result.status, "failed")
        self.assertIn("wrong target actor", result.message)

    def test_handler_does_not_handle_unrelated_event(self) -> None:
        handler = im_wake_handler.ImMessageCreatedHandler()

        self.assertFalse(handler.handles(_Trigger("example.ready", self._actor().to_payload(), {"message_id": "msg-abc123"})))


if __name__ == "__main__":
    unittest.main()
