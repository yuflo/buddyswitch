#!/usr/bin/env python3
"""Actor message tool projection tests for Central IM."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from env.tools.message import _impl as message_impl  # noqa: E402
from env.services import messages as message_service  # noqa: E402
from env.tool_runtime import im_client as im_client_module  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class _ExplodingMessageRepo:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"old message repo must not be used: {name}")


class _ExplodingDaemon:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"old daemon message path must not be used: {name}")


class _Repos:
    message = _ExplodingMessageRepo()


class _Rules:
    pass


class _FakeImClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def contacts(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("contacts", dict(args)))
        return {"ok": True, "action": "message.contacts", "contacts": []}

    def send(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("send", dict(args)))
        return {"ok": True, "action": "message.send", "message_id": "msg-im-client"}

    def get(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("get", dict(args)))
        return {"ok": True, "action": "message.get", "message": {"id": args["message_id"]}}

    def list(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("list", dict(args)))
        return {"ok": True, "action": "message.list", "messages": []}

    def conversation(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("conversation", dict(args)))
        return {"ok": True, "action": "message.conversation", "messages": []}

    def mark(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("mark", dict(args)))
        return {"ok": True, "action": "message.mark", "message_id": args["message_id"]}


class _Context(dict[str, Any]):
    def __init__(self, client: _FakeImClient) -> None:
        actor_address = ActorAddress(role_id="market", actor_id="act-market-tool")
        super().__init__(
            active_actor=actor_address.to_payload(),
            active_role="market",
            manifest={"roles": [{"id": "market"}, {"id": "pm"}]},
        )
        self.actor_address = actor_address
        self.im_client = client
        self.repos = _Repos()
        self.daemon = _ExplodingDaemon()
        self.rules = _Rules()


class _RealImContext(dict[str, Any]):
    def __init__(self, *, actor_address: ActorAddress, daemon: Any) -> None:
        super().__init__(
            active_actor=actor_address.to_payload(),
            active_role=actor_address.role_id,
            manifest={"roles": [{"id": actor_address.role_id}, {"id": "pm"}]},
        )
        self.actor_address = actor_address
        self.daemon = daemon


class _FailingParentDaemon:
    def __init__(self) -> None:
        self.parent_requests: list[dict[str, Any]] = []

    def request_parent_message_handling(self, *, message_id: str, prompt: str) -> dict[str, Any]:
        self.parent_requests.append({"message_id": message_id, "prompt": prompt})
        raise RuntimeError("parent submit unavailable")


class _RecordingWakeDaemon:
    def __init__(self) -> None:
        self.wake_calls: list[dict[str, Any]] = []

    def wake_im_actor(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.wake_calls.append(dict(payload))
        return {"wake_status": "submitted", "runtime_target": "parent", "error": None}


class MessageToolImClientTests(unittest.TestCase):
    def test_all_message_actions_delegate_to_im_client(self) -> None:
        client = _FakeImClient()
        context = _Context(client)
        target = {"role_id": "pm", "actor_id": "act-pm-tool"}

        cases = [
            ("contacts", {"role": "pm"}, ("contacts", {"role": "pm"})),
            ("send", {"target_actor_address": target, "content": "hello"}, ("send", {"target_actor_address": target, "content": "hello"})),
            ("get", {"message_id": "msg-1"}, ("get", {"message_id": "msg-1"})),
            ("list", {"limit": 5}, ("list", {"limit": 5})),
            ("conversation", {"target_actor_address": target}, ("conversation", {"target_actor_address": target})),
            ("mark", {"message_id": "msg-1", "disposition": "absorbed"}, ("mark", {"message_id": "msg-1", "disposition": "absorbed"})),
        ]

        for action, args, expected_call in cases:
            with self.subTest(action=action):
                result = message_impl.invoke(action=action, args=args, context=context)
                self.assertTrue(result["ok"], msg=result)
                self.assertEqual(client.calls[-1], expected_call)


class ActorImClientMarkTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_actor_can_reply_to_external_origin_message_with_reply_to_only(self) -> None:
        actor = ActorAddress(
            role_id="dev",
            actor_id=self._runtime_actor_id(role="dev", label="act-dev-im-reply"),
        )
        registration = message_service.register_external_participant(
            client_kind="script",
            display_name="local smoke",
        )
        root = message_service.send_im_message(
            sender_participant=registration["participant"],
            to={"kind": "actor", "actor_address": actor.to_payload()},
            content="ping",
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        daemon = _RecordingWakeDaemon()
        client = im_client_module.ActorImClient(_RealImContext(actor_address=actor, daemon=daemon))

        reply = client.send({"content": "pong", "reply_to": root["message"]["id"]})

        self.assertTrue(reply.get("ok"), msg=reply)
        self.assertEqual(reply["message"]["reply_to"], root["message"]["id"])
        self.assertEqual(reply["message"]["conversation_id"], root["message"]["conversation_id"])
        self.assertEqual(reply["wake_status"], "not_applicable")
        self.assertEqual(reply["original_message_id"], root["message"]["id"])
        self.assertEqual(reply["original_final_disposition"], "replied")
        self.assertEqual(daemon.wake_calls, [])

        state_path = (
            self.runtime_state_root
            / "im"
            / "message_states"
            / f"{root['message']['id']}--actor--dev--{actor.actor_id}.json"
        )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["disposition"], "replied")

    def test_mark_needs_parent_submit_failure_leaves_im_state_unseen(self) -> None:
        active_actor = ActorAddress(
            role_id="dev",
            actor_id=self._runtime_actor_id(role="dev", label="act-dev-im-parent-fail"),
        )
        sender_actor = ActorAddress(
            role_id="pm",
            actor_id=self._runtime_actor_id(role="pm", label="act-pm-im-parent-fail"),
        )
        incoming = message_service.send_im_message(
            sender_participant={"kind": "actor", "actor_address": sender_actor.to_payload()},
            to={"kind": "actor", "actor_address": active_actor.to_payload()},
            content="This needs parent handling.",
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        message_id = incoming["message"]["id"]
        daemon = _FailingParentDaemon()
        client = im_client_module.ActorImClient(_RealImContext(actor_address=active_actor, daemon=daemon))

        response = client.mark(
            {
                "message_id": message_id,
                "disposition": "needs_parent",
                "reason": "This changes the active parent-thread objective.",
            }
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PARENT_REQUIRED_SUBMIT_FAILED")
        self.assertEqual(len(daemon.parent_requests), 1)
        self.assertEqual(daemon.parent_requests[0]["message_id"], message_id)
        self.assertIn(message_id, daemon.parent_requests[0]["prompt"])
        self.assertIs(response.get("parent_prompt_submitted"), False, msg=response)
        self.assertEqual(response.get("original_previous_disposition"), "unseen")
        self.assertEqual(response.get("original_final_disposition"), "unseen")

        state_path = (
            self.runtime_state_root
            / "im"
            / "message_states"
            / f"{message_id}--actor--dev--{active_actor.actor_id}.json"
        )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["disposition"], "unseen")


if __name__ == "__main__":
    unittest.main()
