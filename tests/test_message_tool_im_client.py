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
        return {"ok": True, "action": "message.list", "events": [], "next_cursor": args.get("cursor")}

    def conversation(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("conversation", dict(args)))
        return {"ok": True, "action": "message.conversation", "messages": []}

    def mark(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("mark", dict(args)))
        return {"ok": True, "action": "message.mark", "message_id": args["message_id"]}


class _Context(dict[str, Any]):
    def __init__(self, client: _FakeImClient) -> None:
        super().__init__(
            current_identity={"id": "act-market-tool", "type": "actor"},
            active_role="market",
            manifest={"roles": [{"id": "market"}, {"id": "pm"}]},
        )
        self.im_client = client
        self.repos = _Repos()
        self.daemon = _ExplodingDaemon()
        self.rules = _Rules()


class _RealImContext(dict[str, Any]):
    def __init__(self, *, identity_id: str, role_id: str, daemon: Any) -> None:
        super().__init__(
            current_identity={"id": identity_id, "type": "actor"},
            active_role=role_id,
            manifest={"roles": [{"id": role_id}, {"id": "pm"}]},
        )
        self.daemon = daemon


class _RecordingParentDaemon:
    def __init__(self) -> None:
        self.parent_requests: list[dict[str, Any]] = []


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
        target_identity_id = "act-pm-tool"

        cases = [
            ("contacts", {"role": "pm"}, ("contacts", {"role": "pm"})),
            ("send", {"target_identity_id": target_identity_id, "content": "hello"}, ("send", {"target_identity_id": target_identity_id, "content": "hello"})),
            ("get", {"message_id": "msg-1"}, ("get", {"message_id": "msg-1"})),
            ("list", {"cursor": "imev-000000000001", "limit": 5}, ("list", {"cursor": "imev-000000000001", "limit": 5})),
            ("conversation", {"target_identity_id": target_identity_id}, ("conversation", {"target_identity_id": target_identity_id})),
            ("mark", {"message_id": "msg-1", "disposition": "absorbed"}, ("mark", {"message_id": "msg-1", "disposition": "absorbed"})),
        ]

        for action, args, expected_call in cases:
            with self.subTest(action=action):
                result = message_impl.invoke(action=action, args=args, context=context)
                self.assertTrue(result["ok"], msg=result)
                self.assertEqual(client.calls[-1], expected_call)


class ActorImClientMarkTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def test_send_with_invalid_target_identity_id_returns_payload_error(self) -> None:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-invalid-target")
        client = im_client_module.ActorImClient(_RealImContext(identity_id=actor_id, role_id="dev", daemon=_RecordingWakeDaemon()))

        response = client.send(
            {
                "target_identity_id": "",
                "content": "hello",
            }
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_IM_PAYLOAD")
        self.assertIn("target_identity_id", response.get("error", {}).get("message", ""))

    def test_actor_can_reply_to_external_origin_message_with_reply_to_only(self) -> None:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-im-reply")
        created = message_service.create_external_connection(display_name="local smoke")
        self.assertTrue(created.get("ok"), msg=created)
        auth = message_service.authenticate_external_connection_key(str(created["connection_key"]))
        self.assertTrue(auth.get("ok"), msg=auth)
        root = message_service.send_im_message(
            sender_identity=auth["identity"],
            to={"id": actor_id, "type": "actor"},
            target_role_id="dev",
            content="ping",
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        daemon = _RecordingWakeDaemon()
        client = im_client_module.ActorImClient(_RealImContext(identity_id=actor_id, role_id="dev", daemon=daemon))

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
            / f"{root['message']['id']}--{actor_id}.json"
        )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["owner_identity_id"], actor_id)
        self.assertEqual(persisted["disposition"], "replied")

    def test_mark_needs_parent_is_rejected_without_parent_submit(self) -> None:
        active_actor_id = self._runtime_actor_id(role="dev", label="act-dev-im-parent-fail")
        sender_actor_id = self._runtime_actor_id(role="pm", label="act-pm-im-parent-fail")
        incoming = message_service.send_im_message(
            sender_identity={"id": sender_actor_id, "type": "actor"},
            to={"id": active_actor_id, "type": "actor"},
            target_role_id="dev",
            content="This needs parent handling.",
            wake_actor=lambda _payload: {"wake_status": "submitted"},
        )
        message_id = incoming["message"]["id"]
        daemon = _RecordingParentDaemon()
        client = im_client_module.ActorImClient(_RealImContext(identity_id=active_actor_id, role_id="dev", daemon=daemon))

        response = client.mark(
            {
                "message_id": message_id,
                "disposition": "needs_parent",
                "reason": "This changes the active parent-thread objective.",
            }
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
        self.assertIn("task_sys.need_parent", (response.get("error") or {}).get("message", ""))
        self.assertEqual(daemon.parent_requests, [])

        state_path = (
            self.runtime_state_root
            / "im"
            / "message_states"
            / f"{message_id}--{active_actor_id}.json"
        )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["owner_identity_id"], active_actor_id)
        self.assertEqual(persisted["disposition"], "unseen")


if __name__ == "__main__":
    unittest.main()
