"""External-user Central IM reply loop acceptance tests."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

from tools.launcher import daemon_mailbox  # noqa: E402
from tools.launcher import im_http_router  # noqa: E402
from tools.launcher import im_wake_handler  # noqa: E402
from env.repos import identities  # noqa: E402
from env.tool_runtime import im_actor_delivery  # noqa: E402
from env.tool_runtime import im_client as im_client_module  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402


class _ActorContext(dict[str, Any]):
    def __init__(self, *, identity_id: str, role_id: str, capabilities: Any) -> None:
        super().__init__(
            current_identity={"id": identity_id, "type": "actor"},
            active_role=role_id,
            manifest={"roles": [{"id": role_id}]},
        )
        self.actor_directory = capabilities
        self.im_actor_delivery = capabilities


class _RecordingImDelivery:
    def __init__(self) -> None:
        self.delivery_calls: list[dict[str, Any]] = []

    def deliver(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.delivery_calls.append(dict(payload))
        return {"actor_handling_status": "submitted", "runtime_target": "parent", "error": None}

    def check_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
        return {"reachability_status": "offline", "target_identity_id": target_identity_id}


class _RecordingTriggerDispatcher:
    def __init__(self) -> None:
        self.triggers: list[Any] = []

    def __call__(self, trigger: Any) -> dict[str, Any]:
        self.triggers.append(trigger)
        return {
            "accepted": True,
            "handled_count": 1,
            "matched_count": 1,
            "handling_status": "handled",
        }


class _Runtime:
    def parent_activity(self) -> dict[str, str]:
        return {"status": "idle"}


class _WakeHandlerDispatcher:
    def __init__(self, *, identity_id: str, role_id: str) -> None:
        self.context = type("Context", (), {"actor_id": identity_id, "role": role_id})()
        self.identity_id = identity_id
        self.role_id = role_id
        self.runtime = _Runtime()
        self.handler = im_wake_handler.ImMessageCreatedHandler()
        self.triggers: list[Any] = []
        self.task_sys_instructions: list[dict[str, Any]] = []

    def _execute_instruction(self, _context: object, instruction: dict[str, Any]) -> dict[str, Any]:
        expected = {"actor_id": self.identity_id, "role_id": self.role_id}
        if instruction.get("actor_target") != expected:
            raise AssertionError(f"wrong task sys target: {instruction.get('actor_target')!r}")
        self.task_sys_instructions.append(instruction)
        return {"action": instruction["type"], "task_id": instruction["task_id"]}

    def __call__(self, trigger: Any) -> dict[str, Any]:
        self.triggers.append(trigger)
        original_execute = im_wake_handler.task_sys_daemon_adapter.execute_instruction
        im_wake_handler.task_sys_daemon_adapter.execute_instruction = self._execute_instruction
        try:
            result = self.handler.handle(self.context, None, self.runtime, trigger)
        finally:
            im_wake_handler.task_sys_daemon_adapter.execute_instruction = original_execute
        return {
            "accepted": True,
            "handled_count": 1 if result.status == "handled" else 0,
            "matched_count": 1,
            "handling_status": result.status,
        }

class ImExternalReplyLoopTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _create_external_session(self, router: im_http_router.ImHttpRouter) -> str:
        status, created = router.handle(
            "POST",
            "/api/im/external-sessions",
            json.dumps({"display_name": "local acceptance"}).encode("utf-8"),
            {},
        )
        self.assertEqual(status, 200, msg=created)
        self.assertTrue(created.get("ok"), msg=created)
        self.assertIsInstance(created.get("external_session_key"), str, msg=created)
        self.assertNotIn("connection_key", created)
        self.assertNotIn("participant_" + "token", created)
        self.assertNotIn("event_" + "cursor", created)
        return str(created["external_session_key"])

    def test_external_send_actor_reply_to_external_visible_once_without_cursor(self) -> None:
        actor_identity_id = self._runtime_actor_id(role="market", label="reply-loop")
        identities.save_actor_identity_profile(
            {
                "identity": {"id": actor_identity_id, "type": "actor"},
                "role_id": "market",
            }
        )
        delivery = _RecordingImDelivery()
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda _role_id: [
                {
                    "identity_id": actor_identity_id,
                    "identity": {"id": actor_identity_id, "type": "actor"},
                    "role_id": "market",
                    "status": "online",
                }
            ],
            actor_reachability_checker=lambda *, target_identity_id: {
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {"identity_id": actor_identity_id},
            },
            actor_delivery_handler=delivery.deliver,
        )
        key = self._create_external_session(router)

        status, sent = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps(
                {
                    "target_identity_id": actor_identity_id,
                    "content": "ping",
                }
            ).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=sent)
        self.assertEqual(sent["delivery_status"], "accepted")
        self.assertEqual(sent["actor_handling_status"], "submitted")
        self.assertNotIn("next_cursor", sent)
        self.assertEqual(len(delivery.delivery_calls), 1)
        self.assertNotIn("target_role_id", delivery.delivery_calls[0])
        original_message_id = sent["message"]["id"]

        actor_client = im_client_module.ActorImClient(
            _ActorContext(identity_id=actor_identity_id, role_id="market", capabilities=delivery)
        )
        reply = actor_client.send({"content": "pong", "reply_to": original_message_id})

        self.assertTrue(reply.get("ok"), msg=reply)
        self.assertEqual(reply["message"]["reply_to"], original_message_id)
        self.assertEqual(reply["actor_handling_status"], "not_applicable")

        status, events = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=events)
        self.assertEqual([event["message_id"] for event in events["events"]], [reply["message"]["id"]])
        self.assertNotIn("next_cursor", events)

        status, repeated = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=repeated)
        self.assertEqual([event["message_id"] for event in repeated["events"]], [reply["message"]["id"]])

        status, acked = router.handle(
            "POST",
            "/api/im/events/ack",
            json.dumps({"event_id": reply["event_id"]}).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=acked)
        self.assertTrue(acked["ok"], msg=acked)

        status, after_ack = router.handle(
            "GET",
            "/api/im/events?wait_ms=0",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=after_ack)
        self.assertEqual(after_ack["events"], [])

        status, fetched = router.handle(
            "GET",
            f"/api/im/messages/{reply['message']['id']}",
            b"",
            {"Authorization": f"Bearer {key}"},
        )
        self.assertEqual(status, 200, msg=fetched)
        self.assertEqual(fetched["message"]["content"], "pong")
        self.assertEqual(fetched["message"]["reply_to"], original_message_id)

    def test_wake_bridge_derives_role_from_identity_profile_not_sender_payload(self) -> None:
        target_identity_id = "act-market-wake"
        target_role_id = "market"
        identities.save_actor_identity_profile(
            {
                "identity": {"id": target_identity_id, "type": "actor"},
                "role_id": target_role_id,
                "label": "Market wake",
            }
        )
        mailbox_calls: list[dict[str, Any]] = []

        def fake_check_reachability(*, target_identity_id: str, socket_path: Path | None = None) -> dict[str, Any]:
            self.assertEqual(target_identity_id, "act-market-wake")
            self.assertIsNone(socket_path)
            return {
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {
                    "identity_id": target_identity_id,
                    "role_id": "wrong",
                    "endpoint": {
                        "kind": "daemon_mailbox_socket",
                        "socket_path": "/tmp/buddyswitch-test-mailbox.sock",
                    },
                    "status": "online",
                },
            }

        def fake_request_mailbox(method: str, params: dict[str, Any], *, socket_path: Path) -> dict[str, Any]:
            mailbox_calls.append({"method": method, "params": params, "socket_path": str(socket_path)})
            return {"ok": True, "result": {"handling_status": "handled"}}

        result = im_actor_delivery.deliver(
            {
                "type": "im.message.created",
                "wake_id": "imwake-1",
                "target_identity_id": target_identity_id,
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "event_id": "imev-1",
            },
            check_reachability_fn=fake_check_reachability,
            request_mailbox_fn=fake_request_mailbox,
        )

        self.assertEqual(result["actor_handling_status"], "submitted")
        self.assertEqual(len(mailbox_calls), 1)
        self.assertEqual(mailbox_calls[0]["method"], "mailbox.local_trigger")
        self.assertEqual(mailbox_calls[0]["socket_path"], "/tmp/buddyswitch-test-mailbox.sock")
        self.assertNotIn("target_role_id", mailbox_calls[0]["params"]["payload"])
        self.assertEqual(
            mailbox_calls[0]["params"],
            {
                "identity_id": target_identity_id,
                "role_id": target_role_id,
                "type": "im.message.created",
                "payload": {"message_id": "msg-1", "conversation_id": "conv-1", "event_id": "imev-1"},
                "origin_id": "msg-1",
                "correlation_id": "imwake-1",
                "source_context": {"source": "central_im"},
            },
        )

    def test_wake_bridge_rejects_sender_supplied_target_role_id(self) -> None:
        payload = {
            "type": "im.message.created",
            "target_identity_id": "act-market-wake",
            "message_id": "msg-1",
            "conversation_id": "conv-1",
            "event_id": "imev-1",
        }
        payload["target_role_id"] = "market"

        result = im_actor_delivery.deliver(
            payload,
            check_reachability_fn=lambda **_kwargs: {"reachability_status": "online", "record": {}},
            request_mailbox_fn=lambda *_args, **_kwargs: {"ok": True},
        )

        self.assertEqual(result["actor_handling_status"], "handling_failed")
        self.assertIn("target_role_id is not accepted", result["error"])

    def test_wake_bridge_reaches_real_mailbox_socket_and_im_handler(self) -> None:
        target_identity_id = "act-market-wake"
        target_role_id = "market"
        identities.save_actor_identity_profile(
            {
                "identity": {"id": target_identity_id, "type": "actor"},
                "role_id": target_role_id,
            }
        )
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            dispatcher = _WakeHandlerDispatcher(identity_id=target_identity_id, role_id=target_role_id)
            server = daemon_mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_identity_id=target_identity_id,
                local_role_id=target_role_id,
                handlers=[],
                trigger_dispatcher=dispatcher,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)
            self.addCleanup(thread.join, 2)

            result = im_actor_delivery.deliver(
                {
                    "type": "im.message.created",
                    "wake_id": "imwake-socket",
                    "target_identity_id": target_identity_id,
                    "message_id": "msg-socket",
                    "conversation_id": "conv-socket",
                    "event_id": "imev-socket",
                },
                check_reachability_fn=lambda **_kwargs: {
                    "reachability_status": "online",
                    "record": {
                        "identity_id": target_identity_id,
                        "role_id": "wrong",
                        "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(socket_path)},
                    },
                },
            )
            server.close()
            thread.join(timeout=2)

        self.assertEqual(result["actor_handling_status"], "submitted", msg=result)
        self.assertEqual(result["handling_status"], "handled")
        self.assertEqual(len(dispatcher.triggers), 1)
        trigger = dispatcher.triggers[0]
        self.assertEqual(trigger.type, "im.message.created")
        self.assertEqual(trigger.origin_id, "msg-socket")
        self.assertEqual(trigger.correlation_id, "imwake-socket")
        self.assertEqual(trigger.payload, {"message_id": "msg-socket", "conversation_id": "conv-socket", "event_id": "imev-socket"})
        self.assertEqual(trigger.source_context, {"source": "central_im"})
        self.assertEqual(len(dispatcher.task_sys_instructions), 1)
        instruction = dispatcher.task_sys_instructions[0]
        self.assertEqual(instruction["type"], "start_side")
        self.assertEqual(instruction["actor_target"], {"actor_id": target_identity_id, "role_id": target_role_id})
        frame = instruction["frame"]
        self.assertEqual(frame["kind"], "task_sys.side_frame")
        self.assertEqual(frame["source"]["type"], "im.message.created")
        self.assertEqual(
            frame["source"]["ref"],
            {"message_id": "msg-socket", "conversation_id": "conv-socket", "event_id": "imev-socket"},
        )

    def test_actor_to_actor_send_writes_refs_and_reaches_target_local_runtime(self) -> None:
        source_identity_id = self._runtime_actor_id(role="dev", label="act-dev-integrated-send")
        target_identity_id = self._runtime_actor_id(role="market", label="act-market-integrated-target")
        target_role_id = "market"
        identities.save_actor_identity_profile(
            {
                "identity": {"id": target_identity_id, "type": "actor"},
                "role_id": target_role_id,
            }
        )

        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "target-mailbox.sock"
            dispatcher = _WakeHandlerDispatcher(identity_id=target_identity_id, role_id=target_role_id)
            server = daemon_mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_identity_id=target_identity_id,
                local_role_id=target_role_id,
                handlers=[],
                trigger_dispatcher=dispatcher,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)
            self.addCleanup(thread.join, 2)

            class _SourceCapabilities:
                def __init__(self) -> None:
                    self.delivery_calls: list[dict[str, Any]] = []

                def list_online_actors(self, *, role_id: str | None = None) -> dict[str, Any]:
                    raise AssertionError("message.send must not call list_online_actors")

                def check_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
                    return {
                        "reachability_status": "online",
                        "target_identity_id": target_identity_id,
                        "record": {"identity_id": target_identity_id},
                    }

                def deliver(self, payload: dict[str, Any]) -> dict[str, Any]:
                    self.delivery_calls.append(dict(payload))
                    return im_actor_delivery.deliver(
                        payload,
                        check_reachability_fn=lambda **_kwargs: {
                            "reachability_status": "online",
                            "record": {
                                "identity_id": target_identity_id,
                                "role_id": "wrong",
                                "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(socket_path)},
                            },
                        },
                    )

            capabilities = _SourceCapabilities()
            client = im_client_module.ActorImClient(
                _ActorContext(identity_id=source_identity_id, role_id="dev", capabilities=capabilities)
            )

            response = client.send({"target_identity_id": target_identity_id, "content": "integrated ping"})
            server.close()
            thread.join(timeout=2)

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["delivery_status"], "accepted")
        self.assertEqual(response["actor_handling_status"], "submitted")
        self.assertNotIn("wake_status", response)
        self.assertNotIn("target_role_id", response)
        message_ref = response["message"]
        message_id = message_ref["id"]
        conversation_id = message_ref["conversation_id"]
        event_id = response["event_id"]

        message_path = self.runtime_state_root / "im" / "messages" / f"{message_id}.json"
        self.assertTrue(message_path.is_file())
        message = json.loads(message_path.read_text(encoding="utf-8"))
        self.assertEqual(message["sender_identity"], {"id": source_identity_id, "type": "actor"})
        self.assertEqual(message["target_identity"], {"id": target_identity_id, "type": "actor"})
        self.assertEqual(message["content"], "integrated ping")

        self.assertEqual(
            capabilities.delivery_calls,
            [
                {
                    "type": "im.message.created",
                    "target_identity_id": target_identity_id,
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "event_id": event_id,
                }
            ],
        )
        self.assertEqual(len(dispatcher.triggers), 1)
        trigger = dispatcher.triggers[0]
        self.assertEqual(trigger.type, "im.message.created")
        self.assertEqual(trigger.target_identity_id, target_identity_id)
        self.assertEqual(trigger.target_role_id, target_role_id)
        self.assertEqual(trigger.payload, {"message_id": message_id, "conversation_id": conversation_id, "event_id": event_id})
        self.assertEqual(len(dispatcher.task_sys_instructions), 1)
        instruction = dispatcher.task_sys_instructions[0]
        self.assertEqual(instruction["actor_target"], {"actor_id": target_identity_id, "role_id": target_role_id})
        self.assertEqual(
            instruction["frame"]["source"]["ref"],
            {"message_id": message_id, "conversation_id": conversation_id, "event_id": event_id},
        )

    def test_wake_bridge_reports_offline_target_without_mailbox_request(self) -> None:
        mailbox_calls: list[dict[str, Any]] = []
        identities.save_actor_identity_profile(
            {
                "identity": {"id": "act-market-offline", "type": "actor"},
                "role_id": "market",
            }
        )

        result = im_actor_delivery.deliver(
            {
                "type": "im.message.created",
                "wake_id": "imwake-1",
                "target_identity_id": "act-market-offline",
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "event_id": "imev-1",
            },
            check_reachability_fn=lambda **_kwargs: {
                "reachability_status": "registered_offline",
                "record": None,
            },
            request_mailbox_fn=lambda *args, **kwargs: mailbox_calls.append({"args": args, "kwargs": kwargs}) or {},
        )

        self.assertEqual(result["actor_handling_status"], "target_not_online")
        self.assertEqual(result["runtime_target"], "none")
        self.assertEqual(mailbox_calls, [])

    def test_no_external_reply_loop_shortcuts_in_active_surfaces(self) -> None:
        active_surface = "\n".join(
            (
                (ROOT / "tools/launcher/web_management.py").read_text(encoding="utf-8"),
                (ROOT / "tools/launcher/assets/web-management/app.js").read_text(encoding="utf-8"),
                (ROOT / "scripts/env/tool_runtime/im_client.py").read_text(encoding="utf-8"),
                (ROOT / "scripts/env/tools/message/_impl.py").read_text(encoding="utf-8"),
            )
        )

        self.assertNotIn("/api/messages" + "/send", active_surface)
        self.assertNotIn("act-user" + "-local", active_surface)
        self.assertNotIn("WebUser" + "ActorRuntime", active_surface)
        self.assertNotIn("send_from_web" + "_user", active_surface)
        self.assertNotIn("message" + ".available", active_surface)


if __name__ == "__main__":
    unittest.main()
