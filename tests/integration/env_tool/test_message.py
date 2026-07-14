"""Actor message tool projection tests for Central IM."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

from env.tools.message import _impl as message_impl  # noqa: E402
from env.repos import identities as identity_repo  # noqa: E402
from env.services import messages as message_service  # noqa: E402
from env.tool_runtime import im_client as im_client_module  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402


class _ExplodingMessageRepo:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"old message repo must not be used: {name}")


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
        self.rules = _Rules()


class _RealImContext(dict[str, Any]):
    def __init__(self, *, identity_id: str, role_id: str, capabilities: Any) -> None:
        super().__init__(
            current_identity={"id": identity_id, "type": "actor"},
            active_role=role_id,
            manifest={"roles": [{"id": role_id}, {"id": "pm"}]},
        )
        self.actor_directory = capabilities
        self.im_actor_delivery = capabilities


class _RecordingParentCapability:
    def __init__(self) -> None:
        self.parent_requests: list[dict[str, Any]] = []


class _RecordingImDelivery:
    def __init__(self) -> None:
        self.delivery_calls: list[dict[str, Any]] = []

    def deliver(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.delivery_calls.append(dict(payload))
        return {"actor_handling_status": "submitted", "runtime_target": "parent", "error": None}

    def check_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
        return {"reachability_status": "offline", "target_identity_id": target_identity_id}

    def list_online_actors(self, *, role_id: str | None = None) -> dict[str, Any]:
        del role_id
        return {"actors": [], "count": 0}


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


class ActorImClientMarkTests(RuntimeWorkspaceTestCase):
    def _save_actor_profile(self, *, identity_id: str, role_id: str) -> None:
        identity_repo.save_actor_identity_profile(
            {
                "identity": {"id": identity_id, "type": "actor"},
                "role_id": role_id,
            }
        )

    def test_send_with_invalid_target_identity_id_returns_payload_error(self) -> None:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-invalid-target")
        client = im_client_module.ActorImClient(
            _RealImContext(identity_id=actor_id, role_id="dev", capabilities=_RecordingImDelivery())
        )

        response = client.send(
            {
                "target_identity_id": "",
                "content": "hello",
            }
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_IM_PAYLOAD")
        self.assertIn("target_identity_id", response.get("error", {}).get("message", ""))

    def test_actor_send_calls_message_service_with_identity_only_target(self) -> None:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-im-send")
        target_id = self._runtime_actor_id(role="pm", label="act-pm-im-target")
        self._save_actor_profile(identity_id=target_id, role_id="pm")
        captured: dict[str, Any] = {}
        handling_calls: list[dict[str, Any]] = []

        class _Capabilities:
            def check_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
                if target_identity_id != target_id:
                    raise AssertionError(f"expected {target_id}, got {target_identity_id}")
                return {
                    "reachability_status": "online",
                    "target_identity_id": target_id,
                    "record": {"identity_id": target_id},
                }

            def list_online_actors(self, *, role_id: str | None = None) -> dict[str, Any]:
                raise AssertionError("message.send must not call list_online_actors")

            def deliver(self, payload: dict[str, Any]) -> dict[str, Any]:
                handling_calls.append(dict(payload))
                return {"actor_handling_status": "submitted", "runtime_target": "parent", "error": None}

        def fake_send_im_message(**kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {
                "ok": True,
                "message": {"id": "msg-identity-only", "conversation_id": "conv-identity-only", "reply_to": None},
                "event_id": "imev-identity-only",
                "delivery_status": "accepted",
                "next_cursor": "imev-identity-only",
            }

        original = im_client_module.message_service.send_im_message
        im_client_module.message_service.send_im_message = fake_send_im_message
        try:
            client = im_client_module.ActorImClient(
                _RealImContext(identity_id=actor_id, role_id="dev", capabilities=_Capabilities())
            )
            response = client.send({"target_identity_id": target_id, "content": "hello"})
        finally:
            im_client_module.message_service.send_im_message = original

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response.get("actor_handling_status"), "submitted")
        self.assertEqual(captured["sender_identity"], {"id": actor_id, "type": "actor"})
        self.assertEqual(captured["target_identity"], {"id": target_id, "type": "actor"})
        self.assertEqual(captured["content"], "hello")
        self.assertIsNone(captured.get("reply_to"))
        self.assertNotIn("target_" + "role_id", captured)
        self.assertNotIn("wake_" + "actor", captured)
        self.assertEqual(
            handling_calls,
            [
                {
                    "type": "im.message.created",
                    "target_identity_id": target_id,
                    "message_id": "msg-identity-only",
                    "conversation_id": "conv-identity-only",
                    "event_id": "imev-identity-only",
                }
            ],
        )

    def test_actor_send_external_target_writes_message_visible_to_external_session(self) -> None:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-im-ext-send")
        created = message_service.create_external_session(display_name="external target")
        self.assertTrue(created.get("ok"), msg=created)
        auth = message_service.authenticate_external_session_key(str(created["external_session_key"]))
        self.assertTrue(auth.get("ok"), msg=auth)
        external_id = auth["identity"]["id"]

        class _Capabilities:
            def __init__(self) -> None:
                self.reachability_calls: list[dict[str, object]] = []
                self.delivery_calls: list[dict[str, object]] = []

            def check_reachability(self, *, target_identity_id: str) -> dict[str, object]:
                self.reachability_calls.append({"target_identity_id": target_identity_id})
                return {
                    "reachability_status": "online",
                    "target_identity_id": target_identity_id,
                    "record": {"identity_id": target_identity_id},
                }

            def list_online_actors(self, *, role_id: str | None = None) -> dict[str, object]:
                raise AssertionError("message.send must not list actors to resolve an explicit target")

            def deliver(self, payload: dict[str, object]) -> dict[str, object]:
                self.delivery_calls.append(dict(payload))
                return {"actor_handling_status": "submitted"}

        capabilities = _Capabilities()
        client = im_client_module.ActorImClient(
            _RealImContext(identity_id=actor_id, role_id="dev", capabilities=capabilities)
        )

        response = client.send({"target_identity_id": external_id, "content": "hello external"})
        events = message_service.read_external_session_events(
            external_session=auth["external_session"],
            limit=20,
            wait_ms=0,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["target_identity"], auth["identity"])
        self.assertEqual(response["actor_handling_status"], "not_applicable")
        self.assertEqual(capabilities.reachability_calls, [])
        self.assertEqual(capabilities.delivery_calls, [])
        self.assertEqual([row["message_id"] for row in events["events"]], [response["message"]["id"]])

    def test_actor_can_reply_to_external_origin_message_with_reply_to_only(self) -> None:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-im-reply")
        created = message_service.create_external_session(display_name="local smoke")
        self.assertTrue(created.get("ok"), msg=created)
        auth = message_service.authenticate_external_session_key(str(created["external_session_key"]))
        self.assertTrue(auth.get("ok"), msg=auth)
        root = message_service.send_im_message(
            sender_identity=auth["identity"],
            target_identity={"id": actor_id, "type": "actor"},
            content="ping",
        )
        capabilities = _RecordingImDelivery()
        client = im_client_module.ActorImClient(
            _RealImContext(identity_id=actor_id, role_id="dev", capabilities=capabilities)
        )

        reply = client.send({"content": "pong", "reply_to": root["message"]["id"]})

        self.assertTrue(reply.get("ok"), msg=reply)
        self.assertEqual(reply["message"]["reply_to"], root["message"]["id"])
        self.assertEqual(reply["message"]["conversation_id"], root["message"]["conversation_id"])
        self.assertEqual(reply["actor_handling_status"], "not_applicable")
        self.assertNotIn("wake_" + "status", reply)
        self.assertEqual(reply["original_message_id"], root["message"]["id"])
        self.assertEqual(reply["original_final_disposition"], "replied")
        self.assertEqual(capabilities.delivery_calls, [])

        state_path = (
            self.runtime_state_root
            / "im"
            / "message_states"
            / f"{root['message']['id']}--{actor_id}.json"
        )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["owner_identity_id"], actor_id)
        self.assertEqual(persisted["disposition"], "replied")

    def test_actor_reply_to_actor_origin_message_uses_resolved_target_for_actor_handling(self) -> None:
        active_actor_id = self._runtime_actor_id(role="dev", label="act-dev-im-actor-reply")
        source_actor_id = self._runtime_actor_id(role="pm", label="act-pm-im-actor-reply")
        self._save_actor_profile(identity_id=active_actor_id, role_id="dev")
        self._save_actor_profile(identity_id=source_actor_id, role_id="pm")
        root = message_service.send_im_message(
            sender_identity={"id": source_actor_id, "type": "actor"},
            target_identity={"id": active_actor_id, "type": "actor"},
            content="Need a reply.",
        )
        self.assertTrue(root.get("ok"), msg=root)

        reachability_calls: list[str] = []

        class _Capabilities(_RecordingImDelivery):
            def check_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
                reachability_calls.append(target_identity_id)
                return {
                    "reachability_status": "online",
                    "target_identity_id": target_identity_id,
                    "record": {"identity_id": target_identity_id},
                }

        capabilities = _Capabilities()
        client = im_client_module.ActorImClient(
            _RealImContext(identity_id=active_actor_id, role_id="dev", capabilities=capabilities)
        )

        reply = client.send({"content": "Reply from dev.", "reply_to": root["message"]["id"]})

        self.assertTrue(reply.get("ok"), msg=reply)
        self.assertEqual(reachability_calls, [source_actor_id])
        self.assertEqual(reply["message"]["reply_to"], root["message"]["id"])
        self.assertEqual(reply["target_identity"], {"id": source_actor_id, "type": "actor"})
        self.assertEqual(reply["actor_handling_status"], "submitted")
        self.assertEqual(
            capabilities.delivery_calls,
            [
                {
                    "type": "im.message.created",
                    "target_identity_id": source_actor_id,
                    "message_id": reply["message"]["id"],
                    "conversation_id": reply["message"]["conversation_id"],
                    "event_id": reply["event_id"],
                }
            ],
        )
        self.assertNotIn("wake_" + "status", reply)

    def test_actor_reply_to_offline_actor_rejects_without_message_write(self) -> None:
        active_actor_id = self._runtime_actor_id(role="dev", label="act-dev-wrapper-offline")
        source_actor_id = self._runtime_actor_id(role="pm", label="act-pm-wrapper-offline")
        self._save_actor_profile(identity_id=active_actor_id, role_id="dev")
        self._save_actor_profile(identity_id=source_actor_id, role_id="pm")
        root = message_service.send_im_message(
            sender_identity={"id": source_actor_id, "type": "actor"},
            target_identity={"id": active_actor_id, "type": "actor"},
            content="Need a reply.",
        )
        before_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))

        class _Capabilities(_RecordingImDelivery):
            def check_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
                if target_identity_id != source_actor_id:
                    raise AssertionError(f"expected {source_actor_id}, got {target_identity_id}")
                return {
                    "reachability_status": "offline",
                    "target_identity_id": target_identity_id,
                    "record": {"identity_id": target_identity_id},
                }

        capabilities = _Capabilities()
        client = im_client_module.ActorImClient(
            _RealImContext(identity_id=active_actor_id, role_id="dev", capabilities=capabilities)
        )

        reply = client.send({"content": "Reply from dev.", "reply_to": root["message"]["id"]})

        self.assertFalse(reply.get("ok"), msg=reply)
        self.assertEqual(reply["error"]["code"], "E_IM_TARGET")
        after_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))
        self.assertEqual(after_messages, before_messages)
        state_path = (
            self.runtime_state_root
            / "im"
            / "message_states"
            / f"{root['message']['id']}--{active_actor_id}.json"
        )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["owner_identity_id"], active_actor_id)
        self.assertEqual(persisted["disposition"], "unseen")
        self.assertEqual(capabilities.delivery_calls, [])

    def test_actor_send_rejects_target_identity_and_reply_to_together_without_message_write(self) -> None:
        active_actor_id = self._runtime_actor_id(role="dev", label="act-dev-wrapper-both")
        source_actor_id = self._runtime_actor_id(role="pm", label="act-pm-wrapper-both")
        self._save_actor_profile(identity_id=active_actor_id, role_id="dev")
        self._save_actor_profile(identity_id=source_actor_id, role_id="pm")
        root = message_service.send_im_message(
            sender_identity={"id": source_actor_id, "type": "actor"},
            target_identity={"id": active_actor_id, "type": "actor"},
            content="Need a reply.",
        )
        before_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))
        capabilities = _RecordingImDelivery()
        client = im_client_module.ActorImClient(
            _RealImContext(identity_id=active_actor_id, role_id="dev", capabilities=capabilities)
        )

        response = client.send(
            {
                "target_identity_id": source_actor_id,
                "reply_to": root["message"]["id"],
                "content": "bad payload",
            }
        )

        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response["error"]["code"], "E_IM_PAYLOAD")
        after_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))
        self.assertEqual(after_messages, before_messages)
        self.assertEqual(capabilities.delivery_calls, [])

    def test_mark_needs_parent_is_rejected_without_parent_submit(self) -> None:
        active_actor_id = self._runtime_actor_id(role="dev", label="act-dev-im-parent-fail")
        sender_actor_id = self._runtime_actor_id(role="pm", label="act-pm-im-parent-fail")
        incoming = message_service.send_im_message(
            sender_identity={"id": sender_actor_id, "type": "actor"},
            target_identity={"id": active_actor_id, "type": "actor"},
            content="This needs parent handling.",
        )
        message_id = incoming["message"]["id"]
        capabilities = _RecordingParentCapability()
        client = im_client_module.ActorImClient(
            _RealImContext(identity_id=active_actor_id, role_id="dev", capabilities=capabilities)
        )

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
        self.assertEqual(capabilities.parent_requests, [])

        state_path = (
            self.runtime_state_root
            / "im"
            / "message_states"
            / f"{message_id}--{active_actor_id}.json"
        )
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["owner_identity_id"], active_actor_id)
        self.assertEqual(persisted["disposition"], "unseen")
