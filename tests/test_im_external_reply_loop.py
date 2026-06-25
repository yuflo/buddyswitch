#!/usr/bin/env python3
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

from env.tool_runtime import daemon_client  # noqa: E402
from env.tool_runtime import im_client as im_client_module  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402
from tests.runtime_root_test_helper import RuntimeWorkspaceTestMixin  # noqa: E402
from tools.launcher import daemon_mailbox  # noqa: E402
from tools.launcher import im_http_router  # noqa: E402
from tools.launcher import im_wake_handler  # noqa: E402


class _ActorContext(dict[str, Any]):
    def __init__(self, actor_address: ActorAddress, daemon: Any) -> None:
        super().__init__(
            active_actor=actor_address.to_payload(),
            active_role=actor_address.role_id,
            manifest={"roles": [{"id": actor_address.role_id}]},
        )
        self.actor_address = actor_address
        self.daemon = daemon


class _WakeDaemon:
    def __init__(self) -> None:
        self.wake_calls: list[dict[str, Any]] = []

    def wake_im_actor(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.wake_calls.append(dict(payload))
        return {"wake_status": "submitted", "runtime_target": "parent", "error": None}


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
    def __init__(self) -> None:
        self.parent_prompts: list[dict[str, Any]] = []

    def parent_activity(self) -> dict[str, str]:
        return {"status": "idle"}

    def submit_parent_prompt(self, prompt: str, **kwargs: Any) -> None:
        self.parent_prompts.append({"prompt": prompt, **kwargs})


class _WakeHandlerDispatcher:
    def __init__(self, actor_address: ActorAddress) -> None:
        self.context = type("Context", (), {"actor_address": actor_address})()
        self.runtime = _Runtime()
        self.handler = im_wake_handler.ImMessageCreatedHandler()
        self.triggers: list[Any] = []

    def __call__(self, trigger: Any) -> dict[str, Any]:
        self.triggers.append(trigger)
        result = self.handler.handle(self.context, None, self.runtime, trigger)
        return {
            "accepted": True,
            "handled_count": 1 if result.status == "handled" else 0,
            "matched_count": 1,
            "handling_status": result.status,
        }


class ImExternalReplyLoopTests(RuntimeWorkspaceTestMixin, unittest.TestCase):
    def _register_external(self, router: im_http_router.ImHttpRouter) -> dict[str, Any]:
        status, registration = router.handle(
            "POST",
            "/api/im/external-participants",
            json.dumps({"client_kind": "script", "display_name": "local acceptance"}).encode("utf-8"),
            {},
        )
        self.assertEqual(status, 200, msg=registration)
        self.assertTrue(registration.get("ok"), msg=registration)
        return registration

    def test_external_send_actor_reply_to_external_visible_via_cursor(self) -> None:
        actor_address = ActorAddress(
            role_id="market",
            actor_id=self._runtime_actor_id(role="market", label="reply-loop"),
        )
        daemon = _WakeDaemon()
        router = im_http_router.ImHttpRouter(
            actor_lister=lambda _role_id: [{"actor_address": actor_address.to_payload(), "status": "online"}],
            wake_actor=daemon.wake_im_actor,
        )
        registration = self._register_external(router)
        token = registration["participant_token"]

        status, sent = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps(
                {
                    "to": {"kind": "actor", "actor_address": actor_address.to_payload()},
                    "content": "ping",
                }
            ).encode("utf-8"),
            {"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(status, 200, msg=sent)
        self.assertEqual(sent["delivery_status"], "accepted")
        self.assertEqual(sent["wake_status"], "submitted")
        self.assertEqual(len(daemon.wake_calls), 1)
        original_message_id = sent["message"]["id"]

        actor_client = im_client_module.ActorImClient(_ActorContext(actor_address, daemon))
        reply = actor_client.send({"content": "pong", "reply_to": original_message_id})

        self.assertTrue(reply.get("ok"), msg=reply)
        self.assertEqual(reply["message"]["reply_to"], original_message_id)
        self.assertEqual(reply["wake_status"], "not_applicable")

        status, events = router.handle(
            "GET",
            f"/api/im/events?cursor={sent['next_cursor']}&wait_ms=0",
            b"",
            {"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(status, 200, msg=events)
        self.assertEqual([event["message_id"] for event in events["events"]], [reply["message"]["id"]])

        status, fetched = router.handle(
            "GET",
            f"/api/im/messages/{reply['message']['id']}",
            b"",
            {"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(status, 200, msg=fetched)
        self.assertEqual(fetched["message"]["content"], "pong")
        self.assertEqual(fetched["message"]["reply_to"], original_message_id)

    def test_wake_bridge_submits_local_im_trigger_to_target_mailbox(self) -> None:
        target = {"role_id": "market", "actor_id": "act-market-wake"}
        mailbox_calls: list[dict[str, Any]] = []

        def fake_check_reachability(*, target_actor_address: dict[str, Any], socket_path: Path | None = None) -> dict[str, Any]:
            self.assertEqual(target_actor_address, target)
            self.assertIsNone(socket_path)
            return {
                "reachability_status": "online",
                "target_actor_address": target,
                "record": {
                    "actor_address": target,
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

        result = daemon_client.wake_im_actor(
            {
                "type": "im.message.created",
                "wake_id": "imwake-1",
                "target_actor_address": target,
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "event_id": "imev-1",
            },
            check_reachability_fn=fake_check_reachability,
            request_mailbox_fn=fake_request_mailbox,
        )

        self.assertEqual(result["wake_status"], "submitted")
        self.assertEqual(len(mailbox_calls), 1)
        self.assertEqual(mailbox_calls[0]["method"], "mailbox.local_trigger")
        self.assertEqual(mailbox_calls[0]["socket_path"], "/tmp/buddyswitch-test-mailbox.sock")
        self.assertEqual(
            mailbox_calls[0]["params"],
            {
                "actor_address": target,
                "type": "im.message.created",
                "payload": {"message_id": "msg-1", "conversation_id": "conv-1", "event_id": "imev-1"},
                "origin_id": "msg-1",
                "correlation_id": "imwake-1",
                "source_context": {"source": "central_im"},
            },
        )

    def test_wake_bridge_reaches_real_mailbox_socket_and_im_handler(self) -> None:
        target = {"role_id": "market", "actor_id": "act-market-wake"}
        with tempfile.TemporaryDirectory() as temp_root:
            socket_path = Path(temp_root) / "mailbox.sock"
            dispatcher = _WakeHandlerDispatcher(ActorAddress.from_payload(target))
            server = daemon_mailbox.DaemonMailboxServer(
                socket_path=socket_path,
                local_actor_address=target,
                handlers=[],
                trigger_dispatcher=dispatcher,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.close)
            self.addCleanup(thread.join, 2)

            result = daemon_client.wake_im_actor(
                {
                    "type": "im.message.created",
                    "wake_id": "imwake-socket",
                    "target_actor_address": target,
                    "message_id": "msg-socket",
                    "conversation_id": "conv-socket",
                    "event_id": "imev-socket",
                },
                check_reachability_fn=lambda **_kwargs: {
                    "reachability_status": "online",
                    "record": {
                        "actor_address": target,
                        "endpoint": {"kind": "daemon_mailbox_socket", "socket_path": str(socket_path)},
                    },
                },
            )
            server.close()
            thread.join(timeout=2)

        self.assertEqual(result["wake_status"], "submitted", msg=result)
        self.assertEqual(result["handling_status"], "handled")
        self.assertEqual(len(dispatcher.triggers), 1)
        trigger = dispatcher.triggers[0]
        self.assertEqual(trigger.type, "im.message.created")
        self.assertEqual(trigger.origin_id, "msg-socket")
        self.assertEqual(trigger.correlation_id, "imwake-socket")
        self.assertEqual(trigger.payload, {"message_id": "msg-socket", "conversation_id": "conv-socket", "event_id": "imev-socket"})
        self.assertEqual(trigger.source_context, {"source": "central_im"})
        self.assertEqual(len(dispatcher.runtime.parent_prompts), 1)
        self.assertIn('message__get with message_id="msg-socket"', dispatcher.runtime.parent_prompts[0]["prompt"])

    def test_wake_bridge_reports_offline_target_without_mailbox_request(self) -> None:
        mailbox_calls: list[dict[str, Any]] = []

        result = daemon_client.wake_im_actor(
            {
                "type": "im.message.created",
                "wake_id": "imwake-1",
                "target_actor_address": {"role_id": "market", "actor_id": "act-market-offline"},
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

        self.assertEqual(result["wake_status"], "target_not_online")
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
